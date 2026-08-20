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
