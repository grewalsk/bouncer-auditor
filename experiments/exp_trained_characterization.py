"""Characterize the trained-controller audit beyond the maximal-shift demo.

This experiment keeps the model, cache, leader budget, CUSUM parameters, and
exact PC marginals fixed while varying how much of the cache experiences the
PC/reuse semantic reversal.  It also evaluates gradual drift, two PSEL counter
widths as architectural references, adjacent-window temporal A/B estimation,
three controlled cache/reuse configurations, and a deliberately violated
representative-sampling premise under Zipf traffic.

The outputs are synthetic operating characteristics, not application-level
generalization claims.  All randomness remains inside the same trace-replay
family and is described as such in the JSON and paper.
"""
from __future__ import annotations

from dataclasses import replace
from math import comb
from typing import Dict, Iterable, List

import matplotlib.pyplot as plt
import numpy as np

from bouncer.cusum import LowerCusum, detection_delay_approx
from experiments import workshop_common as C
from experiments.exp_trained_controller import (
    Config,
    LogisticInsertionPolicy,
    make_training_data,
    simulate,
)


SEVERITIES = np.linspace(0.0, 1.0, 9)
N_SEEDS = 12
SWEEP_WINDOWS = 80
SWEEP_SHIFT = 20
RAMP_WINDOWS = 16


def fit_model(cfg: Config) -> LogisticInsertionPolicy:
    pc_tr, y_tr, _, _ = make_training_data(cfg)
    model = LogisticInsertionPolicy()
    model.fit(pc_tr, y_tr)
    return model


def run_mode(cfg: Config, model: LogisticInsertionPolicy, mode: str, *,
             severity: float, ramp_windows: int = 0, psel_bits: int = 10,
             shift_order: np.ndarray | None = None) -> List[Dict[str, object]]:
    return [
        simulate(
            cfg,
            model,
            10_000 + i,
            mode,
            post_shift_severity=severity,
            ramp_windows=ramp_windows,
            psel_bits=psel_bits,
            shift_order=shift_order,
        )
        for i in range(N_SEEDS)
    ]


def _curves(runs: List[Dict[str, object]], key: str = "hit_rate") -> np.ndarray:
    return np.asarray([r[key] for r in runs], dtype=float)


