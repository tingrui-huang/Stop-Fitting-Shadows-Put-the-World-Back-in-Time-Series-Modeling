# Synthesis - grounding, shortcuts and task semantics

Three phenomena are separated below. They are not exclusive: an instance can carry more than one label, and instances where nothing is observable carry none.

- **TEMPORAL_GROUNDING_FAILURE** - the answer, right or wrong, is explained by evidence that is inadmissible for the anchor
- **SEMANTIC_SHORTCUT** - the MCQA label is recovered without any admissible evidence being used
- **INPUT_WINDOW_TASK_SEMANTICS_MISMATCH** - the inherited option semantics need information after publication that the input-window protocol does not supply

## Headline

- answer accuracy: C1 44/50 = 0.88, C2 46/50 = 0.92
- grounded rate (rationale reading): C1 46/50 = 0.92, C2 34/50 = 0.68
- on INPUT_WINDOW_SUFFICIENT (n=20): C1 20/20 = 1.00, C2 19/20 = 0.95
  - every C1 error falls in a class whose options are not decidable from the supplied window; C2's single error there is instance 274
- on POST_PUBLICATION_EVIDENCE_REQUIRED (n=7): C1 4/7 = 0.57, C2 4/7 = 0.57
- the PARTIALLY_UNDERDETERMINED class alone: C1 20/23, C2 23/23. Accuracy and grounding move in opposite directions across the same 50 items.

## Revisions to the earlier flip-case analysis

- **instance 252**: the flip-case audit labelled this CONSISTENT_WITH_TIMESTAMP_HELP with HIGH confidence. That still describes what the rationales show - C2 states it cannot tie any reaction to a news date - but this audit adds that the item's gold is not decidable from the supplied window at all: options B and D both describe post-announcement price action and publication is 17.0 h after the last window point. The timestamp helped C1 pick the gold without giving it a valid basis, so the case belongs under INPUT_WINDOW_TASK_SEMANTICS_MISMATCH as well.
- **instance 265**: the flip-case audit could only say that C1 'anchored on the pre-publication tail'. The price-level check makes it concrete: the gold's move 67.2 -> 70.94 sits at 28-33% and 40-79% of the window, entirely before publication, so C1's timestamp-aligned reading correctly found no such move at the publication instant and rejected the gold.
- **instance 18**: unchanged, and now supported by the class assignment: the item is PARTIALLY_UNDERDETERMINED because option D's post-publication claim competes with the gold.
- **instance 96**: unchanged, and reinforced: option C names $147.61, a level absent from the supplied window.

## Label counts

| phenomenon | SUPPORTED | PLAUSIBLE |
| --- | --- | --- |
| INPUT_WINDOW_TASK_SEMANTICS_MISMATCH | 7 | 23 |
| SEMANTIC_SHORTCUT | 4 | 9 |
| TEMPORAL_GROUNDING_FAILURE | 5 | 2 |

## Cases

