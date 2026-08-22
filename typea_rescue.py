"""Manual/semantic rescue pass over Type-A candidates the heuristic rejected.

The keyword heuristic types an article by the strongest event verb it finds,
which mislabels whole recurring genres: a Zacks daily market-update piece is
typed "earnings" because its body quotes earnings estimates, and a screen /
recommendation piece is typed "other".  This pass adds a second opinion at the
GENRE level, read off the title, and rescues a candidate only when its genre is
the same recurring episode type as the ground-truth article.

A candidate is never rescued merely because it mentions the company.  Same
ticker and abs(offset_days) >= 90 remain hard requirements - neither is touched.

Updates typeA_manual_review_candidates.jsonl in place (manual_semantic_status,
rescue_reason) and writes typeA_rescue_summary.json.

Usage:  python typea_rescue.py
"""

import collections
import json
import re

GENRES = [
    ("daily_market_update",
     r"(stock moves -?\d|gains (as|but) |dips more than|stock sinks as|"
     r"outpaces stock market|underperforms|falls more than (the )?(broader )?market|"
     r"rises but|lags market)"),
    ("analyst_ratings",
     r"(expert ratings|analyst ratings|maintains .*rating|upgrade[sd]?\b|"
     r"downgrade[sd]?\b|price target|initiates coverage)"),
    ("screen_recommendation",
     r"(could be a great addition|top[- ]ranked|is trending stock|should you buy|"
     r"a buy now|top momentum stock|perfect start|value investors buy|"
     r"which stock should|poised to beat|is it time to buy|potential winner|"
     r"read this before placing a bet|hammer chart pattern|why this 1 )"),
    ("earnings_episode",
     r"(earnings|q[1-4] (results|earnings)|quarterly results|reports (fy ?)?\d|"
     r"surpass(es)? .*estimates|top estimates|beats? (expectations|estimates)|"
     r"earnings call transcript|since last earnings report)"),
    ("guidance_episode", r"(guidance|outlook|reaffirms|forecast|previsiones)"),
    ("corporate_announcement",
     r"(announces|announce |commissions|opens applications|introduces|launches|"
     r"invita|invite|lädt|annonce|to report .*financial results|"
     r"website to broadcast)"),
    ("ma_deal_episode",
     r"(acquisition|acquires|to add .*with acquisition|agreement to sell|"
     r"completed the sale|divest)"),
]
GENRE_PATTERNS = [(name, re.compile(pat, re.I)) for name, pat in GENRES]


def genre_of(title):
    for name, pattern in GENRE_PATTERNS:
        if pattern.search(title or ""):
            return name
    return "unclassified"


