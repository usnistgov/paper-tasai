#!/usr/bin/env python
"""Create workflow and TOC figures for the paper."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

import graphviz
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np


def render_workflow_figure(output_base: Path):
    """Render the workflow figure using the Graphviz layout under review."""
    dot = graphviz.Digraph(
        name="TAS_AI_Workflow_Fixed",
        format=output_base.suffix.lstrip("."),
        graph_attr={
            "rankdir": "LR",
            "splines": "ortho",
            "nodesep": "0.8",
            "ranksep": "0.8",
            "fontname": "Helvetica",
        },
    )
    dot.attr(
        label=(
            '<<B><FONT POINT-SIZE="20">TAS-AI Hybrid Workflow</FONT></B>'
            '<BR/><FONT POINT-SIZE="14">The main loop combines agnostic discovery, physics-aware inference, motion-aware execution, and an optional audit layer.</FONT><BR/><BR/>>'
        ),
        labelloc="t",
    )
    dot.attr("node", shape="rect", style="filled,rounded", fontname="Helvetica", margin="0.3", penwidth="2")
    dot.attr("edge", fontname="Helvetica", fontsize="11", penwidth="1.5", color="#333333")

    dot.node(
        "1",
        '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">'
        '<TR><TD ALIGN="LEFT"><B><FONT POINT-SIZE="14"> 1 </FONT></B></TD></TR>'
        '<TR><TD><B>Agnostic discovery</B></TD></TR>'
        '<TR><TD><FONT POINT-SIZE="10">Enhanced Log-GP mapping</FONT></TD></TR>'
        "</TABLE>>",
        fillcolor="#e1ebf4",
    )
    dot.node(
        "2",
        '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">'
        '<TR><TD ALIGN="LEFT"><B><FONT POINT-SIZE="14"> 2 </FONT></B></TD></TR>'
        '<TR><TD><B>Physics-informed discrimination and refinement</B></TD></TR>'
        '<TR><TD><FONT POINT-SIZE="10">Candidate Hamiltonians are compared against data,<BR/>then the next probes are ranked by model contrast<BR/>and parameter information gain.</FONT></TD></TR>'
        "</TABLE>>",
        fillcolor="#f7dcdb",
    )
    dot.node(
        "3",
        '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">'
        '<TR><TD ALIGN="LEFT"><B><FONT POINT-SIZE="14"> 3 </FONT></B></TD></TR>'
        '<TR><TD><B>Motion-aware sequencing and execution</B></TD></TR>'
        '<TR><TD><FONT POINT-SIZE="10">Accepted probes are ordered greedily or with<BR/>short-horizon MCTS to reduce wall-clock overhead<BR/>before the next batch is executed.</FONT></TD></TR>'
        "</TABLE>>",
        fillcolor="#fdf2d0",
    )
    dot.node(
        "4",
        '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">'
        '<TR><TD ALIGN="LEFT"><B><FONT POINT-SIZE="14"> 4 </FONT></B></TD></TR>'
        '<TR><TD><B>Strategic audit (optional)</B></TD></TR>'
        '<TR><TD><FONT POINT-SIZE="10">A constrained router may request a small number<BR/>of falsification probes when the current planner<BR/>becomes too self-reinforcing.</FONT></TD></TR>'
        "</TABLE>>",
        fillcolor="#dceddf",
        style="filled, rounded, dashed",
    )
    dot.node(
        "model",
        '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">'
        '<TR><TD><B>Candidate-model family</B></TD></TR>'
        '<TR><TD><FONT POINT-SIZE="10">Hand-specified or seeded from<BR/>crystal-structure proposals.</FONT></TD></TR>'
        "</TABLE>>",
        fillcolor="#f4f4f4",
    )
    dot.node(
        "state",
        '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">'
        '<TR><TD><B>Updated experiment state</B></TD></TR>'
        '<TR><TD><FONT POINT-SIZE="10">Accumulated data, accessible windows,<BR/>and current model scores feed the next cycle.</FONT></TD></TR>'
        "</TABLE>>",
        fillcolor="#f0f4f0",
    )

    dot.edge("1", "2", label=" handoff once signal structure is localized ")
    dot.edge("2", "3")
    dot.edge("3", "4", label=" bounded audit requests ", style="dashed")
    dot.edge("model", "2", label=" candidate family supplied here ")
    dot.edge("state", "1")
    dot.edge(
        "3",
        "state",
        label=" new data continue the loop until model discrimination is decisive ",
        fontcolor="#3b759e",
        color="#3b759e",
        constraint="false",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_base = Path(tmpdir) / output_base.stem
        rendered = Path(dot.render(str(tmp_base), cleanup=True))
        output_base.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(rendered, output_base)


def create_swimlane_figure():
    """Generate improved workflow/example swimlane diagram."""
    fig, ax = plt.subplots(figsize=(14, 8), dpi=300)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    box_w, box_h = 2.0, 1.3
    gap, x_start = 0.5, 0.5
    y_top, y_bot = 6.0, 2.5

    c_blue = "#dae8fc"
    c_yellow = "#fff2cc"
    c_green = "#d5e8d4"
    c_red = "#f8cecc"
    c_purple = "#e1d5e7"
    c_db = "#f5f5f5"

    nodes = [
        ("Crystal\nStructure", c_blue, "Input", "Fe-O Square Lattice\n(CIF file)"),
        ("GNN / GK\nHypothesis", c_yellow, "Hypothesis Gen", "GK Rules:\n180° Fe-O-Fe $\\to$ Strong $J_1$\n117° Fe-Fe $\\to$ Weak $J_2$"),
        ("Candidate\nHamiltonians", c_green, "Model Pool", "$M_1$: NN ($J_1$)\n$M_3$: $J_1+J_2$\n$M_4$: Full ($J_1+J_2+D$)"),
        ("TAS-AI Planning\n(Hybrid Strategy)", c_red, "Adaptive Planner", "1. Symmetry Seeding (Prior)\n2. Diversity-JSD (Explore)\n3. Superset Refinement (Exploit)"),
        ("Bayesian\nDiscrimination", c_purple, "Inference", "Posterior Update:\nSuperset plan confirms $J_2$\nBayes Factor > 100"),
        ("Validated\nHamiltonian", c_blue, "Result", "Final Selection:\n$M_4$: >99% (Correct)\n$M_1$: <1% (Rejected)"),
    ]

    for i, (title, color, header, text) in enumerate(nodes):
        x_coord = x_start + i * (box_w + gap)
        ax.add_patch(
            FancyBboxPatch(
                (x_coord + 0.05, y_top - 0.05),
                box_w,
                box_h,
                boxstyle="round,pad=0.1",
                fc="#cccccc",
                ec="none",
                zorder=9,
            )
        )
        ax.add_patch(
            FancyBboxPatch(
                (x_coord, y_top),
                box_w,
                box_h,
                boxstyle="round,pad=0.1",
                ec="#333333",
                fc=color,
                lw=1.5,
                zorder=10,
            )
        )
        ax.text(
            x_coord + box_w / 2,
            y_top + box_h / 2,
            title,
            ha="center",
            va="center",
            fontweight="bold",
            color="#222222",
            zorder=11,
        )

        ax.add_patch(patches.Rectangle((x_coord, y_bot), box_w, box_h * 1.2, ec="#999999", fc="white", zorder=5))
        ax.add_patch(
            patches.Rectangle((x_coord, y_bot + box_h * 1.2 - 0.3), box_w, 0.3, fc=color, alpha=0.6, zorder=6)
        )
        ax.text(
            x_coord + box_w / 2,
            y_bot + box_h * 1.2 - 0.15,
            header,
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            color="#444444",
            zorder=7,
        )
        ax.text(
            x_coord + box_w / 2,
            y_bot + box_h * 0.5,
            text,
            ha="center",
            va="center",
            fontsize=9,
            color="#444444",
            zorder=7,
        )

        ax.plot([x_coord + box_w / 2, x_coord + box_w / 2], [y_top, y_bot + box_h * 1.2], ":", color="#AAAAAA", lw=1.5, zorder=1)

        if i < len(nodes) - 1:
            ax.add_patch(
                FancyArrowPatch(
                    (x_coord + box_w, y_top + box_h / 2),
                    (x_coord + box_w + gap, y_top + box_h / 2),
                    arrowstyle="-|>",
                    mutation_scale=15,
                    color="#333333",
                    zorder=10,
                )
            )

    db_x = x_start + 2.5 * (box_w + gap)
    db_y = 4.5
    ax.add_patch(patches.Rectangle((db_x - 0.75, db_y - 0.4), 1.5, 0.8, fc=c_db, ec="#999999", zorder=1))
    ax.add_patch(patches.Ellipse((db_x, db_y + 0.4), 1.5, 0.3, fc="white", ec="#999999", zorder=2))
    ax.add_patch(patches.Ellipse((db_x, db_y - 0.4), 1.5, 0.3, fc=c_db, ec="#999999", zorder=1))
    ax.text(db_x, db_y, "Training Data\n(Structure $\\to$ $J_{ij}$)", ha="center", va="center", fontweight="bold", fontsize=9, color="#555555", zorder=3)

    end_x = x_start + 5 * (box_w + gap) + box_w / 2
    ax.add_patch(
        FancyArrowPatch(
            (end_x, y_top + box_h),
            (db_x + 0.8, db_y),
            connectionstyle="arc3,rad=-0.2",
            arrowstyle="->",
            mutation_scale=15,
            color="#27ae60",
            lw=2,
            linestyle="--",
            zorder=5,
        )
    )

    hyp_x = x_start + 1 * (box_w + gap) + box_w / 2
    ax.add_patch(
        FancyArrowPatch(
            (db_x - 0.8, db_y),
            (hyp_x, y_top + box_h),
            connectionstyle="arc3,rad=-0.2",
            arrowstyle="->",
            mutation_scale=15,
            color="#27ae60",
            lw=2,
            linestyle="--",
            zorder=5,
        )
    )

    ax.text(
        db_x,
        5.5,
        "Closed-Loop Feedback: Refine Priors",
        ha="center",
        color="#27ae60",
        fontweight="bold",
        bbox=dict(fc="white", ec="none", alpha=0.8),
    )
    ax.text(0.2, y_top + box_h / 2, "(a) Conceptual\nWorkflow", fontsize=12, fontweight="bold", ha="center", va="center", rotation=90)
    ax.text(0.2, y_bot + box_h / 2, "(b) Example:\nFe-O Lattice", fontsize=12, fontweight="bold", ha="center", va="center", rotation=90)

    plt.tight_layout()
    return fig


def _draw_heatmap_panel(ax, x0, y0, w, h):
    xs = np.linspace(0.0, 1.0, 120)
    ys = np.linspace(0.0, 1.0, 120)
    xx, yy = np.meshgrid(xs, ys)
    ridge = np.exp(-((yy - (0.23 + 0.48 * xx + 0.08 * np.sin(5 * xx))) ** 2) / 0.01)
    branch = 0.6 * np.exp(-((yy - (0.68 - 0.32 * xx)) ** 2) / 0.015)
    img = ridge + branch
    ax.imshow(img, extent=(x0, x0 + w, y0, y0 + h), origin="lower", cmap="Blues", alpha=0.95, zorder=1)

    pts = np.array(
        [
            [0.10, 0.18], [0.18, 0.28], [0.28, 0.25], [0.36, 0.36], [0.42, 0.30],
            [0.52, 0.48], [0.62, 0.41], [0.72, 0.55], [0.79, 0.50], [0.87, 0.62],
        ]
    )
    pts[:, 0] = x0 + pts[:, 0] * w
    pts[:, 1] = y0 + pts[:, 1] * h
    ax.scatter(pts[:, 0], pts[:, 1], s=22, c="white", edgecolors="#0b5394", linewidths=1.0, zorder=3)
    ax.text(x0 + 0.08 * w, y0 + 0.86 * h, "JCNS-style\nLog-GP", fontsize=11, fontweight="bold", color="#173f5f", va="top")


def _draw_inference_panel(ax, x0, y0, w, h):
    x = np.linspace(x0 + 0.08 * w, x0 + 0.92 * w, 200)
    t = (x - x.min()) / (x.max() - x.min())
    y_main = y0 + h * (0.22 + 0.46 * t)
    y_alt1 = y0 + h * (0.28 + 0.33 * t + 0.05 * np.sin(4 * np.pi * t))
    y_alt2 = y0 + h * (0.72 - 0.30 * t)

    ax.plot(x, y_alt1, color="#f6b26b", lw=2.0, alpha=0.9)
    ax.plot(x, y_alt2, color="#b4a7d6", lw=2.0, alpha=0.9)
    ax.plot(x, y_main, color="#cc0000", lw=3.2)

    bar_x = x0 + 0.73 * w
    bars = [0.18, 0.22, 0.60]
    colors = ["#f6b26b", "#b4a7d6", "#cc0000"]
    for i, (height, color) in enumerate(zip(bars, colors)):
        bx = bar_x + i * 0.07 * w
        ax.add_patch(patches.Rectangle((bx, y0 + 0.10 * h), 0.045 * w, height * h, fc=color, ec="none", alpha=0.95))
    ax.text(x0 + 0.08 * w, y0 + 0.86 * h, "Physics-aware\ninference", fontsize=11, fontweight="bold", color="#7a1f1f", va="top")


def _draw_audit_panel(ax, x0, y0, w, h):
    for cx, cy, r, alpha in [(0.32, 0.60, 0.18, 0.10), (0.55, 0.36, 0.22, 0.08), (0.72, 0.72, 0.16, 0.07)]:
        ax.add_patch(patches.Circle((x0 + cx * w, y0 + cy * h), r * min(w, h), fc="#d9ead3", ec="none", alpha=alpha))

    curve_x = np.linspace(x0 + 0.12 * w, x0 + 0.88 * w, 150)
    t = (curve_x - curve_x.min()) / (curve_x.max() - curve_x.min())
    curve_y = y0 + h * (0.25 + 0.22 * t + 0.06 * np.sin(2.3 * np.pi * t))
    ax.plot(curve_x, curve_y, color="#38761d", lw=2.4)

    probe_x = x0 + 0.58 * w
    probe_y = y0 + 0.48 * h
    ax.scatter([probe_x], [probe_y], s=70, c="#ffd966", edgecolors="#a61c00", linewidths=1.6, zorder=4)
    ax.annotate(
        "",
        xy=(probe_x, probe_y),
        xytext=(x0 + 0.28 * w, y0 + 0.78 * h),
        arrowprops=dict(arrowstyle="->", lw=2.0, color="#a61c00"),
    )

    shield = np.array(
        [
            [0.80, 0.76], [0.88, 0.76], [0.91, 0.67], [0.84, 0.56], [0.77, 0.67],
        ]
    )
    shield[:, 0] = x0 + shield[:, 0] * w
    shield[:, 1] = y0 + shield[:, 1] * h
    ax.add_patch(patches.Polygon(shield, closed=True, fc="#93c47d", ec="#274e13", lw=1.5))
    ax.text(x0 + 0.84 * w, y0 + 0.67 * h, "?", ha="center", va="center", fontsize=12, fontweight="bold", color="#274e13")
    ax.text(x0 + 0.08 * w, y0 + 0.86 * h, "Guarded\nfalsification", fontsize=11, fontweight="bold", color="#274e13", va="top")


def create_toc_figure():
    """Create a simple TOC graphic centered on the paper's three control stages."""
    fig, ax = plt.subplots(figsize=(9.5, 4.2), dpi=300)
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 9.5)
    ax.set_ylim(0, 4.2)
    ax.axis("off")

    panels = [
        (0.35, 0.55, 2.75, 2.65, "#d9eaf7", "Discovery"),
        (3.40, 0.55, 2.75, 2.65, "#f9dfdc", "Inference"),
        (6.45, 0.55, 2.70, 2.65, "#deefd5", "Audit"),
    ]

    for x0, y0, w, h, color, title in panels:
        ax.add_patch(
            FancyBboxPatch(
                (x0, y0),
                w,
                h,
                boxstyle="round,pad=0.03,rounding_size=0.18",
                fc=color,
                ec="#2f2f2f",
                lw=1.6,
            )
        )
        ax.text(x0 + 0.12, y0 + h + 0.20, title, fontsize=14, fontweight="bold", color="#1f1f1f")

    _draw_heatmap_panel(ax, 0.35, 0.55, 2.75, 2.65)
    _draw_inference_panel(ax, 3.40, 0.55, 2.75, 2.65)
    _draw_audit_panel(ax, 6.45, 0.55, 2.70, 2.65)

    for x1, x2 in [(3.12, 3.33), (6.17, 6.38)]:
        ax.add_patch(
            FancyArrowPatch((x1, 1.88), (x2, 1.88), arrowstyle="-|>", mutation_scale=16, lw=2.2, color="#333333")
        )

    ax.text(
        4.75,
        3.92,
        "Autonomous neutron spectroscopy with hybrid control",
        ha="center",
        va="top",
        fontsize=17,
        fontweight="bold",
        color="#111111",
    )
    ax.text(
        4.75,
        0.18,
        "Agnostic mapping localizes signal, physics planning resolves models, and a guarded audit layer breaks algorithmic myopia.",
        ha="center",
        va="bottom",
        fontsize=10.5,
        color="#333333",
    )
    plt.tight_layout(pad=0.2)
    return fig


