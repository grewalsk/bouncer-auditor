"""
E1 figure -- the real-ChampSim REPLACEMENT finding (honest negative + refinement).

Reads the committed ChampSim dueling logs (results/champsim_e1/) produced by
champsim_plugin/run_e1_replacement.sh and renders the two real results:

 (a) the secret per-epoch reseed -- the very thing that buys mimicry resistance --
     CONFOUNDS the per-window replacement-competence signal: with reseeding the
     dueling estimate Delta-hat sits at noise (rL ~ rF) even though the learned
     policy genuinely dominates; with FIXED leaders (reseed off, DRRIP-style) the
     SAME estimator resolves the gap. Replacement reward is STATEFUL -- a set must
     run one policy consistently to build the policy-specific cache state DRRIP
     accumulates -- so set-locality is necessary but NOT sufficient: the reward
     must also be (near-)stateless, or the leaders stable.

 (b) the whole-cache competence gap is real and large (learned LIP vs fallback
     SRRIP-HP); the cache_fill API fix makes Delta-hat a real nonzero signal (it
     was identically 0 under the hit-only reward -- the prior 'dhat~0' artifact).

This is a faithful real-systems boundary result, NOT a clean upside-capture
trajectory: the clean-case dynamics remain in the synthetic harness (P1).
"""
import os, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import common as C

E1DIR = os.path.join(C.RESDIR, "champsim_e1")


def read(path):
    out = []
    with open(path) as f:
        next(f)
        for ln in f:
            p = ln.strip().split(",")
            out.append(dict(window=int(p[0]), dhat=float(p[1]), sigma=float(p[2]),
                            rL=float(p[3]), rF=float(p[4]), deg=int(p[7]), state=p[8]))
    return out


def main():
    C.setstyle()
    res = read(os.path.join(E1DIR, "dueling_reseeded.csv"))
    fix = read(os.path.join(E1DIR, "dueling_fixed_leader.csv"))
    base = json.load(open(os.path.join(E1DIR, "baselines.json")))

    def clean_mean_dhat(rows):
        v = [r["dhat"] for r in rows if r["deg"] == 0 and r["window"] > 10]
        return float(np.mean(v)), float(np.std(v))

    res_m, res_s = clean_mean_dhat(res)
    fix_m, fix_s = clean_mean_dhat(fix)

    fig, axes = plt.subplots(1, 2, figsize=(8.6, 2.9), gridspec_kw=dict(width_ratios=[1.5, 1]))
    # (a) per-window dhat: reseeded (confounded) vs fixed-leader (resolves)
    ax = axes[0]
    rr = [r for r in res if r["deg"] == 0]
    ff = [r for r in fix if r["deg"] == 0]
    ax.plot([r["window"] for r in rr], [r["dhat"] for r in rr], "-", color=C.PALETTE["unguarded"],
            lw=1.2, label=f"secret reseed (mean $\\hat\\Delta$={res_m:.3f})")
    ax.plot([r["window"] for r in ff], [r["dhat"] for r in ff], "-", color=C.PALETTE["bouncer"],
            lw=1.2, label=f"fixed leaders (mean $\\hat\\Delta$={fix_m:.3f})")
    ax.axhline(0, color="#888", lw=0.6)
    ax.set_xlabel("audit window"); ax.set_ylabel(r"dueling $\hat\Delta=\bar r_L-\bar r_F$")
    ax.set_title("(a) Secret reseed confounds a STATEFUL competence signal")
    ax.legend(loc="upper left", fontsize=7)
    # (b) whole-cache competence gap
    ax = axes[1]
    names = ["learned\n(LIP)", "fallback\n(SRRIP-HP)", "corrupted\n(injected)"]
    vals = [base["learned_LIP_insert3"], base["fallback_SRRIP_HP_insert2"], base["corrupted_MRU_insert0"]]
    cols = [C.PALETTE["bouncer"], C.PALETTE["fallback"], C.PALETTE["unguarded"]]
    ax.bar(range(3), [v * 100 for v in vals], color=cols, width=0.62)
    ax.set_xticks(range(3)); ax.set_xticklabels(names, fontsize=7.5)
    ax.set_ylabel("whole-cache LLC hit rate (\\%)")
    ax.set_title("(b) Real competence gap exists")
    C.savefig(fig, "e1_replacement.pdf")

    verdict = dict(
        KEYSTONE_REAL=False,
        finding="Real-ChampSim replacement: (1) cache_fill API fix makes dhat nonzero (was ==0); "
                "(2) whole-cache competence gap is real (LIP %.3f vs SRRIP-HP %.3f); "
                "(3) secret per-epoch reseed CONFOUNDS the per-window dueling signal for the STATEFUL "
                "replacement reward (reseeded mean dhat=%.4f ~ noise; fixed-leader mean dhat=%.4f resolves). "
                "Set-locality is necessary but not sufficient: reward must be (near-)stateless or leaders stable."
                % (base["learned_LIP_insert3"], base["fallback_SRRIP_HP_insert2"], res_m, fix_m),
        reseeded_clean_mean_dhat=res_m, reseeded_clean_std=res_s,
        fixed_leader_clean_mean_dhat=fix_m, fixed_leader_clean_std=fix_s,
        whole_cache_baselines=base,
        scope="Clean-case upside-capture DYNAMICS remain in the synthetic harness (P1); the real "
              "replacement integration is a boundary/limitation result, not a clean-case validation.",
    )
    C.save_json("e1_keystone.json", verdict)
    print(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()
