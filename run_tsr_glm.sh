#!/usr/bin/env bash
# Run frozen TSRBench conditions through GLM-5.3-Flash-FP8 on the TU/e SPIKE gateway.
#
#   bash run_tsr_glm.sh <cond_lower> [cond_lower ...]
#
# Environment:
#   SPIKE_API_KEY   required. Never put the key in this file or in the repo.
#   TSR_TREE        prompt tree (default: tsrbench160/cli)
#   LIMIT           stop after N instances per condition; 0 = all (default 0)
#   MAX_TOKENS      completion ceiling (default 22000, matching the Qwen runs)
#
# No new client is needed. qwen/run_qwen_paper50.py already speaks the
# OpenAI chat-completions schema, already sends Authorization: Bearer from
# VLLM_API_KEY, and already stores the whole response object per instance -
# so the reasoning traces are captured here exactly as they are for Qwen,
# whether the server returns them in a `reasoning` field or inside <think>
# tags. Pointing --base-url at the gateway is the entire change.
#
# Two gateway limits shape the settings below. Any request over ten minutes is
# cut off by the serving platform, so the per-request timeout is 540 s, well
# inside it. And the weekly budget is 10M prompt tokens but only 1M completion
# tokens: prompt side is comfortable (all five conditions over 160 items is
# about 1.8M) while the completion side is the binding constraint. Measure
# before committing to a scope - run with LIMIT=5 first and read the report
# from spike_budget.py.
set -uo pipefail

: "${SPIKE_API_KEY:?set SPIKE_API_KEY first (do not commit it)}"
TREE="${TSR_TREE:-tsrbench160/cli}"
LIMIT="${LIMIT:-0}"
MAX_TOKENS="${MAX_TOKENS:-22000}"

BASE_URL="https://spike-gateway-runai-aiteam.inference.spike.tue.nl/v1"
MODEL="GLM-5.3-Flash-FP8"
TAG="${RUN_TAG:-tsrbench160_glm53flash}"

# The gateway is only reachable from inside the TU/e network. Fail here with a
# clear message rather than after a hundred timed-out instances.
code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 \
       -H "Authorization: Bearer ${SPIKE_API_KEY}" "${BASE_URL}/models")
if [ "$code" != "200" ]; then
  echo "FATAL: gateway returned HTTP ${code} (000 = no route)." >&2
  echo "       The SPIKE gateway needs the TU/e VPN. Connect it and retry." >&2
  exit 1
fi
echo "gateway reachable; live model states:"
curl -s -H "Authorization: Bearer ${SPIKE_API_KEY}" "${BASE_URL}/models" \
  | python -c "
import json,sys
for m in json.load(sys.stdin)['data']:
    print('  %-28s %-12s %s/%s GPUs' % (m['id'], m.get('state','?'),
          m.get('allocated_gpus','?'), m.get('gpu_request','?')))
"

export VLLM_API_KEY="${SPIKE_API_KEY}"
LIMIT_ARG=""
[ "$LIMIT" -gt 0 ] && LIMIT_ARG="--limit ${LIMIT}"

for COND in "$@"; do
  UP=$(echo "${COND}" | tr "a-z" "A-Z")
  echo "########## ${UP}  start $(date -u +%H:%M:%SZ) ##########"

  python qwen/run_qwen_paper50.py \
    --conditions "${UP}" --cli-dir "${TREE}/%s" \
    --model "${MODEL}" --run-tag "${TAG}" \
    --base-url "${BASE_URL}" \
    --temperature 0.0 --top-p 1.0 --seed 20260823 \
    --max-tokens "${MAX_TOKENS}" --timeout 540 --stream ${LIMIT_ARG}

  python qwen/collect_qwen_results.py --condition "${UP}" --cli-dir "${TREE}/%s" \
    --model "${MODEL}" --run-tag "${TAG}"

  python score_c0.py \
    --results "results/${TAG}/${COND}_${TAG}.jsonl" \
    --index   "${TREE}/${COND}/index.jsonl" \
    --report  "results/${TAG}/${COND}_collect_report.json" \
    --summary "results/${TAG}/${COND}_summary.json"

  echo "########## ${UP}  done $(date -u +%H:%M:%SZ) ##########"
  python spike_budget.py --run-tag "${TAG}"
done
