"""R-latency (E3, positive form): detection LATENCY and fixed-deadline TPR vs competence gap.

The E3 detectability sweep showed TPR flat at 1.0, but that number counted *any* gate before
a generous 140-window horizon -- it hides the fact that near the boundary detection is slow.
Two honesty fixes over the earlier version:

  1. SIGMA IS PATH-DEPENDENT. Detection while TRUSTED runs on the small background leader pool
     (n_bg=8 => sigma_bg=0.03125), not the full pool (n_L=32 => sigma_full=0.01563). So the
     minimum standardized drift at the tau boundary, (gamma/2)/sigma, is 1.6 sigma on the
     background/TRUSTED path -- NOT 3.2 sigma (that is the full-duty value, reached only after
     Tier-A escalates to SUSPECT/PROBING). Per-domain audits use even smaller pools and see less.
  2. TPR IS REPORTED AT FIXED DEADLINES. For each gap we report the fraction gated within
     {10, 20, 40} windows, not just "ever." Near tau the short-deadline TPR is low even though
     every episode eventually gates: latency, not deadline-free TPR, is the supported result.

Note on the escalation path: BroadAttack shifts the input marginal, so Tier-A escalates and the
audit runs at FULL duty (32 leaders) during detection here; the deep-drop latencies below are on
that escalated path. A pure competence drop that does not move Tier-A would detect on the slower
background path. Deterministic; emits results/rlatency.json + figures/rlatency.pdf.
"""
import sys, json, os
import numpy as np
sys.path.insert(0, 'experiments')
import common as C
import matplotlib.pyplot as plt
from bouncer.adversary import BroadAttack
from bouncer.simulate import run_episode

DEADLINES = [10, 20, 40]   # windows-after-onset deadlines for fixed-deadline TPR


def u_for_delta(comp, target):
    """Stress u giving true competence advantage `target`: delta_true(u)=a_C-b_C*u-q0."""
    return float((comp.a_C - comp.q0 - target) / comp.b_C)


def _sigma(m, n):
    """sigma_Delta for a symmetric pool of n Leader-C and n Leader-F sets, m decisions/set."""
    return float(np.sqrt((1.0 / (4 * m)) * (2.0 / n)))


def cell(target, n_ep=40, T=140, onset=20):
    comp = C.make_competence()
    K = C.STD["tau"] + C.STD["gamma_detect"] / 2
    H = C.STD["tierb_H"]
    u = float(np.clip(u_for_delta(comp, target), 0.0, 1.0))
    lats = []
    for s in range(n_ep):
        env, b = C.make_bouncer("full", comp=comp, seed=s)
        sim = C.simconfig(T=T)
        adv = BroadAttack(C.STD["n_sets"], onset=onset, offset=None, stress=u, seed=s + 300)
        df = run_episode(comp, env, b, adv, sim, seed=s + 400)
        st = df.state.values
        g = [t for t in range(onset, len(st)) if st[t] == "GATED"]
        lats.append((g[0] - onset) if g else np.inf)
    lats = np.array(lats, float)
    margin = K - target
    D_pred = float(H / margin) if margin > 0 else float("inf")   # deterministic-drift limit
    sigma_full = _sigma(C.STD["m"], C.STD["n_L"])       # full-duty pool (SUSPECT/PROBING)
    sigma_bg = _sigma(C.STD["m"], C.STD["n_L_bg"])      # background/TRUSTED pool
    tpr_by = {f"tpr_by_{d}": float(np.mean(lats <= d)) for d in DEADLINES}
    finite = lats[np.isfinite(lats)]
    return dict(target=round(target, 3), u=round(u, 4), n_ep=n_ep,
                tpr_ever=float(np.mean(np.isfinite(lats))),   # gated at all before horizon
                **tpr_by,
                lat_mean=float(np.mean(finite)) if finite.size else float("inf"),
                lat_median=float(np.median(finite)) if finite.size else float("inf"),
                D_pred=D_pred,
                drift_sigma_full=float(margin / sigma_full),
                drift_sigma_bg=float(margin / sigma_bg))


