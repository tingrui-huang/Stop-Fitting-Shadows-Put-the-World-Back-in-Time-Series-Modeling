# Sanity-check study for the timestamp intervention

Diagnostic only. The official C0-C3 experiment, the final-50 membership, the reviewed distractor pool and every existing model output are untouched; all new material lives under `sanity/` and `results/sanity/`.

## 1. Frozen-input integrity

| file | md5 |
| --- | --- |
| `final50_paper_data.json` | `3ed162d022226352db646a16c6a22b09` |
| `final50_paper_manifest.json` | `3c9b63a38160099c7a69d4c820f7384c` |
| `final50_reviewed_pool.jsonl` | `317326f73f98bc7acb9e0170a4074da5` |
| `out_paper50_reviewed/c0.jsonl` | `7e9a97c98c579846dda66a5e52f2db0a` |
| `out_paper50_reviewed/c1.jsonl` | `adac973c6bb13e51f6886377ad3af8c0` |
| `out_paper50_reviewed/c2.jsonl` | `387d18185a50b68334021e36f3f7bf82` |
| `out_paper50_reviewed/c3.jsonl` | `b1d82eadfda28d1f8eca6cc10ce2fd26` |
| `out_paper50_reviewed/manifest.json` | `15c502b51a6b6d8c922427d1980ba080` |
| `prompts/system.txt` | `8931ce674f4e76b9c41860db08bf7085` |

All six sanity conditions were built and hashed **before** any model output was loaded (`sanity/sanity_conditions_manifest.json` carries a SHA-256 per rendered prompt). Article-timestamp derangement seed: `20260823`.

## 2. Accuracy

| condition | n | accuracy | vs chance (0.25) | answer distribution |
| --- | --- | --- | --- | --- |
| C0 (main run) | 50 | **0.88** | +0.63 | - |
| C1 (main run) | 50 | **0.88** | +0.63 | - |
| C2 (main run) | 50 | **0.92** | +0.67 | - |
| C3 (main run) | 50 | **0.78** | +0.53 | - |
| S1_QO_ONLY | 50 | **0.94** | +0.69 | {'A': 10, 'B': 13, 'C': 16, 'D': 11} |
| S2_GT_TEXT_ONLY | 50 | **0.90** | +0.65 | {'A': 12, 'B': 11, 'C': 15, 'D': 12} |
| S3_POOL_TEXT_ONLY | 50 | **0.94** | +0.69 | {'A': 12, 'B': 12, 'C': 16, 'D': 10} |
| S4_TS_ONLY | 50 | **0.94** | +0.69 | {'A': 12, 'B': 12, 'C': 16, 'D': 10} |
| S5_C2_QO_DATE_MASK | 50 | **0.94** | +0.69 | {'A': 11, 'B': 14, 'C': 17, 'D': 8} |
| S6_C1_METADATA_TIMESTAMP_SHUFFLE | 50 | **0.94** | +0.69 | {'A': 11, 'B': 12, 'C': 17, 'D': 10} |

Missing / malformed across the six sanity conditions: 0 / 0.

## 3. Phase 1 static cue audit

these are counts of what sits in the question and options, outside the evidence context that C2 masks. They are not labelled leakage - the point is to measure how much information survives the intervention.

| cue present in the MCQA | instances (of 50) | occurrences |
| --- | --- | --- |
| absolute_date | 13 | 18 |
| fiscal_year | 2 | 2 |
| named_price_level | 24 | 49 |
| numbers_shared_with_gt_article | 33 | 98 |
| percentage | 23 | 44 |
| publication_reference | 47 | 111 |
| quarter | 8 | 11 |
| relational_temporal_language | 50 | 228 |
| ticker_symbol | 50 | 66 |
| year | 14 | 17 |

## 4. Intervention audits

**S5 masking audit**: 26/50 instances changed, 38 spans replaced, 0 flagged - `NO_SEMANTICALLY_DESTRUCTIVE_MASK_FOUND`. Relational wording (before / after / following / prior / since), named price levels and percentages are preserved in every changed instance.

