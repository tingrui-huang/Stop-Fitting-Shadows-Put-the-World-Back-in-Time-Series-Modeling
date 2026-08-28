#!/bin/bash
# TSRBench-50 QA_ONLY on Qwen3.5-9B - two arms, one factor apart.
#
# Qwen3.5-9B never terminates on a large share of Paper50 items: 16% to 78% of
# instances per condition run the completion ceiling out without producing a
# final answer, worst on the sparsest inputs. The traces are exact character
# level cycles - a 47 to 62 character body repeated up to 1338 times - which is
# what greedy decoding does when the context returns to a state it has already
# been in. The cycle bodies show the model already trying to decide
# ("Okay, I'll choose D. Wait, I'll choose C."), so a prompt that tells it to
# commit may not help at all. That is the question this job answers.
#
#   ctrl    prompts/system.txt              the frozen prompt every Paper50 run
#                                           and the 35B TSRBench run used
#   commit  prompts/system_tsr_commit.txt   same, plus: stop re-checking, commit
#                                           to the current best option, emit the
#                                           JSON. Also drops the inherited
#                                           "finance and stock market" framing,
#                                           which is simply wrong for TSRBench's
#                                           agriculture and labour domains.
#
# The two changes are bundled, so a drop in the failure rate is attributable to
# the pair, not to the commit instruction alone. That is deliberate: if the rate
# does not move, the closed-cycle account is confirmed and the attribution
# question does not arise; if it does move, a third arm can separate them.
#
# ctrl also serves a second purpose - it is the 9B reading of the same prompts
# the 35B scored 0.280 on, so the two models are directly comparable on
# TSRBench's leakage floor.
#
# The arms run concurrently, one vLLM per GPU, because they are independent and
# the 9B's Paper50 S1 sweep - 50 items, 78% of them running to the ceiling -
# took 3h31m on one A100. Serialising would put this job over its walltime.
#
# Decoding is identical to every other 9B run so the failure rates are
# comparable: temperature 0.0, top_p 1.0, seed 20260823, ceiling 22000, TP=1.
#
#SBATCH --job-name=tsr_9b
#SBATCH --partition=gpu_a100
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=36
#SBATCH --gpus-per-node=2
#SBATCH --time=05:00:00
#SBATCH --output=slurm_logs/tsr_9b_%j.out
#SBATCH --error=slurm_logs/tsr_9b_%j.err

set -uo pipefail

REPO=/gpfs/work2/0/prjs2013/users/qyao1/Stop-Fitting-Shadows-Put-the-World-Back-in-Time-Series-Modeling
# A snapshot of the frozen prompts, not the live tree: run_tsr_rest.slurm
# rebuilds tsrbench50/cli in place, and the two jobs may overlap.
SNAP=/gpfs/work2/0/prjs2013/users/qyao1/tsrbench50/cli_snapshot_9b
MODEL="Qwen/Qwen3.5-9B"

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
echo "node=$(hostname)  vllm=$(which vllm)"
nvidia-smi --query-gpu=index,name,memory.total --format=csv
test -f "${SNAP}/qa_only/index.jsonl" || { echo "FATAL: no prompt snapshot at ${SNAP}" >&2; exit 1; }

serve () {  # serve <gpu> <port> <log>
  CUDA_VISIBLE_DEVICES="$1" vllm serve "${MODEL}" --port "$2" \
    --tensor-parallel-size 1 --max-model-len 65536 \
    --reasoning-parser qwen3 --language-model-only >| "$3" 2>&1 &
  echo $!
}

wait_up () {  # wait_up <port> <pid> <log>
  for _ in $(seq 1 240); do
    curl -sf "http://127.0.0.1:$1/v1/models" > /dev/null && { echo "vLLM up on $1"; return 0; }
    kill -0 "$2" 2>/dev/null || { echo "FATAL: vLLM on $1 exited during startup" >&2
                                  tail -n 60 "$3" >&2; return 1; }
    sleep 10
  done
  echo "FATAL: vLLM on $1 never became ready" >&2; tail -n 60 "$3" >&2; return 1
}

LOG_A="vllm_logs/tsr_9b_ctrl_${SLURM_JOB_ID}.log"
LOG_B="vllm_logs/tsr_9b_commit_${SLURM_JOB_ID}.log"
PID_A=$(serve 0 8720 "${LOG_A}")
PID_B=$(serve 1 8721 "${LOG_B}")
trap "kill ${PID_A} ${PID_B} 2>/dev/null || true" EXIT
wait_up 8720 "${PID_A}" "${LOG_A}" || exit 1
wait_up 8721 "${PID_B}" "${LOG_B}" || exit 1

arm () {  # arm <port> <run_tag> <system_prompt>
  local PORT="$1" TAG="$2" SYS="$3"
  echo "########## ${TAG}  start $(date +%H:%M:%S) ##########"
  python qwen/run_qwen_paper50.py \
    --conditions QA_ONLY --cli-dir "${SNAP}/%s" \
    --model "${MODEL}" --run-tag "${TAG}" --system-prompt "${SYS}" \
    --base-url "http://127.0.0.1:${PORT}/v1" \
    --temperature 0.0 --top-p 1.0 --seed 20260823 --max-tokens 22000
  python qwen/collect_qwen_results.py --condition QA_ONLY --cli-dir "${SNAP}/%s" \
    --model "${MODEL}" --run-tag "${TAG}"
  python score_c0.py \
    --results "results/${TAG}/qa_only_${TAG}.jsonl" \
    --index   "${SNAP}/qa_only/index.jsonl" \
    --report  "results/${TAG}/qa_only_collect_report.json" \
    --summary "results/${TAG}/qa_only_summary.json"
  echo "########## ${TAG}  done $(date +%H:%M:%S) ##########"
}

arm 8720 tsrbench50_qwen35        prompts/system.txt              > slurm_logs/tsr_9b_ctrl_${SLURM_JOB_ID}.txt 2>&1 &
A=$!
arm 8721 tsrbench50_qwen35_commit prompts/system_tsr_commit.txt   > slurm_logs/tsr_9b_commit_${SLURM_JOB_ID}.txt 2>&1 &
B=$!
wait "$A"; RC_A=$?
wait "$B"; RC_B=$?
cat "slurm_logs/tsr_9b_ctrl_${SLURM_JOB_ID}.txt"
cat "slurm_logs/tsr_9b_commit_${SLURM_JOB_ID}.txt"

# How many instances never produced a final answer, per arm. This is the number
# the job exists to compare; accuracy over the survivors is secondary and is
# biased whenever the two arms lose different instances.
python - <<'PY'
import glob, json, os
for tag in ("tsrbench50_qwen35", "tsrbench50_qwen35_commit"):
    files = sorted(glob.glob("results/%s/qa_only_raw/*.json" % tag))
    n = len(files)
    trunc = sum(1 for p in files
                if json.load(open(p, encoding="utf-8")).get("truncated"))
    s = "results/%s/qa_only_summary.json" % tag
    acc = json.load(open(s, encoding="utf-8")) if os.path.exists(s) else {}
    print("%-26s results %2d/50   hit the ceiling %2d   summary %s"
          % (tag, n, trunc, json.dumps(acc)))
PY

echo "TSR 9B BOTH ARMS DONE  rc_ctrl=${RC_A} rc_commit=${RC_B}  $(date +%H:%M:%S)"
