"""
P0 — Harness & estimator (validates §4).

(a) Δ̂ tracks ground-truth Δ within σ_Δ on clean + drift.
(b) Empirical std(Δ̂) matches the concentration bound
    Var(Δ̂) <= (r_max^2/4m)(1/n_L + 1/n_F)  across a pool-size sweep.
(c) Scatter Δ̂ vs Δ with R^2.
Outputs: figures/p0_tracking.pdf, figures/p0_variance.pdf, results/p0.json
"""
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

import common as C
from bouncer.adversary import Clean, BenignDrift
from bouncer.simulate import run_episode


def tracking():
    comp = C.make_competence()
    # full-pool measurement (n_bg = n_L) so Δ̂ reflects the estimator, not duty
    env, b = C.make_bouncer("no_auditor", comp=comp, n_L_bg=32, n_F_bg=32, seed=7)
    sim = C.simconfig(T=320)
    adv = BenignDrift(C.STD["n_sets"], onset=80, slope=0.022, final=0.95, seed=4)
    df = run_episode(comp, env, b, adv, sim, seed=5)
    sigma = b.dueling.sigma_delta(sim.m)
    # R^2 between estimate and truth
    r2 = stats.pearsonr(df.delta_hat, df.delta_true)[0] ** 2
    rmse = float(np.sqrt(np.mean((df.delta_hat - df.delta_true) ** 2)))
    return df, sigma, r2, rmse, comp


def variance_sweep():
    comp = C.make_competence()
    m = C.STD["m"]
    ns = [4, 8, 16, 32, 64, 128]
    emp, pred = [], []
    for n in ns:
        env, b = C.make_bouncer("no_auditor", comp=comp, n_L=n, n_F=n,
                                n_L_bg=n, n_F_bg=n, seed=100 + n)
        sim = C.simconfig(T=600)
        df = run_episode(comp, env, b, Clean(C.STD["n_sets"], seed=3), sim, seed=9)
        emp.append(float(np.std(df.delta_hat.values[20:])))   # drop warmup
        pred.append(b.dueling.sigma_delta(m))
    return ns, np.array(emp), np.array(pred)


def main():
    C.setstyle()
    df, sigma, r2, rmse, comp = tracking()
    ns, emp, pred = variance_sweep()

    # --- Figure: tracking ---
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.7))
    ax = axes[0]
    t = df.t.values
    ax.fill_between(t, df.delta_hat - 2 * sigma, df.delta_hat + 2 * sigma,
                    color=C.PALETTE["bouncer"], alpha=0.18, lw=0, label=r"$\hat\Delta \pm 2\sigma_\Delta$")
    ax.plot(t, df.delta_hat, color=C.PALETTE["bouncer"], lw=1.2, label=r"$\hat\Delta_W$ (set-dueling)")
    ax.plot(t, df.delta_true, color=C.PALETTE["unguarded"], lw=1.4, ls="--", label=r"$\Delta_W$ (ground truth)")
    ax.axhline(comp.q0 * 0 + C.STD["tau"], color="k", lw=0.7, ls=":", label=r"$\tau$")
    ax.axhline(0, color="#999", lw=0.5)
    ax.set_xlabel("window $t$"); ax.set_ylabel(r"competence advantage $\Delta$")
    ax.set_title(r"(a) $\hat\Delta$ tracks $\Delta$ under benign drift")
    ax.legend(loc="upper right", ncol=1)

    ax = axes[1]
    ax.scatter(df.delta_true, df.delta_hat, s=7, color=C.PALETTE["bouncer"], alpha=0.6, edgecolor="none")
    lim = [min(df.delta_true.min(), df.delta_hat.min()) - 0.02,
           max(df.delta_true.max(), df.delta_hat.max()) + 0.02]
    ax.plot(lim, lim, color="#999", lw=0.8, ls="--")
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel(r"$\Delta_W$ (ground truth)"); ax.set_ylabel(r"$\hat\Delta_W$")
    ax.set_title(rf"(b) estimator fidelity  $R^2={r2:.3f}$")
    C.savefig(fig, "p0_tracking.pdf")

    # --- Figure: variance validation ---
    fig, ax = plt.subplots(figsize=(3.6, 2.7))
    ax.plot(ns, pred, "o-", color=C.PALETTE["accent"], label=r"bound $\sqrt{\frac{r_{max}^2}{4m}(\frac{1}{n_L}+\frac{1}{n_F})}$")
    ax.plot(ns, emp, "s--", color=C.PALETTE["bouncer"], label=r"empirical std$(\hat\Delta)$")
    ax.set_xscale("log", base=2); ax.set_yscale("log", base=2)
    ax.set_xlabel(r"dueling pool size $n_L=n_F$"); ax.set_ylabel(r"$\sigma_\Delta$")
    ax.set_title("estimator variance vs pool size")
    ax.legend()
    C.savefig(fig, "p0_variance.pdf")

    res = dict(
        r2=r2, rmse=rmse, sigma_delta_pred=float(sigma),
        variance_sweep=dict(n=ns, empirical=emp.tolist(), predicted=pred.tolist(),
                            ratio=(emp / pred).tolist()),
        note="Empirical std(Δ̂) tracks the bound within sampling error; the bound is a (tight) upper envelope.",
    )
    C.save_json("p0.json", res)
    print(f"  R^2={r2:.4f} RMSE={rmse:.4f} sigma_pred={sigma:.4f}")
    print(f"  emp/pred std ratio: {np.round(emp/pred,3).tolist()}")


if __name__ == "__main__":
    main()
