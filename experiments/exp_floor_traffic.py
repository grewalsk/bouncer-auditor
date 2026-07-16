"""Traffic-weighted audit-exposure: the Lemma-1 counterexample, the sorted-prefix bug, and the repair.

Lemma 1's audit-exposure term charges each drop window the *traffic* on the sets still running C,
not their set count. Assumptions A1-A5 do not bound per-set traffic, so under concentrated traffic
the per-window regret can reach r_max. The secret sampler is what turns this into a bounded
EXPECTATION -- but only if every set is exposed with probability <= phi_P INDEPENDENT of its
traffic. This script tests that on the ACTUAL routing (bouncer.set_dueling.SetDueling), not a
surrogate, and exercises both GATED (Leader-C) exposure and PROBING (audited-follower) exposure.

Three things are measured:
 (1) COUNTEREXAMPLE (concentrated traffic breaks the naive per-window bound): with all traffic on
     one set, the event that the secret sampler tags it Leader-C (prob phi_G) makes the whole
     window run C, so realized one-window regret is r_max -- a 1/phi_P ~ 15.6x violation of the
     naive per-window phi_P allowance.
 (2) THE SORTED-PREFIX BUG (reviewer R2): if PROBING audited `sorted(followers)[:n_aud]`, a
     low-index hot set is exposed almost deterministically (P ~ 1 - n_L/n_sets), NOT phi_P. The
     fix draws a secret UNIFORM audit subset (set_dueling.is_audited); we measure both the buggy
     sorted-prefix probability and the fixed uniform probability, at low AND high index.
 (3) THE REPAIR HOLDS: with the fixed routing, E[exposure] = phi_G (GATED) / <= phi_P (PROBING)
     for ANY traffic; per-window exposures are bounded in [0, r_max] with conditional mean
     <= phi_P*r_max under the fresh secret draw (they need not be independent under history-
     adaptive traffic), so the total concentrates under the Azuma-Hoeffding envelope
     phi_P*T_att*r_max + r_max*sqrt(T_att/2 ln(1/delta_s)).

Deterministic; emits results/floor_traffic.json + figures/floor_traffic.pdf.
"""
import sys, json
import numpy as np
sys.path.insert(0, 'experiments')
import common as C
import matplotlib.pyplot as plt
from bouncer.set_dueling import SetDueling, SetDuelingConfig

N_SETS, N_L, N_F = 2048, 32, 32
RHO_AUD = 0.05
R_MAX = 1.0
PHI_G = N_L / N_SETS
PHI_P = PHI_G + RHO_AUD * (1 - (N_L + N_F) / N_SETS)


def cfg():
    return SetDuelingConfig(n_sets=N_SETS, n_L=N_L, n_F=N_F, audited_frac=RHO_AUD, reseed_period=1)


