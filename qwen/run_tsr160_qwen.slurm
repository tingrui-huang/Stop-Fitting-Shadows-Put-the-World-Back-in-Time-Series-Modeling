#!/bin/bash
# TSRBench-160 on Qwen3.6-35B-A3B - the whole timestamped pool, five conditions.
#
# The 50-item study left every contrast unmeasurable: FULL scored 0.340 against
# a 0.25 four-way floor at p = 0.144, so no intervention had room to fall. This
# is the same design over all 160 items that carry real timestamps - the census,
# not a sample - which is the largest n this benchmark can support.
#
# Read the letter baseline carefully. The 50-item draw was balanced across
# answer letters, so a constant answer scored 0.24. The census inherits the
# pool's skew, A34 / B48 / C30 / D48, so always-B or always-D scores 0.30.
# Random guessing is still 0.25, but a degenerate model now clears it: report
# accuracy against BOTH 0.25 and the 0.30 best-constant baseline.
#
# One task per condition. Per-item wall times measured on the 50-item run were
# 6 / 40 / 15 / 42 / 37 s (qa_only / full / no_ts / shuffled / relative), so the
# longest sweep is about 2.5 hours at 160 items once the instances that run to
# the completion ceiling are included; 3 hours leaves margin without pushing the
# job into the badly-backfilled range. An instance whose result file exists is
# skipped on resubmission, so a timeout costs nothing.
#
# Decoding matches every earlier Qwen run exactly: temperature 0.0, top_p 1.0,
# seed 20260823, ceiling 22000, TP=2, frozen prompts/system.txt.
#
#SBATCH --job-name=tsr160
#SBATCH --partition=gpu_h100
#SBATCH --array=0-4
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gpus-per-node=2
#SBATCH --time=03:00:00
#SBATCH --output=slurm_logs/tsr160_%A_%a.out
#SBATCH --error=slurm_logs/tsr160_%A_%a.err

set -uo pipefail

REPO=/gpfs/work2/0/prjs2013/users/qyao1/Stop-Fitting-Shadows-Put-the-World-Back-in-Time-Series-Modeling
TSR=/gpfs/work2/0/prjs2013/users/qyao1/tsrbench160
MODEL="Qwen/Qwen3.6-35B-A3B"
RUN_TAG="tsrbench160_qwen36"

CONDS=(QA_ONLY FULL NO_TS SHUFFLED RELATIVE)
COND="${CONDS[${SLURM_ARRAY_TASK_ID}]}"
LOW=$(echo "${COND}" | tr "A-Z" "a-z")
PORT=$((8750 + SLURM_ARRAY_TASK_ID))

source ~/miniforge3/etc/profile.d/conda.sh
conda activate qwen_vllm312
module load 2025
module load CUDA/12.9.1
export CUDA_HOME="$(dirname "$(dirname "$(which nvcc)")")"
export PATH="${CUDA_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${CUDA_HOME}/lib64:${LD_LIBRARY_PATH:-}"
export HF_HOME=/gpfs/work2/0/prjs2013/users/qyao1/hf_cache
export HF_HUB_OFFLINE=1

cd "${REPO}"
mkdir -p slurm_logs vllm_logs
LOG="vllm_logs/tsr160_${LOW}_${SLURM_ARRAY_JOB_ID}.log"
echo "task ${SLURM_ARRAY_TASK_ID}: ${COND}  node=$(hostname)  port=${PORT}"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

python "${TSR}/verify_tsr_prompts.py" --cli "${TSR}/cli" --condition "${COND}" \
  || { echo "FATAL: prompt verification failed" >&2; exit 1; }

vllm serve "${MODEL}" --port "${PORT}" --tensor-parallel-size 2 \
  --max-model-len 131072 --reasoning-parser qwen3 --language-model-only \
  >| "${LOG}" 2>&1 &
VP=$!
trap "kill ${VP} 2>/dev/null || true" EXIT
for _ in $(seq 1 240); do
  curl -sf "http://127.0.0.1:${PORT}/v1/models" > /dev/null && { echo "vLLM is up"; break; }
  kill -0 "${VP}" 2>/dev/null || { echo "FATAL: vLLM exited during startup" >&2
                                   tail -n 60 "${LOG}" >&2; exit 1; }
  sleep 10
done
curl -sf "http://127.0.0.1:${PORT}/v1/models" > /dev/null \
  || { echo "FATAL: vLLM not ready" >&2; tail -n 60 "${LOG}" >&2; exit 1; }

echo "########## ${COND}  start $(date +%H:%M:%S) ##########"
python qwen/run_qwen_paper50.py \
  --conditions "${COND}" --cli-dir "${TSR}/cli/%s" \
  --model "${MODEL}" --run-tag "${RUN_TAG}" \
  --base-url "http://127.0.0.1:${PORT}/v1" \
  --temperature 0.0 --top-p 1.0 --seed 20260823 --max-tokens 22000
python qwen/collect_qwen_results.py --condition "${COND}" --cli-dir "${TSR}/cli/%s" \
  --model "${MODEL}" --run-tag "${RUN_TAG}"
python score_c0.py \
  --results "results/${RUN_TAG}/${LOW}_${RUN_TAG}.jsonl" \
  --index   "${TSR}/cli/${LOW}/index.jsonl" \
  --report  "results/${RUN_TAG}/${LOW}_collect_report.json" \
  --summary "results/${RUN_TAG}/${LOW}_summary.json"
echo "########## ${COND}  done $(date +%H:%M:%S) ##########"
