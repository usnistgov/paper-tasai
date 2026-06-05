# Reviewer Guide

This repository is meant to be a clean paper-facing bundle.

If you only want the shortest path through the evidence:

1. Read the current manuscript:
   - [paper/TAS-AI_Digital_Discovery.docx](paper/TAS-AI_Digital_Discovery.docx)
   - [paper/TAS-AI_Digital_Discovery_SI.docx](paper/TAS-AI_Digital_Discovery_SI.docx)
2. Check the figure assets used by the manuscript:
   - [paper/figures/](paper/figures/)
3. Check the archived data behind the claims:
   - [paper/data/final/](paper/data/final/)
   - [paper/data/ablation_runs/](paper/data/ablation_runs/)
4. If needed, inspect the paper-facing scripts:
   - [paper/scripts/](paper/scripts/)
5. If needed, inspect the markdown sources of record:
   - [paper/digital_discovery_paper.md](paper/digital_discovery_paper.md)
   - [paper/TAS-AI_Digital_Discovery_SI.md](paper/TAS-AI_Digital_Discovery_SI.md)
6. If needed, inspect the pinned paper environment:
   - [environment.yml](environment.yml)

## What Is In Scope Here

This repo includes:

- manuscript markdown
- rendered manuscript outputs
- exact figure files referenced by the manuscript
- archived benchmark/pilot/ablation JSON and CSV files
- paper-facing scripts used to generate figures and summaries
- a pinned paper-facing environment file

This repo intentionally excludes:

- operational mailbox logs and runtime state
- in-progress prompt experiments
- slides and cover letters
- old manuscript versions
- the full TAS-AI library source tree

A sanitized reference implementation of the overseer mailbox watcher
and its supporting CLI tools (referee 3's specific code-availability
request) is now included under `scripts/`; see the dedicated
subsection below.

## Key Provenance Pointers

### Main paper benchmark and pilot artifacts

- [paper/data/final/benchmark_summary_fair_analytic_20260218.json](paper/data/final/benchmark_summary_fair_analytic_20260218.json)
- [paper/data/final/benchmark_summary_fair_pyspinw_20260402c.json](paper/data/final/benchmark_summary_fair_pyspinw_20260402c.json)
- [paper/data/final/benchmark_tasai_analytic_sunny_20260318.json](paper/data/final/benchmark_tasai_analytic_sunny_20260318.json)
- [paper/data/final/benchmark_tasai_pyspinw_20260402d.json](paper/data/final/benchmark_tasai_pyspinw_20260402d.json)
- [paper/data/final/time_aware_refinement_full_20260327.json](paper/data/final/time_aware_refinement_full_20260327.json)
- [paper/data/final/time_aware_search_results_20260327.json](paper/data/final/time_aware_search_results_20260327.json)
- [paper/data/final/overseer_loggpfix_20260327_final_summary.json](paper/data/final/overseer_loggpfix_20260327_final_summary.json)

### NiPS3 structure-to-discrimination example

- [simulations/data/nips3_mp676040.cif](simulations/data/nips3_mp676040.cif)
- [simulations/nips3_hk0_pyspinw_benchmark.py](simulations/nips3_hk0_pyspinw_benchmark.py)
- [simulations/nips3_gk_pipeline.py](simulations/nips3_gk_pipeline.py)
- [run_logs/nips3_hk0_pyspinw_local.json](run_logs/nips3_hk0_pyspinw_local.json)
- [paper/figures/nips3_hk0_posterior_evolution.png](paper/figures/nips3_hk0_posterior_evolution.png)

This example demonstrates the implemented structure-to-candidate-to-data
workflow on NiPS3 in a single HK0 scattering plane. It is not part of the main
square-lattice benchmark tables, but it is the concrete real-material example
referenced in the revised Section 6 discussion and the SI.

### Section 5 ablations

- one-seed ghost-optic:
  - [paper/data/ablation_runs/ghost_optic](paper/data/ablation_runs/ghost_optic)
- one-seed cleaned bilayer:
  - [paper/data/ablation_runs/bilayer_fm_cleaned](paper/data/ablation_runs/bilayer_fm_cleaned)