def summarize_protected(cfg: Config, learned: List[Dict[str, object]],
                        fallback: List[Dict[str, object]],
                        protected: List[Dict[str, object]], *,
                        ramp_windows: int = 0) -> Dict[str, object]:
    lc = _curves(learned)
    fc = _curves(fallback)
    pc = _curves(protected)
    gap = lc - fc
    gates = np.asarray([
        np.nan if r["gate_window"] is None else float(r["gate_window"])
        for r in protected
    ])

    steady_start = min(
        cfg.windows - 1,
        cfg.shift_window + max(8, ramp_windows + 4),
    )
    steady = slice(steady_start, cfg.windows)
    pre = slice(5, cfg.shift_window)
    pre_gap_by_seed = np.mean(gap[:, pre], axis=1)
    steady_gap_by_seed = np.mean(gap[:, steady], axis=1)
    harmful = steady_gap_by_seed < 0.0
    below_reference = steady_gap_by_seed < cfg.cusum_K
    target_starts = np.full(N_SEEDS, np.nan)
    for i in np.flatnonzero(below_reference | (pre_gap_by_seed < cfg.cusum_K)):
        search_start = 0 if pre_gap_by_seed[i] < cfg.cusum_K else cfg.shift_window
        if ramp_windows == 0 and search_start == cfg.shift_window:
            target_starts[i] = float(cfg.shift_window)
            continue
        # A three-window prospective mean avoids defining a gradual crossing
        # from one access-order fluctuation.  K is the detector's reference;
        # Delta<0 (learned worse than fallback) is reported separately.
        for w in range(search_start, cfg.windows - 2):
            if float(np.mean(gap[i, w:w + 3])) < cfg.cusum_K:
                target_starts[i] = float(w)
                break

    detected = below_reference & np.isfinite(gates) & (gates >= target_starts)
    detected_harmful = harmful & np.isfinite(gates) & (gates >= target_starts)
    false_gate = np.isfinite(gates) & (
        ~np.isfinite(target_starts) | (gates < target_starts)
    )
    delays = gates[detected] - target_starts[detected]
    oracle = np.maximum(lc, fc)

    # The simulator exposes shadow per-set outcomes for diagnosis only.
    dhat = _curves(protected, "delta_hat")
    lset = np.asarray([r["per_set_hit_rate"] for r in learned], dtype=float)
    fset = np.asarray([r["per_set_hit_rate"] for r in fallback], dtype=float)
    follower_delta = np.zeros_like(dhat)
    for i, r in enumerate(protected):
        followers = np.asarray(r["followers"], dtype=int)
        follower_delta[i] = np.mean(
            lset[i, :, followers] - fset[i, :, followers], axis=0
        )
    bias = dhat - follower_delta

    return {
        "true_gap_steady_mean": float(np.mean(gap[:, steady])),
        "true_gap_steady_std_across_seeds": float(
            np.std(np.mean(gap[:, steady], axis=1), ddof=1)
        ),
        "true_gap_pre_mean": float(np.mean(pre_gap_by_seed)),
        "harmful_seeds": int(np.sum(harmful)),
        "detected_harmful_seeds": int(np.sum(detected_harmful)),
        "below_cusum_reference_seeds": int(np.sum(below_reference)),
        "detected_below_reference_seeds": int(np.sum(detected)),
        "detection_fraction": (
            float(np.sum(detected) / np.sum(below_reference))
            if np.any(below_reference) else None
        ),
        "false_gate_seeds": int(np.sum(false_gate)),
        "delay_from_reference_crossing_mean": (
            float(np.mean(delays)) if delays.size else None
        ),
        "delay_from_reference_crossing_min": (
            int(np.min(delays)) if delays.size else None
        ),
        "delay_from_reference_crossing_max": (
            int(np.max(delays)) if delays.size else None
        ),
        "post_learned_mean": float(np.mean(lc[:, steady])),
        "post_fallback_mean": float(np.mean(fc[:, steady])),
        "post_protected_mean": float(np.mean(pc[:, steady])),
        "post_oracle_mean": float(np.mean(oracle[:, steady])),
        "regret_to_window_oracle_mean": float(np.mean(oracle[:, steady] - pc[:, steady])),
        "leader_estimate_steady_mean": float(np.mean(dhat[:, steady])),
        "leader_estimate_steady_std_across_seeds": float(
            np.std(np.mean(dhat[:, steady], axis=1), ddof=1)
        ),
        "estimator_bias_mean": float(np.mean(bias)),
        "estimator_bias_rmse": float(np.sqrt(np.mean(bias ** 2))),
        "gate_windows": gates.tolist(),
        "reference_crossing_windows": target_starts.tolist(),
    }


def run_severity_sweep(cfg: Config, model: LogisticInsertionPolicy):
    cells = []
    saved = {}
    for severity in SEVERITIES:
        learned = run_mode(cfg, model, "learned", severity=float(severity))
        fallback = run_mode(cfg, model, "fallback", severity=float(severity))
        bouncer = run_mode(cfg, model, "bouncer", severity=float(severity))
        cell = summarize_protected(cfg, learned, fallback, bouncer)
        cell["severity"] = float(severity)
        cells.append(cell)
        saved[float(severity)] = (learned, fallback, bouncer)
        dfrac = "n/a" if cell["detection_fraction"] is None else f"{cell['detection_fraction']:.2f}"
        delay = "n/a" if cell["delay_from_reference_crossing_mean"] is None else f"{cell['delay_from_reference_crossing_mean']:.2f}"
        print(
            f"  severity={severity:.3f}: gap={cell['true_gap_steady_mean']:+.4f}, "
            f"harmful={cell['harmful_seeds']}/{N_SEEDS}, detect={dfrac}, "
            f"delay={delay}, false gates={cell['false_gate_seeds']}"
        )
    return cells, saved


