#!/bin/bash
# Length-limit retry pass for Qwen3.5-9B on the frozen Paper50 prompts.
#
# Decoding is unchanged from the main run - temperature 0.0, top_p 1.0,
# seed 20260823.  The only difference is the completion ceiling: 16,384 tokens
# in the main pass, 22,000 here, for the instances that spent the whole
# original budget on reasoning without emitting a final answer.
#
# Which instances actually run is decided by the runner resume logic:
#     valid saved result                                   -> skipped, untouched
#     no result file (the empty-content length failures)   -> run
#     result file with no usable answer and truncated=true -> re-run
#
# Context budget: the longest frozen prompt is 41,669 tokens, so
# 41,669 + 22,000 = 63,669 fits inside --max-model-len 65536.
#
# Submit from the repository root:
#     mkdir -p slurm_logs        # Slurm opens these before the script runs
#     sbatch qwen/run_qwen35_array_retry.slurm
#
#SBATCH --job-name=qwen35_retry
#SBATCH --array=0-3
#SBATCH --partition=gpu_a100
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=18
#SBATCH --gpus-per-node=1
#SBATCH --time=04:00:00
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
PORT=$((8100 + SLURM_ARRAY_TASK_ID))
BASE_URL="http://127.0.0.1:${PORT}/v1"

# ---- environment (this is what the previous working run used) ---------------
source ~/miniforge3/etc/profile.d/conda.sh
conda activate qwen_vllm312

module load 2025
module load CUDA/12.9.1

export CUDA_HOME="$(dirname "$(dirname "$(which nvcc)")")"
export PATH="${CUDA_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${CUDA_HOME}/lib64:${LD_LIBRARY_PATH:-}"
export HF_HOME=/gpfs/work2/0/prjs2013/users/qyao1/hf_cache

mkdir -p slurm_logs vllm_logs
VLLM_LOG="vllm_logs/qwen35_retry_${COND}_${SLURM_JOB_ID}.log"

echo "task ${SLURM_ARRAY_TASK_ID}: condition ${COND}, port ${PORT}, node $(hostname)"
echo "python: $(which python)"
echo "vllm:   $(which vllm)"
echo "vllm log: ${VLLM_LOG}"

# The frozen prompts must be bit-identical before anything is sent.
python qwen/verify_frozen_inputs.py

# ---- serve the model on this node (never on a login node) -------------------
vllm serve "${MODEL}" \
  --port "${PORT}" \
  --tensor-parallel-size 1 \
  --max-model-len "${MAX_MODEL_LEN}" \
  --reasoning-parser qwen3 \
  --language-model-only \
  >| "${VLLM_LOG}" 2>&1 &
VLLM_PID=$!
cleanup() { kill "${VLLM_PID}" 2>/dev/null || true; wait "${VLLM_PID}" 2>/dev/null || true; }
trap cleanup EXIT

echo "waiting for vLLM on port ${PORT} ..."
for _ in $(seq 1 240); do
  if curl -sf "http://127.0.0.1:${PORT}/v1/models" > /dev/null; then
    echo "vLLM is up"
    break
  fi
  if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
    echo "vLLM exited before becoming ready; last 100 lines of ${VLLM_LOG}:" >&2
    tail -n 100 "${VLLM_LOG}" >&2
    exit 1
  fi
  sleep 10
done
curl -sf "http://127.0.0.1:${PORT}/v1/models" > /dev/null || {
  echo "vLLM did not become ready within 40 minutes" >&2
  tail -n 100 "${VLLM_LOG}" >&2
  exit 1; }

# ---- retry pass -------------------------------------------------------------
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

c=$(echo "${COND}" | tr "A-Z" "a-z")
python score_c0.py \
  --results "results/${RUN_TAG}/${c}_${RUN_TAG}.jsonl" \
  --index   "out_paper50_reviewed/${c}_cli/index.jsonl" \
  --report  "results/${RUN_TAG}/${c}_collect_report.json" \
  --summary "results/${RUN_TAG}/${c}_summary.json"

# ---- prove the retry used the frozen text -----------------------------------
python qwen/verify_frozen_inputs.py --check-results --run-tag "${RUN_TAG}"

echo "task ${SLURM_ARRAY_TASK_ID} (${COND}) done"
