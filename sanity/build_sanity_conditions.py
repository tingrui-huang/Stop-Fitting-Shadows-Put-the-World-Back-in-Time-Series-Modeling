"""PHASE 0 - build and freeze the six sanity-check conditions.

Diagnostic only.  This script reads the frozen benchmark and the frozen
rendered C0/C1/C2 prompts, and writes new prompts under sanity/ only.  It never
opens a model output: condition construction here is blind to which items
Sonnet answered correctly.

    S1_QO_ONLY                        question + options, nothing else
    S2_GT_TEXT_ONLY                   GT article (as rendered in C0) + question
    S3_POOL_TEXT_ONLY                 C1 minus the time series
    S4_TS_ONLY                        timestamped TS + question, no news
    S5_C2_QO_DATE_MASK                C2 with absolute dates masked in the MCQA
    S6_C1_METADATA_TIMESTAMP_SHUFFLE  C1 with article timestamps deranged

Every prompt is assembled from spans copied verbatim out of the frozen files,
so article text, time-series values and MCQA wording cannot drift.

Usage:  python sanity/build_sanity_conditions.py
"""

import hashlib
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build_conditions import RESPONSE_FORMAT  # noqa: E402
from temporal_mask import mask_temporal  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "sanity")
FROZEN = {
    "final50_paper_data.json": None,
    "final50_paper_manifest.json": None,
    "final50_reviewed_pool.jsonl": None,
    "out_paper50_reviewed/c0.jsonl": None,
    "out_paper50_reviewed/c1.jsonl": None,
    "out_paper50_reviewed/c2.jsonl": None,
    "out_paper50_reviewed/c3.jsonl": None,
    "out_paper50_reviewed/manifest.json": None,
    "prompts/system.txt": None,
}
SHUFFLE_SEED = 20260823

# Templates.  The response block is imported from the main builder so it stays
# byte-identical; only the Task sentence and which sections appear can differ,
# because a condition cannot promise evidence it does not supply.
T_QO = """Task

Answer the following multiple-choice question.

Question

{MCQA_QUESTION}

Select the single best answer.

{RESPONSE_FORMAT}"""

T_NEWS = """Task

Answer the following multiple-choice question using the provided news context.

News Context

{NEWS_CONTEXT}

Question

{MCQA_QUESTION}

Select the single best answer.

{RESPONSE_FORMAT}"""

T_TS = """Task

Answer the following multiple-choice question using the provided financial time series.

Time Series

Ticker: {TICKER}

{TIME_SERIES}

Question

{MCQA_QUESTION}

Select the single best answer.

{RESPONSE_FORMAT}"""