def _hypergeom_pmf(N: int, M: int, n: int, x: int) -> float:
    if x < max(0, n - (N - M)) or x > min(n, M):
        return 0.0
    return comb(M, x) * comb(N - M, n - x) / comb(N, n)


def add_hypergeometric_predictions(cfg: Config, cells) -> None:
    """Predict leader-overlap variation under nested set-level reversal.

    If M of N sets are shifted and n learned leaders are drawn without
    replacement, X~Hypergeom(N,M,n).  The fallback's shift response is nearly
    invariant in this controlled trace, so the first-order prediction maps X
    through the learned arm's two endpoint hit rates.  Access-order noise and
    fallback-arm variation are deliberately excluded and remain visible in the
    measured standard deviation.
    """
    learned_clean = float(cells[0]["post_learned_mean"])
    learned_shifted = float(cells[-1]["post_learned_mean"])
    fallback = float(np.mean([c["post_fallback_mean"] for c in cells]))
    N = cfg.n_sets
    n = cfg.n_learned_leaders
    for cell in cells:
        M = int(round(float(cell["severity"]) * N))
        p = M / N
        mean_x = n * p
        var_x = n * p * (1.0 - p) * (N - n) / (N - 1) if N > 1 else 0.0
        predicted_gap = (
            (1.0 - mean_x / n) * learned_clean
            + (mean_x / n) * learned_shifted
            - fallback
        )
        prob_below = 0.0
        for x in range(n + 1):
            gap_x = (
                (1.0 - x / n) * learned_clean
                + (x / n) * learned_shifted
                - fallback
            )
            if gap_x < cfg.cusum_K:
                prob_below += _hypergeom_pmf(N, M, n, x)
        cell["hypergeometric_prediction"] = {
            "population_sets": N,
            "shifted_sets": M,
            "learned_leaders": n,
            "expected_shifted_learned_leaders": mean_x,
            "std_shifted_learned_leaders": float(np.sqrt(var_x)),
            "predicted_leader_gap_mean": predicted_gap,
            "predicted_between_seed_std_from_overlap_only": (
                abs(learned_shifted - learned_clean) * np.sqrt(var_x) / n
            ),
            "probability_one_window_gap_below_K": prob_below,
            "deterministic_delay_heuristic": (
                float(detection_delay_approx(cfg.cusum_K, cfg.cusum_H, predicted_gap))
                if predicted_gap < cfg.cusum_K else None
            ),
            "scope": (
                "First-order finite-population prediction; excludes access-order noise, "
                "fallback-arm variation, CUSUM resets, and overshoot."
            ),
        }


def psel_severity_sweep(cfg: Config, model: LogisticInsertionPolicy, saved):
    out = []
    for severity in SEVERITIES:
        learned, fallback, _ = saved[float(severity)]
        row = {"severity": float(severity)}
        for bits in (8, 10):
            psel = run_mode(
                cfg, model, "psel", severity=float(severity), psel_bits=bits
            )
            row[f"PSEL-{bits}"] = summarize_protected(
                cfg, learned, fallback, psel
            )
        out.append(row)
    return out


def detector_reference(cfg: Config, model: LogisticInsertionPolicy, *,
                       ramp_windows: int, learned, fallback):
    out = {}
    bouncer = run_mode(
        cfg, model, "bouncer", severity=1.0, ramp_windows=ramp_windows
    )
    out["Bouncer"] = summarize_protected(
        cfg, learned, fallback, bouncer, ramp_windows=ramp_windows
    )
    for bits in (8, 10):
        psel = run_mode(
            cfg, model, "psel", severity=1.0,
            ramp_windows=ramp_windows, psel_bits=bits,
        )
        out[f"PSEL-{bits}"] = summarize_protected(
            cfg, learned, fallback, psel, ramp_windows=ramp_windows
        )
    return out


