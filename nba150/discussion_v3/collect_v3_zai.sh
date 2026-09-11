#!/usr/bin/env bash
# Collect and score whatever the sharded discussion_v3 Z.AI run has finished.
# Safe to run repeatedly while shards are still going: it only reads.
#
#   bash nba150/discussion_v3/collect_v3_zai.sh [cond_upper ...]
#
# --schema v3: the v3 prompts ask for answer/rationale/evidence_event_ids/
# evidence_series_times and no confidence field, so the legacy validator would
# record every good answer as malformed.
set -uo pipefail
V3="nba150/discussion_v3"
TAG="${RUN_TAG:-nba150_v3_glm53flash_zai}"
MODEL="${MODEL:-glm-5.3-flash}"
export PYTHONIOENCODING=utf-8

CONDS=("$@")
[ ${#CONDS[@]} -eq 0 ] && CONDS=(QA_ONLY FULL REMOVE SHUFFLE RELATIVE)

for COND in "${CONDS[@]}"; do
  LOW=$(echo "${COND}" | tr 'A-Z' 'a-z')
  [ -d "results/${TAG}/${LOW}_raw" ] || { echo "  <- ${COND}: nothing yet"; continue; }
  python qwen/collect_qwen_results.py --condition "${COND}" --cli-dir "${V3}/cli/%s" \
    --schema v3 --model "${MODEL}" --run-tag "${TAG}" > /dev/null 2>&1
  python score_c0.py \
    --results "results/${TAG}/${LOW}_${TAG}.jsonl" \
    --index   "${V3}/cli/${LOW}/index.jsonl" \
    --report  "results/${TAG}/${LOW}_collect_report.json" \
    --summary "results/${TAG}/${LOW}_summary.json" 2>/dev/null \
    | grep -E "completed|correct|accuracy|missing" | tr '\n' ' '
  echo "  <- ${COND}"
done
