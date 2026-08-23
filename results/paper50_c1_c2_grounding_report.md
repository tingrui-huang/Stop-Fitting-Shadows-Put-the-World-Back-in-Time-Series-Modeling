# All-50 C1/C2 grounding audit - Sonnet-5, final frozen benchmark

Diagnostic only. No benchmark file, distractor, mask, option or model output was modified and no inference was run.

Two readings are reported throughout, because they answer different questions:

- **declared** - an article counts as support if the model listed it in `evidence_articles`. No rationale in either condition names an article and then rejects it, so `cited_but_rejected` is empty everywhere.
- **rationale** - only articles the rationale actually builds on count. Articles listed but never mentioned are excluded.

The truth is bracketed by the two.

## C1 - answer accuracy 44/50 = 0.88

### declared reading

| grounding | n |
| --- | --- |
| GROUNDED | 46 |
| MIXED_GROUNDING | 2 |
| NO_CLEAR_GROUNDING | 1 |
| TEMPORALLY_INVALID_GROUNDING | 1 |

grounded rate 0.92, invalid-grounding rate 0.02, mixed rate 0.04

| answer x grounding | n | instances |
| --- | --- | --- |
| correct + GROUNDED | 40 | [37, 41, 49, 50, 51, 53, 55, 61, 66, 120, 123, 124, 133, 140, 147, 148, 172, 182, 191, 215, 233, 234, 252, 256, 268, 274, 275, 295, 303, 313, 317, 320, 334, 353, 371, 405, 441, 453, 454, 484] |
| correct + MIXED_GROUNDING | 2 | [15, 288] |
| correct + NO_CLEAR_GROUNDING | 1 | [98] |
| correct + TEMPORALLY_INVALID_GROUNDING | 1 | [35] |
| wrong + GROUNDED | 6 | [18, 47, 96, 176, 201, 265] |

correct but temporally invalid: [35]

### rationale reading

| grounding | n |
| --- | --- |
| GROUNDED | 46 |
| NO_CLEAR_GROUNDING | 3 |
| TEMPORALLY_INVALID_GROUNDING | 1 |

grounded rate 0.92, invalid-grounding rate 0.02, mixed rate 0.00

| answer x grounding | n | instances |
| --- | --- | --- |
| correct + GROUNDED | 42 | [15, 37, 41, 49, 50, 51, 53, 55, 61, 66, 120, 123, 124, 133, 140, 147, 148, 172, 182, 191, 215, 233, 234, 252, 256, 268, 274, 275, 288, 295, 303, 313, 317, 320, 334, 353, 371, 405, 441, 453, 454, 484] |
| correct + NO_CLEAR_GROUNDING | 1 | [98] |
| correct + TEMPORALLY_INVALID_GROUNDING | 1 | [35] |
| wrong + GROUNDED | 4 | [18, 47, 201, 265] |
| wrong + NO_CLEAR_GROUNDING | 2 | [96, 176] |

correct but temporally invalid: [35]

## C2 - answer accuracy 46/50 = 0.92

### declared reading

| grounding | n |
| --- | --- |
| GROUNDED | 34 |
| MIXED_GROUNDING | 9 |
| NO_CLEAR_GROUNDING | 4 |
| TEMPORALLY_INVALID_GROUNDING | 3 |

grounded rate 0.68, invalid-grounding rate 0.06, mixed rate 0.18

| answer x grounding | n | instances |
| --- | --- | --- |
| correct + GROUNDED | 31 | [18, 37, 41, 49, 50, 53, 55, 61, 66, 120, 123, 124, 133, 147, 148, 172, 182, 191, 233, 268, 275, 288, 295, 303, 313, 320, 334, 405, 453, 454, 484] |
| correct + MIXED_GROUNDING | 8 | [15, 51, 215, 234, 256, 265, 317, 371] |
| correct + NO_CLEAR_GROUNDING | 4 | [96, 98, 140, 353] |
| correct + TEMPORALLY_INVALID_GROUNDING | 3 | [35, 176, 441] |
| wrong + GROUNDED | 3 | [47, 252, 274] |
| wrong + MIXED_GROUNDING | 1 | [201] |

correct but temporally invalid: [35, 176, 441]

### rationale reading

