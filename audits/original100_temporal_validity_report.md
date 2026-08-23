# Outcome-blind temporal-validity audit of the original 100 MCQA

Sources: `c0_data.json` (50) and `hard50_data.json` (50). No results file, condition build, distractor pool or model output was read. No source file was modified and no inference was run.

## 1. Pool integrity

- **c0_data.json**: 50 rows, 50 unique ids, duplicates none, output-window-like fields **NONE**
  - time-series lengths seen: [309, 312, 324, 339, 380, 383, 390]; rows with duplicated (timestamp, value) samples: [268, 61]
- **hard50_data.json**: 50 rows, 50 unique ids, duplicates none, output-window-like fields **NONE**
  - time-series lengths seen: [276, 312, 337, 354, 390, 391]; rows with duplicated (timestamp, value) samples: [99, 278]
- combined: **100 rows, 100 unique ids**, id overlap between files none
- schema difference: hard50_data.json carries an extra 'subset' field (constant value 'hard_50'); every other field is identical in both files
- the brief names c0_data(2).json; the repository holds c0_data.json, read-only, 50 rows, with exactly the fields the brief lists

## 2. Temporal geometry

- instances with any time-series point strictly after the ground-truth publication: **0 / 100**
- instances with none: **100 / 100**
- publication minus last supplied point: min 0.00 h, median 1.84 h, max 89.08 h (all positive - publication always follows the window)

| gap (hours) | n |
| --- | --- |
| <=0.1 | 44 |
| 0.1-2 | 13 |
| 2-12 | 15 |
| 12-24 | 22 |
| >24 | 6 |

Having no post-publication series is the official input-window protocol and is not an error in itself. What follows asks whether the question semantics need what the protocol does not supply.

## 3. Option temporal requirements (400 options)

- ABSOLUTE_DATE_REFERENCE: 13
- BEFORE_AFTER_COMPARISON_REQUIRED: 4
- FUTURE_FORECAST_OR_EXPECTATION: 46
- POST_PUBLICATION_PRICE_REQUIRED: 150
- PRE_PUBLICATION_OR_STATIC: 151
- TEMPORALLY_MISLABELED_OBSERVED_MOVE: 36

Options requiring post-publication prices or a before/after comparison: **154 / 400**.

Options that relabel a supplied pre-publication move as happening after the news: **36 / 400** - 4C, 37A, 49B, 49C, 91D, 120C, 123A, 130B, 140B, 265D, 320B, 333D, 371B, 441D, 36C, 55C, 66D, 78B, 78C, 92D, 98D, 142C, 174C, 215C, 233D, 278A, 295C, 308C, 317B, 317C, 353B, 357A, 437B, 437C, 466A, 484C

## 4. Mechanical price and date checks

a named level counts as present in the window when some sample matches it within max(0.02 absolute, 0.0015 relative).

### Price levels named by an option but absent from the supplied series

| id | option | gold? | claimed | closest actual |
| --- | --- | --- | --- | --- |
| 15 | C | yes | 80 | 82.57 |
| 19 | C |  | 116.32 | 115.36 |
| 56 | D |  | 160.86 | 163.43 |
| 96 | C |  | 147.61 | 148.13 |
| 122 | D | yes | 175 | 168.78 |
| 133 | D |  | 100 | 99.425 |
| 147 | A |  | 283.66 | 284.11 |
| 234 | B | yes | 180.81 | 179.72 |
| 268 | C | yes | 2023 | 2071.12 |
| 303 | D | yes | 88.22 | 87.7104 |
| 313 | D | yes | 18 | 19.655 |
| 313 | D | yes | 19 | 19.655 |
| 334 | C | yes | 53.83 | 49.13 |
| 369 | A |  | 51.2 | 50.855 |
| 375 | B |  | 250 | 257.43 |
| 376 | B |  | 354.74 | 351.65 |
| 10 | B |  | 102 | 101.21 |
| 99 | D |  | 85 | 85.21 |
| 117 | C |  | 45 | 43.1 |
| 131 | C |  | 39.84 | 39.665 |
| 148 | A |  | 98.27 | 95.73 |
| 223 | C |  | 55.4 | 56.64 |
| 223 | D |  | 55.28 | 56.64 |
| 238 | B |  | 109.09 | 108.11 |
| 249 | A | yes | 128.18 | 127.31 |
| 278 | B |  | 28.57 | 29.36 |
| 279 | B |  | 190.56 | 188.295 |
| 357 | C |  | 51.02 | 50.87 |
| 382 | B | yes | 157.42 | 159.89 |
| 418 | A |  | 45.53 | 45.46 |
| 418 | D | yes | 46.85 | 45.46 |

