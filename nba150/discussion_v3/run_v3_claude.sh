#!/usr/bin/env bash
# Run one discussion_v3 condition through the Claude CLI and save raw stdout.
#
#   bash nba150/discussion_v3/run_v3_claude.sh <cond_lower> [model] [first_id] [last_id] [jobs]
#
# Same invocation as run_c0_claude.sh: one fresh non-interactive call per
# instance, no history between instances, tools disabled, safe mode.  The
# system prompt is nba150/discussion_v3/system.txt (prompts/system.txt minus
# its finance persona line).  Decoding parameters are not exposed by the CLI
# and are therefore NOT explicitly controlled.
set -u

COND="${1:?usage: run_v3_claude.sh <cond_lower> [model] [first_id] [last_id] [jobs]}"
MODEL="${2:-claude-sonnet-5}"
FIRST="${3:-1}"
LAST="${4:-150}"
JOBS="${5:-4}"
SRC="nba150/discussion_v3/prompts/$COND"
DST="results/nba150_v3_sonnet5/${COND}_raw"
SYSTEM_PROMPT="nba150/discussion_v3/system.txt"
META="results/nba150_v3_sonnet5/${COND}_run_metadata.json"

mkdir -p "$DST"
CLI_VERSION="$(claude --version 2>&1 | head -1)"

cat > "$META" <<JSON
{
  "condition": "$COND",
  "cli_version": "$CLI_VERSION",
  "requested_model": "$MODEL",
  "resolved_or_used_model": "not observed (CLI text output does not report the served model)",
  "system_prompt_file": "$SYSTEM_PROMPT",
  "system_prompt_sha256": "$(sha256sum "$SYSTEM_PROMPT" | cut -d' ' -f1)",
  "cli_flags": ["-p", "--model", "--system-prompt-file", "--tools \"\"", "--safe-mode", "--strict-mcp-config"],
  "tools_disabled": true,
  "fresh_invocation_per_instance": true,
  "conversation_history_between_instances": false,
  "temperature": "not explicitly controlled",
  "retry_policy": "one attempt per instance; a failed call leaves no file",
  "instance_ids": "$FIRST-$LAST",
  "parallel_jobs": $JOBS,
  "started_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON

run_one() {
  id="$1"
  f="$SRC/$id.txt"
  out="$DST/$id.txt"
  if [ -s "$out" ]; then echo "skip $id"; return 0; fi
  if claude -p --model "$MODEL" \
            --system-prompt-file "$SYSTEM_PROMPT" \
            --tools "" \
            --safe-mode \
            --strict-mcp-config < "$f" > "$out.tmp" && [ -s "$out.tmp" ]; then
    mv "$out.tmp" "$out"; echo "ok   $id"
  else
    rm -f "$out.tmp"; echo "FAIL $id" >&2
  fi
}
export -f run_one
export SRC DST MODEL SYSTEM_PROMPT

seq "$FIRST" "$LAST" | xargs -P "$JOBS" -I{} bash -c 'run_one {}'
echo "done $COND $FIRST-$LAST"
