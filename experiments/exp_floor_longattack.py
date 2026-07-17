"""Long-attack floor regression (Lemma 1, corrected three-term bound).

The released system keeps the n_L Leader-C sets running C in EVERY gate state
(simulate.py:82, "leaders fixed") so Delta-hat stays measurable and PROBING
re-trust is measured, not timed. A persistent drop therefore bleeds an
audit-exposure regret the old two-term bound N_ep*D*r_max + alpha*T*c_sw does not
count. This script (i) reproduces the reviewer's counterexample to the two-term
bound and (ii) verifies that the corrected loose three-term bound envelopes it:

  audit-exposure fractions   phi_G = n_L / n_sets            (GATED: only Leader-C runs C)
                             phi_P = phi_G + rho_aud*(1 - (n_L+n_F)/n_sets)   (PROBING: + audited region)
  LOOSE   Sigma (r^pi0 - r^Bouncer) <= N_ep*D*r_max + phi_P*T_att*r_max + alpha*T*c_sw
  PLUG-IN replace r_max by the realized gap (q0 - mu_C^att) and split the
          post-detection occupancy: phi_G on GATED windows, phi_P on PROBING.
          This is a descriptive tracker, not a bound: it inserts the mean-delay
          approximation D=H/(K-Delta), and an individual seeded trajectory can exceed it.
          The guarantee under the stated premises is the LOOSE expectation bound (only its
          exposure term additionally receives a high-probability envelope).

Deterministic: all RNG explicitly seeded. Emits results/floor_longattack.json.
"""
import sys, json, os
import numpy as np
sys.path.insert(0, 'experiments')
import common as C
from bouncer.adversary import BroadAttack
from bouncer.simulate import run_episode, SimConfig
from bouncer.theory import regret_bound

RHO_AUD = SimConfig.audited_region_frac          # 0.05, the PROBING audited fraction
PHI_G = C.STD["n_L"] / C.STD["n_sets"]            # 1.5625%
PHI_P = PHI_G + RHO_AUD * (1 - (C.STD["n_L"] + C.STD["n_F"]) / C.STD["n_sets"])   # ~6.41%


def run(T, onset, seed):
    comp = C.make_competence()
    K = C.STD["tau"] + C.STD["gamma_detect"] / 2
    env, b = C.make_bouncer("full", comp=comp, seed=seed)
    sim = C.simconfig(T=T)
    adv = BroadAttack(C.STD["n_sets"], onset=onset, offset=None, stress=0.92, seed=seed + 100)
    df = run_episode(comp, env, b, adv, sim, seed=seed + 200)

    gap = comp.q0 - float(comp.mu_C(0.92)) / comp.r_max        # realized reward gap q0 - mu_C^att = 0.344
    T_att = T - onset                                          # windows inside the (single, persistent) drop episode
    fb = regret_bound(r_max=1.0, N_ep=1, T=T, c_sw=env.ipc_slope * 0.1, K=K,
                      H=b.cfg.tierb_H, sigma_delta=b.dueling.sigma_delta(C.STD["m"]),
                      mean_signal_clean=0.265, delta_true_drop=float(comp.delta_true(0.92)))
    D = fb.D
    old_loose = fb.detection_term * env.ipc_slope + fb.false_alarm_term      # FALSE two-term bound

    per = (df["ipc_fallback"] - df["ipc_bouncer"]).values
    pos = float(np.cumsum(np.maximum(per, 0))[-1])
    raw = float(np.cumsum(per)[-1])
    g = df[df["state"] == "GATED"]; p = df[df["state"] == "PROBING"]
    n_gated, n_prob = len(g), len(p)

    # corrected LOOSE (r_max=1 per exposed window, phi_P worst-case exposure), in IPC units
    corrected_loose = env.ipc_slope * (fb.detection_term + PHI_P * T_att * 1.0) + fb.false_alarm_term
    # Descriptive plug-in tracker (realized gap and occupancy), in IPC units. It is
    # intentionally not asserted as an envelope because D is only a mean approximation.
    tracker = env.ipc_slope * gap * (fb.detection_term + PHI_G * n_gated + PHI_P * n_prob)
    return dict(T=T, onset=onset, seed=seed, D=float(D), gap=float(gap), T_att=int(T_att),
                phi_G=float(PHI_G), phi_P=float(PHI_P),
                old_loose=float(old_loose), corrected_loose=float(corrected_loose),
                tracker=float(tracker), measured_pos=pos, measured_raw=raw,
                n_gated=n_gated, n_prob=n_prob,
                per_gated=float((g.ipc_fallback - g.ipc_bouncer).mean()),
                per_prob=float((p.ipc_fallback - p.ipc_bouncer).mean()))