| id | ticker | C1 | C2 | semantics | labels |
| --- | --- | --- | --- | --- | --- |
| 15 | NKE | C/GROUNDED | C/INVALID | INPUT_WINDOW_SUFFICIENT | TEMPORAL=PLAUSIBLE, SEMANTIC=SUPPORTED |
| 18 | LULU | D/GROUNDED | C/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 35 | NVDA | C/INVALID | C/INVALID | INPUT_WINDOW_SUFFICIENT | TEMPORAL=SUPPORTED, SEMANTIC=SUPPORTED |
| 37 | F | A/GROUNDED | A/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 47 | DIS | D/GROUNDED | D/GROUNDED | POST_PUBLICATION_EVIDENCE_REQUIRED | INPUT=SUPPORTED |
| 49 | GM | A/GROUNDED | A/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 50 | NUE | C/GROUNDED | C/UNCLEAR | INPUT_WINDOW_SUFFICIENT | SEMANTIC=PLAUSIBLE |
| 51 | MU | C/GROUNDED | C/MIXED | INPUT_WINDOW_SUFFICIENT | TEMPORAL=SUPPORTED |
| 53 | MDLZ | A/GROUNDED | A/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 55 | SPY | C/GROUNDED | C/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 61 | TSM | B/GROUNDED | B/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 96 | WMT | C/UNCLEAR | D/UNCLEAR | PARTIALLY_UNDERDETERMINED | SEMANTIC=PLAUSIBLE, INPUT=PLAUSIBLE |
| 98 | HRB | D/UNCLEAR | D/UNCLEAR | PARTIALLY_UNDERDETERMINED | SEMANTIC=PLAUSIBLE, INPUT=PLAUSIBLE |
| 123 | SPY | A/GROUNDED | A/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 124 | ARCC | B/GROUNDED | B/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 140 | F | B/GROUNDED | B/UNCLEAR | PARTIALLY_UNDERDETERMINED | SEMANTIC=PLAUSIBLE, INPUT=PLAUSIBLE |
| 148 | DIS | C/GROUNDED | C/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 176 | PLD | C/UNCLEAR | A/INVALID | POST_PUBLICATION_EVIDENCE_REQUIRED | TEMPORAL=SUPPORTED, SEMANTIC=SUPPORTED, INPUT=SUPPORTED |
| 201 | GD | C/GROUNDED | D/INVALID | POST_PUBLICATION_EVIDENCE_REQUIRED | TEMPORAL=SUPPORTED, INPUT=SUPPORTED |
| 215 | ADP | C/GROUNDED | C/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 233 | VZ | B/GROUNDED | B/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 234 | DIS | B/GROUNDED | B/GROUNDED | POST_PUBLICATION_EVIDENCE_REQUIRED | INPUT=SUPPORTED |
| 252 | GILD | D/GROUNDED | B/GROUNDED | POST_PUBLICATION_EVIDENCE_REQUIRED | INPUT=SUPPORTED |
| 265 | BLDR | A/GROUNDED | D/MIXED | PARTIALLY_UNDERDETERMINED | TEMPORAL=SUPPORTED, INPUT=PLAUSIBLE |
| 275 | AAPL | B/GROUNDED | B/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 288 | NFLX | C/GROUNDED | C/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 295 | CM | D/GROUNDED | D/UNCLEAR | INPUT_WINDOW_SUFFICIENT | SEMANTIC=PLAUSIBLE |
| 303 | AMD | D/GROUNDED | D/GROUNDED | POST_PUBLICATION_EVIDENCE_REQUIRED | INPUT=SUPPORTED |
| 313 | T | D/GROUNDED | D/UNCLEAR | POST_PUBLICATION_EVIDENCE_REQUIRED | SEMANTIC=PLAUSIBLE, INPUT=SUPPORTED |
| 317 | WIX | A/GROUNDED | A/UNCLEAR | PARTIALLY_UNDERDETERMINED | SEMANTIC=PLAUSIBLE, INPUT=PLAUSIBLE |
| 353 | RH | B/GROUNDED | B/UNCLEAR | PARTIALLY_UNDERDETERMINED | SEMANTIC=PLAUSIBLE, INPUT=PLAUSIBLE |
| 371 | MHK | A/GROUNDED | A/UNCLEAR | PARTIALLY_UNDERDETERMINED | SEMANTIC=PLAUSIBLE, INPUT=PLAUSIBLE |
| 405 | MHK | C/GROUNDED | C/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
| 441 | SPY | B/GROUNDED | B/INVALID | PARTIALLY_UNDERDETERMINED | TEMPORAL=PLAUSIBLE, SEMANTIC=SUPPORTED, INPUT=PLAUSIBLE |
| 454 | DDD | C/GROUNDED | C/GROUNDED | PARTIALLY_UNDERDETERMINED | INPUT=PLAUSIBLE |
