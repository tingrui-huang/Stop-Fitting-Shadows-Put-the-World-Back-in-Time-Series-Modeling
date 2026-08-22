"""Adaptive target-and-fill distractor coverage over all 50 locked anchors.

No globally fixed A/B ratio.  Target 7 Type A + 3 Type B; whichever type falls
short is topped up from the other until exactly 10 distractors are selected.
An anchor with fewer than 10 valid candidates in total stays UNRESOLVED - no
requirement is relaxed to reach 10.

Type A: same ticker REQUIRED, abs(offset_days) >= 90 REQUIRED, exact match
        preferred, then family, then a manually rescued same-genre episode;
        historical and future aliases both allowed.
Type B: same ticker preferred, otherwise an explicit related-entity mention;
        topically adjacent, target event absent, cannot itself explain the MCQA.

Writes adaptive_distractor_coverage.json.

Usage:  python adaptive_coverage.py [--target-a 7] [--target-b 3]
"""

import argparse
import collections
import json
import statistics

from build_final_hard50 import load_json
from distractor_policy import (alias_map_from, index_by_ticker, load_corpus_frame,
                               type_a_candidates, type_b_candidates_v2)
from news_corpus import event_type, parse_article, parse_utc

DATA = "final50_locked_data.json"
RESCUES = "typeA_manual_review_candidates.jsonl"
N_TOTAL = 10


