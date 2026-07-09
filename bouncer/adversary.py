"""
adversary.py — Scenarios and adversaries (§2 threat model, §10 conditions).

Every scenario produces, per window, a per-set latent stress vector ``u_C`` on
the *controller path* (what C experiences if run on that set), plus flags telling
the simulator how the observable Tier-A signals behave. Stress u in [u_boost, 1]:
  u ~ 0      -> in-distribution, C competent (mu_C ~ 0.77 r_max)
  u -> 1     -> boundary / off-manifold, C collapses (mu_C -> 0.1 r_max)
  u < 0      -> "super-easy" inputs, C reward boosted toward r_max (used by the
                redistributive covert attacker to preserve aggregate counters)

Two Tier-A behaviours encode the §5 spoofability asymmetry:
  suppress_features=False : input marginals shift with |stress| (S_in can see it)
  suppress_features=True  : adversary crafts boundary-seeking inputs whose
                            *marginals* stay in-distribution (S_in blind) -- this
                            is the spoof S_in cannot resist (§5: "adversary can
                            hold marginals fixed").
S_res (reward-vs-prediction residual) always reflects the *realized reward*, so
it remains a harder signal than S_in unless the adversary also preserves the
aggregate reward (the redistributive RegionalCovertAttack does exactly that).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class Window:
    """What an adversary emits each window."""
    u_C: np.ndarray                  # (n_sets,) stress on controller path
    suppress_features: bool = False  # True -> S_in held in-distribution (spoof)
    label_attack: bool = False       # ground-truth: is this an attack window?


# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------
class Clean:
    name = "clean"

    def __init__(self, n_sets: int, base_stress: float = 0.05, seed: int = 0):
        self.n_sets = n_sets
        self.base = base_stress
        self.rng = np.random.default_rng(seed)

    def window(self, t: int, dueling=None, gate_state=None) -> Window:
        u = self.base + 0.02 * self.rng.standard_normal(self.n_sets)
        return Window(np.clip(u, 0, 1), suppress_features=False, label_attack=False)


# ---------------------------------------------------------------------------
# Benign drift  (slow, phase-correlated, self-consistent new regime)
# ---------------------------------------------------------------------------
class BenignDrift:
    name = "benign-drift"

    def __init__(self, n_sets: int, onset: int, slope: float = 0.04,
                 final: float = 0.85, base: float = 0.05, seed: int = 0):
        self.n_sets = n_sets
        self.onset = onset
        self.slope = slope
        self.final = final
        self.base = base
        self.rng = np.random.default_rng(seed)

    def window(self, t: int, dueling=None, gate_state=None) -> Window:
        if t < self.onset:
            lvl = self.base
        else:
            lvl = min(self.final, self.base + self.slope * (t - self.onset))
        u = lvl + 0.02 * self.rng.standard_normal(self.n_sets)
        # drift is a *valid new regime*: features shift self-consistently (S_in
        # sees it). It is genuine competence loss, not an attack.
        attack = False
        return Window(np.clip(u, 0, 1), suppress_features=False, label_attack=attack)


# ---------------------------------------------------------------------------
# Broad attack  (naive DoS: drive every set toward the boundary, abruptly)
# ---------------------------------------------------------------------------
class BroadAttack:
    name = "broad-attack"

    def __init__(self, n_sets: int, onset: int, stress: float = 0.9,
                 base: float = 0.05, pulse: Optional[tuple] = None,
                 offset: Optional[int] = None, seed: int = 0):
        self.n_sets = n_sets
        self.onset = onset
        self.offset = offset      # attack ends at this window (None = never)
        self.stress = stress
        self.base = base
        self.pulse = pulse  # (period, duty) to pulse the attack on/off
        self.rng = np.random.default_rng(seed)

    def window(self, t: int, dueling=None, gate_state=None) -> Window:
        active = t >= self.onset and (self.offset is None or t < self.offset)
        if active and self.pulse is not None:
            period, duty = self.pulse
            active = ((t - self.onset) % period) < int(duty * period)
        lvl = self.stress if active else self.base
        u = lvl + 0.02 * self.rng.standard_normal(self.n_sets)
        # naive attack moves input marginals (it is not trying to be stealthy):
        return Window(np.clip(u, 0, 1), suppress_features=False, label_attack=active)


# ---------------------------------------------------------------------------
# Mimicry attack (adaptive): degrade C's aggregate competence while holding the
# *input-distribution* tripwire S_in blind. Defeats "input-OOD-only" baselines;
# full Bouncer still sees it via S_res + Tier-B competence.  (Headline A.)
# ---------------------------------------------------------------------------
class MimicryAttack:
    name = "mimicry-attack"

    def __init__(self, n_sets: int, onset: int, stress: float = 0.9,
                 base: float = 0.05, offset: Optional[int] = None, seed: int = 0):
        self.n_sets = n_sets
        self.onset = onset
        self.offset = offset
        self.stress = stress
        self.base = base
        self.rng = np.random.default_rng(seed)

    def window(self, t: int, dueling=None, gate_state=None) -> Window:
        active = t >= self.onset and (self.offset is None or t < self.offset)
        lvl = self.stress if active else self.base
        u = lvl + 0.02 * self.rng.standard_normal(self.n_sets)
        # The defining capability: boundary-seeking inputs whose MARGINALS stay
        # in-distribution -> S_in cannot see the degradation.
        return Window(np.clip(u, 0, 1), suppress_features=active, label_attack=active)


# ---------------------------------------------------------------------------
# Regional covert attack (strongest): degrade a victim region while holding the
# *input marginals* (S_in) in-distribution and sparing the sets it believes are
# Leader-C. Detection rests entirely on the SECRET per-region set-dueling, and
# only while the assignment is secret. ``known_frac`` = leaked fraction of the
# secret (the §8/P4 secrecy ablation; empirical Prop 1).
#
# NOTE on faithfulness: this models an adversary that suppresses the *input*
# tripwire (S_in) and spares guessed leaders. It does NOT fully preserve the
# aggregate reward (the region is a fraction of the resource and only ~n_L*|R|/
# n_sets leaders fall inside it), so a global Δ̂ would barely move — which is
# exactly why detection requires per-region dueling. The headline holds because
# at full leakage (f=1) the spared leaders keep Δ̂_R above τ regardless.
# ---------------------------------------------------------------------------
class RegionalCovertAttack:
    name = "regional-covert"

    def __init__(self, n_sets: int, region: np.ndarray, onset: int,
                 sink_stress: float = 0.9, known_frac: float = 0.0,
                 base: float = 0.05, seed: int = 0):
        self.n_sets = n_sets
        self.region = np.asarray(region)
        self.onset = onset
        self.sink = sink_stress
        self.known_frac = known_frac
        self.base = base
        self.rng = np.random.default_rng(seed)

    def window(self, t: int, dueling=None, gate_state=None) -> Window:
        u = self.base + 0.02 * self.rng.standard_normal(self.n_sets)
        active = t >= self.onset
        if active and dueling is not None:
            # adversary's (partial) belief about which region sets are Leader-C
            believed_leaderC = dueling.leaked_leaderC_mask(self.known_frac, self.rng)
            for s in self.region:
                if believed_leaderC[s]:
                    # spare guessed-leaders: keep them clean (and slightly boost
                    # to preserve aggregate reward) so Δ̂ stays high
                    u[s] = -0.10
                else:
                    # sink the victim sets
                    u[s] = self.sink
        return Window(np.clip(u, -0.286, 1.0),
                      suppress_features=active,   # marginals held in-distribution
                      label_attack=active)


# ---------------------------------------------------------------------------
# Boiling-frog attack: a *very slow*, stealthy degradation designed to keep the
# per-window change small so a change detector cannot trigger on the increment.
# The headline question (threat-reviewer §13): can a slow attack stay under the
# CUSUM? Answer: no -- a one-sided CUSUM integrates the *level* (K - Δ̂), not the
# slope, so once Δ̂ < K the statistic accumulates regardless of how slowly it got
# there. We measure the extra regret accrued during the slow descent.
# ---------------------------------------------------------------------------
class BoilingFrogAttack:
    name = "boiling-frog"

    def __init__(self, n_sets: int, onset: int, slope: float = 0.006,
                 final_stress: float = 0.95, base: float = 0.05, seed: int = 0):
        self.n_sets = n_sets
        self.onset = onset
        self.slope = slope            # stress increase per window (tiny)
        self.final = final_stress
        self.base = base
        self.rng = np.random.default_rng(seed)

    def window(self, t: int, dueling=None, gate_state=None) -> Window:
        if t < self.onset:
            lvl = self.base
        else:
            lvl = min(self.final, self.base + self.slope * (t - self.onset))
        u = lvl + 0.015 * self.rng.standard_normal(self.n_sets)
        active = lvl > self.base + 0.02
        # stealthy: hold input marginals in-distribution (the attacker's choice)
        return Window(np.clip(u, 0, 1), suppress_features=active, label_attack=active)


# ---------------------------------------------------------------------------
# PROBING-exploit attack (closed-loop): the attacker observes the gate and backs
# off whenever Bouncer is GATED or PROBING (to pass the audit), then resumes once
# TRUSTED -- the classic "wait out the cooldown" strategy. Bouncer's *measured*
# re-trust (PROBING audits Δ̂, not a timer) + exponential dwell backoff bound the
# fraction of windows the victim is actually harmed, and shrink it over time.
# ---------------------------------------------------------------------------
class ProbingExploitAttack:
    name = "probing-exploit"

    def __init__(self, n_sets: int, onset: int, stress: float = 0.92,
                 base: float = 0.05, seed: int = 0):
        self.n_sets = n_sets
        self.onset = onset
        self.stress = stress
        self.base = base
        self.rng = np.random.default_rng(seed)

    def window(self, t: int, dueling=None, gate_state=None) -> Window:
        gname = getattr(gate_state, "name", None)
        # back off while Bouncer is auditing / fallback-active; attack when trusted
        attacking = (t >= self.onset) and (gname in (None, "TRUSTED", "SUSPECT"))
        lvl = self.stress if attacking else self.base
        u = lvl + 0.02 * self.rng.standard_normal(self.n_sets)
        return Window(np.clip(u, 0, 1), suppress_features=attacking, label_attack=attacking)
