"""Three mechanism upgrades requested by the MLForSys adversarial review.

1. Traffic-stratified leaders repair the Zipf/correlated-shift failure by
   sampling both policy arms inside activity strata and aggregating strata by
   follower request mass.
2. Adaptive audit allocation normally uses two leaders per arm and expands to
   eight when the lower-CUSUM evidence becomes suspicious.
3. The stateful warm-up experiment supplies reset, fixed, and shadow-state
   contrasts; this script folds its slow-warmup cell into the joint figure.

The first two studies reuse paired per-set potential outcomes from the trained
cache replay.  Potential outcomes are available because this is a simulator;
they are used to audit the online rule, never as detector input.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np

from bouncer.cusum import LowerCusum
from experiments import workshop_common as C
from experiments.exp_trained_characterization import (
    N_SEEDS,
    SWEEP_SHIFT,
    SWEEP_WINDOWS,
    fit_model,
    run_mode,
)
from experiments.exp_trained_controller import Config, LogisticInsertionPolicy


ROOT = Path(__file__).resolve().parents[1]
TRAFFIC_SEVERITY = 0.125
ZIPF_EXPONENT = 1.2
HOT_STRATUM_SIZE = 8
HOT_LEADERS_PER_ARM = 1
ADAPTIVE_SEVERITIES = (0.0, 0.375, 0.5, 1.0)
BASE_LEADERS = 2
MAX_LEADERS = 8
ESCALATE_SCORE = 0.03
ESCALATE_GAP = 0.04
SHRINK_STABLE_WINDOWS = 4


def potential_outcomes(cfg: Config, model: LogisticInsertionPolicy, *,
                       severity: float, shift_order: np.ndarray | None = None):
    learned = run_mode(
        cfg, model, "learned", severity=severity, shift_order=shift_order
    )
    fallback = run_mode(
        cfg, model, "fallback", severity=severity, shift_order=shift_order
    )
    return learned, fallback


def _arrays(learned, fallback, seed_index: int) -> Tuple[np.ndarray, np.ndarray]:
    lr = np.asarray(learned[seed_index]["per_set_hit_rate"], dtype=float)
    fr = np.asarray(fallback[seed_index]["per_set_hit_rate"], dtype=float)
    return lr, fr


def uniform_partition(cfg: Config, seed: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    perm = np.random.default_rng(seed).permutation(cfg.n_sets)
    l = np.sort(perm[:cfg.n_learned_leaders])
    f = np.sort(perm[cfg.n_learned_leaders:
                     cfg.n_learned_leaders + cfg.n_fallback_leaders])
    followers = np.setdiff1d(np.arange(cfg.n_sets), np.concatenate([l, f]))
    return l, f, followers


def stratified_partition(cfg: Config, seed: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Draw both policy arms inside activity-defined hot/cold strata.

    The strata are defined before the semantic shift from request rank.  One
    leader per arm is drawn from the hottest eighth, leaving six of those sets
    in the follower pool; seven per arm come from the remaining sets.
    """
    rng = np.random.default_rng(seed)
    hot = rng.permutation(np.arange(HOT_STRATUM_SIZE))
    cold = rng.permutation(np.arange(HOT_STRATUM_SIZE, cfg.n_sets))
    cold_per_arm = cfg.n_learned_leaders - HOT_LEADERS_PER_ARM
    l = np.concatenate([
        hot[:HOT_LEADERS_PER_ARM],
        cold[:cold_per_arm],
    ])
    f = np.concatenate([
        hot[HOT_LEADERS_PER_ARM:2 * HOT_LEADERS_PER_ARM],
        cold[cold_per_arm:2 * cold_per_arm],
    ])
    l, f = np.sort(l), np.sort(f)
    followers = np.setdiff1d(np.arange(cfg.n_sets), np.concatenate([l, f]))
    return l, f, followers


def _stratified_delta(lr: np.ndarray, fr: np.ndarray, w: int,
                      l: np.ndarray, f: np.ndarray, followers: np.ndarray,
                      weights: np.ndarray) -> float:
    total = float(np.sum(weights[followers]))
    delta = 0.0
    for stratum in (
        np.arange(HOT_STRATUM_SIZE),
        np.arange(HOT_STRATUM_SIZE, weights.size),
    ):
        follower_s = np.intersect1d(followers, stratum)
        l_s = np.intersect1d(l, stratum)
        f_s = np.intersect1d(f, stratum)
        if follower_s.size == 0:
            continue
        if l_s.size == 0 or f_s.size == 0:
            raise AssertionError("each represented follower stratum needs both policy arms")
        mass = float(np.sum(weights[follower_s]) / total)
        delta += mass * (
            float(np.mean(lr[w, l_s])) - float(np.mean(fr[w, f_s]))
        )
    return delta


