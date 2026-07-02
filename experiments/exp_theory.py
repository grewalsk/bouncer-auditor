"""
Theory validation — the CUSUM ARL constants worked through, and Lemma 6.1's
regret bound checked against measured cumulative regret.

(1) ARL validation. For a one-sided lower CUSUM on a Gaussian signal of known
    mean/std, compare the empirical ARL0 (mean windows-to-false-alarm, in-control)
    and ARL1 (detection delay, out-of-control) against Siegmund's corrected-
    boundary approximation across a threshold sweep. Operates in a regime where
    ARL0 is finite and measurable (margin comparable to sigma).
    -> figures/th_arl.pdf
(2) Regret bound. Sweep the number of genuine drop episodes N_ep; overlay the
    Lemma 6.1 bound N_ep*D*r_max + alpha*T*c_sw on the measured worst-case
    cumulative regret of the full Bouncer. The bound is a valid (loose) envelope.
    -> figures/th_regret.pdf
"""
import numpy as np
import matplotlib.pyplot as plt

import common as C
from bouncer.cusum import LowerCusum, siegmund_arl, detection_delay_approx
from bouncer.adversary import BroadAttack, Clean
from bouncer.simulate import run_episode, SimConfig
from bouncer import metrics as M


def empirical_arl(K, H, mean, sigma, n_runs=4000, max_len=40000, seed=0):
    """Mean run length of a lower CUSUM on N(mean, sigma) draws, vectorized over
    n_runs parallel walks: C_t = max(0, C_{t-1} + (K - x)), alarm at C_t > H."""
    rng = np.random.default_rng(seed)
    Cstat = np.zeros(n_runs)
    alarm_t = np.full(n_runs, -1, dtype=np.int64)
    alive = np.ones(n_runs, dtype=bool)
    chunk = 2000
    t = 0
    while alive.any() and t < max_len:
        steps = min(chunk, max_len - t)
        draws = rng.normal(mean, sigma, size=(steps, n_runs))
        for s in range(steps):
            Cstat = np.maximum(0.0, Cstat + (K - draws[s]))
            fired = alive & (Cstat > H)
            if fired.any():
                alarm_t[fired] = t + s + 1
                alive[fired] = False
                Cstat[fired] = 0.0
        t += steps
    alarm_t[alarm_t < 0] = max_len
    return float(np.mean(alarm_t))


def arl_validation():
    # regime with finite, measurable ARL0: small margin relative to sigma
    K = 0.0
    sigma = 1.0
    mean_in = 0.5    # in-control: signal above K by 0.5 sigma -> delta=(K-mean)/sigma=-0.5
    mean_out = -0.5  # out-of-control: drift below K -> delta=+0.5
    Hs = np.linspace(1.0, 6.0, 11)
    emp0, th0, emp1, th1 = [], [], [], []
    for H in Hs:
        emp0.append(empirical_arl(K, H, mean_in, sigma, n_runs=3000, seed=int(H * 100)))
        th0.append(siegmund_arl(K, H, mean_in, sigma))
        emp1.append(empirical_arl(K, H, mean_out, sigma, n_runs=3000, seed=int(H * 100) + 7))
        th1.append(siegmund_arl(K, H, mean_out, sigma))
        print(f"  H={H:.1f}  ARL0 emp={emp0[-1]:.0f} th={th0[-1]:.0f} | ARL1 emp={emp1[-1]:.1f} th={th1[-1]:.1f}")
    return dict(H=Hs.tolist(), arl0_emp=emp0, arl0_th=th0, arl1_emp=emp1, arl1_th=th1)


