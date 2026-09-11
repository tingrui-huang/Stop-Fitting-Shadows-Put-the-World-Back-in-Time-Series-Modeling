# NBA150 discussion-v3 conditions

All conditions ask the same abductive multiple-choice question: reconstruct the event at a missing position using whatever evidence is visible before and after it. They preserve the four original answer choices and their order. Gold answers are stored only in the separate indexes.

- `FULL`: complete past and future event records with game clocks, plus the complete four-channel numerical table with game clocks and a target marker.
- `TEXT_ONLY`: the same event records, clocks and target moment as FULL, without a numerical table or a score/win-probability summary.
- `SERIES_ONLY`: the complete four-channel numerical table, clocks and target marker, without event context.
- `QA_ONLY`: the generic missing-event question, choices and response format only.
- `REMOVE`: FULL evidence with explicit game-clock fields removed from event records, the target moment and the numerical table. Source order, past/future sections and the target marker remain.
- `SHUFFLE`: FULL evidence with only the numerical table's game-time labels reassigned across all rows. Event records and their clocks, numerical rows, the marker and the target moment stay in place.
- `RELATIVE`: FULL evidence with event and numerical times converted to exact seconds relative to the target. Negative values precede the target, positive values follow it and the target is zero.

REMOVE deletes explicit clock anchors, but event order, past/future partitions and natural-language phase cues such as `End of the 4th Quarter` remain. SHUFFLE deliberately creates a conflict between time labels and numerical values and can break monotonicity. RELATIVE preserves intervals and alignment, so its span can still reveal game progress. These interventions should therefore be interpreted as practical input comparisons rather than strict isolation of three independent theoretical concepts.

No retrieval, event pool, model call or evaluation is part of this bundle.