def temporal_ab_diagnostic(learned, fallback) -> Dict[str, float]:
    """Adjacent-window contrast: lower deployment cost requires stronger timing assumptions."""
    lc = _curves(learned)
    fc = _curves(fallback)
    pair_end = np.arange(1, lc.shape[1], 2)
    estimate = lc[:, pair_end - 1] - fc[:, pair_end]
    target = 0.5 * (
        (lc - fc)[:, pair_end - 1] + (lc - fc)[:, pair_end]
    )
    return {
        "estimator_rmse": float(np.sqrt(np.mean((estimate - target) ** 2))),
        "learned_policy_exposure_before_decision": 0.5,
        "windows_per_contrast": 2,
        "note": (
            "This diagnostic compares different windows and therefore targets a temporal "
            "contrast only under cross-window stability; it is not a concurrent causal baseline."
        ),
    }


def family_perturbations(cfg: Config, model: LogisticInsertionPolicy):
    families = {
        "nominal": cfg,
        "tight_4way": replace(cfg, ways=4, hot_lines=4),
        "larger_reuse_set": replace(cfg, ways=8, hot_lines=8),
        "low_pressure_16way": replace(cfg, ways=16, hot_lines=4),
    }
    out = {}
    for name, fcfg in families.items():
        learned = run_mode(fcfg, model, "learned", severity=0.5)
        fallback = run_mode(fcfg, model, "fallback", severity=0.5)
        bouncer = run_mode(fcfg, model, "bouncer", severity=0.5)
        out[name] = summarize_protected(fcfg, learned, fallback, bouncer)
        out[name]["config"] = {
            "ways": fcfg.ways,
            "hot_lines": fcfg.hot_lines,
            "accesses_per_set_window": fcfg.accesses_per_set_window,
        }
    return out


def zipf_sampling_boundary(cfg: Config, model: LogisticInsertionPolicy):
    """Deliberately violate representative sampling with hot-set-correlated shift."""
    exponent = 1.2
    weights = 1.0 / np.arange(1, cfg.n_sets + 1, dtype=float) ** exponent
    weights /= np.sum(weights)
    # Set IDs are activity-ranked; the first 1/8 receive the semantic reversal.
    order = np.arange(cfg.n_sets, dtype=int)
    severity = 0.125
    learned = run_mode(
        cfg, model, "learned", severity=severity, shift_order=order
    )
    fallback = run_mode(
        cfg, model, "fallback", severity=severity, shift_order=order
    )
    lc = np.asarray([r["per_set_hit_rate"] for r in learned], dtype=float)
    fc = np.asarray([r["per_set_hit_rate"] for r in fallback], dtype=float)

    bias_post = []
    target_post = []
    estimate_post = []
    harmful = 0
    detected = 0
    for i, r in enumerate(learned):
        leaders_l = np.asarray(r["learned_leaders"], dtype=int)
        leaders_f = np.asarray(r["fallback_leaders"], dtype=int)
        followers = np.asarray(r["followers"], dtype=int)
        dhat = (
            np.mean(lc[i, :, leaders_l], axis=0)
            - np.mean(fc[i, :, leaders_f], axis=0)
        )
        wf = weights[followers]
        target = np.sum(
            (lc[i, :, followers] - fc[i, :, followers]) * wf[:, None], axis=0
        ) / np.sum(wf)
        post = slice(cfg.shift_window + 8, cfg.windows)
        bias_post.append(float(np.mean(dhat[post] - target[post])))
        target_post.append(float(np.mean(target[post])))
        estimate_post.append(float(np.mean(dhat[post])))
        is_harmful = float(np.mean(target[post])) < 0.0
        harmful += int(is_harmful)
        detector = LowerCusum(K=cfg.cusum_K, H=cfg.cusum_H, auto_reset=False)
        alarm = None
        for w, value in enumerate(dhat):
            if detector.update(float(value)):
                alarm = w + 1
                break
        detected += int(is_harmful and alarm is not None and alarm >= cfg.shift_window)

    return {
        "zipf_exponent": exponent,
        "shifted_set_fraction": severity,
        "shifted_request_weight": float(np.sum(weights[: int(cfg.n_sets * severity)])),
        "harmful_seeds": harmful,
        "detected_harmful_seeds": detected,
        "weighted_follower_gap_post_mean": float(np.mean(target_post)),
        "unweighted_leader_estimate_post_mean": float(np.mean(estimate_post)),
        "estimator_bias_post_mean": float(np.mean(bias_post)),
        "note": (
            "This is a negative-control boundary test: activity-ranked hot sets shift while "
            "leaders remain a uniform set sample and the deployed target is request-weighted. "
            "It intentionally violates representative sampling; failures are expected and "
            "must not be interpreted as detector false negatives under the paper's premises."
        ),
    }


