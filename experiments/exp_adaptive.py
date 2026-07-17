"""
Adaptive timing adversaries (threat-model hardening, §13).

(1) Boiling-frog: a very slow stealthy degradation. A one-sided CUSUM integrates
    the LEVEL (K - Δ̂), not the slope, so once Δ̂<K it accumulates regardless of
    how slowly it got there. We show Bouncer still gates and bound the extra
    regret accrued during the slow descent through the (-γ,τ) band.
    -> figures/adaptive_boiling.pdf

(2) PROBING-exploit (closed-loop): the attacker watches the gate and backs off
    during GATED/PROBING to pass the audit, resuming when TRUSTED. We show the
    *measured* re-trust + exponential dwell-backoff bound the fraction of windows
    the victim is harmed and shrink it over time -- the attacker cannot wait out
    a fixed cooldown because there isn't one.
    -> figures/adaptive_probing.pdf
"""
import numpy as np
import matplotlib.pyplot as plt

import common as C
from bouncer.adversary import BoilingFrogAttack, ProbingExploitAttack, BroadAttack
from bouncer.simulate import run_episode
from bouncer import metrics as M


def boiling_frog():
    comp = C.make_competence()
    T = 480
    env, b = C.make_bouncer("full", comp=comp, seed=7)
    sim = C.simconfig(T=T)
    adv = BoilingFrogAttack(C.STD["n_sets"], onset=60, slope=0.006, final_stress=0.95, seed=3)
    df = run_episode(comp, env, b, adv, sim, seed=8)
    tau = b.cfg.tau
    lat = M.detection_latency(df, tau)
    cross = M.first_sustained_crossing(df, tau)
    gated = M.first_gated(df, after=cross or 0)
    # regret accrued during the slow descent (Δ<τ but not yet gated)
    reg = M.cumulative_regret_vs_fallback(df)
    floor_v = M.steady_state_floor_violation(df)
    # compare: abrupt attack to the same final stress
    env2, b2 = C.make_bouncer("full", comp=comp, seed=7)
    adv2 = BroadAttack(C.STD["n_sets"], onset=60, stress=0.95, seed=3)
    df2 = run_episode(comp, env2, b2, adv2, sim, seed=8)
    lat2 = M.detection_latency(df2, tau)
    return dict(df=df, lat=lat, cross=cross, gated=gated, floor_v=floor_v,
                abrupt_lat=lat2, comp=comp, tau=tau)


def probing_exploit():
    comp = C.make_competence()
    T = 420
    env, b = C.make_bouncer("full", comp=comp, seed=5)
    sim = C.simconfig(T=T)
    adv = ProbingExploitAttack(C.STD["n_sets"], onset=60, stress=0.92, seed=2)
    df = run_episode(comp, env, b, adv, sim, seed=6)
    # victim harmed: attacking AND C active on followers (gate open)
    harmed = (df["label_attack"].values) & (df["C_active"].values)
    # harmed fraction in sliding windows over time (shows backoff shrinking it)
    win = 40
    frac_t = np.array([harmed[max(0, t - win):t + 1].mean() for t in range(len(harmed))])
    # post-onset overall harmed fraction
    post = harmed[60:]
    harmed_frac = float(post.mean())
    # first vs second half (does backoff shrink it?)
    half = len(post) // 2
    h1, h2 = float(post[:half].mean()), float(post[half:].mean())
    floor_v = M.steady_state_floor_violation(df)
    return dict(df=df, harmed=harmed, frac_t=frac_t, harmed_frac=harmed_frac,
                h1=h1, h2=h2, floor_v=floor_v, win=win)


