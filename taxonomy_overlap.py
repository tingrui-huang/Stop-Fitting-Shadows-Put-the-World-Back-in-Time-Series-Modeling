"""Audit the Type-A / Type-B boundary: the two modes must be mutually exclusive.

Type A is a same-ticker article of the same or clearly analogous target event
type at least 90 days away.  Such an article documents ANOTHER EPISODE OF THE
SAME MECHANISM, so it can never also count as absence evidence.

Two overlap classes are checked for every anchor:

  hard_overlap   the candidate satisfies the full Type-A test (same ticker,
                 analogous event type, abs(offset) >= 90) and still appears in
                 the Type-B pool
  mechanism_overlap
                 the candidate is a same-ticker article of the same or
                 analogous event type but closer than 90 days, so it is not a
                 valid alias either - it still documents the target mechanism
                 and must not be absence evidence

Writes distractor_taxonomy_overlap_audit.json.

Usage:  python taxonomy_overlap.py
"""

import collections
import json

from build_final_hard50 import load_json
from distractor_policy import (ALIAS_MIN_DAYS, alias_map_from, index_by_ticker,
                               load_corpus_frame, match_tier, offset_days,
                               type_a_candidates)
from news_corpus import event_type, parse_article, parse_utc
from paper_minimal_coverage import anchor_company_name, type_b_paper_minimal

DATA = "final50_locked_data.json"


def main():
    df = load_corpus_frame()
    by_ticker = index_by_ticker(df)
    corpus_rows = [a for rows in by_ticker.values() for a in rows]
    alias = alias_map_from(df)

    per_anchor, examples = [], []
    for rec in load_json(DATA):
        iid, ticker = rec["instance_id"], rec["ticker"]
        title, text = parse_article(rec["gt_article_text"])
        gt_event = event_type(title, text)
        gt_dt = parse_utc(rec["gt_published_utc"])
        anchor = {"ticker": ticker, "gt_title": title, "gt_event": gt_event,
                  "gt_dt": gt_dt}
        same = [a for a in by_ticker.get(ticker, [])
                if a["title"].strip() != title.strip()]

        a_pool = type_a_candidates(same, gt_event, gt_dt)
        a_ids = {c["article"]["article_id"] for c in a_pool}
        company = anchor_company_name(title, ticker, alias)
        b_raw = type_b_paper_minimal(anchor, corpus_rows, alias, company)

        hard, mechanism = [], []
        for c in b_raw:
            art = c["article"]
            if art["article_id"] in a_ids:
                hard.append(c)
                continue
            if ticker in art["tickers"]:
                tier = match_tier(gt_event, art["event_type"])
                if tier is not None:
                    mechanism.append((c, tier))

        per_anchor.append({
            "instance_id": iid, "ticker": ticker, "gt_event_type": gt_event,
            "n_type_a": len(a_pool),
            "n_type_b_before_exclusion": len(b_raw),
            "n_hard_overlap": len(hard),
            "n_mechanism_overlap": len(mechanism),
            "n_type_b_after_exclusion": len(b_raw) - len(hard) - len(mechanism),
            "hard_overlap_ids": [c["article"]["article_id"] for c in hard],
            "mechanism_overlap": [
                {"article_id": c["article"]["article_id"],
                 "title": c["article"]["title"],
                 "inferred_event_type": c["article"]["event_type"],
                 "match_tier": tier,
                 "offset_days": round(c["offset_days"], 2),
                 "why_excluded": "same ticker and %s match to the %s target "
                                 "mechanism at %+.0f days - closer than the %d-day "
                                 "alias threshold, so it is neither a valid temporal "
                                 "alias nor absence evidence"
                                 % (tier, gt_event, c["offset_days"], ALIAS_MIN_DAYS)}
                for c, tier in mechanism],
        })
        for c, tier in mechanism[:2]:
            examples.append({"instance_id": iid, "ticker": ticker,
                             "gt_event_type": gt_event,
                             "article_id": c["article"]["article_id"],
                             "title": c["article"]["title"],
                             "match_tier": tier,
                             "offset_days": round(c["offset_days"], 2)})

    summary = {
        "rule": "candidate_is_type_a => candidate cannot be Type B; and a "
                "same-ticker article of the same or analogous event type is never "
                "absence evidence at any offset, because it documents the target "
                "mechanism",
        "hard_overlap_definition": "in the Type-A pool (same ticker, analogous event "
                                   "type, abs(offset) >= %d) and still present in the "
                                   "Type-B pool" % ALIAS_MIN_DAYS,
        "mechanism_overlap_definition": "same ticker and analogous event type but "
                                        "closer than %d days: not a valid alias, and "
                                        "not valid absence evidence either"
                                        % ALIAS_MIN_DAYS,
        "totals": {
            "n_anchors": len(per_anchor),
            "n_hard_overlap": sum(a["n_hard_overlap"] for a in per_anchor),
            "n_mechanism_overlap": sum(a["n_mechanism_overlap"] for a in per_anchor),
            "anchors_with_hard_overlap": [a["instance_id"] for a in per_anchor
                                          if a["n_hard_overlap"]],
            "anchors_with_mechanism_overlap": [a["instance_id"] for a in per_anchor
                                               if a["n_mechanism_overlap"]],
        },
        "examples": examples[:25],
        "anchors": per_anchor,
    }
    with open("distractor_taxonomy_overlap_audit.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    t = summary["totals"]
    print("hard overlaps (type A leaking into B): %d across %d anchors"
          % (t["n_hard_overlap"], len(t["anchors_with_hard_overlap"])))
    print("mechanism overlaps (same mechanism, < 90 days): %d across %d anchors"
          % (t["n_mechanism_overlap"], len(t["anchors_with_mechanism_overlap"])))
    print("anchors affected by mechanism overlap: %s"
          % t["anchors_with_mechanism_overlap"][:20])
    for e in examples[:8]:
        print("   %-4d %-5s %s-match %+.0fd  %s"
              % (e["instance_id"], e["ticker"], e["match_tier"], e["offset_days"],
                 e["title"][:60]))
    print("wrote distractor_taxonomy_overlap_audit.json")


if __name__ == "__main__":
    main()
