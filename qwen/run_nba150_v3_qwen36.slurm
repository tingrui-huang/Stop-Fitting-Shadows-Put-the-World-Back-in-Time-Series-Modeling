#!/bin/bash
# NBA150 discussion_v3 on Qwen3.6-35B-A3B: FULL and the three time interventions.
#
# The v3 bundle (nba150/discussion_v3/) is the abductive task rebuilt so that the
# model sees evidence on both sides of the missing event, with opaque event IDs
# and no positional labels. Seven conditions were built; this runs the four that
# form the time-intervention contrast, one task per condition:
#
#     FULL      real game clock on events and on the numerical table
#     REMOVE    every explicit clock deleted, order and past/future kept
#     SHUFFLE   event clocks deranged, then events sorted chronologically; table fixed
#     RELATIVE  every time replaced by signed seconds from the target event
#
# QA_ONLY, TEXT_ONLY and SERIES_ONLY are not run here.
#
# The system prompt is nba150/discussion_v3/system.txt, the frozen one minus its
# finance persona line, which is what the v3 Sonnet run used; keeping it lets
# the two models be read side by side. Decoding matches every earlier Qwen run:
# temperature 0.0, top_p 1.0, seed 20260823, ceiling 22000, TP=2. One attempt
# per instance; a run that exhausts the ceiling without an answer leaves no
# file and is scored wrong. An instance whose result file exists is skipped on
# resubmission, so a timeout costs nothing.
#
# v3 prompts are about four times the size of the GDELT ones (median 46k chars,
# max 59k), so the per-item wall time is longer than the 40 s measured there.
# Six hours is a guess with margin; the job is billed on elapsed time.
#
#SBATCH --job-name=nba_v3_q36
#SBATCH --partition=gpu_h100
#SBATCH --array=0-3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gpus-per-node=2
#SBATCH --time=06:00:00
#SBATCH --output=slurm_logs/nba_v3_q36_%A_%a.out
#SBATCH --error=slurm_logs/nba_v3_q36_%A_%a.err

set -uo pipefail

REPO=/gpfs/work2/0/prjs2013/users/qyao1/Stop-Fitting-Shadows-Put-the-World-Back-in-Time-Series-Modeling
MODEL="Qwen/Qwen3.6-35B-A3B"
RUN_TAG="nba150_v3_qwen36"
V3="nba150/discussion_v3"

CONDS=(FULL REMOVE SHUFFLE RELATIVE)
COND="${CONDS[${SLURM_ARRAY_TASK_ID}]}"
LOW=$(echo "${COND}" | tr "A-Z" "a-z")
PORT=$((8850 + SLURM_ARRAY_TASK_ID))

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
LOG="vllm_logs/nba_v3_q36_${LOW}_${SLURM_ARRAY_JOB_ID}.log"
echo "task ${SLURM_ARRAY_TASK_ID}: ${COND}  node=$(hostname)  port=${PORT}"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

# Stage the runner layout from the committed prompts and verify every sha256.
python "${V3}/stage_runner_index.py" "${LOW}" \
  || { echo "FATAL: prompt staging/verification failed" >&2; exit 1; }

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
  --conditions "${COND}" --cli-dir "${V3}/cli/%s" \
  --system-prompt "${V3}/system.txt" \
  --model "${MODEL}" --run-tag "${RUN_TAG}" \
  --base-url "http://127.0.0.1:${PORT}/v1" \
  --temperature 0.0 --top-p 1.0 --seed 20260823 --max-tokens 22000
python qwen/collect_qwen_results.py --condition "${COND}" --cli-dir "${V3}/cli/%s" \
  --model "${MODEL}" --run-tag "${RUN_TAG}"
python score_c0.py \
  --results "results/${RUN_TAG}/${LOW}_${RUN_TAG}.jsonl" \
  --index   "${V3}/cli/${LOW}/index.jsonl" \
  --report  "results/${RUN_TAG}/${LOW}_collect_report.json" \
  --summary "results/${RUN_TAG}/${LOW}_summary.json"
echo "########## ${COND}  done $(date +%H:%M:%S) ##########"