def make_figure(cfg: Config, severity_cells, full_runs, abrupt_refs, gradual_refs):
    C.setstyle()
    learned, fallback, bouncer = full_runs
    x = np.arange(cfg.windows)
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.45),
                             gridspec_kw={"width_ratios": [1.45, 1.05, 0.9]})

    ax = axes[0]
    for runs, color, label in (
        (learned, C.PALETTE["unguarded"], "learned"),
        (fallback, C.PALETTE["fallback"], "LRU"),
        (bouncer, C.PALETTE["bouncer"], "Bouncer"),
    ):
        mean = np.mean(_curves(runs), axis=0)
        ax.plot(x, mean, color=color, label=label)
    ax.axvline(cfg.shift_window, color="#333", ls="--", lw=0.9)
    ax.text(cfg.shift_window + 1, 0.06, "full semantic\nreversal", fontsize=6.5)
    ax.annotate("12.5% fixed\nlearned leaders", xy=(cfg.windows - 8, 0.287),
                xytext=(cfg.windows - 27, 0.17), fontsize=6.2,
                arrowprops={"arrowstyle": "->", "lw": 0.6, "color": "#555"})
    ax.set(xlabel="audit window", ylabel="hit rate", ylim=(0, 0.52),
           title="(a) Constructed maximal shift")
    ax.legend(fontsize=6.5, loc="upper right")

    ax = axes[1]
    sev = np.asarray([c["severity"] for c in severity_cells])
    gaps = np.asarray([c["true_gap_steady_mean"] for c in severity_cells])
    det = np.asarray([
        np.nan if c["detection_fraction"] is None else c["detection_fraction"]
        for c in severity_cells
    ])
    ax.plot(sev, gaps, "o-", color=C.PALETTE["accent"], label="learned - LRU")
    ax.axhline(0, color="#555", lw=0.7)
    ax.axhline(cfg.cusum_K, color="#888", lw=0.7, ls=":", label="$K$")
    ax.set(xlabel="shifted set fraction", ylabel="steady hit-rate gap",
           title="(b) Severity stresses detection")
    ax2 = ax.twinx()
    ax2.plot(sev, det, "s--", color=C.PALETTE["bouncer"], label="detected harmful")
    ax2.set_ylabel("detection fraction", color=C.PALETTE["bouncer"], fontsize=7)
    ax2.set_ylim(-0.05, 1.05)
    lines = [
        line for line in ax.get_lines() + ax2.get_lines()
        if line.get_label() and not line.get_label().startswith("_")
    ]
    labels = [line.get_label() for line in lines]
    ax.legend(lines, labels, fontsize=5.8, loc="lower left")

    ax = axes[2]
    names = ["Bouncer", "PSEL-8", "PSEL-10"]
    abrupt = [abrupt_refs[n]["delay_from_reference_crossing_mean"] for n in names]
    gradual = [gradual_refs[n]["delay_from_reference_crossing_mean"] for n in names]
    pos = np.arange(len(names))
    ax.bar(pos - 0.17, abrupt, 0.34, color=C.PALETTE["bouncer"], label="abrupt")
    ax.bar(pos + 0.17, gradual, 0.34, color=C.PALETTE["fallback"], label="16-window ramp")
    ax.set_xticks(pos)
    ax.set_xticklabels(["Bouncer", "PSEL\n8-bit", "PSEL\n10-bit"], fontsize=6.2)
    ax.set_ylabel("delay after common gap crossing")
    ax.set_title("(c) Reference-rule latency")
    ax.legend(fontsize=5.8, loc="upper left")
    C.savefig(fig, "trained_characterization.pdf")


