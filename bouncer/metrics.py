"""
metrics.py — The §10 evaluation metrics, computed from a run_episode DataFrame.

Ground-truth "off-policy" is the operational definition from §13: a *sustained*
competence drop below tau. Detection latency is measured from that crossing to
the first GATED window.
"""
from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd


def first_sustained_crossing(df: pd.DataFrame, tau: float, hold: int = 3) -> Optional[int]:
    """First window t where delta_true < tau and stays below for `hold` windows."""
    below = (df["delta_true"].values < tau)
    for t in range(len(below) - hold + 1):
        if below[t:t + hold].all():
            return t
    return None


def first_gated(df: pd.DataFrame, after: int = 0) -> Optional[int]:
    g = df["state"].values
    for t in range(after, len(g)):
        if g[t] == "GATED":
            return t
    return None


def detection_latency(df: pd.DataFrame, tau: float, hold: int = 3) -> Optional[int]:
    """Windows from true off-policy crossing to GATED. None if never crossed;
    np.inf if crossed but never gated."""
    cross = first_sustained_crossing(df, tau, hold)
    if cross is None:
        return None
    g = first_gated(df, after=cross)
    if g is None:
        return np.inf
    return g - cross


def detected(df: pd.DataFrame, tau: float, hold: int = 3, deadline: Optional[int] = None) -> bool:
    """True if a genuine off-policy episode was gated (within deadline windows)."""
    lat = detection_latency(df, tau, hold)
    if lat is None or lat is np.inf:
        return False
    if deadline is not None:
        return lat <= deadline
    return True


def false_alarm(df: pd.DataFrame, tau: float, hold: int = 3) -> bool:
    """True if GATED ever fired with no genuine sustained off-policy episode
    (clean-episode false alarm)."""
    cross = first_sustained_crossing(df, tau, hold)
    if cross is not None:
        # there was a genuine episode; a gate before it is still a false alarm
        g = first_gated(df, after=0)
        return (g is not None) and (g < cross)
    return first_gated(df, after=0) is not None


def detection_latency_onset(df: pd.DataFrame, onset: int) -> float:
    """Windows from a known attack onset to GATED. For attacks whose *global*
    competence barely moves by design (regional covert), the ground-truth
    positive is the onset itself. np.inf if never gated after onset."""
    g = first_gated(df, after=onset)
    return np.inf if g is None else (g - onset)


def steady_state_floor_violation(df: pd.DataFrame) -> float:
    """Floor violation restricted to GATED windows (steady-state protection),
    excluding the bounded pre-detection transient. Target ~0."""
    sub = df[df["state"] == "GATED"]
    if len(sub) == 0:
        return float("nan")
    v = (sub["ipc_fallback"] - sub["ipc_bouncer"]) / sub["ipc_fallback"]
    return float(v.max())


def clean_tax(df_clean: pd.DataFrame) -> float:
    """IPC_Bouncer / IPC_unguarded on a clean episode (target >= 0.99)."""
    return float(df_clean["ipc_bouncer"].mean() / df_clean["ipc_unguarded"].mean())


def safety_floor_violation(df: pd.DataFrame) -> float:
    """max_t (IPC_fallback - IPC_Bouncer)/IPC_fallback (target <= small)."""
    v = (df["ipc_fallback"] - df["ipc_bouncer"]) / df["ipc_fallback"]
    return float(v.max())


def performance_recovered(df: pd.DataFrame, df_clean_mean_ipc: float) -> float:
    """(IPC_Bouncer - IPC_unguarded_attacked) / (IPC_clean - IPC_unguarded_attacked),
    measured over the attack window. 1.0 = fully recovered to clean."""
    atk = df[df["label_attack"]]
    if len(atk) == 0:
        return float("nan")
    ipc_b = atk["ipc_bouncer"].mean()
    ipc_u = atk["ipc_unguarded"].mean()
    denom = (df_clean_mean_ipc - ipc_u)
    if abs(denom) < 1e-9:
        return float("nan")
    return float((ipc_b - ipc_u) / denom)


def cumulative_regret_vs_fallback(df: pd.DataFrame) -> np.ndarray:
    """Σ_t (IPC_fallback - IPC_Bouncer) — the quantity Lemma 6.1 bounds.
    Positive mass = windows where Bouncer underperforms the floor."""
    return np.cumsum((df["ipc_fallback"] - df["ipc_bouncer"]).values)


def roc_point(detected_flags: np.ndarray, fa_flags: np.ndarray) -> tuple:
    """TPR, FPR from boolean arrays over episodes."""
    tpr = float(np.mean(detected_flags)) if len(detected_flags) else 0.0
    fpr = float(np.mean(fa_flags)) if len(fa_flags) else 0.0
    return tpr, fpr
