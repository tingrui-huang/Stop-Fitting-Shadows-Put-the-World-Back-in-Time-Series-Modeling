#!/usr/bin/env bash
# Run every exported C0 prompt through the Claude CLI and save raw stdout.
#
#   bash run_c0_claude.sh [model] [max_instances]
#
# One fresh, non-interactive CLI invocation per instance; no conversation history
# is carried between instances.  Every flag below was checked against the
# installed CLI's --help (v2.1.177); no API key or SDK is used.
#
#   -p                       non-interactive: print the response and exit
#   --system-prompt-file     the fixed neutral system prompt, identical for all runs
#   --tools ""               disable all built-in tools
#   --safe-mode              ignore CLAUDE.md, skills, plugins, hooks, MCP servers
#   --strict-mcp-config      no MCP servers beyond --mcp-config (none given)
#
# Decoding parameters (temperature, top-p) are not exposed by the CLI and are
# therefore not explicitly controlled.
set -u

MODEL="${1:-claude-sonnet-5}"
LIMIT="${2:-0}"                   # 0 = all instances; e.g. 3 for a small pilot
SRC="out/c0_cli"
DST="results/c0_raw"
SYSTEM_PROMPT="prompts/system.txt"
META="results/c0_run_metadata.json"

mkdir -p "$DST"
CLI_VERSION="$(claude --version 2>&1 | head -1)"
N_INSTANCES="$(ls "$SRC"/*.txt 2>/dev/null | wc -l | tr -d ' ')"

cat > "$META" <<EOF
{
  "condition": "C0",
  "cli_version": "$CLI_VERSION",
  "requested_model": "$MODEL",
  "resolved_or_used_model": "not observed (CLI text output does not report the served model)",
  "system_prompt_file": "$SYSTEM_PROMPT",
  "cli_flags": ["-p", "--model", "--system-prompt-file", "--tools \"\"", "--safe-mode", "--strict-mcp-config"],
  "tools_disabled": true,
  "fresh_invocation_per_instance": true,
  "conversation_history_between_instances": false,
  "temperature": "not explicitly controlled",
  "n_instances": $N_INSTANCES,
  "started_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
echo "wrote $META"

n=0
for f in "$SRC"/*.txt; do
  id="$(basename "$f" .txt)"
  out="$DST/$id.txt"
  if [ -s "$out" ]; then
    echo "skip $id (already collected)"
    continue
  fi
  if [ "$LIMIT" -gt 0 ] && [ "$n" -ge "$LIMIT" ]; then
    echo "stopping after $LIMIT instance(s)"
    break
  fi
  echo "run  $id"
  if claude -p --model "$MODEL" \
            --system-prompt-file "$SYSTEM_PROMPT" \
            --tools "" \
            --safe-mode \
            --strict-mcp-config < "$f" > "$out"; then
    n=$((n + 1))
  else
    echo "FAILED $id - removing empty output" >&2
    rm -f "$out"
  fi
done

echo "done. next: python collect_c0_results.py && python score_c0.py"
