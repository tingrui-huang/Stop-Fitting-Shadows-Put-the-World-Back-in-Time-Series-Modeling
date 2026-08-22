"""Build distractor CANDIDATE pools for the pilot anchors from the real corpus.

Two types only, as the current paper defines them:

  temporal_aliasing : same ticker, same event type, >= 90 days before the GT
                      article (a different reporting cycle of the same event)
  absence_evidence  : same ticker, topically adjacent, but documenting a
                      different mechanism - no corresponding target event

This produces a REVIEW POOL, not a final 10-per-anchor selection: the paper does
not fix an A/B ratio, so the ratio is left open and the available counts are
reported instead.  Every candidate is a real corpus row; nothing is generated.

Corpus: data/MTBench_finance_news.parquet (GGLabYale/MTBench_finance_news).

Writes pilot10_distractor_candidates.jsonl and pilot10_distractor_manifest.json.

Usage:  python build_pilot_candidates.py [--target-a 12] [--target-b 6]
"""

import argparse
import datetime as dt
import json

import pandas as pd

from build_final_hard50 import load_json
from news_corpus import event_type, parse_article, parse_utc

CORPUS = "data/MTBench_finance_news.parquet"
PILOT = "pilot10_locked_data.json"
COLS = ["id", "tickers", "published_utc", "title", "content", "description",
        "publisher", "article_url", "label_type", "label_time", "label_sentiment"]

ALIAS_MIN_DAYS = 90      # paper: >= 90 days, about one fiscal quarter
ABSENCE_MAX_DAYS = 45    # "topically adjacent" context around the episode

# "same or clearly analogous event type": exact inferred type first, then a
# coarse family.  Which tier matched is recorded on every candidate.
FAMILY = {
    "earnings": "results_outlook", "guidance": "results_outlook",
    "analyst_rating": "analyst",
    "stock_move": "market_move", "macro_market": "market_move",
    "ma_deal": "corporate_action", "product_launch": "corporate_action",
    "executive": "corporate_action", "dividend_buyback": "corporate_action",
    "legal_regulatory": "corporate_action",
    "other": "other",
}


def match_level(gt_event, cand_event):
    """-> (level, quality) or (None, None) when the types are not analogous."""
    if cand_event == gt_event:
        return ("exact", "weak (both fall in the catch-all 'other' class)"
                if gt_event == "other" else "strong")
    if FAMILY.get(cand_event) == FAMILY.get(gt_event) and FAMILY.get(gt_event) != "other":
        return ("family", "medium")
    return (None, None)


def as_list(x):
    return [] if x is None else list(x)


