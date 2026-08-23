#!/usr/bin/env bash
# Run one exported sanity condition through the Claude CLI and save raw stdout.
#
#   bash sanity/run_sanity_claude.sh <cond_lower> [model]
#
# Identical invocation to run_c0_claude.sh, which produced the final C0-C3 runs:
# one fresh non-interactive call per instance, no history between instances, the
# same system prompt, tools disabled.  Decoding parameters are not exposed by
# the CLI and are therefore NOT explicitly controlled - this is not temperature 0.
set -u

COND="${1:?usage: run_sanity_claude.sh <cond_lower> [model]}"
MODEL="${2:-claude-sonnet-5}"
SRC="sanity/cli/$COND"
DST="results/sanity/${COND}_raw"
SYSTEM_PROMPT="prompts/system.txt"
META="results/sanity/${COND}_run_metadata.json"

mkdir -p "$DST"
CLI_VERSION="$(claude --version 2>&1 | head -1)"
N_INSTANCES="$(ls "$SRC"/*.txt 2>/dev/null | wc -l | tr -d ' ')"

cat > "$META" <<EOF
{
  "condition": "$COND",
  "cli_version": "$CLI_VERSION",
  "requested_model": "$MODEL",
  "resolved_or_used_model": "not observed (CLI text output does not report the served model)",
  "system_prompt_file": "$SYSTEM_PROMPT",
  "cli_flags": ["-p", "--model", "--system-prompt-file", "--tools \"\"", "--safe-mode", "--strict-mcp-config"],
  "tools_disabled": true,
  "fresh_invocation_per_instance": true,
  "conversation_history_between_instances": false,
  "temperature": "not explicitly controlled",
  "retry_policy": "one attempt per instance; a failed call leaves no file and is reported as missing, exactly as in the main runs",
  "n_instances": $N_INSTANCES,
  "started_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

for f in "$SRC"/*.txt; do
  id="$(basename "$f" .txt)"
  out="$DST/$id.txt"
  if [ -s "$out" ]; then continue; fi
  if claude -p --model "$MODEL" \
            --system-prompt-file "$SYSTEM_PROMPT" \
            --tools "" \
            --safe-mode \
            --strict-mcp-config < "$f" > "$out"; then
    echo "ok   $COND $id"
  else
    echo "FAIL $COND $id" >&2
    rm -f "$out"
  fi
done
echo "done $COND"
