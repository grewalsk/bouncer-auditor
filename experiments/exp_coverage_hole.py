"""
N4 — Coverage-hole / slow-bleed DEMONSTRATION (pre-registered, FALLBACK branch).

This is the empirical confirmation of the closed-form result from hardening/nodes/N2.md:
with a finite per-region leader budget B the dueling estimator has a resolution floor
δ_R^min(B) = k·σ_R, σ_R = r_max·√((1/4m)(1/n_{L,R}+1/n_{F,R})); a redistributive
adversary whose per-window competence harm h stays BELOW δ_R^min evades the secret
gate indefinitely while the victim's cumulative harm grows without bound.

It runs against the REAL deployed Bouncer (bouncer/bouncer.py, region dueling, full
mode, live CUSUM + gate FSM). It is labelled SYNTHETIC because it uses the Python
competence harness, not ChampSim (per the pre-registration: the realised δ_R^min on
available SPEC SimPoints is too small to render a visible attack in 20 ChampSim evals;
the controlled harness exhibits the same evade-forever-below-floor behaviour cleanly).

Outputs: figures/coverage_hole.pdf, results/coverage_hole.json
"""
import numpy as np
import matplotlib.pyplot as plt

import common as C
from bouncer.adversary import Window
from bouncer.simulate import run_episode
from bouncer import metrics as M

ONSET, T = 40, 360


class SlowBleed:
    """Constant per-window competence harm h on a victim region R, applied to ALL
    region sets (the secret is intact, so the adversary cannot spare the leaders).
    h maps to region stress via mu_C: Δ_true,R = Δ_clean − h."""
    name = "slow-bleed"

    def __init__(self, n_sets, region, h, comp, onset=ONSET, seed=0):
        self.n_sets = n_sets; self.region = np.asarray(region)
        self.onset = onset; self.rng = np.random.default_rng(seed)
        # stress u s.t. mu_C(u) = mu_C(base) − h  ->  Δ drops by exactly h
        base_u = 0.05
        mu_target = float(comp.mu_C(base_u)) - h
        self.u_bleed = (comp.a_C - mu_target / comp.r_max) / comp.b_C
        self.base_u = base_u

    def window(self, t, dueling=None, gate_state=None):
        u = self.base_u + 0.02 * self.rng.standard_normal(self.n_sets)
        if t >= self.onset:
            u[self.region] = self.u_bleed + 0.02 * self.rng.standard_normal(len(self.region))
        return Window(np.clip(u, 0, 1), suppress_features=(t >= self.onset), label_attack=(t >= self.onset))


def sigma_R(n_L_eff, n_F_eff, m, r_max=1.0):
    return float(r_max * np.sqrt((1.0 / (4 * m)) * (1.0 / n_L_eff + 1.0 / n_F_eff)))


def run_h(h, region, comp, seed=0):
    env, b = C.make_bouncer("full", comp=comp, region=region, seed=seed)
    sim = C.simconfig(T=T)
    df = run_episode(comp, env, b, SlowBleed(C.STD["n_sets"], region, h, comp, seed=seed), sim, seed=seed + 100)
    gated = M.first_gated(df, after=ONSET)
    # victim cumulative harm = Σ over post-onset windows of (clean − degraded) on region followers
    per_window_harm = h
    if gated is None:
        cum_harm = per_window_harm * (T - ONSET)   # bled the whole horizon, never caught
        evaded = True
    else:
        cum_harm = per_window_harm * (gated - ONSET)
        evaded = False
    return dict(df=df, gated=gated, evaded=evaded, cum_harm=cum_harm)


