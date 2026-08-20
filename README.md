# Stop-Fitting-Shadows-Put-the-World-Back-in-Time-Series-Modeling

## What this pipeline does

We start from 50 MTBench finance instances ("anchor instances") in `c0_data.json`.
Each anchor instance contains:

- a time series and its timestamps
- one ground-truth (GT) news article and its publication timestamp
- one MCQA question
- one gold answer

From each anchor instance the pipeline renders four prompt variants — the four
experimental conditions — and writes them as JSONL, one file per condition.

`c0_data.json` is not tracked in git; place it at the repo root before running
the build (or point at it with `--data`).

```
c0_data.json (50 anchor instances)
        |
        |  sample 10 distractors  ->  shuffle GT + distractors   (once per instance,
        |                                                         seeded by seed+instance_id)
        v
  ordered article pool (11 articles)
        |
        +--> C0   GT only, timestamps kept
        +--> C1   full pool, timestamps kept
        +--> C2   same pool, same order, temporal information removed
        +--> C3   pool minus GT, timestamps kept
        |
        v
  out/c0.jsonl  out/c1.jsonl  out/c2.jsonl  out/c3.jsonl  out/manifest.json  out/examples/
        |
        v
  verify_conditions.py  (re-checks invariance from the rendered prompts)
```

## The four conditions

**C0 — GT only**
- timestamped time series
- ground-truth article only
- temporal information preserved
- clean / upper-bound condition

**C1 — GT + distractors, timestamps preserved**
- same time series as C0
- GT article + 10 distractor articles
- timestamps preserved for both the time series and the articles
- distractors are shuffled together with the GT article
- the GT article is not identified to the model

**C2 — same pool as C1, temporal information removed**
- exactly the same time-series values
- exactly the same GT article
- exactly the same 10 distractors
- exactly the same article order as C1
- time-series timestamps replaced by ordinal positions
- publication timestamps removed
- temporal expressions in article title and text deterministically masked with
  `[DATE]`, `[YEAR]`, `[QUARTER]`
- purpose: make C1 vs C2 a controlled comparison in which temporal information is
  the intended manipulated factor

**C3 — distractors only, timestamps preserved**
- same timestamped time series as C1
- the same 10 distractors
- GT article removed
- timestamps preserved
- distractor order is the C1 order with GT filtered out

## Build logic (`build_conditions.py`)

1. Load the 50 anchor instances from `c0_data.json`.
2. Sample distractors once per instance.
3. Shuffle GT + distractors once per instance.
4. Render C1, C2 and C3 from that same ordered article pool.
5. Apply temporal masking only when rendering C2.
6. Write the rendered conditions plus `manifest.json` and `examples/`.
7. Run `verify_conditions.py` to re-check the invariance requirements from the
   rendered outputs.

Key implementation property: distractor sampling and shuffling happen **once per
instance**, seeded by `(seed, instance_id)`. C1, C2 and C3 are all derived from
that one ordered pool. C2 is never re-sampled and never re-shuffled; C3 is
produced by filtering GT out of the same ordered list.

## Temporal masking (`temporal_mask.py`)

- deterministic ordered-regex masking; same input always yields the same output
- no LLM rewriting
- allowed replacement tokens are exactly `[DATE]`, `[YEAR]`, `[QUARTER]`
- intent: remove explicit temporal identifiers while leaving non-temporal wording
  unchanged

Used only for C2 article titles and bodies (and, optionally, the question — see
Open design decisions).

## Verification / invariance checks (`verify_conditions.py`)

The verifier parses the rendered prompt files and re-derives its claims from
them, rather than trusting the build process. Representative checks:

- same instance set, question and time-series values across paired conditions
- same distractor identities where required
- same article order between C1 and C2
- C3 equals the C1 pool with GT removed, distractor order preserved
- re-masking each C1 article reproduces the corresponding C2 article byte for byte
- no explicit year, ISO date or `Q1`–`Q4` token survives in a C2 news context
- a rebuild with the same seed is byte-identical

All 21 current checks pass on the current build.

## How to run

```bash
python build_conditions.py
python verify_conditions.py
```

or:

```bash
python build_conditions.py && python verify_conditions.py
```

