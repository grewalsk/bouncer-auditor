#!/usr/bin/env python3
"""Fail closed if the MLForSys paper's trained-controller claims drift."""
from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "trained_controller.json"


def close(actual: float, expected: float, tol: float, label: str) -> None:
    if not math.isclose(actual, expected, abs_tol=tol, rel_tol=0.0):
        raise AssertionError(f"{label}: expected {expected} +/- {tol}, got {actual}")
    print(f"  [OK] {label}: {actual:.6f}")


def main() -> None:
    d = json.loads(RESULT.read_text())
    close(d["model"]["validation_accuracy"], 0.9628, 5e-5, "validation accuracy")
    close(d["model"]["validation_majority_accuracy"], 0.5082, 5e-5,
          "validation majority baseline")
    close(d["model"]["validation_logloss"], 0.1603, 5e-5,
          "validation log loss")
    if (d["uncertainty"]["method"] !=
            "two-sided 95% Student-t intervals across deployment seeds"):
        raise AssertionError(f"uncertainty method drifted: {d['uncertainty']}")
    close(d["pc_marginal"]["max_total_variation"], 0.0, 1e-12, "PC-marginal TV")
    if d["pc_marginal"]["input_ood_alarms"] != 0:
        raise AssertionError("input-OOD baseline must remain silent")
    print("  [OK] input-OOD alarms: 0")

    pre = d["steady_hit_rate"]["pre_shift"]
    post = d["steady_hit_rate"]["post_shift"]
    close(pre["learned"]["mean"], 0.4375, 5e-5, "pre-shift learned hit rate")
    close(pre["fallback"]["mean"], 0.3276, 8e-5, "pre-shift fallback hit rate")
    close(pre["bouncer"]["mean"], 0.4237, 8e-5, "pre-shift Bouncer hit rate")
    close(post["learned"]["mean"], 0.0, 1e-12, "post-shift learned hit rate")
    close(post["fallback"]["mean"], 0.3279, 8e-5, "post-shift fallback hit rate")
    close(post["bouncer"]["mean"], 0.2869, 8e-5, "post-shift Bouncer hit rate")

    det = d["detection"]
    if det["detected_seeds"] != 12 or det["total_seeds"] != 12:
        raise AssertionError(f"detection count drifted: {det}")
    close(det["delay_windows_mean"], 1.0, 1e-12, "mean gate delay")
    close(d["utility"]["clean_learned_gain_retained"]["mean"], 0.875, 5e-4,
          "clean learned gain retained")
    close(d["utility"]["shifted_fallback_loss_recovered"]["mean"], 0.875, 5e-4,
          "shifted fallback loss recovered")
    print("\n  15/15 MLForSys claim checks passed.")


if __name__ == "__main__":
    main()