| grounding | n |
| --- | --- |
| GROUNDED | 34 |
| MIXED_GROUNDING | 2 |
| NO_CLEAR_GROUNDING | 9 |
| TEMPORALLY_INVALID_GROUNDING | 5 |

grounded rate 0.68, invalid-grounding rate 0.10, mixed rate 0.04

| answer x grounding | n | instances |
| --- | --- | --- |
| correct + GROUNDED | 31 | [18, 37, 41, 49, 53, 55, 61, 66, 120, 123, 124, 133, 147, 148, 172, 182, 191, 215, 233, 234, 256, 268, 275, 288, 303, 320, 334, 405, 453, 454, 484] |
| correct + MIXED_GROUNDING | 2 | [51, 265] |
| correct + NO_CLEAR_GROUNDING | 9 | [50, 96, 98, 140, 295, 313, 317, 353, 371] |
| correct + TEMPORALLY_INVALID_GROUNDING | 4 | [15, 35, 176, 441] |
| wrong + GROUNDED | 3 | [47, 252, 274] |
| wrong + TEMPORALLY_INVALID_GROUNDING | 1 | [201] |

correct but temporally invalid: [15, 35, 176, 441]

## Grounding transitions C1 -> C2

### declared reading

| transition | n | instances |
| --- | --- | --- |
| GROUNDED -> GROUNDED | 33 | [18, 37, 41, 47, 49, 50, 53, 55, 61, 66, 120, 123, 124, 133, 147, 148, 172, 182, 191, 233, 252, 268, 274, 275, 295, 303, 313, 320, 334, 405, 453, 454, 484] |
| GROUNDED -> INVALID | 2 | [176, 441] |
| GROUNDED -> MIXED | 8 | [51, 201, 215, 234, 256, 265, 317, 371] |
| GROUNDED -> UNCLEAR | 3 | [96, 140, 353] |
| INVALID -> INVALID | 1 | [35] |
| MIXED -> GROUNDED | 1 | [288] |
| MIXED -> MIXED | 1 | [15] |
| UNCLEAR -> UNCLEAR | 1 | [98] |

- right answer, wrong evidence (C1 correct+grounded -> C2 correct+invalid): **[441]**
- grounded -> invalid regardless of correctness: **[176, 441]**
- grounded -> any distractor use: **[51, 176, 201, 215, 234, 256, 265, 317, 371, 441]**

### rationale reading

| transition | n | instances |
| --- | --- | --- |
| GROUNDED -> GROUNDED | 34 | [18, 37, 41, 47, 49, 53, 55, 61, 66, 120, 123, 124, 133, 147, 148, 172, 182, 191, 215, 233, 234, 252, 256, 268, 274, 275, 288, 303, 320, 334, 405, 453, 454, 484] |
| GROUNDED -> INVALID | 3 | [15, 201, 441] |
| GROUNDED -> MIXED | 2 | [51, 265] |
| GROUNDED -> UNCLEAR | 7 | [50, 140, 295, 313, 317, 353, 371] |
| INVALID -> INVALID | 1 | [35] |
| UNCLEAR -> INVALID | 1 | [176] |
| UNCLEAR -> UNCLEAR | 2 | [96, 98] |

- right answer, wrong evidence (C1 correct+grounded -> C2 correct+invalid): **[15, 441]**
- grounded -> invalid regardless of correctness: **[15, 201, 441]**
- grounded -> any distractor use: **[15, 51, 201, 265, 441]**

## Temporal-alias use

### declared reading

| | C1 | C2 |
| --- | --- | --- |
| instances using >=1 Type A | 1 | 8 |
| ... future alias | 0 | 6 |
| ... historical alias | 1 | 4 |
| Type A explicitly rejected | 0 | 0 |

C1 ids: [15]

C2 ids: [35, 51, 176, 201, 215, 265, 317, 371]

### rationale reading

| | C1 | C2 |
| --- | --- | --- |
| instances using >=1 Type A | 0 | 5 |
| ... future alias | 0 | 4 |
| ... historical alias | 0 | 2 |
| Type A explicitly rejected | 0 | 0 |

C1 ids: none

C2 ids: [35, 51, 176, 201, 265]

## EA1 / EA2 - POST-HOC OBSERVABLE DIAGNOSTICS

These are diagnostics, not primary endpoints. Neither is inferred from a wrong answer, and no hidden reasoning is assumed.

