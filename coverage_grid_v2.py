"""Coverage grid v2: corrected Type-B policy (same ticker preferred, not required).

Type A (unchanged): same ticker REQUIRED, exact-or-family event type,
abs(offset_days) >= 90, both directions.

Type B (corrected): topically adjacent article documenting no corresponding
target event.  Tier B1 = same ticker; tier B2 = a different company whose
article explicitly discusses the anchor company.  No time window is imposed;
temporal proximity is only a late ranking preference.

Writes distractor_coverage_grid_v2.json.

Usage:  python coverage_grid_v2.py
"""

import collections
import json
import statistics

from build_final_hard50 import load_json
from distractor_policy import (alias_map_from, index_by_ticker, load_corpus_frame,
                               type_a_candidates, type_b_candidates_v2)
from news_corpus import event_type, parse_article, parse_utc

DATA = "final50_locked_data.json"
RATIOS = [(8, 2), (7, 3), (6, 4), (5, 5)]


def stats(values):
    return {"min": min(values), "median": float(statistics.median(values)),
            "max": max(values)}


def main():
    df = load_corpus_frame()
    by_ticker = index_by_ticker(df)
    corpus_rows = [a for rows in by_ticker.values() for a in rows]
    alias = alias_map_from(df)
    anchors = load_json(DATA)

    per_anchor = []
    for rec in anchors:
        title, text = parse_article(rec["gt_article_text"])
        gt_event = event_type(title, text)
        gt_dt = parse_utc(rec["gt_published_utc"])
        same_ticker_pool = [a for a in by_ticker.get(rec["ticker"], [])
                            if a["title"].strip() != title.strip()]
        gt_row = next((a for a in by_ticker.get(rec["ticker"], [])
                       if a["title"].strip() == title.strip()), None)

        a_c = type_a_candidates(same_ticker_pool, gt_event, gt_dt)
        b_c = [c for c in type_b_candidates_v2(gt_row, gt_event, gt_dt, rec["ticker"],
                                               alias, by_ticker, corpus_rows)
               if c["article"]["title"].strip() != title.strip()]

        rel = collections.Counter(c["entity_relation"] for c in b_c)
        per_anchor.append({
            "instance_id": rec["instance_id"], "ticker": rec["ticker"],
            "gt_event_type": gt_event,
            "same_ticker_articles": len(same_ticker_pool),
            "type_a_total": len(a_c),
            "type_a_exact": sum(1 for c in a_c if c["tier"] == "exact"),
            "type_a_family": sum(1 for c in a_c if c["tier"] == "family"),
            "type_a_historical": sum(1 for c in a_c
                                     if c["alias_direction"] == "historical"),
            "type_a_future": sum(1 for c in a_c if c["alias_direction"] == "future"),
            "type_b_total": len(b_c),
            "type_b_same_ticker": rel.get("same_ticker", 0),
            "type_b_related_entity": rel.get("closely_related_entity", 0),
        })

    grid = []
    for n_a, n_b in RATIOS:
        covered, uncovered = [], []
        for r in per_anchor:
            ok_a, ok_b = r["type_a_total"] >= n_a, r["type_b_total"] >= n_b
            if ok_a and ok_b:
                covered.append(r["instance_id"])
            else:
                uncovered.append({
                    "instance_id": r["instance_id"], "ticker": r["ticker"],
                    "type_a_total": r["type_a_total"],
                    "type_b_total": r["type_b_total"],
                    "failure_due_to": ("A and B" if not ok_a and not ok_b
                                       else "A" if not ok_a else "B"),
                })
        grid.append({
            "ratio": "%dA+%dB" % (n_a, n_b),
            "n_covered": len(covered), "covered_ids": covered,
            "n_uncovered": len(uncovered), "uncovered": uncovered,
            "failure_reason_counts": dict(collections.Counter(
                u["failure_due_to"] for u in uncovered)),
            "n_relying_on_family_a": sum(
                1 for r in per_anchor
                if r["instance_id"] in covered and r["type_a_exact"] < n_a),
            "n_relying_on_related_entity_b": sum(
                1 for r in per_anchor
                if r["instance_id"] in covered and r["type_b_same_ticker"] < n_b),
        })

    summary = {
        "version": 2,
        "correction": "same ticker is required for Type A only. Type B prefers the "
                      "same ticker but accepts a closely related entity, and no time "
                      "window is imposed on Type B.",
        "type_b_tiers": {
            "B1": "same ticker + topically adjacent + target event absent",
            "B2": "a different company whose article explicitly discusses the anchor "
                  "company + topically adjacent + target event absent",
        },
        "sector_note": "the corpus has no sector/industry field and every row is "
                       "tagged with exactly one ticker (0/20000 multi-ticker rows), "
                       "so 'same_sector' cannot be evidenced from the data; tier B2 "
                       "uses explicit cross-company mention instead and is always "
                       "labelled entity_relation_source = inferred",
        "type_a_counts": stats([r["type_a_total"] for r in per_anchor]),
        "type_a_exact_counts": stats([r["type_a_exact"] for r in per_anchor]),
        "type_a_family_counts": stats([r["type_a_family"] for r in per_anchor]),
        "type_a_historical_total": sum(r["type_a_historical"] for r in per_anchor),
        "type_a_future_total": sum(r["type_a_future"] for r in per_anchor),
        "type_b_counts": stats([r["type_b_total"] for r in per_anchor]),
        "type_b_entity_relation_totals": {
            "same_ticker": sum(r["type_b_same_ticker"] for r in per_anchor),
            "closely_related_entity": sum(r["type_b_related_entity"] for r in per_anchor),
        },
        "grid": grid,
        "anchors": per_anchor,
    }
    with open("distractor_coverage_grid_v2.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("Type A: %s | exact %s | family %s"
          % (summary["type_a_counts"], summary["type_a_exact_counts"],
             summary["type_a_family_counts"]))
    print("Type A totals: %d historical / %d future"
          % (summary["type_a_historical_total"], summary["type_a_future_total"]))
    print("Type B: %s | same_ticker %d, related_entity %d"
          % (summary["type_b_counts"],
             summary["type_b_entity_relation_totals"]["same_ticker"],
             summary["type_b_entity_relation_totals"]["closely_related_entity"]))
    print("\n%-8s %-10s %-22s %-10s %s" % ("ratio", "covered", "failure reason",
                                           "family A", "related-entity B"))
    for g in grid:
        print("%-8s %2d/50      %-22s %-10d %d"
              % (g["ratio"], g["n_covered"], g["failure_reason_counts"] or "-",
                 g["n_relying_on_family_a"], g["n_relying_on_related_entity_b"]))
    print("\nwrote distractor_coverage_grid_v2.json")


if __name__ == "__main__":
    main()