**S6 shuffle audit**: 50 instances, all mechanical checks pass (0 flagged) - same article ids and order, unchanged timestamp multiset, zero fixed points, no article keeps its own timestamp, only `Published:` lines differ, time series and MCQA unchanged.

## 5. Paired comparisons

EXPLORATORY / SANITY-CHECK analyses. Exact McNemar p-values are reported descriptively on 50 paired items and are not primary hypothesis tests.

| comparison | both correct | orig->wrong | orig->correct | both wrong | answers changed | exact McNemar p |
| --- | --- | --- | --- | --- | --- | --- |
| C1_vs_S3_POOL_TEXT_ONLY | 42 | 2 | 5 | 1 | 8/50 | 0.4531 |
| C2_vs_S5_C2_QO_DATE_MASK | 46 | 0 | 1 | 3 | 1/50 | 1.0000 |
| C1_vs_S6_C1_METADATA_TIMESTAMP_SHUFFLE | 44 | 0 | 3 | 3 | 4/50 | 0.2500 |

## 6. Observable evidence use

Declared reading: an article counts if the model listed it in `evidence_articles`.

| condition | cites GT | cites Type A | cites Type B | no evidence |
| --- | --- | --- | --- | --- |
| C1 (main) | 48 | 1 | 3 | 1 |
| C2 (main) | 43 | 8 | 6 | 4 |
| S3_POOL_TEXT_ONLY | 45 | 8 | 3 | 1 |
| S6_C1_METADATA_TIMESTAMP_SHUFFLE | 42 | 5 | 7 | 3 |

## 7. Phase 5 decision logic

**A. Question/option shortcut.** S1_QO_ONLY = **0.94** with no time series, no ground-truth article and no distractors, against a 0.25 chance level and C1 = 0.88, C2 = 0.92. That is 107% of C1's accuracy recovered from the MCQA text alone.

**B. Text-semantic shortcut.** S2_GT_TEXT_ONLY = **0.90**, S3_POOL_TEXT_ONLY = **0.94**, C1 = 0.88. S3 differs from C1 only by deleting the time series.

**C. Question/option temporal leakage.** C2 = 0.92, S5_C2_QO_DATE_MASK = **0.94**; 1 of 50 answers changed (26 instances actually carried a maskable date).

**D. Actual timestamp use.** C1 = 0.88, S6 = **0.94** with every article's publication timestamp deranged; 4 of 50 answers changed. S6 tests metadata timestamps only - dates inside article prose are left in place, so a null result here does not mean the model ignores time altogether.

**E. Overall experiment validity.** **1. STRONG SHORTCUT EVIDENCE**

S1_QO_ONLY (0.94) equals or exceeds every condition that carries evidence, including C0 (0.88), C1 (0.88), C2 (0.92) and C3 (0.78). The MCQA label is recoverable from the question and answer options alone, with no time series, no ground-truth article and no distractors. Adding the evidence context does not raise accuracy - it lowers it slightly.

Interpretation 3 also has support and is not in conflict with it: observable evidence use does move under the interventions (Type-A citation 1 -> 8 from C1 to C2; GT citation 48 -> 42 from C1 to S6) while accuracy stays flat. The two findings combine into a single claim - **MCQA accuracy on this benchmark is not a measure of temporal grounding**, because the label survives removing the evidence entirely.

## 8. Caveats

- **Decoding is not controlled.** The CLI exposes no temperature or top-p, so this is not temperature 0 and single-run differences of a few items are within plausible run-to-run noise. Every condition here is one sample per instance, exactly as in the main runs.
- **S1/S2/S4 could not reuse the C0-C3 Task sentence verbatim**; it promises a time series and a news context those ablations withhold. The response-format block is byte-identical in all six conditions, and the MCQA text is byte-identical to the frozen benchmark.
- **S6 deranges metadata timestamps only.** Dates inside article prose are untouched by design, so a flat S6 shows the model does not lean on the `Published:` field - not that it ignores time entirely.
- The McNemar p-values are descriptive on 50 paired items and are labelled exploratory; they are not primary hypothesis tests.
- No dataset membership, distractor, gold label or main-run output was changed, and nothing was committed.
