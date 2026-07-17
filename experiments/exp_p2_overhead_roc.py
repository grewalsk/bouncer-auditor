"""
P2 — Tripwires, ROC, the §4 dependency chain, and the §9 overhead budget.

(1) ROC: detection TPR vs FPR sweeping the CUSUM threshold, for the *competence*
    detector (Tier-B Δ̂) vs the *input-OOD* detector (S_in), on broad and mimicry
    attacks. Competence dominates; S_in collapses to the diagonal under mimicry.
(2) Detection latency vs dueling pool size — the central design chain
    pool size n -> sigma_Δ -> CUSUM threshold H (held at fixed false-alarm) ->
    detection delay D. Empirical latency overlaid with the analytic D≈H/(K-Δ).
(3) Overhead Pareto: storage (dueling counters + Tier-A sketches) vs detection
    latency, and the §9 budget table (analytical bit/energy counts).

Detector-level evaluation: we extract the Δ̂ and S_in streams from no-auditor runs
and run offline CUSUMs, the standard way to characterize a detector independent of
the gate FSM (whose end-to-end behaviour P1 already shows).
"""
import numpy as np
import matplotlib.pyplot as plt

import common as C
from bouncer.adversary import Clean, BroadAttack, MimicryAttack, BenignDrift
from bouncer.simulate import run_episode
from bouncer.cusum import LowerCusum, TwoSidedCusum, detection_delay_approx
from bouncer import metrics as M

ONSET, T = 80, 220


def collect_streams(adv_factory, n_ep, n_L=32, signal="delta", m=None, seed0=0):
    """Return list of 1D signal streams (delta_hat or S_in) from no-auditor runs."""
    streams = []
    for ep in range(n_ep):
        comp = C.make_competence()
        env, b = C.make_bouncer("no_auditor", comp=comp, n_L=n_L, n_F=n_L,
                                n_L_bg=n_L, n_F_bg=n_L, seed=seed0 + ep)
        sim = C.simconfig(T=T, m=m)
        df = run_episode(comp, env, b, adv_factory(seed0 + ep), sim, seed=seed0 + 5000 + ep)
        streams.append(df["S_in"].values if signal == "in" else df["delta_hat"].values)
    return streams


def offline_lower_alarm(stream, K, H, onset, deadline=40):
    det = LowerCusum(K=K, H=H, auto_reset=False)
    for t, x in enumerate(stream):
        if det.update(x):
            return t
    return None


def offline_twosided_alarm(stream, ref, k, H, onset, deadline=40):
    det = TwoSidedCusum(ref=ref, k=k, H=H, auto_reset=False)
    for t, x in enumerate(stream):
        if det.update(x):
            return t
    return None


def roc_curve(clean_streams, atk_streams, kind, K=0.10, onset=ONSET, deadline=40,
              Hgrid=None, ref=0.0, k=0.02):
    Hgrid = Hgrid if Hgrid is not None else np.linspace(0.05, 3.0, 24)
    tpr, fpr = [], []
    for H in Hgrid:
        if kind == "lower":
            ca = [offline_lower_alarm(s, K, H, onset) for s in clean_streams]
            aa = [offline_lower_alarm(s, K, H, onset) for s in atk_streams]
        else:
            ca = [offline_twosided_alarm(s, ref, k, H, onset) for s in clean_streams]
            aa = [offline_twosided_alarm(s, ref, k, H, onset) for s in atk_streams]
        fpr.append(np.mean([a is not None for a in ca]))
        tpr.append(np.mean([(a is not None and onset <= a <= onset + deadline) for a in aa]))
    return np.array(fpr), np.array(tpr)


