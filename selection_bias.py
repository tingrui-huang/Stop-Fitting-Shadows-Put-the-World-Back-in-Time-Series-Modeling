"""Does a fixed A/B ratio bias the benchmark? Compare three anchor sets.

  A  all 50 locked anchors (the reference distribution)
  B  the fixed 7A+3B eligible subset (distractor_coverage_grid_v2.json)
  C  the adaptive target-and-fill covered subset (adaptive_distractor_coverage.json)

Dimensions: event family, earnings vs non-earnings, gold label, publication
period, source subset, ticker diversity.  Retention per stratum shows which
kinds of anchor a policy silently drops.

Writes distractor_policy_selection_bias.json.

Usage:  python selection_bias.py
"""

import collections
import json

from build_final_hard50 import load_json
from distractor_policy import FAMILY
from news_corpus import event_type, parse_article, parse_utc

DATA = "final50_locked_data.json"
MANIFEST = "final50_locked_manifest.json"


def period(stamp):
    d = parse_utc(stamp)
    return "%d-H%d" % (d.year, 1 if d.month <= 6 else 2)


def profile(rows):
    def dist(key):
        return dict(sorted(collections.Counter(r[key] for r in rows).items()))
    return {
        "n": len(rows),
        "event_family": dist("event_family"),
        "event_type": dist("event_type"),
        "earnings_vs_non_earnings": dict(sorted(collections.Counter(
            "earnings" if r["event_type"] == "earnings" else "non_earnings"
            for r in rows).items())),
        "gold_label": dist("gold"),
        "publication_period": dist("period"),
        "source_subset": dist("source"),
        "n_distinct_tickers": len({r["ticker"] for r in rows}),
        "ticker_diversity_ratio": round(len({r["ticker"] for r in rows}) /
                                        max(1, len(rows)), 3),
        "median_same_ticker_corpus_articles": sorted(
            r["corpus_articles_same_ticker"] for r in rows)[len(rows) // 2] if rows else 0,
    }


def retention(all_rows, subset_ids, key):
    out = {}
    totals = collections.Counter(r[key] for r in all_rows)
    kept = collections.Counter(r[key] for r in all_rows if r["instance_id"] in subset_ids)
    for k in sorted(totals):
        out[k] = {"total": totals[k], "kept": kept.get(k, 0),
                  "retention": round(kept.get(k, 0) / totals[k], 2)}
    return out


def main():
    data = load_json(DATA)
    src = {m["instance_id"]: m["selected_source"] for m in
           json.load(open(MANIFEST, encoding="utf-8"))["instances"]}
    grid = json.load(open("distractor_coverage_grid_v2.json", encoding="utf-8"))
    adaptive = json.load(open("adaptive_distractor_coverage.json", encoding="utf-8"))
    corpus_counts = {a["instance_id"]: a["same_ticker_articles"] for a in grid["anchors"]}

    fixed_ids = set(next(g for g in grid["grid"] if g["ratio"] == "7A+3B")["covered_ids"])
    adaptive_ids = {a["instance_id"] for a in adaptive["anchors"] if a["reaches_10"]}

    rows = []
    for rec in data:
        title, text = parse_article(rec["gt_article_text"])
        et = event_type(title, text)
        rows.append({
            "instance_id": rec["instance_id"], "ticker": rec["ticker"],
            "event_type": et, "event_family": FAMILY.get(et, "other"),
            "gold": rec["mcqa_answer"],
            "period": period(rec["gt_published_utc"]),
            "source": src[rec["instance_id"]],
            "corpus_articles_same_ticker": corpus_counts.get(rec["instance_id"], 0),
        })

    groups = {
        "A_all_locked_50": rows,
        "B_fixed_7A_3B_eligible": [r for r in rows if r["instance_id"] in fixed_ids],
        "C_adaptive_covered": [r for r in rows if r["instance_id"] in adaptive_ids],
    }
    profiles = {name: profile(rs) for name, rs in groups.items()}

    summary = {
        "purpose": "check whether forcing a fixed A/B ratio biases the benchmark "
                   "toward high-news-volume, earnings-heavy tickers",
        "groups": {"A": "all 50 locked anchors",
                   "B": "fixed 7A+3B eligible subset",
                   "C": "adaptive target-and-fill covered subset"},
        "membership": {"B_ids": sorted(fixed_ids), "C_ids": sorted(adaptive_ids),
                       "in_C_not_B": sorted(adaptive_ids - fixed_ids),
                       "in_B_not_C": sorted(fixed_ids - adaptive_ids)},
        "profiles": profiles,
        "retention_by_stratum": {
            "fixed_7A_3B": {
                "event_family": retention(rows, fixed_ids, "event_family"),
                "earnings": retention(rows, fixed_ids, "event_type"),
                "gold_label": retention(rows, fixed_ids, "gold"),
                "period": retention(rows, fixed_ids, "period"),
                "source": retention(rows, fixed_ids, "source"),
            },
            "adaptive": {
                "event_family": retention(rows, adaptive_ids, "event_family"),
                "earnings": retention(rows, adaptive_ids, "event_type"),
                "gold_label": retention(rows, adaptive_ids, "gold"),
                "period": retention(rows, adaptive_ids, "period"),
                "source": retention(rows, adaptive_ids, "source"),
            },
        },
    }
    with open("distractor_policy_selection_bias.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("%-26s %-4s %-30s %-22s %-16s %s"
          % ("group", "n", "earnings vs non", "gold labels", "tickers", "median same-ticker corpus"))
    for name, p in profiles.items():
        print("%-26s %-4d %-30s %-22s %-16s %d"
              % (name, p["n"], p["earnings_vs_non_earnings"], p["gold_label"],
                 "%d (%.2f)" % (p["n_distinct_tickers"], p["ticker_diversity_ratio"]),
                 p["median_same_ticker_corpus_articles"]))
    print("\nevent family by group:")
    for name, p in profiles.items():
        print("  %-26s %s" % (name, p["event_family"]))
    print("\nsource subset by group:")
    for name, p in profiles.items():
        print("  %-26s %s" % (name, p["source_subset"]))
    print("\nin adaptive but not fixed: %s" % summary["membership"]["in_C_not_B"])
    print("in fixed but not adaptive: %s" % summary["membership"]["in_B_not_C"])
    print("wrote distractor_policy_selection_bias.json")


if __name__ == "__main__":
    main()