## Outputs (`out/`, gitignored)

| file | contents |
| --- | --- |
| `c0.jsonl` | 50 C0 prompts |
| `c1.jsonl` | 50 C1 prompts |
| `c2.jsonl` | 50 C2 prompts |
| `c3.jsonl` | 50 C3 prompts |
| `manifest.json` | per-instance build record: seed, article order, GT position, mask counts, invariance hashes |
| `examples/` | one instance rendered in all four conditions, as plain text, for eyeballing |

Each JSONL record carries `instance_id`, `condition`, `ticker`, `answer`,
`n_articles`, `article_order` (source instance ids in prompt order),
`gt_position`, `timestamps_present` and the fully rendered `prompt`.

## Prompt and inference protocol

One protocol is shared by all four conditions. It is defined in two places only:
`prompts/system.txt` (system prompt) and `PROMPT_TEMPLATE` / `RESPONSE_FORMAT` in
`build_conditions.py` (user prompt). Nothing downstream appends to a prompt.

This is an experimental extension of the MTBench finance MCQA task, **not** an
exact reproduction of its published baseline; the numbers here are not
comparable to published MTBench Claude scores.

**Inherited from MTBench**

- the finance MCQA task and its semantics
- the original question and answer options, unmodified
- the 7-day stock-price context
- zero-shot answering from the provided time series + news context
- MCQA accuracy as the main quantitative score

**Intentionally different here**

- observation-level timestamps are exposed explicitly in timestamp-preserving
  conditions
- C0/C1/C2/C3 apply controlled context interventions
- output is structured JSON rather than a bare letter
- a short rationale, `evidence_articles` and self-reported confidence are
  collected for diagnostics (they are not part of the primary metric)
- a Sonnet 5 CLI pilot instead of the original MTBench model configuration

**Fixed across conditions**

system prompt · user-prompt wording · response schema · model and CLI
configuration · one fresh invocation per instance · no external tools · no
conversation history · MCQA task framing.

Only the content that C0/C1/C2/C3 explicitly define — the time-series rendering
and the news context — is allowed to differ. The prompts contain no
condition-specific hints: nothing states that articles are distractors, that
timestamps were removed, that a ground-truth article is absent or present, or
that any article aligns with the end of the time series. The model has to infer
temporal relations from what the condition exposes.

The user prompt is:

```
Task

Answer the following multiple-choice question using the provided financial time series and news context.

Time Series

Ticker: {TICKER}

{TIME_SERIES}

News Context

{NEWS_CONTEXT}

Question

{MCQA_QUESTION}

Select the single best answer.

{RESPONSE_FORMAT}
```

and `{RESPONSE_FORMAT}`, the single response instruction in the whole pipeline,
asks for one JSON object with `answer` (`<A|B|C|D>`, no example letter is given),
`confidence`, a brief 1-3 sentence `rationale`, and `evidence_articles`. The
rationale is a short externally useful justification for error analysis — private
chain-of-thought is never requested.

## Running the C0 baseline

The C0 pilot only checks that the C0 prompt is runnable and that the model can do
the original MCQA task. C1/C2/C3 are untouched by it.

```bash
python build_conditions.py
python verify_conditions.py
python export_c0_cli.py
```

`export_c0_cli.py` reads `out/c0.jsonl` and writes one prompt file per instance
plus an index:

```
out/c0_cli/408.txt, 96.txt, ...   the C0 prompt, byte for byte
out/c0_cli/index.jsonl            {"instance_id": 408, "prompt_file": "408.txt", "gold_answer": "B", "ticker": "SPY"}
```

The exporter adds nothing to the prompt — the response instruction is already in
it — and asserts that every exported file is byte-identical to the `prompt` field
it came from. `python export_c0_cli.py --check` re-runs that comparison without
rewriting anything.

Then:

```
out/c0_cli/*.txt
        ↓
Claude CLI / Sonnet 5
        ↓
results/c0_raw/*.txt
        ↓
python collect_c0_results.py
        ↓
results/c0_sonnet5.jsonl
        ↓
python score_c0.py
        ↓
results/c0_summary.json
```

### Claude CLI invocation

