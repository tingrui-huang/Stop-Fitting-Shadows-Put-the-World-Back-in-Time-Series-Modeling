#!/usr/bin/env bash
# Run NBA150 discussion_v3 conditions through GLM on the Z.AI API, sharded.
#
#   bash nba150/discussion_v3/run_v3_zai.sh [cond_upper ...]
#
# Environment:
#   ZAI_API_KEY  required. Never put the key in this file or in the repo.
#   SHARDS       parallel processes per condition (default 3)
#                All conditions launch together, so live concurrency is
#                SHARDS x conditions. 3 x 5 = 15 keeps it under the 16
#                concurrent requests this endpoint was measured to take
#                without rate limiting.
#   RUN_TAG      output tree under results/ (default nba150_v3_glm53flash_zai)
#   MODEL        model id sent to the endpoint (default glm-5.3-flash)
#   BASE_URL     OpenAI-compatible endpoint (default the Z.AI paid API)
#   MAX_TOKENS   completion ceiling (default 22000, matching every other arm)
#   SMOKE        non-empty: send instance 1 of the first condition only, then stop
#
# What is run is whatever nba150/discussion_v3/stage_runner_index.py staged:
# the per-condition index.jsonl is the work list, so a condition capped at 20
# items sends 20 and its collector calls that complete. Re-stage to change the
# scope; do not edit ids here.
#
# Sharding rather than a concurrent runner, for the same reason as
# run_tsr_zai_sharded.sh: the runner is sequential and its resume logic is
# per-instance, so N processes over disjoint id sets share no state - no locks,
# no interleaved writes, and a process that dies loses only its in-flight
# instance. Every instance whose result file exists is skipped, so re-running
# this script after an interruption resumes rather than repeats.
#
# The system prompt is nba150/discussion_v3/system.txt - the frozen one minus
# its finance persona line - which is what the v3 Sonnet and Qwen arms used, so
# the three can be read side by side. Decoding stays at temperature 0.0 /
# top_p 1.0 / seed 20260823 rather than the vendor's recommended 1.0 / 0.95:
# this study holds decoding fixed across models on purpose.
#
# clear_thinking false is what makes this model return its trace instead of
# dropping it, which is the point of storing raw results.
set -uo pipefail

: "${ZAI_API_KEY:?set ZAI_API_KEY first (do not commit it)}"
V3="nba150/discussion_v3"
SHARDS="${SHARDS:-3}"
TAG="${RUN_TAG:-nba150_v3_glm53flash_zai}"
MODEL="${MODEL:-glm-5.3-flash}"
BASE_URL="${BASE_URL:-https://api.z.ai/api/paas/v4}"
MAX_TOKENS="${MAX_TOKENS:-22000}"
LOGDIR="${LOGDIR:-zai_logs}"
THINKING='{"thinking": {"type": "enabled", "clear_thinking": false}}'

CONDS=("$@")
[ ${#CONDS[@]} -eq 0 ] && CONDS=(QA_ONLY FULL REMOVE SHUFFLE RELATIVE)

export VLLM_API_KEY="${ZAI_API_KEY}"
export PYTHONIOENCODING=utf-8
mkdir -p "${LOGDIR}"

# Fail here with a clear message rather than after a hundred failed instances.
code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 \
       -H "Authorization: Bearer ${ZAI_API_KEY}" "${BASE_URL}/models")
[ "$code" = "200" ] || echo "WARNING: ${BASE_URL}/models returned HTTP ${code}" >&2

# Every prompt that will be sent must match the sha256 its staged index
# records. Not stage_runner_index.py --check: that verifies against the full
# 150-row index and so fails on any capped stage, which is exactly what a
# 20/30-item run is. This checks the staged index, i.e. the work list itself.
python - "${V3}" "${CONDS[@]}" <<'CHECK' || { echo "FATAL: staged prompts missing or altered; re-run stage_runner_index.py" >&2; exit 1; }
import hashlib, io, json, os, sys
v3, conds, bad = sys.argv[1], sys.argv[2:], 0
for cond in conds:
    low = cond.lower()
    idx = os.path.join(v3, "cli", low, "index.jsonl")
    if not os.path.exists(idx):
        print("MISSING %s" % idx); bad += 1; continue
    rows = [json.loads(l) for l in io.open(idx, encoding="utf-8") if l.strip()]
    for r in rows:
        f = os.path.join(v3, "cli", low, "%d.txt" % r["instance_id"])
        if (not os.path.exists(f) or hashlib.sha256(
                io.open(f, "rb").read()).hexdigest() != r["prompt_sha256"]):
            print("BAD %s" % f); bad += 1
    print("  %-10s %3d instances  ids %d-%d" % (low, len(rows),
          rows[0]["instance_id"], rows[-1]["instance_id"]))
sys.exit(1 if bad else 0)
CHECK

if [ -n "${SMOKE:-}" ]; then
  COND="${CONDS[0]}"
  echo "SMOKE: ${COND} instance 1 only"
  python qwen/run_qwen_paper50.py \
    --conditions "${COND}" --cli-dir "${V3}/cli/%s" \
    --system-prompt "${V3}/system.txt" \
    --model "${MODEL}" --run-tag "${TAG}" --base-url "${BASE_URL}" \
    --temperature 0.0 --top-p 1.0 --seed 20260823 \
    --max-tokens "${MAX_TOKENS}" --timeout 900 \
    --stream --extra-body "${THINKING}" --only 1
  exit $?
fi

for COND in "${CONDS[@]}"; do
  LOW=$(echo "${COND}" | tr 'A-Z' 'a-z')
  IDX="${V3}/cli/${LOW}/index.jsonl"
  N=$(grep -c . "${IDX}")
  for ((s=0; s<SHARDS; s++)); do
    IDS=$(python - "$s" "$SHARDS" "${IDX}" <<'PY'
import json, sys
shard, n, idx = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
ids = [json.loads(l)["instance_id"] for l in open(idx, encoding="utf-8") if l.strip()]
print(" ".join(str(i) for k, i in enumerate(sorted(ids)) if k % n == shard))
PY
)
    [ -z "${IDS}" ] && continue
    nohup python qwen/run_qwen_paper50.py \
      --conditions "${COND}" --cli-dir "${V3}/cli/%s" \
      --system-prompt "${V3}/system.txt" \
      --model "${MODEL}" --run-tag "${TAG}" --base-url "${BASE_URL}" \
      --temperature 0.0 --top-p 1.0 --seed 20260823 \
      --max-tokens "${MAX_TOKENS}" --timeout 900 \
      --stream --extra-body "${THINKING}" \
      --only ${IDS} \
      > "${LOGDIR}/v3_${LOW}_s${s}.log" 2>&1 &
  done
  echo "  ${COND}: ${N} instances over ${SHARDS} shards launched"
done

echo "all launched. collect and score with:"
echo "  bash ${V3}/collect_v3_zai.sh"
