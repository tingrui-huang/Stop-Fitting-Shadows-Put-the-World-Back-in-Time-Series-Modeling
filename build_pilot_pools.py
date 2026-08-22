"""Render pilot C1/C2 prompts from the resolved distractor slots.

Reuses the existing prompt template, article rendering and temporal masker - no
new wording, no condition-specific hints, no schema change.  One fixed shuffled
article order per anchor, reused byte for byte by C1 and C2; C2 differs only by
temporal masking (positional time series, no publication line, masked article
text).

IMPORTANT: with the corpus currently available, no anchor has all 10 slots
resolved.  Pools are written for anchors with at least one resolved distractor
and are flagged pool_complete=false; the manifest carries ready_for_inference,
which is true only when every pool holds GT + 10 distractors.

Writes out/pilot10/c1.jsonl, out/pilot10/c2.jsonl, out/pilot10/manifest.json.

Usage:  python build_pilot_pools.py [--seed 20260821]
"""

import argparse
import json
import os
import random

from build_conditions import (PROMPT_TEMPLATE, RESPONSE_FORMAT, fmt_articles,
                              fmt_ts_positional, fmt_ts_timestamped)
from build_final_hard50 import load_json
from news_corpus import load_corpus, parse_article
from temporal_mask import mask_temporal

OUT_DIR = os.path.join("out", "pilot10")
N_SLOTS = 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260821)
    args = ap.parse_args()

    corpus = load_corpus(load_json)
    pilot = {r["instance_id"]: r for r in load_json("pilot10_data.json")}
    slots = [json.loads(l) for l in
             open("pilot10_distractors.jsonl", encoding="utf-8") if l.strip()]

    by_anchor = {}
    for row in slots:
        by_anchor.setdefault(row["anchor_instance_id"], []).append(row)

    os.makedirs(OUT_DIR, exist_ok=True)
    f1 = open(os.path.join(OUT_DIR, "c1.jsonl"), "w", encoding="utf-8", newline="\n")
    f2 = open(os.path.join(OUT_DIR, "c2.jsonl"), "w", encoding="utf-8", newline="\n")
    manifest_rows, n_complete = [], 0

    for iid in sorted(pilot):
        rec = pilot[iid]
        gt_title, gt_text = parse_article(rec["gt_article_text"])
        gt_article = {"article_id": "gt:%d" % iid, "title": gt_title,
                      "text": gt_text, "published": rec["gt_published_utc"]}

        rows = sorted(by_anchor.get(iid, []), key=lambda r: r["distractor_slot"])
        resolved = [r for r in rows if r["resolved"]]
        distractors = []
        for r in resolved:
            a = corpus[r["distractor_article_id"]]
            distractors.append({"article_id": a["article_id"], "title": a["title"],
                                "text": a["text"], "published": a["published_utc"],
                                "distractor_type": r["distractor_type"],
                                "distractor_slot": r["distractor_slot"]})

        if not distractors:
            manifest_rows.append({
                "instance_id": iid, "ticker": rec["ticker"],
                "n_distractors": 0, "pool_complete": False,
                "article_order": [], "gt_position": None,
                "type_counts": {}, "note": "no distractor slot could be resolved "
                                           "from the local corpus; no pool rendered",
            })
            continue

        # one fixed order per anchor, reused by C1 and C2
        rng = random.Random("%d:%d" % (args.seed, iid))
        ordered = distractors + [gt_article]
        rng.shuffle(ordered)
        order_ids = [a["article_id"] for a in ordered]
        gt_position = order_ids.index(gt_article["article_id"]) + 1

        masked = []
        for a in ordered:
            t, _ = mask_temporal(a["title"])
            x, _ = mask_temporal(a["text"])
            masked.append({"article_id": a["article_id"], "title": t, "text": x,
                           "published": None})

        question = rec["mcqa_question"].strip()
        prompts = {}
        for cond, articles, ts, show in (
                ("C1", ordered, fmt_ts_timestamped(rec["ts_timestamps"], rec["ts_values"]), True),
                ("C2", masked, fmt_ts_positional(rec["ts_values"]), False)):
            prompts[cond] = PROMPT_TEMPLATE.format(
                TICKER=rec["ticker"], TIME_SERIES=ts,
                NEWS_CONTEXT=fmt_articles(articles, show),
                MCQA_QUESTION=question, RESPONSE_FORMAT=RESPONSE_FORMAT)

        complete = len(distractors) == N_SLOTS
        n_complete += complete
        type_counts = {}
        for d in distractors:
            type_counts[d["distractor_type"]] = type_counts.get(d["distractor_type"], 0) + 1

        for cond, fh in (("C1", f1), ("C2", f2)):
            fh.write(json.dumps({
                "instance_id": iid,
                "condition": cond,
                "ticker": rec["ticker"],
                "answer": rec["mcqa_answer"],
                "n_articles": len(ordered),
                "article_order": order_ids,
                "gt_article_id": gt_article["article_id"],
                "gt_position": gt_position,
                "timestamps_present": cond == "C1",
                "pool_complete": complete,
                "prompt": prompts[cond],
            }, ensure_ascii=False) + "\n")

        manifest_rows.append({
            "instance_id": iid, "ticker": rec["ticker"],
            "n_distractors": len(distractors), "pool_complete": complete,
            "article_order": order_ids, "gt_position": gt_position,
            "type_counts": type_counts,
            "note": "" if complete else
                    "INCOMPLETE: %d/%d distractor slots resolved; not runnable as "
                    "the pilot" % (len(distractors), N_SLOTS),
        })

    f1.close()
    f2.close()
    manifest = {
        "seed": args.seed,
        "n_anchors": len(pilot),
        "n_pools_rendered": sum(1 for r in manifest_rows if r["n_distractors"]),
        "n_pools_complete": n_complete,
        "ready_for_inference": n_complete == len(pilot),
        "target_type_counts": {"temporal_aliasing": 6, "near_time_competing": 2,
                               "future_retrospective": 1,
                               "absence_no_valid_cause": 1},
        "anchors": manifest_rows,
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("rendered %d/%d pools (%d complete) -> %s"
          % (manifest["n_pools_rendered"], len(pilot), n_complete, OUT_DIR))
    print("ready_for_inference: %s" % manifest["ready_for_inference"])


if __name__ == "__main__":
    main()
