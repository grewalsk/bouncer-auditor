"""
common.py — Shared experiment harness: the pinned §12 operating point for
Pythia/ChampSim-scale evaluation, a reference-fit helper, and publication-grade
matplotlib styling.

Standard operating point (§12 hyperparameters pinned to concrete P0 values):
  n_sets               2048      (LLC-scale resource)
  n_L = n_F            32        (dueling leader pools; DIP-scale)
  m                    64        (decisions / set / window)
  |W|                  ~ m*n_sets ≈ 1.3e5 decisions (matches §9 epoch grain)
  tau                  0.05      (trust threshold)
  gamma_detect         0.10  ->  K = tau + gamma/2 = 0.10
  tierb_H              0.8       (Tier-B lower-CUSUM threshold)
  n_L/F background     8         (TRUSTED duty cycle)
  Tier-A sample 1/k    k = 8
  => sigma_Δ(m=64,n=32) = sqrt((1/256)(1/32+1/32)) = 0.0156
"""
from __future__ import annotations

import os, json
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from bouncer.environment import MicroArchEnv, CompetenceModel
from bouncer.bouncer import Bouncer, BouncerConfig
from bouncer.set_dueling import SetDuelingConfig
from bouncer.tier_a import TierAConfig
from bouncer.gate_fsm import GateConfig
from bouncer.simulate import SimConfig

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGDIR = os.path.join(HERE, "figures")
RESDIR = os.path.join(HERE, "results")
os.makedirs(FIGDIR, exist_ok=True)
os.makedirs(RESDIR, exist_ok=True)

# --- standard operating point ------------------------------------------------
STD = dict(n_sets=2048, n_L=32, n_F=32, m=64, tau=0.05, gamma_detect=0.10,
           tierb_H=0.8, n_L_bg=8, n_F_bg=8, k=8, T=300, onset=100)


def make_competence(**kw) -> CompetenceModel:
    return CompetenceModel(**kw)


def make_bouncer(mode="full", *, comp=None, n_sets=None, n_L=None, n_F=None,
                 tau=None, gamma=None, tierb_H=None, k=None, n_L_bg=None,
                 n_F_bg=None, region=None, seed=0, reseed_period=1,
                 model_based=False, model_q0=0.5, model_bias=0.0):
    comp = comp or make_competence()
    p = STD
    n_sets = n_sets or p["n_sets"]
    n_L = n_L or p["n_L"]; n_F = n_F or p["n_F"]
    cfg = BouncerConfig(
        n_sets=n_sets, tau=tau if tau is not None else p["tau"],
        gamma_detect=gamma if gamma is not None else p["gamma_detect"],
        tierb_H=tierb_H if tierb_H is not None else p["tierb_H"],
        n_L_background=n_L_bg or p["n_L_bg"], n_F_background=n_F_bg or p["n_F_bg"],
        detector_mode=mode,
        set_dueling=SetDuelingConfig(n_sets=n_sets, n_L=n_L, n_F=n_F,
                                     reseed_period=reseed_period,
                                     audited_frac=SimConfig.audited_region_frac),
        tier_a=TierAConfig(feature_dim=16, sample_rate_inv_k=k or p["k"]),
        gate=GateConfig(), region=region,
        model_based=model_based, model_q0=model_q0, model_bias=model_bias)
    env = MicroArchEnv(comp=comp, n_sets=n_sets, seed=seed + 10)
    b = Bouncer(cfg, seed=seed)
    _fit_reference(env, b, comp, seed=seed + 99)
    return env, b


def _fit_reference(env, b, comp, n=4000, seed=99):
    rng = np.random.default_rng(seed)
    uv = np.clip(0.05 + 0.02 * rng.standard_normal(n), 0, 1)
    X = env.features(uv); c = env.confidence(uv)
    a = np.ones(n); r = (rng.random(n) < comp.mu_C(uv)).astype(float)
    b.fit_reference(X, c, a, r)


def simconfig(n_sets=None, m=None, T=None, k=None) -> SimConfig:
    p = STD
    return SimConfig(n_sets=n_sets or p["n_sets"], m=m or p["m"],
                     sample_rate_inv_k=k or p["k"], T=T or p["T"])


def save_json(name, obj):
    path = os.path.join(RESDIR, name)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=_default)
    print(f"  wrote {path}")
    return path


def _default(o):
    if isinstance(o, (np.floating,)): return float(o)
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, np.ndarray): return o.tolist()
    if o is np.inf: return "inf"
    return str(o)


# --- figure styling ----------------------------------------------------------
PALETTE = dict(bouncer="#1f4e79", fallback="#9aa0a6", unguarded="#c0392b",
               oracle="#2e7d32", sin="#e69500", accent="#6a3d9a",
               grid="#dfe3e8", probe="#7fb3d5")


def setstyle():
    plt.rcParams.update({
        "figure.dpi": 130, "savefig.dpi": 200,
        "font.family": "serif", "font.size": 9,
        "axes.titlesize": 9.5, "axes.labelsize": 9,
        "axes.edgecolor": "#444", "axes.linewidth": 0.8,
        "axes.grid": True, "grid.color": PALETTE["grid"], "grid.linewidth": 0.6,
        "legend.fontsize": 7.5, "legend.frameon": False,
        "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
        "lines.linewidth": 1.4, "figure.constrained_layout.use": True,
    })


def savefig(fig, name):
    setstyle()
    path = os.path.join(FIGDIR, name)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {path}")
    return path