def run_fixed_partition_gate(cfg: Config, lr: np.ndarray, fr: np.ndarray,
                             l: np.ndarray, f: np.ndarray,
                             followers: np.ndarray, weights: np.ndarray, *,
                             stratified: bool) -> Dict[str, object]:
    detector = LowerCusum(K=cfg.cusum_K, H=cfg.cusum_H, auto_reset=False)
    gate_open = True
    gate_window = None
    dhat, target, deployed = [], [], []
    norm = float(np.sum(weights))
    follower_norm = float(np.sum(weights[followers]))
    for w in range(cfg.windows):
        if stratified:
            d = _stratified_delta(lr, fr, w, l, f, followers, weights)
        else:
            d = float(np.mean(lr[w, l]) - np.mean(fr[w, f]))
        dhat.append(d)
        target.append(float(np.sum(
            (lr[w, followers] - fr[w, followers]) * weights[followers]
        ) / follower_norm))

        rates = np.empty(cfg.n_sets, dtype=float)
        rates[l] = lr[w, l]
        rates[f] = fr[w, f]
        rates[followers] = lr[w, followers] if gate_open else fr[w, followers]
        deployed.append(float(np.sum(rates * weights) / norm))

        if gate_open and detector.update(d):
            gate_open = False
            gate_window = w + 1
    return {
        "delta_hat": dhat,
        "follower_target": target,
        "deployed_hit_rate": deployed,
        "gate_window": gate_window,
        "learned_leaders": l.tolist(),
        "fallback_leaders": f.tolist(),
        "followers": followers.tolist(),
    }


def summarize_traffic_strategy(cfg: Config, runs: Sequence[Dict[str, object]],
                               weights: np.ndarray) -> Dict[str, object]:
    post = slice(cfg.shift_window + 8, cfg.windows)
    target = np.asarray([r["follower_target"] for r in runs], dtype=float)
    estimate = np.asarray([r["delta_hat"] for r in runs], dtype=float)
    deployed = np.asarray([r["deployed_hit_rate"] for r in runs], dtype=float)
    target_seed = np.mean(target[:, post], axis=1)
    estimate_seed = np.mean(estimate[:, post], axis=1)
    harmful = target_seed < 0.0
    gates = np.asarray([
        np.nan if r["gate_window"] is None else float(r["gate_window"])
        for r in runs
    ])
    detected = harmful & np.isfinite(gates) & (gates >= cfg.shift_window)
    shifted_follower_mass = []
    for r in runs:
        followers = np.asarray(r["followers"], dtype=int)
        hot_followers = followers[followers < HOT_STRATUM_SIZE]
        shifted_follower_mass.append(
            float(np.sum(weights[hot_followers]) / np.sum(weights[followers]))
        )
    return {
        "weighted_follower_gap_post_mean": float(np.mean(target_seed)),
        "leader_estimate_post_mean": float(np.mean(estimate_seed)),
        "estimator_bias_post_mean": float(np.mean(estimate_seed - target_seed)),
        "estimator_rmse_post": float(np.sqrt(np.mean((estimate_seed - target_seed) ** 2))),
        "sign_agreement_seeds": int(np.sum(np.sign(estimate_seed) == np.sign(target_seed))),
        "harmful_seeds": int(np.sum(harmful)),
        "detected_harmful_seeds": int(np.sum(detected)),
        "post_deployed_hit_rate_mean": float(np.mean(deployed[:, post])),
        "shifted_request_weight_within_followers_mean": float(
            np.mean(shifted_follower_mass)
        ),
        "gate_windows": gates.tolist(),
    }


