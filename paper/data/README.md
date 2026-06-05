# paper/data layout

This directory is split into stable manuscript inputs and legacy snapshots.

## final/ (canonical manuscript inputs)

- `final/benchmark_summary_fair_analytic_20260218.json`
- `final/benchmark_summary_fair_pyspinw_20260402c.json`
- `final/benchmark_tasai_analytic_sunny_20260318.json`
- `final/benchmark_tasai_pyspinw_20260402d.json`
- `final/table2_fair_benchmark_20260218.csv`

These are the benchmark artifacts cited by current manuscript Table 1 / Figures 3-4. The merged `benchmark_summary_fair_*` files remain the source for the agnostic benchmark columns, while the explicit `benchmark_tasai_*` reruns provide the TAS-AI column. For the PySpinW+Cooper-Nathans rows, the April 2, 2026 files are the corrected fair-scorer benchmark artifacts used by the current manuscript.

These `final/` artifacts, together with `paper/data/table2_provenance.md`, are the source of record for current benchmark claims. Supplementary Table S3 is now computed from the preserved `mean_time_per_suggestion` values in these benchmark JSON files, so it is reproducible from the current repository state.

## ablation_runs/ (canonical audit-ablation inputs)

These archived summaries back the Section 5 audit-ablation discussion in the
current manuscript and SI.

### One-seed canonical summaries

- `ablation_runs/ghost_optic/`
  - archived ghost-optic posterior-lock-in summaries for `none`, `loggp`, and
    `llm`
  - used for main-text Table 4 and SI Note S4
- `ablation_runs/bilayer_fm_cleaned/`
  - cleaned routed-controller bilayer ferromagnet summaries for `none`,
    `hybrid`, `max_disagreement`, and `llm`
  - used for main-text Figure 12, Table 5, the associated bilayer discussion in
    Section 5.3, and SI Note S5

### Five-seed robustness reruns (SI §S5.2)

- `ablation_runs/ghost_optic_5seed_20260415c/`
  - five-seed ghost-optic rerun for the `none`, `loggp`, `max_disagreement`,
    and `llm` policies
  - backs SI Table S5 (median and IQR over five seeds, success rate)
- `ablation_runs/bilayer_fm_5seed_20260415c/`
  - five-seed bilayer ferromagnet rerun for `none`, `hybrid`,
    `max_disagreement`, and `llm`
  - backs SI Table S6

### Multi-model stress test (SI §S5.3)

- `ablation_runs/multimodel_trap/`
  - one-seed multi-model trap stress test for `none`, `max_disagreement`,
    `max_disagreement_all`, and `llm`
  - backs the SI §S5.3 table comparing top-two and broader falsification
- `multimodel_trap_state_20260403.json` *(top level)*
  - the seeded initial posterior-rank state used to construct the trap;
    required to reproduce the §S5.3 table from scratch
- Three exploratory `multimodel_trap_state_20260403_{fixed,quick,tiny}.json`
  variants are retained in the dev tree only and are intentionally not part
  of the public bundle

The sibling directory `ablation_runs/bilayer_fm_corrected/` contains earlier
provisional bilayer summaries retained only for development provenance.
Current manuscript claims should use `ablation_runs/bilayer_fm_cleaned/`
(one-seed) or `ablation_runs/bilayer_fm_5seed_20260415c/` (five-seed).

## Robustness and calibration archives (SI §S3)

- `reviewer_sensitivity_20260403.json`
  - three-seed sensitivity sweep used in SI Note S3.1; documents `tas_ai`
    3/3 success with median 11 measurements at 225 s convergence
- `laplace_coverage_refinement_20260415.json`
  - 10-seed coverage calculation for the Laplace credible intervals used in
    SI Note S3.4; backs the J1/J2/D coverage table (0.30 / 0.70 / 0.10)

## NiPS3 real-material demonstration (§6.1 / SI Note S6)

The NiPS3 reproduction pipeline lives in the top-level `simulations/` and
`paper/scripts/` trees rather than under `paper/data/`. See:

- `simulations/data/nips3_mp676040.cif`
  - Materials Project structure used for the structure-informed pipeline
- `simulations/nips3_gk_pipeline.py`
  - exchange-path + Goodenough-Kanamori-Anderson pipeline that seeds the
    candidate-model family from the CIF
- `simulations/nips3_hk0_pyspinw_benchmark.py`
  - PySpinW HK0 benchmark driver used to produce the SI §S6 dispersion
- `paper/scripts/plot_nips3_posterior_evolution.py`
  - regenerates `paper/figures/nips3_hk0_posterior_evolution.png`

## legacy/ (historical snapshots)

Contains older threshold runs and intermediate benchmark campaigns retained for provenance:

- `legacy/benchmark_summary_thr03*.json`
- `legacy/benchmark_summary_thr035*.json`
- `legacy/benchmark_pyspinw_groundtruth.json`
- `legacy/benchmark_pyspinw_cn_seed*.json`
- `legacy/pyspinw_cn_v3/`

## table3_sources/ (closed-loop provenance)

- Canonical source tables and checkpoints used to populate Table 3.
- Current archived LLM overseer rerun used for Figure 10:
  `paper/data/overseer_loggpfix_20260327_checkpoint.json`
- Current canonical LLM Table 3 row:
  `paper/data/table3_sources/table3_llm_nosym_model_table_loggpfix_20260327.csv`
- Targeted M4 uncertainty fit for that refreshed rerun:
  `paper/data/final/overseer_loggpfix_20260327_m4_uncertainty_fit.json`
- See `table3_provenance.md` for mapping details.

## Policy

- Manuscript text/scripts should reference `paper/data/final/` for benchmark claims.
- Manuscript text/scripts should reference `paper/data/ablation_runs/ghost_optic/`
  and `paper/data/ablation_runs/bilayer_fm_cleaned/` for the current one-seed
  audit ablation claims.
- SI §S5.2 five-seed robustness tables should reference
  `paper/data/ablation_runs/ghost_optic_5seed_20260415c/` and
  `paper/data/ablation_runs/bilayer_fm_5seed_20260415c/`.
- SI §S5.3 multi-model stress-test discussion should reference
  `paper/data/ablation_runs/multimodel_trap/` and the seeded initial state
  in `paper/data/multimodel_trap_state_20260403.json`.
- SI §S3 robustness/calibration notes should reference
  `paper/data/reviewer_sensitivity_20260403.json` and
  `paper/data/laplace_coverage_refinement_20260415.json`.
- The §6.1 / SI Note S6 NiPS3 demonstration draws on the
  `simulations/` tree as listed above, not on `paper/data/`.
- Legacy files are archival only and should not be cited in main-text claims.
- Exploratory artifacts (`*.out`, `*.log`, ad-hoc checkpoints) are ignored by git via `.gitignore`.
- Local mailbox/runtime state in `run_logs/` is operational output, not
  canonical paper provenance.
