"""Figure for the real ChampSim L1D result (reads results/champsim.json).
Two traces: lbm (floor cap works) and roms (reward-proxy over-gates a helpful
prefetcher). Honest framing: the auditor is only as good as its competence reward."""
import json
import numpy as np
import matplotlib.pyplot as plt
import common as C


def main():
    C.setstyle()
    d = json.load(open(f"{C.RESDIR}/champsim.json"))
    order = [k for k in ["perlbench", "lbm", "roms"] if k in d["traces"]] or list(d["traces"])
    traces = [(k, d["traces"][k]) for k in order]
    fig, axes = plt.subplots(1, len(traces), figsize=(2.4 * len(traces) + 0.6, 3.0))
    if len(traces) == 1:
        axes = [axes]
    cfgs = ["unguarded_clean", "bouncer_clean", "unguarded_attack", "bouncer_attack"]
    labels = ["unguard\nclean", "Bounce\nclean", "unguard\nattack", "Bounce\nattack"]
    cols = [C.PALETTE["unguarded"], C.PALETTE["bouncer"], C.PALETTE["unguarded"], C.PALETTE["bouncer"]]
    hatch = ["", "", "//", "//"]
    for ax, (name, tr) in zip(axes, traces):
        i = tr["ipc"]; vals = [i[c] for c in cfgs]
        x = np.arange(4)
        for xi, v, c, h in zip(x, vals, cols, hatch):
            ax.bar(xi, v, 0.64, color=c, hatch=h, edgecolor="white", linewidth=0.6)
            ax.text(xi, v + (max(vals) - min(vals)) * 0.03, f"{v:.3f}", ha="center", fontsize=6.3)
        ax.axhline(i["bouncer_clean"], color="#666", lw=0.8, ls=":")
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=6.3)
        ax.set_ylabel("IPC")
        lo = min(vals) - (max(vals) - min(vals)) * 0.4; hi = max(vals) + (max(vals) - min(vals)) * 0.25
        ax.set_ylim(lo, hi)
        ax.set_title(f"SPEC {tr['name']}  (clean tax {100*(1-tr['clean_tax']):.0f}\\%)", fontsize=8)
    fig.suptitle("Real ChampSim L1D on SPEC: floor cap holds; the auditor is only as good as its reward", fontsize=8.0)
    C.savefig(fig, "champsim.pdf")
    print("  clean tax: " + ", ".join(f"{k}={v['clean_tax']}" for k, v in traces))


if __name__ == "__main__":
    main()
