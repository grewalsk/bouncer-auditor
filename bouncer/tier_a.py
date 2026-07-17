"""
tier_a.py — Sampled Tier-A tripwires (§5). The architectural proposal places
their updates off the access path; this floating-point reference model does not
measure hardware area, energy, or timing.

Tier-A never gates on its own — it only escalates the gate to SUSPECT, which
raises Tier-B's duty cycle. Its false positives therefore cost a little energy,
never correctness.

Three signals:
  S_in  — input covariate shift. Frozen dense random projection with reference
          mean/std; online squared standardized displacement of the projected
          window mean. Spoofable because an adversary can hold those monitored
          marginals fixed — exactly the tripwire the mimicry adversary defeats.
  S_dec — decision-confidence collapse (entropy / max-Q margin / TD magnitude).
          Nearly free when the controller already computes confidence in HW
          (Pythia reward, SHiP/perceptron weighted-sum).
  S_res — innovation residual. A (d+2)-coefficient linear forward model
          r̂ = g(x,a) fit on D_val (features + action + bias); online residual
          e = r - r̂; two-sided CUSUM on e. Catches
          "the world responds differently than at validation" even when input
          marginals look clean — the architectural analogue of a Kalman
          innovation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

from .cusum import TwoSidedCusum


# ---------------------------------------------------------------------------
# S_in : covariate-shift sketch
# ---------------------------------------------------------------------------
class CovariateShiftSketch:
    """Random projection P (p hashes) + reference mean/cov of projected D_val.
    Online score = windowed Mahalanobis-ish energy of projected features vs
    reference. Cheap: p*d MACs on 1/k decisions; stores P (d x p) + p-vector
    reference statistics (~1-4 KB)."""

    def __init__(self, feature_dim: int, p: int = 8, seed: int = 0):
        rng = np.random.default_rng(seed)
        self.P = rng.normal(0, 1.0 / np.sqrt(feature_dim), size=(feature_dim, p))
        self.p = p
        self.ref_mean = None
        self.ref_std = None

    def fit_reference(self, X_val: np.ndarray):
        Z = X_val @ self.P
        self.ref_mean = Z.mean(axis=0)
        self.ref_std = Z.std(axis=0) + 1e-6

    def score(self, X_win: np.ndarray) -> float:
        """Windowed energy (mean standardized squared deviation) of projected
        features. ~0 in-distribution, grows under covariate shift."""
        Z = X_win @ self.P
        d = (Z.mean(axis=0) - self.ref_mean) / self.ref_std
        return float(np.mean(d * d))


# ---------------------------------------------------------------------------
# S_dec : decision-confidence collapse
# ---------------------------------------------------------------------------
class ConfidenceCollapse:
    """Tracks the running mean confidence and flags collapse relative to the
    validation reference. In silicon this reuses already-computed confidence."""

    def __init__(self):
        self.ref_mean = None

    def fit_reference(self, conf_val: np.ndarray):
        self.ref_mean = float(np.mean(conf_val))

    def score(self, conf_win: np.ndarray) -> float:
        """Confidence *drop* vs reference (>=0 means collapse). """
        return float(self.ref_mean - np.mean(conf_win))


# ---------------------------------------------------------------------------
# S_res : forward-model innovation residual
# ---------------------------------------------------------------------------
class InnovationResidual:
    """(d+2)-coefficient linear forward model r̂ = w·[x, a, 1] fit on D_val by least
    squares; online residual e = r - r̂. Two-sided CUSUM on e detects regime
    change invisible to input marginals."""

    def __init__(self, feature_dim: int, k: float = 0.05, H: float = 1.5):
        self.w = None
        self.feature_dim = feature_dim
        self.cusum = TwoSidedCusum(ref=0.0, k=k, H=H)

    def _design(self, X: np.ndarray, a: np.ndarray) -> np.ndarray:
        a = np.atleast_1d(a).reshape(-1, 1)
        ones = np.ones((len(X), 1))
        return np.hstack([X, a, ones])

    def fit_reference(self, X_val: np.ndarray, a_val: np.ndarray, r_val: np.ndarray):
        Phi = self._design(X_val, a_val)
        self.w, *_ = np.linalg.lstsq(Phi, r_val, rcond=None)
        self.ref_resid_std = float(np.std(r_val - Phi @ self.w)) + 1e-6

    def residual(self, X: np.ndarray, a: np.ndarray, r: np.ndarray) -> np.ndarray:
        Phi = self._design(X, a)
        return r - Phi @ self.w

    def score_and_update(self, X: np.ndarray, a: np.ndarray, r: np.ndarray) -> tuple[float, bool]:
        e = self.residual(X, a, r)
        mean_e = float(np.mean(e)) / self.ref_resid_std  # standardized
        fired = self.cusum.update(mean_e)
        return mean_e, fired


# ---------------------------------------------------------------------------
# Tier-A bundle
# ---------------------------------------------------------------------------
@dataclass
class TierAConfig:
    feature_dim: int = 16
    sample_rate_inv_k: int = 8     # update on 1/k decisions
    s_in_H: float = 0.30           # energy-distance CUSUM threshold
    s_in_k: float = 0.02
    s_dec_H: float = 0.30
    s_dec_k: float = 0.02
    s_res_H: float = 1.5
    s_res_k: float = 0.05


class TierA:
    def __init__(self, cfg: TierAConfig, seed: int = 0):
        self.cfg = cfg
        self.s_in = CovariateShiftSketch(cfg.feature_dim, p=8, seed=seed)
        self.s_dec = ConfidenceCollapse()
        self.s_res = InnovationResidual(cfg.feature_dim, k=cfg.s_res_k, H=cfg.s_res_H)
        # CUSUMs on windowed S_in / S_dec scores
        self.cusum_in = TwoSidedCusum(ref=0.0, k=cfg.s_in_k, H=cfg.s_in_H)
        self.cusum_dec = TwoSidedCusum(ref=0.0, k=cfg.s_dec_k, H=cfg.s_dec_H)
        self.last = {"S_in": 0.0, "S_dec": 0.0, "S_res": 0.0}

    def fit_reference(self, X_val, conf_val, a_val, r_val):
        self.s_in.fit_reference(X_val)
        self.s_dec.fit_reference(conf_val)
        self.s_res.fit_reference(X_val, a_val, r_val)

    def step_window(self, X_win, conf_win, a_win, r_win) -> tuple[bool, dict]:
        """Process one window of sampled decisions; return (escalate?, scores).
        escalate is True if ANY Tier-A CUSUM fires."""
        s_in = self.s_in.score(X_win)
        s_dec = self.s_dec.score(conf_win)
        s_res, fired_res = self.s_res.score_and_update(X_win, a_win, r_win)
        fired_in = self.cusum_in.update(s_in)
        fired_dec = self.cusum_dec.update(s_dec)
        self.last = {"S_in": s_in, "S_dec": s_dec, "S_res": s_res,
                     "fired_in": fired_in, "fired_dec": fired_dec, "fired_res": fired_res}
        return (fired_in or fired_dec or fired_res), self.last
