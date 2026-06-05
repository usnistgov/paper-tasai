#!/bin/bash
#SBATCH -J nips3-hk0
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -p spr
#SBATCH -t 00:20:00
#SBATCH -A CDA24014
#SBATCH -o /work2/09870/williamratcliff/stampede3/tasai_paper_clean/run_outputs/nips3_hk0_%j.out
#SBATCH -e /work2/09870/williamratcliff/stampede3/tasai_paper_clean/run_outputs/nips3_hk0_%j.err

set -euo pipefail

WORK_ROOT=/work2/09870/williamratcliff/stampede3
PAPER_ROOT="${WORK_ROOT}/tasai_paper_clean"
SRC_ROOT="${PAPER_ROOT}/src"
CODE_ROOT="${WORK_ROOT}/tasai/src"
PYSPINW_ROOT="${WORK_ROOT}/tasai/pyspinw_repo"

mkdir -p "${PAPER_ROOT}/run_outputs" "${PAPER_ROOT}/run_logs"

source "${WORK_ROOT}/conda/etc/profile.d/conda.sh"
conda activate "${WORK_ROOT}/conda_envs/tasai"
export TASAI_SRC="${CODE_ROOT}"
export PYSPINW_PATH="${PYSPINW_ROOT}"
export PYTHONPATH="${PYSPINW_ROOT}:${CODE_ROOT}:${PYTHONPATH:-}"
export OMP_NUM_THREADS=1

cd "${SRC_ROOT}"

python3 simulations/nips3_hk0_pyspinw_benchmark.py \
  --n-measurements 6 \
  --seed 7 \
  --output "${PAPER_ROOT}/run_logs/nips3_hk0_pyspinw_${SLURM_JOB_ID}.json"
