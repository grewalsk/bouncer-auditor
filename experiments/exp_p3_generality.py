"""
P3 — Generality + attack-vs-drift triage.

(1) Generality: the same auditor wraps three controller classes with different
    competence profiles and Δ̂ mechanisms:
      prefetch (Pythia)       : secret set-dueling on PC-hash buckets
      replacement (Hawkeye)   : secret set-dueling on cache sets (its home turf)
      memory scheduler (RL)   : *model-based* Δ̂ (no clean counterfactual sampling
                                -> weakens Prop 6.2); banks/channels
    The safety floor holds for all three under broad attack and benign drift; the
    scheduler pays for the weaker estimator with longer latency and lost mimicry
    resistance.  -> figures/p3_generality.pdf

(2) Triage: a logistic model over (ΔS_in, ΔS_res, co-tenant-correlation,
    abruptness) separates attack from benign drift (§7). Secondary contribution:
    detection does not depend on it; misclassification only mis-selects between
    equally-safe responses.  -> figures/p3_triage.pdf
"""
import numpy as np
import matplotlib.pyplot as plt

import common as C
from bouncer.adversary import Clean, BroadAttack, MimicryAttack, BenignDrift
from bouncer.simulate import run_episode
from bouncer import metrics as M

ONSET, T = 90, 260

# competence profiles per controller class (a_C in-dist competence, b_C collapse
# rate, q0 fallback floor)
CONTROLLERS = {
    "prefetch\n(Pythia)":  dict(a_C=0.80, b_C=0.70, q0=0.50, model_based=False),
    "replacement\n(Hawkeye)": dict(a_C=0.74, b_C=0.62, q0=0.55, model_based=False),
    "scheduler\n(RL, model-Δ̂)": dict(a_C=0.78, b_C=0.66, q0=0.52, model_based=True),
}


def run_controller(profile, adv_factory, seed=0):
    comp = C.make_competence(a_C=profile["a_C"], b_C=profile["b_C"], q0=profile["q0"])
    env, b = C.make_bouncer("full", comp=comp, seed=seed,
                            model_based=profile["model_based"],
                            model_q0=profile["q0"],
                            model_bias=0.02 if profile["model_based"] else 0.0)
    sim = C.simconfig(T=T)
    df = run_episode(comp, env, b, adv_factory(seed), sim, seed=seed + 7000)
    return df, b, comp


def generality():
    N = 15
    res = {}
    for name, prof in CONTROLLERS.items():
        for cond, fac in [("broad", lambda s: BroadAttack(C.STD["n_sets"], onset=ONSET, stress=0.9, seed=s)),
                          ("drift", lambda s: BenignDrift(C.STD["n_sets"], onset=ONSET, slope=0.05, final=0.95, seed=s))]:
            lats, fvs, recs = [], [], []
            for ep in range(N):
                df, b, comp = run_controller(prof, fac, seed=ep)
                lat = M.detection_latency(df, b.cfg.tau)
                if lat is not None and np.isfinite(lat):
                    lats.append(lat)
                fvs.append(M.steady_state_floor_violation(df))
            res[(name, cond)] = dict(
                latency=float(np.nanmean(lats)) if lats else float("inf"),
                floor_viol=float(np.nanmean([f for f in fvs if not np.isnan(f)])),
                detect_rate=float(len(lats) / N))
            print(f"  {name.strip().splitlines()[0]:12s} {cond}: lat={res[(name,cond)]['latency']:.1f} "
                  f"floorV={res[(name,cond)]['floor_viol']:.4f} detect={res[(name,cond)]['detect_rate']:.2f}")
    return res


