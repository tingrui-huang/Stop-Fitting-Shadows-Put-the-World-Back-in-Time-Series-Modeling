#!/usr/bin/env bash
# Run the whole TSRBench-160 census through GLM-5.3-Flash on Z.AI, in parallel.
#
#   bash run_tsr_zai_sharded.sh [shards_per_condition]
#
# Why sharding rather than a concurrent runner: the runner is deliberately
# sequential and its resume logic is per-instance, so N independent processes
# over disjoint id sets share no state at all - no locks, no interleaved
# writes, and a process that dies loses only its own in-flight instance. Every
# instance whose result file exists is skipped, so re-running this script after
# any interruption resumes rather than repeats.
#
# Measured on this endpoint before launching: a FULL item takes about 290 s and
# 16,000 completion tokens at roughly 55 tokens/s, and 16 concurrent requests
# returned with no rate limiting. Sequential, the 800 calls would take 64 hours;
# at six shards per condition the longest condition is about three.
#
# Cost at the current Flash price ($0.075 / $0.25 per 1M in/out) is around $3.5
# for the full 800-call study - the binding constraint here is wall clock, not
# money.
#
# Pre-flight, all verified before this script was written: the 800 prompts hash
# to what tsrbench160/cli/manifest.json recorded at build time and carry no CR,
# the system prompt is the frozen b99b3d2a used by the Sonnet and Qwen arms, and
# a stored result carries the trace, the parsed answer, the usage, the decoding
# settings and the exact extra_body that was sent.
set -uo pipefail

: "${ZAI_API_KEY:?set ZAI_API_KEY first}"
SHARDS="${1:-6}"
TREE="${TSR_TREE:-tsrbench160/cli}"
TAG="${RUN_TAG:-tsrbench160_glm53flash_zai}"
LOGDIR="${LOGDIR:-zai_logs}"

BASE_URL="https://api.z.ai/api/paas/v4"
MODEL="glm-5.3-flash"
THINKING='{"thinking": {"type": "enabled", "clear_thinking": false}}'

export VLLM_API_KEY="${ZAI_API_KEY}"
export PYTHONIOENCODING=utf-8
mkdir -p "${LOGDIR}"

N=$(ls "${TREE}"/full/*.txt | wc -l | tr -d " ")
echo "sharding ${N} instances x 5 conditions into ${SHARDS} shards each"

for COND in QA_ONLY FULL NO_TS SHUFFLED RELATIVE; do
  LOW=$(echo "${COND}" | tr "A-Z" "a-z")
  for ((s=0; s<SHARDS; s++)); do
    IDS=$(python - "$s" "$SHARDS" "${TREE}/${LOW}/index.jsonl" <<'PY'
import json, sys
shard, n, idx = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
ids = [json.loads(l)["instance_id"] for l in open(idx, encoding="utf-8") if l.strip()]
print(" ".join(str(i) for k, i in enumerate(sorted(ids)) if k % n == shard))
PY
)
    [ -z "${IDS}" ] && continue
    nohup python qwen/run_qwen_paper50.py \
      --conditions "${COND}" --cli-dir "${TREE}/%s" \
      --model "${MODEL}" --run-tag "${TAG}" \
      --base-url "${BASE_URL}" \
      --temperature 0.0 --top-p 1.0 --seed 20260823 \
      --max-tokens 22000 --timeout 900 \
      --stream --extra-body "${THINKING}" \
      --only ${IDS} \
      > "${LOGDIR}/${LOW}_s${s}.log" 2>&1 &
  done
  echo "  ${COND}: ${SHARDS} shards launched"
done

echo "all launched. collect and score each condition once its shards are done:"
echo "  bash collect_tsr_zai.sh"