def md5(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def jsonl(path):
    with open(path, encoding="utf-8") as f:
        return {json.loads(l)["instance_id"]: json.loads(l) for l in f if l.strip()}


# ---- span extraction from the frozen prompts ------------------------------
def section(prompt, start, end=None):
    i = prompt.index(start) + len(start)
    j = prompt.index(end, i) if end else len(prompt)
    return prompt[i:j].strip("\n")


def ts_block(rec):
    return section(rec["prompt"], "\nTicker: %s\n" % rec["ticker"],
                   "\n\nNews Context\n")


def news_block(rec):
    return section(rec["prompt"], "\n\nNews Context\n", "\n\nQuestion\n")


def question_block(rec):
    return section(rec["prompt"], "\n\nQuestion\n",
                   "\n\nSelect the single best answer.")


PUBLISHED = re.compile(r"^Published: (.+)$", re.M)


def derange(n, rng):
    """A permutation of range(n) with no fixed point."""
    while True:
        p = list(range(n))
        rng.shuffle(p)
        if all(p[i] != i for i in range(n)):
            return p


def shuffle_timestamps(news, rng):
    """Permute only the 'Published:' lines of a rendered news block."""
    stamps = PUBLISHED.findall(news)
    n = len(stamps)
    for _ in range(200):
        perm = derange(n, rng)
        new = [stamps[perm[i]] for i in range(n)]
        if all(new[i] != stamps[i] for i in range(n)):
            break
    else:
        raise SystemExit("could not derange timestamps (duplicate values?)")
    it = iter(new)
    out = PUBLISHED.sub(lambda m: "Published: " + next(it), news)
    return out, perm, stamps, new


def main():
    os.makedirs(OUT, exist_ok=True)
    for k in FROZEN:
        FROZEN[k] = md5(os.path.join(ROOT, k))

    data = {r["instance_id"]: r for r in json.load(
        open(os.path.join(ROOT, "final50_paper_data.json"), encoding="utf-8"))}
    man = {m["instance_id"]: m for m in json.load(
        open(os.path.join(ROOT, "out_paper50_reviewed/manifest.json"),
             encoding="utf-8"))["instances"]}
    c0 = jsonl(os.path.join(ROOT, "out_paper50_reviewed/c0.jsonl"))
    c1 = jsonl(os.path.join(ROOT, "out_paper50_reviewed/c1.jsonl"))
    c2 = jsonl(os.path.join(ROOT, "out_paper50_reviewed/c2.jsonl"))
    ids = sorted(c1)

    rng = random.Random(SHUFFLE_SEED)
    conds = {k: [] for k in ("S1_QO_ONLY", "S2_GT_TEXT_ONLY", "S3_POOL_TEXT_ONLY",
                             "S4_TS_ONLY", "S5_C2_QO_DATE_MASK",
                             "S6_C1_METADATA_TIMESTAMP_SHUFFLE")}
    s5_changes, s6_perms = {}, {}

    for i in ids:
        q1 = question_block(c1[i])
        q2 = question_block(c2[i])
        assert q1 == q2 == question_block(c0[i]), i
        ticker, gold = c1[i]["ticker"], c1[i]["answer"]
        base = {"instance_id": i, "ticker": ticker, "answer": gold}

        # ---- S1 ----------------------------------------------------------
        conds["S1_QO_ONLY"].append(dict(
            base, condition="S1_QO_ONLY",
            prompt=T_QO.format(MCQA_QUESTION=q1, RESPONSE_FORMAT=RESPONSE_FORMAT)))

        # ---- S2 : GT article exactly as C0 renders it ----------------------
        conds["S2_GT_TEXT_ONLY"].append(dict(
            base, condition="S2_GT_TEXT_ONLY",
            prompt=T_NEWS.format(NEWS_CONTEXT=news_block(c0[i]),
                                 MCQA_QUESTION=q1,
                                 RESPONSE_FORMAT=RESPONSE_FORMAT)))

        # ---- S3 : C1's pool, C1's order, no time series --------------------
        conds["S3_POOL_TEXT_ONLY"].append(dict(
            base, condition="S3_POOL_TEXT_ONLY",
            article_order=c1[i]["article_order"], gt_position=c1[i]["gt_position"],
            prompt=T_NEWS.format(NEWS_CONTEXT=news_block(c1[i]),
                                 MCQA_QUESTION=q1,
                                 RESPONSE_FORMAT=RESPONSE_FORMAT)))

        # ---- S4 : timestamped TS, no news ---------------------------------
        conds["S4_TS_ONLY"].append(dict(
            base, condition="S4_TS_ONLY",
            prompt=T_TS.format(TICKER=ticker, TIME_SERIES=ts_block(c1[i]),
                               MCQA_QUESTION=q1,
                               RESPONSE_FORMAT=RESPONSE_FORMAT)))

        # ---- S5 : C2 with absolute dates masked inside the MCQA ------------
        masked_q, n_sub = mask_temporal(q2)
        prompt5 = c2[i]["prompt"].replace(q2, masked_q, 1) if n_sub else \
            c2[i]["prompt"]
        conds["S5_C2_QO_DATE_MASK"].append(dict(
            base, condition="S5_C2_QO_DATE_MASK", n_question_masks=n_sub,
            question_changed=bool(n_sub), prompt=prompt5))
        if n_sub:
            s5_changes[i] = {"n_substitutions": n_sub,
                             "question_before": q2, "question_after": masked_q}

        # ---- S6 : C1 with the article timestamps deranged ------------------
        news1 = news_block(c1[i])
        news6, perm, before, after = shuffle_timestamps(news1, rng)
        prompt6 = c1[i]["prompt"].replace(news1, news6, 1)
        conds["S6_C1_METADATA_TIMESTAMP_SHUFFLE"].append(dict(
            base, condition="S6_C1_METADATA_TIMESTAMP_SHUFFLE",
            article_order=c1[i]["article_order"], gt_position=c1[i]["gt_position"],
            timestamp_permutation=perm, prompt=prompt6))
        s6_perms[i] = {"permutation": perm, "timestamps_before": before,
                       "timestamps_after": after,
                       "gt_position": c1[i]["gt_position"],
                       "gt_timestamp_before": before[c1[i]["gt_position"] - 1],
                       "gt_timestamp_after": after[c1[i]["gt_position"] - 1]}

    manifest = {
        "purpose": "sanity-check ablations for the timestamp intervention; "
                   "diagnostic only, not part of C0-C3",
        "built_blind": "prompts were constructed and hashed before any model "
                       "output was loaded; no C0-C3 result file is read by this "
                       "script",
        "frozen_inputs_md5": FROZEN,
        "shuffle_seed": SHUFFLE_SEED,
        "response_format_sha256": sha(RESPONSE_FORMAT),
        "templates": {"S1_QO_ONLY": sha(T_QO), "S2_GT_TEXT_ONLY": sha(T_NEWS),
                      "S3_POOL_TEXT_ONLY": sha(T_NEWS),
                      "S4_TS_ONLY": sha(T_TS),
                      "S5_C2_QO_DATE_MASK": "frozen C2 prompt, MCQA span replaced",
                      "S6_C1_METADATA_TIMESTAMP_SHUFFLE":
                          "frozen C1 prompt, Published: lines permuted"},
        "template_note": "S1/S2/S4 cannot use the C0-C3 Task sentence verbatim "
                         "because it promises a time series and a news context "
                         "that those ablations deliberately withhold; the "
                         "response-format block is byte-identical to the main "
                         "experiment in all six conditions",
        "conditions": {},
        "s5_question_changes": s5_changes,
        "s6_permutations": s6_perms,
    }
    for name, rows in conds.items():
        rows.sort(key=lambda r: r["instance_id"])
        path = os.path.join(OUT, "%s.jsonl" % name.lower())
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        manifest["conditions"][name] = {
            "file": os.path.relpath(path, ROOT).replace("\\", "/"),
            "n_instances": len(rows),
            "prompt_sha256": {str(r["instance_id"]): sha(r["prompt"])
                              for r in rows},
            "median_prompt_chars": sorted(len(r["prompt"]) for r in rows)[len(rows) // 2],
        }
        print("%-34s %d prompts -> %s" % (name, len(rows), path))

    mpath = os.path.join(OUT, "sanity_conditions_manifest.json")
    with open(mpath, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print("\nwrote %s" % mpath)
    print("instances with an absolute date masked in the MCQA (S5): %d/%d"
          % (len(s5_changes), len(ids)))


if __name__ == "__main__":
    main()
