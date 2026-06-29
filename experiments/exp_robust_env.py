"""
Model-misspecification robustness (addresses the review concern that the harness
reward is built from the theorems' own assumptions). We deliberately VIOLATE the
clean i.i.d.-set assumption: each set gets a fixed competence offset (hot/cold
sets, conflict skew) drawn from N(0, sigma_het), so Leader-C and Leader-F pools
are no longer exchangeable except in expectation (Prop 1's beta-bias regime). We
sweep sigma_het and show detection (mimicry TPR), false alarms, and the safety
floor all degrade GRACEFULLY rather than breaking -- the secret reseeding
re-randomizes which physical sets are leaders each epoch, shrinking the bias.
Outputs: results/robust_env.json, figures/robust_env.pdf
"""
import numpy as np
import matplotlib.pyplot as plt

import common as C
from bouncer.adversary import Clean, BroadAttack, MimicryAttack
from bouncer.simulate import run_episode
from bouncer import metrics as M

ONSET, T, SEEDS = 90, 240, 24


class HeteroWrap:
    """Wrap a base adversary, adding a FIXED per-set competence offset (set
    heterogeneity) to its stress each window. Offsets are a property of the
    physical set; the secret leader assignment is re-drawn each epoch, so the
    bias they inject into Δ̂ averages down."""
    def __init__(self, base, n_sets, sigma_het, seed):
        self.base = base
        self.name = base.name + "+het"
        rng = np.random.default_rng(seed)
        self.offset = rng.normal(0.0, sigma_het, size=n_sets)

    def window(self, t, dueling=None, gate_state=None):
        w = self.base.window(t, dueling=dueling, gate_state=gate_state)
        w.u_C = np.clip(w.u_C + self.offset, -0.286, 1.0)
        return w


def main():
    C.setstyle()
    sigmas = [0.0, 0.05, 0.10, 0.15, 0.20, 0.30]
    out = {"sigma_het": sigmas, "mim_tpr": [], "clean_fpr": [], "floor_viol": [], "det_lat": []}
    for sg in sigmas:
        mim, fpr, fv, lat = [], [], [], []
        for s in range(SEEDS):
            comp = C.make_competence()
            # mimicry detection under heterogeneity
            env, b = C.make_bouncer("full", comp=comp, seed=s)
            sim = C.simconfig(T=T)
            adv = HeteroWrap(MimicryAttack(C.STD["n_sets"], onset=ONSET, stress=0.9, seed=1000 + s),
                             C.STD["n_sets"], sg, seed=500 + s)
            dfm = run_episode(comp, env, b, adv, sim, seed=2000 + s)
            mim.append(M.detected(dfm, b.cfg.tau, deadline=40))
            # clean FPR under heterogeneity
            env2, b2 = C.make_bouncer("full", comp=comp, seed=s)
            advc = HeteroWrap(Clean(C.STD["n_sets"], seed=3000 + s), C.STD["n_sets"], sg, seed=500 + s)
            dfc = run_episode(comp, env2, b2, advc, sim, seed=4000 + s)
            fpr.append(M.first_gated(dfc) is not None)
            # floor + latency under heterogeneity (broad attack)
            env3, b3 = C.make_bouncer("full", comp=comp, seed=s)
            adva = HeteroWrap(BroadAttack(C.STD["n_sets"], onset=ONSET, stress=0.92, seed=6000 + s),
                              C.STD["n_sets"], sg, seed=500 + s)
            dfa = run_episode(comp, env3, b3, adva, sim, seed=7000 + s)
            fv.append(M.steady_state_floor_violation(dfa))
            l = M.detection_latency(dfa, b3.cfg.tau)
            if l is not None and np.isfinite(l):
                lat.append(l)
        out["mim_tpr"].append(float(np.mean(mim)))
        out["clean_fpr"].append(float(np.mean(fpr)))
        out["floor_viol"].append(float(np.nanmean(fv)))
        out["det_lat"].append(float(np.mean(lat)) if lat else float("nan"))
        print(f"  sigma_het={sg:.2f}: mim TPR={out['mim_tpr'][-1]:.2f} cleanFPR={out['clean_fpr'][-1]:.2f} "
              f"floor={out['floor_viol'][-1]*100:.2f}% lat={out['det_lat'][-1]:.1f}")

    fig, ax = plt.subplots(figsize=(3.9, 2.9))
    ax.plot(sigmas, out["mim_tpr"], "o-", color=C.PALETTE["bouncer"], label="mimicry TPR")
    ax.plot(sigmas, out["clean_fpr"], "s--", color=C.PALETTE["sin"], label="clean FPR")
    ax.set_xlabel(r"set heterogeneity $\sigma_{het}$ (violating i.i.d.)")
    ax.set_ylabel("rate"); ax.set_ylim(-0.05, 1.08); ax.legend(loc="center left")
    ax2 = ax.twinx()
    ax2.plot(sigmas, [f * 100 for f in out["floor_viol"]], "^:", color=C.PALETTE["accent"], lw=1.1)
    ax2.set_ylabel("steady floor violation (%)", color=C.PALETTE["accent"])
    ax2.tick_params(axis="y", labelcolor=C.PALETTE["accent"]); ax2.grid(False)
    ax.set_title("Graceful degradation under set heterogeneity")
    C.savefig(fig, "robust_env.pdf")
    C.save_json("robust_env.json", out)


if __name__ == "__main__":
    main()
