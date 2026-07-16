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
  (ii) SUSTAINED EVASION: a single window's realized evasion carries no implication, but the
       assignment is redrawn INDEPENDENTLY each epoch and rewards are bounded, so for a truly
       degrading strategy (E[dhat_R] <= tau - eps) Hoeffding gives
           P( mean of W per-window dhat_R >= tau ) <= exp(-2 W eps^2 / range^2),
       and once the running average is below tau the CUSUM (reference K = tau + gamma/2 > tau)
       accumulates >= gamma/2 per window and fires within 2H/gamma more windows. Sustained
       realized evasion by a degrading adversary is exponentially unlikely in the audit length.

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
RANGE = 2.0                    # dhat in [-1, 1] in that construction


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
    eps = tau). Compare to the Hoeffding envelope exp(-2 W eps^2 / range^2)."""
    rng = np.random.default_rng(seed)
    rows = []
    for W in Ws:
        dh = rng.choice([-1.0, 1.0], size=(n_rep, W))
        p = float((dh.mean(axis=1) >= TAU).mean())
        hoeff = float(np.exp(-2 * W * TAU ** 2 / RANGE ** 2))
        rows.append(dict(W=W, p_sustained_evade=p, hoeffding=hoeff))
    return rows


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

    print("(1) two-set counterexample (single-window realized claim is FALSE):")
    print(f"    E[r_L]={ce['E_rL']:.4f}  E[r_foll]={ce['E_rfoll']:.4f}  (unconditional identity holds)")
    print(f"    P(evade)={ce['p_evade']:.4f}  E[r_foll | evade]={ce['E_rfoll_given_evade']:.4f}"
          f"  << claimed floor {ce['claimed_floor']:.1f}")
    print("(2) sustained evasion decays (Hoeffding envelope holds):")
    for r in se:
        print(f"    W={r['W']:2d}: P(evade W-avg)={r['p_sustained_evade']:.4f}  <= exp(-W/8)={r['hoeffding']:.4f}")
    print("(3) pinned operating point (independent sets, n_L=32, m=64):")
    print(f"    P(evade)={pp['p_evade']:.4f}  follower selection bias={pp['selection_bias']:.5f} (~0)")

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
                label=r"Hoeffding $e^{-2W\epsilon^2/r^2}$")
    ax.set_xlabel("audit windows $W$"); ax.set_ylabel("sustained-evasion prob.")
    ax.set_title("Single-window evasion is cheap (selection);\nsustained evasion decays exponentially")
    ax.legend(fontsize=7)
    C.savefig(fig, "prop1_selection.pdf")

    C.save_json("prop1_selection.json", dict(
        note=("Owns the TMLR-R5 Prop-1 counterexample: conditioning on a single window's realized "
              "evasion (dhat_R >= tau) after an unconditional exchangeability identity is selection "
              "bias -- in the two-set construction E[r_foll|evade]=0 despite E[r_foll]=0.5, so the old "
              "realized single-window claim is FALSE. The corrected Prop 1 states (i) the expectation "
              "form (valid algebra) and (ii) the sustained-evasion form: with independent per-epoch "
              "reseeds and bounded rewards, a truly degrading strategy (E[dhat]<=tau-eps) sustains "
              "W-window evasion only w.p. <= exp(-2 W eps^2/range^2) (measured decay under the "
              "envelope), and the CUSUM (reference K>tau) then fires within 2H/gamma windows. At the "
              "pinned many-set operating point the single-window follower selection bias is ~0; the "
              "catastrophe needs cross-set anticorrelation plus a tiny pool."),
        two_set=ce, sustained=se, pinned=pp,
        invariants=dict(counterexample_real=counterexample_real,
                        sustained_evasion_decays=decays,
                        hoeffding_envelope_holds=hoeff_holds,
                        pinned_point_bias_negligible=pinned_clean)))
    assert counterexample_real, "the two-set counterexample must reproduce (E[r_foll|evade]~0)"
    assert decays, "sustained-evasion probability must decay with W"
    assert hoeff_holds, "the Hoeffding envelope must cover the measured decay"
    assert pinned_clean, "at the pinned operating point the follower selection bias should be ~0"


if __name__ == "__main__":
    main()