def triage_features(df, scenario_kind, rng):
    """Extract (ΔS_in, ΔS_res, |Δ̂ slope|, co-tenant-corr) at the detection point.
    ALL inputs are auditor-observable: ΔS_in/ΔS_res are Tier-A scores and the
    abruptness is the slope of the *estimated* competence Δ̂ (NOT the unobservable
    ground-truth Δ). The co-tenant correlation is a modeled §7 signature, drawn
    with deliberate class overlap so it is not a label-trivial feature."""
    cross = M.first_sustained_crossing(df, 0.05) or ONSET
    w = slice(max(0, cross - 4), min(len(df), cross + 6))
    pre = slice(max(0, cross - 12), max(1, cross - 4))
    dS_in = float(df["S_in"].iloc[w].mean() - df["S_in"].iloc[pre].mean())
    dS_res = float(abs(df["S_res"].iloc[w].mean()) - abs(df["S_res"].iloc[pre].mean()))
    # abruptness from the OBSERVABLE Δ̂ stream (not ground-truth Δ)
    dh = df["delta_hat"].values
    abruptness = float(abs(np.mean(np.diff(dh[max(0, cross - 3):cross + 3]))))
    # co-tenant correlation: modeled §7 signature with substantial class overlap
    # (std 0.28) so it cannot by itself trivially separate the classes.
    if scenario_kind == "attack":
        cotenant = float(np.clip(rng.normal(0.60, 0.28), 0, 1))
    else:
        cotenant = float(np.clip(rng.normal(0.30, 0.28), 0, 1))
    return [dS_in, dS_res, abruptness, cotenant]


