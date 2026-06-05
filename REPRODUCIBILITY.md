# Reproducibility

This paper-facing bundle is designed to let a reviewer inspect:

- the manuscript source
- the exact figures referenced by the current manuscript snapshot
- the archived JSON/CSV artifacts behind the quantitative claims
- the paper-facing scripts used to generate figures and summaries

## Canonical Entry Points

- Main manuscript:
  - [paper/digital_discovery_paper.md](paper/digital_discovery_paper.md)
- Supplementary information:
  - [paper/TAS-AI_Digital_Discovery_SI.md](paper/TAS-AI_Digital_Discovery_SI.md)
- Figure assets:
  - [paper/figures/](paper/figures/)
- Paper-facing scripts:
  - [paper/scripts/](paper/scripts/)
- Pinned environment:
  - [environment.yml](environment.yml)
- Archived data:
  - [paper/data/](paper/data/)

## Build the Manuscript

The manuscript subtree is self-contained. From the repo root:

```bash
cd paper
bash scripts/build_manuscript.sh
```

This uses:

- [paper/Dockerfile.pandoc](paper/Dockerfile.pandoc)
- [paper/scripts/build_manuscript.sh](paper/scripts/build_manuscript.sh)
- [environment.yml](environment.yml) for the pinned paper-facing Python stack

For the PySpinW-backed NiPS3 benchmark, the base environment is supplemented by
a compatible local `pyspinw` source checkout exposed through `PYSPINW_PATH` (or
otherwise added to `sys.path`), because that backend is consumed from source in
the current workflow.

## Main Archived Data

The main paper tables and figure summaries are backed by:

- [paper/data/final/benchmark_summary_fair_analytic_20260218.json](paper/data/final/benchmark_summary_fair_analytic_20260218.json)
- [paper/data/final/benchmark_summary_fair_pyspinw_20260402c.json](paper/data/final/benchmark_summary_fair_pyspinw_20260402c.json)
- [paper/data/final/benchmark_tasai_analytic_sunny_20260318.json](paper/data/final/benchmark_tasai_analytic_sunny_20260318.json)
- [paper/data/final/benchmark_tasai_pyspinw_20260402d.json](paper/data/final/benchmark_tasai_pyspinw_20260402d.json)
- [paper/data/final/time_aware_refinement_full_20260327.json](paper/data/final/time_aware_refinement_full_20260327.json)
- [paper/data/final/time_aware_search_results_20260327.json](paper/data/final/time_aware_search_results_20260327.json)
- [paper/data/final/overseer_loggpfix_20260327_final_summary.json](paper/data/final/overseer_loggpfix_20260327_final_summary.json)

## NiPS3 Structure-to-Discrimination Example

The added NiPS3 workflow example is backed by:

- [simulations/data/nips3_mp676040.cif](simulations/data/nips3_mp676040.cif)
- [simulations/nips3_hk0_pyspinw_benchmark.py](simulations/nips3_hk0_pyspinw_benchmark.py)
- [simulations/nips3_gk_pipeline.py](simulations/nips3_gk_pipeline.py)
- [run_logs/nips3_hk0_pyspinw_local.json](run_logs/nips3_hk0_pyspinw_local.json)
- [run_logs/nips3_gk_pipeline_local.json](run_logs/nips3_gk_pipeline_local.json)
- [paper/scripts/plot_nips3_posterior_evolution.py](paper/scripts/plot_nips3_posterior_evolution.py)
- [paper/figures/nips3_hk0_posterior_evolution.png](paper/figures/nips3_hk0_posterior_evolution.png)

The HK0 benchmark demonstrates structure-informed candidate generation from the
NiPS3 crystal structure followed by one-plane model discrimination within the
`J1`, `J1+J3`, `J1+J2+J3`, and `J1+J2+J3+D` family.

## Section 5 Ablation Archives

The Section 5 discussion is backed by:

- original one-seed ghost-optic archive:
  - [paper/data/ablation_runs/ghost_optic](paper/data/ablation_runs/ghost_optic)
- original one-seed cleaned bilayer archive:
  - [paper/data/ablation_runs/bilayer_fm_cleaned](paper/data/ablation_runs/bilayer_fm_cleaned)
- multi-model trap archive:
  - [paper/data/ablation_runs/multimodel_trap](paper/data/ablation_runs/multimodel_trap)
  - seeded initial-rank state used to construct the §S5.3 trap (required to reproduce the table from scratch):
    [paper/data/multimodel_trap_state_20260403.json](paper/data/multimodel_trap_state_20260403.json)
