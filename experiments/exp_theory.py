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
from bouncer.simulate import run_episode
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


def regret_validation():
    """Worst-case cumulative regret vs fallback as N_ep genuine drop episodes
    accumulate; compare to Lemma 6.1 bound."""
    comp = C.make_competence()
    sim_T = 60   # windows per episode segment
    K = C.STD["tau"] + C.STD["gamma_detect"] / 2
    sigma = np.sqrt((1.0 / (4 * C.STD["m"])) * (2.0 / C.STD["n_L"]))
    delta_drop = float(comp.delta_true(0.92))
    D = detection_delay_approx(K, C.STD["tierb_H"], delta_drop)
    Neps = [1, 2, 3, 4, 5, 6]
    meas, bound, tight = [], [], []
    # tight bound: pre-detection FULL-resource degradation for D windows, then
    # only the n_L/n_sets Leader-C fraction stays degraded for the rest of the
    # L_att-window attack (the steady-state dueling cost). gap = q0 - mu_C(att).
    gap = comp.q0 - float(comp.mu_C(0.92)) / comp.r_max
    L_att = sim_T
    leaderC_frac = C.STD["n_L"] / C.STD["n_sets"]
    for Nep in Neps:
        # build a trace with Nep attack pulses
        env, b = C.make_bouncer("full", comp=comp, seed=Nep)
        T = sim_T * (2 * Nep + 1)
        # pulse: attack for sim_T windows every other segment
        from bouncer.adversary import BroadAttack
        pulses = []

        class MultiPulse:
            name = "multi"
            def __init__(self, n_sets, seed):
                self.n_sets = n_sets; self.rng = np.random.default_rng(seed)
            def window(self, t, dueling=None, gate_state=None):
                seg = t // sim_T
                active = (seg % 2 == 1) and (seg // 2 < Nep)
                from bouncer.adversary import Window
                lvl = 0.92 if active else 0.05
                u = np.clip(lvl + 0.02 * self.rng.standard_normal(self.n_sets), 0, 1)
                return Window(u, suppress_features=False, label_attack=active)

        sim = C.simconfig(T=T)
        df = run_episode(comp, env, b, MultiPulse(C.STD["n_sets"], seed=100 + Nep), sim, seed=200 + Nep)
        reg = M.cumulative_regret_vs_fallback(df)
        worst = float(np.max(np.maximum.accumulate(np.maximum(reg, 0))))  # max positive excursion
        # also the running positive regret (only windows below floor)
        pos = np.cumsum(np.maximum((df["ipc_fallback"] - df["ipc_bouncer"]).values, 0))
        meas.append(float(pos[-1]))
        # Lemma 1 bound in IPC units: N_ep*D*r_max (r_max=1) scaled by ipc_slope.
        # This is the LOOSE Eq.(floor) bound (caps the per-window gap at r_max);
        # alpha*T*c_sw ~ 0 at this operating point.
        det_term = Nep * D * env.ipc_slope * comp.r_max
        bnd = det_term + 0.0
        bound.append(float(bnd))
        tght = Nep * env.ipc_slope * gap * (D + leaderC_frac * (L_att - D))
        tight.append(float(tght))
        print(f"  N_ep={Nep}: measured={meas[-1]:.2f}  loose={bnd:.2f}  tight={tght:.2f}  D={D:.2f}")
    return dict(Nep=Neps, measured=meas, bound=bound, tight=tight, D=float(D))


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

    # --- regret figure ---
    fig, ax = plt.subplots(figsize=(3.9, 2.8))
    ax.plot(reg["Nep"], reg["bound"], "s--", color="k", label=r"loose bound $N_{ep}D\,r_{max}$")
    ax.plot(reg["Nep"], reg["tight"], "^-", color=C.PALETTE["accent"], label="tight bound (+ steady-state)")
    ax.plot(reg["Nep"], reg["measured"], "o-", color=C.PALETTE["bouncer"], label="measured positive regret")
    ax.fill_between(reg["Nep"], reg["measured"], reg["tight"], color=C.PALETTE["grid"], alpha=0.6)
    ax.set_xlabel("genuine drop episodes $N_{ep}$")
    ax.set_ylabel("cumulative regret vs floor (IPC·win)")
    ax.set_title("Lemma 6.1: both bounds envelope measured regret")
    ax.legend(loc="upper left", fontsize=6.8)
    C.savefig(fig, "th_regret.pdf")

    # ratio diagnostics
    r0 = np.array(arl["arl0_emp"]) / np.maximum(np.array(arl["arl0_th"]), 1)
    C.save_json("theory.json", dict(arl=arl, regret=reg,
                arl0_ratio_geomean=float(np.exp(np.mean(np.log(np.clip(r0, 1e-3, 1e6)))))))
    print(f"  ARL0 emp/theory geomean ratio = {np.exp(np.mean(np.log(np.clip(r0,1e-3,1e6)))):.2f}")


if __name__ == "__main__":
    main()
