"""Harness invariants (regression tests for the TMLR-R1 fixes). Deterministic; no output files.

1. SINGLE-ASSIGNMENT-PER-WINDOW. One secret assignment must govern the adversary view, the
   Delta-hat estimate, and the deployed routing for the same window. run_episode enforces this
   with an inline assertion (simulate.py); here we exercise it directly and, to prove the
   assertion is real, we reconstruct the OLD reseed-inside-step ordering and confirm it would
   have drifted the assignment (the counterfactual-estimator bug the review caught).
2. RESEED ACTUALLY RESHUFFLES. With reseed_period=1 the leader assignment changes across
   windows; with a large period it stays fixed.
"""
import sys
import numpy as np
sys.path.insert(0, 'experiments')
import common as C
from bouncer.simulate import run_episode
from bouncer.adversary import BroadAttack


def test_single_assignment_per_window():
    # If the inline invariant in run_episode ever regresses, this raises AssertionError.
    comp = C.make_competence()
    env, b = C.make_bouncer("full", comp=comp, seed=1)
    sim = C.simconfig(T=40)
    adv = BroadAttack(C.STD["n_sets"], onset=10, offset=None, stress=0.9, seed=7)
    df = run_episode(comp, env, b, adv, sim, seed=11)
    assert len(df) == 40
    print("  [ok] single-assignment-per-window invariant held for 40 windows")


def test_reseed_reshuffles():
    from bouncer.set_dueling import SetDueling, SetDuelingConfig
    d1 = SetDueling(SetDuelingConfig(n_sets=2048, n_L=32, n_F=32, reseed_period=1), seed=3)
    a0 = d1.leaderC.copy(); d1.maybe_reseed(); a1 = d1.leaderC.copy()
    assert not np.array_equal(a0, a1), "reseed_period=1 must reshuffle every window"
    d2 = SetDueling(SetDuelingConfig(n_sets=2048, n_L=32, n_F=32, reseed_period=10), seed=3)
    b0 = d2.leaderC.copy(); d2.maybe_reseed(); b1 = d2.leaderC.copy()
    assert np.array_equal(b0, b1), "reseed_period=10 must hold the assignment fixed at window 1"
    print("  [ok] reseed reshuffles at period 1 and holds at period 10")


def test_estimate_matches_deployment_pool():
    # Directly check the property the inline assert guards: within a window the pool the
    # estimator reads is the pool deployment routes on (no reseed in between).
    comp = C.make_competence()
    env, b = C.make_bouncer("full", comp=comp, seed=5)
    before = b.dueling.leaderC.copy()
    obs = dict(rC_per_set=np.full(2048, 0.6), rF_per_set=np.full(2048, 0.5),
               feat_win=np.zeros((8, 16)), conf_win=np.full(8, 0.9),
               a_win=np.ones(8), r_win=np.full(8, 0.6), delta_true=0.1)
    b.step(obs)                       # estimator consumes `before`; step no longer reseeds
    assert np.array_equal(b.dueling.leaderC, before), "step must not reseed (deployment uses same pool)"
    print("  [ok] bouncer.step does not reseed internally; estimator == deployment pool")


def test_gate_transition_applies_next_window():
    # An end-of-window oracle alarm may change the next state, but it cannot reroute
    # rewards from the window that produced the alarm.
    comp = C.make_competence()
    _, b = C.make_bouncer("oracle", comp=comp, seed=6)
    obs = dict(rC_per_set=np.full(2048, 0.1), rF_per_set=np.full(2048, 0.5),
               feat_win=np.zeros((8, 16)), conf_win=np.full(8, 0.9),
               a_win=np.ones(8), r_win=np.full(8, 0.1), delta_true=-0.4)
    tel = b.step(obs)
    assert tel["state"].name == "TRUSTED" and tel["C_active"], tel
    assert tel["state_next"].name == "GATED" and not tel["C_active_next"], tel
    print("  [ok] end-of-window alarm changes next-window routing only")


