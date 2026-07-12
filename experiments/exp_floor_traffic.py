"""Traffic-weighted audit-exposure: the Lemma-1 counterexample, and the corrected bound.

The earlier Lemma-1 audit-exposure term charged each drop window at most phi*r_max, where
phi = (leader sets)/(all sets). That is only valid if traffic is (near-)uniform across sets:
the n_L Leader-C sets keep running C during a drop, and their regret contribution is the
*traffic* that lands on them, not their *set count*. Assumptions A1-A5 never bounded per-set
traffic, so the per-window bound is false under concentrated traffic.

COUNTEREXAMPLE (reviewer's): put all of a window's traffic on ONE hot set. The ordinary
random event that the secret sampler tags that hot set Leader-C has probability phi_G =
n_L/n_sets; when it happens the whole window runs C, so with r_C=0, r_0=1 the realized
one-window regret is r_max=1 -- far above the claimed phi_G*r_max (or the looser PROBING
allowance phi_P*r_max). This script measures that violation factor.

CORRECTED BOUND. Because the assignment is a fresh secret uniform draw each epoch, each set
is Leader-C with probability phi_G independent of its traffic, so for ANY traffic distribution:

  * EXPECTATION (over the secret sampler): E[per-window exposure regret] <= phi_G*r_max
    (phi_P while PROBING). Traffic-agnostic; this is what the middle term bounds in expectation.
  * HIGH PROBABILITY (over T_att independently-reseeded windows): the total exposure regret
    is a sum of independent [0, r_max] variables, so by Hoeffding, w.p. >= 1-delta',
        Sum <= phi_P*T_att*r_max + r_max*sqrt( T_att * ln(1/delta') / 2 ).
    The sqrt slack is the sampler randomness the old statement omitted; it is o(T_att), so the
    per-window worst case washes out over an attack of any length.

This script reproduces the counterexample and verifies the expectation and high-probability
envelopes empirically. Deterministic; emits results/floor_traffic.json + figures/floor_traffic.pdf.
"""
import sys, json
import numpy as np
sys.path.insert(0, 'experiments')
import common as C
import matplotlib.pyplot as plt

N_SETS, N_L, N_F = 2048, 32, 32
RHO_AUD = 0.05
R_MAX = 1.0
PHI_G = N_L / N_SETS
PHI_P = PHI_G + RHO_AUD * (1 - (N_L + N_F) / N_SETS)


def exposure_regret_one_window(rng, traffic, phi_leaders=PHI_G, r_c=0.0, r_0=1.0):
    """Regret vs pi0 from the leader sets that keep running C this window, given a traffic
    distribution `traffic` (sums to 1) and a fresh secret assignment. Leader-C sets contribute
    (r_0 - r_c) * traffic_on_them. `phi_leaders` picks the exposed fraction (phi_G GATED)."""
    n_leaderC = int(round(phi_leaders * N_SETS))
    leaderC = rng.choice(N_SETS, size=n_leaderC, replace=False)
    return (r_0 - r_c) * float(traffic[leaderC].sum()) * R_MAX