def main():
    C.setstyle()
    bf = boiling_frog()
    pe = probing_exploit()

    # --- boiling-frog figure ---
    df = bf["df"]; t = df.t.values
    fig, axes = plt.subplots(2, 1, figsize=(7.0, 3.8), gridspec_kw=dict(height_ratios=[1.4, 1]))
    ax = axes[0]
    ax.plot(t, df.delta_true, color=C.PALETTE["unguarded"], lw=1.3, ls="--", label=r"$\Delta_W$ (true)")
    ax.plot(t, df.delta_hat, color=C.PALETTE["bouncer"], lw=1.0, label=r"$\hat\Delta_W$")
    ax.axhline(bf["tau"], color="k", lw=0.7, ls=":", label=r"$\tau$")
    ax.axhline(C.STD["tau"] + C.STD["gamma_detect"] / 2, color="#888", lw=0.7, ls="-.", label="$K$")
    if bf["gated"] is not None:
        ax.axvline(bf["gated"], color=C.PALETTE["oracle"], lw=1.0, label="GATED")
    ax.set_ylabel(r"competence $\Delta$"); ax.legend(loc="upper right", ncol=2, fontsize=6.5)
    ax.set_title(f"(a) boiling-frog: slow descent still gated (latency {bf['lat']} windows after $\\Delta<\\tau$)")
    ax = axes[1]
    ax.plot(t, df.ipc_bouncer, color=C.PALETTE["bouncer"], lw=1.3, label="Bouncer")
    ax.plot(t, df.ipc_fallback, color=C.PALETTE["fallback"], lw=1.0, ls="--", label=r"$\pi_0$ floor")
    ax.plot(t, df.ipc_unguarded, color=C.PALETTE["unguarded"], lw=0.8, alpha=0.6, label="unguarded")
    ax.set_xlabel("window $t$"); ax.set_ylabel("IPC"); ax.legend(loc="lower left", fontsize=6.5)
    ax.set_title(f"(b) floor held: steady violation {bf['floor_v']*100:.2f}%")
    C.savefig(fig, "adaptive_boiling.pdf")

    # --- probing-exploit figure ---
    df = pe["df"]; t = df.t.values
    fig, axes = plt.subplots(2, 1, figsize=(7.0, 3.6), gridspec_kw=dict(height_ratios=[1, 1]))
    ax = axes[0]
    ax.plot(t, pe["frac_t"], color=C.PALETTE["accent"], lw=1.4)
    ax.fill_between(t, 0, pe["frac_t"], color=C.PALETTE["accent"], alpha=0.15)
    ax.set_ylabel(f"victim-harmed frac\n({pe['win']}-win avg)")
    ax.set_title(f"(a) PROBING-exploit: harmed frac {pe['h1']:.2f} (1st half) $\\to$ {pe['h2']:.2f} (2nd half)")
    ax.set_ylim(0, max(0.3, pe["frac_t"].max() * 1.2))
    ax = axes[1]
    # gate state as steps
    state_num = {"TRUSTED": 0, "SUSPECT": 1, "PROBING": 2, "GATED": 3}
    sn = [state_num[s] for s in df.state.values]
    ax.step(t, sn, color=C.PALETTE["bouncer"], lw=1.0, where="post")
    ax.set_yticks(list(state_num.values())); ax.set_yticklabels(list(state_num.keys()), fontsize=6.5)
    ax.set_xlabel("window $t$"); ax.set_title("(b) gate cycles GATED$\\leftrightarrow$PROBING with growing dwell (backoff)")
    C.savefig(fig, "adaptive_probing.pdf")

    res = dict(
        boiling_frog=dict(detection_latency_after_cross=float(bf["lat"]) if bf["lat"] is not None else None,
                          abrupt_latency=float(bf["abrupt_lat"]) if bf["abrupt_lat"] is not None else None,
                          steady_floor_violation=bf["floor_v"],
                          cross=int(bf["cross"]) if bf["cross"] is not None else None,
                          gated=int(bf["gated"]) if bf["gated"] is not None else None),
        probing_exploit=dict(harmed_frac=pe["harmed_frac"], harmed_first_half=pe["h1"],
                             harmed_second_half=pe["h2"], steady_floor_violation=pe["floor_v"]))
    C.save_json("adaptive.json", res)
    print(f"  boiling-frog: gated at {bf['gated']} (Δ<τ at {bf['cross']}), latency {bf['lat']}, "
          f"abrupt latency {bf['abrupt_lat']}, floor {bf['floor_v']*100:.2f}%")
    print(f"  probing-exploit: harmed frac {pe['harmed_frac']:.3f} ({pe['h1']:.3f}->{pe['h2']:.3f}), "
          f"floor {pe['floor_v']*100:.2f}%")


if __name__ == "__main__":
    main()