def _save_figure(fig, output_base: Path):
    output_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_base.with_suffix(".png"), dpi=300, bbox_inches="tight", facecolor="white", edgecolor="none")
    if output_base.suffix.lower() == ".pdf":
        fig.savefig(output_base, bbox_inches="tight", facecolor="white", edgecolor="none")


def main():
    parser = argparse.ArgumentParser(description="Create workflow and TOC figures.")
    parser.add_argument("--save-dir", default="figures", help="Directory for generated outputs.")
    parser.add_argument("--toc-only", action="store_true", help="Generate only the TOC figure.")
    args = parser.parse_args()

    save_dir = Path(args.save_dir)
    if not save_dir.is_absolute():
        save_dir = (Path.cwd() / save_dir).resolve()
    save_dir.mkdir(parents=True, exist_ok=True)

    if args.toc_only:
        fig = create_toc_figure()
        fig.savefig(save_dir / "figure_toc.png", dpi=300, bbox_inches="tight", facecolor="white", edgecolor="none")
        plt.close(fig)
        print(f"Saved: {save_dir / 'figure_toc.png'}")
        return

    output_dirs = [save_dir]
    repo_root = Path.cwd().resolve()
    mirror_dir = repo_root / "paper" / "figures"
    if mirror_dir.exists() and mirror_dir not in output_dirs:
        output_dirs.append(mirror_dir)

    for out_dir in output_dirs:
        render_workflow_figure(out_dir / "closed_loop_workflow.png")
        render_workflow_figure(out_dir / "closed_loop_workflow.pdf")
    print(f"Saved: {save_dir / 'closed_loop_workflow.png'}")

    fig2 = create_swimlane_figure()
    fig2.savefig(save_dir / "workflow_with_example.png", dpi=150, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig2)
    print(f"Saved: {save_dir / 'workflow_with_example.png'}")

    fig3 = create_toc_figure()
    fig3.savefig(save_dir / "figure_toc.png", dpi=300, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig3)
    print(f"Saved: {save_dir / 'figure_toc.png'}")


if __name__ == "__main__":
    main()
