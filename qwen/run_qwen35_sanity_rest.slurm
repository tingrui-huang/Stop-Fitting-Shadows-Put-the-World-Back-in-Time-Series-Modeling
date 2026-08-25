#!/bin/bash
# The five remaining sanity ablations for Qwen3.5-9B, one array task each.
#
#   0  S2_GT_TEXT_ONLY                   GT article (as rendered in C0) + question
#   1  S3_POOL_TEXT_ONLY                 C1 minus the time series
#   2  S4_TS_ONLY                        timestamped TS + question, no news
#   3  S5_C2_QO_DATE_MASK                C2 with absolute dates masked in the MCQA
#   4  S6_C1_METADATA_TIMESTAMP_SHUFFLE  C1 with article timestamps deranged
#
# S1_QO_ONLY has its own script, run_qwen35_sanity_s1.slurm.
#
# Decoding matches the Qwen3.5-9B C0-C3 runs - temperature 0.0, top_p 1.0, seed
# 20260823, ceiling 22000 - so these are comparable with them. They are not
# decoding-matched to the Sonnet-5 sanity runs, which went through the Claude
# CLI and whose metadata records "temperature": "not explicitly controlled".
#
# One task per condition rather than one job for all five: each task then needs
# only a four-hour gap to be backfilled into, and tasks start independently as
# GPUs free up. A single job covering all five would need one sixteen-hour gap.
#
# The largest prompts here are S6 at about 74,000 characters (~18.5k tokens),
# so 18.5k + 22,000 fits inside --max-model-len 65536 with room to spare.
#
# Results land in results/qwen35_9b/<cond>_raw/, disjoint from C0-C3 and from
# the Sonnet-5 sanity tree under results/sanity/.
#
# Submit from the repository root:
#     mkdir -p slurm_logs
#     sbatch qwen/run_qwen35_sanity_rest.slurm
#
#SBATCH --job-name=qwen35_sanity
#SBATCH --array=0-4
#SBATCH --partition=gpu_a100
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=18
#SBATCH --gpus-per-node=1
#SBATCH --time=04:00:00
#SBATCH --output=slurm_logs/qwen35_sanity_%A_%a.out
#SBATCH --error=slurm_logs/qwen35_sanity_%A_%a.err

set -euo pipefail

CONDITIONS=(S2_GT_TEXT_ONLY S3_POOL_TEXT_ONLY S4_TS_ONLY \
            S5_C2_QO_DATE_MASK S6_C1_METADATA_TIMESTAMP_SHUFFLE)
DIRS=(s2_gt_text_only s3_pool_text_only s4_ts_only \
      s5_c2_qo_date_mask s6_c1_metadata_timestamp_shuffle)
COND="${CONDITIONS[$SLURM_ARRAY_TASK_ID]}"
DIR="${DIRS[$SLURM_ARRAY_TASK_ID]}"
SRC="sanity/${DIR}.jsonl"

MODEL="Qwen/Qwen3.5-9B"
RUN_TAG="qwen35_9b"
PORT=$((8500 + SLURM_ARRAY_TASK_ID))

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
VLLM_LOG="vllm_logs/qwen35_sanity_${DIR}_${SLURM_JOB_ID}.log"
echo "task ${SLURM_ARRAY_TASK_ID}: ${COND}  node=$(hostname)  port=${PORT}"
echo "vllm=$(which vllm)"

# Rebuild the frozen sanity prompts and prove they did not drift. The build
# rewrites sanity_conditions_manifest.json, which is tracked, so an unchanged
# manifest is the evidence that these are the same bytes the Sonnet-5 run saw.
python sanity/build_sanity_conditions.py > /dev/null
git diff --quiet sanity/sanity_conditions_manifest.json \
  || { echo "FATAL: sanity manifest changed - prompts are not the frozen ones" >&2
       exit 1; }
python sanity/export_sanity_cli.py --input "${SRC}" --condition "${COND}" \
  --out-dir "sanity/cli/${DIR}" --check

vllm serve "${MODEL}" --port "${PORT}" --tensor-parallel-size 1 \
  --max-model-len 65536 --reasoning-parser qwen3 --language-model-only \
  >| "${VLLM_LOG}" 2>&1 &
VP=$!
trap "kill ${VP} 2>/dev/null || true" EXIT
for _ in $(seq 1 180); do
  curl -sf "http://127.0.0.1:${PORT}/v1/models" > /dev/null && { echo "vLLM is up"; break; }
  kill -0 "${VP}" 2>/dev/null || { echo "FATAL: vLLM exited during startup" >&2
                                   tail -n 80 "${VLLM_LOG}" >&2; exit 1; }
  sleep 10
done
curl -sf "http://127.0.0.1:${PORT}/v1/models" > /dev/null \
  || { echo "FATAL: vLLM not ready" >&2; tail -n 80 "${VLLM_LOG}" >&2; exit 1; }

python qwen/run_qwen_paper50.py \
  --conditions "${COND}" --cli-dir "sanity/cli/%s" \
  --model "${MODEL}" --run-tag "${RUN_TAG}" \
  --base-url "http://127.0.0.1:${PORT}/v1" \
  --temperature 0.0 --top-p 1.0 --seed 20260823 --max-tokens 22000

echo "task ${SLURM_ARRAY_TASK_ID} (${COND}) done"
