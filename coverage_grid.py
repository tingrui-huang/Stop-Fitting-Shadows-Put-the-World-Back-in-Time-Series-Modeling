"""Coverage grid over the 50 locked anchors: how many support each A/B ratio.

Type A follows the paper (same ticker, analogous event type, abs(offset) >= 90,
both directions).  Type B is evaluated under four time-window policies.  The
goal is the LEAST RELAXED fixed policy with the best coverage; cross-ticker
distractors are never considered.

Writes distractor_coverage_grid.json.

Usage:  python coverage_grid.py
"""

import json
import statistics

from build_final_hard50 import load_json
from distractor_policy import (alias_map_from, index_by_ticker, load_corpus_frame,
                               type_a_candidates, type_b_candidates)
from news_corpus import event_type, parse_article, parse_utc

DATA = "final50_locked_data.json"
B_WINDOWS = [("+/-45d", 45), ("+/-90d", 90), ("+/-180d", 180), ("unrestricted", None)]
RATIOS = [(8, 2), (7, 3), (6, 4), (5, 5)]


def main():
    df = load_corpus_frame()
    by_ticker = index_by_ticker(df)
    alias = alias_map_from(df)
    anchors = load_json(DATA)

    per_anchor = []
    for rec in anchors:
        title, text = parse_article(rec["gt_article_text"])
        gt_event = event_type(title, text)
        gt_dt = parse_utc(rec["gt_published_utc"])
        pool = [a for a in by_ticker.get(rec["ticker"], [])
                if a["title"].strip() != title.strip()]

        a_cands = type_a_candidates(pool, gt_event, gt_dt)
        exact = [c for c in a_cands if c["tier"] == "exact"]
        family = [c for c in a_cands if c["tier"] == "family"]
        hist = [c for c in a_cands if c["alias_direction"] == "historical"]
        fut = [c for c in a_cands if c["alias_direction"] == "future"]

        row = {
            "instance_id": rec["instance_id"], "ticker": rec["ticker"],
            "gt_event_type": gt_event,
            "same_ticker_articles": len(pool),
            "type_a_total": len(a_cands),
            "type_a_exact": len(exact), "type_a_family": len(family),
            "type_a_historical": len(hist), "type_a_future": len(fut),
            "type_b": {},
        }
        for name, window in B_WINDOWS:
            b = type_b_candidates(pool, gt_event, gt_dt, alias, rec["ticker"], window)
            row["type_b"][name] = len(b)
        per_anchor.append(row)

    def stats(values):
        return {"min": min(values), "median": int(statistics.median(values)),
                "max": max(values)}

    grid = []
    for name, _ in B_WINDOWS:
        for n_a, n_b in RATIOS:
            ok, unsat, family_dependent = [], [], []
            for r in per_anchor:
                has_a = r["type_a_total"] >= n_a
                has_b = r["type_b"][name] >= n_b
                if has_a and has_b:
                    ok.append(r["instance_id"])
                    if r["type_a_exact"] < n_a:
                        family_dependent.append(r["instance_id"])
                else:
                    unsat.append({"instance_id": r["instance_id"],
                                  "ticker": r["ticker"],
                                  "type_a_total": r["type_a_total"],
                                  "type_b_available": r["type_b"][name],
                                  "short_of": ("A" if not has_a else "") +
                                              ("B" if not has_b else "")})
            grid.append({
                "type_b_window": name,
                "ratio": "%dA+%dB" % (n_a, n_b),
                "n_anchors_satisfying": len(ok),
                "satisfying_ids": ok,
                "n_unsatisfied": len(unsat),
                "unsatisfied": unsat,
                "n_relying_on_family_a_matches": len(family_dependent),
                "family_dependent_ids": family_dependent,
            })

    summary = {
        "policy": {
            "type_a": "same ticker, exact-or-family event type, abs(offset_days) "
                      ">= 90, both directions (historical and future) allowed",
            "type_b": "same ticker, company-topical, target event class absent, "
                      "not a strong event that could explain the episode, not "
                      "boilerplate, focused article (<= 4 tickers, >= 800 chars)",
            "cross_ticker": "never used",
        },
        "type_a_counts": stats([r["type_a_total"] for r in per_anchor]),
        "type_a_exact_counts": stats([r["type_a_exact"] for r in per_anchor]),
        "type_a_family_counts": stats([r["type_a_family"] for r in per_anchor]),
        "type_a_historical_total": sum(r["type_a_historical"] for r in per_anchor),
        "type_a_future_total": sum(r["type_a_future"] for r in per_anchor),
        "type_b_counts_by_window": {name: stats([r["type_b"][name] for r in per_anchor])
                                    for name, _ in B_WINDOWS},
        "grid": grid,
        "anchors": per_anchor,
    }
    with open("distractor_coverage_grid.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("Type A per anchor: %s | exact %s | family %s"
          % (summary["type_a_counts"], summary["type_a_exact_counts"],
             summary["type_a_family_counts"]))
    print("Type A totals: %d historical, %d future"
          % (summary["type_a_historical_total"], summary["type_a_future_total"]))
    print("Type B per anchor by window: %s\n" % summary["type_b_counts_by_window"])
    print("%-14s %-8s %-10s %-8s %s" % ("B window", "ratio", "satisfied", "family",
                                        "unsatisfied ids"))
    for g in grid:
        ids = [u["instance_id"] for u in g["unsatisfied"]]
        print("%-14s %-8s %2d/50      %2d       %s"
              % (g["type_b_window"], g["ratio"], g["n_anchors_satisfying"],
                 g["n_relying_on_family_a_matches"],
                 (str(ids[:12]) + (" ..." if len(ids) > 12 else "")) if ids else "-"))
    print("\nwrote distractor_coverage_grid.json")


if __name__ == "__main__":
    main()
