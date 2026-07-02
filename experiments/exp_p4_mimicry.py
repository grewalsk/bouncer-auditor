"""
P4 — Adaptive adversary (the headline). Two results:

(A) Mimicry survival. An adaptive adversary degrades C's competence while holding
    the input-distribution tripwire S_in in-distribution. The "input-OOD-only"
    baseline (S_in alone — the standard OOD-monitoring approach) collapses to its
    false-positive floor; full Bouncer holds high TPR because it measures realized
    competence (S_res + Tier-B), not input distribution.
    -> figures/p4_mimicry_survival.pdf

(B) Randomized-secret ablation (empirical Prop 1). The strongest adversary also
    spoofs aggregate Tier-A and mounts a redistributive covert attack on a victim
    region; only the SECRET per-region set-dueling remains. Detection power vs the
    leaked fraction f of the secret assignment: high at f=0, collapsing as f->1.
    The evasion budget is bounded by sigma_Delta.
    -> figures/p4_secrecy_ablation.pdf
"""
import numpy as np
import matplotlib.pyplot as plt

import common as C
from bouncer.adversary import Clean, MimicryAttack, RegionalCovertAttack
from bouncer.simulate import run_episode
from bouncer import metrics as M

ONSET, T = 90, 280
N_EPISODES = 40


def mimicry_survival():
    """TPR of S_in-only vs full Bouncer under mimicry, swept over attack strength.
    Also FPR on clean to anchor the ROC interpretation."""
    strengths = [0.55, 0.65, 0.75, 0.85, 0.95]
    out = {"strength": strengths, "full_tpr": [], "sin_tpr": []}
    for s in strengths:
        full_det, sin_det = [], []
        for ep in range(N_EPISODES):
            comp = C.make_competence()
            env, b = C.make_bouncer("full", comp=comp, seed=ep)
            sim = C.simconfig(T=T)
            adv = MimicryAttack(C.STD["n_sets"], onset=ONSET, stress=s, seed=1000 + ep)
            df = run_episode(comp, env, b, adv, sim, seed=2000 + ep)
            full_det.append(M.detected(df, b.cfg.tau, deadline=40))

            env2, b2 = C.make_bouncer("s_in_only", comp=comp, seed=ep)
            adv2 = MimicryAttack(C.STD["n_sets"], onset=ONSET, stress=s, seed=1000 + ep)
            df2 = run_episode(comp, env2, b2, adv2, sim, seed=2000 + ep)
            sin_det.append(M.detected(df2, b2.cfg.tau, deadline=40))
        out["full_tpr"].append(float(np.mean(full_det)))
        out["sin_tpr"].append(float(np.mean(sin_det)))
        print(f"  mimicry stress={s:.2f}: full TPR={np.mean(full_det):.2f}  S_in-only TPR={np.mean(sin_det):.2f}")
    # clean FPR for both (deadline irrelevant; any gate on clean is a FP)
    fpr_full, fpr_sin = [], []
    for ep in range(N_EPISODES):
        comp = C.make_competence()
        env, b = C.make_bouncer("full", comp=comp, seed=ep)
        sim = C.simconfig(T=T)
        df = run_episode(comp, env, b, Clean(C.STD["n_sets"], seed=3000 + ep), sim, seed=4000 + ep)
        fpr_full.append(M.first_gated(df) is not None)
        env2, b2 = C.make_bouncer("s_in_only", comp=comp, seed=ep)
        df2 = run_episode(comp, env2, b2, Clean(C.STD["n_sets"], seed=3000 + ep), sim, seed=4000 + ep)
        fpr_sin.append(M.first_gated(df2) is not None)
    out["full_fpr"] = float(np.mean(fpr_full))
    out["sin_fpr"] = float(np.mean(fpr_sin))
    print(f"  clean FPR: full={out['full_fpr']:.2f}  S_in-only={out['sin_fpr']:.2f}")
    return out


def secrecy_ablation():
    """Per-region covert attack; TPR + detection latency vs leaked secret fraction f."""
    fracs = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    region = np.arange(0, 256)          # contested victim region (1/8 of sets)
    out = {"frac": fracs, "tpr": [], "latency": [], "latency_std": []}
    for f in fracs:
        det, lats = [], []
        for ep in range(N_EPISODES):
            comp = C.make_competence()
            env, b = C.make_bouncer("full", comp=comp, region=region, seed=ep)
            sim = C.simconfig(T=T)
            adv = RegionalCovertAttack(C.STD["n_sets"], region=region, onset=ONSET,
                                       sink_stress=0.92, known_frac=f, seed=1000 + ep)
            df = run_episode(comp, env, b, adv, sim, seed=2000 + ep)
            lat = M.detection_latency_onset(df, ONSET)
            d = np.isfinite(lat) and lat <= 40
            det.append(d)
            if d:
                lats.append(lat)
        out["tpr"].append(float(np.mean(det)))
        out["latency"].append(float(np.mean(lats)) if lats else float("inf"))
        out["latency_std"].append(float(np.std(lats)) if lats else 0.0)
        print(f"  secrecy f={f:.1f}: TPR={np.mean(det):.2f}  mean latency={out['latency'][-1]}")
    return out


def main():
    C.setstyle()
    surv = mimicry_survival()
    abl = secrecy_ablation()

    # --- Figure A: mimicry survival ---
    fig, ax = plt.subplots(figsize=(3.7, 2.8))
    s = surv["strength"]
    ax.plot(s, surv["full_tpr"], "o-", color=C.PALETTE["bouncer"], lw=1.8,
            label="full Bouncer (competence)")
    ax.plot(s, surv["sin_tpr"], "s--", color=C.PALETTE["sin"], lw=1.6,
            label="input-OOD-only ($S_{in}$)")
    ax.axhline(surv["sin_fpr"], color=C.PALETTE["sin"], lw=0.7, ls=":")
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlabel("mimicry attack strength (stress)")
    ax.set_ylabel("detection TPR")
    ax.set_title("Mimicry survival: behaviour beats input-OOD")
    ax.legend(loc="center left")
    ax.text(s[0], surv["sin_fpr"] + 0.03, "$S_{in}$ FPR floor", color=C.PALETTE["sin"], fontsize=6.5)
    C.savefig(fig, "p4_mimicry_survival.pdf")

    # --- Figure B: secrecy ablation ---
    fig, ax = plt.subplots(figsize=(3.7, 2.8))
    f = abl["frac"]
    ax.plot(f, abl["tpr"], "o-", color=C.PALETTE["accent"], lw=1.8, label="detection TPR")
    ax.set_xlabel("leaked fraction of secret assignment $f$")
    ax.set_ylabel("detection TPR", color=C.PALETTE["accent"])
    ax.set_ylim(-0.05, 1.05)
    ax.tick_params(axis="y", labelcolor=C.PALETTE["accent"])
    ax2 = ax.twinx()
    lat = [l if np.isfinite(l) else np.nan for l in abl["latency"]]
    ax2.plot(f, lat, "s--", color=C.PALETTE["bouncer"], lw=1.4, label="detection latency")
    ax2.set_ylabel("detection latency (windows)", color=C.PALETTE["bouncer"])
    ax2.tick_params(axis="y", labelcolor=C.PALETTE["bouncer"])
    ax2.grid(False)
    ax.set_title("Prop 1: secrecy is load-bearing")
    ax.axvspan(0.0, 0.0, color="none")
    C.savefig(fig, "p4_secrecy_ablation.pdf")

    C.save_json("p4.json", dict(mimicry_survival=surv, secrecy_ablation=abl,
                                n_episodes=N_EPISODES))


if __name__ == "__main__":
    main()
