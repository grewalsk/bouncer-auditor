"""
set_dueling.py — Tier-B competence estimator via randomized-secret set-dueling.

This is the spine of Bouncer (§4). We repurpose the DIP/set-dueling idiom — long
present in silicon for *policy selection* — to instead measure *policy trust*.

Three pools over the controller's resource (cache sets / PC-hash buckets / banks),
reseeded every epoch from a hardware RNG and unobservable to software:

  * Leader-C  (n_L sets): always run by the learned controller C.
  * Leader-F  (n_F sets): always run by the fallback pi0.
  * Follower  (rest)    : runs whichever leader currently wins -> what the victim
                          mostly experiences.

Estimator:                 Δ̂_W = r̄_L  -  r̄_F
Concentration (Bernoulli/bounded rewards, m decisions/set/window):
                           Var(Δ̂_W) <= (r_max^2 / 4m) * (1/n_L + 1/n_F)
which is the central design dependency: pool size -> estimator variance ->
CUSUM threshold -> detection delay -> safety-floor slack.

Secrecy is load-bearing (Prop 1): an adversary who cannot see the L/F
assignment cannot degrade the Follower victim while keeping Leader-C clean.
``secret_known_frac`` models partial leakage of the assignment for the §8 / P4
secrecy ablation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple
import numpy as np


@dataclass
class SetDuelingConfig:
    n_sets: int = 256
    n_L: int = 32          # Leader-C sets
    n_F: int = 32          # Leader-F (fallback) sets
    reseed_period: int = 1  # epochs between reseeds (1 = every epoch)
    r_max: float = 1.0


class SetDueling:
    """Maintains the secret pool assignment and computes Δ̂ per window.

    The *simulator* knows the true assignment (it must, to route rewards); the
    *adversary* is given only a leaked fraction via ``leaked_leaderC_mask``.
    """

    def __init__(self, cfg: SetDuelingConfig, seed: int = 0):
        self.cfg = cfg
        self.hw_rng = np.random.default_rng(seed)  # the secret hardware RNG
        self.epoch = -1
        self._assign()

    def _assign(self):
        """Secret uniform partition of sets into Leader-C / Leader-F / Follower."""
        c = self.cfg
        perm = self.hw_rng.permutation(c.n_sets)
        self.leaderC = np.sort(perm[: c.n_L])
        self.leaderF = np.sort(perm[c.n_L : c.n_L + c.n_F])
        self.follower = np.sort(perm[c.n_L + c.n_F :])
        self.epoch += 1
        # boolean masks for fast routing
        self.is_leaderC = np.zeros(c.n_sets, dtype=bool); self.is_leaderC[self.leaderC] = True
        self.is_leaderF = np.zeros(c.n_sets, dtype=bool); self.is_leaderF[self.leaderF] = True
        self.is_follower = np.zeros(c.n_sets, dtype=bool); self.is_follower[self.follower] = True

    def maybe_reseed(self):
        if (self.epoch + 1) % self.cfg.reseed_period == 0:
            self._assign()

    # ------------------------------------------------------------------
    # Adversary's (partial) knowledge of the secret
    # ------------------------------------------------------------------
    def leaked_leaderC_mask(self, known_frac: float, adv_rng: np.random.Generator) -> np.ndarray:
        """Return a boolean mask of sets the adversary *believes* are Leader-C.

        known_frac in [0,1]: fraction of the true Leader-C set the adversary has
        correctly identified. The complement is filled with random false guesses
        of equal count, modelling an attacker with imperfect side information.
        known_frac=0 -> a uniformly random guess (no information);
        known_frac=1 -> exact knowledge (secrecy fully broken).
        """
        c = self.cfg
        n_known = int(round(known_frac * c.n_L))
        true_known = adv_rng.choice(self.leaderC, size=n_known, replace=False) if n_known > 0 else np.array([], int)
        remaining = np.setdiff1d(np.arange(c.n_sets), true_known)
        n_false = c.n_L - n_known
        false_guess = adv_rng.choice(remaining, size=n_false, replace=False) if n_false > 0 else np.array([], int)
        mask = np.zeros(c.n_sets, dtype=bool)
        mask[true_known] = True
        mask[false_guess] = True
        return mask

    # ------------------------------------------------------------------
    # The estimator
    # ------------------------------------------------------------------
    def estimate(self, reward_C_per_set: np.ndarray, reward_F_per_set: np.ndarray
                 ) -> Tuple[float, float, float]:
        """Δ̂_W = r̄_L - r̄_F over this window.

        reward_C_per_set[s] : mean controller-path reward on set s this window
        reward_F_per_set[s] : mean fallback-path reward on set s this window
        Only Leader-C sets contribute r̄_L (they ran C); only Leader-F sets
        contribute r̄_F (they ran pi0) — this is what makes Δ̂ a *measured*, not
        counterfactual, quantity.
        Returns (delta_hat, rbar_L, rbar_F).
        """
        rbar_L = float(np.mean(reward_C_per_set[self.is_leaderC]))
        rbar_F = float(np.mean(reward_F_per_set[self.is_leaderF]))
        return rbar_L - rbar_F, rbar_L, rbar_F

    # ------------------------------------------------------------------
    # Analytical variance (the §4 concentration bound)
    # ------------------------------------------------------------------
    def sigma_delta(self, m: int) -> float:
        """std(Δ̂) upper bound from the bounded-reward concentration:
        Var(Δ̂) <= (r_max^2/4m)(1/n_L + 1/n_F)."""
        c = self.cfg
        var = (c.r_max ** 2 / (4.0 * m)) * (1.0 / c.n_L + 1.0 / c.n_F)
        return float(np.sqrt(var))
