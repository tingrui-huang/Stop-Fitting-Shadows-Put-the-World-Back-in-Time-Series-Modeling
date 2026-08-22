"""Select 10 pilot anchors from final50_frozen_data.json (2 challenge + 8 normal).

Deterministic: candidates are visited in a seed-shuffled order and picked
greedily by how much new coverage they add (ticker, gold answer, event type,
time period, source dataset), with instance_id as the tie-breaker.

Writes pilot10_ids.json and pilot10_data.json.

Usage:  python select_pilot10.py [--seed 20260821]
"""

import argparse
import json
import random

from build_final_hard50 import load_json
from news_corpus import event_type, load_corpus, parse_article, parse_utc

DATA = "final50_frozen_data.json"
MANIFEST = "final50_frozen_manifest.json"
N_CHALLENGE = 2
N_NORMAL = 8


def period(stamp):
    d = parse_utc(stamp)
    return "%d-H%d" % (d.year, 1 if d.month <= 6 else 2)


def confidence_bucket(entry):
    confs = [c for c in (entry.get("final50_confidence"),) if c is not None]
    if not confs:
        return "unrun"
    mean = sum(confs) / len(confs)
    return "low" if mean < 0.6 else ("mid" if mean < 0.8 else "high")


def pick(candidates, n, seed_key, seed):
    """Greedy diversity pick; deterministic given the seed."""
    rng = random.Random("%d:%s" % (seed, seed_key))
    order = sorted(candidates, key=lambda c: c["instance_id"])
    rng.shuffle(order)
    chosen, seen = [], {k: set() for k in
                        ("ticker", "gold", "event", "period", "source", "conf")}
    while order and len(chosen) < n:
        best, best_score = None, None
        for cand in order:
            # diversity first, then same-ticker corpus coverage, then lowest id
            score = (sum(cand[k] not in seen[k] for k in seen),
                     min(cand["same_ticker_articles_local"], 1),
                     -cand["instance_id"])
            if best_score is None or score > best_score:
                best, best_score = cand, score
        chosen.append(best)
        order.remove(best)
        for k in seen:
            seen[k].add(best[k])
    return sorted(chosen, key=lambda c: c["instance_id"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260821)
    args = ap.parse_args()

    with open(DATA, encoding="utf-8") as f:
        data = {r["instance_id"]: r for r in json.load(f)}
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)

    corpus = load_corpus(load_json)
    ticker_counts = {}
    for a in corpus.values():
        ticker_counts[a["ticker"]] = ticker_counts.get(a["ticker"], 0) + 1

    cands = []
    for entry in manifest["instances"]:
        rec = data[entry["instance_id"]]
        title, text = parse_article(rec["gt_article_text"])
        cands.append({
            "instance_id": entry["instance_id"],
            "ticker": rec["ticker"],
            "gold": rec["mcqa_answer"],
            "event": event_type(title, text),
            "period": period(rec["gt_published_utc"]),
            "source": entry["selected_source"],
            "conf": confidence_bucket(entry),
            "challenge_anchor": entry["challenge_anchor"],
            "gt_title": title,
            "gt_published_utc": rec["gt_published_utc"],
            "challenge_reason": entry["challenge_reason"],
            "same_ticker_articles_local": ticker_counts.get(rec["ticker"], 1) - 1,
        })

    challenge = pick([c for c in cands if c["challenge_anchor"]],
                     N_CHALLENGE, "challenge", args.seed)
    normal = pick([c for c in cands if not c["challenge_anchor"]],
                  N_NORMAL, "normal", args.seed)
    pilot = sorted(challenge + normal, key=lambda c: c["instance_id"])

    with open("pilot10_ids.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({"seed": args.seed, "source_dataset": DATA,
                   "same_ticker_coverage_source":
                       "local fallback corpus (100 GT articles of c0_data.json + "
                       "hard50_data.json); the real MTBench finance-news corpus is "
                       "not present, so this coverage signal must be recomputed once "
                       "data/MTBench_finance_news.parquet is available",
                   "n_challenge": N_CHALLENGE, "n_normal": N_NORMAL,
                   "challenge_ids": [c["instance_id"] for c in challenge],
                   "normal_ids": [c["instance_id"] for c in normal],
                   "anchors": pilot}, f, indent=2, ensure_ascii=False)
    with open("pilot10_data.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump([data[c["instance_id"]] for c in pilot], f, indent=2, ensure_ascii=False)

    print("pilot anchors (%d):" % len(pilot))
    for c in pilot:
        print("  %-4d %-6s gold=%s %-16s %-8s %-5s %-5s %s"
              % (c["instance_id"], c["ticker"], c["gold"], c["event"], c["period"],
                 c["source"], c["conf"],
                 "CHALLENGE(%s)" % c["challenge_reason"] if c["challenge_anchor"] else ""))
    print("\ndistinct tickers %d | golds %s | events %d | periods %d | sources %s"
          % (len({c["ticker"] for c in pilot}),
             sorted({c["gold"] for c in pilot}),
             len({c["event"] for c in pilot}),
             len({c["period"] for c in pilot}),
             sorted({c["source"] for c in pilot})))
    print("wrote pilot10_ids.json and pilot10_data.json")


if __name__ == "__main__":
    main()
