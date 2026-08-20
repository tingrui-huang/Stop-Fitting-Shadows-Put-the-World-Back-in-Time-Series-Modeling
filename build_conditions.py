"""Build prompt datasets for conditions C0, C1, C2, C3 from c0_data.json.

C0 = timestamped TS + timestamped GT article
C1 = timestamped TS + GT article + 10 distractors, all timestamped, shuffled once
C2 = same instance as C1 with all temporal information removed
     (TS -> ordinal positions, no publication timestamps, article text masked)
C3 = timestamped TS + the same 10 distractors in the same relative order, GT removed

Cross-condition invariance (ticker, TS values, question, options, article text,
distractor identity, article order) is enforced by construction and re-checked by
verify_conditions.py.

Usage:  python build_conditions.py [--seed 20240101] [--out out] [--n-distractors 10]
"""

import argparse
import ast
import datetime as dt
import hashlib
import json
import os
import random

from temporal_mask import mask_temporal

PROMPT_TEMPLATE = """You are given a financial time series and a set of financial news articles.
Your task is to answer the multiple-choice question using only the information provided below.

Time Series
Ticker: {TICKER}
{TIME_SERIES}

News Context
{NEWS_CONTEXT}

Question
{MCQA_QUESTION}

Select the single best answer.
Return only the following JSON object:

```json
{{"answer": "A"}}
```

where "A" must be one of "A", "B", "C", or "D"."""

ARTICLE_SEP = "\n\n"


# --------------------------------------------------------------------------- #
# parsing / formatting
# --------------------------------------------------------------------------- #
def parse_article(raw):
    """Split the stored 'Title: ... [newline] Content: [...]' blob into (title, body)."""
    title, _, body = raw.partition(" \n Content: ")
    title = title[len("Title: "):].strip() if title.startswith("Title: ") else title.strip()
    paragraphs = ast.literal_eval(body)
    text = "\n".join(p.strip() for p in paragraphs if p and p.strip())
    return title, text


def fmt_ts_timestamped(timestamps, values):
    lines = []
    for t, v in zip(timestamps, values):
        stamp = dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        lines.append("%s | %.2f" % (stamp, v))
    return "\n".join(lines)


def fmt_ts_positional(values):
    return "\n".join("Position %d | %.2f" % (i + 1, v) for i, v in enumerate(values))


def fmt_articles(articles, show_published):
    """articles: list of dicts with title/text/published (already masked for C2)."""
    blocks = []
    for i, a in enumerate(articles, 1):
        head = ["Article %d" % i]
        if show_published:
            head.append("Published: %s" % a["published"])
        head.append("Title: %s" % a["title"])
        head.append("Content:")
        blocks.append("\n".join(head) + "\n" + a["text"])
    return ARTICLE_SEP.join(blocks)


