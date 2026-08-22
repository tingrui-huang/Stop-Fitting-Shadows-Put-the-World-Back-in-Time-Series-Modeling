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

# The response instruction lives here, once, and is shared by every condition.
# No example answer letter, no request for hidden reasoning.
RESPONSE_FORMAT = """Return exactly one JSON object with the following fields:

{
  "answer": "<A|B|C|D>",
  "confidence": <number between 0 and 1>,
  "rationale": "<brief 1-3 sentence justification>",
  "evidence_articles": [<article indices used as evidence>]
}

Rules:
- "answer" must be A, B, C, or D.
- "confidence" must be a number between 0 and 1.
- "rationale" must be concise and based only on the provided time series and news context.
- "evidence_articles" must list the article indices actually used as evidence; use [] if no article was used.
- Return only the JSON object."""

# One neutral user-prompt template for C0/C1/C2/C3.  Condition-specific content
# enters only through TIME_SERIES and NEWS_CONTEXT; the wording never changes.
PROMPT_TEMPLATE = """Task

Answer the following multiple-choice question using the provided financial time series and news context.

Time Series

Ticker: {TICKER}

{TIME_SERIES}

News Context

{NEWS_CONTEXT}

Question

{MCQA_QUESTION}

Select the single best answer.

{RESPONSE_FORMAT}"""

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


