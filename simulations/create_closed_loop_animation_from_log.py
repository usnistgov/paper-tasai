#!/usr/bin/env python3
"""
Generate a closed-loop animation from a toy_closed_loop log.
"""

import argparse
import re
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

from toy_closed_loop import (
    SquareLatticeDispersion,
    create_toy_structure,
    generate_hypotheses,
    init_tas,
    TAS,
    fit_model_parameters,
    create_symmetry_seed_points,
)


PLANNED_RE = re.compile(
    r"\(h,k\)\s+=\s+\((?P<h>[-\d.]+),\s+(?P<k>[-\d.]+)\),\s+E\s+=\s+(?P<E>[-\d.]+)"
)
MEASURED_RE = re.compile(
    r"E=\s*(?P<E>[-\d.]+)\s+meV:\s+I\s+=\s+(?P<I>[-\d.]+)\s+±\s+(?P<err>[-\d.]+)"
)


def parse_log(log_path: Path):
    planned = []
    measured = []
    fitted_params = {}
    current_model = None
    for line in log_path.read_text().splitlines():
        match = PLANNED_RE.search(line)
        if match:
            planned.append({
                "h": float(match.group("h")),
                "k": float(match.group("k")),
                "E": float(match.group("E")),
            })
            continue
        match = MEASURED_RE.search(line)
        if match:
            measured.append({
                "E": float(match.group("E")),
                "intensity": float(match.group("I")),
                "uncertainty": float(match.group("err")),
            })
            continue

        if "fitted" in line and ":" in line:
            current_model = line.strip().split(":")[0]
            fitted_params.setdefault(current_model, {})
            continue
        if current_model and "=" in line and "meV" in line:
            parts = line.strip().split("=")
            if len(parts) >= 2:
                name = parts[0].strip()
                value_str = parts[1].split("±")[0].strip().split()[0]
                try:
                    fitted_params[current_model][name] = float(value_str)
                except ValueError:
                    pass
    if not planned or not measured:
        raise ValueError(f"No measurements found in {log_path}")
    return planned, measured, fitted_params


def build_measurements(planned, measured, candidates):
    if len(measured) > len(planned):
        extra = len(measured) - len(planned)
        seed_points = create_symmetry_seed_points(
            candidates,
            total_budget=extra,
            fraction=1.0,
            min_points=extra
        )
        planned = seed_points + planned

    n = min(len(planned), len(measured))
    measurements = []
    for idx in range(n):
        meas = {
            "h": planned[idx]["h"],
            "k": planned[idx]["k"],
            "E": planned[idx]["E"],
            "intensity": measured[idx]["intensity"],
            "uncertainty": measured[idx]["uncertainty"],
        }
        measurements.append(meas)
    return measurements


def compute_posteriors(meas_subset, candidates, fitted_params):
    results = {}
    for cand in candidates:
        free_params = []
        if cand["params"]["J1"] != 0:
            free_params.append("J1")
        if cand["params"]["J2"] != 0:
            free_params.append("J2")
        if cand["params"]["D"] != 0:
            free_params.append("D")

        model = SquareLatticeDispersion(**cand["params"])
        model_key = cand["name"].split(":")[0]
        if model_key in fitted_params:
            params = fitted_params[model_key]
            if "J1" in params:
                model.J1 = params["J1"]
            if "J2" in params:
                model.J2 = params["J2"]
            if "D" in params:
                model.D = params["D"]
        param_bounds = None
        if cand["name"].startswith("M4"):
            param_bounds = {
                "J1": (4.0, 6.0),
                "J2": (0.1, 2.0),
                "D": (0.02, 0.5),
            }

        chi2 = sum(
            ((m["intensity"] - model.intensity(m["h"], m["k"], m["E"],
                                               use_realistic_resolution=False)) / m["uncertainty"]) ** 2
            for m in meas_subset
        )

        n_params = len(free_params)
        n_data = max(len(meas_subset), 1)
        bic = chi2 + n_params * np.log(n_data)
        log_post = (-0.5 * bic) + np.log(cand["prior"])
        results[cand["name"]] = log_post

    log_posts = [results[name] for name in results.keys()]
    max_log = max(log_posts)
    posteriors = np.exp(np.array(log_posts) - max_log)
    posteriors /= posteriors.sum()
    return posteriors


def render_animation(measurements, candidates, fitted_params, output_path: Path):
    true_model = SquareLatticeDispersion(J1=5.0, J2=0.8, D=0.1, S=2.5)
    posteriors_history = []
    for n_meas in range(1, len(measurements) + 1):
        posteriors_history.append(
            compute_posteriors(measurements[:n_meas], candidates, fitted_params)
        )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    h_plot = np.linspace(0.5, 1.7, 100)
    omega_true = [true_model.omega(h, h) for h in h_plot]
    colors = ["#ff6b6b", "#ffa94d", "#4ecdc4", "#45b7d1"]
    names = ["M1: NN", "M2: NN+D", "M3: J1-J2", "M4: Full"]

    def init():
        ax1.clear()
        ax2.clear()
        return []

    def update(frame):
        ax1.clear()
        ax2.clear()
        n = min(frame + 1, len(measurements))

        ax1.plot(h_plot, omega_true, "k-", lw=2, label="True dispersion")
        for meas in measurements[:n]:
            ax1.scatter(
                meas["h"], meas["E"], s=80, c="red", alpha=0.8,
                edgecolors="black", zorder=5
            )
        ax1.set_xlabel("(h, h, 0) [r.l.u.]")
        ax1.set_ylabel("E [meV]")
        ax1.set_xlim(0.5, 1.7)
        ax1.set_ylim(0, 50)
        ax1.set_title(f"Measurements: {n}/{len(measurements)}")

        if n > 0 and n <= len(posteriors_history):
            posteriors = posteriors_history[n - 1]
            bars = ax2.barh(names, posteriors, color=colors, edgecolor="black")
            for bar, prob in zip(bars, posteriors):
                if prob > 0.01:
                    ax2.text(
                        bar.get_width() + 0.02,
                        bar.get_y() + bar.get_height() / 2,
                        f"{prob:.1%}",
                        va="center",
                        fontsize=10,
                    )
        ax2.set_xlim(0, 1.1)
        ax2.set_xlabel("Posterior Probability")
        ax2.set_title("Model Probabilities")

        plt.suptitle("Closed-Loop Model Discrimination", fontsize=14, fontweight="bold")
        plt.tight_layout()
        return []

    anim = FuncAnimation(
        fig, update, init_func=init,
        frames=len(measurements) + 3,
        interval=600, blit=False,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    anim.save(output_path, writer=PillowWriter(fps=2))
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Create closed-loop animation from a log file")
    parser.add_argument("--log-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    init_tas(False)
    structure = create_toy_structure()
    candidates = generate_hypotheses(structure)
    uniform = 1.0 / len(candidates)
    for cand in candidates:
        cand["prior"] = uniform

    planned, measured, fitted_params = parse_log(args.log_file)
    measurements = build_measurements(planned, measured, candidates)
    render_animation(measurements, candidates, fitted_params, args.output)


if __name__ == "__main__":
    main()
