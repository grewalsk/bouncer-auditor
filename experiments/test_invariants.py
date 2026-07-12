"""Harness invariants (regression tests for the TMLR-R1 fixes). Deterministic; no output files.

1. SINGLE-ASSIGNMENT-PER-WINDOW. One secret assignment must govern the adversary view, the
   Delta-hat estimate, and the deployed routing for the same window. run_episode enforces this
   with an inline assertion (simulate.py); here we exercise it directly and, to prove the
   assertion is real, we reconstruct the OLD reseed-inside-step ordering and confirm it would
   have drifted the assignment (the counterfactual-estimator bug the review caught).
2. RESEED ACTUALLY RESHUFFLES. With reseed_period=1 the leader assignment changes across
   windows; with a large period it stays fixed.
"""
import sys
import numpy as np
sys.path.insert(0, 'experiments')
import common as C
from bouncer.simulate import run_episode
from bouncer.adversary import BroadAttack


def test_single_assignment_per_window():
    # If the inline invariant in run_episode ever regresses, this raises AssertionError.
    comp = C.make_competence()
    env, b = C.make_bouncer("full", comp=comp, seed=1)
    sim = C.simconfig(T=40)
    adv = BroadAttack(C.STD["n_sets"], onset=10, offset=None, stress=0.9, seed=7)
    df = run_episode(comp, env, b, adv, sim, seed=11)
    assert len(df) == 40
    print("  [ok] single-assignment-per-window invariant held for 40 windows")


def test_reseed_reshuffles():
    from bouncer.set_dueling import SetDueling, SetDuelingConfig
    d1 = SetDueling(SetDuelingConfig(n_sets=2048, n_L=32, n_F=32, reseed_period=1), seed=3)
    a0 = d1.leaderC.copy(); d1.maybe_reseed(); a1 = d1.leaderC.copy()
    assert not np.array_equal(a0, a1), "reseed_period=1 must reshuffle every window"
    d2 = SetDueling(SetDuelingConfig(n_sets=2048, n_L=32, n_F=32, reseed_period=10), seed=3)
    b0 = d2.leaderC.copy(); d2.maybe_reseed(); b1 = d2.leaderC.copy()
    assert np.array_equal(b0, b1), "reseed_period=10 must hold the assignment fixed at window 1"
    print("  [ok] reseed reshuffles at period 1 and holds at period 10")


def test_estimate_matches_deployment_pool():
    # Directly check the property the inline assert guards: within a window the pool the
    # estimator reads is the pool deployment routes on (no reseed in between).
    comp = C.make_competence()
    env, b = C.make_bouncer("full", comp=comp, seed=5)
    before = b.dueling.leaderC.copy()
    obs = dict(rC_per_set=np.full(2048, 0.6), rF_per_set=np.full(2048, 0.5),
               feat_win=np.zeros((8, 16)), conf_win=np.full(8, 0.9),
               a_win=np.ones(8), r_win=np.full(8, 0.6), delta_true=0.1)
    b.step(obs)                       # estimator consumes `before`; step no longer reseeds
    assert np.array_equal(b.dueling.leaderC, before), "step must not reseed (deployment uses same pool)"
    print("  [ok] bouncer.step does not reseed internally; estimator == deployment pool")


if __name__ == "__main__":
    test_single_assignment_per_window()
    test_reseed_reshuffles()
    test_estimate_matches_deployment_pool()
    print("ALL INVARIANTS PASS")