def main():
    C.setstyle()
    comp = C.make_competence()
    m = C.STD["m"]; n_sets = C.STD["n_sets"]; n_L = C.STD["n_L"]

    Kref = C.STD["tau"] + C.STD["gamma_detect"] / 2
    clean_delta = float(comp.delta_true(0.05))   # ~0.265

    # CLOSED-FORM resolution floor delta_R^min(B) = k*sigma_R, sigma_R ∝ 1/√B (from N2)
    k = 3.0
    budgets = []
    for region_size in (128, 256, 512, 1024):
        nLR = max(1, round(n_L * region_size / n_sets))
        sR = sigma_R(nLR, nLR, m)
        budgets.append(dict(region_size=region_size, nLR=nLR, B=2 * nLR, sigma_R=sR, dRmin=k * sR))

    # --- the money trace: an evasive slow-bleed (h well below clean-K) on region R ---
    region = np.arange(0, 256)
    h_evade = 0.06   # per-window harm; Δ_R = clean-h ≈ 0.205 stays above K=0.10 -> CUSUM never accumulates
    main_run = run_h(h_evade, region, comp, seed=0)
    df = main_run["df"]; t = df.t.values
    cum = np.cumsum(np.where(df.label_attack.values, h_evade, 0.0))
    K = C.STD["tau"] + C.STD["gamma_detect"] / 2

    fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.9))
    ax = axes[0]
    ax.plot(t, cum, color=C.PALETTE["unguarded"], lw=1.8, label="cumulative victim harm")
    ax2 = ax.twinx()
    ax2.plot(t, df.delta_hat.values, color=C.PALETTE["bouncer"], lw=1.0, alpha=0.8, label=r"$\hat\Delta_R$")
    ax2.axhline(C.STD["tau"], color="k", lw=0.7, ls=":")
    ax2.axhline(K, color="#888", lw=0.7, ls="-.")
    ax2.set_ylabel(r"$\hat\Delta_R$ (stays $\geq\tau$)", color=C.PALETTE["bouncer"])
    ax2.tick_params(axis="y", labelcolor=C.PALETTE["bouncer"]); ax2.grid(False)
    ax.set_xlabel("window $t$"); ax.set_ylabel("cumulative harm", color=C.PALETTE["unguarded"])
    ax.tick_params(axis="y", labelcolor=C.PALETTE["unguarded"])
    gated = main_run["gated"]
    ax.set_title(f"(a) slow-bleed at $h{{=}}{h_evade:.2f}<\\delta_R^{{min}}$: never gated" + (" (synthetic)" if True else ""))
    ax.legend(loc="upper left", fontsize=6.5)

    # panel (b): evade-FOREVER -> cumulative harm grows linearly without bound in T
    ax = axes[1]
    Ts = [120, 240, 360, 480, 600]
    cum_by_T, all_evaded = [], True
    global T
    for TT in Ts:
        T = TT
        r = run_h(h_evade, region, comp, seed=1)
        cum_by_T.append(r["cum_harm"]); all_evaded = all_evaded and r["evaded"]
    T = 360
    ax.plot(Ts, cum_by_T, "o-", color=C.PALETTE["unguarded"], lw=1.7)
    ax.set_xlabel("horizon $T$ (windows)"); ax.set_ylabel("total victim harm at $T$")
    ax.set_title(f"(b) evade-forever: harm $\\propto T$ (all evaded={all_evaded})")
    C.savefig(fig, "coverage_hole.pdf")

    res = dict(synthetic=True, branch="FALLBACK (controlled harness, real Bouncer region dueling)",
               horizon=T, onset=ONSET, m=m, k=k, clean_delta=clean_delta, K=Kref,
               budgets=[{kk: (vv if not isinstance(vv, np.ndarray) else None) for kk, vv in bd.items()
                         if kk != "region"} for bd in budgets],
               h_evade=h_evade,
               main_trace=dict(h=h_evade, gated=main_run["gated"], evaded=main_run["evaded"],
                               cumulative_harm=float(cum[-1]), delta_hat_min=float(df.delta_hat.min()),
                               delta_hat_mean_postonset=float(df.delta_hat.values[ONSET:].mean()),
                               cusum_ever_alarmed=(main_run["gated"] is not None)),
               horizon_scaling=dict(T=Ts, cum_harm=cum_by_T, all_evaded=all_evaded))
    C.save_json("coverage_hole.json", res)
    print(f"  closed-form δ_R^min(B): " + ", ".join(f"B={bd['B']}→{bd['dRmin']:.3f}" for bd in budgets))
    print(f"  money-trace h={h_evade:.3f}: gated={main_run['gated']} cum_harm={cum[-1]:.2f} "
          f"Δ̂_mean={df.delta_hat.values[ONSET:].mean():.3f} (≥τ={C.STD['tau']}); harm∝T evaded_all={all_evaded}")


if __name__ == "__main__":
    main()
