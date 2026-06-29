#!/usr/bin/env python3
"""N1 reward-swap analysis. Reads the per-config ChampSim logs + gate CSVs for
each reward signal and computes the head-to-head metrics:
  clean_tax                      = 1 - bouncer_clean / unguarded_clean
  unguarded_attack_loss_pct      = (1 - unguarded_attack/unguarded_clean) * 100
  bouncer_atk_vs_unguarded_atk   = (bouncer_attack/unguarded_attack - 1) * 100
Holds (tau,H,window,partition,FSM) fixed; the ONLY thing varying across columns
is BOUNCER_REWARD. Emits results/N1_reward_swap.json + a markdown table."""
import json, re, sys, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))
CFGS = ["unguarded_clean", "bouncer_clean", "unguarded_attack", "bouncer_attack"]
REWARDS = ["cachehit", "ownacc", "ownpf", "ownpf_peraccess"]

def ipc(reward, cfg):
    p = os.path.join(HERE, f"{reward}_{cfg}.log")
    if not os.path.exists(p): return None
    m = re.findall(r"cumulative IPC:\s*([0-9.]+)", open(p).read(), re.I)
    return float(m[-1]) if m else None

def gate_stats(reward, cfg):
    p = os.path.join(HERE, f"{reward}_{cfg}.gate.csv")
    if not os.path.exists(p): return None
    rows = [l.strip().split(",") for l in open(p).read().splitlines()[1:] if l.strip()]
    if not rows: return None
    n = len(rows); g = sum(1 for r in rows if r[2] == "GATED")
    dh = [float(r[1]) for r in rows]
    states = [r[2] for r in rows]
    return {"windows": n, "gated_windows": g, "gated_frac": round(g / n, 3),
            "mean_delta_hat": round(sum(dh) / n, 5),
            "final_state": states[-1],
            "first_gated_window": next((i for i, r in enumerate(rows) if r[2] == "GATED"), None)}

def metrics(reward):
    d = {c: ipc(reward, c) for c in CFGS}
    uc, bc, ua, ba = (d[c] for c in CFGS)
    out = {"ipc": d}
    if uc and bc: out["clean_tax_pct"] = round((1 - bc / uc) * 100, 2)
    if uc and ua: out["unguarded_attack_loss_pct"] = round((1 - ua / uc) * 100, 2)
    if ua and ba: out["bouncer_atk_vs_unguarded_atk_pct"] = round((ba / ua - 1) * 100, 2)
    out["gate"] = {c: gate_stats(reward, c) for c in CFGS}
    return out

def main():
    res = {r: metrics(r) for r in REWARDS if ipc(r, "unguarded_clean") is not None}
    json.dump(res, open(os.path.join(HERE, "N1_reward_swap.json"), "w"), indent=2)

    def g(r, k): return res.get(r, {}).get(k)
    print("\n## N1 reward-swap: roms 654.roms_s, FIXED (tau=0,H=0.25,window=40000); swap ONLY the reward\n")
    names = {"cachehit": "cachehit (baseline)", "ownacc": "ownacc (own reward)",
             "ownpf": "ownpf (leaky ablation)", "ownpf_peraccess": "ownpf_peraccess (sparse ablation)"}
    cols = [r for r in REWARDS if r in res]
    print("| metric | " + " | ".join(names.get(r, r) for r in cols) + " |")
    print("|" + "---|" * (len(cols) + 1))
    rows = [
        ("unguarded_clean IPC",   lambda r: g(r, "ipc")["unguarded_clean"]),
        ("bouncer_clean IPC",     lambda r: g(r, "ipc")["bouncer_clean"]),
        ("unguarded_attack IPC",  lambda r: g(r, "ipc")["unguarded_attack"]),
        ("bouncer_attack IPC",    lambda r: g(r, "ipc")["bouncer_attack"]),
        ("**clean_tax %**",       lambda r: g(r, "clean_tax_pct")),
        ("bouncer_atk vs unguard_atk %", lambda r: g(r, "bouncer_atk_vs_unguarded_atk_pct")),
        ("clean: gated windows",  lambda r: f'{g(r,"gate")["bouncer_clean"]["gated_windows"]}/{g(r,"gate")["bouncer_clean"]["windows"]}' if g(r,"gate")["bouncer_clean"] else None),
        ("clean: mean Δ̂",         lambda r: g(r,"gate")["bouncer_clean"]["mean_delta_hat"] if g(r,"gate")["bouncer_clean"] else None),
        ("attack: first GATED win", lambda r: g(r,"gate")["bouncer_attack"]["first_gated_window"] if g(r,"gate")["bouncer_attack"] else None),
    ]
    for label, fn in rows:
        cells = []
        for r in REWARDS:
            try: v = fn(r) if r in res else None
            except Exception: v = None
            cells.append(str(v))
        print(f"| {label} | " + " | ".join(cells) + " |")

if __name__ == "__main__":
    main()
