"""Long-attack floor regression: verifies the (corrected) Lemma 1 bound envelopes a
single PERSISTENT drop episode. Pre-fix, this reproduces the reviewer's counterexample
to the two-term bound."""
import sys, numpy as np
sys.path.insert(0, 'experiments')
import common as C
from bouncer.adversary import BroadAttack
from bouncer.simulate import run_episode
from bouncer.theory import regret_bound

def run(T, onset, seed):
    comp = C.make_competence()
    K = C.STD["tau"] + C.STD["gamma_detect"]/2
    env, b = C.make_bouncer("full", comp=comp, seed=seed)
    sim = C.simconfig(T=T)
    adv = BroadAttack(C.STD["n_sets"], onset=onset, offset=None, stress=0.92, seed=seed+100)
    df = run_episode(comp, env, b, adv, sim, seed=seed+200)
    fb = regret_bound(r_max=1.0, N_ep=1, T=T, c_sw=env.ipc_slope*0.1, K=K,
                      H=b.cfg.tierb_H, sigma_delta=b.dueling.sigma_delta(C.STD["m"]),
                      mean_signal_clean=0.265, delta_true_drop=float(comp.delta_true(0.92)))
    old_loose = fb.detection_term*env.ipc_slope + fb.false_alarm_term   # two-term bound
    per = (df["ipc_fallback"]-df["ipc_bouncer"]).values
    pos = np.cumsum(np.maximum(per, 0)); raw = np.cumsum(per)
    g = df[df["state"]=="GATED"]; p = df[df["state"]=="PROBING"]
    return dict(old_loose=old_loose, pos=pos[-1], raw=raw[-1],
                n_gated=len(g), per_gated=float((g.ipc_fallback-g.ipc_bouncer).mean()),
                n_prob=len(p),  per_prob=float((p.ipc_fallback-p.ipc_bouncer).mean()),
                gated_sum=float((g.ipc_fallback-g.ipc_bouncer).sum()))

for seed in (5, 11, 23):
    r = run(1400, 50, seed); print(seed, r)
print(run(2600, 5, 5))
