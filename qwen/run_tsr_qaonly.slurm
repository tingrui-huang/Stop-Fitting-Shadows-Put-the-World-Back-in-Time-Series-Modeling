#!/bin/bash
# TSRBench-50 QA_ONLY on Qwen3.6-35B-A3B - the acceptance check.
#
# QA_ONLY strips the events and every timestamp and leaves the question stem
# and the four candidate orderings. Nothing in it identifies which ordering is
# right, so a benchmark that measures what it claims to measure should score at
# the four-way floor, 0.25. Anything meaningfully above that is leakage, and no
# contrast built on this pool would mean anything until it is fixed.
#
# Decoding matches the Qwen3.6-35B-A3B Paper50 runs so the two benchmarks stay
# comparable: temperature 0.0, top_p 1.0, seed 20260823, ceiling 22000, TP=2.
#
#SBATCH --job-name=tsr_qaonly
#SBATCH --partition=gpu_h100
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gpus-per-node=2
#SBATCH --time=02:00:00
#SBATCH --output=slurm_logs/tsr_qaonly_%j.out
#SBATCH --error=slurm_logs/tsr_qaonly_%j.err

set -uo pipefail

REPO=/gpfs/work2/0/prjs2013/users/qyao1/Stop-Fitting-Shadows-Put-the-World-Back-in-Time-Series-Modeling
TSR=/gpfs/work2/0/prjs2013/users/qyao1/tsrbench50
MODEL="Qwen/Qwen3.6-35B-A3B"
RUN_TAG="tsrbench50_qwen36"
PORT=8700

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
LOG="vllm_logs/tsr_qaonly_${SLURM_JOB_ID}.log"
echo "node=$(hostname)  vllm=$(which vllm)"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

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

python qwen/run_qwen_paper50.py \
  --conditions QA_ONLY --cli-dir "${TSR}/cli/%s" \
  --model "${MODEL}" --run-tag "${RUN_TAG}" \
  --base-url "http://127.0.0.1:${PORT}/v1" \
  --temperature 0.0 --top-p 1.0 --seed 20260823 --max-tokens 22000

python qwen/collect_qwen_results.py --condition QA_ONLY --cli-dir "${TSR}/cli/%s" \
  --model "${MODEL}" --run-tag "${RUN_TAG}"

python score_c0.py \
  --results "results/${RUN_TAG}/qa_only_${RUN_TAG}.jsonl" \
  --index   "${TSR}/cli/qa_only/index.jsonl" \
  --report  "results/${RUN_TAG}/qa_only_collect_report.json" \
  --summary "results/${RUN_TAG}/qa_only_summary.json"

echo "QA_ONLY done"
