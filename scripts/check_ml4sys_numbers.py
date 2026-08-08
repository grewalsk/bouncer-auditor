#!/usr/bin/env python3
"""Fail closed if the MLForSys paper's trained-controller claims drift."""
from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_RESULT = ROOT / "results" / "trained_controller.json"
CHAR_RESULT = ROOT / "results" / "trained_characterization.json"
UPGRADE_RESULT = ROOT / "results" / "trained_upgrades.json"
WARMUP_RESULT = ROOT / "results" / "warmup_predictor.json"
EXPECTED_CHECKS = 60
N_CHECKS = 0


def passed(label: str, value) -> None:
    global N_CHECKS
    N_CHECKS += 1
    print(f"  [OK] {label}: {value}")


def close(actual: float, expected: float, tol: float, label: str) -> None:
    if not math.isclose(actual, expected, abs_tol=tol, rel_tol=0.0):
        raise AssertionError(f"{label}: expected {expected} +/- {tol}, got {actual}")
    passed(label, f"{actual:.6f}")


def require(condition: bool, label: str, value) -> None:
    if not condition:
        raise AssertionError(f"{label}: {value}")
    passed(label, value)


def main() -> None:
    d = json.loads(MAIN_RESULT.read_text())
    c = json.loads(CHAR_RESULT.read_text())
    u = json.loads(UPGRADE_RESULT.read_text())
    w = json.loads(WARMUP_RESULT.read_text())

    close(d["model"]["validation_accuracy"], 0.9628, 5e-5, "validation accuracy")
    close(d["model"]["validation_majority_accuracy"], 0.5082, 5e-5,
          "validation majority baseline")
    close(d["model"]["validation_logloss"], 0.1603, 5e-5,
          "validation log loss")
    require(
        d["uncertainty"]["method"] ==
        "two-sided 95% Student-t intervals across deployment seeds",
        "uncertainty method",
        d["uncertainty"]["method"],
    )
    close(d["pc_marginal"]["max_total_variation"], 0.0, 1e-12,
          "PC-marginal TV")
    require(d["pc_marginal"]["input_ood_alarms"] == 0,
            "PC-monitor alarms", d["pc_marginal"]["input_ood_alarms"])
    close(d["model_confidence_monitor"]["distribution_total_variation"],
          0.0, 1e-12, "model-confidence TV")
    require(d["model_confidence_monitor"]["alarms"] == 0,
            "confidence-monitor alarms", d["model_confidence_monitor"]["alarms"])

    pre = d["steady_hit_rate"]["pre_shift"]
    post = d["steady_hit_rate"]["post_shift"]
    close(pre["learned"]["mean"], 0.4375, 5e-5,
          "pre-shift learned hit rate")
    close(pre["fallback"]["mean"], 0.3276, 8e-5,
          "pre-shift fallback hit rate")
    close(pre["bouncer"]["mean"], 0.4237, 8e-5,
          "pre-shift Bouncer hit rate")
    close(post["learned"]["mean"], 0.0, 1e-12,
          "post-shift learned hit rate")
    close(post["fallback"]["mean"], 0.3279, 8e-5,
          "post-shift fallback hit rate")
    close(post["bouncer"]["mean"], 0.2869, 8e-5,
          "post-shift Bouncer hit rate")

    det = d["detection"]
    require(det["detected_seeds"] == 12 and det["total_seeds"] == 12,
            "maximal-shift detections", f"{det['detected_seeds']}/{det['total_seeds']}")
    close(det["delay_windows_mean"], 1.0, 1e-12, "maximal-shift gate delay")
    require(det["pre_shift_false_alarms"] == 0,
            "maximal-shift pre-change false alarms", det["pre_shift_false_alarms"])

    utility = d["utility"]
    close(utility["designed_clean_gain_retention"], 0.875, 1e-12,
          "designed clean-retention ceiling")
    close(utility["designed_shift_loss_recovery"], 0.875, 1e-12,
          "designed shifted-recovery ceiling")
    close(utility["clean_learned_gain_retained"]["mean"], 0.875, 5e-4,
          "observed clean learned gain retained")
    close(utility["shifted_fallback_loss_recovered"]["mean"], 0.875, 5e-4,
          "observed shifted fallback loss recovered")
    require(abs(d["estimator_audit"]["mean_bias_all"]) < 0.001,
            "homogeneous-workload estimator mean bias",
            f"{d['estimator_audit']['mean_bias_all']:+.6f}")
    close(d["estimator_audit"]["rmse_all"], 0.010424, 5e-6,
          "homogeneous-workload estimator RMSE")

    cells = c["severity_sweep"]
    require(len(cells) == 9, "severity-cell count", len(cells))
    require([x["severity"] for x in cells] == [i / 8 for i in range(9)],
            "severity grid", [x["severity"] for x in cells])
    require(cells[0]["false_gate_seeds"] == 0,
            "zero-shift false gates", cells[0]["false_gate_seeds"])
    require(cells[1]["true_gap_steady_mean"] > 0.05 and
            cells[1]["false_gate_seeds"] == 1,
            "weak-shift in-control stress", {
                "gap": cells[1]["true_gap_steady_mean"],
                "false_gates": cells[1]["false_gate_seeds"],
            })
    require(cells[2]["detected_below_reference_seeds"] == 7,
            "near-boundary detections", f"{cells[2]['detected_below_reference_seeds']}/12")
    require(cells[3]["detected_below_reference_seeds"] == 10,
            "37.5%-severity detections", f"{cells[3]['detected_below_reference_seeds']}/12")
    require(cells[4]["detected_below_reference_seeds"] == 11,
            "50%-severity detections", f"{cells[4]['detected_below_reference_seeds']}/12")
    require(cells[5]["detected_below_reference_seeds"] == 12,
            "62.5%-severity detections", f"{cells[5]['detected_below_reference_seeds']}/12")
    require(cells[-1]["detected_below_reference_seeds"] == 12 and
            cells[-1]["delay_from_reference_crossing_mean"] == 1.0,
            "maximal severity characterization", {
                "detected": cells[-1]["detected_below_reference_seeds"],
                "delay": cells[-1]["delay_from_reference_crossing_mean"],
            })

    refs = c["detector_references"]
    gradual = refs["gradual_16_window_ramp"]
    require(gradual["Bouncer"]["detected_below_reference_seeds"] == 12,
            "gradual-shift Bouncer detections",
            gradual["Bouncer"]["detected_below_reference_seeds"])
    require(
        refs["abrupt"]["PSEL-10"]["delay_from_reference_crossing_mean"] >
        refs["abrupt"]["Bouncer"]["delay_from_reference_crossing_mean"],
        "10-bit PSEL has greater abrupt inertia",
        {
            "PSEL-10": refs["abrupt"]["PSEL-10"]["delay_from_reference_crossing_mean"],
            "Bouncer": refs["abrupt"]["Bouncer"]["delay_from_reference_crossing_mean"],
        },
    )
    close(c["input_monitors"]["model_confidence_distribution_total_variation_all_cells"],
          0.0, 1e-12, "confidence TV across severity sweep")
    close(c["temporal_ab_reference"]["learned_policy_exposure_before_decision"],
          0.5, 1e-12, "temporal A/B clean exposure")

    zipf = c["representative_sampling_boundary"]
    require(zipf["weighted_follower_gap_post_mean"] < 0.0 and
            zipf["unweighted_leader_estimate_post_mean"] > 0.0,
            "Zipf boundary reverses estimand sign", {
                "follower": zipf["weighted_follower_gap_post_mean"],
                "leaders": zipf["unweighted_leader_estimate_post_mean"],
            })
    require(zipf["detected_harmful_seeds"] == 4 and zipf["harmful_seeds"] == 12,
            "Zipf boundary detections", f"{zipf['detected_harmful_seeds']}/{zipf['harmful_seeds']}")
    families = c["controlled_family_perturbations_at_severity_0_5"]
    require(len(families) == 4, "controlled family perturbation count", len(families))
    require(families["nominal"]["detected_below_reference_seeds"] == 11,
            "nominal 50%-severity family detections",
            families["nominal"]["detected_below_reference_seeds"])
    require(families["tight_4way"]["false_gate_seeds"] == 5,
            "near-reference 4-way false gates",
            families["tight_4way"]["false_gate_seeds"])

    hg = cells[2]["hypergeometric_prediction"]
    close(hg["expected_shifted_learned_leaders"], 2.0, 1e-12,
          "near-boundary expected shifted learned leaders")
    require(abs(hg["predicted_between_seed_std_from_overlap_only"] -
                cells[2]["leader_estimate_steady_std_across_seeds"]) < 0.01,
            "hypergeometric overlap predicts observed leader-gap spread", {
                "predicted": hg["predicted_between_seed_std_from_overlap_only"],
                "measured": cells[2]["leader_estimate_steady_std_across_seeds"],
            })
    close(hg["probability_one_window_gap_below_K"], 0.6485865, 1e-6,
          "near-boundary one-window crossing probability")
    close(hg["deterministic_delay_heuristic"], 6.082218, 1e-6,
          "near-boundary deterministic delay heuristic")

    psel025 = refs["psel_severity_sweep"][2]
    require(psel025["PSEL-8"]["detected_below_reference_seeds"] == 3,
            "PSEL-8 near-boundary detections",
            psel025["PSEL-8"]["detected_below_reference_seeds"])
    require(psel025["PSEL-10"]["delay_from_reference_crossing_mean"] >
            psel025["PSEL-8"]["delay_from_reference_crossing_mean"],
            "PSEL-10 near-boundary delay exceeds PSEL-8", {
                "PSEL-8": psel025["PSEL-8"]["delay_from_reference_crossing_mean"],
                "PSEL-10": psel025["PSEL-10"]["delay_from_reference_crossing_mean"],
            })

    traffic = u["traffic_stratified_sampling"]
    uniform = traffic["uniform"]
    stratified = traffic["traffic_stratified"]
    require(uniform["leader_estimate_post_mean"] > 0.0 and
            stratified["leader_estimate_post_mean"] < 0.0,
            "traffic strata correct the estimator sign", {
                "uniform": uniform["leader_estimate_post_mean"],
                "stratified": stratified["leader_estimate_post_mean"],
            })
    require(abs(stratified["estimator_bias_post_mean"]) < 0.005,
            "traffic-stratified estimator bias",
            f"{stratified['estimator_bias_post_mean']:+.6f}")
    require(uniform["detected_harmful_seeds"] == 4 and
            stratified["detected_harmful_seeds"] == 12,
            "traffic-stratified harmful-shift detections", {
                "uniform": uniform["detected_harmful_seeds"],
                "stratified": stratified["detected_harmful_seeds"],
            })

    adaptive = u["adaptive_audit_allocation"]["cells"]
    by_severity = {cell["severity"]: cell for cell in adaptive}
    base = by_severity[0.0]["adaptive_2_to_8_per_arm"]
    require(base["mean_leaders_per_arm_all"] < 2.1,
            "adaptive clean-regime mean leaders per arm",
            base["mean_leaders_per_arm_all"])
    require(base["false_gate_seeds"] == 0,
            "adaptive clean-regime false gates", base["false_gate_seeds"])
    for severity in (0.375, 0.5):
        cell = by_severity[severity]
        require(cell["adaptive_2_to_8_per_arm"]["detected_below_reference_seeds"] >=
                cell["fixed_8_per_arm"]["detected_below_reference_seeds"],
                f"adaptive detections at severity {severity}", {
                    "adaptive": cell["adaptive_2_to_8_per_arm"]["detected_below_reference_seeds"],
                    "fixed": cell["fixed_8_per_arm"]["detected_below_reference_seeds"],
                })
    maximal_adaptive = by_severity[1.0]["adaptive_2_to_8_per_arm"]
    require(maximal_adaptive["detected_below_reference_seeds"] == 12 and
            maximal_adaptive["mean_leaders_per_arm_all"] == 2.0,
            "adaptive maximal-shift operation", {
                "detected": maximal_adaptive["detected_below_reference_seeds"],
                "leaders_per_arm": maximal_adaptive["mean_leaders_per_arm_all"],
            })

    state = u["state_preserving_shadow_metadata"]
    require(state["reset_on_rotation_gap"] < 0.05,
            "state reset attenuates the measured gap", state["reset_on_rotation_gap"])
    require(state["fixed_leader_gap"] > 0.29,
            "fixed assignment preserves stateful gap", state["fixed_leader_gap"])
    require(state["shadow_state_gap"] > 0.29,
            "shadow metadata preserves stateful gap", state["shadow_state_gap"])
    require(w["invariants"]["mult_shadow_recovers_gap_at_slow_warmup"],
            "shadow-state recovery invariant",
            w["invariants"]["mult_shadow_recovers_gap_at_slow_warmup"])
    require(w["shadow_metadata_model"]["bytes_for_64_sets"] == 128,
            "modeled shadow metadata for 64 sets",
            w["shadow_metadata_model"]["bytes_for_64_sets"])

    require(N_CHECKS == EXPECTED_CHECKS, "checker self-count",
            f"{N_CHECKS} substantive checks before self-count")
    print(f"\n  {N_CHECKS}/{N_CHECKS} MLForSys claim checks passed.")


if __name__ == "__main__":
    main()