def main():
    print(f"phi_G={PHI_G:.6f}  phi_P={PHI_P:.6f}  (rho_aud={RHO_AUD})")
    seeds = (5, 11, 23)
    cells = [run(1400, 50, s) for s in seeds]          # persistent drop, L_att = 1350
    long = run(2600, 5, 5)                             # longer horizon, the two-term breaks harder

    # REGRESSION ASSERTIONS: two-term FALSE, corrected loose three-term envelope VALID.
    for r in cells:
        assert r["measured_pos"] > r["old_loose"], \
            f"two-term bound should be VIOLATED: measured {r['measured_pos']:.2f} <= old_loose {r['old_loose']:.2f}"
        assert r["tracker"] <= r["corrected_loose"] + 1e-6, \
            f"loose must dominate plug-in tracker: tracker {r['tracker']:.2f} > corrected_loose {r['corrected_loose']:.2f}"
        assert r["measured_pos"] <= r["corrected_loose"] + 1e-6, \
            f"corrected loose envelope failed: measured {r['measured_pos']:.2f} > loose {r['corrected_loose']:.2f}"
    assert long["measured_raw"] > long["old_loose"], "T=2600 raw must exceed the two-term bound"
    assert long["tracker"] <= long["corrected_loose"] + 1e-6
    assert long["measured_pos"] <= long["corrected_loose"] + 1e-6

    for r in cells:
        print(f"  seed {r['seed']}: measured={r['measured_pos']:.2f}  tracker={r['tracker']:.2f}  "
              f"corrected_loose={r['corrected_loose']:.2f}  old_two_term={r['old_loose']:.2f}  "
              f"(n_gated={r['n_gated']} @ {r['per_gated']:.5f}, n_prob={r['n_prob']})")
    print(f"  T=2600: measured_raw={long['measured_raw']:.2f}  old_two_term={long['old_loose']:.2f}")

    out = dict(
        note=("Corrected Lemma 1: the two-term bound N_ep*D*r_max + alpha*T*c_sw is FALSE for the "
              "released system because n_L Leader-C sets run C in every gate state (simulate.py:82); "
              "a persistent drop bleeds phi_G*gap per GATED window. The three-term bound with an "
              "audit-exposure term phi_P*T_att*r_max envelopes it. The smaller plug-in tracker uses the "
              "realized gap, GATED/PROBING occupancy, and a mean-delay approximation; it is descriptive "
              "rather than a bound and can slightly under-predict individual seeded trajectories."),
        phi_G=PHI_G, phi_P=PHI_P, rho_aud=RHO_AUD,
        persistent=cells, long_horizon=long,
        summary=dict(
            old_two_term_loose=cells[0]["old_loose"],
            measured_pos_mean=float(np.mean([r["measured_pos"] for r in cells])),
            tracker_mean=float(np.mean([r["tracker"] for r in cells])),
            corrected_loose_mean=float(np.mean([r["corrected_loose"] for r in cells])),
            blended_exposure_frac=float(np.mean(
                [(r["phi_G"] * r["n_gated"] + r["phi_P"] * r["n_prob"]) / (r["n_gated"] + r["n_prob"])
                 for r in cells])),
        ),
    )
    path = os.path.join(C.RESDIR, "floor_longattack.json")
    json.dump(out, open(path, "w"), indent=2)
    print(f"  wrote {path}  (blended exposure {out['summary']['blended_exposure_frac']*100:.2f}% of the gap)")


if __name__ == "__main__":
    main()
