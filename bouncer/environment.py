"""
environment.py — A faithful, controllable microarchitectural decision process (MDP)
for validating the Bouncer competence auditor.

Design philosophy
-----------------
Bouncer's guarantees (Lemma 1 safety floor; Prop 1 mimicry resistance) are
*environment-agnostic*: they rest only on (i) bounded per-decision reward and
(ii) the ability to randomly partition a shared resource into dueling pools.
Therefore a faithful abstract model of a learned microarchitectural controller
is sufficient to validate the auditor, which is the contribution of the paper.

We model the prefetcher setting (Pythia) as the anchor; replacement and memory
scheduling are obtained by changing the resource granularity and reward proxy.

Key abstractions
----------------
* Resource is partitioned into ``n_sets`` sets (cache sets / PC-hash buckets /
  banks). Each decision lands on one set.
* Each decision carries a latent **stress** u in [0, 1]: how far the *input* has
  been pushed toward the controller's decision boundary / off the validation
  manifold D_val. Stress is the single knob through which both benign drift and
  adversarial steering act. The auditor never observes u directly.
* The learned controller C earns expected reward mu_C(u), high in-distribution
  (small u), collapsing as u -> 1. The safe fallback pi0 earns a constant,
  stress-robust mu_0. This is exactly the §1 asymmetry: C has unbounded
  upside/downside, pi0 a bounded attack-resistant downside.
* Rewards are Bernoulli(mu/r_max) * r_max, so they are bounded in [0, r_max] and
  their per-window variance obeys Var <= r_max^2 / (4 m) exactly, which is what
  the §4 concentration bound assumes.

The environment also exposes Tier-A observable features x_t (a d-dim vector) and,
for online-learner controllers, a confidence/value signal — both functions of u
plus benign nuisance, so that a *mimicry* adversary can try to hold the
observable features in-distribution while still driving u (and hence Δ) down.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


# ---------------------------------------------------------------------------
# Controller competence model
# ---------------------------------------------------------------------------
@dataclass
class CompetenceModel:
    """Maps latent stress u in [0,1] to expected per-decision reward for the
    learned controller C and the safe fallback pi0.

    mu_C(u) = r_max * clip(a_C - b_C * u, 0, 1)      (collapses under stress)
    mu_0    = r_max * q0                              (flat, robust floor)

    With defaults: in-distribution (u~0) C earns 0.80*r_max vs floor 0.50*r_max
    (Δ ~ +0.30), and under full stress (u=1) C earns 0.10*r_max < floor
    (Δ ~ -0.40). The true competence crossing Δ=0 occurs at
    u* = (a_C - q0) / b_C.
    """

    r_max: float = 1.0
    a_C: float = 0.80      # C's in-distribution competence (fraction of r_max)
    b_C: float = 0.70      # how fast C collapses with stress
    q0: float = 0.50       # fallback competence floor (fraction of r_max)

    def mu_C(self, u: np.ndarray | float) -> np.ndarray | float:
        return self.r_max * np.clip(self.a_C - self.b_C * np.asarray(u, dtype=float), 0.0, 1.0)

    def mu_0(self, u: np.ndarray | float = 0.0) -> np.ndarray | float:
        # pi0 is stress-robust; u accepted for signature symmetry.
        return self.r_max * np.full(np.shape(np.asarray(u, dtype=float)), self.q0) \
            if np.ndim(u) else self.r_max * self.q0

    def delta_true(self, u: np.ndarray | float) -> np.ndarray | float:
        """Ground-truth per-decision competence advantage Δ = mu_C(u) - mu_0."""
        return self.mu_C(u) - self.r_max * self.q0

    @property
    def u_crossing(self) -> float:
        """Stress at which C's competence equals the floor (Δ = 0)."""
        return (self.a_C - self.q0) / self.b_C