def traffic_stratified_repair(cfg: Config, model: LogisticInsertionPolicy) -> Dict[str, object]:
    weights = 1.0 / np.arange(1, cfg.n_sets + 1, dtype=float) ** ZIPF_EXPONENT
    weights /= np.sum(weights)
    order = np.arange(cfg.n_sets, dtype=int)
    learned, fallback = potential_outcomes(
        cfg, model, severity=TRAFFIC_SEVERITY, shift_order=order
    )
    uniform_runs: List[Dict[str, object]] = []
    stratified_runs: List[Dict[str, object]] = []
    for i in range(N_SEEDS):
        seed = 10_000 + i
        lr, fr = _arrays(learned, fallback, i)
        uniform_runs.append(run_fixed_partition_gate(
            cfg, lr, fr, *uniform_partition(cfg, seed), weights,
            stratified=False,
        ))
        stratified_runs.append(run_fixed_partition_gate(
            cfg, lr, fr, *stratified_partition(cfg, seed), weights,
            stratified=True,
        ))
    return {
        "zipf_exponent": ZIPF_EXPONENT,
        "shifted_set_fraction": TRAFFIC_SEVERITY,
        "shifted_request_weight": float(np.sum(weights[:HOT_STRATUM_SIZE])),
        "leader_budget_per_arm": cfg.n_learned_leaders,
        "hot_stratum_sets": HOT_STRATUM_SIZE,
        "hot_leaders_per_arm": HOT_LEADERS_PER_ARM,
        "uniform": summarize_traffic_strategy(cfg, uniform_runs, weights),
        "traffic_stratified": summarize_traffic_strategy(cfg, stratified_runs, weights),
        "scope": (
            "Activity strata are known before the shift. Stratum aggregation uses follower "
            "request mass; it repairs this two-stratum correlated-shift construction, not "
            "arbitrary within-stratum heterogeneity."
        ),
    }


