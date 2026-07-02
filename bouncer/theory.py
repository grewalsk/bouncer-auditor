"""
theory.py — Numerical evaluation of the Bouncer guarantees.

Lemma 1 (Safety floor / bounded regret vs. fallback). The n_L Leader-C sets run C in
EVERY gate state (they must, so Delta-hat stays measurable), so the bound is THREE-term,
not two. With audit-exposure fractions phi_G = n_L/n_sets (GATED) and
phi_P = phi_G + rho_aud*(1 - (n_L+n_F)/n_sets) (PROBING), T_att drop-episode windows,
detection delay <= D w.p. >= 1-delta, false-alarm rate <= alpha, switch transient <= c_sw,
and N_ep drop episodes over horizon T, then w.p. >= 1 - delta*N_ep:

    Σ_t (r^{pi0}_t - r^{Bouncer}_t)  <=  N_ep*D*r_max  +  phi_P*T_att*r_max  +  alpha*T*c_sw
                                        (detection)     (audit exposure)     (false alarm)

i.e. R_Bouncer >= R_{pi0} - [ N_ep*D*r_max + phi_P*T_att*r_max + alpha*T*c_sw ].

The detection and false-alarm terms are the §4 CUSUM knobs (D, alpha are functions of pool
size n, decisions/window m, CUSUM H through sigma_Δ and the Siegmund ARL); the audit-exposure
term is a design constant (phi_P), linear in attack duration. regret_bound() composes the
detection and false-alarm terms; the exposure term is added by the caller (exp_theory,
exp_p1_floor, exp_floor_longattack). WARNING: the old two-term bound (no exposure) is FALSE
for long attacks; see exp_floor_longattack.py for the regression that caught it.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .cusum import siegmund_arl, detection_delay_approx, false_alarm_rate_per_window


@dataclass
class FloorBound:
    detection_term: float        # N_ep * D * r_max
    false_alarm_term: float      # alpha * T * c_sw
    total: float                 # sum
    D: float
    alpha: float


def regret_bound(*, r_max: float, N_ep: int, T: int, c_sw: float,
                 K: float, H: float, sigma_delta: float,
                 mean_signal_clean: float, delta_true_drop: float) -> FloorBound:
    """Compose Lemma 1's bound from the operating point.

    K, H            : Tier-B lower-CUSUM reference and threshold
    sigma_delta     : std of Δ̂ per window (from set_dueling.sigma_delta(m))
    mean_signal_clean : E[Δ̂] in-control (clean), used for ARL0/alpha
    delta_true_drop : true competence during a drop episode (< K), sets D
    """
    D = detection_delay_approx(K, H, delta_true_drop)
    alpha = false_alarm_rate_per_window(K, H, mean_signal_clean, sigma_delta)
    det = N_ep * D * r_max
    fa = alpha * T * c_sw
    return FloorBound(detection_term=det, false_alarm_term=fa, total=det + fa,
                      D=D, alpha=alpha)


def pareto_operating_points(*, r_max, n_L_grid, m, tau, gamma, H_grid,
                            mean_signal_clean, delta_true_drop):
    """Sweep (pool size n_L, CUSUM H) -> (sigma_Δ, ARL0, detection delay D).
    Returns a list of dicts forming the §9 Pareto frontier (overhead vs latency
    vs false-alarm)."""
    K = tau + gamma / 2.0
    pts = []
    for n_L in n_L_grid:
        n_F = n_L
        sigma = np.sqrt((r_max ** 2 / (4.0 * m)) * (1.0 / n_L + 1.0 / n_F))
        for H in H_grid:
            arl0 = siegmund_arl(K, H, mean_signal_clean, sigma)
            D = detection_delay_approx(K, H, delta_true_drop)
            pts.append(dict(n_L=n_L, n_F=n_F, H=H, sigma_delta=sigma,
                            ARL0=arl0, alpha=1.0 / max(arl0, 1.0), D=D,
                            storage_counters=n_L + n_F))
    return pts