def main():
    C.setstyle()
    # all targets are off-policy (< tau=0.05); sweep from a deep drop up to just below tau
    targets = [-0.344, -0.20, -0.10, -0.05, -0.02, 0.00, 0.02, 0.04]
    rows = [cell(t) for t in targets]
    for r in rows:
        print(f"  Delta={r['target']:+.3f} (drift {r['drift_sigma_bg']:.1f} sd bg / "
              f"{r['drift_sigma_full']:.1f} sd full): latency={r['lat_mean']:.1f}  D_pred={r['D_pred']:.1f}  "
              f"TPR@10={r['tpr_by_10']:.2f} @20={r['tpr_by_20']:.2f} @40={r['tpr_by_40']:.2f}")

    # sanity on the sigma claim
    sf, sb = _sigma(C.STD["m"], C.STD["n_L"]), _sigma(C.STD["m"], C.STD["n_L_bg"])
    min_drift_full = (C.STD["gamma_detect"] / 2) / sf
    min_drift_bg = (C.STD["gamma_detect"] / 2) / sb
    print(f"  min standardized drift at tau: full-duty {min_drift_full:.2f} sigma; "
          f"background/TRUSTED {min_drift_bg:.2f} sigma  (sigma_full={sf:.5f}, sigma_bg={sb:.5f})")

    # every episode eventually gates across the range (given the horizon)...
    ever_all = all(r["tpr_ever"] >= 0.95 for r in rows)
    # ...but the short-deadline TPR DROPS as the gap approaches tau (latency, not TPR, is the result)
    tpr10 = [r["tpr_by_10"] for r in rows]
    deadline_tpr_degrades = tpr10[0] > tpr10[-1]     # deep drop gates fast; near-tau does not
    # latency rises toward the boundary and tracks the deterministic-drift prediction
    lm = [r["lat_mean"] for r in rows]
    rises = lm[-1] > lm[0]
    ratios = [r["lat_mean"] / r["D_pred"] for r in rows if np.isfinite(r["D_pred"]) and r["D_pred"] > 0]
    tracks = max(ratios) / min(ratios) < 3.0 if ratios else False
    print(f"  gates-ever across range: {ever_all} | short-deadline TPR degrades near tau: "
          f"{deadline_tpr_degrades} | latency rises Delta->tau: {rises} | tracks D within band: {tracks}")

    fig, ax = plt.subplots(figsize=(4.4, 2.9))
    d = np.array([r["target"] for r in rows])
    ax.plot(d, [r["D_pred"] for r in rows], "s--", color="k", label=r"prediction $D{=}H/(K{-}\Delta)$")
    ax.plot(d, [r["lat_mean"] for r in rows], "o-", color=C.PALETTE["bouncer"], label="measured latency")
    ax2 = ax.twinx()
    ax2.plot(d, [r["tpr_by_10"] for r in rows], "^:", color=C.PALETTE["oracle"], label="TPR@10", alpha=0.8)
    ax2.plot(d, [r["tpr_by_20"] for r in rows], "v:", color=C.PALETTE["sin"], label="TPR@20", alpha=0.8)
    ax2.set_ylabel("TPR at fixed deadline"); ax2.set_ylim(0, 1.05)
    ax.axvline(C.STD["tau"], color=C.PALETTE["unguarded"], lw=0.8, ls=":")
    ax.annotate(r"$\tau$", xy=(C.STD["tau"], ax.get_ylim()[1] * 0.9), color=C.PALETTE["unguarded"], fontsize=8)
    ax.set_xlabel(r"true competence $\Delta$ (off-policy: $\Delta<\tau$)")
    ax.set_ylabel("detection latency (windows)")
    ax.set_title("Latency tracks $H/(K{-}\\Delta)$; fixed-deadline TPR falls near $\\tau$")
    ax.legend(loc="upper left", fontsize=6.5)
    ax2.legend(loc="lower left", fontsize=6.5)
    C.savefig(fig, "rlatency.pdf")

    C.save_json("rlatency.json", dict(
        note=("Positive form of E3. Detection LATENCY rises toward the tau boundary tracking the "
              "deterministic-drift limit D=H/(K-Delta). Every episode eventually gates within the "
              "horizon, but the fixed-deadline TPR (by 10/20/40 windows) falls as the gap approaches "
              "tau -- latency, not deadline-free TPR, is the supported result. The minimum "
              "standardized drift at tau is 1.6 sigma on the background/TRUSTED pool (n_bg=8), and "
              "3.2 sigma only at full duty (n_L=32) after Tier-A escalation; per-domain pools see less."),
        K=C.STD["tau"] + C.STD["gamma_detect"] / 2, H=C.STD["tierb_H"], tau=C.STD["tau"],
        sigma_full=sf, sigma_bg=sb,
        min_drift_full_sigma=min_drift_full, min_drift_bg_sigma=min_drift_bg,
        deadlines=DEADLINES, cells=rows,
        invariants=dict(gates_ever_across_range=ever_all,
                        deadline_tpr_degrades_near_tau=deadline_tpr_degrades,
                        latency_rises_toward_tau=rises,
                        latency_tracks_prediction=tracks)))
    # regressions: the positive result must hold, honestly stated
    assert ever_all, "every gap should eventually gate within the horizon"
    assert rises, "latency should rise as Delta -> tau"
    assert deadline_tpr_degrades, "short-deadline TPR should degrade near tau (latency is the result)"


if __name__ == "__main__":
    main()