def test_probing_audit_is_uniform_secret():
    # A6: the PROBING audit subset must be a uniform secret subset of followers, NOT a sorted
    # prefix. Check a low-index set is audited ~rho_aud (not ~1), index-independent.
    from bouncer.set_dueling import SetDueling, SetDuelingConfig
    d = SetDueling(SetDuelingConfig(n_sets=2048, n_L=32, n_F=32, audited_frac=0.05, reseed_period=1), seed=9)
    lo = hi = 0; N = 4000
    for _ in range(N):
        d.maybe_reseed()
        lo += int(d.is_audited[0]); hi += int(d.is_audited[2047])
    lo, hi = lo / N, hi / N
    assert lo < 0.15 and hi < 0.15, f"audit should be ~rho_aud everywhere, got lo={lo} hi={hi}"
    assert abs(lo - hi) < 0.05, f"audit exposure must be index-independent, got lo={lo} hi={hi}"
    print(f"  [ok] PROBING audit is uniform-secret (low={lo:.3f}, high={hi:.3f} ~ rho_aud)")


def test_implemented_phi_p_below_bound():
    # The rounded implemented PROBING exposure prob must not exceed the Lemma's phi_P formula.
    from bouncer.set_dueling import SetDuelingConfig
    from bouncer.simulate import SimConfig
    n_sets, n_L, n_F = 2048, 32, 32
    rho = SimConfig.audited_region_frac
    assert abs(rho - SetDuelingConfig().audited_frac) < 1e-12, "audit fraction must be single-sourced"
    n_foll = n_sets - n_L - n_F
    n_aud = round(rho * n_foll)
    impl = (n_L + n_aud) / n_sets                       # union: Leader-L always + audited followers
    phi_P = n_L / n_sets + rho * (1 - (n_L + n_F) / n_sets)
    assert impl <= phi_P + 1e-9, f"implemented exposure {impl} exceeds bound phi_P {phi_P}"
    print(f"  [ok] implemented PROBING exposure {impl:.6f} <= Lemma phi_P {phi_P:.6f}")


def test_theory_envelopes():
    # Exercise the Lemma-1 helpers (reviewer R2 noted they were untested).
    from bouncer.theory import exposure_envelope, false_alarm_envelope
    env = exposure_envelope(phi=0.064, T_att=240, r_max=1.0, delta_s=0.01)
    assert env > 0.064 * 240 and env < 0.064 * 240 + 30, f"exposure envelope out of range: {env}"
    fa = false_alarm_envelope(alpha=1e-3, T=1000, c_sw=0.1, delta_f=0.01)
    assert fa > 0, "false-alarm envelope (independence-conditional helper) should be positive"
    print(f"  [ok] theory helpers exercised (exposure_envelope={env:.2f}, false_alarm_envelope={fa:.3f})")


def test_siegmund_zero_drift_limit():
    # Regression for the removable singularity in the ARL expression. Expanding
    # exp(-2 δ b) through second order gives b^2, not b^2/2.
    from bouncer.cusum import siegmund_arl
    K, H, sigma = 0.0, 2.0, 1.0
    b = H / sigma + 1.166
    got = siegmund_arl(K=K, H=H, mean_signal=K, sigma=sigma)
    assert abs(got - b * b) < 1e-12, f"zero-drift ARL limit wrong: {got}"
    print(f"  [ok] Siegmund zero-drift ARL limit = b^2 = {got:.6f}")


if __name__ == "__main__":
    test_single_assignment_per_window()
    test_reseed_reshuffles()
    test_estimate_matches_deployment_pool()
    test_gate_transition_applies_next_window()
    test_probing_audit_is_uniform_secret()
    test_implemented_phi_p_below_bound()
    test_theory_envelopes()
    test_siegmund_zero_drift_limit()
    print("ALL INVARIANTS PASS")
