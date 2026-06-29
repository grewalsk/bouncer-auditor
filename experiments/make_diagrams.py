"""Vector diagrams for the paper: two-tier architecture + gate FSM."""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import common as C


def box(ax, x, y, w, h, text, fc, ec="#333", fs=8, tc="#111"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                fc=fc, ec=ec, lw=1.1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc)


def arrow(ax, p1, p2, color="#333", style="-|>", rad=0.0, lw=1.2, ls="-"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=11,
                                 connectionstyle=f"arc3,rad={rad}", color=color, lw=lw, ls=ls))


def architecture():
    C.setstyle()
    fig, ax = plt.subplots(figsize=(7.0, 2.5))
    ax.set_xlim(0, 10); ax.set_ylim(0, 3.4); ax.axis("off")
    box(ax, 0.1, 1.2, 1.05, 1.0, "Learned\ncontroller $C$\n$x_t,a_t,r_t$", "#eef3f9", fs=7)
    box(ax, 1.5, 1.25, 2.7, 0.9, "Tier-A (hot, off-path)\n$S_{in}$  $S_{dec}$  $S_{res}$  (CUSUM)", "#fff4e0", fs=7.5)
    box(ax, 4.6, 1.25, 2.7, 0.9, "Tier-B (warm, epoch)\nsecret set-dueling $\\hat\\Delta$\n→ lower CUSUM vs $\\tau$", "#e9eef5", fs=7.5)
    box(ax, 7.7, 1.25, 2.1, 0.9, "Gate FSM\nTRUSTED…PROBING", "#e6f2ea", fs=7.5)
    arrow(ax, (1.15, 1.7), (1.5, 1.7))
    arrow(ax, (4.2, 1.7), (4.6, 1.7), color="#b06a00")
    ax.text(4.4, 1.95, "escalate", fontsize=6.5, color="#b06a00", ha="center")
    arrow(ax, (7.3, 1.7), (7.7, 1.7), color="#1f4e79")
    # taps annotation
    ax.text(0.62, 2.45, "taps (no datapath latency)", fontsize=7, ha="center", color="#555")
    arrow(ax, (1.6, 2.35), (5.9, 2.35), color="#aaa", style="-", rad=-0.12, lw=0.9)
    C.savefig(fig, "arch.pdf")


def fsm():
    C.setstyle()
    fig, ax = plt.subplots(figsize=(7.0, 2.3))
    ax.set_xlim(0, 10); ax.set_ylim(0, 2.6); ax.axis("off")
    states = [("TRUSTED", 0.6, "#e6f2ea"), ("SUSPECT", 3.0, "#fff4e0"),
              ("GATED", 5.6, "#e9eef5"), ("PROBING", 8.2, "#eef3f9")]
    cx = {}
    for name, x, fc in states:
        box(ax, x, 1.0, 1.4, 0.7, name, fc, fs=8)
        cx[name] = (x + 0.7, 1.35)
    def link(a, b, label, rad=0.0, color="#333", yoff=0.0, ls="-"):
        (x1, y1), (x2, y2) = cx[a], cx[b]
        # connect on box edges
        if x2 > x1: p1 = (x1 + 0.7, y1); p2 = (x2 - 0.7, y2)
        else: p1 = (x1 - 0.7, y1); p2 = (x2 + 0.7, y2)
        arrow(ax, p1, p2, color=color, rad=rad, ls=ls)
        ax.text((x1 + x2) / 2, 1.35 + yoff, label, fontsize=6.3, ha="center", color=color)
    link("TRUSTED", "SUSPECT", "Tier-A fires", yoff=0.5, rad=-0.25)
    link("SUSPECT", "GATED", "$\\hat\\Delta$ CUSUM", yoff=0.5, rad=-0.25, color="#c0392b")
    link("GATED", "PROBING", "dwell $T_{dwell}$", yoff=0.5, rad=-0.25)
    link("SUSPECT", "TRUSTED", "clears", yoff=-0.7, rad=-0.25, color="#2e7d32")
    link("PROBING", "TRUSTED", "$\\hat\\Delta\\geq\\tau+\\Delta_{hys}$", yoff=-0.95, rad=-0.32, color="#2e7d32")
    link("PROBING", "GATED", "$\\hat\\Delta<\\tau$ (backoff)", yoff=-0.7, rad=-0.25, color="#c0392b")
    # background Tier-B mimicry path TRUSTED->GATED
    (x1, y1), (x2, y2) = cx["TRUSTED"], cx["GATED"]
    arrow(ax, (x1, y1 + 0.35), (x2, y2 + 0.35), color="#6a3d9a", rad=-0.4, ls=(0, (3, 2)))
    ax.text(3.1, 2.35, "background Tier-B (mimicry path)", fontsize=6.3, ha="center", color="#6a3d9a")
    C.savefig(fig, "fsm.pdf")


if __name__ == "__main__":
    architecture()
    fsm()
