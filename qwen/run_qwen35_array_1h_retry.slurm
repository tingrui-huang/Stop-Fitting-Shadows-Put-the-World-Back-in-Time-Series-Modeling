#!/bin/bash
# Length-limit retry pass for Qwen3.5-9B on the frozen Paper50 prompts.
#
# This is NOT a change of decoding strategy.  Decoding stays exactly as in the
# main run - temperature 0.0, top_p 1.0, seed 20260823 - and the only thing that
# differs is the completion ceiling: 16,384 tokens in the main pass, 22,000 here,
# for the instances that spent the whole original budget on reasoning without
# emitting a final answer.
#
# Which instances actually run is decided by the runner's own resume logic, not
# by this script:
#     valid saved result                                 -> skipped, untouched
#     no result file (the empty-content length failures)  -> run
#     result file with no usable answer and truncated=true -> re-run
# A result whose final answer parses is never re-run, whatever flags are passed.
#
# Results land in the existing tree, results/qwen35_9b/<cond>_raw/.  No second
# dataset is created.  Every newly written file records its own generation block,
# so a retried instance is visibly max_tokens=22000 while the instances kept from
# the first pass still read 16384.
#
# Context budget: the longest frozen prompt is 41,669 tokens, so 41,669 + 22,000
# = 63,669 fits inside --max-model-len 65536 with 1,867 tokens to spare.
#
# Submit from the repository root:
#     sbatch qwen/run_qwen35_array_1h_retry.slurm
#
#SBATCH --job-name=qwen35_retry
#SBATCH --array=0-3
#SBATCH --partition=gpu_a100
#SBATCH --gpus=1
#SBATCH --cpus-per-task=18
#SBATCH --time=01:00:00
#SBATCH --output=slurm_logs/qwen35_retry_%A_%a.out
#SBATCH --error=slurm_logs/qwen35_retry_%A_%a.err

set -euo pipefail

CONDITIONS=(C0 C1 C2 C3)
COND="${CONDITIONS[$SLURM_ARRAY_TASK_ID]}"

MODEL="Qwen/Qwen3.5-9B"
RUN_TAG="qwen35_9b"
MAX_MODEL_LEN=65536
MAX_TOKENS=22000          # retry ceiling; the main pass used 16384
TEMPERATURE=0.0
TOP_P=1.0
SEED=20260823
PORT=$((8000 + SLURM_ARRAY_TASK_ID))
BASE_URL="http://127.0.0.1:${PORT}/v1"

mkdir -p slurm_logs
echo "task ${SLURM_ARRAY_TASK_ID}: condition ${COND}, port ${PORT}, node $(hostname)"

# The frozen prompts must be bit-identical before anything is sent.
python qwen/verify_frozen_inputs.py

# ---- serve the model on this node (never on a login node) -------------------
vllm serve "${MODEL}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --reasoning-parser qwen3 \
  --language-model-only \
  --port "${PORT}" &
VLLM_PID=$!
cleanup() { kill "${VLLM_PID}" 2>/dev/null || true; wait "${VLLM_PID}" 2>/dev/null || true; }
trap cleanup EXIT

echo "waiting for vLLM on port ${PORT} ..."
for _ in $(seq 1 120); do
  if curl -sf "http://127.0.0.1:${PORT}/v1/models" > /dev/null; then
    echo "vLLM is up"
    break
  fi
  if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
    echo "vLLM exited before becoming ready" >&2
    exit 1
  fi
  sleep 10
done
curl -sf "http://127.0.0.1:${PORT}/v1/models" > /dev/null || {
  echo "vLLM did not become ready within 20 minutes" >&2; exit 1; }

# ---- retry pass -------------------------------------------------------------
# --redo-truncated only reconsiders files that hit the ceiling with no usable
# answer; instances missing a file entirely are picked up by the normal resume.
python qwen/run_qwen_paper50.py \
  --conditions "${COND}" \
  --model "${MODEL}" \
  --run-tag "${RUN_TAG}" \
  --base-url "${BASE_URL}" \
  --temperature "${TEMPERATURE}" \
  --top-p "${TOP_P}" \
  --seed "${SEED}" \
  --max-tokens "${MAX_TOKENS}" \
  --redo-truncated

# ---- collect and score ------------------------------------------------------
python qwen/collect_qwen_results.py \
  --condition "${COND}" --model "${MODEL}" --run-tag "${RUN_TAG}"

c=$(echo "${COND}" | tr 'A-Z' 'a-z')
python score_c0.py \
  --results "results/${RUN_TAG}/${c}_${RUN_TAG}.jsonl" \
  --index   "out_paper50_reviewed/${c}_cli/index.jsonl" \
  --report  "results/${RUN_TAG}/${c}_collect_report.json" \
  --summary "results/${RUN_TAG}/${c}_summary.json"

# ---- prove the retry used the frozen text -----------------------------------
python qwen/verify_frozen_inputs.py --check-results --run-tag "${RUN_TAG}"

echo "task ${SLURM_ARRAY_TASK_ID} (${COND}) done"

# Note on run order: each array task handles a single condition, so the
# C1,C2,C3 / C2,C3,C1 / C3,C1,C2 rotation that --balanced applies within one
# process does not apply here.  Every request is a fresh stateless call, so run
# order cannot influence an answer either way.
#
# Note on partition: gpu_a100 / --gpus=1 matches the usual Snellius A100 setup;
# adjust the partition name and account (--account=...) to your allocation.
# Set HF_HOME (or HF_HUB_CACHE) to a project-space path in your environment so
# the weights are cached off the home filesystem.
