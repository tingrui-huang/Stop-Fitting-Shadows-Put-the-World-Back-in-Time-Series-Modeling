"""Structural checks for the pilot C1/C2 pools.

Checks are re-derived from the rendered prompts, like verify_conditions.py.
Taxonomy and pool-size checks apply only to complete pools (GT + 10 slots);
their status is reported either way so an incomplete pilot cannot be mistaken
for a runnable one.

Usage:  python verify_pilot10.py
"""

import json
import os
import re
import sys

from build_final_hard50 import load_json
from news_corpus import load_corpus
from temporal_mask import mask_temporal
from verify_conditions import news_block, question_block, split_articles, ts_block

OUT_DIR = os.path.join("out", "pilot10")
FAILURES = []


def check(name, ok, detail=""):
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  <- " + detail))
    if not ok:
        FAILURES.append(name)


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return {json.loads(l)["instance_id"]: json.loads(l) for l in f if l.strip()}


def main():
    c1 = load_jsonl(os.path.join(OUT_DIR, "c1.jsonl"))
    c2 = load_jsonl(os.path.join(OUT_DIR, "c2.jsonl"))
    manifest = json.load(open(os.path.join(OUT_DIR, "manifest.json"), encoding="utf-8"))
    slots = [json.loads(l) for l in
             open("pilot10_distractors.jsonl", encoding="utf-8") if l.strip()]
    pilot = {r["instance_id"]: r for r in load_json("pilot10_data.json")}
    corpus = load_corpus(load_json)
    ids = sorted(c1)

    check("10 pilot anchors selected", len(pilot) == 10, "%d" % len(pilot))
    check("100 distractor slots enumerated (10 x 10)", len(slots) == 100,
          "%d" % len(slots))
    check("C1 and C2 cover the same anchors", sorted(c1) == sorted(c2))

    art1 = {i: split_articles(news_block(c1[i])) for i in ids}
    art2 = {i: split_articles(news_block(c2[i])) for i in ids}

    check("same article identities and order in C1 vs C2",
          all(c1[i]["article_order"] == c2[i]["article_order"]
              and len(art1[i]) == len(art2[i]) == len(c1[i]["article_order"])
              for i in ids))
    check("C1 -> C2 differs only by deterministic temporal masking",
          all(all((mask_temporal(t)[0], mask_temporal(x)[0]) == (t2, x2)
                  for (_, t, x), (_, t2, x2) in zip(art1[i], art2[i])) for i in ids))
    check("C2 shows no publication timestamps",
          all(all(p is None for p, _, _ in art2[i]) for i in ids))
    check("C2 news context has no year / ISO date / Q-number",
          all(not re.search(r"\b(?:19|20)\d{2}\b|\bQ[1-4]\b", news_block(c2[i]))
              for i in ids))
    check("same MCQA question and options in C1 vs C2",
          all(question_block(c1[i]) == question_block(c2[i]) for i in ids))
    check("same gold answer and ticker in C1 vs C2",
          all(c1[i]["answer"] == c2[i]["answer"] and c1[i]["ticker"] == c2[i]["ticker"]
              for i in ids))

    def values(block):
        return [ln.split(" | ")[1] for ln in block.splitlines()]

    check("identical time-series values in C1 vs C2",
          all(values(ts_block(c1[i])) == values(ts_block(c2[i])) for i in ids))
    check("C2 time series uses ordinal positions only",
          all(all(ln.startswith("Position %d | " % (k + 1))
                  for k, ln in enumerate(ts_block(c2[i]).splitlines())) for i in ids))
    check("C1 keeps real timestamps",
          all(re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| ",
                       ts_block(c1[i]).splitlines()[0]) for i in ids))

    check("GT article appears exactly once per pool",
          all(c1[i]["article_order"].count(c1[i]["gt_article_id"]) == 1 for i in ids))
    check("no duplicate article inside a pool",
          all(len(set(c1[i]["article_order"])) == len(c1[i]["article_order"])
              for i in ids))
    check("no condition-specific hint wording in the prompts",
          not any(re.search(r"distractor|ground[- ]truth|timestamps were removed|"
                            r"find the correct article", c1[i]["prompt"] + c2[i]["prompt"],
                            re.I) for i in ids))

    resolved = [s for s in slots if s["resolved"]]
    check("every resolved distractor traces to a real corpus article",
          all(s["distractor_article_id"] in corpus for s in resolved))
    check("no resolved distractor is the anchor's GT article",
          all(s["distractor_article_id"] != s["gt_article_id"] for s in resolved))
    check("resolved distractors keep the corpus publication timestamp",
          all(corpus[s["distractor_article_id"]]["published_utc"]
              == s["distractor_published_utc"] for s in resolved))
    check("no fabricated article: every rendered article id is GT or corpus",
          all(a == c1[i]["gt_article_id"] or a in corpus
              for i in ids for a in c1[i]["article_order"]))

    complete = [r for r in manifest["anchors"] if r["pool_complete"]]
    check("distractor-type counts are 6/2/1/1 in every complete pool",
          all(r["type_counts"] == manifest["target_type_counts"] for r in complete))
    check("complete pools hold GT + 10 distractors",
          all(len(art1[r["instance_id"]]) == 11 for r in complete))

    n_res = len(resolved)
    print("\nresolved distractor slots: %d/100" % n_res)
    print("pools rendered: %d, complete: %d, ready_for_inference: %s"
          % (manifest["n_pools_rendered"], manifest["n_pools_complete"],
             manifest["ready_for_inference"]))
    if not manifest["ready_for_inference"]:
        print("NOT RUNNABLE: the pilot needs 10/10 slots per anchor; see "
              "pilot10_distractor_manifest.json for the unresolved slots")
    if FAILURES:
        print("FAILED: %s" % ", ".join(FAILURES))
        sys.exit(1)
    print("all structural checks passed")


if __name__ == "__main__":
    main()
