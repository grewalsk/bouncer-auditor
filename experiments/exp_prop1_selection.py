"""Selection bias in realized evasion, and the sustained-evasion repair (TMLR-R5's Prop-1 gap).

The old Proposition 1 argued: exchangeability gives the UNCONDITIONAL identity
E[r_L] = E[r_foll] + b, so any strategy keeping dhat_R >= tau forces follower reward
>= fallback + tau - beta. The R5 review showed the inference is INVALID: conditioning on the
realized evasion event {dhat_R >= tau} after using an unconditional identity is selection bias.
Their counterexample (owned here as part 1): two exchangeable sets with rewards {1,0} randomly
permuted, one secretly Leader-L, fallback 0.2, tau 0.5, beta 0. Unconditionally E[r_L] =
E[r_foll] = 0.5, but conditioned on evasion the leader always drew the 1 and the follower the 0:
E[r_foll | evade] = 0 << fallback + tau = 0.7, with P(evade) = 0.5 per window.

The repair (the corrected Proposition 1) has two forms:
  (i)  EXPECTATION: if E[dhat_R] >= tau then E[follower reward] >= fallback + tau - beta.
       (The unconditional identity, applied unconditionally -- valid algebra.)
  (ii) SUSTAINED EVASION, under an EXPLICIT TEMPORAL PREMISE: assume the per-window dhat_R are
       independent given the strategy. The fresh secret reseed makes the ASSIGNMENTS
       independent; the premise additionally requires the reward process not to depend on gate
       history -- it holds for the harness's i.i.d. per-decision reward and is violable by
       adaptive, gate-history-dependent strategies (see the paper's discharge table). Then
       dhat_R in [-r_max, r_max] (support width 2*r_max) and Hoeffding give, for a truly
       degrading strategy (E[dhat_R] <= tau - eps),
           P( mean of W per-window dhat_R >= tau ) <= exp(-W eps^2 / (2 r_max^2)),
       and the no-alarm event is CONTAINED in the high-average event: the CUSUM's max(0,.)
       floor only raises the statistic, so no alarm within W windows forces the block average
       of dhat_R to be at least K - H/W >= tau once W >= 2H/gamma. Sustained realized evasion
       by a degrading adversary is exponentially unlikely in the audit length. (An earlier
       draft's incorrect 'once the average dips the CUSUM fires within 2H/gamma windows' step
       is reproduced as a counterexample below -- see cusum_block_tests.)

This script verifies: (1) the counterexample (single-window realized claim is FALSE); (2) the
sustained-evasion probability decays with W and stays under the Hoeffding envelope; (3) at the
pinned operating point (n_L=32 sets, m=64 decisions, independent per-set rewards) the
single-window selection bias on the followers is ~0 -- the catastrophic case needs cross-set
anticorrelation plus a tiny pool, which the reseeded many-set audit does not have.

Deterministic; emits results/prop1_selection.json + figures/prop1_selection.pdf.
"""
import sys
import numpy as np
sys.path.insert(0, 'experiments')
import common as C
import matplotlib.pyplot as plt

TAU, FALLBACK = 0.5, 0.2      # the reviewer's two-set construction
R_MAX = 1.0                    # dhat in [-r_max, r_max] = [-1, 1] in that construction


def two_set_counterexample(n_draws=1_000_000, seed=0):
    """Rewards {1,0} exchangeable across 2 sets; one uniformly-secret Leader-L; per-window
    dhat = r_L - r_F(=fallback-side read of the other set's controller path). Evade iff dhat>=tau."""
    rng = np.random.default_rng(seed)
    hot = rng.integers(0, 2, size=n_draws)         # which set drew reward 1 this window
    leader = rng.integers(0, 2, size=n_draws)      # which set is secretly Leader-L
    r_L = (hot == leader).astype(float)            # leader's realized controller reward
    r_foll = 1.0 - r_L                             # the other (follower/victim) set's reward
    dhat = r_L - r_foll                            # in {-1, +1}
    evade = dhat >= TAU
    return dict(E_rL=float(r_L.mean()), E_rfoll=float(r_foll.mean()),
                p_evade=float(evade.mean()),
                E_rfoll_given_evade=float(r_foll[evade].mean()),
                claimed_floor=FALLBACK + TAU)


