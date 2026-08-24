#!/bin/bash
# Qwen3.6-35B-A3B on the frozen Paper50 prompts, one array task per condition.
#
# This is the pipeline default model, so no --model / --run-tag override is
# needed: qwen_common.DEFAULT_MODEL is Qwen/Qwen3.6-35B-A3B and results land in
# results/qwen36/, disjoint from the Qwen3.5-9B tree in results/qwen35_9b/.
#
# Decoding matches the Qwen3.5-9B run so the two are comparable:
# temperature 0.0, top_p 1.0, seed 20260823.  Thinking stays on;
# enable_thinking=False is never sent.
#
# Serving: the checkpoint is Qwen3_5MoeForConditionalGeneration - a 256-expert
# MoE (8 active per token, 40 layers) that also carries a vision tower.
# --language-model-only drops the vision half, which the frozen prompts never
# use.  Native context is 262,144; 131,072 is plenty for the longest frozen
# prompt (41,669 tokens) plus the 22,000-token completion ceiling.
#
# 35.95B params in bf16 is ~72 GiB, so it does not fit one H100 alongside a
# KV cache of this size -> --tensor-parallel-size 2, matching qwen/README.md.
#
# Submit from the repository root:
#     mkdir -p slurm_logs
#     sbatch qwen/run_qwen36_array.slurm
#
#SBATCH --job-name=qwen36
#SBATCH --array=0-3
#SBATCH --partition=gpu_h100
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gpus-per-node=2
#SBATCH --time=12:00:00
#SBATCH --output=slurm_logs/qwen36_%A_%a.out
#SBATCH --error=slurm_logs/qwen36_%A_%a.err

set -euo pipefail

CONDITIONS=(C0 C1 C2 C3)
COND="${CONDITIONS[$SLURM_ARRAY_TASK_ID]}"

MODEL="Qwen/Qwen3.6-35B-A3B"
RUN_TAG="qwen36"
TP_SIZE=2
MAX_MODEL_LEN=131072
MAX_TOKENS=22000
TEMPERATURE=0.0
TOP_P=1.0
SEED=20260823
PORT=$((8200 + SLURM_ARRAY_TASK_ID))
BASE_URL="http://127.0.0.1:${PORT}/v1"

# ---- environment ------------------------------------------------------------
source ~/miniforge3/etc/profile.d/conda.sh
conda activate qwen_vllm312

module load 2025
module load CUDA/12.9.1

export CUDA_HOME="$(dirname "$(dirname "$(which nvcc)")")"
export PATH="${CUDA_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${CUDA_HOME}/lib64:${LD_LIBRARY_PATH:-}"
export HF_HOME=/gpfs/work2/0/prjs2013/users/qyao1/hf_cache
# The weights are pre-fetched; never let four array tasks race the hub.
export HF_HUB_OFFLINE=1

mkdir -p slurm_logs vllm_logs
VLLM_LOG="vllm_logs/qwen36_${COND}_${SLURM_JOB_ID}.log"

echo "task ${SLURM_ARRAY_TASK_ID}: condition ${COND}, port ${PORT}, node $(hostname)"
echo "python: $(which python)"
echo "vllm:   $(which vllm)"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

# The frozen prompts must be bit-identical before anything is sent.
python qwen/verify_frozen_inputs.py

# ---- serve ------------------------------------------------------------------
vllm serve "${MODEL}" \
  --port "${PORT}" \
  --tensor-parallel-size "${TP_SIZE}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --reasoning-parser qwen3 \
  --language-model-only \
  >| "${VLLM_LOG}" 2>&1 &
VLLM_PID=$!
cleanup() { kill "${VLLM_PID}" 2>/dev/null || true; wait "${VLLM_PID}" 2>/dev/null || true; }
trap cleanup EXIT

echo "waiting for vLLM on port ${PORT} ..."
for _ in $(seq 1 360); do
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
  echo "vLLM did not become ready within 60 minutes" >&2
  tail -n 100 "${VLLM_LOG}" >&2
  exit 1; }

# ---- run --------------------------------------------------------------------
python qwen/run_qwen_paper50.py \
  --conditions "${COND}" \
  --model "${MODEL}" \
  --run-tag "${RUN_TAG}" \
  --base-url "${BASE_URL}" \
  --temperature "${TEMPERATURE}" \
  --top-p "${TOP_P}" \
  --seed "${SEED}" \
  --max-tokens "${MAX_TOKENS}"

# ---- collect and score ------------------------------------------------------
python qwen/collect_qwen_results.py \
  --condition "${COND}" --model "${MODEL}" --run-tag "${RUN_TAG}"

c=$(echo "${COND}" | tr "A-Z" "a-z")
python score_c0.py \
  --results "results/${RUN_TAG}/${c}_${RUN_TAG}.jsonl" \
  --index   "out_paper50_reviewed/${c}_cli/index.jsonl" \
  --report  "results/${RUN_TAG}/${c}_collect_report.json" \
  --summary "results/${RUN_TAG}/${c}_summary.json"

python qwen/verify_frozen_inputs.py --check-results --run-tag "${RUN_TAG}"

echo "task ${SLURM_ARRAY_TASK_ID} (${COND}) done"