def _run_pulses(comp, Nep, seg_len, seed):
    """Run a trace with Nep attack pulses of seg_len windows each; return the
    episode dataframe. Attack on every other segment (clean, attack, clean, ...)."""
    env, b = C.make_bouncer("full", comp=comp, seed=seed)
    T = seg_len * (2 * Nep + 1)

    class MultiPulse:
        name = "multi"
        def __init__(self, n_sets, s):
            self.n_sets = n_sets; self.rng = np.random.default_rng(s)
        def window(self, t, dueling=None, gate_state=None):
            seg = t // seg_len
            active = (seg % 2 == 1) and (seg // 2 < Nep)
            from bouncer.adversary import Window
            lvl = 0.92 if active else 0.05
            u = np.clip(lvl + 0.02 * self.rng.standard_normal(self.n_sets), 0, 1)
            return Window(u, suppress_features=False, label_attack=active)

    sim = C.simconfig(T=T)
    return run_episode(comp, env, b, MultiPulse(C.STD["n_sets"], s=100 + seed), sim, seed=200 + seed), env


def regret_validation():
    """Worst-case cumulative regret vs fallback vs the CORRECTED Lemma 1 bound.

    The audit-exposure fractions (n_L Leader-C sets run C in every gate state, plus
    a rho_aud audited region in PROBING) make the bound three-term:
       LOOSE  N_ep*D*r_max + phi_P*T_att*r_max + alpha*T*c_sw
       TIGHT  realized gap, split GATED/PROBING occupancy.
    The old two-term bound (no exposure) still envelopes SHORT attacks (L_att=60,
    where the N_ep sweep lives) but is VIOLATED for long attacks (the L_att sweep)."""
    comp = C.make_competence()
    sim_T = 60   # windows per episode segment (short-attack regime; protected numbers)
    K = C.STD["tau"] + C.STD["gamma_detect"] / 2
    delta_drop = float(comp.delta_true(0.92))
    D = detection_delay_approx(K, C.STD["tierb_H"], delta_drop)
    gap = comp.q0 - float(comp.mu_C(0.92)) / comp.r_max
    phi_G = C.STD["n_L"] / C.STD["n_sets"]
    phi_P = phi_G + SimConfig.audited_region_frac * (1 - (C.STD["n_L"] + C.STD["n_F"]) / C.STD["n_sets"])

    # --- N_ep sweep at L_att=60 (protected: loose/tight/measured 15.14/7.83/5.92 at N_ep=6) ---
    Neps = [1, 2, 3, 4, 5, 6]
    meas, bound, tight, corrected = [], [], [], []
    for Nep in Neps:
        df, env = _run_pulses(comp, Nep, sim_T, seed=Nep)
        pos = np.cumsum(np.maximum((df["ipc_fallback"] - df["ipc_bouncer"]).values, 0))
        meas.append(float(pos[-1]))
        det_term = Nep * D * env.ipc_slope * comp.r_max
        bound.append(float(det_term))                                          # old two-term (no exposure)
        tight.append(float(Nep * env.ipc_slope * gap * (D + phi_G * (sim_T - D))))
        T_att = Nep * sim_T
        corrected.append(float(det_term + env.ipc_slope * phi_P * T_att * comp.r_max))  # corrected loose
        print(f"  N_ep={Nep}: measured={meas[-1]:.2f}  two_term={bound[-1]:.2f}  "
              f"tight={tight[-1]:.2f}  corrected_loose={corrected[-1]:.2f}  D={D:.2f}")

    # --- L_att sweep at fixed N_ep=3: the two-term bound BREAKS as attacks lengthen ---
    Latts = [60, 240, 960]
    la_meas, la_two, la_tight, la_corr = [], [], [], []
    Nep_la = 3
    for La in Latts:
        df, env = _run_pulses(comp, Nep_la, La, seed=Nep_la)
        pos = float(np.cumsum(np.maximum((df["ipc_fallback"] - df["ipc_bouncer"]).values, 0))[-1])
        g = df[df["state"] == "GATED"]; p = df[df["state"] == "PROBING"]
        la_meas.append(pos)
        la_two.append(float(Nep_la * D * env.ipc_slope))                       # constant in L_att
        la_tight.append(float(env.ipc_slope * gap * (Nep_la * D + phi_G * len(g) + phi_P * len(p))))
        la_corr.append(float(Nep_la * D * env.ipc_slope + env.ipc_slope * phi_P * Nep_la * La))
        print(f"  L_att={La}: measured={pos:.2f}  two_term={la_two[-1]:.2f}"
              f"{'  <-- two-term VIOLATED' if pos > la_two[-1] else ''}"
              f"  tight={la_tight[-1]:.2f}  corrected_loose={la_corr[-1]:.2f}")

    # REGRESSION: measured <= tight <= corrected_loose everywhere; two-term breaks for long attacks
    for i, Nep in enumerate(Neps):
        assert meas[i] <= tight[i] + 1e-6 <= corrected[i] + 2e-6, f"N_ep={Nep} ordering"
    for i, La in enumerate(Latts):
        assert la_meas[i] <= la_tight[i] + 1e-6 <= la_corr[i] + 2e-6, f"L_att={La} ordering"
    assert la_meas[-1] > la_two[-1], "two-term bound must be VIOLATED at L_att=960"

    return dict(Nep=Neps, measured=meas, bound=bound, tight=tight, corrected_loose=corrected,
                D=float(D), phi_G=float(phi_G), phi_P=float(phi_P),
                Latt=dict(L_att=Latts, N_ep=Nep_la, measured=la_meas, two_term=la_two,
                          tight=la_tight, corrected_loose=la_corr))


def main():
    C.setstyle()
    arl = arl_validation()
    reg = regret_validation()

    # --- ARL figure ---
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8))
    ax = axes[0]
    ax.semilogy(arl["H"], arl["arl0_emp"], "o", color=C.PALETTE["bouncer"], label="empirical")
    ax.semilogy(arl["H"], arl["arl0_th"], "-", color=C.PALETTE["accent"], label="Siegmund approx.")
    ax.set_xlabel("CUSUM threshold $H/\\sigma$"); ax.set_ylabel("$ARL_0$ (windows)")
    ax.set_title("(a) false-alarm: $ARL_0$ vs threshold")
    ax.legend()
    ax = axes[1]
    ax.plot(arl["H"], arl["arl1_emp"], "o", color=C.PALETTE["bouncer"], label="empirical")
    ax.plot(arl["H"], arl["arl1_th"], "-", color=C.PALETTE["accent"], label="Siegmund approx.")
    ax.set_xlabel("CUSUM threshold $H/\\sigma$"); ax.set_ylabel("$ARL_1$ = detection delay")
    ax.set_title("(b) detection delay vs threshold")
    ax.legend()
    C.savefig(fig, "th_arl.pdf")

    # --- regret figure: (a) N_ep sweep (short attacks), (b) L_att sweep (two-term breaks) ---
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8))
    ax = axes[0]
    ax.plot(reg["Nep"], reg["bound"], "s--", color="k", label=r"two-term $N_{ep}D\,r_{max}$")
    ax.plot(reg["Nep"], reg["corrected_loose"], "D:", color=C.PALETTE["unguarded"], label="corrected loose (+ exposure)")
    ax.plot(reg["Nep"], reg["tight"], "^-", color=C.PALETTE["accent"], label="tight (Lemma 1 corollary)")
    ax.plot(reg["Nep"], reg["measured"], "o-", color=C.PALETTE["bouncer"], label="measured positive regret")
    ax.fill_between(reg["Nep"], reg["measured"], reg["tight"], color=C.PALETTE["grid"], alpha=0.6)
    ax.set_xlabel("genuine drop episodes $N_{ep}$ ($L_{att}{=}60$)")
    ax.set_ylabel("cumulative regret vs floor (IPC·win)")
    ax.set_title("(a) short attacks: all bounds hold")
    ax.legend(loc="upper left", fontsize=6.2)
    ax = axes[1]
    la = reg["Latt"]
    ax.plot(la["L_att"], la["two_term"], "s--", color="k", label="two-term (const.)")
    ax.plot(la["L_att"], la["corrected_loose"], "D:", color=C.PALETTE["unguarded"], label="corrected loose")
    ax.plot(la["L_att"], la["tight"], "^-", color=C.PALETTE["accent"], label="tight")
    ax.plot(la["L_att"], la["measured"], "o-", color=C.PALETTE["bouncer"], label="measured")
    ax.set_xlabel(f"attack length $L_{{att}}$ (windows, $N_{{ep}}{{=}}{la['N_ep']}$)")
    ax.set_ylabel("cumulative regret vs floor (IPC·win)")
    ax.set_title("(b) long attacks: two-term is violated")
    ax.set_yscale("log"); ax.legend(loc="upper left", fontsize=6.2)
    C.savefig(fig, "th_regret.pdf")

    # ratio diagnostics
    r0 = np.array(arl["arl0_emp"]) / np.maximum(np.array(arl["arl0_th"]), 1)
    C.save_json("theory.json", dict(arl=arl, regret=reg,
                arl0_ratio_geomean=float(np.exp(np.mean(np.log(np.clip(r0, 1e-3, 1e6)))))))
    print(f"  ARL0 emp/theory geomean ratio = {np.exp(np.mean(np.log(np.clip(r0,1e-3,1e6)))):.2f}")


if __name__ == "__main__":
    main()