Not every number in this table is a share price - analyst targets, P/E ratios and percentages land in the same numeric band and are noted per instance in the JSONL.

### Explicit dates outside the supplied window

| id | option | gold? | phrase |
| --- | --- | --- | --- |
| 96 | C |  | November 12 |
| 140 | B | yes | August 26, 2021 |
| 313 | D | yes | April 19 |
| 36 | A |  | July 21, 2021 |
| 41 | D |  | March 20 |
| 98 | B |  | September 30 |
| 98 | D | yes | September 30 |
| 131 | C |  | October 4 |
| 148 | A |  | June 24 |
| 238 | B |  | July 29, 2022 |
| 249 | A | yes | January 3, 2023 |
| 252 | A |  | January 26 |
| 263 | B |  | June 29, 2023 |
| 263 | C | yes | June 29, 2023 |
| 278 | D |  | August 9 |
| 279 | B |  | June 30, 2023 |
| 295 | B |  | May 22, 2023 |
| 353 | B | yes | March 24, 2022 |
| 357 | C |  | July 27, 2022 |
| 360 | B |  | January 27 |
| 382 | B | yes | April 25, 2023 |
| 454 | D |  | May 9 |
| 481 | D | yes | September 21, 2022 |

## 5. Gold-answer support

- GOLD_FULLY_VERIFIABLE: 9
- GOLD_REQUIRES_UNAVAILABLE_POST_PUBLICATION_TS: 28
- GOLD_SEMANTICALLY_VERIFIABLE: 54
- GOLD_TEMPORALLY_MISLABELED: 9

Problematic golds (**37**): [37, 47, 53, 54, 55, 56, 98, 123, 140, 142, 176, 201, 215, 216, 218, 229, 234, 249, 251, 252, 263, 265, 278, 302, 303, 308, 313, 333, 353, 357, 375, 382, 405, 418, 437, 441, 481]

- requires unavailable post-publication series: [47, 53, 54, 56, 142, 176, 201, 216, 218, 229, 234, 249, 251, 252, 263, 302, 303, 308, 313, 333, 357, 375, 382, 405, 418, 437, 441, 481]
- describes a supplied pre-publication move as post-publication: [37, 55, 98, 123, 140, 215, 265, 278, 353]

## 6. Instance well-posedness

Precedence: GOLD_REQUIRES_UNAVAILABLE_FUTURE > TEMPORAL_LABEL_INCONSISTENCY > OTHER_AMBIGUITY > GOLD_VALID_BUT_DISTRACTORS_UNDERDETERMINED > STRICTLY_WELL_POSED

| class | combined | c0 | hard50 |
| --- | --- | --- | --- |
| GOLD_REQUIRES_UNAVAILABLE_FUTURE | 28 | 13 | 15 |
| TEMPORAL_LABEL_INCONSISTENCY | 25 | 11 | 14 |
| OTHER_AMBIGUITY | 1 | 0 | 1 |
| GOLD_VALID_BUT_DISTRACTORS_UNDERDETERMINED | 21 | 13 | 8 |
| STRICTLY_WELL_POSED | 25 | 13 | 12 |

