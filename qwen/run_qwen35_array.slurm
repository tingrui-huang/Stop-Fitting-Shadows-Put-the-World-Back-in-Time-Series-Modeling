#!/bin/bash
#SBATCH --job-name=qwen35-paper50
#SBATCH --partition=gpu_a100
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=18
#SBATCH --gpus-per-node=1
#SBATCH --time=06:00:00
#SBATCH --array=0-3
#SBATCH --output=qwen35_%A_%a.out
#SBATCH --error=qwen35_%A_%a.err

set -e

CONDS=(C0 C1 C2 C3)
COND=${CONDS[$SLURM_ARRAY_TASK_ID]}
PORT=$((8100 + SLURM_ARRAY_TASK_ID))

echo "=== $COND ==="
echo "node: $(hostname)"
echo "port: $PORT"
echo "job: $SLURM_JOB_ID"

# Environment
source ~/miniforge3/etc/profile.d/conda.sh
conda activate qwen_vllm312

module load 2025
module load CUDA/12.9.1

export CUDA_HOME=$(dirname $(dirname $(which nvcc)))
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"

export HF_HOME=/gpfs/work2/0/prjs2013/users/qyao1/hf_cache

cd ~/Projects/Stop-Fitting-Shadows-Put-the-World-Back-in-Time-Series-Modeling

mkdir -p ~/vllm_logs

# Start one Qwen server for this GPU/job
vllm serve Qwen/Qwen3.5-9B \
    --port "$PORT" \
    --tensor-parallel-size 1 \
    --max-model-len 65536 \
    --reasoning-parser qwen3 \
    --language-model-only \
    >| ~/vllm_logs/qwen35_${COND}_${SLURM_JOB_ID}.log 2>&1 &

SERVER_PID=$!

# Kill server when the job finishes
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

echo "Waiting for vLLM server..."

for i in $(seq 1 120); do
    if curl -s "http://127.0.0.1:${PORT}/v1/models" > /dev/null; then
        echo "vLLM ready."
        break
    fi

    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "vLLM died during startup."
        tail -n 100 ~/vllm_logs/qwen35_${COND}_${SLURM_JOB_ID}.log
        exit 1
    fi

    sleep 5
done

curl -f "http://127.0.0.1:${PORT}/v1/models" > /dev/null

echo "Starting Paper50 $COND..."

python qwen/run_qwen_paper50.py \
    --conditions "$COND" \
    --model Qwen/Qwen3.5-9B \
    --run-tag qwen35_9b \
    --base-url "http://127.0.0.1:${PORT}/v1" \
    --temperature 0.0 \
    --top-p 1.0 \
    --max-tokens 16384 \
    --seed 20260823

echo "$COND finished."

