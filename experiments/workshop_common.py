"""Lightweight output and plotting helpers for the MLForSys artifact.

The workshop experiment only needs NumPy and Matplotlib.  Importing the full
``experiments.common`` module also imports the Pandas-based synthetic harness,
which made ``run_ml4sys.sh`` fail in otherwise sufficient minimal environments.
Keep this helper intentionally small and dependency-local.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
FIGDIR = ROOT / "figures"
RESDIR = ROOT / "results"
FIGDIR.mkdir(exist_ok=True)
RESDIR.mkdir(exist_ok=True)

PALETTE = dict(
    bouncer="#1f4e79",
    fallback="#9aa0a6",
    unguarded="#c0392b",
    oracle="#2e7d32",
    accent="#6a3d9a",
    grid="#dfe3e8",
)


def _json_default(obj):
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"cannot serialize {type(obj)!r}")


def save_json(name: str, obj) -> Path:
    path = RESDIR / name
    path.write_text(json.dumps(obj, indent=2, default=_json_default) + "\n")
    print(f"  wrote {path}")
    return path


def setstyle() -> None:
    plt.rcParams.update({
        "figure.dpi": 130,
        "savefig.dpi": 200,
        "font.family": "serif",
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.labelsize": 9,
        "axes.edgecolor": "#444",
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "grid.color": PALETTE["grid"],
        "grid.linewidth": 0.6,
        "legend.fontsize": 7.5,
        "legend.frameon": False,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "lines.linewidth": 1.4,
        "figure.constrained_layout.use": True,
    })


def savefig(fig, name: str) -> Path:
    setstyle()
    path = FIGDIR / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {path}")
    return path