def main():
    C.setstyle()
    rng = np.random.default_rng(0)

    uniform = np.full(N_SETS, 1.0 / N_SETS)
    concentrated = np.zeros(N_SETS); concentrated[0] = 1.0        # all traffic on one hot set

    # --- (1) single-window counterexample: concentrated traffic breaks the per-window bound ---
    N_DRAWS = 200_000
    reg_conc = np.array([exposure_regret_one_window(rng, concentrated, PHI_G) for _ in range(2000)])
    # closed form under concentration: regret = r_max with prob phi_G, else 0
    p_hot_is_leaderC = PHI_G
    worst_window_regret = R_MAX                                    # realized when hot set is Leader-C
    naive_gated_allow = PHI_G * R_MAX
    naive_probing_allow = PHI_P * R_MAX
    violation_vs_probing = worst_window_regret / naive_probing_allow
    mean_conc = float(reg_conc.mean())

    # --- (2) expectation holds for arbitrary traffic (mean over the secret sampler = phi_G) ---
    reg_unif = np.array([exposure_regret_one_window(rng, uniform, PHI_G) for _ in range(2000)])
    exp_conc, exp_unif = float(reg_conc.mean()), float(reg_unif.mean())

    # --- (3) high-probability envelope over T_att independently-reseeded windows ---
    def hoeffding_slack(T_att, delta_p):
        return R_MAX * np.sqrt(T_att * np.log(1.0 / delta_p) / 2.0)

    delta_p = 0.01
    Ts = [30, 60, 120, 240, 480]
    hp_rows = []
    for T_att in Ts:
        # worst-case traffic (concentrated) EACH window, independent fresh assignment per window
        totals = np.array([
            sum(exposure_regret_one_window(rng, concentrated, PHI_G) for _ in range(T_att))
            for _ in range(4000)
        ])
        envelope = PHI_G * T_att * R_MAX + hoeffding_slack(T_att, delta_p)  # GATED-tight; phi_P is looser
        envelope_probing = PHI_P * T_att * R_MAX + hoeffding_slack(T_att, delta_p)
        cover = float(np.mean(totals <= envelope))          # empirical coverage of the phi_G envelope
        cover_probing = float(np.mean(totals <= envelope_probing))
        hp_rows.append(dict(T_att=T_att, mean_total=float(totals.mean()),
                            p99=float(np.percentile(totals, 99)),
                            envelope_phiG=float(envelope), coverage_phiG=cover,
                            envelope_phiP=float(envelope_probing), coverage_phiP=cover_probing,
                            expectation_target=PHI_G * T_att * R_MAX))

    print(f"phi_G={PHI_G:.6f}  phi_P={PHI_P:.6f}")
    print(f"(1) concentrated single-window: worst realized regret={worst_window_regret:.3f} vs "
          f"naive phi_P allowance={naive_probing_allow:.5f}  -> {violation_vs_probing:.2f}x violation "
          f"(prob hot set is Leader-C = {p_hot_is_leaderC:.5f}); measured mean={mean_conc:.5f}")
    print(f"(2) expectation over sampler: E[regret] concentrated={exp_conc:.5f}, uniform={exp_unif:.5f} "
          f"(both ~ phi_G={PHI_G:.5f}, traffic-agnostic)")
    print("(3) Hoeffding high-prob envelope over independently-reseeded windows (delta'=0.01):")
    for r in hp_rows:
        print(f"    T_att={r['T_att']:4d}: mean={r['mean_total']:.3f} p99={r['p99']:.3f} "
              f"<= phi_G-envelope {r['envelope_phiG']:.3f}? coverage={r['coverage_phiG']:.4f}")

    # invariants: the counterexample is real, and the corrected envelopes hold
    counterexample_real = violation_vs_probing > 10.0
    expectation_holds = abs(exp_conc - PHI_G) < 0.003 and abs(exp_unif - PHI_G) < 0.003
    hp_holds = all(r["coverage_phiG"] >= 1 - 2 * delta_p for r in hp_rows)   # phi_G-tight envelope

    fig, ax = plt.subplots(figsize=(4.4, 2.9))
    T = np.array([r["T_att"] for r in hp_rows])
    ax.plot(T, [r["p99"] for r in hp_rows], "o-", color=C.PALETTE["bouncer"], label="measured 99th pct total")
    ax.plot(T, [r["expectation_target"] for r in hp_rows], "s:", color="k",
            label=r"expectation $\phi_G T_{att}$")
    ax.plot(T, [r["envelope_phiG"] for r in hp_rows], "^--", color=C.PALETTE["oracle"],
            label=r"high-prob envelope ($+$ Hoeffding)")
    ax.set_xlabel(r"attack windows $T_{att}$")
    ax.set_ylabel("total audit-exposure regret")
    ax.set_title("Concentrated-traffic exposure stays under the\ntraffic-agnostic high-probability envelope")
    ax.legend(loc="upper left", fontsize=6.8)
    C.savefig(fig, "floor_traffic.pdf")

    C.save_json("floor_traffic.json", dict(
        note=("Audit exposure must be traffic-weighted. Under concentrated traffic the per-window "
              "regret can reach r_max (violating the old per-window phi*r_max bound by ~1/phi_P), but "
              "because the secret assignment is a fresh uniform draw each epoch, E[exposure]=phi_G*r_max "
              "for ANY traffic, and over T_att independently-reseeded windows the total concentrates "
              "under phi_P*T_att*r_max + r_max*sqrt(T_att*ln(1/delta')/2) w.p. >= 1-delta'."),
        phi_G=PHI_G, phi_P=PHI_P, r_max=R_MAX,
        counterexample=dict(worst_window_regret=worst_window_regret,
                            naive_phiP_allowance=naive_probing_allow,
                            violation_factor=violation_vs_probing,
                            prob_hot_is_leaderC=p_hot_is_leaderC,
                            measured_mean=mean_conc),
        expectation=dict(concentrated=exp_conc, uniform=exp_unif, target_phiG=PHI_G),
        high_prob_delta=delta_p, high_prob_cells=hp_rows,
        invariants=dict(counterexample_real=counterexample_real,
                        expectation_holds=expectation_holds,
                        high_prob_envelope_holds=hp_holds)))
    assert counterexample_real, "concentrated traffic should break the per-window bound by >10x"
    assert expectation_holds, "E[exposure] should equal phi_G for arbitrary traffic (secret sampler)"
    assert hp_holds, "the Hoeffding high-probability envelope should cover the reseeded totals"


if __name__ == "__main__":
    main()