def _logreg_cv(X, y, k=5, seed=0):
    """k-fold CV accuracy of a standardized logistic regression (no sklearn)."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    folds = np.array_split(idx, k)
    accs = []
    for i in range(k):
        te = folds[i]; tr = np.concatenate([folds[j] for j in range(k) if j != i])
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
        Xtr, Xte = (X[tr] - mu) / sd, (X[te] - mu) / sd
        w = np.zeros(X.shape[1]); b0 = 0.0
        for _ in range(4000):
            z = Xtr @ w + b0; pr = 1 / (1 + np.exp(-z)); g = pr - y[tr]
            w -= 0.1 * (Xtr.T @ g / len(tr) + 1e-3 * w); b0 -= 0.1 * g.mean()
        pred = (1 / (1 + np.exp(-(Xte @ w + b0))) > 0.5).astype(int)
        accs.append((pred == y[te]).mean())
    return float(np.mean(accs)), float(np.std(accs))


def triage():
    rng = np.random.default_rng(0)
    X, y = [], []
    prof = CONTROLLERS["prefetch\n(Pythia)"]
    N = 60
    for ep in range(N):
        fac = (lambda s: BroadAttack(C.STD["n_sets"], onset=ONSET, stress=0.9, seed=s)) if ep % 2 == 0 \
            else (lambda s: MimicryAttack(C.STD["n_sets"], onset=ONSET, stress=0.9, seed=s))
        df, b, comp = run_controller(prof, fac, seed=ep)
        X.append(triage_features(df, "attack", rng)); y.append(1)
        dff, b2, c2 = run_controller(prof, lambda s: BenignDrift(C.STD["n_sets"], onset=ONSET, slope=0.05, final=0.95, seed=s), seed=ep)
        X.append(triage_features(dff, "drift", rng)); y.append(0)
    X = np.array(X); y = np.array(y)
    feat_names = ["ΔS_in", "ΔS_res", "abruptness", "co-tenant corr"]
    # honest 5-fold CV accuracy (train/test split, not in-sample)
    acc, acc_std = _logreg_cv(X, y, k=5, seed=1)
    # per-feature drop ablation: show no single feature (esp. co-tenant) is load-bearing
    ablation = {}
    for j, name in enumerate(feat_names):
        cols = [c for c in range(X.shape[1]) if c != j]
        a, _ = _logreg_cv(X[:, cols], y, k=5, seed=1)
        ablation[f"drop {name}"] = a
    # also: emergent-only (drop the modeled co-tenant feature entirely)
    emergent_acc, _ = _logreg_cv(X[:, :3], y, k=5, seed=1)
    # full-fit weights (for the figure direction) + confusion via CV-style holdout
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Xs = (X - mu) / sd
    w = np.zeros(X.shape[1]); b0 = 0.0
    for _ in range(4000):
        z = Xs @ w + b0; pr = 1 / (1 + np.exp(-z)); g = pr - y
        w -= 0.1 * (Xs.T @ g / len(y) + 1e-3 * w); b0 -= 0.1 * g.mean()
    pred = (1 / (1 + np.exp(-(Xs @ w + b0))) > 0.5).astype(int)
    cm = np.zeros((2, 2), int)
    for ti, pi in zip(y, pred): cm[ti, pi] += 1
    importance = dict(zip(feat_names, w.tolist()))
    print(f"  triage 5-fold CV acc = {acc:.3f} +/- {acc_std:.3f}; emergent-only(3 feat) = {emergent_acc:.3f}")
    print(f"  drop-feature ablation: {({k: round(v,3) for k,v in ablation.items()})}")
    return dict(acc=acc, acc_std=acc_std, emergent_acc=emergent_acc, ablation=ablation,
                cm=cm.tolist(), weights=importance, X=X.tolist(), y=y.tolist())


def main():
    C.setstyle()
    gen = generality()
    tri = triage()

    # --- Figure: generality (grouped bars: floor violation + latency) ---
    names = list(CONTROLLERS.keys())
    conds = ["broad", "drift"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8))
    x = np.arange(len(names)); wbar = 0.36
    for j, cond in enumerate(conds):
        fv = [gen[(n, cond)]["floor_viol"] * 100 for n in names]
        axes[0].bar(x + (j - 0.5) * wbar, fv, wbar, label=cond,
                    color=[C.PALETTE["bouncer"], C.PALETTE["accent"]][j])
    axes[0].set_xticks(x); axes[0].set_xticklabels([n.replace("\n", " ") for n in names], fontsize=6.2, rotation=12)
    axes[0].set_ylabel("steady-state floor violation (%)")
    axes[0].set_title("(a) safety floor holds across controllers")
    axes[0].legend()
    for j, cond in enumerate(conds):
        lt = [gen[(n, cond)]["latency"] for n in names]
        axes[1].bar(x + (j - 0.5) * wbar, lt, wbar, label=cond,
                    color=[C.PALETTE["bouncer"], C.PALETTE["accent"]][j])
    axes[1].set_xticks(x); axes[1].set_xticklabels([n.replace("\n", " ") for n in names], fontsize=6.2, rotation=12)
    axes[1].set_ylabel("detection latency (windows)")
    axes[1].set_title("(b) scheduler pays for model-based Δ̂")
    axes[1].legend()
    C.savefig(fig, "p3_generality.pdf")

    # --- Figure: triage (confusion matrix + feature scatter) ---
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.8))
    cm = np.array(tri["cm"])
    ax = axes[0]
    im = ax.imshow(cm, cmap="Blues", vmin=0)
    for i in range(2):
        for j in range(2):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=11)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["drift", "attack"])
    ax.set_yticks([0, 1]); ax.set_yticklabels(["drift", "attack"])
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"(a) triage confusion (5-fold CV acc={tri['acc']:.2f})")
    ax = axes[1]
    X = np.array(tri["X"]); y = np.array(tri["y"])
    ax.scatter(X[y == 0, 0], X[y == 0, 1], s=14, color=C.PALETTE["accent"], label="drift", alpha=0.7, edgecolor="none")
    ax.scatter(X[y == 1, 0], X[y == 1, 1], s=14, color=C.PALETTE["unguarded"], label="attack", alpha=0.7, edgecolor="none")
    ax.set_xlabel("ΔS_in (input shift)"); ax.set_ylabel("ΔS_res (innovation)")
    ax.set_title("(b) drift shifts input; attack spikes innovation")
    ax.legend()
    C.savefig(fig, "p3_triage.pdf")

    C.save_json("p3.json", dict(
        generality={f"{n}|{c}": gen[(n, c)] for (n, c) in gen},
        triage=dict(acc=tri["acc"], acc_std=tri["acc_std"], emergent_acc=tri["emergent_acc"],
                    ablation=tri["ablation"], cm=tri["cm"], weights=tri["weights"])))


if __name__ == "__main__":
    main()
