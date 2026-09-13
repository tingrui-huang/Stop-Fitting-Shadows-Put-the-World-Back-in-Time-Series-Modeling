#!/bin/bash
# NBA150 discussion_v3 on Qwen3.5-9B: FULL and the three time interventions.
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
# temperature 0.0, top_p 1.0, seed 20260823, ceiling 22000, TP=1 on one A100. One attempt
# per instance; a run that exhausts the ceiling without an answer leaves no
# file and is scored wrong. An instance whose result file exists is skipped on
# resubmission, so a timeout costs nothing.
#
# Measured on the first 50 items: about 69 generated tokens a second, median
# completion 5000-7500 tokens, so 4 to 6 minutes an item and roughly 2.5 hours
# per condition. The remaining 100 items are therefore 7 to 10 hours, which the
# earlier 10-hour limit would have cut off mid-sweep; 20 hours leaves margin and
# costs nothing, since the job is billed on elapsed time and a longer --time did
# not delay the start. The 9B writes three to five times as much thinking as the
# 35B and hit the 22000 ceiling on 30 to 42 per cent of the pilot items.
# A pilot runs with V3_LIMIT set at submit time:
#     V3_LIMIT=50 V3_REPO=$PWD sbatch --export=ALL,V3_LIMIT,V3_REPO qwen/run_nba150_v3_qwen35.slurm
# Extending it later names the new ids instead, so that nothing already tried
# gets a second attempt:
#     V3_ONLY="$(seq 51 150)" V3_REPO=$PWD sbatch --export=ALL,V3_ONLY,V3_REPO qwen/run_nba150_v3_qwen35.slurm
#
#SBATCH --job-name=nba_v3_q35
#SBATCH --partition=gpu_a100
#SBATCH --array=0-3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=18
#SBATCH --gpus-per-node=1
#SBATCH --time=20:00:00
#SBATCH --output=slurm_logs/nba_v3_q35_%A_%a.out
#SBATCH --error=slurm_logs/nba_v3_q35_%A_%a.err

set -uo pipefail

# The checkout to run from. The default tree holds single-copy run outputs
# that a branch switch would fight over, so V3_REPO points this at a git
# worktree of the v3 branch instead and leaves that tree alone.
REPO="${V3_REPO:-/gpfs/work2/0/prjs2013/users/qyao1/Stop-Fitting-Shadows-Put-the-World-Back-in-Time-Series-Modeling}"
MODEL="Qwen/Qwen3.5-9B"
RUN_TAG="nba150_v3_qwen35"
V3="nba150/discussion_v3"

CONDS=(FULL REMOVE SHUFFLE RELATIVE)
COND="${CONDS[${SLURM_ARRAY_TASK_ID}]}"
LOW=$(echo "${COND}" | tr "A-Z" "a-z")
LIMIT_ARG=""
[ -n "${V3_LIMIT:-}" ] && LIMIT_ARG="--limit ${V3_LIMIT}"

# V3_ONLY restricts the call to these instance ids. It exists because an
# instance that exhausted the ceiling leaves no result file, so a plain
# resubmission re-sends it - a second attempt for exactly the instances the
# scoring rule counts as wrong, and only for those, which is how unequal
# retry effort creeps back in. Extending a pilot therefore names the new ids
# rather than relying on resume. The staged index still covers every item, so
# the collector and scorer still count the ones left unanswered.
ONLY_ARG=""
[ -n "${V3_ONLY:-}" ] && ONLY_ARG="--only ${V3_ONLY}"

PORT=$((8860 + SLURM_ARRAY_TASK_ID))

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
LOG="vllm_logs/nba_v3_q35_${LOW}_${SLURM_ARRAY_JOB_ID}.log"
echo "task ${SLURM_ARRAY_TASK_ID}: ${COND}  node=$(hostname)  port=${PORT}"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

# Stage the runner layout from the committed prompts and verify every sha256.
# V3_LIMIT caps the item count for a pilot. The cap lives in the staged index
# so that the collector and scorer agree on what "complete" means; the same ids
# are taken in every condition, so the conditions stay paired.
python "${V3}/stage_runner_index.py" ${LIMIT_ARG} "${LOW}" \
  || { echo "FATAL: prompt staging/verification failed" >&2; exit 1; }

vllm serve "${MODEL}" --port "${PORT}" --tensor-parallel-size 1 \
  --max-model-len 65536 --reasoning-parser qwen3 --language-model-only \
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
  --temperature 0.0 --top-p 1.0 --seed 20260823 --max-tokens 22000 ${ONLY_ARG}
python qwen/collect_qwen_results.py --condition "${COND}" --cli-dir "${V3}/cli/%s" --schema v3 \
  --model "${MODEL}" --run-tag "${RUN_TAG}"
python score_c0.py \
  --results "results/${RUN_TAG}/${LOW}_${RUN_TAG}.jsonl" \
  --index   "${V3}/cli/${LOW}/index.jsonl" \
  --report  "results/${RUN_TAG}/${LOW}_collect_report.json" \
  --summary "results/${RUN_TAG}/${LOW}_summary.json"
echo "########## ${COND}  done $(date +%H:%M:%S) ##########"