def sha(obj):
    return hashlib.sha256(repr(obj).encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="c0_data.json")
    ap.add_argument("--out", default="out")
    ap.add_argument("--seed", default="20240101")
    ap.add_argument("--n-distractors", type=int, default=10)
    ap.add_argument("--mask-question", action="store_true",
                    help="also temporally mask the MCQA question in C2. OFF by "
                         "default: the spec pins the question as invariant across "
                         "conditions. 14/50 questions name a year, quarter or month, "
                         "so with the flag off those instances still leak absolute "
                         "time into C2 (see question_has_temporal_tokens in the "
                         "manifest to filter them out at analysis time).")
    args = ap.parse_args()

    with open(args.data, encoding="utf-8") as f:
        rows = json.load(f)

    # canonical article record per instance (this is also the distractor pool)
    pool = {}
    for r in rows:
        title, text = parse_article(r["gt_article_text"])
        pool[r["instance_id"]] = {
            "source_id": r["instance_id"],
            "ticker": r["ticker"],
            "published": r["gt_published_utc"],
            "title": title,
            "text": text,
        }

    os.makedirs(args.out, exist_ok=True)
    files = {c: open(os.path.join(args.out, "%s.jsonl" % c), "w", encoding="utf-8")
             for c in ("c0", "c1", "c2", "c3")}
    manifest = []

    for r in rows:
        iid, ticker = r["instance_id"], r["ticker"]
        gt = pool[iid]

        # ---- distractor sampling: deterministic per instance, never same ticker
        rng = random.Random("%s:%d" % (args.seed, iid))
        candidates = sorted(
            (a for a in pool.values()
             if a["source_id"] != iid and a["ticker"] != ticker),
            key=lambda a: a["source_id"],
        )
        distractors = rng.sample(candidates, args.n_distractors)

        # ---- ONE shuffle, reused verbatim by C1 / C2 / C3
        ordered = distractors + [gt]
        rng.shuffle(ordered)
        order_ids = [a["source_id"] for a in ordered]
        gt_position = order_ids.index(iid) + 1

        ts_stamped = fmt_ts_timestamped(r["ts_timestamps"], r["ts_values"])
        ts_positional = fmt_ts_positional(r["ts_values"])

        # ---- C2 articles: same articles, same order, temporal info masked only
        n_masked = 0
        masked = []
        for a in ordered:
            t, k1 = mask_temporal(a["title"])
            x, k2 = mask_temporal(a["text"])
            n_masked += k1 + k2
            masked.append({"source_id": a["source_id"], "title": t,
                           "text": x, "published": None})

        c3_articles = [a for a in ordered if a["source_id"] != iid]

        news = {
            "c0": fmt_articles([gt], True),
            "c1": fmt_articles(ordered, True),
            "c2": fmt_articles(masked, False),
            "c3": fmt_articles(c3_articles, True),
        }
        ts_block = {"c0": ts_stamped, "c1": ts_stamped,
                    "c2": ts_positional, "c3": ts_stamped}
        orders = {"c0": [iid], "c1": order_ids, "c2": order_ids,
                  "c3": [i for i in order_ids if i != iid]}

        question = r["mcqa_question"].strip()
        q_masked, _ = mask_temporal(question)

        for cond in ("c0", "c1", "c2", "c3"):
            prompt = PROMPT_TEMPLATE.format(
                TICKER=ticker,
                TIME_SERIES=ts_block[cond],
                NEWS_CONTEXT=news[cond],
                MCQA_QUESTION=(q_masked if cond == "c2" and args.mask_question
                               else question),
            )
            rec = {
                "instance_id": iid,
                "condition": cond.upper(),
                "ticker": ticker,
                "answer": r["mcqa_answer"],
                "n_articles": len(orders[cond]),
                "article_order": orders[cond],
                "gt_source_id": None if cond == "c3" else iid,
                "gt_position": (1 if cond == "c0" else
                                gt_position if cond in ("c1", "c2") else None),
                "timestamps_present": cond != "c2",
                "prompt": prompt,
            }
            files[cond].write(json.dumps(rec, ensure_ascii=False) + "\n")
            if iid == rows[0]["instance_id"]:      # readable sample for eyeballing
                ex_dir = os.path.join(args.out, "examples")
                os.makedirs(ex_dir, exist_ok=True)
                with open(os.path.join(ex_dir, "instance_%d_%s.txt" % (iid, cond)),
                          "w", encoding="utf-8") as g:
                    g.write(prompt)

        manifest.append({
            "instance_id": iid,
            "ticker": ticker,
            "answer": r["mcqa_answer"],
            "n_points": len(r["ts_values"]),
            "gt_published_utc": r["gt_published_utc"],
            "article_order": order_ids,
            "gt_position": gt_position,
            "n_temporal_masks_c2": n_masked,
            "question_has_temporal_tokens": q_masked != question,
            "ts_value_hash": sha(["%.2f" % v for v in r["ts_values"]]),
            "question_hash": sha(r["mcqa_question"]),
            "article_pool_hash": sha(order_ids),
        })

    for f in files.values():
        f.close()
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"seed": args.seed, "n_distractors": args.n_distractors,
                   "mask_question": args.mask_question,
                   "instances": manifest}, f, indent=2)

    print("wrote %d instances x 4 conditions to %s/" % (len(rows), args.out))
    print("mean temporal masks per C2 instance: %.1f"
          % (sum(m["n_temporal_masks_c2"] for m in manifest) / len(manifest)))
    print("instances whose question names a year/quarter/month: %d/%d%s"
          % (sum(m["question_has_temporal_tokens"] for m in manifest), len(manifest),
             " (masked in C2)" if args.mask_question else " (NOT masked; --mask-question is off)"))
    print("GT position distribution in C1/C2:",
          sorted(__import__("collections").Counter(
              m["gt_position"] for m in manifest).items()))


if __name__ == "__main__":
    main()
