"""Select 10 pilot anchors from final50_locked_data.json for distractor validation.

Selection is deterministic (seed 20260821) and uses NO model results: candidates
are visited in a seed-shuffled order and picked greedily for coverage of ticker,
inferred event type, publication period, gold label and source subset, with
same-ticker corpus coverage as a secondary term and instance_id as tie-breaker.

Writes pilot10_locked_ids.json and pilot10_locked_data.json.

Usage:  python select_pilot10_locked.py [--seed 20260821]
"""

import argparse
import collections
import json
import random

import pandas as pd

from build_final_hard50 import load_json
from news_corpus import event_type, parse_article, parse_utc

DATA = "final50_locked_data.json"
MANIFEST = "final50_locked_manifest.json"
CORPUS = "data/MTBench_finance_news.parquet"
N_PILOT = 10


def period(stamp):
    d = parse_utc(stamp)
    return "%d-H%d" % (d.year, 1 if d.month <= 6 else 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260821)
    args = ap.parse_args()

    data = {r["instance_id"]: r for r in load_json(DATA)}
    manifest = {m["instance_id"]: m for m in
                json.load(open(MANIFEST, encoding="utf-8"))["instances"]}

    df = pd.read_parquet(CORPUS, columns=["tickers"])
    coverage = collections.Counter()
    for tickers in df["tickers"]:
        for t in (tickers if tickers is not None else []):
            coverage[t] += 1

    cands = []
    for i, rec in data.items():
        title, text = parse_article(rec["gt_article_text"])
        cands.append({
            "instance_id": i,
            "ticker": rec["ticker"],
            "gold": rec["mcqa_answer"],
            "event": event_type(title, text),
            "period": period(rec["gt_published_utc"]),
            "source": manifest[i]["selected_source"],
            "gt_title": title,
            "gt_published_utc": rec["gt_published_utc"],
            "corpus_articles_same_ticker": coverage.get(rec["ticker"], 0),
        })

    rng = random.Random("%d:pilot-locked" % args.seed)
    order = sorted(cands, key=lambda c: c["instance_id"])
    rng.shuffle(order)
    chosen, seen = [], {k: set() for k in ("ticker", "gold", "event", "period", "source")}
    while order and len(chosen) < N_PILOT:
        best, best_score = None, None
        for c in order:
            score = (sum(c[k] not in seen[k] for k in seen),        # diversity first
                     min(c["corpus_articles_same_ticker"], 40),     # then coverage
                     -c["instance_id"])
            if best_score is None or score > best_score:
                best, best_score = c, score
        chosen.append(best)
        order.remove(best)
        for k in seen:
            seen[k].add(best[k])
    pilot = sorted(chosen, key=lambda c: c["instance_id"])

    with open("pilot10_locked_ids.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({
            "seed": args.seed,
            "source_dataset": DATA,
            "selection": "deterministic diversity-greedy over ticker, inferred event "
                         "type, publication period, gold label and source subset; "
                         "same-ticker corpus coverage as secondary term; no model "
                         "results used",
            "corpus": CORPUS,
            "pilot_ids": [c["instance_id"] for c in pilot],
            "anchors": pilot,
        }, f, indent=2, ensure_ascii=False)
    with open("pilot10_locked_data.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump([data[c["instance_id"]] for c in pilot], f, indent=2, ensure_ascii=False)

    print("pilot anchors (%d):" % len(pilot))
    for c in pilot:
        print("  %-4d %-6s gold=%s %-16s %-8s %-4s corpus_same_ticker=%d"
              % (c["instance_id"], c["ticker"], c["gold"], c["event"], c["period"],
                 c["source"], c["corpus_articles_same_ticker"]))
    print("\ntickers %d | golds %s | events %d | periods %d | sources %s"
          % (len({c["ticker"] for c in pilot}), sorted({c["gold"] for c in pilot}),
             len({c["event"] for c in pilot}), len({c["period"] for c in pilot}),
             sorted({c["source"] for c in pilot})))
    print("wrote pilot10_locked_ids.json and pilot10_locked_data.json")


if __name__ == "__main__":
    main()
