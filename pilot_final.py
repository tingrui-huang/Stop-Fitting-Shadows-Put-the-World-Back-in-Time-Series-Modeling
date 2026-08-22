"""Select the pilot 10 under the chosen coverage policy and build review pools.

Policy (from distractor_coverage_grid.json - least relaxed cell with the best
coverage): 8 temporal-aliasing + 2 absence-evidence per anchor, Type B window
unrestricted within the corpus.  22 of the 50 locked anchors satisfy it.

Selection is deterministic (seed 20260821), uses NO model results, and balances
ticker, event family, gold label, publication period, source subset and whether
the anchor needs family-tier aliases to reach 8.

Review pools are deliberately larger than needed: 10 Type A (8+2) and 4 Type B
(2+2) per anchor, ranked by match tier and plausibility - never by nearest
timestamp.

Writes pilot10_final_ids.json, pilot10_final_data.json,
pilot10_review_candidates.jsonl, pilot10_review_manifest.json.

Usage:  python pilot_final.py [--seed 20260821]
"""

import argparse
import datetime as dt
import json
import random

from build_final_hard50 import load_json
from distractor_policy import (ALIAS_MIN_DAYS, FAMILY, alias_map_from,
                               index_by_ticker, load_corpus_frame,
                               type_a_candidates, type_b_candidates)
from news_corpus import event_type, parse_article, parse_utc

DATA = "final50_locked_data.json"
MANIFEST = "final50_locked_manifest.json"
POLICY = {"n_a": 8, "n_b": 2, "type_b_window_days": None}
REVIEW_EXTRA = 2
N_PILOT = 10