`claude` is installed locally (v2.1.177). The pilot runs one fresh non-interactive
invocation per instance, with no conversation history between instances:

```bash
claude -p --model claude-sonnet-5 --system-prompt-file prompts/system.txt --tools "" --safe-mode --strict-mcp-config < out/c0_cli/408.txt > results/c0_raw/408.txt
```

| flag | effect (from the installed CLI's `--help`) |
| --- | --- |
| `-p` | non-interactive: print the response and exit |
| `--system-prompt-file` | use `prompts/system.txt` as the system prompt |
| `--tools ""` | disable all built-in tools |
| `--safe-mode` | ignore CLAUDE.md, skills, plugins, hooks, MCP servers, custom agents |
| `--strict-mcp-config` | no MCP servers beyond `--mcp-config` (none is given) |

All instances (resumable — instances already collected are skipped; pass a second
argument to stop after N instances):

```bash
bash run_c0_claude.sh claude-sonnet-5 3
```

Caveats, none of them papered over:

- Every flag above was confirmed to exist in this CLI version (a deliberately
  bogus flag is rejected with `unknown option`, these are not). They have **not**
  been confirmed by a successful end-to-end run: the local CLI returns
  `401 OAuth access token has expired`. Re-authenticate before running the pilot.
- The model identifier is **not** validated client-side — a nonsense `--model`
  value also reaches the auth error — so `claude-sonnet-5` is unverified here. If
  it is rejected once authenticated, fall back to the `sonnet` alias and record
  which one was used.
- Decoding parameters (temperature, top-p) are not exposed by the CLI and are
  therefore **not explicitly controlled**. Do not report this pilot as
  temperature 0.
- No API key and no SDK is used anywhere in this workflow.

`run_c0_claude.sh` writes `results/c0_run_metadata.json` (CLI version, requested
model, system-prompt file, flags, tools disabled, fresh invocation per instance,
temperature "not explicitly controlled", instance count, start time) so a run can
be reconstructed later. The served model is not reported by the CLI's text output,
so that field records "not observed" rather than a guess.

### Collecting and scoring

```bash
python collect_c0_results.py
python score_c0.py
```

`collect_c0_results.py` reads each `results/c0_raw/<id>.txt`, locates the JSON
object (tolerating markdown fences and a little surrounding prose), validates it,
and writes one record per instance to `results/c0_sonnet5.jsonl`. Missing and
malformed outputs are listed in `results/c0_collect_report.json` and printed —
never guessed at, never repaired by a model. `score_c0.py` reports completed /
correct / accuracy, missing and malformed instances, the A–D prediction
distribution and mean confidence overall and split by correctness, and writes
`results/c0_summary.json`.

Field meanings (see also `results/README.md`):

| field | meaning |
| --- | --- |
| `gold_answer` | the dataset's answer, taken from the index; never overwritten |
| `prediction` | the model's answer, parsed from its JSON |
| `rationale` | the model's short justification |
| `raw_output` | the unmodified model output, preserved verbatim |
| `correct` | computed as `prediction == gold_answer` |

`confidence` is the model's **self-reported** confidence, not a calibrated
probability. Accuracy is the primary metric; rationale, `evidence_articles` and
confidence are diagnostic only.

The rationale is intended for later qualitative / error analysis. It is a short
justification, not a request for private chain-of-thought.

## Open design decisions

**1. Distractor source.** No separate distractor pool exists in the repo, so the
current provisional implementation samples distractors from the GT articles of
other anchor instances, excluding same-ticker articles. This is a placeholder
implementation choice, not necessarily the final scientific design. A
purpose-built distractor pool can replace it without changing the downstream
rendering logic.

**2. Temporal tokens in MCQA questions.** 17 of the 50 questions contain explicit
year, month or quarter information. By default the question stays invariant
across conditions, so those tokens remain in C2. The pipeline supports a
`--mask-question` option if the experiment later decides to remove temporal
information from the question as well; `manifest.json` records
`question_has_temporal_tokens` per instance.

**3. Boilerplate.** The scraped articles contain site boilerplate, so prompts can
be long. This is currently left untouched because it is identical across paired
conditions.
