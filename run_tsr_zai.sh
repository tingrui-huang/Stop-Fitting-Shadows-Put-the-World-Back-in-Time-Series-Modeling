#!/usr/bin/env bash
# Run frozen TSRBench conditions through GLM-5.3-Flash on the Z.AI API.
#
#   bash run_tsr_zai.sh <cond_lower> [cond_lower ...]
#
# Environment:
#   ZAI_API_KEY   required. Never put the key in this file or in the repo.
#   TSR_TREE      prompt tree (default: tsrbench160/cli)
#   RUN_TAG       output tree under results/ (default: tsrbench160_glm53flash_zai)
#   LIMIT         stop after N instances per condition; 0 = all (default 0)
#   MAX_TOKENS    completion ceiling (default 22000, matching the Qwen runs)
#
# Why this exists alongside run_tsr_glm.sh: the same model is reachable two
# ways. The TU/e SPIKE gateway is free but metered at 1M completion tokens a
# week, and one 50-item condition of this study costs about 840k of that, so it
# cannot carry the full design. The Z.AI endpoint is paid but the whole
# 160-item five-condition study costs a few dollars at the current Flash price.
# Results from the two are kept in separate run tags and are not pooled: the
# deployments differ, and only within-endpoint contrasts are safe to read.
#
# The runner is unchanged apart from two flags. Z.AI is OpenAI-compatible, and
# REASONING_KEYS already covers the reasoning_content field it returns, so the
# thinking traces are stored exactly as they are for every other model.
#
#   --stream       long thinking phases otherwise risk a proxy read timeout,
#                  and this endpoint allows 128K of output
#   --extra-body   thinking cannot be disabled on this model; clear_thinking
#                  false is what makes it return the trace instead of dropping
#                  it, which is the whole point of storing raw results
#
# Decoding stays at temperature 0.0 / top_p 1.0 / seed 20260823, matching every
# Qwen arm, rather than the vendor's recommended temperature 1.0 / top_p 0.95.
# The study holds decoding fixed across models on purpose; using per-vendor
# defaults would confound the model comparison with a decoding difference.
set -uo pipefail

: "${ZAI_API_KEY:?set ZAI_API_KEY first (do not commit it)}"
TREE="${TSR_TREE:-tsrbench160/cli}"
TAG="${RUN_TAG:-tsrbench160_glm53flash_zai}"
LIMIT="${LIMIT:-0}"
MAX_TOKENS="${MAX_TOKENS:-22000}"

BASE_URL="https://api.z.ai/api/paas/v4"
MODEL="glm-5.3-flash"
THINKING='{"thinking": {"type": "enabled", "clear_thinking": false}}'

export VLLM_API_KEY="${ZAI_API_KEY}"
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
    --max-tokens "${MAX_TOKENS}" --timeout 900 \
    --stream --extra-body "${THINKING}" ${LIMIT_ARG}

  python qwen/collect_qwen_results.py --condition "${UP}" --cli-dir "${TREE}/%s" \
    --model "${MODEL}" --run-tag "${TAG}"

  python score_c0.py \
    --results "results/${TAG}/${COND}_${TAG}.jsonl" \
    --index   "${TREE}/${COND}/index.jsonl" \
    --report  "results/${TAG}/${COND}_collect_report.json" \
    --summary "results/${TAG}/${COND}_summary.json"

  echo "########## ${UP}  done $(date -u +%H:%M:%SZ) ##########"
  python spike_budget.py --run-tag "${TAG}" 2>/dev/null | head -12
done