def nested_candidates(cfg: Config, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    perm = np.random.default_rng(seed).permutation(cfg.n_sets)
    l = perm[:MAX_LEADERS]
    f = perm[MAX_LEADERS:2 * MAX_LEADERS]
    return l, f


def run_adaptive_gate(cfg: Config, lr: np.ndarray, fr: np.ndarray, seed: int, *,
                      adaptive: bool) -> Dict[str, object]:
    cand_l, cand_f = nested_candidates(cfg, seed)
    n = BASE_LEADERS if adaptive else MAX_LEADERS
    detector = LowerCusum(K=cfg.cusum_K, H=cfg.cusum_H, auto_reset=False)
    gate_open = True
    gate_window = None
    stable = 0
    deployed, dhat, n_trace = [], [], []
    for w in range(cfg.windows):
        if adaptive and n == BASE_LEADERS:
            # Rotate the small probe across the preselected candidate cohort.
            # This preserves a 2+2 instantaneous audit budget while preventing
            # a weak shift from hiding indefinitely outside the initial four
            # leaders.  The trace-replay controller is stateless; the separate
            # warm-up experiment measures why stateful rotation needs shadowing.
            start = (w * BASE_LEADERS) % MAX_LEADERS
            idx = (start + np.arange(BASE_LEADERS)) % MAX_LEADERS
            l, f = cand_l[idx], cand_f[idx]
        else:
            l, f = cand_l[:n], cand_f[:n]
        followers = np.setdiff1d(np.arange(cfg.n_sets), np.concatenate([l, f]))
        d = float(np.mean(lr[w, l]) - np.mean(fr[w, f]))
        dhat.append(d)
        n_trace.append(n)

        rates = np.empty(cfg.n_sets, dtype=float)
        rates[l] = lr[w, l]
        rates[f] = fr[w, f]
        rates[followers] = lr[w, followers] if gate_open else fr[w, followers]
        deployed.append(float(np.mean(rates)))

        alarm = gate_open and detector.update(d)
        if alarm:
            gate_open = False
            gate_window = w + 1
        if adaptive and gate_open:
            if n == BASE_LEADERS and (
                detector.C >= ESCALATE_SCORE or d < ESCALATE_GAP
            ):
                n = MAX_LEADERS
                stable = 0
            elif n == MAX_LEADERS:
                if detector.C == 0.0 and d >= ESCALATE_GAP:
                    stable += 1
                    if stable >= SHRINK_STABLE_WINDOWS:
                        n = BASE_LEADERS
                        stable = 0
                else:
                    stable = 0
    return {
        "gate_window": gate_window,
        "delta_hat": dhat,
        "deployed_hit_rate": deployed,
        "leaders_per_arm": n_trace,
    }


def summarize_allocation(cfg: Config, learned, fallback, *, adaptive: bool,
                         severity: float) -> Dict[str, object]:
    runs = []
    full_gap = []
    for i in range(N_SEEDS):
        lr, fr = _arrays(learned, fallback, i)
        runs.append(run_adaptive_gate(cfg, lr, fr, 10_000 + i, adaptive=adaptive))
        full_gap.append(np.mean(lr - fr, axis=1))
    gap = np.asarray(full_gap)
    post = slice(cfg.shift_window + 8, cfg.windows)
    gap_seed = np.mean(gap[:, post], axis=1)
    below = gap_seed < cfg.cusum_K
    gates = np.asarray([
        np.nan if r["gate_window"] is None else float(r["gate_window"])
        for r in runs
    ])
    detected = below & np.isfinite(gates) & (gates >= cfg.shift_window)
    delays = gates[detected] - cfg.shift_window
    ntrace = np.asarray([r["leaders_per_arm"] for r in runs], dtype=float)
    deployed = np.asarray([r["deployed_hit_rate"] for r in runs], dtype=float)
    return {
        "severity": severity,
        "below_reference_seeds": int(np.sum(below)),
        "detected_below_reference_seeds": int(np.sum(detected)),
        "false_gate_seeds": int(np.sum(np.isfinite(gates) & ~below)),
        "delay_from_shift_mean": float(np.mean(delays)) if delays.size else None,
        "mean_leaders_per_arm_all": float(np.mean(ntrace)),
        "mean_leaders_per_arm_pre": float(np.mean(ntrace[:, :cfg.shift_window])),
        "mean_leaders_per_arm_post": float(np.mean(ntrace[:, cfg.shift_window:])),
        "mean_dedicated_set_fraction_all": float(2.0 * np.mean(ntrace) / cfg.n_sets),
        "post_deployed_hit_rate_mean": float(np.mean(deployed[:, post])),
        "gate_windows": gates.tolist(),
    }


def adaptive_allocation(cfg: Config, model: LogisticInsertionPolicy) -> Dict[str, object]:
    cells = []
    for severity in ADAPTIVE_SEVERITIES:
        learned, fallback = potential_outcomes(cfg, model, severity=severity)
        cells.append({
            "severity": severity,
            "fixed_8_per_arm": summarize_allocation(
                cfg, learned, fallback, adaptive=False, severity=severity
            ),
            "adaptive_2_to_8_per_arm": summarize_allocation(
                cfg, learned, fallback, adaptive=True, severity=severity
            ),
        })
    return {
        "base_leaders_per_arm": BASE_LEADERS,
        "maximum_leaders_per_arm": MAX_LEADERS,
        "base_probe_rotation_period_windows": MAX_LEADERS // BASE_LEADERS,
        "escalate_cusum_score": ESCALATE_SCORE,
        "escalate_if_gap_below": ESCALATE_GAP,
        "shrink_after_stable_windows": SHRINK_STABLE_WINDOWS,
        "cells": cells,
        "scope": (
            "Nested candidate leaders are safe in this stateless, rotating-tag trace. "
            "The separate stateful experiment tests the reset problem and shadow repair."
        ),
    }


def load_stateful_result() -> Dict[str, object]:
    path = ROOT / "results" / "warmup_predictor.json"
    if not path.exists():
        raise FileNotFoundError("run experiments/exp_warmup_predictor.py first")
    data = json.loads(path.read_text())
    slow = data["multiplicative_cells"][-1]
    return {
        "warmup_timescale_windows": slow["warmup_windows"],
        "true_warm_gap": data["gap"],
        "reset_on_rotation_gap": slow["reseeded_dhat"],
        "fixed_leader_gap": slow["fixed_dhat"],
        "shadow_state_gap": slow["shadow_reseeded_dhat"],
        "shadow_metadata_model": data["shadow_metadata_model"],
        "scope": (
            "Controlled multiplicative warm-up reward with counter-like shadow state; "
            "not a full stateful cache-content replica."
        ),
    }


def make_figure(traffic: Dict[str, object], allocation: Dict[str, object],
                stateful: Dict[str, object]) -> None:
    C.setstyle()
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.45))

    ax = axes[0]
    labels = ["follower\ntarget", "uniform\nleaders", "stratified\nleaders"]
    values = [
        traffic["uniform"]["weighted_follower_gap_post_mean"],
        traffic["uniform"]["leader_estimate_post_mean"],
        traffic["traffic_stratified"]["leader_estimate_post_mean"],
    ]
    ax.bar(np.arange(3), values, color=[
        C.PALETTE["oracle"], C.PALETTE["unguarded"], C.PALETTE["bouncer"]
    ])
    ax.axhline(0, color="#555", lw=0.7)
    ax.set_xticks(np.arange(3), labels, fontsize=6.2)
    ax.set_ylabel("post-shift hit-rate gap")
    ax.set_title("(a) Traffic strata repair bias")
    ax.text(0.03, 0.03,
            f"detect: {traffic['uniform']['detected_harmful_seeds']}/12 -> "
            f"{traffic['traffic_stratified']['detected_harmful_seeds']}/12",
            transform=ax.transAxes, fontsize=6.5)

    ax = axes[1]
    sev = np.asarray([c["severity"] for c in allocation["cells"]])
    fixed = np.asarray([
        c["fixed_8_per_arm"]["detected_below_reference_seeds"] / N_SEEDS
        for c in allocation["cells"]
    ])
    adaptive = np.asarray([
        c["adaptive_2_to_8_per_arm"]["detected_below_reference_seeds"] / N_SEEDS
        for c in allocation["cells"]
    ])
    leaders = np.asarray([
        c["adaptive_2_to_8_per_arm"]["mean_leaders_per_arm_all"]
        for c in allocation["cells"]
    ])
    ax.plot(sev, fixed, "s--", color=C.PALETTE["fallback"], label="fixed 8/arm")
    ax.plot(sev, adaptive, "o-", color=C.PALETTE["bouncer"], label="adaptive 2-8/arm")
    ax.set(xlabel="shifted set fraction", ylabel="detection fraction",
           ylim=(-0.05, 1.05), title="(b) Audit budget follows evidence")
    ax2 = ax.twinx()
    ax2.plot(sev, leaders, "^-", color=C.PALETTE["accent"], alpha=0.7,
             label="adaptive leaders/arm")
    ax2.set_ylabel("mean leaders/arm", color=C.PALETTE["accent"], fontsize=7)
    ax2.set_ylim(0, 9)
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [x.get_label() for x in lines], fontsize=5.6,
              loc="center right")

    ax = axes[2]
    vals = [
        stateful["reset_on_rotation_gap"],
        stateful["fixed_leader_gap"],
        stateful["shadow_state_gap"],
    ]
    ax.bar(np.arange(3), vals, color=[
        C.PALETTE["unguarded"], C.PALETTE["fallback"], C.PALETTE["bouncer"]
    ])
    ax.axhline(stateful["true_warm_gap"], color="#333", ls=":", lw=0.9,
               label="warm gap")
    ax.set_xticks(np.arange(3), ["reset", "fixed", "shadow"], fontsize=6.2)
    ax.set_ylabel(r"measured $\hat\Delta$")
    ax.set_ylim(0, 0.34)
    ax.set_title("(c) Shadow state survives rotation")
    ax.legend(fontsize=6, loc="upper left")
    C.savefig(fig, "trained_upgrades.pdf")