def sustained_evasion(Ws=(1, 2, 4, 8, 16), n_rep=200_000, seed=1):
    """P(mean of W i.i.d. per-window dhat >= tau) in the same construction (E[dhat]=0, so
    eps = tau). Compare to the corrected Hoeffding envelope exp(-W eps^2 / (2 r_max^2))."""
    rng = np.random.default_rng(seed)
    rows = []
    for W in Ws:
        dh = rng.choice([-1.0, 1.0], size=(n_rep, W))
        p = float((dh.mean(axis=1) >= TAU).mean())
        hoeff = float(np.exp(-W * TAU ** 2 / (2 * R_MAX ** 2)))
        rows.append(dict(W=W, p_sustained_evade=p, hoeffding=hoeff))
    return rows


def printed_formula_regression():
    """TMLR-R6: assert the PRINTED Hoeffding constant, exactly. dhat in [-r_max, r_max] has range
    width 2*r_max, so the valid envelope is exp(-W eps^2/(2 r_max^2)); the earlier draft printed
    exp(-2W eps^2/r_max^2), which iid Rademacher dhat at W=100, tau=eps=0.2, r_max=1 violates:
    P(mean >= 0.2) = P(Binom(100,.5) >= 60) = 0.0284 >> exp(-8) = 0.000335 (84.8x)."""
    from math import comb, exp
    W, tau, r_max = 100, 0.2, 1.0
    p_exact = sum(comb(W, k) for k in range(60, W + 1)) / 2.0 ** W
    old_env = exp(-2 * W * tau ** 2 / r_max ** 2)
    new_env = exp(-W * tau ** 2 / (2 * r_max ** 2))
    return dict(W=W, tau=tau, p_exact=float(p_exact), old_envelope=float(old_env),
                new_envelope=float(new_env), old_violation_factor=float(p_exact / old_env),
                new_holds=bool(p_exact <= new_env))


