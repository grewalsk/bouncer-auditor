"""
theory.py — Numerical evaluation of the Bouncer guarantees.

Lemma 1 (Safety floor / bounded regret vs. fallback). The n_L Leader-C sets run C in
EVERY gate state (they must, so Delta-hat stays measurable), so the bound is THREE-term,
not two. With audit-exposure fractions phi_G = n_L/n_sets (GATED) and
phi_P = phi_G + rho_aud*(1 - (n_L+n_F)/n_sets) (PROBING), T_att drop-episode windows,
detection delay <= D w.p. >= 1-delta, per-window false-alarm probability <= alpha, switch
transient <= c_sw, and N_ep drop episodes over horizon T:

    E[ Σ_t (r^{pi0}_t - r^{Bouncer}_t) ]  <=  N_ep*D*r_max  +  phi_P*T_att*r_max  +  alpha*T*c_sw
                                             (detection)      (audit exposure)      (false alarm)

Two subtleties the earlier statement got wrong (TMLR-R1 review), now fixed:

  (A) TRAFFIC-WEIGHTING + SAMPLER RANDOMNESS. The exposure term is the *traffic* on the
      Leader-C sets, not their set fraction. A1-A5 do not bound per-set traffic, so the
      per-window bound phi*r_max is FALSE under concentrated traffic (a single hot set tagged
      Leader-C -> regret r_max; see exp_floor_traffic.py, ~15.6x violation). It is repaired by
      the *secret sampler*: each set is Leader-C w.p. phi_G independent of its traffic, so for
      ANY traffic E[per-window exposure] <= phi_G*r_max (phi_P PROBING). Over T_att
      INDEPENDENTLY reseeded windows the total exposure is a sum of independent [0,r_max]
      variables, so by Hoeffding, w.p. >= 1-delta_s,
          Sum_exposure <= phi_P*T_att*r_max + r_max*sqrt(T_att*ln(1/delta_s)/2)   (o(T_att) slack).
      exposure_envelope() returns this high-probability envelope.

  (B) FALSE-ALARM CONCENTRATION. A3 gives a per-window false-alarm *probability* alpha, so the
      realized false-alarm count over T windows is random; alpha*T is its EXPECTATION. The
      high-probability count is alpha*T + sqrt(T*ln(1/delta_f)/2) (Hoeffding on independent
      window alarms). The bound above is stated in expectation; the high-probability form adds
      the two sqrt slacks and unions the sampler/detection/false-alarm failures into the total
      probability 1 - delta*N_ep - delta_s - delta_f.

The detection and false-alarm terms are the §4 CUSUM knobs (D, alpha are functions of pool
size n, decisions/window m, CUSUM H through sigma_Δ and the Siegmund ARL); the audit-exposure
term is a design constant (phi_P), linear in attack duration. regret_bound() composes the
detection and false-alarm terms; the exposure term is added by the caller (exp_theory,
exp_p1_floor, exp_floor_longattack, exp_floor_traffic). WARNING: the old two-term bound (no
exposure) is FALSE for long attacks; see exp_floor_longattack.py for the regression that
caught it, and exp_floor_traffic.py for the traffic-weighting counterexample and repair.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .cusum import siegmund_arl, detection_delay_approx, false_alarm_rate_per_window


def exposure_envelope(*, phi: float, T_att: int, r_max: float, delta_s: float = 0.01) -> float:
    """High-probability audit-exposure envelope, traffic-agnostic (Lemma-1 subtlety A).

    Over T_att independently-reseeded windows the total exposure regret is a sum of independent
    [0, r_max] variables with per-window mean <= phi*r_max, so by Hoeffding it is at most
        phi*T_att*r_max + r_max*sqrt(T_att*ln(1/delta_s)/2)
    with probability >= 1 - delta_s, for ANY per-set traffic distribution. The sqrt slack is the
    sampler randomness the old deterministic phi*T_att*r_max statement omitted."""
    mean = phi * T_att * r_max
    slack = r_max * float(np.sqrt(T_att * np.log(1.0 / delta_s) / 2.0))
    return mean + slack


def false_alarm_envelope(*, alpha: float, T: int, c_sw: float, delta_f: float = 0.01) -> float:
    """High-probability false-alarm regret (Lemma-1 subtlety B): alpha*T is the EXPECTED count;
    the count concentrates as alpha*T + sqrt(T*ln(1/delta_f)/2) by Hoeffding on independent
    per-window alarms, so the regret is at most (alpha*T + sqrt(T*ln(1/delta_f)/2))*c_sw."""
    count = alpha * T + float(np.sqrt(T * np.log(1.0 / delta_f) / 2.0))
    return count * c_sw


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