def main() -> None:
    cfg = replace(Config(), windows=SWEEP_WINDOWS, shift_window=SWEEP_SHIFT)
    model = fit_model(cfg)

    severity_cells, saved = run_severity_sweep(cfg, model)
    add_hypergeometric_predictions(cfg, severity_cells)
    full_learned, full_fallback, full_bouncer = saved[1.0]
    psel_sweep = psel_severity_sweep(cfg, model, saved)

    abrupt_refs = detector_reference(
        cfg, model, ramp_windows=0,
        learned=full_learned, fallback=full_fallback,
    )
    gradual_learned = run_mode(
        cfg, model, "learned", severity=1.0, ramp_windows=RAMP_WINDOWS
    )
    gradual_fallback = run_mode(
        cfg, model, "fallback", severity=1.0, ramp_windows=RAMP_WINDOWS
    )
    gradual_refs = detector_reference(
        cfg, model, ramp_windows=RAMP_WINDOWS,
        learned=gradual_learned, fallback=gradual_fallback,
    )

    temporal = temporal_ab_diagnostic(full_learned, full_fallback)
    families = family_perturbations(cfg, model)
    zipf = zipf_sampling_boundary(cfg, model)
    make_figure(
        cfg, severity_cells, (full_learned, full_fallback, full_bouncer),
        abrupt_refs, gradual_refs,
    )

    result = {
        "scope": (
            "Controlled trace-replay characterization within one synthetic workload class; "
            "severity, drift rate, cache pressure, and reuse-set size vary, but no cell is an "
            "independent application trace."
        ),
        "fixed_parameters": {
            "n_sets": cfg.n_sets,
            "ways_nominal": cfg.ways,
            "accesses_per_set_window": cfg.accesses_per_set_window,
            "learned_leaders": cfg.n_learned_leaders,
            "fallback_leaders": cfg.n_fallback_leaders,
            "cusum_K": cfg.cusum_K,
            "cusum_H": cfg.cusum_H,
            "seeds_per_cell": N_SEEDS,
            "windows": cfg.windows,
            "shift_window": cfg.shift_window,
        },
        "severity_sweep": severity_cells,
        "detector_references": {
            "interpretation": (
                "PSEL is the closest architectural ancestor, not a calibrated safety "
                "detector. Counter width/history set its inertia; Bouncer's H/K encode a "
                "named evidence margin."
            ),
            "abrupt": abrupt_refs,
            "gradual_16_window_ramp": gradual_refs,
            "psel_severity_sweep": psel_sweep,
        },
        "input_monitors": {
            "pc_histogram_total_variation_all_cells": 0.0,
            "model_confidence_distribution_total_variation_all_cells": 0.0,
            "note": (
                "Every set-window contains exactly 25% of each PC, so the distribution of "
                "any deterministic PC-only model score is invariant as well."
            ),
        },
        "temporal_ab_reference": temporal,
        "controlled_family_perturbations_at_severity_0_5": families,
        "representative_sampling_boundary": zipf,
    }
    C.save_json("trained_characterization.json", result)

    full = severity_cells[-1]
    assert full["detected_harmful_seeds"] == N_SEEDS
    assert full["delay_from_reference_crossing_mean"] == 1.0
    assert severity_cells[0]["false_gate_seeds"] == 0
    assert zipf["harmful_seeds"] > zipf["detected_harmful_seeds"]
    print(
        "  abrupt delays: "
        + ", ".join(
            f"{name}={cell['delay_from_reference_crossing_mean']}"
            for name, cell in abrupt_refs.items()
        )
    )
    print(
        f"  Zipf boundary: follower gap={zipf['weighted_follower_gap_post_mean']:+.4f}, "
        f"leader estimate={zipf['unweighted_leader_estimate_post_mean']:+.4f}, "
        f"detected={zipf['detected_harmful_seeds']}/{zipf['harmful_seeds']}"
    )


if __name__ == "__main__":
    main()
