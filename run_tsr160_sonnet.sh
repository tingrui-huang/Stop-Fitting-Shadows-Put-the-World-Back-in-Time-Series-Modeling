#!/usr/bin/env bash
# Sonnet-5 over the whole TSRBench-160 census, all five conditions.
#
#   bash run_tsr160_sonnet.sh [parallel]
#
# Runs on a login node, not under Slurm: the Claude CLI needs outbound network
# and the compute nodes have none. No GPU is involved, so this proceeds
# alongside the Qwen jobs rather than competing with them for the queue.
#
# Conditions are ordered so the two that decide everything land first. QA_ONLY
# is the acceptance check - if the question alone answers itself nothing below
# it means anything - and FULL is the reference every intervention is read
# against. If FULL sits on the floor, the remaining three are confirmation
# rather than discovery, and can be read whenever they finish.
#
# Each condition is collected and scored as soon as its sweep ends, so partial
# results are usable while the rest is still running.
set -u

PAR="${1:-8}"
TREE=/gpfs/work2/0/prjs2013/users/qyao1/tsrbench160/cli
TAG=tsrbench160_sonnet5
MODEL=claude-sonnet-5

for COND in qa_only full no_ts shuffled relative; do
  echo "########## ${COND}  start $(date -u +%H:%M:%S)Z ##########"
  bash run_tsr_claude.sh "${TREE}" "${COND}" "${TAG}" "${MODEL}" "${PAR}"

  python collect_c0_results.py \
    --index "${TREE}/${COND}/index.jsonl" \
    --raw-dir "results/${TAG}/${COND}_raw" \
    --out "results/${TAG}/${COND}_${TAG}.jsonl" \
    --report "results/${TAG}/${COND}_collect_report.json" \
    --model "${MODEL}"

  python score_c0.py \
    --results "results/${TAG}/${COND}_${TAG}.jsonl" \
    --index   "${TREE}/${COND}/index.jsonl" \
    --report  "results/${TAG}/${COND}_collect_report.json" \
    --summary "results/${TAG}/${COND}_summary.json"

  echo "########## ${COND}  done $(date -u +%H:%M:%S)Z ##########"
  python - <<PY
import io, json
d = json.load(io.open("results/${TAG}/${COND}_summary.json", encoding="utf-8"))
print("  ${COND}: %d/%d correct, accuracy %.3f, missing %d"
      % (d["n_correct"], d["n_total"], d["n_correct"] / d["n_total"], d["n_missing"]))
print("  baselines: random 0.250, best constant answer 0.300 (the census is D48/B48/A34/C30)")
PY
done

echo "ALL SONNET CONDITIONS DONE $(date -u +%H:%M:%S)Z"