def cusum_block_tests(seed=3):
    """TMLR-R6/R7: (a) the OLD 'average dips -> CUSUM fires within 2H/gamma windows' step is
    FALSE: the reviewer's stream (one 0, then 0.09s) has prefix average 0.045 < tau=0.05 yet
    after 16 further windows C=0.27 < H=0.8, no alarm. (b) the CORRECT block containment on the
    real LowerCusum: on the no-alarm event no reset occurs, so C_t >= sum(K - dhat) throughout
    (the max(0,.) floor only raises it), and no alarm by window W -- C_t <= H for all t, the
    implemented detector alarming only on the strict C_t > H -- forces block mean(dhat) >=
    K - H/W >= tau for W >= 2H/gamma. Verified on random degrading streams AND exhaustively:
    every path of a 3-point reward support over W=8 windows from three starting statistics
    C_0 in {0, 0.3, 0.6}. (c) equality-at-threshold: a path reaching C == H exactly does NOT
    alarm (strict >), so the containment must -- and does -- use C_W <= H, not C_W < H.
    (d) exact no-alarm probability: for an i.i.d. two-point degrading stream SUPPORTED ON
    [-r_max, r_max] with mean exactly tau - eps, an exact dynamic program over the integer-
    lattice CUSUM states gives P(no alarm over W_block), cross-checked by Monte Carlo on the
    real detector; both sit under the corrected envelope exp(-W eps^2/(2 r_max^2))."""
    import itertools
    from fractions import Fraction
    from bouncer.cusum import LowerCusum
    K, H, tau, gamma = 0.10, 0.80, 0.05, 0.10
    W_block = int(np.ceil(2 * H / gamma))                       # 16

    # (a) reviewer's counterexample: no alarm despite prefix average < tau
    c = LowerCusum(K=K, H=H)
    stream = [0.0, 0.09] + [0.09] * 16
    fired = any(c.update(x) for x in stream)
    prefix_avg = np.mean(stream[:2])
    final_C = c.C

    # (b1) containment on random degrading streams (support [-0.47, 0.53] c [-1, 1])
    rng = np.random.default_rng(seed)
    containment_ok = True
    for _ in range(2000):
        c = LowerCusum(K=K, H=H)
        xs = rng.uniform(-1, 1, size=W_block) * 0.5 + (tau - 0.02)   # noisy, mean below tau
        alarm = False
        for x in xs:
            if c.update(x):
                alarm = True
                break
        if not alarm and np.mean(xs) <= K - H / W_block - 1e-12:
            containment_ok = False                                   # would contradict containment
            break

    # (b2) EXHAUSTIVE containment: every 3-point path over W=8, three starting statistics.
    # Also count no-alarm paths that touch C == H exactly (float-exact), regression-backing
    # the strict-> boundary: reaching the threshold without crossing it must not alarm.
    W_ex, support = 8, (-0.65, 0.05, 0.35)
    exhaustive_ok, n_noalarm_paths, n_boundary_paths = True, 0, 0
    for C0 in (0.0, 0.3, 0.6):
        for path in itertools.product(support, repeat=W_ex):
            c = LowerCusum(K=K, H=H, C=C0)
            alarm, touched_H = False, False
            for x in path:
                if c.update(x):
                    alarm = True
                    break
                if c.C == H:
                    touched_H = True
            if not alarm:
                n_noalarm_paths += 1
                n_boundary_paths += int(touched_H)
                if np.mean(path) < K - H / W_ex - 1e-12:
                    exhaustive_ok = False

    # Repeat the same finite sweep with exact rational arithmetic. Binary
    # floating point rounds a few paths just above H and therefore reports fewer
    # no-alarm paths. The difference is conservative, but the artifact records
    # both counts instead of presenting the implementation-specific count as
    # mathematical combinatorics.
    K_q, H_q = Fraction(1, 10), Fraction(4, 5)
    support_q = (Fraction(-65, 100), Fraction(5, 100), Fraction(35, 100))
    exact_noalarm_paths, exact_boundary_paths, exact_containment_ok = 0, 0, True
    for C0_q in (Fraction(0), Fraction(3, 10), Fraction(3, 5)):
        for path_q in itertools.product(support_q, repeat=W_ex):
            C_q, alarm_q, touched_q = C0_q, False, False
            for x_q in path_q:
                C_q = max(Fraction(0), C_q + K_q - x_q)
                if C_q > H_q:
                    alarm_q = True
                    break
                touched_q = touched_q or C_q == H_q
            if not alarm_q:
                exact_noalarm_paths += 1
                exact_boundary_paths += int(touched_q)
                if sum(path_q, Fraction(0)) / W_ex < K_q - H_q / W_ex:
                    exact_containment_ok = False
    # (c) equality-at-threshold through the real detector: eight x=0 steps of K=0.125 land
    # C exactly at H=1.0 (0.125 is dyadic, so float-exact); strict > must NOT alarm
    c_eq = LowerCusum(K=0.125, H=1.0)
    eq_fired = any(c_eq.update(0.0) for _ in range(8))
    eq_at_H = bool(c_eq.C == 1.0)

    # (d) exact DP no-alarm probability, in-support two-point degrading stream.
    # x in {-0.65, +0.35} w.p. 1/2 each: support c [-r_max, r_max] = [-1, 1], mean = -0.15
    # = tau - eps exactly (eps = 0.20). Increments K - x in {+0.75, -0.25} are multiples of
    # 0.01, so the reachable no-alarm CUSUM states form an exact integer lattice (hundredths).
    eps, r_max = 0.20, 1.0
    x_lo, x_hi = -0.65, 0.35
    assert abs(0.5 * x_lo + 0.5 * x_hi - (tau - eps)) < 1e-15, "two-point mean must be tau - eps"
    assert max(abs(x_lo), abs(x_hi)) <= r_max, "two-point support must lie in [-r_max, r_max]"
    inc_lo, inc_hi, H_int = 75, -25, 80                          # hundredths: K-x_lo, K-x_hi, H
    states = {0: Fraction(1)}                                    # C (hundredths) -> P(no alarm yet)
    for _ in range(W_block):
        nxt = {}
        for cv, pr in states.items():
            for d in (inc_lo, inc_hi):
                c2 = max(0, cv + d)
                if c2 > H_int:                                   # strict > H alarms; drop path
                    continue
                nxt[c2] = nxt.get(c2, Fraction(0)) + pr / 2
        states = nxt
    p_noalarm_exact = float(sum(states.values()))
    # Monte Carlo cross-check on the real detector, same distribution
    n_rep, mc_hits = 100_000, 0
    lo_draws = rng.random((n_rep, W_block)) < 0.5
    for i in range(n_rep):
        c = LowerCusum(K=K, H=H)
        alarm = False
        for lo in lo_draws[i]:
            if c.update(x_lo if lo else x_hi):
                alarm = True
                break
        mc_hits += int(not alarm)
    p_noalarm_mc = mc_hits / n_rep
    mc_sigma = float(np.sqrt(p_noalarm_exact * (1 - p_noalarm_exact) / n_rep))
    envelope = float(np.exp(-W_block * eps ** 2 / (2 * r_max ** 2)))
    return dict(W_block=W_block,
                counterexample=dict(prefix_avg=float(prefix_avg), fired=bool(fired), final_C=float(final_C)),
                containment_holds=bool(containment_ok),
                exhaustive=dict(W=W_ex, support=list(support), C0=[0.0, 0.3, 0.6],
                                n_noalarm_paths=int(n_noalarm_paths),
                                n_boundary_paths=int(n_boundary_paths), holds=bool(exhaustive_ok),
                                exact_rational_noalarm_paths=int(exact_noalarm_paths),
                                exact_rational_boundary_paths=int(exact_boundary_paths),
                                exact_rational_holds=bool(exact_containment_ok),
                                float_count_is_conservative=bool(
                                    n_noalarm_paths <= exact_noalarm_paths)),
                equality_at_H=dict(fired=bool(eq_fired), C_equals_H=eq_at_H),
                exact_dp=dict(eps=eps, r_max=r_max, support=[x_lo, x_hi], mean=tau - eps,
                              p_noalarm_exact=p_noalarm_exact, p_noalarm_mc=float(p_noalarm_mc),
                              mc_sigma=mc_sigma, corrected_envelope=envelope))


