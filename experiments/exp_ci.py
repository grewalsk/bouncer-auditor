"""
Multi-seed statistical rigor: confidence intervals on every headline number.
Addresses the review finding that single-seed absolute claims (TPR=1.0, FPR=0,
floor=0.6%) need uncertainty. We report Wilson 95% intervals for rates and
bootstrap/normal 95% intervals for continuous metrics, over N_SEEDS independent
episodes.
Outputs: results/ci.json, figures/ci_mimicry.pdf
"""
import numpy as np
import matplotlib.pyplot as plt

import common as C
from bouncer.adversary import Clean, MimicryAttack, BroadAttack, RegionalCovertAttack
from bouncer.simulate import run_episode
from bouncer import metrics as M

N_SEEDS = 50
ONSET, T = 90, 260


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0, c - h), min(1, c + h))


def mean_ci(x, z=1.96):
    x = np.asarray(x, float)
    if len(x) == 0:
        return (float("nan"), float("nan"), float("nan"))
    m = x.mean(); se = x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0
    return (float(m), float(m - z * se), float(m + z * se))


def run_one(mode, adv_factory, seed):
    comp = C.make_competence()
    env, b = C.make_bouncer(mode, comp=comp, seed=seed)
    sim = C.simconfig(T=T)
    return run_episode(comp, env, b, adv_factory(seed), sim, seed=seed + 9000), b


def main():
    C.setstyle()
    res = {}

    # --- mimicry survival: full vs s_in_only TPR + clean FPR ---
    full_det = []; sin_det = []
    for s in range(N_SEEDS):
        df, b = run_one("full", lambda sd: MimicryAttack(C.STD["n_sets"], onset=ONSET, stress=0.9, seed=1000 + sd), s)
        full_det.append(M.detected(df, b.cfg.tau, deadline=40))
        df2, b2 = run_one("s_in_only", lambda sd: MimicryAttack(C.STD["n_sets"], onset=ONSET, stress=0.9, seed=1000 + sd), s)
        sin_det.append(M.detected(df2, b2.cfg.tau, deadline=40))
    full_fp = []; sin_fp = []
    for s in range(N_SEEDS):
        df, b = run_one("full", lambda sd: Clean(C.STD["n_sets"], seed=3000 + sd), s)
        full_fp.append(M.first_gated(df) is not None)
        df2, b2 = run_one("s_in_only", lambda sd: Clean(C.STD["n_sets"], seed=3000 + sd), s)
        sin_fp.append(M.first_gated(df2) is not None)
    res["mimicry"] = dict(
        full_tpr=wilson(sum(full_det), N_SEEDS), sin_tpr=wilson(sum(sin_det), N_SEEDS),
        full_fpr=wilson(sum(full_fp), N_SEEDS), sin_fpr=wilson(sum(sin_fp), N_SEEDS), n=N_SEEDS)
    print(f"  mimicry full TPR={res['mimicry']['full_tpr']}, sin TPR={res['mimicry']['sin_tpr']}")
    print(f"  clean FPR full={res['mimicry']['full_fpr']}, sin={res['mimicry']['sin_fpr']}")

    # --- P1 floor metrics with CIs (broad attack) ---
    lat = []; fv = []; ctax = []
    for s in range(N_SEEDS):
        df, b = run_one("full", lambda sd: BroadAttack(C.STD["n_sets"], onset=ONSET, stress=0.92, seed=2000 + sd), s)
        l = M.detection_latency(df, b.cfg.tau)
        if l is not None and np.isfinite(l):
            lat.append(l)
        fv.append(M.steady_state_floor_violation(df))
        dfc, _ = run_one("full", lambda sd: Clean(C.STD["n_sets"], seed=4000 + sd), s)
        ctax.append(M.clean_tax(dfc))
    res["floor"] = dict(detection_latency=mean_ci(lat), steady_floor_violation=mean_ci(fv),
                        clean_tax=mean_ci(ctax), n=N_SEEDS)
    print(f"  detection latency={res['floor']['detection_latency']}")
    print(f"  steady floor viol={res['floor']['steady_floor_violation']}")
    print(f"  clean tax={res['floor']['clean_tax']}")

    # --- secrecy ablation with CIs (per-region covert) ---
    fracs = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    region = np.arange(0, 256)
    sec = {"frac": fracs, "tpr": [], "tpr_lo": [], "tpr_hi": []}
    for f in fracs:
        det = 0
        for s in range(N_SEEDS):
            comp = C.make_competence()
            env, b = C.make_bouncer("full", comp=comp, region=region, seed=s)
            sim = C.simconfig(T=T)
            adv = RegionalCovertAttack(C.STD["n_sets"], region=region, onset=ONSET,
                                       sink_stress=0.92, known_frac=f, seed=1000 + s)
            df = run_episode(comp, env, b, adv, sim, seed=s + 9000)
            l = M.detection_latency_onset(df, ONSET)
            det += int(np.isfinite(l) and l <= 40)
        p, lo, hi = wilson(det, N_SEEDS)
        sec["tpr"].append(p); sec["tpr_lo"].append(lo); sec["tpr_hi"].append(hi)
        print(f"  secrecy f={f}: TPR={p:.3f} [{lo:.2f},{hi:.2f}]")
    res["secrecy"] = sec

    C.save_json("ci.json", res)

    # --- figure: mimicry + secrecy with CIs ---
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8))
    ax = axes[0]
    labels = ["full\nBouncer", "input-OOD\nonly"]
    vals = [res["mimicry"]["full_tpr"], res["mimicry"]["sin_tpr"]]
    xs = [0, 1]
    for x, (p, lo, hi), col in zip(xs, vals, [C.PALETTE["bouncer"], C.PALETTE["sin"]]):
        ax.bar(x, p, 0.55, color=col)
        ax.errorbar(x, p, yerr=[[p - lo], [hi - p]], fmt="none", ecolor="k", capsize=4, lw=1)
    ax.set_xticks(xs); ax.set_xticklabels(labels)
    ax.set_ylabel("mimicry detection TPR"); ax.set_ylim(0, 1.08)
    ax.set_title(f"(a) mimicry survival (N={N_SEEDS}, Wilson 95%)")
    ax.text(0, 1.02, "Wilson 95%", ha="center", fontsize=6.5, color="#555")
    ax = axes[1]
    f = sec["frac"]
    ax.plot(f, sec["tpr"], "o-", color=C.PALETTE["accent"], lw=1.6)
    ax.fill_between(f, sec["tpr_lo"], sec["tpr_hi"], color=C.PALETTE["accent"], alpha=0.2, lw=0)
    ax.set_xlabel("leaked secret fraction $f$"); ax.set_ylabel("detection TPR")
    ax.set_ylim(-0.05, 1.08); ax.set_title(f"(b) secrecy ablation (N={N_SEEDS}, 95% band)")
    C.savefig(fig, "ci_mimicry.pdf")


if __name__ == "__main__":
    main()
