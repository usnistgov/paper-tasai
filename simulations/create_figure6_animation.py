#!/usr/bin/env python
"""
Create an animation for Figure 6 showing hybrid exploration.
"""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

THIS_DIR = Path(__file__).parent
FIGURES_DIR = THIS_DIR.parent / "figures"
FIGURES_DIR.mkdir(exist_ok=True)


def _load_hybrid_module():
    module_path = THIS_DIR / "hybrid_exploration_demo.py"
    spec = importlib.util.spec_from_file_location("hybrid_module", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load hybrid_exploration_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[call-arg]
    return module


def generate_data(seed: int = 42):
    hybrid = _load_hybrid_module()
    model = hybrid.ToyDispersion(J1=8.0, J2=1.2, D=0.5)
    agnostic_meas, gp = hybrid.run_agnostic_phase(model, n_measurements=15, seed=seed)
    all_meas, param_history = hybrid.run_informed_phase(
        model, gp, agnostic_meas, n_measurements=35, seed=seed
    )
    return model, agnostic_meas, all_meas, param_history


def build_animation(seed: int = 42, fps: int = 2):
    model, agnostic_meas, all_meas, param_history = generate_data(seed=seed)
    agnostic_pts = np.array([[m["h"], m["E"]] for m in agnostic_meas])
    informed_pts = np.array([[m["h"], m["E"]] for m in all_meas[len(agnostic_meas) :]])
    total_measurements = len(all_meas)
    phase_boundary = len(agnostic_meas)
    phase2_frames = 5
    frames_total = total_measurements + phase2_frames  # pause for Phase 2

    measurement_x = np.arange(phase_boundary, phase_boundary + len(param_history))
    j1_err = (np.array([p[0] for p in param_history]) - model.J1) / model.J1 * 100
    j2_err = (np.array([p[1] for p in param_history]) - model.J2) / model.J2 * 100
    d_err = (np.array([p[2] for p in param_history]) - model.D) / model.D * 100

    h_grid = np.linspace(0.02, 0.48, 40)
    e_grid = np.linspace(2, 25, 40)
    H_mesh, E_mesh = np.meshgrid(h_grid, e_grid)
    intensity = np.zeros_like(H_mesh)
    for i, h in enumerate(h_grid):
        for j, e in enumerate(e_grid):
            intensity[j, i] = model.intensity(h, e)

    h_plot = np.linspace(0, 0.5, 200)
    omega_true = [model.omega(h) for h in h_plot]

    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except OSError:
        plt.style.use("seaborn-whitegrid")
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(12, 5))
    fig.subplots_adjust(top=0.88)
    phase_text = fig.suptitle("Phase 1 – Agnostic GP exploration", fontsize=16, weight="bold")

    cmap = ax_left.contourf(H_mesh, E_mesh, intensity, levels=20, cmap="viridis", alpha=0.7)
    true_line, = ax_left.plot(h_plot, omega_true, "w--", linewidth=2, label="True dispersion")
    ax_left.set_xlabel("H [r.l.u.]")
    ax_left.set_ylabel("Energy [meV]")
    ax_left.set_title("Measured S(Q, ω)")
    ax_left.set_xlim(0, 0.5)
    ax_left.set_ylim(0, 28)

    ag_scatter = ax_left.scatter([], [], c="red", s=70, edgecolors="white", linewidths=0.8)
    inf_scatter = ax_left.scatter([], [], c="cyan", s=70, edgecolors="black", linewidths=0.8, marker="s")
    phase2_patch = Rectangle((0, 0), width=0.5, height=28, facecolor="orange", alpha=0.2, visible=False, zorder=1)
    ax_left.add_patch(phase2_patch)
    current_point = ax_left.scatter([], [], facecolors="none", edgecolors="yellow", s=200, linewidths=1.5)
    fig.colorbar(cmap, ax=ax_left, shrink=0.8, label="Intensity (a.u.)")

    init_J1, init_J2, init_D = param_history[0]

    def omega_from_params(params):
        temp = model.__class__(*params)
        return [temp.omega(h) for h in h_plot]

    current_params = (init_J1, init_J2, init_D)
    omega_init = omega_from_params(current_params)
    model_line, = ax_left.plot(h_plot, omega_init, color="gold", linestyle="--", linewidth=2,
                               alpha=0.0, label="Current model")
    phase2_text = ax_left.text(0.02, 0.02, "", transform=ax_left.transAxes, fontsize=10,
                               bbox=dict(boxstyle="round", facecolor="white", alpha=0.8), visible=False)
    final_J1, final_J2, final_D = param_history[-1]

    legend_handles = [
        true_line, model_line,
        Line2D([], [], marker="o", color="white", markerfacecolor="red", markeredgecolor="white",
               markersize=8, linestyle="", label="Phase 1 pts"),
        Line2D([], [], marker="s", color="black", markerfacecolor="cyan", markeredgecolor="black",
               markersize=8, linestyle="", label="Phase 3 pts"),
    ]
    ax_left.legend(handles=legend_handles, loc="upper left", fontsize=10)

    ax_right.axhspan(-5, 5, color="lightgreen", alpha=0.3, label="±5% band")
    ax_right.axvline(phase_boundary, color="black", linestyle="--", alpha=0.5)
    ax_right.set_xlim(phase_boundary - 1, phase_boundary + len(param_history))
    ax_right.set_ylim(-30, 40)
    ax_right.set_xlabel("Measurement number")
    ax_right.set_ylabel("Parameter error [%]")
    ax_right.set_title("Panel (d): parameter convergence")

    line_j1, = ax_right.plot([], [], "b-o", linewidth=2, markersize=4, label=r"$J_1$")
    line_j2, = ax_right.plot([], [], "r-s", linewidth=2, markersize=4, label=r"$J_2$")
    line_d, = ax_right.plot([], [], "g-^", linewidth=2, markersize=4, label="D")
    ax_right.legend(loc="upper right", fontsize=10)
    final_text = ax_right.text(0.02, 0.02, "", transform=ax_right.transAxes, fontsize=10,
                               bbox=dict(boxstyle="round", facecolor="white", alpha=0.8), visible=False)

    def update(frame: int):
        if frame < phase_boundary:
            meas_count = frame + 1
            phase_label = "Phase 1 – Agnostic GP exploration"
            phase2_patch.set_visible(False)
            phase2_text.set_visible(False)
            final_text.set_visible(False)
            model_line.set_alpha(0.0)
        elif frame < phase_boundary + phase2_frames:
            meas_count = phase_boundary
            phase_label = "Phase 2 – Model initialization"
            phase2_patch.set_visible(True)
            phase2_text.set_visible(True)
            phase2_text.set_text(fr"Initial fit:\n$J_1$ = {init_J1:.1f} meV\n$J_2$ = {init_J2:.1f} meV\n$D$ = {init_D:.2f} meV")
            final_text.set_visible(False)
            model_line.set_alpha(0.9)
        else:
            meas_count = frame - (phase2_frames - 1)
            phase_label = "Phase 3 – Physics-informed refinement"
            phase2_patch.set_visible(True)
            phase2_text.set_visible(False)
            model_line.set_alpha(0.9)
        phase_text.set_text(phase_label)

        if meas_count <= phase_boundary:
            params = param_history[0]
        else:
            idx = min(meas_count - phase_boundary, len(param_history) - 1)
            params = param_history[idx]
        if model_line.get_alpha() > 0:
            model_line.set_data(h_plot, omega_from_params(params))

        if meas_count <= phase_boundary:
            ag_offsets = agnostic_pts[:meas_count]
            inf_offsets = np.empty((0, 2))
        else:
            ag_offsets = agnostic_pts
            inf_offsets = informed_pts[: meas_count - phase_boundary]

        ag_scatter.set_offsets(ag_offsets if len(ag_offsets) else np.empty((0, 2)))
        inf_scatter.set_offsets(inf_offsets if len(inf_offsets) else np.empty((0, 2)))

        meas_index = max(min(meas_count - 1, total_measurements - 1), 0)
        current_pt = all_meas[meas_index]
        current_point.set_offsets([[current_pt["h"], current_pt["E"]]])

        mask = measurement_x <= meas_count
        if np.any(mask):
            x_vals = measurement_x[mask]
            line_j1.set_data(x_vals, j1_err[mask])
            line_j2.set_data(x_vals, j2_err[mask])
            line_d.set_data(x_vals, d_err[mask])
        else:
            line_j1.set_data([], [])
            line_j2.set_data([], [])
            line_d.set_data([], [])

        if meas_count >= total_measurements:
            final_text.set_visible(True)
            final_text.set_text(fr"Final fit:\n$J_1$ = {final_J1:.2f} meV\n$J_2$ = {final_J2:.2f} meV\n$D$ = {final_D:.2f} meV")
        else:
            final_text.set_visible(False)

        return ag_scatter, inf_scatter, current_point, line_j1, line_j2, line_d, phase_text

    anim = FuncAnimation(fig, update, frames=frames_total, interval=700, blit=False)
    output_path = FIGURES_DIR / "figure6_animation.gif"
    anim.save(output_path, writer=PillowWriter(fps=fps))
    plt.close(fig)
    print(f"Saved animation -> {output_path}")


def main():
    fps = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    build_animation(seed=42, fps=fps)


if __name__ == "__main__":
    main()