def main():
    C.setstyle()

    # --- (1) single-window counterexample: concentrated traffic, GATED (Leader-C) exposure ---
    d = SetDueling(cfg(), seed=1)
    hot_lo, hot_hi = 0, N_SETS - 1
    draws = 20000
    exp_leaderC_lo = 0
    for _ in range(draws):
        d.maybe_reseed()
        exp_leaderC_lo += int(d.is_leaderC[hot_lo])
    p_leaderC = exp_leaderC_lo / draws                       # ~ phi_G
    worst_window_regret = R_MAX
    naive_probing_allow = PHI_P * R_MAX
    violation_vs_probing = worst_window_regret / naive_probing_allow

    # --- (2) sorted-prefix bug vs fixed uniform PROBING audit, low AND high index ---
    d = SetDueling(cfg(), seed=2)
    n_aud = int(round(RHO_AUD * (N_SETS - N_L - N_F)))
    buggy_lo = buggy_hi = fixed_lo = fixed_hi = 0
    for _ in range(draws):
        d.maybe_reseed()
        # BUGGY (old): audited = sorted(followers)[:n_aud] -> low indices almost always exposed
        buggy_aud = set(d.follower[:n_aud].tolist())         # d.follower is sorted
        buggy_lo += int((hot_lo in buggy_aud) or d.is_leaderC[hot_lo])
        buggy_hi += int((hot_hi in buggy_aud) or d.is_leaderC[hot_hi])
        # FIXED: audited = secret uniform subset (is_audited), C also on Leader-C
        fixed_lo += int(d.is_audited[hot_lo] or d.is_leaderC[hot_lo])
        fixed_hi += int(d.is_audited[hot_hi] or d.is_leaderC[hot_hi])
    buggy_lo, buggy_hi = buggy_lo / draws, buggy_hi / draws
    fixed_lo, fixed_hi = fixed_lo / draws, fixed_hi / draws
    # analytic buggy low-index exposure: a low-index set is a non-leader (prob 1-64/2048) and then
    # lands in the sorted-prefix; for index 0 it is audited unless it is a leader -> ~ 1 - n_L/n_sets
    buggy_lo_analytic = 1 - N_L / N_SETS

    # --- (3) expectation of PROBING exposure over arbitrary traffic + Hoeffding envelope ---
    # concentrated traffic on the WORST-CASE (low-index) set each window, fixed routing, fresh reseed.
    def hoeffding_slack(T_att, dp):
        return R_MAX * np.sqrt(T_att * np.log(1.0 / dp) / 2.0)
    delta_p = 0.01
    Ts = [30, 60, 120, 240, 480]
    d = SetDueling(cfg(), seed=3)
    hp_rows = []
    for T_att in Ts:
        totals = []
        for _ in range(2000):
            s = 0.0
            for _w in range(T_att):
                d.maybe_reseed()
                s += R_MAX if (d.is_audited[hot_lo] or d.is_leaderC[hot_lo]) else 0.0  # all traffic on hot_lo
            totals.append(s)
        totals = np.array(totals)
        envelope = PHI_P * T_att * R_MAX + hoeffding_slack(T_att, delta_p)
        hp_rows.append(dict(T_att=T_att, mean_total=float(totals.mean()),
                            p99=float(np.percentile(totals, 99)),
                            per_window_mean=float(totals.mean() / T_att),
                            envelope_phiP=float(envelope),
                            coverage_phiP=float(np.mean(totals <= envelope)),
                            expectation_target=PHI_P * T_att * R_MAX))

    print(f"phi_G={PHI_G:.6f}  phi_P={PHI_P:.6f}")
    print(f"(1) GATED: hot set is Leader-C with prob {p_leaderC:.5f} (~phi_G); concentrated one-window "
          f"regret={worst_window_regret:.3f} = {violation_vs_probing:.2f}x the naive phi_P allowance")
    print(f"(2) PROBING audit exposure of a hot set:")
    print(f"    SORTED-PREFIX (buggy): low-index={buggy_lo:.4f} (analytic {buggy_lo_analytic:.4f})  high-index={buggy_hi:.4f}")
    print(f"    UNIFORM SECRET (fixed): low-index={fixed_lo:.4f}  high-index={fixed_hi:.4f}  (target ~phi_P={PHI_P:.4f})")
    print(f"(3) fixed-routing concentrated-traffic exposure + Hoeffding envelope (delta'=0.01):")
    for r in hp_rows:
        print(f"    T_att={r['T_att']:4d}: per-window mean={r['per_window_mean']:.4f} (~phi_P) "
              f"p99 total={r['p99']:.1f} <= envelope {r['envelope_phiP']:.1f}? cov={r['coverage_phiP']:.4f}")

    # invariants
    counterexample_real = violation_vs_probing > 10.0
    sorted_prefix_bug_real = buggy_lo > 0.5                       # low-index exposed >50% under sorted prefix
    fix_uniform = abs(fixed_lo - PHI_P) < 0.01 and abs(fixed_hi - PHI_P) < 0.01  # index-independent ~phi_P
    hp_holds = all(r["coverage_phiP"] >= 1 - 2 * delta_p for r in hp_rows)

    fig, ax = plt.subplots(figsize=(4.6, 2.9))
    idx = ["low index\n(set 0)", "high index\n(set 2047)"]
    x = np.arange(2)
    ax.bar(x - 0.2, [buggy_lo, buggy_hi], 0.38, color=C.PALETTE["unguarded"], label="sorted-prefix (buggy)")
    ax.bar(x + 0.2, [fixed_lo, fixed_hi], 0.38, color=C.PALETTE["bouncer"], label="uniform secret (fixed)")
    ax.axhline(PHI_P, color="k", lw=0.9, ls=":", label=f"$\\phi_P$={PHI_P:.3f}")
    ax.set_xticks(x); ax.set_xticklabels(idx, fontsize=7.5)
    ax.set_ylabel("PROBING exposure prob. of a hot set")
    ax.set_title("Sorted-prefix audit exposes low-index sets\nnear-deterministically; uniform secret audit does not")
    ax.legend(loc="center right", fontsize=6.6)
    C.savefig(fig, "floor_traffic.pdf")

    C.save_json("floor_traffic.json", dict(
        note=("Audit exposure is traffic-weighted; the secret UNIFORM sampler bounds it in expectation. "
              "GATED: E[exposure]=phi_G for any traffic. PROBING: the audit subset must be a secret "
              "uniform subset of followers (set_dueling.is_audited), NOT a sorted prefix -- a sorted "
              "prefix exposes low-index sets with prob ~1-n_L/n_sets (the R2 reviewer's bug), whereas "
              "the uniform subset exposes any set with prob ~phi_P independent of index/traffic. "
              "Per-window exposures are bounded in [0, r_max] with conditional mean <= phi_P*r_max "
              "under the fresh uniform secret draw; they need not be independent under history-"
              "adaptive traffic, so the total concentrates under the Azuma-Hoeffding envelope "
              "(same constant independence would give)."),
        phi_G=PHI_G, phi_P=PHI_P, r_max=R_MAX, rho_aud=RHO_AUD,
        counterexample=dict(worst_window_regret=worst_window_regret,
                            naive_phiP_allowance=naive_probing_allow,
                            violation_factor=violation_vs_probing,
                            prob_hot_is_leaderC=p_leaderC),
        probing_audit=dict(sorted_prefix_low=buggy_lo, sorted_prefix_low_analytic=buggy_lo_analytic,
                           sorted_prefix_high=buggy_hi, uniform_low=fixed_lo, uniform_high=fixed_hi,
                           target_phiP=PHI_P),
        high_prob_delta=delta_p, high_prob_cells=hp_rows,
        invariants=dict(counterexample_real=counterexample_real,
                        sorted_prefix_bug_real=sorted_prefix_bug_real,
                        fix_uniform_index_independent=fix_uniform,
                        high_prob_envelope_holds=hp_holds)))
    assert counterexample_real, "concentrated traffic should break the per-window bound by >10x"
    assert sorted_prefix_bug_real, "sorted-prefix audit should expose a low-index set >50% (the bug)"
    assert fix_uniform, "uniform secret audit should expose any set ~phi_P independent of index"
    assert hp_holds, "the Hoeffding high-probability envelope should cover the reseeded totals"


if __name__ == "__main__":
    main()
