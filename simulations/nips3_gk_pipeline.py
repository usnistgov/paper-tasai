#!/usr/bin/env python3
"""
Private NiPS3 structure-to-candidate-to-discrimination demo.

This is a lightweight revision-side benchmark intended to answer a narrow
question: can we show an end-to-end, non-LLM path that starts from a real
NiPS3 crystal structure, extracts Goodenough-Kanamori exchange-path cues, and
then performs data-driven discrimination among a small Hamiltonian family?

The downstream "measurement" model is deliberately compact and synthetic. It is
not a full spin-wave fit. The purpose is to exercise the pipeline structure:

    CIF -> structure -> GK path analysis -> candidate family -> active
    discrimination/refinement

Literature anchor:
- Materials Project dataset for NiPS3 (mp-676040) via OSTI page 1282919.
- Lançon et al., Phys. Rev. B 98, 134414 (2018). The reported exchange values
  use the opposite sign convention from TAS-AI. Here we convert to:
      J1 = -1.9 meV   (FM)
      J2 = +0.1 meV   (small AFM)
      J3 = +6.9 meV   (strong AFM)
      D  = +0.3 meV   (easy-axis anisotropy)
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np


LOG = logging.getLogger("nips3_gk_pipeline")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CIF = Path(__file__).resolve().parent / "data" / "nips3_mp676040.cif"


def _resolve_tasai_src() -> Path:
    candidates = [
        Path.cwd() / "deps" / "tasai",
        Path.home() / "tasai_nist_clean",
        Path("/work2/09870/williamratcliff/stampede3/tasai/src"),
    ]
    env = Path(str(Path.cwd()))  # placeholder to keep type checker happy
    env_str = None
    try:
        import os
        env_str = os.environ.get("TASAI_SRC")
    except Exception:
        env_str = None
    if env_str:
        candidates.insert(0, Path(env_str))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Could not locate TAS-AI source tree. Set TASAI_SRC or stage "
        "tasai_nist_clean / stampede3/tasai/src."
    )


TASAI_SRC = _resolve_tasai_src()
if str(TASAI_SRC) not in sys.path:
    sys.path.insert(0, str(TASAI_SRC))

from tasai.extensions.goodenough_kanamori import GoodenoughKanamoriAnalyzer


@dataclass(frozen=True)
class MeasurementChannel:
    name: str
    constant: float
    coeffs: Dict[str, float]
    sigma: float


CHANNELS: List[MeasurementChannel] = [
    MeasurementChannel("Gamma_gap", 1.2, {"J1": -0.10, "J2": 0.20, "J3": 0.15, "D": 4.20}, 0.18),
    MeasurementChannel("Gamma_upper", 2.4, {"J1": -0.20, "J2": 0.10, "J3": 0.45, "D": 1.20}, 0.20),
    MeasurementChannel("M_low", 0.7, {"J1": -0.85, "J2": 0.10, "J3": 0.55, "D": 0.30}, 0.18),
    MeasurementChannel("M_split", 1.4, {"J1": -0.35, "J2": 0.25, "J3": 0.65, "D": 0.80}, 0.18),
    MeasurementChannel("K_mid", 1.9, {"J1": -0.45, "J2": -0.30, "J3": 0.50, "D": 0.10}, 0.20),
    MeasurementChannel("K_upper", 3.1, {"J1": -0.25, "J2": 0.10, "J3": 0.85, "D": 0.30}, 0.20),
    MeasurementChannel("ZoneEdge_A", 2.6, {"J1": -0.55, "J2": 0.80, "J3": 0.30, "D": 0.05}, 0.22),
    MeasurementChannel("ZoneEdge_B", 1.7, {"J1": -0.20, "J2": 1.10, "J3": 0.15, "D": 0.15}, 0.22),
    MeasurementChannel("HighBand_A", 4.6, {"J1": -0.10, "J2": 0.05, "J3": 1.05, "D": 0.00}, 0.24),
    MeasurementChannel("HighBand_B", 5.1, {"J1": -0.15, "J2": -0.10, "J3": 0.95, "D": 0.20}, 0.24),
    MeasurementChannel("IntensityProbe_A", 0.9, {"J1": -0.60, "J2": 0.35, "J3": 0.40, "D": 0.00}, 0.18),
    MeasurementChannel("IntensityProbe_B", 1.3, {"J1": -0.15, "J2": 0.55, "J3": 0.25, "D": 0.25}, 0.18),
]


TRUTH_PARAMS = {"J1": -1.9, "J2": 0.1, "J3": 6.9, "D": 0.3}


def load_simple_cif(path: Path) -> Dict:
    lines = path.read_text().splitlines()
    cell = {}
    atom_headers: List[str] = []
    atom_rows: List[List[str]] = []

    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("_cell_length_a"):
            cell["a"] = float(s.split()[-1])
        elif s.startswith("_cell_length_b"):
            cell["b"] = float(s.split()[-1])
        elif s.startswith("_cell_length_c"):
            cell["c"] = float(s.split()[-1])
        elif s.startswith("_cell_angle_alpha"):
            cell["alpha"] = float(s.split()[-1])
        elif s.startswith("_cell_angle_beta"):
            cell["beta"] = float(s.split()[-1])
        elif s.startswith("_cell_angle_gamma"):
            cell["gamma"] = float(s.split()[-1])

    idx = 0
    while idx < len(lines):
        if lines[idx].strip() == "loop_":
            headers: List[str] = []
            j = idx + 1
            while j < len(lines) and lines[j].strip().startswith("_atom_site_"):
                headers.append(lines[j].strip())
                j += 1
            if headers:
                atom_headers = headers
                while j < len(lines):
                    s = lines[j].strip()
                    if not s or s.startswith("loop_") or s.startswith("_"):
                        break
                    atom_rows.append(s.split())
                    j += 1
                break
        idx += 1

    required = {"a", "b", "c", "alpha", "beta", "gamma"}
    if required - set(cell):
        raise ValueError(f"Incomplete CIF cell parameters in {path}")
    if not atom_headers or not atom_rows:
        raise ValueError(f"Could not find atom loop in {path}")

    alpha = math.radians(cell["alpha"])
    beta = math.radians(cell["beta"])
    gamma = math.radians(cell["gamma"])
    sin_gamma = math.sin(gamma)
    volume_term = (
        1
        + 2 * math.cos(alpha) * math.cos(beta) * math.cos(gamma)
        - math.cos(alpha) ** 2
        - math.cos(beta) ** 2
        - math.cos(gamma) ** 2
    )
    lattice = np.array(
        [
            [cell["a"], 0.0, 0.0],
            [cell["b"] * math.cos(gamma), cell["b"] * sin_gamma, 0.0],
            [
                cell["c"] * math.cos(beta),
                cell["c"] * (math.cos(alpha) - math.cos(beta) * math.cos(gamma)) / max(sin_gamma, 1.0e-8),
                cell["c"] * math.sqrt(max(volume_term, 0.0)) / max(sin_gamma, 1.0e-8),
            ],
        ],
        dtype=float,
    )

    col = {name: pos for pos, name in enumerate(atom_headers)}
    species = [row[col["_atom_site_type_symbol"]] for row in atom_rows]
    coords = np.array(
        [
            [
                float(row[col["_atom_site_fract_x"]]),
                float(row[col["_atom_site_fract_y"]]),
                float(row[col["_atom_site_fract_z"]]),
            ]
            for row in atom_rows
        ],
        dtype=float,
    )
    return {"name": path.stem, "lattice": lattice, "species": species, "coords": coords}


def summarize_paths(analyzer: GoodenoughKanamoriAnalyzer) -> List[Dict]:
    ranked = analyzer.rank_paths(analyzer.find_exchange_paths(max_distance=8.0, max_bridging=2, bond_cutoff=2.8))
    clusters = analyzer.cluster_paths(ranked)
    summary = []
    for idx, cluster in enumerate(clusters, 1):
        rep = cluster[0]
        summary.append(
            {
                "cluster": idx,
                "multiplicity": len(cluster),
                "distance_A": round(rep.distance, 4),
                "path_type": rep.path_type,
                "bridging_atoms": list(rep.bridging_atoms),
                "bond_angle_deg": round(rep.bond_angle, 2),
                "predicted_sign": rep.predicted_sign,
                "signed_strength": round(rep.signed_strength, 5),
                "gk_channel": rep.gk_channel,
            }
        )
    return summary


def literature_candidate_family() -> List[Dict]:
    return [
        {
            "name": "M1: J1 only",
            "terms": ("J1",),
            "prior": 0.10,
            "proposal_means": {"J1": -1.9},
            "proposal_sigma": {"J1": 0.8},
            "notes": "Nearest-neighbor-only baseline.",
        },
        {
            "name": "M2: J1 + J3",
            "terms": ("J1", "J3"),
            "prior": 0.25,
            "proposal_means": {"J1": -1.9, "J3": 6.9},
            "proposal_sigma": {"J1": 0.8, "J3": 2.0},
            "notes": "Dominant FM J1 plus strong AFM J3.",
        },
        {
            "name": "M3: J1 + J2 + J3",
            "terms": ("J1", "J2", "J3"),
            "prior": 0.25,
            "proposal_means": {"J1": -1.9, "J2": 0.1, "J3": 6.9},
            "proposal_sigma": {"J1": 0.8, "J2": 0.3, "J3": 2.0},
            "notes": "Adds small frustrated J2 channel.",
        },
        {
            "name": "M4: full model",
            "terms": ("J1", "J2", "J3", "D"),
            "prior": 0.40,
            "proposal_means": dict(TRUTH_PARAMS),
            "proposal_sigma": {"J1": 0.8, "J2": 0.3, "J3": 2.0, "D": 0.15},
            "notes": "Adds easy-axis anisotropy.",
        },
    ]


def channel_value(channel: MeasurementChannel, params: Dict[str, float]) -> float:
    total = channel.constant
    for term, coeff in channel.coeffs.items():
        total += coeff * params.get(term, 0.0)
    return float(total)


def synth_measurement(channel_idx: int, rng: np.random.Generator) -> Dict:
    channel = CHANNELS[channel_idx]
    truth = channel_value(channel, TRUTH_PARAMS)
    observed = float(rng.normal(truth, channel.sigma))
    return {
        "channel": channel.name,
        "index": channel_idx,
        "observed": observed,
        "truth": truth,
        "sigma": channel.sigma,
    }


def fit_model(model: Dict, measurements: Sequence[Dict]) -> Dict:
    terms = list(model["terms"])
    if not measurements:
        return {
            "fit": dict(model["proposal_means"]),
            "chi2": 0.0,
            "aic": 2 * len(terms),
            "log_posterior": math.log(model["prior"]),
        }

    A_rows = []
    b = []
    weights = []
    prior_mu = np.array([model["proposal_means"][term] for term in terms], dtype=float)
    prior_tau = np.array([model["proposal_sigma"][term] for term in terms], dtype=float)

    for meas in measurements:
        channel = CHANNELS[meas["index"]]
        A_rows.append([channel.coeffs.get(term, 0.0) for term in terms])
        b.append(meas["observed"] - channel.constant)
        weights.append(1.0 / max(meas["sigma"], 1.0e-6))

    A = np.asarray(A_rows, dtype=float)
    b_vec = np.asarray(b, dtype=float)
    W = np.diag(np.asarray(weights, dtype=float))
    reg = np.diag(1.0 / np.maximum(prior_tau, 1.0e-6))

    lhs = A.T @ W @ W @ A + reg.T @ reg
    rhs = A.T @ W @ W @ b_vec + reg.T @ reg @ prior_mu
    fit = np.linalg.solve(lhs, rhs)

    residual = (A @ fit - b_vec) * np.asarray(weights)
    chi2 = float(residual @ residual)
    k = len(terms)
    aic = chi2 + 2 * k
    log_prior_penalty = -0.5 * float(np.sum(((fit - prior_mu) / np.maximum(prior_tau, 1.0e-6)) ** 2))
    log_posterior = -0.5 * aic + math.log(model["prior"]) + log_prior_penalty

    return {
        "fit": {term: float(val) for term, val in zip(terms, fit)},
        "chi2": chi2,
        "aic": aic,
        "log_posterior": log_posterior,
    }


def normalize_posteriors(results: Dict[str, Dict]) -> None:
    logs = np.array([res["log_posterior"] for res in results.values()], dtype=float)
    max_log = float(np.max(logs))
    probs = np.exp(logs - max_log)
    probs /= max(float(probs.sum()), 1.0e-12)
    for prob, res in zip(probs, results.values()):
        res["posterior"] = float(prob)


def select_next_channel(candidates: Sequence[Dict], results: Dict[str, Dict], measured: set[int]) -> int:
    remaining = [idx for idx in range(len(CHANNELS)) if idx not in measured]
    best_idx = remaining[0]
    best_score = -1.0
    for idx in remaining:
        preds = []
        weights = []
        for model in candidates:
            res = results[model["name"]]
            params = {term: 0.0 for term in TRUTH_PARAMS}
            params.update(res["fit"])
            preds.append(channel_value(CHANNELS[idx], params))
            weights.append(res["posterior"])
        preds_arr = np.asarray(preds, dtype=float)
        w = np.asarray(weights, dtype=float)
        mean = float(np.sum(w * preds_arr))
        score = float(np.sum(w * (preds_arr - mean) ** 2))
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx


def run_demo(n_measurements: int, seed: int) -> Dict:
    structure = load_simple_cif(DEFAULT_CIF)
    analyzer = GoodenoughKanamoriAnalyzer(structure, default_oxidation={"Ni": "Ni2+"})
    path_summary = summarize_paths(analyzer)
    models = literature_candidate_family()

    rng = np.random.default_rng(seed)
    measurements: List[Dict] = []
    measured: set[int] = set()
    history = []

    bootstrap = [0, 2, 5]
    for idx in bootstrap[: min(len(bootstrap), n_measurements)]:
        meas = synth_measurement(idx, rng)
        measurements.append(meas)
        measured.add(idx)

    while len(measurements) < n_measurements:
        results = {model["name"]: fit_model(model, measurements) for model in models}
        normalize_posteriors(results)
        next_idx = select_next_channel(models, results, measured)
        meas = synth_measurement(next_idx, rng)
        measurements.append(meas)
        measured.add(next_idx)
        ranked = sorted(results.items(), key=lambda item: item[1]["posterior"], reverse=True)
        history.append(
            {
                "n": len(measurements),
                "selected_channel": CHANNELS[next_idx].name,
                "leader": ranked[0][0],
                "leader_posterior": ranked[0][1]["posterior"],
            }
        )

    final_results = {model["name"]: fit_model(model, measurements) for model in models}
    normalize_posteriors(final_results)
    ranked_final = sorted(final_results.items(), key=lambda item: item[1]["posterior"], reverse=True)

    return {
        "structure_name": structure["name"],
        "materials_project_id": "mp-676040",
        "source_dataset": "OSTI 1282919 / Materials Project",
        "truth_convention": "TAS-AI H = +J S_i·S_j, AFM positive",
        "truth_params": TRUTH_PARAMS,
        "gk_path_summary": path_summary,
        "candidate_family": models,
        "measurements": measurements,
        "history": history,
        "final_results": final_results,
        "winner": {
            "name": ranked_final[0][0],
            "posterior": ranked_final[0][1]["posterior"],
            "fit": ranked_final[0][1]["fit"],
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-measurements", type=int, default=8)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "run_logs" / "nips3_gk_pipeline.json",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    LOG.info("Using TAS-AI source: %s", TASAI_SRC)
    LOG.info("Loading CIF: %s", DEFAULT_CIF)

    result = run_demo(args.n_measurements, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))

    winner = result["winner"]
    LOG.info("Winner: %s (posterior %.1f%%)", winner["name"], 100.0 * winner["posterior"])
    LOG.info("Fit: %s", ", ".join(f"{k}={v:.3f}" for k, v in winner["fit"].items()))
    LOG.info("Wrote %s", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