def period(stamp):
    d = parse_utc(stamp)
    return "%d-H%d" % (d.year, 1 if d.month <= 6 else 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260821)
    args = ap.parse_args()

    df = load_corpus_frame()
    by_ticker = index_by_ticker(df)
    alias = alias_map_from(df)
    data = {r["instance_id"]: r for r in load_json(DATA)}
    src = {m["instance_id"]: m["selected_source"]
           for m in json.load(open(MANIFEST, encoding="utf-8"))["instances"]}

    # ---- per-anchor candidate generation under the fixed policy -------------
    anchors = {}
    for iid, rec in data.items():
        title, text = parse_article(rec["gt_article_text"])
        gt_event = event_type(title, text)
        gt_dt = parse_utc(rec["gt_published_utc"])
        pool = [a for a in by_ticker.get(rec["ticker"], [])
                if a["title"].strip() != title.strip()]
        a_c = type_a_candidates(pool, gt_event, gt_dt)
        b_c = type_b_candidates(pool, gt_event, gt_dt, alias, rec["ticker"],
                                POLICY["type_b_window_days"])
        anchors[iid] = {
            "instance_id": iid, "ticker": rec["ticker"],
            "gold": rec["mcqa_answer"],
            "gt_title": title, "gt_event_type": gt_event,
            "gt_event_family": FAMILY.get(gt_event, "other"),
            "gt_published_utc": rec["gt_published_utc"],
            "period": period(rec["gt_published_utc"]),
            "source": src[iid],
            "a": a_c, "b": b_c,
            "n_a": len(a_c), "n_b": len(b_c),
            "n_a_exact": sum(1 for c in a_c if c["tier"] == "exact"),
            "satisfies": len(a_c) >= POLICY["n_a"] and len(b_c) >= POLICY["n_b"],
        }
        anchors[iid]["needs_family"] = (anchors[iid]["n_a_exact"] < POLICY["n_a"])

    eligible = [a for a in anchors.values() if a["satisfies"]]

    # ---- deterministic diversity pick --------------------------------------
    rng = random.Random("%d:pilot-final" % args.seed)
    order = sorted(eligible, key=lambda a: a["instance_id"])
    rng.shuffle(order)
    keys = ("ticker", "gt_event_family", "gold", "period", "source", "needs_family")
    chosen, seen = [], {k: set() for k in keys}
    while order and len(chosen) < N_PILOT:
        best, best_score = None, None
        for a in order:
            score = (sum(a[k] not in seen[k] for k in keys), -a["instance_id"])
            if best_score is None or score > best_score:
                best, best_score = a, score
        chosen.append(best)
        order.remove(best)
        for k in keys:
            seen[k].add(best[k])
    pilot = sorted(chosen, key=lambda a: a["instance_id"])

    with open("pilot10_final_ids.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({
            "seed": args.seed, "source_dataset": DATA,
            "policy": POLICY,
            "policy_source": "distractor_coverage_grid.json (least relaxed cell with "
                             "the best coverage: 8A+2B, Type B window unrestricted)",
            "n_eligible_anchors": len(eligible),
            "eligible_ids": sorted(a["instance_id"] for a in eligible),
            "pilot_ids": [a["instance_id"] for a in pilot],
            "selection": "deterministic diversity-greedy over ticker, event family, "
                         "gold label, period, source subset and family-tier "
                         "dependence; no model results used",
            "anchors": [{k: a[k] for k in
                         ("instance_id", "ticker", "gold", "gt_event_type",
                          "gt_event_family", "period", "source", "gt_published_utc",
                          "gt_title", "n_a", "n_a_exact", "n_b", "needs_family")}
                        for a in pilot],
        }, f, indent=2, ensure_ascii=False)
    with open("pilot10_final_data.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump([data[a["instance_id"]] for a in pilot], f, indent=2,
                  ensure_ascii=False)

    # ---- review candidate pools --------------------------------------------
    want_a, want_b = POLICY["n_a"] + REVIEW_EXTRA, POLICY["n_b"] + REVIEW_EXTRA
    records, per_anchor = [], []
    for a in pilot:
        iid = a["instance_id"]
        for rank, c in enumerate(a["a"][:want_a], 1):
            art = c["article"]
            records.append({
                "anchor_instance_id": iid, "anchor_ticker": a["ticker"],
                "gt_published_utc": a["gt_published_utc"],
                "gt_event_type": a["gt_event_type"],
                "distractor_type": "temporal_aliasing",
                "candidate_rank": rank,
                "distractor_article_id": art["article_id"],
                "distractor_ticker": a["ticker"],
                "distractor_ticker_list": art["tickers"],
                "distractor_published_utc": art["published_utc"],
                "distractor_title": art["title"],
                "distractor_content_chars": len(art["content"]),
                "distractor_content_preview": art["content"][:600],
                "offset_days": round(c["offset_days"], 2),
                "alias_direction": c["alias_direction"],
                "event_match_tier": c["tier"],
                "distractor_event_type": art["event_type"],
                "event_type_source": "inferred (keyword heuristic over the real "
                                     "article text); corpus label_type is explicit "
                                     "and is carried verbatim",
                "label_type_explicit": art["label_type"],
                "label_time_explicit": art["label_time"],
                "label_sentiment_explicit": art["label_sentiment"],
                "semantic_plausibility_reason":
                    "same ticker and %s event type (%s vs %s), %s by %.0f days: a "
                    "different reporting episode of the same recurring event, so it "
                    "stays plausible once explicit dates are masked"
                    % (c["tier"], art["event_type"], a["gt_event_type"],
                       c["alias_direction"], abs(c["offset_days"])),
                "why_not_valid_gt":
                    "it belongs to a different episode (%.0f days %s the target "
                    "article, beyond the %d-day separation), so it cannot be the "
                    "evidence the question is about"
                    % (abs(c["offset_days"]),
                       "before" if c["offset_days"] < 0 else "after", ALIAS_MIN_DAYS),
                "provenance": {"dataset": "GGLabYale/MTBench_finance_news",
                               "local_copy": "data/MTBench_finance_news.parquet",
                               "corpus_id": art["article_id"],
                               "article_url": art["article_url"],
                               "publisher": art["publisher"],
                               "text_modified": False, "timestamp_modified": False},
                "manual_review_required": True,
                "notes": "",
            })
        for rank, c in enumerate(a["b"][:want_b], 1):
            art = c["article"]
            records.append({
                "anchor_instance_id": iid, "anchor_ticker": a["ticker"],
                "gt_published_utc": a["gt_published_utc"],
                "gt_event_type": a["gt_event_type"],
                "distractor_type": "absence_evidence",
                "candidate_rank": rank,
                "distractor_article_id": art["article_id"],
                "distractor_ticker": a["ticker"],
                "distractor_ticker_list": art["tickers"],
                "distractor_published_utc": art["published_utc"],
                "distractor_title": art["title"],
                "distractor_content_chars": len(art["content"]),
                "distractor_content_preview": art["content"][:600],
                "offset_days": round(c["offset_days"], 2),
                "alias_direction": "n/a",
                "event_match_tier": "n/a",
                "distractor_event_type": art["event_type"],
                "event_type_source": "inferred (keyword heuristic); corpus label_type "
                                     "carried verbatim",
                "label_type_explicit": art["label_type"],
                "label_time_explicit": art["label_time"],
                "label_sentiment_explicit": art["label_sentiment"],
                "topical_relation": c["topical_relation"],
                "target_event_absent": True,
                "why_target_event_absent":
                    "the article never matches the %s event pattern, so the mechanism "
                    "the question turns on is not documented in it" % a["gt_event_type"],
                "why_semantically_plausible":
                    "same ticker, company named %s, %.0f days from the target episode, "
                    "so it reads as relevant company context"
                    % ("in the title" if c["entity"]["entity_in_title"]
                       else "in the body", abs(c["offset_days"])),
                "semantic_plausibility_reason":
                    "same-ticker company coverage adjacent to the episode without the "
                    "target event",
                "why_not_valid_gt":
                    "it documents %s rather than %s and is not a strong event class, "
                    "so it cannot serve as an alternative explanation for the MCQA"
                    % (art["event_type"], a["gt_event_type"]),
                "provenance": {"dataset": "GGLabYale/MTBench_finance_news",
                               "local_copy": "data/MTBench_finance_news.parquet",
                               "corpus_id": art["article_id"],
                               "article_url": art["article_url"],
                               "publisher": art["publisher"],
                               "text_modified": False, "timestamp_modified": False},
                "manual_review_required": True,
                "notes": "",
            })

        got_a = a["a"][:want_a]
        got_b = a["b"][:want_b]
        per_anchor.append({
            "instance_id": iid, "ticker": a["ticker"],
            "gt_event_type": a["gt_event_type"],
            "n_type_a_in_pool": len(got_a), "n_type_a_available": a["n_a"],
            "n_type_a_exact": sum(1 for c in got_a if c["tier"] == "exact"),
            "n_type_a_family": sum(1 for c in got_a if c["tier"] == "family"),
            "n_type_a_historical": sum(1 for c in got_a
                                       if c["alias_direction"] == "historical"),
            "n_type_a_future": sum(1 for c in got_a if c["alias_direction"] == "future"),
            "n_type_b_in_pool": len(got_b), "n_type_b_available": a["n_b"],
            "pool_meets_review_target": len(got_a) >= want_a and len(got_b) >= want_b,
        })

    with open("pilot10_review_candidates.jsonl", "w", encoding="utf-8",
              newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open("pilot10_review_manifest.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({
            "policy": POLICY,
            "review_pool_targets": {"type_a": want_a, "type_b": want_b},
            "corpus": {"dataset": "GGLabYale/MTBench_finance_news",
                       "local_copy": "data/MTBench_finance_news.parquet",
                       "rows": int(len(df))},
            "ranking": {
                "type_a": "exact tier, then family tier, then closest analogous "
                          "episode beyond 90 days, then article id - never nearest "
                          "timestamp first",
                "type_b": "company named in the title, then temporal proximity, "
                          "then article id",
            },
            "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "REVIEW POOL - the final 10 per anchor are NOT locked",
            "totals": {
                "n_candidates": len(records),
                "n_type_a": sum(1 for r in records
                                if r["distractor_type"] == "temporal_aliasing"),
                "n_type_b": sum(1 for r in records
                                if r["distractor_type"] == "absence_evidence"),
                "anchors_meeting_review_target": sum(1 for a in per_anchor
                                                     if a["pool_meets_review_target"]),
            },
            "anchors": per_anchor,
        }, f, indent=2, ensure_ascii=False)

    print("eligible anchors under %dA+%dB: %d/50" % (POLICY["n_a"], POLICY["n_b"],
                                                     len(eligible)))
    print("pilot: %s" % [a["instance_id"] for a in pilot])
    for a in pilot:
        print("  %-4d %-5s gold=%s %-15s %-8s %-4s A=%d (exact %d) B=%d family_needed=%s"
              % (a["instance_id"], a["ticker"], a["gold"], a["gt_event_type"],
                 a["period"], a["source"], a["n_a"], a["n_a_exact"], a["n_b"],
                 a["needs_family"]))
    print("\nreview candidates: %d (A %d, B %d), anchors meeting pool target: %d/10"
          % (len(records),
             sum(1 for r in records if r["distractor_type"] == "temporal_aliasing"),
             sum(1 for r in records if r["distractor_type"] == "absence_evidence"),
             sum(1 for a in per_anchor if a["pool_meets_review_target"])))
    print("wrote pilot10_final_ids.json, pilot10_final_data.json, "
          "pilot10_review_candidates.jsonl, pilot10_review_manifest.json")


if __name__ == "__main__":
    main()