- five-seed ghost-optic rerun:
  - [paper/data/ablation_runs/ghost_optic_5seed_20260415c](paper/data/ablation_runs/ghost_optic_5seed_20260415c)
- five-seed bilayer rerun:
  - [paper/data/ablation_runs/bilayer_fm_5seed_20260415c](paper/data/ablation_runs/bilayer_fm_5seed_20260415c)

## Coverage and Sensitivity Checks

The SI robustness/calibration additions are backed by:

- [paper/data/laplace_coverage_refinement_20260415.json](paper/data/laplace_coverage_refinement_20260415.json)
- [paper/data/reviewer_sensitivity_20260403.json](paper/data/reviewer_sensitivity_20260403.json)

## Closed-Loop Drivers and Physics Backends

The manuscript-specific closed-loop drivers live under this repo at
[paper/scripts/](paper/scripts/):

- `toy_closed_loop.py` — end-to-end closed-loop pilot used for Figure 9
  (fixed 13+15+N handoff) and Figure 10 (90-measurement overseer run,
  four-model candidate set with the `[0.10, 0.10, 0.10, 0.70]` prior).
- `run_audit_ablation.py` — harness for the §5.3 ablations (ghost-optic,
  bilayer ferromagnet, multi-model trap).
- `toy_closed_loop_llm_overseer.py` — overseer-mode wrapper.
- `exchange_path_analysis.py` — Goodenough–Kanamori exchange-path
  enumeration used for Figure 13.
- `simulations/create_workflow_figure.py` — Figure 1 workflow diagram.
- `plot_nips3_posterior_evolution.py` — SI posterior-evolution figure for
  the NiPS3 one-plane HK0 benchmark.

The analytic spin-wave physics used by these drivers is upstreamed into
the library so the closed-loop pilots can be rerun without copying
physics code out of this repo:

- `tasai.physics.SquareLatticeAFM` — Néel-phase J₁-J₂-D AFM on the
  square lattice (§3.6 / Fig 10).
- `tasai.physics.SquareFMBilayer` — square-lattice bilayer ferromagnet
  with acoustic + optic branches and L-dependent weights (§5.3.2).

## Mailbox / Overseer Watcher Tools

A sanitized reference implementation of the mailbox-backed LLM audit
path used in the §5 overseer experiments lives under
[scripts/](scripts/). Referee 3 specifically flagged these as missing
in the original bundle; they are now included and described in
[scripts/README_mailbox_tools.md](scripts/README_mailbox_tools.md).
The three scripts cited in SI Note §7.2 are:

- [scripts/llm_danse2_watcher.py](scripts/llm_danse2_watcher.py) — the
  mailbox watcher that polls a mailbox endpoint, runs local CLI-backed
  LLMs, and posts suggestions or overseer decisions back.
- [scripts/llm_mailbox_client.py](scripts/llm_mailbox_client.py) —
  minimal helper for checking mailbox status, posting prompts, and
  retrieving suggestions.
- [scripts/llm_audit_mailbox_runner.py](scripts/llm_audit_mailbox_runner.py) —
  local watcher used for the audit-ablation batches.

The supporting batch worker, campaign manager, foreground executor,
and supervisor are included alongside for completeness; configuration
notes (mailbox URL, token, CLI defaults including `gpt-5.2-codex` for
Codex runs) are in `README_mailbox_tools.md`. The scientific results
do not depend on this exact transport layer — equivalent direct-API
or alternative service-mediated implementations are possible.

## Citation Audit

A read-only citation checker that diffs `paper/references.bib` against
Crossref (author lists, year, DOIs) and scans the two markdown sources
for unresolved or unused `[@key]` citations is available at
[paper/scripts/check_citations.py](paper/scripts/check_citations.py).
It uses only the Python standard library and returns a non-zero exit
code when warnings are present.

## Relationship to the Code Repo

This repo does not duplicate the full TAS-AI library source. The public code repo is:

- [usnistgov/tasai](https://github.com/usnistgov/tasai)

The public paper-bundle mirror is:

- [usnistgov/paper-tasai](https://github.com/usnistgov/paper-tasai)

The manuscript text points to those two public repositories directly:

- `usnistgov/tasai` for the reusable library code
- `usnistgov/paper-tasai` for manuscript sources, paper-facing scripts, archived data, and provenance artifacts