| | C1 | C2 |
| --- | --- | --- |
| EA1 candidates (rationale reading) | 0  | 5 [35, 51, 176, 201, 265] |
| EA1 candidates (declared reading) | 1 [15] | 8 [35, 51, 176, 201, 215, 265, 317, 371] |
| EA2 candidates | 0 | 2 [176, 265] |
| EA2 weaker candidates | 0 | 2 [35, 201] |

Absence evidence used as the sole support: C1 [35], C2 [15, 441] (reported apart from EA1 - absence evidence is non-probative rather than temporally inadmissible).

## Per-instance table (rationale reading)

| id | ticker | C1 ans | C1 grounding | C2 ans | C2 grounding |
| --- | --- | --- | --- | --- | --- |
| 15 | NKE | C | GROUNDED | C | INVALID |
| 18 | LULU | D (wrong) | GROUNDED | C | GROUNDED |
| 35 | NVDA | C | INVALID | C | INVALID |
| 37 | F | A | GROUNDED | A | GROUNDED |
| 41 | JWN | B | GROUNDED | B | GROUNDED |
| 47 | DIS | D (wrong) | GROUNDED | D (wrong) | GROUNDED |
| 49 | GM | A | GROUNDED | A | GROUNDED |
| 50 | NUE | C | GROUNDED | C | UNCLEAR |
| 51 | MU | C | GROUNDED | C | MIXED |
| 53 | MDLZ | A | GROUNDED | A | GROUNDED |
| 55 | SPY | C | GROUNDED | C | GROUNDED |
| 61 | TSM | B | GROUNDED | B | GROUNDED |
| 66 | CPB | C | GROUNDED | C | GROUNDED |
| 96 | WMT | C (wrong) | UNCLEAR | D | UNCLEAR |
| 98 | HRB | D | UNCLEAR | D | UNCLEAR |
| 120 | MU | B | GROUNDED | B | GROUNDED |
| 123 | SPY | A | GROUNDED | A | GROUNDED |
| 124 | ARCC | B | GROUNDED | B | GROUNDED |
| 133 | AMD | A | GROUNDED | A | GROUNDED |
| 140 | F | B | GROUNDED | B | UNCLEAR |
| 147 | LULU | D | GROUNDED | D | GROUNDED |
| 148 | DIS | C | GROUNDED | C | GROUNDED |
| 172 | NFLX | A | GROUNDED | A | GROUNDED |
| 176 | PLD | C (wrong) | UNCLEAR | A | INVALID |
| 182 | LECO | A | GROUNDED | A | GROUNDED |
| 191 | WMT | B | GROUNDED | B | GROUNDED |
| 201 | GD | C (wrong) | GROUNDED | D (wrong) | INVALID |
| 215 | ADP | C | GROUNDED | C | GROUNDED |
| 233 | VZ | B | GROUNDED | B | GROUNDED |
| 234 | DIS | B | GROUNDED | B | GROUNDED |
| 252 | GILD | D | GROUNDED | B (wrong) | GROUNDED |
| 256 | KO | C | GROUNDED | C | GROUNDED |
| 265 | BLDR | A (wrong) | GROUNDED | D | MIXED |
| 268 | CMG | C | GROUNDED | C | GROUNDED |
| 274 | PHM | D | GROUNDED | C (wrong) | GROUNDED |
| 275 | AAPL | B | GROUNDED | B | GROUNDED |
| 288 | NFLX | C | GROUNDED | C | GROUNDED |
| 295 | CM | D | GROUNDED | D | UNCLEAR |
| 303 | AMD | D | GROUNDED | D | GROUNDED |
| 313 | T | D | GROUNDED | D | UNCLEAR |
| 317 | WIX | A | GROUNDED | A | UNCLEAR |
| 320 | COST | A | GROUNDED | A | GROUNDED |
| 334 | TOL | C | GROUNDED | C | GROUNDED |
| 353 | RH | B | GROUNDED | B | UNCLEAR |
| 371 | MHK | A | GROUNDED | A | UNCLEAR |
| 405 | MHK | C | GROUNDED | C | GROUNDED |
| 441 | SPY | B | GROUNDED | B | INVALID |
| 453 | NKE | C | GROUNDED | C | GROUNDED |
| 454 | DDD | C | GROUNDED | C | GROUNDED |
| 484 | O | B | GROUNDED | B | GROUNDED |
