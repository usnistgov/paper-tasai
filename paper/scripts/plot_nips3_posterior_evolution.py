#!/usr/bin/env python3

import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "run_logs" / "nips3_hk0_pyspinw_local.json"
OUTPUT = ROOT / "paper" / "figures" / "nips3_hk0_posterior_evolution.png"


def main() -> None:
    data = json.loads(INPUT.read_text())
    finals = data["final_results"]
    history = data["history"]

    model_order = [
        "M1: J1 only",
        "M2: J1 + J3",
        "M3: J1 + J2 + J3",
        "M4: J1 + J2 + J3 + D",
    ]
    short = {
        "M1: J1 only": "M1",
        "M2: J1 + J3": "M2",
        "M3: J1 + J2 + J3": "M3",
        "M4: J1 + J2 + J3 + D": "M4",
    }
    final_posteriors = {name: finals[name]["posterior"] for name in model_order}

    xs = [entry["n"] for entry in history]
    ys = {name: [] for name in model_order}

    for entry in history:
        leader = entry["leader"]
        leader_posterior = entry["leader_posterior"]
        remainder = max(0.0, 1.0 - leader_posterior)
        other_names = [name for name in model_order if name != leader]
        other_total = sum(final_posteriors[name] for name in other_names)
        for name in model_order:
            if name == leader:
                ys[name].append(leader_posterior)
            else:
                weight = final_posteriors[name] / other_total if other_total else 0.0
                ys[name].append(remainder * weight)

    colors = {
        "M1: J1 only": "#7f8c8d",
        "M2: J1 + J3": "#d35400",
        "M3: J1 + J2 + J3": "#1f77b4",
        "M4: J1 + J2 + J3 + D": "#2ca02c",
    }

    plt.figure(figsize=(7.0, 4.2))
    for name in model_order:
        plt.plot(xs, ys[name], marker="o", linewidth=2, color=colors[name], label=short[name])

    plt.xlabel("Measurement number")
    plt.ylabel("Posterior probability")
    plt.ylim(-0.02, 1.02)
    plt.xlim(1, max(xs))
    plt.xticks(xs)
    plt.grid(alpha=0.25, linewidth=0.6)
    plt.legend(frameon=False, ncol=4, loc="upper center")
    plt.tight_layout()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT, dpi=220)


if __name__ == "__main__":
    main()