def pinned_point_bias(n_draws=200_000, seed=2):
    """At the pinned operating point (32 leader sets, m=64 Bernoulli decisions each, independent
    per-set rewards, equal true means), conditioning on dhat >= tau=0.05 barely moves the
    followers: with independent sets the selection acts only on the leader pools' noise."""
    rng = np.random.default_rng(seed)
    m, n_L = 64, 32
    rL = rng.binomial(m, 0.5, size=(n_draws, n_L)).mean(axis=1) / m
    rF = rng.binomial(m, 0.5, size=(n_draws, n_L)).mean(axis=1) / m
    rfoll = rng.binomial(m, 0.5, size=n_draws) / m          # an independent victim set
    dhat = rL - rF
    evade = dhat >= 0.05
    return dict(p_evade=float(evade.mean()),
                E_rfoll=float(rfoll.mean()),
                E_rfoll_given_evade=float(rfoll[evade].mean()) if evade.any() else float("nan"),
                selection_bias=float(abs(rfoll[evade].mean() - rfoll.mean())) if evade.any() else 0.0)


def main():
    C.setstyle()
    ce = two_set_counterexample()
    se = sustained_evasion()
    pp = pinned_point_bias()
    pf = printed_formula_regression()
    cb = cusum_block_tests()

    print("(1) two-set counterexample (single-window realized claim is FALSE):")
    print(f"    E[r_L]={ce['E_rL']:.4f}  E[r_foll]={ce['E_rfoll']:.4f}  (unconditional identity holds)")
    print(f"    P(evade)={ce['p_evade']:.4f}  E[r_foll | evade]={ce['E_rfoll_given_evade']:.4f}"
          f"  << claimed floor {ce['claimed_floor']:.1f}")
    print("(2) sustained evasion decays (Hoeffding envelope holds):")
    for r in se:
        print(f"    W={r['W']:2d}: P(evade W-avg)={r['p_sustained_evade']:.4f}  <= exp(-W/8)={r['hoeffding']:.4f}")
    print("(3) pinned operating point (independent sets, n_L=32, m=64):")
    print(f"    P(evade)={pp['p_evade']:.4f}  follower selection bias={pp['selection_bias']:.5f} (~0)")
    print("(4) printed-formula regression (W=100, tau=eps=0.2, Rademacher):")
    print(f"    exact P={pf['p_exact']:.6f}  OLD range-1 envelope={pf['old_envelope']:.6f} "
          f"(violated {pf['old_violation_factor']:.1f}x)  corrected range-2 envelope={pf['new_envelope']:.6f} holds={pf['new_holds']}")
    print("(5) real-CUSUM block tests (K=0.10, H=0.80, W_block=16):")
    print(f"    reviewer stream: prefix avg {cb['counterexample']['prefix_avg']:.3f} < tau, fired={cb['counterexample']['fired']}, "
          f"final C={cb['counterexample']['final_C']:.2f}  (OLD 'fires within 2H/gamma' claim FALSE)")
    print(f"    no-alarm => block-mean containment: random streams {cb['containment_holds']}; "
          f"exhaustive (3^8 paths x 3 C_0, {cb['exhaustive']['n_noalarm_paths']} no-alarm paths) {cb['exhaustive']['holds']}")
    print(f"    exact-rational sweep: {cb['exhaustive']['exact_rational_noalarm_paths']} no-alarm, "
          f"{cb['exhaustive']['exact_rational_boundary_paths']} boundary-touching paths; "
          f"float count is conservative={cb['exhaustive']['float_count_is_conservative']}")
    print(f"    equality-at-H: fired={cb['equality_at_H']['fired']} with C==H exactly ({cb['equality_at_H']['C_equals_H']}) -- strict > semantics")
    print(f"    exact-DP P(no alarm)={cb['exact_dp']['p_noalarm_exact']:.6f}  MC on real detector={cb['exact_dp']['p_noalarm_mc']:.6f} "
          f"(sigma {cb['exact_dp']['mc_sigma']:.6f})  <= envelope {cb['exact_dp']['corrected_envelope']:.4f}")

    counterexample_real = ce["E_rfoll_given_evade"] < 0.05 and abs(ce["E_rfoll"] - 0.5) < 0.01
    # decay is exponential overall; strict per-step monotonicity fails at small W from the
    # +/-1 construction's integer/parity effect (W=2 needs 2/2 ones, W=4 needs only 3/4),
    # so assert the envelope plus an order-of-magnitude drop across the sweep.
    decays = se[-1]["p_sustained_evade"] < 0.1 * se[0]["p_sustained_evade"]
    hoeff_holds = all(r["p_sustained_evade"] <= r["hoeffding"] + 1e-6 for r in se)
    pinned_clean = pp["selection_bias"] < 0.005

    fig, ax = plt.subplots(figsize=(4.2, 2.8))
    ax.semilogy([r["W"] for r in se], [max(r["p_sustained_evade"], 1e-6) for r in se], "o-",
                color=C.PALETTE["bouncer"], label="measured $P$(evade $W$-avg)")
    ax.semilogy([r["W"] for r in se], [r["hoeffding"] for r in se], "s--", color="k",
                label=r"Hoeffding $e^{-W\epsilon^2/(2r_{\max}^2)}$")
    ax.set_xlabel("audit windows $W$"); ax.set_ylabel("sustained-evasion prob.")
    ax.set_title("Single-window evasion is cheap (selection);\nsustained evasion decays exponentially")
    ax.legend(fontsize=7)
    C.savefig(fig, "prop1_selection.pdf")

    dp = cb["exact_dp"]
    C.save_json("prop1_selection.json", dict(
        note=("Owns the TMLR-R5 Prop-1 counterexample: conditioning on a single window's realized "
              "evasion (dhat_R >= tau) after an unconditional exchangeability identity is selection "
              "bias -- in the two-set construction E[r_foll|evade]=0 despite E[r_foll]=0.5, so the old "
              "realized single-window claim is FALSE. The corrected Prop 1 states (i) the expectation "
              "form (valid algebra) and (ii) the sustained-evasion form UNDER AN EXPLICIT TEMPORAL "
              "PREMISE: per-window dhat_R independent given the strategy (fresh reseeds make the "
              "assignments independent; the reward process must additionally not depend on gate "
              "history -- holds for the harness's i.i.d. reward, violable by adaptive gate-history-"
              "dependent strategies). Then a truly degrading strategy (E[dhat]<=tau-eps) sustains a "
              "W-window average >= tau only w.p. <= exp(-W eps^2/(2 r_max^2)) (Hoeffding, width-"
              "2r_max support), and the no-alarm event is CONTAINED in the high-average event: the "
              "CUSUM's max(0,.) floor means no alarm in W windows forces block mean >= K - H/W >= "
              "tau for W >= 2H/gamma. (An earlier draft's incorrect 'average dips -> fires within "
              "2H/gamma windows' step is reproduced as a counterexample in cusum_block.) At the "
              "pinned many-set operating point the single-window follower selection bias is ~0; the "
              "catastrophe needs cross-set anticorrelation plus a tiny pool."),
        two_set=ce, sustained=se, pinned=pp,
        printed_formula=pf, cusum_block=cb,
        invariants=dict(counterexample_real=counterexample_real,
                        sustained_evasion_decays=decays,
                        hoeffding_envelope_holds=hoeff_holds,
                        pinned_point_bias_negligible=pinned_clean,
                        old_range1_formula_violated=bool(pf["old_violation_factor"] > 10),
                        corrected_range2_formula_holds=pf["new_holds"],
                        old_cusum_step_false=bool(not cb["counterexample"]["fired"]),
                        cusum_block_containment=cb["containment_holds"],
                        cusum_exhaustive_containment=cb["exhaustive"]["holds"],
                        cusum_equality_at_H_no_alarm=bool(
                            not cb["equality_at_H"]["fired"] and cb["equality_at_H"]["C_equals_H"]),
                        cusum_dp_matches_mc=bool(
                            abs(dp["p_noalarm_mc"] - dp["p_noalarm_exact"]) <= 5 * dp["mc_sigma"] + 1e-9),
                        cusum_noalarm_under_envelope=bool(
                            dp["p_noalarm_exact"] <= dp["corrected_envelope"]
                            and dp["p_noalarm_mc"] <= dp["corrected_envelope"] + 1e-6))))
    assert counterexample_real, "the two-set counterexample must reproduce (E[r_foll|evade]~0)"
    assert decays, "sustained-evasion probability must decay with W"
    assert hoeff_holds, "the Hoeffding envelope must cover the measured decay"
    assert pinned_clean, "at the pinned operating point the follower selection bias should be ~0"
    assert pf["old_violation_factor"] > 10, "the old range-1 exponent must be shown violated"
    assert pf["new_holds"], "the corrected range-2 exponent must hold exactly"
    assert not cb["counterexample"]["fired"], "reviewer's stream must NOT fire (old CUSUM step false)"
    assert cb["containment_holds"], "no-alarm => block-mean containment must hold on the real CUSUM"
    assert cb["exhaustive"]["holds"], "exhaustive containment must hold on every no-alarm path"
    assert cb["exhaustive"]["n_noalarm_paths"] > 0, "exhaustive sweep must exercise no-alarm paths"
    assert cb["exhaustive"]["n_boundary_paths"] > 0, \
        "exhaustive sweep must include a no-alarm path touching C == H exactly (strict > boundary)"
    assert cb["exhaustive"]["exact_rational_holds"], \
        "exact-rational exhaustive containment must hold"
    assert cb["exhaustive"]["float_count_is_conservative"], \
        "floating-point enumeration must not add no-alarm paths relative to exact arithmetic"
    assert not cb["equality_at_H"]["fired"] and cb["equality_at_H"]["C_equals_H"], \
        "C == H exactly must NOT alarm (the implemented detector is strict >)"
    assert abs(dp["p_noalarm_mc"] - dp["p_noalarm_exact"]) <= 5 * dp["mc_sigma"] + 1e-9, \
        "Monte Carlo on the real detector must match the exact DP no-alarm probability"
    assert dp["p_noalarm_exact"] <= dp["corrected_envelope"], \
        "exact no-alarm probability must sit under the corrected envelope"


if __name__ == "__main__":
    main()
