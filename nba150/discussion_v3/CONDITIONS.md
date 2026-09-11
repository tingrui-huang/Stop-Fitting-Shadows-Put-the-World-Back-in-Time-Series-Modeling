# NBA150 discussion-v3 conditions

All conditions ask the same abductive multiple-choice question: reconstruct the event at a missing position using whatever evidence is visible before and after it. They preserve the four original answer choices and their order. Gold answers are stored only in the separate indexes.

- `FULL`: complete past and future event records with game clocks, plus the complete four-channel numerical table with game clocks and a target marker.
- `TEXT_ONLY`: the same event records, clocks and target moment as FULL, without a numerical table or a score/win-probability summary.
- `SERIES_ONLY`: the complete four-channel numerical table, clocks and target marker, without event context.
- `QA_ONLY`: the generic missing-event question, choices and response format only.
- `REMOVE`: FULL evidence with explicit game-clock fields removed from event records, the target moment and the numerical table. Source order, past/future sections and the target marker remain.
- `SHUFFLE`: the observed events (excluding the missing target) receive a seeded derangement of the observed event-time labels, then each event/ID/time triple is sorted by cumulative elapsed game time. The complete numerical table, its real clocks and target marker, and the real target moment remain identical to FULL.
- `RELATIVE`: FULL evidence with event and numerical times converted to exact seconds relative to the target. Negative values precede the target, positive values follow it and the target is zero.

REMOVE deletes explicit clock anchors, but event order, past/future partitions and natural-language phase cues such as `End of the 4th Quarter` remain. SHUFFLE keeps displayed event times chronological while deliberately breaking the event-to-time-series correspondence; reassigned events can also cross the Past/Future boundary around the fixed target. RELATIVE preserves intervals and alignment, so its span can still reveal game progress. These interventions should therefore be interpreted as practical input comparisons rather than strict isolation of three independent theoretical concepts.

No retrieval, event pool, model call or evaluation is part of this bundle.
