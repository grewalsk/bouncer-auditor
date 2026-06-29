"""
gate_fsm.py — The trust-gate state machine (§3).

States: TRUSTED -> SUSPECT -> GATED -> PROBING.

TRUSTED : C active everywhere. Tier-A on; Tier-B on slow background duty cycle.
            any Tier-A CUSUM fires            -> SUSPECT
SUSPECT : C still active. Tier-B duty cycle UP (more dueling sets / shorter W).
            Tier-B Δ̂ CUSUM fires (Δ̂<τ)       -> GATED
            Tier-A clears for T_clear         -> TRUSTED
GATED   : pi0 active everywhere. Online learning FROZEN. Optional throttle.
            after dwell T_dwell               -> PROBING
PROBING : C re-enabled on a small audited region; Tier-B measures Δ̂ there.
            Δ̂ >= τ + Δ_hys for T_reprobe      -> TRUSTED
            Δ̂ < τ                             -> GATED  (exp backoff on T_dwell)

Hysteresis (enter at τ, leave at τ+Δ_hys) + minimum dwell prevent thrash.
PROBING makes re-trust *measured*, not timed — defeating an attacker who waits
out a fixed cooldown.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Gate(Enum):
    TRUSTED = 0
    SUSPECT = 1
    GATED = 2
    PROBING = 3


@dataclass
class GateConfig:
    tau: float = 0.05
    delta_hys: float = 0.05         # extra margin required to leave PROBING
    T_clear: int = 5                # SUSPECT windows of clean Tier-A -> TRUSTED
    T_dwell: int = 6                # GATED windows before PROBING
    T_dwell_max: int = 24           # cap on exponential backoff
    T_reprobe: int = 4              # PROBING windows of Δ̂>=τ+hys -> TRUSTED
    backoff_mult: float = 2.0


class GateFSM:
    def __init__(self, cfg: GateConfig):
        self.cfg = cfg
        self.state = Gate.TRUSTED
        self.dwell_target = cfg.T_dwell
        self._clear_count = 0
        self._dwell_count = 0
        self._reprobe_count = 0
        self.history = []  # (state) per window for plotting

    @property
    def C_active_everywhere(self) -> bool:
        return self.state in (Gate.TRUSTED, Gate.SUSPECT)

    @property
    def probing(self) -> bool:
        return self.state == Gate.PROBING

    def step(self, tier_a_escalate: bool, tier_a_clear: bool,
             tierb_delta_fired: bool, delta_hat: float) -> Gate:
        """Advance the FSM one window. Inputs:
        tier_a_escalate : any Tier-A CUSUM fired this window
        tier_a_clear    : Tier-A all quiet this window
        tierb_delta_fired: Tier-B lower-CUSUM on Δ̂ fired (Δ̂ below τ-region)
        delta_hat       : current competence estimate (for PROBING re-trust)
        """
        c = self.cfg
        s = self.state

        if s == Gate.TRUSTED:
            if tier_a_escalate:
                self.state = Gate.SUSPECT
                self._clear_count = 0

        elif s == Gate.SUSPECT:
            if tierb_delta_fired:
                self.state = Gate.GATED
                self._dwell_count = 0
            elif tier_a_clear:
                self._clear_count += 1
                if self._clear_count >= c.T_clear:
                    self.state = Gate.TRUSTED
            else:
                self._clear_count = 0

        elif s == Gate.GATED:
            self._dwell_count += 1
            if self._dwell_count >= self.dwell_target:
                self.state = Gate.PROBING
                self._reprobe_count = 0

        elif s == Gate.PROBING:
            if delta_hat >= c.tau + c.delta_hys:
                self._reprobe_count += 1
                if self._reprobe_count >= c.T_reprobe:
                    self.state = Gate.TRUSTED
                    self.dwell_target = c.T_dwell  # reset backoff on success
            elif delta_hat < c.tau:
                # re-trust failed; back off and re-gate
                self.state = Gate.GATED
                self._dwell_count = 0
                self.dwell_target = min(int(self.dwell_target * c.backoff_mult), c.T_dwell_max)
            else:
                self._reprobe_count = 0  # in the hysteresis band: keep probing

        self.history.append(self.state)
        return self.state
