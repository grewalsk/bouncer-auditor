"""
cusum.py — CUSUM change detectors with worked-through ARL constants.

Tier-B uses a one-sided *lower* CUSUM on Δ̂_W to catch a downward shift of true
competence below the trust threshold τ (§4):

    C_t^-  = max(0,  C_{t-1}^-  + (K - Δ̂_W) )         K = τ + γ_detect/2
    alarm  when C_t^- > H

Tier-A uses two-sided CUSUMs on its sketch scores / innovation residual.

ARL theory (Siegmund's approximation)
-------------------------------------
Treat per-window increments of the lower CUSUM as g_t = (K - Δ̂_W), i.i.d. with
mean μ_g = K - E[Δ̂] and std σ_Δ. For a one-sided CUSUM that accumulates g_t and
alarms at threshold H, the average run length is

    ARL(δ) ≈ ( exp(-2 δ b) + 2 δ b - 1 ) / ( 2 δ^2 )          (Siegmund 1985)

with standardized drift  δ = μ_g / σ_Δ  and corrected boundary
    b = H/σ_Δ + 1.166.
The 1.166 is the Siegmund overshoot/ladder-height correction for a Brownian
approximation of the discrete walk.

In-control (Δ̂ ≈ E_clean, well above K so μ_g < 0): δ < 0 -> ARL0 grows
*exponentially* in H/σ_Δ  =>  rare false alarms.
Out-of-control (Δ̂ drops below K so μ_g > 0): δ > 0 -> short ARL1 = detection
delay D. For a clean positive drift, D ≈ H / μ_g = H / (K - Δ_true), the
deterministic-drift limit of the formula. Both regimes are validated empirically
in experiments/exp_theory.py.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------
@dataclass
class LowerCusum:
    """One-sided lower CUSUM: detects a *decrease* of the monitored signal.

    Repeated-CUSUM semantics: the statistic resets to 0 immediately after it
    raises an alarm, so it is armed for the *next* change instead of latching
    high after a long excursion (a latched statistic would re-fire for hundreds
    of windows after the signal recovers, preventing re-trust)."""
    K: float          # reference value (slack), here τ + γ/2
    H: float          # decision threshold
    C: float = 0.0    # running statistic
    auto_reset: bool = True

    def update(self, x: float) -> bool:
        self.C = max(0.0, self.C + (self.K - x))
        if self.C > self.H:
            if self.auto_reset:
                self.C = 0.0
            return True
        return False

    def reset(self):
        self.C = 0.0


@dataclass
class TwoSidedCusum:
    """Two-sided CUSUM for Tier-A residual/score monitors (innovation S_res,
    covariate-shift S_in). Detects a shift of either sign by ``k`` from the
    reference mean ``ref``."""
    ref: float
    k: float
    H: float
    Cp: float = 0.0
    Cn: float = 0.0
    auto_reset: bool = True

    def update(self, x: float) -> bool:
        d = x - self.ref
        self.Cp = max(0.0, self.Cp + d - self.k)
        self.Cn = max(0.0, self.Cn - d - self.k)
        if self.Cp > self.H or self.Cn > self.H:
            if self.auto_reset:
                self.Cp = self.Cn = 0.0
            return True
        return False

    def reset(self):
        self.Cp = self.Cn = 0.0


# ---------------------------------------------------------------------------
# ARL theory (Siegmund approximation) — worked constants
# ---------------------------------------------------------------------------
def siegmund_arl(K: float, H: float, mean_signal: float, sigma: float) -> float:
    """Average run length of a one-sided lower CUSUM accumulating (K - x),
    where x ~ (mean_signal, sigma).

    Standardized drift of the increment g = K - x:  δ = (K - mean_signal)/sigma.
    Returns ARL using Siegmund's corrected-boundary approximation. For δ < 0
    (in-control, signal well above K) this is the (large) ARL0; for δ > 0
    (out-of-control) it is the (small) detection delay.
    """
    if sigma <= 0:
        sigma = 1e-12
    delta = (K - mean_signal) / sigma
    b = H / sigma + 1.166
    if abs(delta) < 1e-9:
        # limit of the formula as δ -> 0 is b^2/2
        return b * b / 2.0
    expo = -2.0 * delta * b
    # In-control (δ<0) the exponential term dominates and ARL0 is astronomically
    # large; clamp the exponent to avoid overflow while preserving monotonicity.
    expo = min(expo, 700.0)
    val = (np.exp(expo) + 2.0 * delta * b - 1.0) / (2.0 * delta * delta)
    return float(min(val, 1e18))


def detection_delay_approx(K: float, H: float, delta_true: float) -> float:
    """Deterministic-drift INITIAL detection delay D_det ≈ H / (K - Δ_true) for Δ_true < K.

    The strong-drift limit of the Siegmund formula — an APPROXIMATION of the mean initial
    delay, not an upper bound. It equals A2's D (expected fully-open windows per episode,
    which also counts false re-trust) only in the reseeded near-i.i.d. regime where
    re-trust ~ 0, as measured in exp_retrust.py; a correlated audit inflates the true D."""
    margin = K - delta_true
    if margin <= 0:
        return np.inf
    return H / margin


def false_alarm_rate_per_window(K: float, H: float, mean_signal: float, sigma: float) -> float:
    """α per window = 1 / ARL0, with ARL0 from siegmund_arl in the in-control
    regime (mean_signal > K so δ < 0)."""
    arl0 = siegmund_arl(K, H, mean_signal, sigma)
    return 1.0 / max(arl0, 1.0)
