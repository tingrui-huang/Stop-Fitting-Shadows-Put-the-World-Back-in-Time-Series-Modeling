"""Filter-stage diagnostic for Type-A temporal aliases, per locked anchor.

A0  same-ticker rows in the corpus
A1  A0 rows with abs(offset_days) >= 90
A2  A1 rows the heuristic calls an EXACT event match
A3  A1 rows the heuristic calls a FAMILY (analogous) match

Neither the same-ticker requirement nor the >= 90-day rule is relaxed anywhere
here.  For anchors where A2+A3 < 7 the complete A1 listing is dumped so the
heuristic's rejections can be inspected by hand.

Writes typeA_filter_diagnostic.json and typeA_manual_review_candidates.jsonl.

Usage:  python typea_diagnostic.py [--threshold 7]
"""

import argparse
import json

from build_final_hard50 import load_json
from distractor_policy import (ALIAS_MIN_DAYS, FAMILY, index_by_ticker,
                               load_corpus_frame, match_tier, offset_days)
from news_corpus import event_type, parse_article, parse_utc

DATA = "final50_locked_data.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=int, default=7)
    args = ap.parse_args()

    df = load_corpus_frame()
    by_ticker = index_by_ticker(df)
    anchors = load_json(DATA)

    rows, dump = [], []
    for rec in anchors:
        title, text = parse_article(rec["gt_article_text"])
        gt_event = event_type(title, text)
        gt_dt = parse_utc(rec["gt_published_utc"])
        same = [a for a in by_ticker.get(rec["ticker"], [])
                if a["title"].strip() != title.strip()]
        a1 = [(a, offset_days(a, gt_dt)) for a in same
              if abs(offset_days(a, gt_dt)) >= ALIAS_MIN_DAYS]
        exact = [(a, o) for a, o in a1 if match_tier(gt_event, a["event_type"]) == "exact"]
        family = [(a, o) for a, o in a1 if match_tier(gt_event, a["event_type"]) == "family"]
        total = len(exact) + len(family)

        row = {
            "instance_id": rec["instance_id"], "ticker": rec["ticker"],
            "gt_event_type": gt_event,
            "gt_event_family": FAMILY.get(gt_event, "other"),
            "gt_published_utc": rec["gt_published_utc"],
            "gt_title": title,
            "A0_same_ticker_rows": len(same),
            "A1_offset_ge_90d": len(a1),
            "A2_exact_match": len(exact),
            "A3_family_match": len(family),
            "A_total": total,
            "below_threshold": total < args.threshold,
        }
        # classify the failure mode
        if len(same) == 0:
            row["failure_mode"] = "NO_SAME_TICKER_COVERAGE"
        elif len(a1) == 0:
            row["failure_mode"] = "NO_90DAY_COVERAGE"
        elif total < args.threshold:
            row["failure_mode"] = "TO_BE_CLASSIFIED"      # needs the manual pass
        else:
            row["failure_mode"] = "COVERED"
        rows.append(row)

        if total < args.threshold:
            for a, off in sorted(a1, key=lambda t: abs(t[1])):
                tier = match_tier(gt_event, a["event_type"])
                dump.append({
                    "anchor_instance_id": rec["instance_id"],
                    "anchor_ticker": rec["ticker"],
                    "gt_event_type": gt_event,
                    "gt_title": title,
                    "gt_published_utc": rec["gt_published_utc"],
                    "article_id": a["article_id"],
                    "title": a["title"],
                    "published_utc": a["published_utc"],
                    "offset_days": round(off, 2),
                    "alias_direction": "historical" if off < 0 else "future",
                    "inferred_event_type": a["event_type"],
                    "label_type_explicit": a["label_type"],
                    "keywords_explicit": a["keywords"],
                    "heuristic_status": tier or "no_match",
                    "rejection_reason": (
                        "" if tier else
                        "inferred event type %s is neither the GT type (%s) nor in "
                        "its family (%s)" % (a["event_type"], gt_event,
                                             FAMILY.get(gt_event, "other"))),
                    "content_preview": a["content"][:300],
                    "manual_semantic_status": "PENDING",
                    "rescue_reason": "",
                })

    summary = {
        "threshold": args.threshold,
        "rule": "same ticker REQUIRED and abs(offset_days) >= %d - neither relaxed"
                % ALIAS_MIN_DAYS,
        "n_anchors": len(rows),
        "n_below_threshold": sum(1 for r in rows if r["below_threshold"]),
        "below_threshold_ids": [r["instance_id"] for r in rows if r["below_threshold"]],
        "zero_alias_ids": [r["instance_id"] for r in rows if r["A_total"] == 0],
        "anchors": rows,
    }
    with open("typeA_filter_diagnostic.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with open("typeA_manual_review_candidates.jsonl", "w", encoding="utf-8",
              newline="\n") as f:
        for d in dump:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    print("%-5s %-6s %-16s %4s %4s %4s %4s %5s  %s"
          % ("id", "ticker", "gt_event", "A0", "A1", "A2", "A3", "tot", "mode"))
    for r in sorted(rows, key=lambda r: (r["A_total"], r["instance_id"])):
        if r["below_threshold"]:
            print("%-5d %-6s %-16s %4d %4d %4d %4d %5d  %s"
                  % (r["instance_id"], r["ticker"], r["gt_event_type"],
                     r["A0_same_ticker_rows"], r["A1_offset_ge_90d"],
                     r["A2_exact_match"], r["A3_family_match"], r["A_total"],
                     r["failure_mode"]))
    print("\nbelow threshold: %d/50 | zero-alias: %s"
          % (summary["n_below_threshold"], summary["zero_alias_ids"]))
    print("dumped %d A1 candidates for manual inspection" % len(dump))


if __name__ == "__main__":
    main()
