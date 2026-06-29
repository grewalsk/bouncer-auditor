"""
Sensitivity / robustness: is the operating point cherry-picked? Sweep the trust
threshold tau and the Tier-B CUSUM threshold H over a grid; report mean detection
latency (on a broad attack) and clean false-alarm rate. A broad robust plateau
around the chosen point (tau=0.05, H=0.8) shows the result is not knife-edge.
Outputs: results/sensitivity.json, figures/sensitivity.pdf
"""
import numpy as np
import matplotlib.pyplot as plt

import common as C
from bouncer.adversary import Clean, BroadAttack
from bouncer.simulate import run_episode
from bouncer import metrics as M

ONSET, T, SEEDS = 80, 200, 6
TAUS = [0.0, 0.025, 0.05, 0.075, 0.10, 0.15]
HS = [0.2, 0.4, 0.8, 1.2, 1.6, 2.4]


def cell(tau, H):
    lats, fps = [], []
    for s in range(SEEDS):
        comp = C.make_competence()
        env, b = C.make_bouncer("full", comp=comp, tau=tau, tierb_H=H, seed=s)
        sim = C.simconfig(T=T)
        dfa = run_episode(comp, env, b, BroadAttack(C.STD["n_sets"], onset=ONSET, stress=0.9, seed=100 + s), sim, seed=200 + s)
        l = M.detection_latency(dfa, tau)
        if l is not None and np.isfinite(l):
            lats.append(l)
        env2, b2 = C.make_bouncer("full", comp=comp, tau=tau, tierb_H=H, seed=s)
        dfc = run_episode(comp, env2, b2, Clean(C.STD["n_sets"], seed=300 + s), sim, seed=400 + s)
        fps.append(M.first_gated(dfc) is not None)
    lat = np.mean(lats) if lats else np.nan
    miss = 1.0 - len(lats) / SEEDS
    return lat, float(np.mean(fps)), miss


def main():
    C.setstyle()
    LAT = np.full((len(TAUS), len(HS)), np.nan)
    FPR = np.full((len(TAUS), len(HS)), np.nan)
    MISS = np.full((len(TAUS), len(HS)), np.nan)
    for i, tau in enumerate(TAUS):
        for j, H in enumerate(HS):
            LAT[i, j], FPR[i, j], MISS[i, j] = cell(tau, H)
        print(f"  tau={tau}: lat row={np.round(LAT[i],1)} fpr row={np.round(FPR[i],2)}")

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0))
    ax = axes[0]
    im = ax.imshow(LAT, origin="lower", aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(HS))); ax.set_xticklabels(HS, fontsize=6.5)
    ax.set_yticks(range(len(TAUS))); ax.set_yticklabels(TAUS, fontsize=6.5)
    ax.set_xlabel("CUSUM threshold $H$"); ax.set_ylabel(r"trust threshold $\tau$")
    ax.set_title("(a) detection latency (windows)")
    fig.colorbar(im, ax=ax, fraction=0.046)
    # mark operating point (tau=0.05 -> idx 2, H=0.8 -> idx 2)
    ax.plot(2, 2, "*", color="white", ms=12, mec="k")
    ax = axes[1]
    im = ax.imshow(FPR, origin="lower", aspect="auto", cmap="rocket_r" if False else "magma")
    ax.set_xticks(range(len(HS))); ax.set_xticklabels(HS, fontsize=6.5)
    ax.set_yticks(range(len(TAUS))); ax.set_yticklabels(TAUS, fontsize=6.5)
    ax.set_xlabel("CUSUM threshold $H$"); ax.set_ylabel(r"trust threshold $\tau$")
    ax.set_title("(b) clean false-alarm rate")
    fig.colorbar(im, ax=ax, fraction=0.046)
    ax.plot(2, 2, "*", color="white", ms=12, mec="k")
    C.savefig(fig, "sensitivity.pdf")

    C.save_json("sensitivity.json", dict(taus=TAUS, Hs=HS, latency=LAT.tolist(),
                fpr=FPR.tolist(), miss=MISS.tolist(),
                operating_point=dict(tau=0.05, H=0.8, latency=float(LAT[2, 2]), fpr=float(FPR[2, 2]))))
    # robustness summary: fraction of grid with fast detection AND no false alarms
    good = (LAT <= 3) & (FPR <= 0.05) & (MISS == 0)
    print(f"  operating point (0.05,0.8): lat={LAT[2,2]:.1f} fpr={FPR[2,2]:.2f}")
    print(f"  robust plateau: {good.sum()}/{good.size} grid cells have lat<=3 & FPR<=0.05 & no misses")


if __name__ == "__main__":
    main()
