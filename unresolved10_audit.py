"""Rejection audit for the 10 anchors the adaptive policy could not resolve.

Every plausible corpus candidate (same ticker, or explicitly naming the anchor
company / ticker) is evaluated and its rejection rules are attributed to the
paper or to our own implementation.

Writes unresolved10_rejection_audit.json and a borderline shortlist
(unresolved10_typeB_manual_review.jsonl) holding the candidates that fail ONLY
implementation heuristics - the ones worth a human read.

Usage:  python unresolved10_audit.py
"""

import collections
import json

from build_final_hard50 import load_json
from distractor_policy import (alias_map_from, index_by_ticker, load_corpus_frame,
                               specific_aliases)
from news_corpus import event_type, parse_article, parse_utc
from typeb_paper_minimal import (IMPLEMENTATION_HEURISTIC, PAPER_REQUIRED, evaluate,
                                 paper_minimal_pool)

DATA = "final50_locked_data.json"
UNRESOLVED = [36, 50, 53, 78, 99, 136, 252, 357, 394, 481]
SHORTLIST_PER_ANCHOR = 12


def main():
    df = load_corpus_frame()
    by_ticker = index_by_ticker(df)
    corpus_rows = [a for rows in by_ticker.values() for a in rows]
    alias = alias_map_from(df)
    data = {r["instance_id"]: r for r in load_json(DATA)}

    audit, shortlist = [], []
    for iid in UNRESOLVED:
        rec = data[iid]
        ticker = rec["ticker"]
        gt_title, gt_text = parse_article(rec["gt_article_text"])
        gt_event = event_type(gt_title, gt_text)
        gt_dt = parse_utc(rec["gt_published_utc"])
        gt_row = next((a for a in by_ticker.get(ticker, [])
                       if a["title"].strip() == gt_title.strip()), None)

        # plausible universe: same-ticker rows + rows naming the company or ticker
        names = specific_aliases(ticker, alias)
        plausible = list(by_ticker.get(ticker, []))
        seen = {a["article_id"] for a in plausible}
        needle_company = [n.lower() for n in names]
        for a in corpus_rows:
            if a["article_id"] in seen:
                continue
            blob = (a["title"] + " " + a["content"][:4000]).lower()
            if any(n in blob for n in needle_company) or \
                    (" %s " % ticker.lower()) in blob or \
                    ("(%s)" % ticker.lower()) in blob:
                plausible.append(a)
                seen.add(a["article_id"])

        records = [evaluate(a, gt_row, gt_event, gt_dt, gt_title, ticker, alias)
                   for a in plausible]
        minimal = paper_minimal_pool(records)
        current_pass = [r for r in records if r["passes_current_policy"]]
        borderline = [r for r in records if r["blocked_only_by_heuristics"]]

        rule_counts = collections.Counter(rule for r in records
                                          for rule in r["rejection_rules"])
        audit.append({
            "instance_id": iid, "ticker": ticker,
            "gt_title": gt_title, "gt_event_type": gt_event,
            "gt_published_utc": rec["gt_published_utc"],
            "gt_in_corpus": gt_row is not None,
            "n_plausible_candidates": len(records),
            "n_pass_current_policy": len(current_pass),
            "n_pass_paper_minimal": len(minimal),
            "n_blocked_only_by_heuristics": len(borderline),
            "paper_minimal_tier_counts": dict(collections.Counter(
                r["tier"] for r in minimal)),
            "rejection_rule_counts": dict(rule_counts),
            "rejection_rule_provenance": {
                r: ("PAPER_REQUIRED" if r in PAPER_REQUIRED else
                    "IMPLEMENTATION_HEURISTIC" if r in IMPLEMENTATION_HEURISTIC
                    else "OTHER") for r in rule_counts},
            "candidates": records,
        })

        for r in sorted(borderline,
                        key=lambda r: ({"B1": 0, "B2": 1, "B3": 2}.get(r["tier"], 3),
                                       abs(r["offset_days"])))[:SHORTLIST_PER_ANCHOR]:
            shortlist.append({
                "anchor_instance_id": iid, "anchor_ticker": ticker,
                "gt_title": gt_title, "gt_event_type": gt_event,
                "gt_published_utc": rec["gt_published_utc"],
                "article_id": r["article_id"], "title": r["title"],
                "tickers": r["tickers"], "published_utc": r["published_utc"],
                "offset_days": r["offset_days"],
                "tier": r["tier"], "entity_relation": r["entity_relation"],
                "entity_relation_evidence": r["entity_relation_evidence"],
                "inferred_event_type": r["inferred_event_type"],
                "label_type_explicit": r["label_type_explicit"],
                "keywords_explicit": r["keywords_explicit"],
                "implementation_only_blockers": r["implementation_only_blockers"],
                "content_preview": r["content_preview"],
                "manual_class": "PENDING",
                "why_semantically_plausible": "",
                "absent_target_event": "",
                "why_not_valid_gt": "",
            })

    summary = {
        "unresolved_anchors": UNRESOLVED,
        "rule_provenance": {
            "PAPER_REQUIRED": sorted(PAPER_REQUIRED),
            "IMPLEMENTATION_HEURISTIC": sorted(IMPLEMENTATION_HEURISTIC),
        },
        "paper_minimal_test": [
            "topically adjacent (defensible entity relation with textual evidence)",
            "does not document the corresponding target event",
            "is not the ground-truth article or a duplicate of it",
            "is not equally valid evidence for the specific MCQA target "
            "(human judgement, recorded in the manual review file)",
        ],
        "totals": {
            "n_plausible": sum(a["n_plausible_candidates"] for a in audit),
            "n_pass_current": sum(a["n_pass_current_policy"] for a in audit),
            "n_pass_paper_minimal": sum(a["n_pass_paper_minimal"] for a in audit),
            "n_blocked_only_by_heuristics": sum(a["n_blocked_only_by_heuristics"]
                                                for a in audit),
        },
        "anchors": audit,
    }
    with open("unresolved10_rejection_audit.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with open("unresolved10_typeB_manual_review.jsonl", "w", encoding="utf-8",
              newline="\n") as f:
        for r in shortlist:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("%-5s %-6s %6s %8s %9s %10s  %s"
          % ("id", "ticker", "plaus", "current", "minimal", "heur-only", "tiers"))
    for a in audit:
        print("%-5d %-6s %6d %8d %9d %10d  %s"
              % (a["instance_id"], a["ticker"], a["n_plausible_candidates"],
                 a["n_pass_current_policy"], a["n_pass_paper_minimal"],
                 a["n_blocked_only_by_heuristics"], a["paper_minimal_tier_counts"]))
    print("\nrejection rules across all 10 anchors:")
    total = collections.Counter()
    for a in audit:
        total.update(a["rejection_rule_counts"])
    for rule, n in total.most_common():
        kind = ("PAPER_REQUIRED" if rule in PAPER_REQUIRED else
                "IMPLEMENTATION_HEURISTIC")
        print("   %-32s %5d  %s" % (rule, n, kind))
    print("\nshortlisted for manual review: %d" % len(shortlist))


if __name__ == "__main__":
    main()