def main() -> None:
    cfg = replace(Config(), windows=SWEEP_WINDOWS, shift_window=SWEEP_SHIFT)
    model = fit_model(cfg)
    traffic = traffic_stratified_repair(cfg, model)
    allocation = adaptive_allocation(cfg, model)
    stateful = load_stateful_result()
    make_figure(traffic, allocation, stateful)

    result = {
        "scope": (
            "Controlled synthetic-family mechanism upgrades; traffic skew, adaptive "
            "leader budgeting, and counter-like state are isolated rather than presented "
            "as application-level validation."
        ),
        "traffic_stratified_sampling": traffic,
        "adaptive_audit_allocation": allocation,
        "state_preserving_shadow_metadata": stateful,
    }
    C.save_json("trained_upgrades.json", result)

    t0, t1 = traffic["uniform"], traffic["traffic_stratified"]
    print(
        f"  traffic repair: estimate {t0['leader_estimate_post_mean']:+.4f} -> "
        f"{t1['leader_estimate_post_mean']:+.4f}; detect "
        f"{t0['detected_harmful_seeds']}/12 -> {t1['detected_harmful_seeds']}/12"
    )
    for cell in allocation["cells"]:
        a = cell["adaptive_2_to_8_per_arm"]
        f = cell["fixed_8_per_arm"]
        print(
            f"  adaptive p={cell['severity']:.3f}: detect "
            f"{a['detected_below_reference_seeds']}/12 vs fixed "
            f"{f['detected_below_reference_seeds']}/12; "
            f"leaders/arm={a['mean_leaders_per_arm_all']:.2f}"
        )
    print(
        f"  state repair: reset={stateful['reset_on_rotation_gap']:.3f}, "
        f"fixed={stateful['fixed_leader_gap']:.3f}, "
        f"shadow={stateful['shadow_state_gap']:.3f}"
    )

    assert t0["leader_estimate_post_mean"] > 0.0
    assert t1["leader_estimate_post_mean"] < 0.0
    assert t1["detected_harmful_seeds"] > t0["detected_harmful_seeds"]
    assert stateful["shadow_state_gap"] >= 0.9 * stateful["true_warm_gap"]


if __name__ == "__main__":
    main()
