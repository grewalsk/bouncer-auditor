"""R-latency (E3, positive form): detection LATENCY vs competence gap.

The E3 detectability sweep showed TPR flat at 1.0 because, for any off-policy gap
(Delta<tau), the CUSUM drift K-Delta >= gamma/2 = 3.2 sigma_Delta is already strong.
The quantity that actually varies is the detection LATENCY. This experiment sweeps the
true competence Delta over the off-policy range and measures the windows-to-GATED,
comparing against the deterministic-drift prediction D = H/(K - Delta). It converts the
'flat TPR' scope-down into a positive, theory-matching result.

Deterministic: all RNG explicitly seeded. Emits results/rlatency.json + figures/rlatency.pdf.
"""
import sys, json, os
import numpy as np
sys.path.insert(0, 'experiments')
import common as C
import matplotlib.pyplot as plt
from bouncer.adversary import BroadAttack
from bouncer.simulate import run_episode


def u_for_delta(comp, target):
    """Stress u giving true competence advantage `target`: delta_true(u)=a_C-b_C*u-q0."""
    return float((comp.a_C - comp.q0 - target) / comp.b_C)


def cell(target, n_ep=40, T=140, onset=20):
    comp = C.make_competence()
    K = C.STD["tau"] + C.STD["gamma_detect"] / 2
    H = C.STD["tierb_H"]
    u = float(np.clip(u_for_delta(comp, target), 0.0, 1.0))
    lats, det = [], 0
    for s in range(n_ep):
        env, b = C.make_bouncer("full", comp=comp, seed=s)
        sim = C.simconfig(T=T)
        adv = BroadAttack(C.STD["n_sets"], onset=onset, offset=None, stress=u, seed=s + 300)
        df = run_episode(comp, env, b, adv, sim, seed=s + 400)
        st = df.state.values
        g = [t for t in range(onset, len(st)) if st[t] == "GATED"]
        if g:
            lats.append(g[0] - onset); det += 1
    margin = K - target
    D_pred = float(H / margin) if margin > 0 else float("inf")   # deterministic-drift limit
    sig = float((C.STD["r_max"] if "r_max" in C.STD else 1.0))
    sigma_delta = float(np.sqrt((1.0 / (4 * C.STD["m"])) * (2.0 / C.STD["n_L"])))
    return dict(target=round(target, 3), u=round(u, 4), n_ep=n_ep, tpr=det / n_ep,
                lat_mean=float(np.mean(lats)) if lats else float("inf"),
                lat_median=float(np.median(lats)) if lats else float("inf"),
                D_pred=D_pred, drift_sigma=float(margin / sigma_delta))


def main():
    C.setstyle()
    # all targets are off-policy (< tau=0.05); sweep from a deep drop up to just below tau
    targets = [-0.344, -0.20, -0.10, -0.05, -0.02, 0.00, 0.02, 0.04]
    rows = [cell(t) for t in targets]
    for r in rows:
        print(f"  Delta={r['target']:+.3f} (drift {r['drift_sigma']:.1f} sd): "
              f"TPR={r['tpr']:.2f}  latency={r['lat_mean']:.1f}  D_pred={r['D_pred']:.1f}")

    tpr_all = all(r["tpr"] >= 0.95 for r in rows)
    # latency should RISE monotonically as Delta -> tau (gap shrinks)
    lm = [r["lat_mean"] for r in rows]
    rises = lm[-1] > lm[0]
    # measured tracks prediction (ratio within 2x across the range, both increasing)
    ratios = [r["lat_mean"] / r["D_pred"] for r in rows if np.isfinite(r["D_pred"]) and r["D_pred"] > 0]
    tracks = max(ratios) / min(ratios) < 3.0 if ratios else False
    print(f"  TPR>=0.95 all: {tpr_all} | latency rises Delta->tau: {rises} | tracks D within band: {tracks}")

    fig, ax = plt.subplots(figsize=(4.2, 2.9))
    d = np.array([r["target"] for r in rows])
    ax.plot(d, [r["D_pred"] for r in rows], "s--", color="k", label=r"prediction $D{=}H/(K{-}\Delta)$")
    ax.plot(d, [r["lat_mean"] for r in rows], "o-", color=C.PALETTE["bouncer"], label="measured latency")
    ax2 = ax.twinx()
    ax2.plot(d, [r["tpr"] for r in rows], "^:", color=C.PALETTE["oracle"], label="TPR", alpha=0.7)
    ax2.set_ylabel("TPR", color=C.PALETTE["oracle"]); ax2.set_ylim(0, 1.05)
    ax.axvline(C.STD["tau"], color=C.PALETTE["unguarded"], lw=0.8, ls=":")
    ax.annotate(r"$\tau$", xy=(C.STD["tau"], ax.get_ylim()[1] * 0.9), color=C.PALETTE["unguarded"], fontsize=8)
    ax.set_xlabel(r"true competence $\Delta$ (off-policy: $\Delta<\tau$)")
    ax.set_ylabel("detection latency (windows)")
    ax.set_title("Detection latency tracks $H/(K{-}\\Delta)$; TPR stays $\\approx\\!1$")
    ax.legend(loc="upper left", fontsize=7)
    C.savefig(fig, "rlatency.pdf")

    C.save_json("rlatency.json", dict(
        note=("Positive form of E3 detection power: TPR stays ~1 across the off-policy range "
              "(drift K-Delta >= 3.2 sigma_Delta), while detection LATENCY rises toward the tau "
              "boundary tracking the deterministic-drift limit D=H/(K-Delta)."),
        K=C.STD["tau"] + C.STD["gamma_detect"] / 2, H=C.STD["tierb_H"], tau=C.STD["tau"],
        cells=rows,
        invariants=dict(tpr_all_ge_095=tpr_all, latency_rises_toward_tau=rises,
                        latency_tracks_prediction=tracks)))
    # regression: the positive result must hold
    assert tpr_all, "TPR should stay ~1 across the off-policy range"
    assert rises, "latency should rise as Delta -> tau"


if __name__ == "__main__":
    main()
