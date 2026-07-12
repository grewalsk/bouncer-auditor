"""
bouncer.py — Top-level two-tier orchestrator wiring Tier-A tripwires, Tier-B
randomized-secret set-dueling, the CUSUM detectors, and the gate FSM (§3).

Detector modes (for the §10 baseline comparison, all sharing the same FSM/gate
so comparisons are apples-to-apples):
  'full'       : Tier-A escalates SUSPECT (raising Tier-B duty); Tier-B Δ̂ CUSUM
                 gates. Background Tier-B can gate directly from TRUSTED (this is
                 the refinement that closes the mimicry gap — see paper §3).
  's_in_only'  : "input-OOD-only" baseline — only the S_in covariate-shift CUSUM,
                 and it gates directly. Proves Tier-A-alone is spoofable.
  'oracle'     : gates on ground-truth Δ<τ. Upper bound on detection.
  'no_auditor' : never gates (C always on). Perf upper bound / safety lower bound.
  'always_fb'  : always gated (pi0 always on). Safety upper bound / perf floor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from .tier_a import TierA, TierAConfig
from .set_dueling import SetDueling, SetDuelingConfig
from .cusum import LowerCusum
from .gate_fsm import GateFSM, GateConfig, Gate


@dataclass
class BouncerConfig:
    n_sets: int = 256
    tau: float = 0.05
    gamma_detect: float = 0.10          # CUSUM reference slack; K = tau + gamma/2
    tierb_H: float = 0.8                # Tier-B lower-CUSUM threshold
    # Duty cycle: number of leader sets averaged in background (TRUSTED) vs full.
    n_L_background: int = 8
    n_F_background: int = 8
    detector_mode: str = "full"
    set_dueling: SetDuelingConfig = field(default_factory=SetDuelingConfig)
    tier_a: TierAConfig = field(default_factory=TierAConfig)
    gate: GateConfig = field(default_factory=GateConfig)
    region: Optional[np.ndarray] = None  # restrict Tier-B to a region (covert attack)
    # model-based Δ̂ for non-sampling-friendly controllers (memory scheduler §13):
    # no Leader-F sets; r̄_F replaced by a model estimate -> weakens Prop 1.
    model_based: bool = False
    model_q0: float = 0.5
    model_bias: float = 0.0


class Bouncer:
    def __init__(self, cfg: BouncerConfig, seed: int = 0):
        self.cfg = cfg
        self.tier_a = TierA(cfg.tier_a, seed=seed + 1)
        self.dueling = SetDueling(cfg.set_dueling, seed=seed + 2)
        K = cfg.tau + cfg.gamma_detect / 2.0
        self.tierb_cusum = LowerCusum(K=K, H=cfg.tierb_H)
        gate_cfg = cfg.gate
        gate_cfg.tau = cfg.tau
        self.gate = GateFSM(gate_cfg)
        self.K = K
        self.telemetry = []

    def fit_reference(self, X_val, conf_val, a_val, r_val):
        self.tier_a.fit_reference(X_val, conf_val, a_val, r_val)

    # ------------------------------------------------------------------
    def _tierb_delta(self, rC_per_set, rF_per_set, full_duty: bool) -> tuple:
        """Compute Δ̂ from the secret dueling pools. In background duty only a
        subset of leaders is averaged (higher σ_Δ); full duty uses all."""
        d = self.dueling
        leaderC = d.leaderC
        leaderF = d.leaderF
        if self.cfg.region is not None:
            leaderC = np.intersect1d(leaderC, self.cfg.region)
            leaderF = np.intersect1d(leaderF, self.cfg.region)
        if not full_duty:
            leaderC = leaderC[: self.cfg.n_L_background]
            leaderF = leaderF[: self.cfg.n_F_background]
        if len(leaderC) == 0:
            return 0.0, 0.0, 0.0
        rbar_L = float(np.mean(rC_per_set[leaderC]))
        if self.cfg.model_based:
            # no secret Leader-F: estimate fallback reward from a model (with bias)
            rbar_F = self.cfg.model_q0 + self.cfg.model_bias
        else:
            if len(leaderF) == 0:
                return 0.0, rbar_L, 0.0
            rbar_F = float(np.mean(rF_per_set[leaderF]))
        return rbar_L - rbar_F, rbar_L, rbar_F

    # ------------------------------------------------------------------
    def step(self, obs: dict) -> dict:
        """Advance one window. obs keys:
        rC_per_set, rF_per_set, feat_win, conf_win, a_win, r_win, delta_true.
        Returns telemetry dict including the gate state and whether C is active.
        """
        cfg = self.cfg
        mode = cfg.detector_mode
        delta_true = obs.get("delta_true", None)

        # --- Tier-A ---
        escalate, ascores = self.tier_a.step_window(
            obs["feat_win"], obs["conf_win"], obs["a_win"], obs["r_win"])

        # --- decide duty & compute Δ̂ ---
        full_duty = self.gate.state in (Gate.SUSPECT, Gate.PROBING)
        delta_hat, rbar_L, rbar_F = self._tierb_delta(
            obs["rC_per_set"], obs["rF_per_set"], full_duty)

        # --- mode-specific gating signals ---
        if mode == "full":
            tierb_fired = self.tierb_cusum.update(delta_hat)
            tier_a_esc = escalate
            tier_a_clr = not escalate
            # background Tier-B can gate directly from TRUSTED (mimicry path);
            # forced by treating tierb_fired as a SUSPECT->... and TRUSTED->GATED.
            self._step_full(tier_a_esc, tier_a_clr, tierb_fired, delta_hat)
        elif mode == "s_in_only":
            # only S_in CUSUM; gates directly (no competence confirmer)
            fired = ascores.get("fired_in", False)
            self._step_direct(fired)
        elif mode == "oracle":
            fired = (delta_true is not None) and (delta_true < cfg.tau)
            self._step_direct(fired)
        elif mode == "no_auditor":
            self.gate.state = Gate.TRUSTED
            self.gate.history.append(Gate.TRUSTED)
        elif mode == "always_fb":
            self.gate.state = Gate.GATED
            self.gate.history.append(Gate.GATED)
        else:
            raise ValueError(mode)

        # NOTE: the secret reseed is deliberately NOT called here. One assignment
        # must govern the adversary's view, the Delta-hat estimate, AND the deployed
        # routing for the *same* window; reseeding here would advance the assignment
        # between estimation and deployment (a counterfactual estimate). The episode
        # runner (simulate.run_episode) reseeds at window close, after deployment.
        tel = {
            "state": self.gate.state,
            "C_active": self.gate.C_active_everywhere,
            "probing": self.gate.probing,
            "delta_hat": delta_hat,
            "rbar_L": rbar_L, "rbar_F": rbar_F,
            "delta_true": delta_true,
            "escalate": escalate,
            "tierb_C": self.tierb_cusum.C,
            **{k: ascores[k] for k in ("S_in", "S_dec", "S_res")},
        }
        self.telemetry.append(tel)
        return tel

    # ------------------------------------------------------------------
    def _step_full(self, tier_a_esc, tier_a_clr, tierb_fired, delta_hat):
        """Full two-tier FSM step, with background Tier-B able to gate from
        TRUSTED (closes the pure-mimicry gap)."""
        g = self.gate
        if g.state == Gate.TRUSTED and tierb_fired:
            # background competence drop detected even without Tier-A escalation
            g.state = Gate.GATED
            g._dwell_count = 0
            g.history.append(g.state)
            return
        g.step(tier_a_esc, tier_a_clr, tierb_fired, delta_hat)

    def _step_direct(self, fired: bool):
        """Single-signal gating with dwell/probe, for baselines."""
        g = self.gate
        c = g.cfg
        s = g.state
        if s in (Gate.TRUSTED, Gate.SUSPECT):
            if fired:
                g.state = Gate.GATED
                g._dwell_count = 0
        elif s == Gate.GATED:
            g._dwell_count += 1
            if g._dwell_count >= g.dwell_target:
                g.state = Gate.PROBING
                g._reprobe_count = 0
        elif s == Gate.PROBING:
            if not fired:
                g._reprobe_count += 1
                if g._reprobe_count >= c.T_reprobe:
                    g.state = Gate.TRUSTED
            else:
                g.state = Gate.GATED
                g._dwell_count = 0
        g.history.append(g.state)
