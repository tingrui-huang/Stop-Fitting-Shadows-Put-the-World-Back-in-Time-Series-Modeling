#!/bin/bash
# TSRBench-50: the reference condition and the three interventions, one array
# task each.
#
#   FULL      events with their timestamps + the timestamped series   reference
#   NO_TS     every timestamp deleted, series and events              [1] event-series alignment
#   SHUFFLED  series timestamp-value pairing deranged                 [2] temporal causal structure
#   RELATIVE  absolute timestamps -> unitless relative indices        [3] time semantics
#
# QA_ONLY already ran and scored 0.280 against a 0.25 four-way floor, so the
# acceptance check passes and these contrasts are worth measuring. Each
# intervention is read against FULL, one factor at a time; the question stem,
# the event texts, the four orderings and the gold letter are byte-identical
# across all five conditions.
#
# Four short tasks rather than one four-hour sweep. The conditions are
# independent, and Snellius reserves the top of the queue three hours out with a
# five-day backfill window, so a 90-minute job fits into far more gaps than a
# four-hour one. The 35B needs about six minutes to load and spent 16 to 23
# minutes per 50-item condition on Paper50, so 90 minutes leaves roughly a
# threefold margin. Paying four vLLM startups back buys that.
#
# A task that runs out of time costs nothing: an instance whose result file
# exists is skipped on resubmission.
#
# Decoding matches the QA_ONLY run and the Paper50 runs exactly, so the two
# benchmarks stay comparable: temperature 0.0, top_p 1.0, seed 20260823,
# ceiling 22000, TP=2. Thinking is on - QA_ONLY spent 1,595 reasoning tokens
# per item on a prompt with nothing in it.
#
#SBATCH --job-name=tsr_rest
#SBATCH --partition=gpu_h100
#SBATCH --array=0-3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gpus-per-node=2
#SBATCH --time=01:30:00
#SBATCH --output=slurm_logs/tsr_rest_%A_%a.out
#SBATCH --error=slurm_logs/tsr_rest_%A_%a.err

set -uo pipefail

REPO=/gpfs/work2/0/prjs2013/users/qyao1/Stop-Fitting-Shadows-Put-the-World-Back-in-Time-Series-Modeling
TSR=/gpfs/work2/0/prjs2013/users/qyao1/tsrbench50
MODEL="Qwen/Qwen3.6-35B-A3B"
RUN_TAG="tsrbench50_qwen36"

CONDS=(FULL NO_TS SHUFFLED RELATIVE)
COND="${CONDS[${SLURM_ARRAY_TASK_ID}]}"
LOW=$(echo "${COND}" | tr "A-Z" "a-z")
PORT=$((8730 + SLURM_ARRAY_TASK_ID))

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
LOG="vllm_logs/tsr_rest_${LOW}_${SLURM_ARRAY_JOB_ID}.log"
echo "task ${SLURM_ARRAY_TASK_ID}: ${COND}  node=$(hostname)  port=${PORT}"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

# Verified, never rebuilt: four tasks rebuilding one tree would race, and the
# prompts are frozen inputs that no run is allowed to move.
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
