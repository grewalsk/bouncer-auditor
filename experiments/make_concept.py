"""
The conceptual diagram (Instant-Readability framework): one schematic of the core
mechanism, titled as a sentence. A reader who skips all text should grasp the
claim from this picture and its title alone.
"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from experiments import workshop_common as C


def box(ax, x, y, w, h, text, fc, ec="#333", fs=8.5, tc="#111", bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.02",
                                fc=fc, ec=ec, lw=1.1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc,
            fontweight=("bold" if bold else "normal"))


def arrow(ax, p1, p2, color="#333", rad=0.0, lw=1.3, ls="-", style="-|>"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=12,
                                 connectionstyle=f"arc3,rad={rad}", color=color, lw=lw, ls=ls))


def main():
    C.setstyle()
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    ax.set_xlim(0, 12); ax.set_ylim(0, 6); ax.axis("off")
    BL, FL, FOL = C.PALETTE["bouncer"], C.PALETTE["fallback"], "#eef3f9"

    # --- the shared resource: a strip of sets tagged L / F / follower ---
    tags = ["·", "L", "·", "F", "·", "·", "L", "·", "·", "F", "·", "·"]
    x0, y0, s = 0.5, 4.2, 0.62
    for i, tg in enumerate(tags):
        fc = BL if tg == "L" else (FL if tg == "F" else FOL)
        tc = "white" if tg in ("L", "F") else "#888"
        ax.add_patch(Rectangle((x0 + i * s, y0), s * 0.88, 0.8, fc=fc, ec="#666", lw=0.7))
        ax.text(x0 + i * s + s * 0.44, y0 + 0.4, tg, ha="center", va="center", fontsize=8, color=tc, fontweight="bold")
    ax.text(x0 + len(tags) * s / 2, y0 + 1.15, "shared resource: cache sets / buckets",
            ha="center", fontsize=8, color="#444")
    # Assignment policy: fixed for the trained stateful-cache experiment; secrecy
    # and reseeding require a separate adaptive-workload threat model.
    ax.text(x0 + len(tags) * s / 2, y0 - 0.42,
            "fixed here to preserve state; hiding/reseeding is optional adversarial hardening",
            ha="center", fontsize=7.3, color=C.PALETTE["accent"], style="italic")
    arrow(ax, (x0 + len(tags) * s - 0.2, y0 + 1.0), (x0 + 0.2, y0 + 1.0),
          color=C.PALETTE["accent"], rad=-0.35, lw=0.9, ls=(0, (3, 2)))

    # --- legend for L / F ---
    ax.add_patch(Rectangle((0.5, 3.2), 0.3, 0.3, fc=BL, ec="#666", lw=0.6)); ax.text(0.95, 3.35, "L: run learned $C$", fontsize=7.5, va="center")
    ax.add_patch(Rectangle((3.7, 3.2), 0.3, 0.3, fc=FL, ec="#666", lw=0.6)); ax.text(4.15, 3.35, r"F: run fallback $\pi_0$", fontsize=7.5, va="center")
    ax.add_patch(Rectangle((6.9, 3.2), 0.3, 0.3, fc=FOL, ec="#666", lw=0.6)); ax.text(7.35, 3.35, "·: follower (runs the winner)", fontsize=7.5, va="center")

    # --- the audit: compare realized reward on L vs F ---
    box(ax, 0.6, 1.7, 2.2, 0.85, r"reward on L sets" + "\n" + r"$\bar r_L$", "#eaf1fb", fs=8)
    box(ax, 3.3, 1.7, 2.2, 0.85, r"reward on F sets" + "\n" + r"$\bar r_F$", "#f2f3f4", fs=8)
    arrow(ax, (1.7, 4.15), (1.7, 2.58), color=BL, lw=1.1)
    arrow(ax, (4.4, 4.15), (4.4, 2.58), color="#777", lw=1.1)
    box(ax, 6.15, 1.75, 2.5, 0.75, r"competence $\hat\Delta=\bar r_L-\bar r_F$", "#fff4e0", fs=8)
    arrow(ax, (2.8, 2.12), (6.1, 2.12), color="#555")
    arrow(ax, (5.5, 2.12), (6.1, 2.05), color="#555")

    # --- the gate ---
    box(ax, 9.1, 1.55, 2.4, 1.15, r"trust gate" + "\n" + r"is $\hat\Delta \geq \tau$ ?" + "\n(one-sided CUSUM)", "#e6f2ea", fs=8)
    arrow(ax, (8.65, 2.12), (9.1, 2.12), color="#555")

    # --- the two outcomes ---
    box(ax, 9.0, 0.15, 1.3, 0.85, "YES\ntrust $C$", "#dff0e6", fs=7.8, bold=True, tc="#1e7d3f")
    box(ax, 10.5, 0.15, 1.3, 0.85, "NO\nrevert to $\\pi_0$", "#fdeaea", fs=7.8, bold=True, tc=C.PALETTE["unguarded"])
    arrow(ax, (9.9, 1.55), (9.65, 1.0), color="#1e7d3f")
    arrow(ax, (10.7, 1.55), (11.15, 1.0), color=C.PALETTE["unguarded"])
    ax.text(6.0, 0.55, "followers (most of the resource, = what the victim experiences)\nrun whichever the gate currently trusts",
            ha="center", fontsize=7.2, color="#444")
    arrow(ax, (9.0, 0.57), (7.7, 0.57), color="#999", lw=0.8)

    fig.suptitle("Concurrently duel a learned controller against its fallback on sampled partitions;\n"
                 "trust it only while it is measurably winning.",
                 fontsize=9.3, y=1.02)
    C.savefig(fig, "concept.pdf")
    print("  wrote figures/concept.pdf")


if __name__ == "__main__":
    main()
