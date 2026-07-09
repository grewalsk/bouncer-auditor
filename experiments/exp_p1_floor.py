"""
P1 — Gate + safety floor (Lemma 1). The "constructive hedge" demonstrated.

On a poisoning trace (attack on at window 90, off at 200), compare:
  unguarded C  (no auditor)   -> crashes far below the fallback floor
  always-fallback             -> safe but never gains
  Bouncer (full)              -> tracks C when trusted, floors to ~pi0 under
                                 attack, re-trusts via PROBING after attack ends
  oracle-Δ                    -> upper bound on detection
Reports detection latency, IPC recovered, clean tax, floor violation
(transient vs steady-state), re-trust latency. Figure: p1_safety_floor.pdf.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

import common as C
from bouncer.adversary import Clean, BroadAttack
from bouncer.simulate import run_episode, SimConfig
from bouncer import metrics as M
from bouncer.theory import regret_bound


ONSET, OFFSET, T = 90, 200, 320


def run(mode, seed=5):
    comp = C.make_competence()
    env, b = C.make_bouncer(mode, comp=comp, seed=seed)
    sim = C.simconfig(T=T)
    adv = BroadAttack(C.STD["n_sets"], onset=ONSET, offset=OFFSET, stress=0.92, seed=4)
    df = run_episode(comp, env, b, adv, sim, seed=6)
    return df, b, comp, env


def clean_ref(seed=5):
    comp = C.make_competence()
    env, b = C.make_bouncer("full", comp=comp, seed=seed)
    sim = C.simconfig(T=T)
    return run_episode(comp, env, b, Clean(C.STD["n_sets"], seed=3), sim, seed=6)


def retrust_latency(df):
    """Windows from attack offset to first sustained TRUSTED."""
    st = df.state.values
    for t in range(OFFSET, len(st)):
        if st[t] == "TRUSTED" and all(s == "TRUSTED" for s in st[t:min(t + 3, len(st))]):
            return t - OFFSET
    return np.inf


def shade_states(ax, df):
    colors = {"TRUSTED": "#ffffff", "SUSPECT": "#fff4e0",
              "GATED": "#e9eef5", "PROBING": "#e6f2ea"}
    st = df.state.values
    t0 = 0
    for t in range(1, len(st) + 1):
        if t == len(st) or st[t] != st[t0]:
            ax.axvspan(t0 - 0.5, t - 0.5, color=colors.get(st[t0], "#fff"),
                       alpha=0.7, lw=0, zorder=0)
            t0 = t


def main():
    C.setstyle()
    df, b, comp, env = run("full")
    dfo, _, _, _ = run("oracle")
    dfclean = clean_ref()

    tau = b.cfg.tau
    lat = M.detection_latency(df, tau)
    lat_o = M.detection_latency(dfo, tau)
    rec = M.performance_recovered(df, dfclean.ipc_unguarded.mean())
    ctax = M.clean_tax(dfclean)
    fv_trans = M.safety_floor_violation(df)
    fv_steady = M.steady_state_floor_violation(df)
    retrust = retrust_latency(df)

    t = df.t.values
    # --- Figure: IPC trajectories with gate shading + cumulative regret ---
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 4.4),
                             gridspec_kw=dict(height_ratios=[2.4, 1]))
    ax = axes[0]
    shade_states(ax, df)
    ax.plot(t, df.ipc_unguarded, color=C.PALETTE["unguarded"], lw=1.2, label="unguarded $C$ (no auditor)")
    ax.plot(t, df.ipc_fallback, color=C.PALETTE["fallback"], lw=1.2, ls=(0, (4, 2)), label=r"always-fallback $\pi_0$")
    ax.plot(t, df.ipc_bouncer, color=C.PALETTE["bouncer"], lw=1.8, label="Bouncer")
    ax.plot(t, dfo.ipc_bouncer, color=C.PALETTE["oracle"], lw=1.0, ls=":", label=r"oracle-$\Delta$")
    ax.axvspan(ONSET, OFFSET, ymin=0.0, ymax=0.03, color="k", alpha=0.5, lw=0)
    ax.annotate("attack", xy=((ONSET + OFFSET) / 2, ax.get_ylim()[0]),
                xytext=((ONSET + OFFSET) / 2, df.ipc_fallback.min() - 0.02),
                ha="center", fontsize=7.5)
    ax.set_ylabel("IPC"); ax.set_xlim(0, T)
    ax.set_title("Bouncer bounds the learned controller to the safe-fallback floor (Lemma 1)")
    handles, labels = ax.get_legend_handles_labels()
    shade_legend = [Patch(facecolor="#fff4e0", label="SUSPECT"),
                    Patch(facecolor="#e9eef5", label="GATED"),
                    Patch(facecolor="#e6f2ea", label="PROBING")]
    ax.legend(handles + shade_legend, labels + ["SUSPECT", "GATED", "PROBING"],
              loc="lower left", ncol=2)

    ax = axes[1]
    reg = M.cumulative_regret_vs_fallback(df)
    reg_o = M.cumulative_regret_vs_fallback(dfo)
    ax.plot(t, reg, color=C.PALETTE["bouncer"], lw=1.5, label="Bouncer cumulative regret vs floor")
    ax.plot(t, reg_o, color=C.PALETTE["oracle"], lw=1.0, ls=":", label="oracle")
    # Corrected Lemma 1 loose bound (N_ep=1 genuine episode), three terms in IPC units:
    #   N_ep*D*r_max  +  phi_P*T_att*r_max  +  alpha*T*c_sw
    # The middle audit-exposure term is REQUIRED: the n_L Leader-C sets keep running C
    # in every gate state (simulate.py:82), so a drop of T_att windows bleeds at the
    # dueling fraction. The old two-term bound (no exposure) is shown for contrast.
    sigma = b.dueling.sigma_delta(C.STD["m"])
    K = tau + b.cfg.gamma_detect / 2
    fb = regret_bound(r_max=1.0, N_ep=1, T=T, c_sw=env.ipc_slope * 0.1,
                      K=K, H=b.cfg.tierb_H, sigma_delta=sigma,
                      mean_signal_clean=0.265, delta_true_drop=float(comp.delta_true(0.92)))
    phi_G = C.STD["n_L"] / C.STD["n_sets"]
    phi_P = phi_G + SimConfig.audited_region_frac * (1 - (C.STD["n_L"] + C.STD["n_F"]) / C.STD["n_sets"])
    T_att = int(df["label_attack"].sum())
    two_term_ipc = fb.detection_term * env.ipc_slope + fb.false_alarm_term
    bound_ipc = two_term_ipc + env.ipc_slope * phi_P * T_att * 1.0        # corrected loose
    ax.axhline(bound_ipc, color="k", lw=0.9, ls="--",
               label=f"Lemma 1 loose (3-term) = {bound_ipc:.2f} IPC$\\cdot$win")
    ax.set_xlabel("window $t$"); ax.set_ylabel("cum. regret\n(IPC$\\cdot$win)")
    ax.set_xlim(0, T); ax.legend(loc="upper left")
    C.savefig(fig, "p1_safety_floor.pdf")

    res = dict(detection_latency=float(lat), oracle_latency=float(lat_o),
               performance_recovered=rec, clean_tax=ctax,
               floor_violation_transient=fv_trans, floor_violation_steady=fv_steady,
               retrust_latency=float(retrust),
               cumulative_regret_final=float(reg[-1]),
               lemma_bound_ipc=float(bound_ipc), lemma_two_term_ipc=float(two_term_ipc),
               T_att=int(T_att), phi_G=float(phi_G), phi_P=float(phi_P),
               D=float(fb.D), alpha=float(fb.alpha), sigma_delta=float(sigma))
    C.save_json("p1.json", res)
    print(f"  detection latency  = {lat} windows  (oracle {lat_o})")
    print(f"  perf recovered     = {rec:.3f}")
    print(f"  clean tax          = {ctax:.4f}")
    print(f"  floor viol (trans) = {fv_trans:.3f}   (steady) = {fv_steady:.4f}")
    print(f"  re-trust latency   = {retrust} windows after attack ends")
    print(f"  cum regret={reg[-1]:.2f}  Lemma bound={bound_ipc:.2f}  D={fb.D:.2f} alpha={fb.alpha:.2e}")


if __name__ == "__main__":
    main()