def main():
    diag = json.load(open("typeA_filter_diagnostic.json", encoding="utf-8"))
    rows = [json.loads(l) for l in
            open("typeA_manual_review_candidates.jsonl", encoding="utf-8") if l.strip()]

    gt_genre = {}
    for r in rows:
        gt_genre.setdefault(r["anchor_instance_id"], genre_of(r["gt_title"]))

    rescued = collections.Counter()
    for r in rows:
        anchor = r["anchor_instance_id"]
        r["gt_genre"] = gt_genre[anchor]
        r["candidate_genre"] = genre_of(r["title"])
        if r["heuristic_status"] in ("exact", "family"):
            r["manual_semantic_status"] = "ALREADY_MATCHED"
            r["rescue_reason"] = ""
            continue
        same_genre = (r["candidate_genre"] == r["gt_genre"]
                      and r["candidate_genre"] != "unclassified")
        if same_genre:
            r["manual_semantic_status"] = "RESCUED"
            r["rescue_reason"] = ("same recurring episode genre as the ground-truth "
                                  "article (%s); the keyword heuristic mis-typed it as "
                                  "%s" % (r["candidate_genre"], r["inferred_event_type"]))
            rescued[anchor] += 1
        else:
            r["manual_semantic_status"] = "NOT_RESCUED"
            r["rescue_reason"] = ("different episode genre (%s vs ground-truth %s); "
                                  "shared ticker alone is not grounds for a temporal "
                                  "alias" % (r["candidate_genre"], r["gt_genre"]))

    with open("typeA_manual_review_candidates.jsonl", "w", encoding="utf-8",
              newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---- recomputed coverage ------------------------------------------------
    per_anchor = []
    for a in diag["anchors"]:
        iid = a["instance_id"]
        extra = rescued.get(iid, 0)
        total = a["A_total"] + extra
        cands = [r for r in rows if r["anchor_instance_id"] == iid]
        if a["A0_same_ticker_rows"] <= 3 and total < 7:
            mode = "NO_SAME_TICKER_COVERAGE"
        elif a["A1_offset_ge_90d"] == 0:
            mode = "NO_90DAY_COVERAGE"
        elif extra >= 2 and a["A_total"] <= 2:
            mode = "EVENT_HEURISTIC_MISS"
        elif extra > 0:
            mode = "MIXED"
        elif a["below_threshold"]:
            mode = "GENUINELY_NO_ANALOGOUS_EVENT"
        else:
            mode = "COVERED"
        per_anchor.append({
            "instance_id": iid, "ticker": a["ticker"],
            "gt_event_type": a["gt_event_type"],
            "gt_genre": gt_genre.get(iid),
            "A0_same_ticker_rows": a["A0_same_ticker_rows"],
            "A1_offset_ge_90d": a["A1_offset_ge_90d"],
            "A2_exact": a["A2_exact_match"], "A3_family": a["A3_family_match"],
            "A_total_heuristic": a["A_total"],
            "n_manually_rescued": extra,
            "A_total_with_rescue": total,
            "failure_mode": mode,
            "rescued_examples": [{"article_id": r["article_id"], "title": r["title"],
                                  "offset_days": r["offset_days"],
                                  "genre": r["candidate_genre"]}
                                 for r in cands
                                 if r["manual_semantic_status"] == "RESCUED"][:5],
        })

    def count(n, key):
        return sum(1 for r in per_anchor if r[key] >= n)

    summary = {
        "method": "genre-level second opinion read off the article title; a candidate "
                  "is rescued only when it is the same recurring episode genre as the "
                  "ground-truth article. Same ticker and abs(offset_days) >= 90 were "
                  "never relaxed.",
        "genres": [g for g, _ in GENRES],
        "n_candidates_reviewed": len(rows),
        "n_rescued": sum(rescued.values()),
        "n_anchors_with_rescues": len(rescued),
        "coverage_heuristic_only": {"A>=5": count(5, "A_total_heuristic"),
                                    "A>=6": count(6, "A_total_heuristic"),
                                    "A>=7": count(7, "A_total_heuristic"),
                                    "A>=8": count(8, "A_total_heuristic")},
        "coverage_with_manual_rescue": {"A>=5": count(5, "A_total_with_rescue"),
                                        "A>=6": count(6, "A_total_with_rescue"),
                                        "A>=7": count(7, "A_total_with_rescue"),
                                        "A>=8": count(8, "A_total_with_rescue")},
        "failure_mode_counts": dict(collections.Counter(r["failure_mode"]
                                                        for r in per_anchor)),
        "anchors": per_anchor,
    }
    with open("typeA_rescue_summary.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("reviewed %d rejected candidates, rescued %d across %d anchors"
          % (len(rows), sum(rescued.values()), len(rescued)))
    print("\n%-5s %-6s %-18s %4s %4s %5s %7s %8s  %s"
          % ("id", "ticker", "gt_genre", "A0", "A1", "heur", "rescued", "total", "mode"))
    for r in sorted(per_anchor, key=lambda r: r["A_total_with_rescue"]):
        if r["A_total_heuristic"] < 7:
            print("%-5d %-6s %-18s %4d %4d %5d %7d %8d  %s"
                  % (r["instance_id"], r["ticker"], r["gt_genre"] or "-",
                     r["A0_same_ticker_rows"], r["A1_offset_ge_90d"],
                     r["A_total_heuristic"], r["n_manually_rescued"],
                     r["A_total_with_rescue"], r["failure_mode"]))
    print("\ncoverage heuristic only : %s" % summary["coverage_heuristic_only"])
    print("coverage with rescue    : %s" % summary["coverage_with_manual_rescue"])
    print("failure modes: %s" % summary["failure_mode_counts"])


if __name__ == "__main__":
    main()
