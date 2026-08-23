# Qwen pipeline for the frozen Paper50 experiment

Runs the **existing frozen** C0/C1/C2/C3 prompts through a Qwen model served
locally by vLLM, keeping the model's thinking trace as a separate field from its
final answer.

One code path, any Qwen model. `--model` names the model that is sent to the
server and recorded in every result; `--run-tag` names the output tree. The
defaults reproduce the original run byte for byte:

| target | command additions | output |
| --- | --- | --- |
| Qwen3.6-35B-A3B (default) | *(none)* | `results/qwen36/` |
| Qwen3.5-9B | `--model Qwen/Qwen3.5-9B --run-tag qwen35_9b` | `results/qwen35_9b/` |

The run tag only selects a directory - it never reaches a prompt, a gold label
or a scoring rule. The scoring `model` label is derived from the model id
recorded in the raw files (`Qwen/Qwen3.6-35B-A3B` -> `qwen3.6-35b-a3b`), so it
always reflects the model actually requested rather than the tag.

Nothing in the Paper50 benchmark is rebuilt, normalised or rewritten. The
prompts under `out_paper50_reviewed/<cond>_cli/` and `prompts/system.txt` are
read byte-for-byte and sent verbatim, whichever model is used. No Sonnet
result is touched: Qwen writes only under `results/<run-tag>/`.

## Files

| file | role |
| --- | --- |
| `qwen_common.py` | transport (stdlib `urllib`, no `openai` dep), reasoning/content split, hashing |
| `run_qwen_paper50.py` | the runner: frozen prompts in, one structured JSON per instance out; resumable |
| `collect_qwen_results.py` | structured JSON → scored JSONL, reusing the Sonnet parser |
| `verify_frozen_inputs.py` | sha256 of all 205 frozen inputs + audit of what each run actually sent |
| `smoke_test_one.py` | the 7-point one-instance validation |
| `offline_selftest.py` | everything except the GPU call, no server needed; also proves the two run targets stay disjoint |
| `frozen_inputs_baseline.json` | the recorded hashes |

Scoring reuses the repository's **unmodified** `score_c0.py`.

## Serving (on an allocated GPU node, never the login node)

```bash
vllm serve Qwen/Qwen3.6-35B-A3B \
  --tensor-parallel-size 2 \
  --max-model-len 131072 \
  --reasoning-parser qwen3 \
  --language-model-only \
  --port 8000
```

For the smaller model, serve that instead — one model per server. To keep both
up at once, give the second a different `--port` and pass a matching
`--base-url` to the scripts.

```bash
vllm serve Qwen/Qwen3.5-9B \
  --max-model-len 131072 \
  --reasoning-parser qwen3 \
  --language-model-only \
  --port 8001
```

Thinking stays on. `enable_thinking=False` is never sent by any script here.
If a server build needs the kwarg spelled out, add `--send-enable-thinking-kwarg`
to the runner or the smoke test; the smoke test fails loudly when no reasoning
comes back, so this is self-checking rather than assumed.

## Order of operations

```bash
# 0. record the frozen-input hashes once, then check them before and after runs
python qwen/verify_frozen_inputs.py --write-baseline
python qwen/verify_frozen_inputs.py

# 0b. plumbing check with no server
python qwen/offline_selftest.py

# 1. ONE instance first
python qwen/smoke_test_one.py --instance-id 15

# 2. all 50 C0
python qwen/run_qwen_paper50.py --conditions C0

# 3. all 150 C1/C2/C3, order-balanced
python qwen/run_qwen_paper50.py --conditions C1 C2 C3 --balanced

# 4. collect and score
python qwen/collect_qwen_results.py --condition C0 C1 C2 C3
for c in c0 c1 c2 c3; do
  python score_c0.py \
    --results results/qwen36/${c}_qwen36.jsonl \
    --index   out_paper50_reviewed/${c}_cli/index.jsonl \
    --report  results/qwen36/${c}_collect_report.json \
    --summary results/qwen36/${c}_summary.json
done

# 5. prove the run used the frozen text
python qwen/verify_frozen_inputs.py --check-results
```

### The same steps for Qwen3.5-9B

```bash
python qwen/smoke_test_one.py --instance-id 15 \
  --model Qwen/Qwen3.5-9B --run-tag qwen35_9b
```
```bash
python qwen/run_qwen_paper50.py --conditions C0 \
  --model Qwen/Qwen3.5-9B --run-tag qwen35_9b
```
```bash
python qwen/run_qwen_paper50.py --conditions C1 C2 C3 --balanced \
  --model Qwen/Qwen3.5-9B --run-tag qwen35_9b
```
```bash
python qwen/collect_qwen_results.py --condition C0 C1 C2 C3 \
  --model Qwen/Qwen3.5-9B --run-tag qwen35_9b
```
```bash
for c in c0 c1 c2 c3; do
  python score_c0.py \
    --results results/qwen35_9b/${c}_qwen35_9b.jsonl \
    --index   out_paper50_reviewed/${c}_cli/index.jsonl \
    --report  results/qwen35_9b/${c}_collect_report.json \
    --summary results/qwen35_9b/${c}_summary.json
done
```
```bash
python qwen/verify_frozen_inputs.py --check-results --run-tag qwen36 qwen35_9b
```