# ---------------------------------------------------------------------------
# Scenario: how stress evolves over time and across sets
# ---------------------------------------------------------------------------
@dataclass
class Scenario:
    """A time- and set-indexed stress schedule plus the controller's online
    output observables. A scenario produces, for each decision, the set index,
    the latent stress on the *learned-controller path* of that set, and the
    benign nuisance for Tier-A features.

    Stress is decomposed as:
        u_set[s, t] = u_base(t) + u_attack[s, t]
    where u_base is the (benign) global regime — clean small, or a drift ramp —
    and u_attack is what the adversary injects on the sets it targets. The
    auditor's job is to detect when the *effective* Δ on the controller path
    falls below τ, regardless of which component caused it.
    """

    name: str
    n_sets: int = 256
    feature_dim: int = 16


# ---------------------------------------------------------------------------
# The MDP itself
# ---------------------------------------------------------------------------
@dataclass
class MicroArchEnv:
    """Steps a stream of decisions over ``n_sets`` sets.

    At each decision the caller supplies, per set, the latent stress on the
    learned-controller path. The env returns Bernoulli rewards for *both*
    policies on *every* set (the counterfactual is available to the simulator
    for ground-truth scoring, but the auditor only ever sees the reward of the
    policy actually run on each set — see SetDueling).
    """

    comp: CompetenceModel = field(default_factory=CompetenceModel)
    n_sets: int = 256
    feature_dim: int = 16
    seed: int = 0
    # IPC transfer: IPC = ipc_base + ipc_slope * reward_rate. Lets us report the
    # §10 systems metrics (clean tax, performance recovered, floor violation) in
    # IPC units from reward rates.
    ipc_base: float = 0.60
    ipc_slope: float = 1.40

    def __post_init__(self):
        self.rng = np.random.default_rng(self.seed)
        # Validation-time feature statistics (the frozen reference D_val sketch
        # is fit against draws from this distribution in tier_a).
        self._feat_mean = self.rng.normal(0, 1, size=self.feature_dim)
        self._feat_scale = 0.5 + 0.5 * self.rng.random(self.feature_dim)

    # --- reward draws -----------------------------------------------------
    def reward_C(self, u: np.ndarray) -> np.ndarray:
        p = self.comp.mu_C(u) / self.comp.r_max
        return (self.rng.random(np.shape(u)) < p).astype(float) * self.comp.r_max

    def reward_0(self, shape) -> np.ndarray:
        p = self.comp.q0
        return (self.rng.random(shape) < p).astype(float) * self.comp.r_max

    # --- observable Tier-A features --------------------------------------
    def features(self, u: np.ndarray) -> np.ndarray:
        """d-dim observable feature vector for a batch of decisions with stress u.

        Off-distribution stress nominally pushes the feature marginals (an OOD
        tripwire S_in can catch this). A *mimicry* adversary will later cancel
        this shift (see adversary.MimicryAdversary) to keep S_in blind while
        still driving u. Shape: (len(u), feature_dim).
        """
        u = np.atleast_1d(np.asarray(u, dtype=float))
        base = self._feat_mean + self._feat_scale * self.rng.normal(size=(len(u), self.feature_dim))
        # stress shifts the first few feature dims (the "off-manifold" signature)
        shift = np.zeros((len(u), self.feature_dim))
        shift[:, :4] = (u[:, None]) * 1.5
        return base + shift

    def confidence(self, u: np.ndarray) -> np.ndarray:
        """Decision confidence (max-Q margin / weighted-sum magnitude). Collapses
        as the input nears the decision boundary (large u). Tier-A S_dec watches
        this; it is *cheap* because Pythia/SHiP/perceptron compute it in HW."""
        u = np.atleast_1d(np.asarray(u, dtype=float))
        return np.clip(1.0 - u, 0.0, 1.0) + 0.05 * self.rng.normal(size=len(u))

    # --- IPC transfer -----------------------------------------------------
    def ipc(self, reward_rate: float) -> float:
        return self.ipc_base + self.ipc_slope * reward_rate