def latency_vs_pool():
    """Per pool size n: calibrate H to a fixed clean FPR (5%), then measure
    detection latency on a *subtle* competence regression (Δ_true just below τ)
    monitored with a SHORT window (m=16). This is the regime where the §4 chain
    pool size -> sigma_Δ -> H -> latency genuinely binds; at the realistic large-
    gap operating point detection is instant and pool-insensitive (overhead-bound)."""
    comp = C.make_competence()
    K = C.STD["tau"] + C.STD["gamma_detect"] / 2
    m_short = 16
    # subtle regression: drive Δ_true ~ 0 (just below τ), the hardest case
    weak_stress = float(comp.u_crossing)   # Δ_true(u_crossing) = 0
    delta_drop = float(comp.delta_true(weak_stress))
    ns = [2, 4, 8, 16, 32, 64, 128]
    rows = []
    for n in ns:
        clean = collect_streams(lambda s: Clean(C.STD["n_sets"], seed=s),
                                16, n_L=n, signal="delta", m=m_short, seed0=300 + n)
        atk = collect_streams(lambda s: BroadAttack(C.STD["n_sets"], onset=ONSET,
                                                    stress=weak_stress, seed=s),
                              24, n_L=n, signal="delta", m=m_short, seed0=600 + n)
        sigma = np.sqrt((1.0 / (4 * m_short)) * (2.0 / n))
        # calibrate H: smallest H with clean FPR <= 0.05
        Hgrid = np.linspace(0.05, 4.0, 80)
        Hsel, fpr_sel = Hgrid[-1], 1.0
        for H in Hgrid:
            ca = [offline_lower_alarm(s, K, H, ONSET) for s in clean]
            fpr = np.mean([a is not None for a in ca])
            if fpr <= 0.05:
                Hsel, fpr_sel = H, fpr
                break
        lats = []
        for s in atk:
            a = offline_lower_alarm(s, K, Hsel, ONSET)
            if a is not None and a >= ONSET:
                lats.append(a - ONSET)
        rows.append(dict(n=n, sigma=sigma, H=Hsel, fpr=float(fpr_sel),
                         latency=float(np.mean(lats)) if lats else float("inf"),
                         latency_std=float(np.std(lats)) if lats else 0.0,
                         D_pred=float(detection_delay_approx(K, Hsel, delta_drop))))
        print(f"  n={n:3d} sigma={sigma:.4f} H*={Hsel:.2f} FPR={fpr_sel:.2f} "
              f"lat={rows[-1]['latency']:.1f} D_pred={rows[-1]['D_pred']:.1f}")
    return ns, rows, delta_drop


def overhead_budget():
    """Illustrative 16-bit storage budget matching the released Tier-A dimensions.

    The Python reference uses floating point; this calculation is a proposed quantized
    representation, not an RTL area, timing, or numerical-fidelity measurement.
    """
    d, p = 16, 8                     # feature dim, dense projection dimension
    n_L = n_F = 32
    # storage (bits)
    rp_matrix = d * p * 16           # proposed 16-bit dense projection weights
    s_in_ref = p * 2 * 16            # projected reference mean and std
    fwd_model = (d + 2) * 16         # feature + action + bias coefficients
    cusum_regs = 4 * 2 * 16          # 4 detectors x {C+,C-} x 16-bit
    dueling_ctr = (n_L + n_F) * 8    # saturating counters (reuse ATD/sampler)
    total_bits = rp_matrix + s_in_ref + fwd_model + cusum_regs + dueling_ctr
    table = [
        ("Set-dueling counters", dueling_ctr, "reuse existing", "sampler"),
        ("S_in: dense projection + mean/std", rp_matrix + s_in_ref,
         f"{d * p} MACs on 1/k dec", "adjacent SRAM"),
        ("S_res: forward model g", fwd_model, f"{d + 2} MACs on 1/k dec", "adjacent"),
        ("CUSUM detectors (x4)", cusum_regs, "2 add/cmp each", "adjacent"),
    ]
    return dict(total_bits=total_bits, total_bytes=total_bits / 8.0,
                table=table,
                area_pct_est=round(total_bits / 8.0 / (1024.0 * 256) * 100, 4),  # vs 256KB SRAM budget
                energy_not_measured=True,
                access_path_timing_not_measured=True,
                proposed_quantization_bits=16)