def load_rescues():
    """-> {anchor_id: {article_id: reason}} for defensible manual matches."""
    out = collections.defaultdict(dict)
    try:
        with open(RESCUES, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("manual_semantic_status") == "RESCUED":
                    out[r["anchor_instance_id"]][r["article_id"]] = r["rescue_reason"]
    except FileNotFoundError:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-a", type=int, default=7)
    ap.add_argument("--target-b", type=int, default=3)
    args = ap.parse_args()

    df = load_corpus_frame()
    by_ticker = index_by_ticker(df)
    corpus_rows = [a for rows in by_ticker.values() for a in rows]
    alias = alias_map_from(df)
    rescues = load_rescues()
    anchors = load_json(DATA)

    per_anchor = []
    for rec in anchors:
        iid, ticker = rec["instance_id"], rec["ticker"]
        title, text = parse_article(rec["gt_article_text"])
        gt_event = event_type(title, text)
        gt_dt = parse_utc(rec["gt_published_utc"])
        same_pool = [a for a in by_ticker.get(ticker, [])
                     if a["title"].strip() != title.strip()]
        gt_row = next((a for a in by_ticker.get(ticker, [])
                       if a["title"].strip() == title.strip()), None)

        a_pool = [dict(c, match_source=c["tier"]) for c in
                  type_a_candidates(same_pool, gt_event, gt_dt)]
        known = {c["article"]["article_id"] for c in a_pool}
        for art in same_pool:                       # manual same-genre rescues
            aid = art["article_id"]
            if aid in rescues.get(iid, {}) and aid not in known:
                off = (art["published_dt"] - gt_dt).total_seconds() / 86400.0
                if abs(off) < 90:
                    continue
                a_pool.append({"article": art, "tier": "manual_rescue",
                               "match_source": "manual_rescue",
                               "offset_days": off,
                               "alias_direction": "historical" if off < 0 else "future",
                               "rescue_reason": rescues[iid][aid]})
        rank = {"exact": 0, "family": 1, "manual_rescue": 2}
        a_pool.sort(key=lambda c: (rank[c["match_source"]], abs(c["offset_days"]),
                                   c["article"]["article_id"]))

        b_pool = [c for c in type_b_candidates_v2(gt_row, gt_event, gt_dt, ticker,
                                                  alias, by_ticker, corpus_rows)
                  if c["article"]["title"].strip() != title.strip()]

        # ---- target and fill ------------------------------------------------
        a_ids = [c["article"]["article_id"] for c in a_pool]
        b_pool = [c for c in b_pool if c["article"]["article_id"] not in set(a_ids)]

        sel_a = a_pool[:args.target_a]
        sel_b = b_pool[:args.target_b]
        fallback = None
        if len(sel_a) + len(sel_b) < N_TOTAL:
            need = N_TOTAL - len(sel_a) - len(sel_b)
            if len(sel_a) < args.target_a:          # A short -> more B
                extra = b_pool[len(sel_b):len(sel_b) + need]
                sel_b += extra
                fallback = "A_short_filled_with_B" if extra else None
                need -= len(extra)
            if need > 0 and len(sel_b) < args.target_b + 1:
                extra = a_pool[len(sel_a):len(sel_a) + need]
                sel_a += extra
                fallback = ("B_short_filled_with_A" if fallback is None
                            else "both_directions")
                need -= len(extra)
            if need > 0:                            # try the other side once more
                extra = a_pool[len(sel_a):len(sel_a) + need]
                sel_a += extra
                if extra:
                    fallback = ("B_short_filled_with_A" if fallback is None
                                else "both_directions")

        total = len(sel_a) + len(sel_b)
        src = collections.Counter(c["match_source"] for c in sel_a)
        direction = collections.Counter(c["alias_direction"] for c in sel_a)
        relation = collections.Counter(c["entity_relation"] for c in sel_b)

        shortage = None
        if total < N_TOTAL:
            if len(same_pool) <= 3:
                shortage = "corpus coverage: the ticker has %d other articles in the " \
                           "corpus" % len(same_pool)
            elif not a_pool and not b_pool:
                shortage = "filtering policy: same-ticker articles exist but none " \
                           "passes either type's semantic criteria"
            elif not a_pool:
                shortage = "event-type scarcity: no same-ticker article of an " \
                           "analogous event type sits >= 90 days away"
            else:
                shortage = "type B scarcity: too few topically adjacent articles " \
                           "without the target event"

        per_anchor.append({
            "instance_id": iid, "ticker": ticker, "gt_event_type": gt_event,
            "n_A_available": len(a_pool), "n_B_available": len(b_pool),
            "n_A_selected": len(sel_a), "n_B_selected": len(sel_b),
            "n_total_selected": total,
            "reaches_10": total == N_TOTAL,
            "fallback_used": fallback,
            "A_exact": src.get("exact", 0), "A_family": src.get("family", 0),
            "A_manual_rescue": src.get("manual_rescue", 0),
            "A_historical": direction.get("historical", 0),
            "A_future": direction.get("future", 0),
            "B_same_ticker": relation.get("same_ticker", 0),
            "B_related_entity": relation.get("closely_related_entity", 0),
            "shortage_reason": shortage,
            "selected_A_ids": [c["article"]["article_id"] for c in sel_a],
            "selected_B_ids": [c["article"]["article_id"] for c in sel_b],
        })

    resolved = [r for r in per_anchor if r["reaches_10"]]
    unresolved = [r for r in per_anchor if not r["reaches_10"]]

    def stats(key, rows):
        vals = [r[key] for r in rows] or [0]
        return {"min": min(vals), "median": float(statistics.median(vals)),
                "max": max(vals)}

    summary = {
        "policy": {
            "target": "%dA + %dB, adaptive fill to exactly %d"
                      % (args.target_a, args.target_b, N_TOTAL),
            "type_a": "same ticker REQUIRED, abs(offset_days) >= 90 REQUIRED, "
                      "exact > family > manual same-genre rescue, both directions",
            "type_b": "same ticker preferred, otherwise explicit related-entity "
                      "mention; topically adjacent, target event absent, cannot "
                      "independently explain the MCQA",
            "nothing_relaxed_to_reach_10": True,
        },
        "n_anchors": len(per_anchor),
        "n_reaching_10": len(resolved),
        "unresolved_ids": [r["instance_id"] for r in unresolved],
        "n_using_fallback": sum(1 for r in resolved if r["fallback_used"]),
        "fallback_counts": dict(collections.Counter(
            r["fallback_used"] for r in resolved if r["fallback_used"])),
        "selected_A_distribution": dict(sorted(collections.Counter(
            r["n_A_selected"] for r in resolved).items())),
        "selected_B_distribution": dict(sorted(collections.Counter(
            r["n_B_selected"] for r in resolved).items())),
        "selected_A_stats": stats("n_A_selected", resolved),
        "selected_B_stats": stats("n_B_selected", resolved),
        "available_A_stats": stats("n_A_available", per_anchor),
        "available_B_stats": stats("n_B_available", per_anchor),
        "A_match_source_totals": {
            "exact": sum(r["A_exact"] for r in resolved),
            "family": sum(r["A_family"] for r in resolved),
            "manual_rescue": sum(r["A_manual_rescue"] for r in resolved)},
        "A_direction_totals": {"historical": sum(r["A_historical"] for r in resolved),
                               "future": sum(r["A_future"] for r in resolved)},
        "B_relation_totals": {"same_ticker": sum(r["B_same_ticker"] for r in resolved),
                              "related_entity": sum(r["B_related_entity"]
                                                    for r in resolved)},
        "anchors": per_anchor,
    }
    with open("adaptive_distractor_coverage.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("anchors reaching exactly 10: %d/50" % len(resolved))
    print("unresolved: %s" % (summary["unresolved_ids"] or "none"))
    print("fallback used by %d resolved anchors %s"
          % (summary["n_using_fallback"], summary["fallback_counts"] or ""))
    print("selected A distribution: %s" % summary["selected_A_distribution"])
    print("selected B distribution: %s" % summary["selected_B_distribution"])
    print("A selected  %s | B selected  %s"
          % (summary["selected_A_stats"], summary["selected_B_stats"]))
    print("A available %s | B available %s"
          % (summary["available_A_stats"], summary["available_B_stats"]))
    print("A sources %s | A direction %s | B relation %s"
          % (summary["A_match_source_totals"], summary["A_direction_totals"],
             summary["B_relation_totals"]))
    for r in unresolved:
        print("  UNRESOLVED %-4d %-5s A=%d B=%d total=%d  %s"
              % (r["instance_id"], r["ticker"], r["n_A_available"],
                 r["n_B_available"], r["n_total_selected"], r["shortage_reason"]))


if __name__ == "__main__":
    main()