def load_reviewed_pool(path, n_expected, anchor_ids):
    """Read the reviewed per-anchor distractor pool (paper mode).

    Articles are used exactly as approved: the text and the publication
    timestamp come from the pool row, or - when the row carries only an id -
    from the local corpus copy.  Nothing is sampled, reordered or rewritten
    here; the only later step is the single deterministic shuffle shared by
    C1/C2/C3.
    """
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]

    need_corpus = [r for r in rows if not r.get("distractor_content")]
    corpus = {}
    if need_corpus:
        import pandas as pd
        wanted = {r["distractor_article_id"] for r in need_corpus}
        df = pd.read_parquet("data/MTBench_finance_news.parquet",
                             columns=["id", "title", "content", "published_utc",
                                      "tickers", "article_url"])
        for row in df[df["id"].isin(wanted)].itertuples(index=False):
            corpus[row.id] = row

    by_anchor = {}
    for r in rows:
        aid = r["distractor_article_id"]
        if r.get("distractor_content"):
            title, text = r["distractor_title"], r["distractor_content"]
            published = r["distractor_published_utc"]
        else:
            src = corpus.get(aid)
            if src is None:
                raise SystemExit("reviewed pool: article %s for anchor %s is not in "
                                 "the local corpus and carries no text"
                                 % (aid, r["anchor_instance_id"]))
            title, text = src.title, src.content or ""
            published = (r.get("distractor_published_utc")
                         or src.published_utc.strftime("%Y-%m-%d %H:%M:%S"))
        by_anchor.setdefault(r["anchor_instance_id"], []).append({
            "source_id": aid,
            "ticker": r.get("distractor_ticker"),
            "published": published,
            "title": title,
            "text": text,
            "distractor_type": r.get("distractor_type"),
            "event_match_tier": r.get("event_match_tier"),
            "offset_days": r.get("offset_days"),
            "alias_direction": r.get("alias_direction"),
            "provenance": r.get("provenance"),
        })

    problems = []
    for iid in sorted(anchor_ids):
        got = by_anchor.get(iid, [])
        if len(got) != n_expected:
            problems.append("anchor %s has %d approved distractors, expected %d"
                            % (iid, len(got), n_expected))
        if len({a["source_id"] for a in got}) != len(got):
            problems.append("anchor %s has duplicate distractor ids" % iid)
    extra = sorted(set(by_anchor) - set(anchor_ids))
    if extra:
        problems.append("pool covers anchors outside the dataset: %s" % extra)
    if problems:
        raise SystemExit("reviewed distractor pool is not usable:\n  "
                         + "\n  ".join(problems))
    return by_anchor


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="c0_data.json")
    ap.add_argument("--out", default="out")
    ap.add_argument("--seed", default="20240101")
    ap.add_argument("--n-distractors", type=int, default=10)
    ap.add_argument("--distractor-pool", default=None,
                    help="JSONL of REVIEWED per-anchor distractors (paper mode). "
                         "Each line needs anchor_instance_id, distractor_article_id, "
                         "distractor_published_utc and either the article text or a "
                         "corpus id resolvable in data/MTBench_finance_news.parquet. "
                         "Exactly --n-distractors approved rows per anchor are "
                         "required; nothing is resampled. Without this flag the "
                         "legacy sampler is used unchanged.")
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

    if args.distractor_pool and args.mask_question:
        raise SystemExit(
            "--mask-question cannot be combined with --distractor-pool.\n"
            "The paper protocol holds the original MTBench question and answer "
            "options byte-identical across C0/C1/C2/C3; the C2 intervention applies "
            "only to the evidence context (time-series timestamps, article "
            "publication metadata, temporal expressions inside the articles).\n"
            "Re-run without --mask-question.")

    reviewed = load_reviewed_pool(args.distractor_pool, args.n_distractors,
                                  {r["instance_id"] for r in rows})         if args.distractor_pool else None

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

        rng = random.Random("%s:%d" % (args.seed, iid))
        if reviewed is not None:
            # ---- reviewed mode: use exactly the approved articles, no resampling
            distractors = reviewed[iid]
        else:
            # ---- legacy sampling: deterministic per instance, never same ticker
            candidates = sorted(
                (a for a in pool.values()
                 if a["source_id"] != gt["source_id"] and a["ticker"] != ticker),
                key=lambda a: a["source_id"],
            )
            distractors = rng.sample(candidates, args.n_distractors)

        # ---- ONE shuffle, reused verbatim by C1 / C2 / C3
        ordered = distractors + [gt]
        rng.shuffle(ordered)
        order_ids = [a["source_id"] for a in ordered]
        gt_position = order_ids.index(gt["source_id"]) + 1

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

        c3_articles = [a for a in ordered if a["source_id"] != gt["source_id"]]

        news = {
            "c0": fmt_articles([gt], True),
            "c1": fmt_articles(ordered, True),
            "c2": fmt_articles(masked, False),
            "c3": fmt_articles(c3_articles, True),
        }
        ts_block = {"c0": ts_stamped, "c1": ts_stamped,
                    "c2": ts_positional, "c3": ts_stamped}
        gt_id = gt["source_id"]
        orders = {"c0": [gt_id], "c1": order_ids, "c2": order_ids,
                  "c3": [i for i in order_ids if i != gt_id]}

        question = r["mcqa_question"].strip()
        q_masked, _ = mask_temporal(question)

        for cond in ("c0", "c1", "c2", "c3"):
            prompt = PROMPT_TEMPLATE.format(
                TICKER=ticker,
                TIME_SERIES=ts_block[cond],
                NEWS_CONTEXT=news[cond],
                MCQA_QUESTION=(q_masked if cond == "c2" and args.mask_question
                               else question),
                RESPONSE_FORMAT=RESPONSE_FORMAT,
            )
            rec = {
                "instance_id": iid,
                "condition": cond.upper(),
                "ticker": ticker,
                "answer": r["mcqa_answer"],
                "n_articles": len(orders[cond]),
                "article_order": orders[cond],
                "gt_source_id": None if cond == "c3" else gt["source_id"],
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
            "distractors": [
                {"article_id": a["source_id"], "ticker": a["ticker"],
                 "published_utc": a["published"],
                 "distractor_type": a.get("distractor_type"),
                 "event_match_tier": a.get("event_match_tier"),
                 "offset_days": a.get("offset_days"),
                 "alias_direction": a.get("alias_direction"),
                 "provenance": a.get("provenance")}
                for a in ordered if a["source_id"] != gt["source_id"]],
        })

    for f in files.values():
        f.close()
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"seed": args.seed, "n_distractors": args.n_distractors,
                   "mask_question": args.mask_question,
                   "distractor_mode": "reviewed" if reviewed else "legacy",
                   "distractor_pool": args.distractor_pool,
                   "instances": manifest}, f, indent=2)

    print("distractor mode: %s%s"
          % ("reviewed" if reviewed else "legacy (cross-ticker sampling)",
             " from %s" % args.distractor_pool if reviewed else ""))
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