- **GOLD_REQUIRES_UNAVAILABLE_FUTURE**: [47, 53, 54, 56, 142, 176, 201, 216, 218, 229, 234, 249, 251, 252, 263, 302, 303, 308, 313, 333, 357, 375, 382, 405, 418, 437, 441, 481]
- **TEMPORAL_LABEL_INCONSISTENCY**: [4, 36, 37, 49, 55, 66, 78, 91, 92, 98, 120, 123, 130, 140, 174, 215, 233, 265, 278, 295, 317, 320, 353, 371, 466]
- **OTHER_AMBIGUITY**: [10]
- **GOLD_VALID_BUT_DISTRACTORS_UNDERDETERMINED**: [6, 18, 19, 35, 96, 122, 124, 131, 133, 147, 148, 172, 191, 223, 238, 243, 262, 279, 369, 376, 467]
- **STRICTLY_WELL_POSED**: [15, 41, 50, 51, 61, 99, 117, 136, 145, 182, 220, 256, 268, 274, 275, 288, 311, 334, 360, 394, 408, 448, 453, 454, 484]

## 7. Strict eligibility

Criterion: instance_class == STRICTLY_WELL_POSED, decided only from question and option semantics, the ground-truth publication time, the supplied window and the ground-truth article

- **strict_temporal_eligible = true for 25 / 100**
- c0_data.json: 13 - [15, 50, 51, 61, 256, 268, 274, 275, 288, 311, 334, 408, 453]
- hard50_data.json: 12 - [41, 99, 117, 136, 145, 182, 220, 360, 394, 448, 454, 484]

Sensitivity: if every borderline call were resolved the other way, the eligible pool would reach at most **31**.

## 8. Borderline cases

32 instances carry an explicit alternative classification; they are written out in `original100_borderline_review.md` and are not silently resolved.

Confidence over the 100: {'HIGH': 28, 'MEDIUM': 72, 'LOW': 0}

## 9. Adjudication rules used

- **mislabeled_observed_move** - an option is TEMPORALLY_MISLABELED_OBSERVED_MOVE when it frames a move as after/following/since the publication AND the move it describes is demonstrably the supplied pre-publication move - established either by matching its named price levels inside the window, or by the ground-truth article reporting the same move as having happened at or before publication. A merely false post-publication claim is not a mislabel.
- **gold_requires_vs_mislabeled** - GOLD_TEMPORALLY_MISLABELED needs the same demonstration. Where a gold asserts post-publication price behaviour but names no level and the article does not report it, the honest verdict is GOLD_REQUIRES_UNAVAILABLE_POST_PUBLICATION_TS with a borderline note - the relocation cannot be shown, only suspected.
- **incorrect_statement_items** - for 'which statement is incorrect' items the gold is the false option. If its falsity follows from article content or from internal logic it is GOLD_SEMANTICALLY_VERIFIABLE even when its wording is about post-publication prices; if refuting it would need the absent prices, it is GOLD_REQUIRES_UNAVAILABLE_POST_PUBLICATION_TS.
- **distractor_underdetermined** - a competing option makes the item GOLD_VALID_BUT_DISTRACTORS_UNDERDETERMINED only when evaluating that option needs absent post-publication prices. An option that fails on its own logic, on an absurd causal claim, or on article facts does not count, even if it carries post-publication wording.
- **price_tolerance** - a named level counts as present in the window when some sample matches it within max(0.02 absolute, 0.0015 relative).

## 10. Decision support

**A. Are there at least 50 strictly well-posed originals?** No. There are **25**, and the optimistic upper bound after flipping every borderline call is **31**.

**C. How many are available, and why the shortfall?** 25. The dominant reason is that 28 items have a gold whose truth needs post-publication prices the protocol does not supply, and a further 25 contain an option - often the gold - that relabels supplied pre-publication movement as happening after the news.

**B. Feasibility of a later outcome-blind filtered subset.** A 50-item temporally-filtered subset cannot be drawn from this pool. A smaller one (n = 25 as classified here) is feasible and would be outcome-blind by construction, since this flag never touches model results, distractor coverage or previous membership.

**D. Systematic mismatch in the raw pool?** Yes. 154 of 400 options require post-publication prices or a before/after comparison, 36 relabel a supplied move, and 37 of 100 golds are themselves problematic. The mismatch is a property of the inherited MTBench MCQA, not of any condition built from it.

**E. Mechanical vs adjudicated.** Mechanical: row counts, id uniqueness, absence of any output-window field, all geometry, every price-level and date match, and the absent-level tables. Adjudicated: the option categories, the gold support class and the instance class - these rest on reading the wording, and 32 of them carry an explicit alternative.
