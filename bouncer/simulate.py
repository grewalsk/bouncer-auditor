"""
simulate.py — Episode runner. Drives a Bouncer instance through a scenario,
drawing faithful per-set bounded rewards, routing them through the secret
dueling pools, and recording everything needed for the §10 metrics.

Counterfactual handling: the simulator draws BOTH the controller-path reward and
the fallback reward for every set (it can, it's a simulator), but the Bouncer
only ever consumes the reward of the policy actually run on each set — Leader-C
sees C, Leader-F sees pi0 — so Δ̂ is a *measured*, non-counterfactual estimate,
exactly as in silicon.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd

from .environment import MicroArchEnv, CompetenceModel
from .bouncer import Bouncer
from .gate_fsm import Gate


def _bernoulli_mean(p: np.ndarray, m: int, rng: np.random.Generator) -> np.ndarray:
    """Mean of m Bernoulli(p) draws per element. Var = p(1-p)/m <= 1/(4m).

    The mean of m i.i.d. Bernoulli(p) is exactly Binomial(m, p)/m, so we draw one
    Binomial per element instead of m Bernoullis — identical distribution, ~m x
    fewer RNG calls."""
    p = np.clip(p, 0.0, 1.0)
    return rng.binomial(m, p).astype(float) / m


@dataclass
class SimConfig:
    n_sets: int = 256
    m: int = 64                 # decisions per set per window
    sample_rate_inv_k: int = 8  # Tier-A samples 1/k of sets each window
    T: int = 400                # windows per episode
    # rho_aud: fraction of followers re-enabled to C in PROBING. make_bouncer wires this value
    # into SetDuelingConfig.audited_frac (which keeps its own default only as a fallback for direct
    # construction), and a per-window assertion in run_episode fails LOUDLY if routing and the
    # Lemma-1 phi_P bound ever diverge -- so they cannot silently disagree.
    audited_region_frac: float = 0.05


def run_episode(comp: CompetenceModel, env: MicroArchEnv, bouncer: Bouncer,
                adversary, simcfg: SimConfig, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = simcfg.n_sets
    m = simcfg.m
    r_max = comp.r_max
    n_sampled = max(8, n // simcfg.sample_rate_inv_k)

    rows = []
    for t in range(simcfg.T):
        win = adversary.window(t, dueling=bouncer.dueling,
                               gate_state=bouncer.gate.state)
        u_C = win.u_C

        # per-set mean rewards (bounded in [0, r_max]); the counterfactual pair
        p_C = comp.mu_C(u_C) / r_max
        rC_per_set = _bernoulli_mean(p_C, m, rng) * r_max
        p_0 = np.full(n, comp.q0)
        rF_per_set = _bernoulli_mean(p_0, m, rng) * r_max

        # ground-truth competence this window (avg over controller path)
        delta_true = float(np.mean(comp.delta_true(u_C)))

        # --- Tier-A aggregate sampled stream ---
        samp = rng.choice(n, size=n_sampled, replace=False)
        u_feat = np.full(len(samp), 0.05) if win.suppress_features else u_C[samp]
        feat_win = env.features(u_feat)
        conf_win = env.confidence(u_feat) if win.suppress_features else env.confidence(u_C[samp])
        a_win = np.ones(len(samp))                  # action proxy (e.g., degree)
        r_win = rC_per_set[samp]                    # realized reward (true, reflects degradation)

        obs = dict(rC_per_set=rC_per_set, rF_per_set=rF_per_set,
                   feat_win=feat_win, conf_win=conf_win, a_win=a_win,
                   r_win=r_win, delta_true=delta_true)
        # INVARIANT (single-assignment-per-window): snapshot the secret assignment
        # the estimator is about to consume; deployment below must route on the SAME
        # one. bouncer.step no longer reseeds internally, so this holds by construction
        # -- the assertion guards against regressions.
        _assign_est = bouncer.dueling.leaderC.copy()
        tel = bouncer.step(obs)

        # routing and the phi_P bound must use the same audit fraction (no silent divergence)
        assert abs(bouncer.dueling.cfg.audited_frac - simcfg.audited_region_frac) < 1e-12, (
            "audited_frac (routing) != audited_region_frac (bound); wire them from one source")
        # --- realized deployed performance (victim experience) ---
        d = bouncer.dueling
        assert np.array_equal(d.leaderC, _assign_est), (
            "assignment drifted between Delta-hat estimation and deployment routing "
            "(the counterfactual-estimator bug); reseed must happen at window close")
        deployed = np.empty(n)
        deployed[d.leaderC] = rC_per_set[d.leaderC]      # leaders fixed
        deployed[d.leaderF] = rF_per_set[d.leaderF]
        foll = d.follower
        if tel["C_active"]:
            deployed[foll] = rC_per_set[foll]            # followers run C
        elif tel["probing"]:
            deployed[foll] = rF_per_set[foll]
            aud = d.audited                                    # secret UNIFORM subset (set_dueling._assign);
            deployed[aud] = rC_per_set[aud]                    # NOT the sorted prefix -- traffic-independent exposure
        else:  # GATED
            deployed[foll] = rF_per_set[foll]

        realized_rate = float(np.mean(deployed))
        unguarded_rate = float(np.mean(rC_per_set))      # C everywhere
        fallback_rate = float(np.mean(rF_per_set))       # pi0 everywhere

        rows.append(dict(
            t=t, delta_true=delta_true, delta_hat=tel["delta_hat"],
            state=tel["state"].name, C_active=tel["C_active"], probing=tel["probing"],
            realized_rate=realized_rate, unguarded_rate=unguarded_rate,
            fallback_rate=fallback_rate,
            ipc_bouncer=env.ipc(realized_rate), ipc_unguarded=env.ipc(unguarded_rate),
            ipc_fallback=env.ipc(fallback_rate),
            S_in=tel["S_in"], S_dec=tel["S_dec"], S_res=tel["S_res"],
            escalate=tel["escalate"], rbar_L=tel["rbar_L"], rbar_F=tel["rbar_F"],
            label_attack=win.label_attack,
            off_policy=(delta_true < bouncer.cfg.tau),
        ))

        # window closed: NOW advance the secret assignment for the next window.
        # Reseeding here (not inside bouncer.step) is what keeps estimation and
        # deployment on one assignment per window -- see the invariant above.
        bouncer.dueling.maybe_reseed()
    return pd.DataFrame(rows)