Passing `--model` to the collector is optional but worth doing: it is checked
against the model id stored in every raw file, and any disagreement is counted
in `n_model_mismatch` in the collect report rather than silently absorbed.

Interrupted jobs resume by relaunching the same command: an instance with an
existing result file is skipped. `--redo-malformed` re-runs only those whose
final JSON does not parse; `--only 15 18` re-runs named instances.

## Generation settings

Explicit in `run_qwen_paper50.py` and recorded in every result file and in
`results/<run-tag>/run_metadata_*.json`, alongside the model and run tag:

| parameter | default |
| --- | --- |
| `temperature` | `0.0` |
| `top_p` | `1.0` |
| `max_tokens` | `16384` (covers thinking + final answer) |
| `seed` | `20260823` |
| `presence_penalty` | unset |

**Read this before the full run.** The default is greedy decoding because you
asked for a conservative deterministic configuration, and it is what makes the
run reproducible. But Qwen's own guidance for thinking mode recommends
`temperature 0.6`, `top_p 0.95`, and warns that greedy decoding can send
reasoning models into repetition loops — which here would show up as
`finish_reason == "length"` and an empty or truncated final answer. The smoke
test and the collector both surface that (`n_truncated`, `truncated_instance_ids`).
If you see it, switch deliberately and record it:

```bash
python qwen/run_qwen_paper50.py --conditions C0 --temperature 0.6 --top-p 0.95
```

Nothing is ever truncated silently: `finish_reason`, `truncated` and the full
`usage` block are stored per instance.

## Output

`results/<run-tag>/<cond>_raw/<instance_id>.json`, one per call:

```json
{
  "instance_id": 15,
  "condition": "C0",
  "model": "Qwen/Qwen3.6-35B-A3B",
  "reasoning": "…the model's thinking trace…",
  "content": "{\"answer\": \"C\", \"confidence\": 0.85, \"rationale\": \"…\", \"evidence_articles\": [1]}",
  "finish_reason": "stop",
  "truncated": false,
  "reasoning_source": "reasoning_content",
  "message_fields_returned": ["content", "reasoning_content", "role"],
  "gold_answer": "C",
  "prompt_file": "out_paper50_reviewed/c0_cli/15.txt",
  "prompt_sha256": "…",
  "system_prompt_sha256": "…",
  "generation": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 16384, "seed": 20260823},
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
  "started_utc": "…", "finished_utc": "…",
  "api_response": { "…the full response, for later audit…" }
}
```

`reasoning` is the thinking trace. `rationale`, inside `content`, is the short
public explanation the experiment's schema asks for. They are never merged.

The field name for the trace is **probed, not assumed**: `reasoning_content`,
`reasoning`, `thinking`, `reasoning_text`, `thought` are tried in order, and if
the server was started without a reasoning parser a `<think>…</think>` block is
split out of `content` instead. Whichever path was taken is recorded in
`reasoning_source`, and `message_fields_returned` lists what the server actually
sent.

## Failure handling

| situation | behaviour |
| --- | --- |
| API exception, HTTP error, timeout | no result file; logged to `results/<run-tag>/failures_*.jsonl`; rerunnable |
| empty response / no message | no result file; logged with a response preview |
| missing final content | no result file; logged **with the reasoning trace kept** |
| malformed final JSON | result file **is** written so the trace survives; reported as malformed by the collector; re-run with `--redo-malformed` |
| invalid answer outside A–D | same as malformed — the Sonnet validator rejects it |
| truncation | file written, `truncated: true`, counted in the collect report |

A failed request never produces a successful-looking result file.

## One deviation you should know about

You asked to preserve the existing C1/C2/C3 run-order balancing. **There is no
such balancing in this repository** — I grepped every script, run log and
collect report, and the Sonnet C1/C2/C3 runs were executed one condition at a
time. The rotation `C1,C2,C3 / C2,C3,C1 / C3,C1,C2` by instance rank is
implemented here exactly as you specified, but it is **new to the Qwen run**,
not inherited. Since every request is a fresh stateless call with no
conversation history, run order cannot influence any answer either way. The
resolved order is written to `results/qwen36/run_metadata_c1_c2_c3.json` so it
is auditable.

## Adding a third model

Nothing in the code is model-specific. Serve it, then pass `--model <id>
--run-tag <tag>` to the smoke test, the runner and the collector. A run tag must
match `^[A-Za-z0-9][A-Za-z0-9_.-]*$`, which is validated at argument-parse time
so a stray path component cannot redirect output outside `results/`.
