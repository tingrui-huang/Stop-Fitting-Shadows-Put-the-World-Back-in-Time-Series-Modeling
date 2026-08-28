#!/bin/bash
# TSRBench-50 under a domain-correct system prompt - the framing sensitivity check.
#
# Every TSRBench result so far was produced under prompts/system.txt, which
# opens "You are an expert in finance and stock market analysis." That sentence
# is inherited from Paper50 and is wrong for all 50 items: they are GDELT
# agriculture and labour events measured on the GoldsteinScale, not market data.
#
# prompts/system_neutral.txt differs from it in exactly one line - verified two
# lines changed, one minus and one plus - so this run isolates the framing from
# every other difference. It is not the 9B commit prompt, which additionally
# carries an anti-loop instruction.
#
#   task 0  FULL      does the correct framing lift the reference condition
#                     off its 0.340, which is not significantly above the
#                     0.25 four-way floor (p = 0.144)
#   task 1  QA_ONLY   the matching floor. Without it a lift in FULL cannot be
#                     told apart from the new prompt lifting everything.
#
# Decoding is identical to every other TSRBench run so the readings are
# comparable: temperature 0.0, top_p 1.0, seed 20260823, ceiling 22000, TP=2.
# The prompts themselves are byte-identical to the ones already run - only the
# system message differs - and are verified against manifest.json, never rebuilt.
#
#SBATCH --job-name=tsr_neutral
#SBATCH --partition=gpu_h100
#SBATCH --array=0-1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gpus-per-node=2
#SBATCH --time=01:30:00
#SBATCH --output=slurm_logs/tsr_neutral_%A_%a.out
#SBATCH --error=slurm_logs/tsr_neutral_%A_%a.err

set -uo pipefail

REPO=/gpfs/work2/0/prjs2013/users/qyao1/Stop-Fitting-Shadows-Put-the-World-Back-in-Time-Series-Modeling
TSR=/gpfs/work2/0/prjs2013/users/qyao1/tsrbench50
MODEL="Qwen/Qwen3.6-35B-A3B"
RUN_TAG="tsrbench50_qwen36_neutral"
SYS="prompts/system_neutral.txt"

CONDS=(FULL QA_ONLY)
COND="${CONDS[${SLURM_ARRAY_TASK_ID}]}"
LOW=$(echo "${COND}" | tr "A-Z" "a-z")
PORT=$((8740 + SLURM_ARRAY_TASK_ID))

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
LOG="vllm_logs/tsr_neutral_${LOW}_${SLURM_ARRAY_JOB_ID}.log"
echo "task ${SLURM_ARRAY_TASK_ID}: ${COND}  node=$(hostname)  port=${PORT}  system=${SYS}"
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

echo "########## ${COND} neutral  start $(date +%H:%M:%S) ##########"
python qwen/run_qwen_paper50.py \
  --conditions "${COND}" --cli-dir "${TSR}/cli/%s" --system-prompt "${SYS}" \
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
echo "########## ${COND} neutral  done $(date +%H:%M:%S) ##########"