- multi-model trap:
  - [paper/data/ablation_runs/multimodel_trap](paper/data/ablation_runs/multimodel_trap)
  - seeded initial-rank state used to construct the §S5.3 trap:
    [paper/data/multimodel_trap_state_20260403.json](paper/data/multimodel_trap_state_20260403.json)
- five-seed ghost-optic rerun:
  - [paper/data/ablation_runs/ghost_optic_5seed_20260415c](paper/data/ablation_runs/ghost_optic_5seed_20260415c)
- five-seed bilayer rerun:
  - [paper/data/ablation_runs/bilayer_fm_5seed_20260415c](paper/data/ablation_runs/bilayer_fm_5seed_20260415c)

### SI robustness additions

- [paper/data/laplace_coverage_refinement_20260415.json](paper/data/laplace_coverage_refinement_20260415.json)
- [paper/data/reviewer_sensitivity_20260403.json](paper/data/reviewer_sensitivity_20260403.json)

### Closed-loop drivers used to generate Figures 9, 10, and Section 5 tables

- [paper/scripts/toy_closed_loop.py](paper/scripts/toy_closed_loop.py) — Figures 9 and 10 (four-model closed-loop pilot with the `[0.10, 0.10, 0.10, 0.70]` chemically-informed prior).
- [paper/scripts/run_audit_ablation.py](paper/scripts/run_audit_ablation.py) — Section 5 ghost-optic, bilayer, and multi-model trap ablations.
- [paper/scripts/toy_closed_loop_llm_overseer.py](paper/scripts/toy_closed_loop_llm_overseer.py) — overseer wrapper for the LLM-audited pilot.
- [paper/scripts/exchange_path_analysis.py](paper/scripts/exchange_path_analysis.py) — Figure 13 exchange-path enumeration.
- [simulations/create_workflow_figure.py](simulations/create_workflow_figure.py) — Figure 1 workflow diagram.

The analytic spin-wave physics that these drivers call is upstreamed into the library as `tasai.physics.SquareLatticeAFM` (Néel-phase J₁-J₂-D AFM, §3.6 / Fig 10) and `tasai.physics.SquareFMBilayer` (square-lattice bilayer ferromagnet with optic branch, §5.3.2). Both modules are covered by unit tests at `tasai/tests/test_paper_backends.py` in the code repo.

### Mailbox / overseer watcher tools (R3 code-availability fix)

A sanitized reference implementation of the mailbox-backed LLM audit
path used in the §5 overseer experiments lives under
[scripts/](scripts/) with an operational README at
[scripts/README_mailbox_tools.md](scripts/README_mailbox_tools.md).
The three scripts referenced from SI Note §7.2 are now present:

- [scripts/llm_danse2_watcher.py](scripts/llm_danse2_watcher.py)
- [scripts/llm_mailbox_client.py](scripts/llm_mailbox_client.py)
- [scripts/llm_audit_mailbox_runner.py](scripts/llm_audit_mailbox_runner.py)

The associated batch worker, campaign manager, foreground executor,
and supervisor are included alongside for completeness. Mailbox URL
and token are taken from explicit command-line arguments; LLM CLI
defaults (including `gpt-5.2-codex` for Codex) are documented in the
README.

### Citation audit tool

- [paper/scripts/check_citations.py](paper/scripts/check_citations.py) — stdlib-only read-only checker that (1) diffs each `references.bib` entry against Crossref (title, year, DOI, position-by-position author list) and (2) scans the two manuscript markdown files for unresolved or unused `[@key]` citations. Returns exit code 1 on warnings so it can be used as a pre-submit gate.

## Code Repository

The underlying reusable library code lives in:

- [usnistgov/tasai](https://github.com/usnistgov/tasai), pinned for this revision at tag **`paper-revision-2026-06`**

The pinned `environment.yml` in this bundle installs that exact snapshot
(equivalent to `pip install git+https://github.com/usnistgov/tasai@paper-revision-2026-06`),
so a reviewer following the install instructions reproduces the same library
state used to generate the figures in this manuscript.

The public paper bundle is:

- [usnistgov/paper-tasai](https://github.com/usnistgov/paper-tasai)
