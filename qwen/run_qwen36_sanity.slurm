#!/bin/bash
# All six sanity ablations for Qwen3.6-35B-A3B.
#
# One job for all six rather than an array of six. Each task would need two
# H100 on one node, and gpu_h100 has been saturated for two days, so six
# allocations is six separate waits; the whole sweep is only about two hours
# behind one five-minute server start, which one allocation covers comfortably.
#
# Decoding matches the Qwen3.6-35B-A3B C0-C3 runs exactly: temperature 0.0,
# top_p 1.0, seed 20260823, ceiling 22000, TP=2, --max-model-len 131072,
# --language-model-only. Results land in results/qwen36/<cond>_raw/, so the
# sweep is comparable with that model C0-C3 numbers and disjoint from both the
# Qwen3.5-9B tree and the Sonnet-5 sanity tree.
#
# Resumable: an instance with a saved result is skipped, so this can be
# resubmitted after a node failure and will pick up where it stopped.
#
# Submit from the repository root:
#     mkdir -p slurm_logs
#     sbatch qwen/run_qwen36_sanity.slurm
#
#SBATCH --job-name=qwen36_sanity
#SBATCH --partition=gpu_h100
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gpus-per-node=2
#SBATCH --time=04:00:00
#SBATCH --output=slurm_logs/qwen36_sanity_%j.out
#SBATCH --error=slurm_logs/qwen36_sanity_%j.err

set -uo pipefail

MODEL="Qwen/Qwen3.6-35B-A3B"
RUN_TAG="qwen36"
PORT=8600

source ~/miniforge3/etc/profile.d/conda.sh
conda activate qwen_vllm312
module load 2025
module load CUDA/12.9.1
export CUDA_HOME="$(dirname "$(dirname "$(which nvcc)")")"
export PATH="${CUDA_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${CUDA_HOME}/lib64:${LD_LIBRARY_PATH:-}"
export HF_HOME=/gpfs/work2/0/prjs2013/users/qyao1/hf_cache
export HF_HUB_OFFLINE=1

mkdir -p slurm_logs vllm_logs
LOG="vllm_logs/qwen36_sanity_${SLURM_JOB_ID}.log"
echo "node=$(hostname)  vllm=$(which vllm)"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

# The frozen sanity prompts must be the bytes every earlier run saw. The build
# rewrites a tracked manifest, so an unchanged manifest is the proof.
python sanity/build_sanity_conditions.py > /dev/null
git diff --quiet sanity/sanity_conditions_manifest.json \
  || { echo "FATAL: sanity manifest changed - prompts are not the frozen ones" >&2
       exit 1; }

CONDS=(S1_QO_ONLY S2_GT_TEXT_ONLY S3_POOL_TEXT_ONLY S4_TS_ONLY \
       S5_C2_QO_DATE_MASK S6_C1_METADATA_TIMESTAMP_SHUFFLE)
DIRS=(s1_qo_only s2_gt_text_only s3_pool_text_only s4_ts_only \
      s5_c2_qo_date_mask s6_c1_metadata_timestamp_shuffle)

for k in "${!CONDS[@]}"; do
  python sanity/export_sanity_cli.py --input "sanity/${DIRS[$k]}.jsonl" \
    --condition "${CONDS[$k]}" --out-dir "sanity/cli/${DIRS[$k]}" --check \
    || { echo "FATAL: export check failed for ${CONDS[$k]}" >&2; exit 1; }
done

vllm serve "${MODEL}" --port "${PORT}" --tensor-parallel-size 2 \
  --max-model-len 131072 --reasoning-parser qwen3 --language-model-only \
  >| "${LOG}" 2>&1 &
VP=$!
trap "kill ${VP} 2>/dev/null || true" EXIT
echo "vLLM starting, log ${LOG}"
for _ in $(seq 1 240); do
  curl -sf "http://127.0.0.1:${PORT}/v1/models" > /dev/null && { echo "vLLM is up"; break; }
  kill -0 "${VP}" 2>/dev/null || { echo "FATAL: vLLM exited during startup" >&2
                                   tail -n 60 "${LOG}" >&2; exit 1; }
  sleep 10
done
curl -sf "http://127.0.0.1:${PORT}/v1/models" > /dev/null \
  || { echo "FATAL: vLLM not ready" >&2; tail -n 60 "${LOG}" >&2; exit 1; }

for k in "${!CONDS[@]}"; do
  C="${CONDS[$k]}"; D="${DIRS[$k]}"
  echo "########## ${C}  $(date +%H:%M:%S) ##########"
  python qwen/run_qwen_paper50.py \
    --conditions "${C}" --cli-dir "sanity/cli/%s" \
    --model "${MODEL}" --run-tag "${RUN_TAG}" \
    --base-url "http://127.0.0.1:${PORT}/v1" \
    --temperature 0.0 --top-p 1.0 --seed 20260823 --max-tokens 22000
  python qwen/collect_qwen_results.py --condition "${C}" --cli-dir "sanity/cli/%s" \
    --model "${MODEL}" --run-tag "${RUN_TAG}"
  python score_c0.py \
    --results "results/${RUN_TAG}/${D}_${RUN_TAG}.jsonl" \
    --index   "sanity/cli/${D}/index.jsonl" \
    --report  "results/${RUN_TAG}/${D}_collect_report.json" \
    --summary "results/${RUN_TAG}/${D}_summary.json"
  echo "########## ${C} done $(date +%H:%M:%S) ##########"
done

python qwen/verify_frozen_inputs.py --check-results --run-tag "${RUN_TAG}"
echo "ALL SANITY DONE $(date +%H:%M:%S)"