def row_record(row):
    return {
        "article_id": row["id"],
        "ticker_list": as_list(row["tickers"]),
        "published_utc": row["published_utc"].strftime("%Y-%m-%d %H:%M:%S"),
        "published_dt": row["published_utc"].to_pydatetime(),
        "title": row["title"],
        "content": row["content"] or "",
        "publisher": (row["publisher"] or {}).get("name") if isinstance(row["publisher"], dict) else None,
        "article_url": row["article_url"],
        "label_type": as_list(row["label_type"]),
        "label_time": as_list(row["label_time"]),
        "label_sentiment": as_list(row["label_sentiment"]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-a", type=int, default=12)
    ap.add_argument("--target-b", type=int, default=6)
    args = ap.parse_args()

    df = pd.read_parquet(CORPUS, columns=COLS)
    by_ticker = {}
    for _, row in df.iterrows():
        for t in as_list(row["tickers"]):
            by_ticker.setdefault(t, []).append(row)

    pilot = load_json(PILOT)
    records, per_anchor = [], []

    for rec in pilot:
        iid, ticker = rec["instance_id"], rec["ticker"]
        gt_title, gt_text = parse_article(rec["gt_article_text"])
        gt_dt = parse_utc(rec["gt_published_utc"])
        gt_event = event_type(gt_title, gt_text)

        pool = [row_record(r) for r in by_ticker.get(ticker, [])]
        gt_match = next((a for a in pool if a["title"].strip() == gt_title.strip()), None)
        gt_article_id = gt_match["article_id"] if gt_match else "anchor:%d" % iid
        pool = [a for a in pool if a["title"].strip() != gt_title.strip()]
        for a in pool:
            a["event_type"] = event_type(a["title"], a["content"])
            a["offset_days"] = (a["published_dt"] - gt_dt).total_seconds() / 86400.0

        for a in pool:
            a["match_level"], a["match_quality"] = match_level(gt_event, a["event_type"])
        alias = sorted((a for a in pool
                        if a["match_level"] is not None
                        and a["offset_days"] <= -ALIAS_MIN_DAYS),
                       key=lambda a: (0 if a["match_level"] == "exact" else 1,
                                      abs(a["offset_days"]), a["article_id"]))
        n_exact = sum(1 for a in alias if a["match_level"] == "exact")
        alias_future = [a for a in pool if a["event_type"] == gt_event
                        and a["offset_days"] >= ALIAS_MIN_DAYS]
        absence = sorted((a for a in pool
                          if a["event_type"] != gt_event
                          and abs(a["offset_days"]) <= ABSENCE_MAX_DAYS),
                         key=lambda a: (abs(a["offset_days"]), a["article_id"]))

        def emit(a, kind, rank):
            records.append({
                "anchor_instance_id": iid,
                "anchor_ticker": ticker,
                "gt_article_id": gt_article_id,
                "gt_article_in_corpus": gt_match is not None,
                "gt_published_utc": rec["gt_published_utc"],
                "gt_event_type": gt_event,
                "distractor_type": kind,
                "candidate_rank": rank,
                "distractor_article_id": a["article_id"],
                "distractor_ticker": ticker,
                "distractor_ticker_list": a["ticker_list"],
                "distractor_published_utc": a["published_utc"],
                "distractor_title": a["title"],
                "distractor_content_chars": len(a["content"]),
                "distractor_content_preview": a["content"][:600],
                "distractor_event_type": a["event_type"],
                "distractor_label_type_explicit": a["label_type"],
                "distractor_label_time_explicit": a["label_time"],
                "distractor_label_sentiment_explicit": a["label_sentiment"],
                "time_offset_days": round(a["offset_days"], 2),
                "same_ticker": True,
                "event_type_match": a["event_type"] == gt_event,
                "event_type_match_level": a.get("match_level"),
                "event_type_match_quality": a.get("match_quality"),
                "event_type_source": "inferred (keyword heuristic over real article "
                                     "text; corpus label_type recorded separately as "
                                     "the explicit but coarser label)",
                "semantic_plausibility_reason":
                    ("same ticker and same event type (%s) as the ground-truth "
                     "article, %.0f days earlier - a different reporting cycle of the "
                     "same recurring event, so it stays plausible once explicit dates "
                     "are masked" % (a["event_type"], abs(a["offset_days"]))) if kind ==
                    "temporal_aliasing" else
                    ("same ticker and only %.0f days from the target episode, so it "
                     "reads as relevant context, but it documents %s rather than %s"
                     % (abs(a["offset_days"]), a["event_type"], gt_event)),
                "why_not_valid_gt":
                    ("it belongs to a different reporting cycle (%.0f days before the "
                     "target episode) and therefore cannot be the evidence the "
                     "question is about" % abs(a["offset_days"]))
                    if kind == "temporal_aliasing" else
                    ("it documents no %s event, so it cannot supply the mechanism the "
                     "question asks about" % gt_event),
                "provenance": {
                    "dataset": "GGLabYale/MTBench_finance_news",
                    "local_copy": CORPUS,
                    "corpus_id": a["article_id"],
                    "article_url": a["article_url"],
                    "publisher": a["publisher"],
                    "text_modified": False,
                    "timestamp_modified": False,
                },
                "manual_review_required": True,
                "notes": "",
            })

        for rank, a in enumerate(alias[:args.target_a], 1):
            emit(a, "temporal_aliasing", rank)
        for rank, a in enumerate(absence[:args.target_b], 1):
            emit(a, "absence_evidence", rank)

        per_anchor.append({
            "instance_id": iid, "ticker": ticker,
            "gt_article_id": gt_article_id,
            "gt_article_in_corpus": gt_match is not None,
            "gt_event_type": gt_event,
            "gt_published_utc": rec["gt_published_utc"],
            "same_ticker_articles_in_corpus": len(pool),
            "n_temporal_aliasing_candidates": min(len(alias), args.target_a),
            "n_temporal_aliasing_available": len(alias),
            "n_temporal_aliasing_exact_type": n_exact,
            "n_temporal_aliasing_family_type": len(alias) - n_exact,
            "n_absence_candidates": min(len(absence), args.target_b),
            "n_absence_available": len(absence),
            "n_future_dated_same_event_excluded": len(alias_future),
            "meets_target_a_8": len(alias) >= 8,
            "meets_target_b_3": len(absence) >= 3,
        })

    with open("pilot10_distractor_candidates.jsonl", "w", encoding="utf-8",
              newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    manifest = {
        "corpus": {
            "dataset": "GGLabYale/MTBench_finance_news",
            "local_copy": CORPUS,
            "rows": int(len(df)),
            "fields": COLS,
        },
        "taxonomy": {
            "temporal_aliasing": "same ticker, same event type, >= %d days before the "
                                 "GT article (different reporting cycle)" % ALIAS_MIN_DAYS,
            "absence_evidence": "same ticker, within %d days, different mechanism - no "
                                "corresponding target event" % ABSENCE_MAX_DAYS,
        },
        "ratio_policy": "the current paper does not fix an A/B split inside the 10, so "
                        "no ratio is imposed here; this file is a review pool and the "
                        "final mix is to be decided after manual review",
        "event_type_source": "inferred by keyword heuristic; the corpus label_type / "
                             "label_time / label_sentiment fields are explicit and are "
                             "recorded verbatim on every candidate",
        "future_dated_same_event_articles": "excluded from temporal_aliasing (the "
                                            "paper defines aliasing as an earlier "
                                            "reporting cycle); counted per anchor",
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "totals": {
            "n_candidates": len(records),
            "n_temporal_aliasing": sum(1 for r in records
                                       if r["distractor_type"] == "temporal_aliasing"),
            "n_absence_evidence": sum(1 for r in records
                                      if r["distractor_type"] == "absence_evidence"),
            "anchors_meeting_target_a_8": sum(1 for a in per_anchor if a["meets_target_a_8"]),
            "anchors_meeting_target_b_3": sum(1 for a in per_anchor if a["meets_target_b_3"]),
        },
        "anchors": per_anchor,
    }
    with open("pilot10_distractor_manifest.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("corpus rows: %d" % len(df))
    print("candidates: %d (%d aliasing, %d absence)"
          % (len(records), manifest["totals"]["n_temporal_aliasing"],
             manifest["totals"]["n_absence_evidence"]))
    for a in per_anchor:
        print("  %-4d %-5s %-15s same-ticker %3d | A avail %2d (target>=8 %s) | "
              "B avail %2d (target>=3 %s) | future-dated same-event %d"
              % (a["instance_id"], a["ticker"], a["gt_event_type"],
                 a["same_ticker_articles_in_corpus"], a["n_temporal_aliasing_available"],
                 "OK" if a["meets_target_a_8"] else "NO", a["n_absence_available"],
                 "OK" if a["meets_target_b_3"] else "NO",
                 a["n_future_dated_same_event_excluded"]))
    print("wrote pilot10_distractor_candidates.jsonl and pilot10_distractor_manifest.json")


if __name__ == "__main__":
    main()
