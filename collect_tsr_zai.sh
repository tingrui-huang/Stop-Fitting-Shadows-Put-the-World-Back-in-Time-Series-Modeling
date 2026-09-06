#!/usr/bin/env bash
# Collect and score whatever the sharded Z.AI run has finished so far.
# Safe to run repeatedly while shards are still going: it only reads.
set -uo pipefail
TREE="${TSR_TREE:-tsrbench160/cli}"
TAG="${RUN_TAG:-tsrbench160_glm53flash_zai}"
export PYTHONIOENCODING=utf-8
for COND in QA_ONLY FULL NO_TS SHUFFLED RELATIVE; do
  LOW=$(echo "${COND}" | tr "A-Z" "a-z")
  [ -d "results/${TAG}/${LOW}_raw" ] || continue
  python qwen/collect_qwen_results.py --condition "${COND}" --cli-dir "${TREE}/%s" \
    --model glm-5.3-flash --run-tag "${TAG}" > /dev/null 2>&1
  python score_c0.py \
    --results "results/${TAG}/${LOW}_${TAG}.jsonl" \
    --index   "${TREE}/${LOW}/index.jsonl" \
    --report  "results/${TAG}/${LOW}_collect_report.json" \
    --summary "results/${TAG}/${LOW}_summary.json" 2>/dev/null | grep -E "completed|correct|accuracy|missing" | tr '\n' ' '
  echo "  <- ${COND}"
done