def main():
    C.setstyle()
    # --- streams for ROC (standard pool n=32) ---
    clean = collect_streams(lambda s: Clean(C.STD["n_sets"], seed=s), 25, signal="delta", seed0=10)
    broad = collect_streams(lambda s: BroadAttack(C.STD["n_sets"], onset=ONSET, stress=0.9, seed=s),
                            25, signal="delta", seed0=40)
    mim = collect_streams(lambda s: MimicryAttack(C.STD["n_sets"], onset=ONSET, stress=0.9, seed=s),
                          25, signal="delta", seed0=70)
    clean_in = collect_streams(lambda s: Clean(C.STD["n_sets"], seed=s), 25, signal="in", seed0=10)
    broad_in = collect_streams(lambda s: BroadAttack(C.STD["n_sets"], onset=ONSET, stress=0.9, seed=s),
                               25, signal="in", seed0=40)
    mim_in = collect_streams(lambda s: MimicryAttack(C.STD["n_sets"], onset=ONSET, stress=0.9, seed=s),
                             25, signal="in", seed0=70)

    K = C.STD["tau"] + C.STD["gamma_detect"] / 2
    fpr_cb, tpr_cb = roc_curve(clean, broad, "lower", K=K, Hgrid=np.linspace(0.05, 3.0, 24))
    fpr_cm, tpr_cm = roc_curve(clean, mim, "lower", K=K, Hgrid=np.linspace(0.05, 3.0, 24))
    fpr_ib, tpr_ib = roc_curve(clean_in, broad_in, "two", ref=0.0, k=0.02, Hgrid=np.linspace(0.02, 1.5, 24))
    fpr_im, tpr_im = roc_curve(clean_in, mim_in, "two", ref=0.0, k=0.02, Hgrid=np.linspace(0.02, 1.5, 24))

    fig, ax = plt.subplots(figsize=(3.7, 3.0))
    ax.plot(fpr_cb, tpr_cb, "-", color=C.PALETTE["bouncer"], lw=1.8, label="competence Δ̂ · broad")
    ax.plot(fpr_cm, tpr_cm, "-", color=C.PALETTE["oracle"], lw=1.8, label="competence Δ̂ · mimicry")
    ax.plot(fpr_ib, tpr_ib, "--", color=C.PALETTE["sin"], lw=1.5, label="input-OOD $S_{in}$ · broad")
    ax.plot(fpr_im, tpr_im, ":", color=C.PALETTE["unguarded"], lw=1.7, label="input-OOD $S_{in}$ · mimicry")
    ax.plot([0, 1], [0, 1], color="#bbb", lw=0.7)
    ax.set_xlabel("false-alarm rate (clean)"); ax.set_ylabel("true-positive rate")
    ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
    ax.set_title("Detection ROC")
    ax.legend(loc="lower right")
    C.savefig(fig, "p2_roc.pdf")

    # --- latency vs pool ---
    ns, rows, delta_drop = latency_vs_pool()
    fig, ax = plt.subplots(figsize=(3.7, 3.0))
    lat = [r["latency"] for r in rows]
    Dp = [r["D_pred"] for r in rows]
    sig = [r["sigma"] for r in rows]
    ax.plot(ns, lat, "o-", color=C.PALETTE["bouncer"], lw=1.6, label="empirical latency")
    ax.plot(ns, Dp, "s--", color=C.PALETTE["accent"], lw=1.3, label=r"analytic $D\approx H/(K-\Delta)$")
    ax.set_xscale("log", base=2)
    ax.set_xlabel(r"dueling pool size $n_L=n_F$")
    ax.set_ylabel("detection latency (windows)")
    ax.set_title("§4 chain: pool size → latency")
    ax.legend()
    ax2 = ax.twinx()
    ax2.plot(ns, sig, "^:", color=C.PALETTE["fallback"], lw=1.0, alpha=0.8)
    ax2.set_ylabel(r"$\sigma_\Delta$", color=C.PALETTE["fallback"])
    ax2.tick_params(axis="y", labelcolor=C.PALETTE["fallback"]); ax2.grid(False)
    C.savefig(fig, "p2_latency_pool.pdf")

    # --- overhead Pareto ---
    fig, ax = plt.subplots(figsize=(3.7, 3.0))
    storage = [2 * n * 8 / 8 for n in ns]   # bytes of dueling counters
    ax.plot(storage, lat, "o-", color=C.PALETTE["bouncer"], lw=1.6)
    for x, y, n in zip(storage, lat, ns):
        ax.annotate(f"n={n}", (x, y), textcoords="offset points", xytext=(4, 4), fontsize=6.5)
    ax.set_xlabel("dueling-counter storage (bytes)")
    ax.set_ylabel("detection latency (windows)")
    ax.set_title("Overhead → latency Pareto frontier")
    C.savefig(fig, "p2_overhead_pareto.pdf")

    budget = overhead_budget()
    C.save_json("p2.json", dict(
        roc=dict(comp_broad=[fpr_cb.tolist(), tpr_cb.tolist()],
                 comp_mim=[fpr_cm.tolist(), tpr_cm.tolist()],
                 sin_broad=[fpr_ib.tolist(), tpr_ib.tolist()],
                 sin_mim=[fpr_im.tolist(), tpr_im.tolist()]),
        latency_vs_pool=rows, delta_drop=delta_drop,
        overhead=budget))
    print(f"  overhead: {budget['total_bytes']:.0f} bytes proposed 16-bit storage, "
          f"~{budget['area_pct_est']}% of a 256KB SRAM; RTL timing/energy not measured")


if __name__ == "__main__":
    main()
