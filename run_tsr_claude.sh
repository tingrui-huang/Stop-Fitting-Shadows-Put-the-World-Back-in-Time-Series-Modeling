#!/usr/bin/env bash
# Run one frozen TSRBench condition through the Claude CLI and save raw stdout.
#
#   bash run_tsr_claude.sh <cli_tree> <cond_lower> <run_tag> [model] [parallel]
#
# The invocation is character for character the one that produced the Sonnet-5
# Paper50 runs (run_c0_claude.sh), so the two studies stay comparable: one fresh
# non-interactive call per instance, no conversation history between instances,
# the frozen system prompt, all tools disabled.
#
#   -p                       non-interactive: print the response and exit
#   --system-prompt-file     the frozen system prompt, identical for all runs
#   --tools ""               disable all built-in tools
#   --safe-mode              ignore CLAUDE.md, skills, plugins, hooks, MCP servers
#   --strict-mcp-config      no MCP servers beyond --mcp-config (none given)
#
# Two things differ from the Qwen runs and must be carried into any comparison:
# the CLI does not expose temperature or seed, so decoding is NOT controlled and
# is certainly not greedy; and there is no completion ceiling, so the
# non-termination that dominates Qwen3.5-9B cannot occur in the same form.
#
# Instances run concurrently because each call is a separate stateless request
# and the work is entirely network-bound. Concurrency is deliberately modest:
# this runs on a login node shared with other users.
#
# Resume: an instance whose output file exists and is non-empty is skipped, so
# an interrupted run can simply be relaunched.
set -u

TREE="${1:?usage: run_tsr_claude.sh <cli_tree> <cond_lower> <run_tag> [model] [parallel]}"
COND="${2:?missing condition}"
TAG="${3:?missing run tag}"
MODEL="${4:-claude-sonnet-5}"
PAR="${5:-5}"

SRC="${TREE}/${COND}"
DST="results/${TAG}/${COND}_raw"
SYSTEM_PROMPT="prompts/system.txt"
META="results/${TAG}/${COND}_run_metadata.json"

test -d "$SRC" || { echo "no prompt tree at $SRC" >&2; exit 1; }
mkdir -p "$DST" "results/${TAG}"

CLI_VERSION="$(claude --version 2>&1 | head -1)"
N_INSTANCES="$(ls "$SRC"/*.txt 2>/dev/null | wc -l | tr -d " ")"

cat > "$META" <<META_EOF
{
  "condition": "${COND}",
  "prompt_tree": "${SRC}",
  "cli_version": "${CLI_VERSION}",
  "requested_model": "${MODEL}",
  "resolved_or_used_model": "not observed (CLI text output does not report the served model)",
  "system_prompt_file": "${SYSTEM_PROMPT}",
  "system_prompt_sha256": "$(python -c "import hashlib,io;print(hashlib.sha256(io.open('${SYSTEM_PROMPT}',encoding='utf-8',newline='').read().encode('utf-8')).hexdigest())")",
  "cli_flags": ["-p", "--model", "--system-prompt-file", "--tools \"\"", "--safe-mode", "--strict-mcp-config"],
  "tools_disabled": true,
  "fresh_invocation_per_instance": true,
  "conversation_history_between_instances": false,
  "concurrency": ${PAR},
  "temperature": "not exposed by the CLI and therefore not controlled",
  "seed": "not exposed by the CLI",
  "completion_ceiling": "none imposed",
  "n_instances": ${N_INSTANCES},
  "started_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
META_EOF
echo "wrote $META  (${N_INSTANCES} instances, concurrency ${PAR})"

run_one () {
  f="$1"; id="$(basename "$f" .txt)"; out="${DST}/${id}.txt"
  if [ -s "$out" ]; then echo "skip $id"; return 0; fi
  if claude -p --model "$MODEL" \
            --system-prompt-file "$SYSTEM_PROMPT" \
            --tools "" --safe-mode --strict-mcp-config < "$f" > "$out" 2>/dev/null \
     && [ -s "$out" ]; then
    echo "ok   $id"
  else
    echo "FAIL $id - leaving no file so it stays rerunnable" >&2
    rm -f "$out"
  fi
}
export -f run_one
export DST MODEL SYSTEM_PROMPT

ls "$SRC"/*.txt | sort -t/ -k99 | xargs -P "$PAR" -I{} bash -c 'run_one "$@"' _ {}

DONE="$(ls "$DST"/*.txt 2>/dev/null | wc -l | tr -d " ")"
echo "done: ${DONE}/${N_INSTANCES} instances have output in ${DST}"
echo "next: python collect_c0_results.py --index ${TREE}/${COND}/index.jsonl \\"
echo "        --raw-dir ${DST} --out results/${TAG}/${COND}_${TAG}.jsonl \\"
echo "        --report results/${TAG}/${COND}_collect_report.json --model ${MODEL}"
