# Docent Ingestion Plan

## Configuration
- Data path: `C:\Users\trhua\AppData\Local\Temp\claude\d--Users-trhua-Research-Stop-Fitting-Shadows-Put-the-World-Back-in-Time-Series-Modeling\0db2d501-18ee-4a92-beb6-f07124fc9b73\scratchpad\docent_qwen_full.json`
- API key source: **not yet available.** No `DOCENT_API_KEY` in the environment, no
  `~/.docent/docent.env`, no project-level `docent.env`. `uvx docent@latest setup`
  raised before reaching its key prompt (it calls `subprocess.run(["claude", ...])`,
  which on Windows does not resolve `claude.CMD`), so the key was never written.
  The plugin itself was installed manually and works.

## Source Analysis
- File structure: a single JSON array of agent-run objects, produced by
  `export_to_docent.py` in this repository from the authoritative per-instance
  result files under `results/tsrbench160_qwen36/full_raw/`.
- Detected formats: one format only; every record has the same shape.
- Expected source record count: **156**

Verified across all 156 records:

| Property | Value |
| --- | --- |
| transcripts per record | 1 |
| messages per transcript | 3 (system, user, assistant) |
| assistant content blocks | `reasoning` then `text` |
| records with an empty reasoning trace | 0 |
| correct | 47 / 156 |

## Docent Model Orientation
- Documentation reviewed: `ingestion.md`, `https://docs.transluce.org/llms.txt`,
  `concepts/chat-messages.md` (ChatMessage types, `ContentReasoning`).
- Important SDK/model assumptions:
  - `parse_chat_message` converts each dict into the right `ChatMessage` subclass.
  - Assistant `content` may be a list of content blocks, so the reasoning trace
    stays a first-class `reasoning` block rather than being concatenated into the
    answer text. This matters here: the whole analysis is about the trace, and
    flattening it would make "what the model finally said" indistinguishable from
    "how it got there".
  - `AgentRun` IDs are assigned by the SDK.

## Proposed Docent Structure
- Collection: `tsrbench-160-qwen36-full`
- AgentRun unit: one instance, i.e. one (model, condition, instance_id) triple.
  This is the right analysis unit: each is an independent, stateless request over
  a frozen prompt, and the questions being asked ("which strategy did this run
  commit to") are per-instance.
- TranscriptGroup usage: none. There are no attempts, phases, or pass@k here -
  one request per instance, no retries that produced an answer.
- Transcript usage: one per AgentRun. Single agent, single turn.

## Field Mapping
| Source | Docent target | Notes |
| --- | --- | --- |
| `prompts/system.txt` | message role `system` | the frozen prompt, byte-identical across all runs and all three models |
| `tsrbench160/cli/full/<id>.txt` | message role `user` | the frozen question, verified against `manifest.json` before the run |
| `reasoning` | assistant `ContentReasoning.reasoning` | verbatim, never truncated |
| `content` | assistant text block | the final JSON the model was asked to emit |
| `gold_answer`, `prediction` | metadata | letter A-D |
| correct | `metadata.scores.correct` | 0/1, so Docent can score and filter |
| `condition`, `condition_gloss` | metadata | one of five one-factor conditions; only FULL in this batch |
| `domain`, `n_events` | metadata | GDELT domain (8 levels) and 6/7/8 events, the two stratification factors |
| `reasoning_chars`, `completion_tokens`, `prompt_tokens` | metadata | lets a query ask for short traces that were nonetheless correct |
| `finish_reason`, `truncated` | metadata | separates "answered" from "ran the ceiling out" |
| `prompt_sha256`, `system_prompt_sha256` | metadata | provenance: proves this run saw the same bytes as the other models' runs |
| `confidence`, `evidence_articles` | metadata | the model's self-report, useful as a calibration axis |

## Omitted Data
| Field/File | Reason | Impact |
| --- | --- | --- |
| Qwen NO_TS / SHUFFLED / RELATIVE (452 runs) | This batch answers a question about the reference condition only. Ingesting the interventions as well would triple the volume for a question they do not bear on. | None for this analysis. They are one flag away (`--conditions`) and can be added to the same collection later. |
| Sonnet-5 (800 runs) | Its reasoning traces do not exist: the Claude CLI returns thinking blocks whose text is encrypted, verified both live and across all 805 stored session transcripts (624 thinking blocks, 0 with text). | Sonnet cannot appear in any trace-level analysis. Its accuracy numbers stand on their own elsewhere. |
| GLM-5.3-Flash (in progress) | The Z.AI sweep is still running; FULL is complete but the other conditions are not. | Ingesting a partial model would bias a cross-model comparison toward whichever instances happened to finish first. Add once the sweep ends. |
| 4 of 160 FULL instances | The model ran the 22,000-token completion ceiling out without producing a final answer, so no result file exists. Their partial traces are in `failures_full.jsonl`. | Accuracy in the paper counts them wrong; they are simply absent here. 156 of 160 present. |

## Confirmation
- Collection name: `tsrbench-160-qwen36-full`
- Data context: Qwen3.6-35B-A3B answering TSRBench-160's FULL condition - order 6-8
  GDELT news events chronologically, given the events, a GoldsteinScale time series,
  and the event timestamps in a stated random order with no event-to-time mapping.
  Decoding was greedy and identical across every Qwen run (temperature 0.0,
  top_p 1.0, seed 20260823, ceiling 22000).
- Analysis goals: cluster the traces by the strategy each commits to, independent of
  whether it was right. Two candidate strategies to test explicitly:
  (a) assuming the k-th listed timestamp belongs to event k - already shown to be the
      gold answer in 0 of 49 items yet the nearest option chosen in 45% (chance 25%,
      p = 0.0025) on the 50-item study;
  (b) trying to invert GoldsteinScale numbers into event semantics - observed
      verbatim in GLM traces, and forbidden by construction: 12,340 series points
      take only 197 distinct values.
  Report each cluster's size and accuracy.
- Approval mode and source: **pending** - `client.get_preferences()` cannot be read
  without an API key, so confirmation is required.
- User confirmed, if required: **not yet**

## Execution Log
- Installed the Claude Code plugin by hand. `uvx docent@latest setup` cannot finish
  it on Windows: `_setup_claude_plugin` shells out with
  `subprocess.run(["claude", ...])`, and CreateProcess does not apply PATHEXT, so
  `claude.CMD` is never found even though `shutil.which("claude")` finds it and the
  step before prints "Found claude". Ran the two commands it would have run:
  `claude plugin marketplace add TransluceAI/claude-code-plugins` and
  `claude plugin install docent@transluce-plugins`. Plugin 0.2.2 is enabled.
  Setup also needs `PYTHONIOENCODING=utf-8` on a zh-CN console: it prints a check
  mark, which the GBK codepage cannot encode, and dies with UnicodeEncodeError.
- Wrote `ingest_docent.py`.
- Converted all 156 records: **156 converted, 0 failed**.
- `check_agent_runs`: **`TranscriptCheckReport(warnings=())`** - no warnings.
- Blocked before upload: no API key.

## Verification
- Source records: 156
- Converted: 156
- Failed conversions: 0
- Uploaded: pending - blocked on the API key
- Sanity warnings: 0
- Collection URL: pending
