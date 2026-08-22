"""Simulate C1/C2 prompts carrying the canonical MCQA - without touching the benchmark.

The existing rendered C1/C2 prompts are reused verbatim and only their question
block is swapped for the proposed canonical wording, so any difference the audit
finds is attributable to the MCQA rewrite alone.

Checks: C1 and C2 question/options byte-identical; no absolute calendar anchor
left in the question/options; C1 still carries timestamps in the series and the
news context; C2 still masks them; nothing temporal survives in C2 beyond
deliberate relational language (earlier / later / referenced).

Writes c2_canonical_mcqa_simulation_audit.json.

Usage:  python simulate_canonical_c2.py [--out-dir out_locked50]
"""

import argparse
import json
import os
import re

from verify_conditions import news_block, question_block, split_articles, ts_block

PROPOSALS = "mcqa_temporal_canonicalization_proposals.json"

ABSOLUTE = {
    "year": re.compile(r"\b(?:19|20)\d{2}\b"),
    "iso_date": re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b"),
    "numeric_date": re.compile(r"\b\d{1,2}/\d{1,2}/(?:\d{2}|\d{4})\b"),
    "month_day": re.compile(r"\b(January|February|March|April|May|June|July|August|"
                            r"September|October|November|December)\s+\d{1,2}\b"),
    "month_year": re.compile(r"\b(January|February|March|April|May|June|July|August|"
                             r"September|October|November|December)\s+(?:19|20)\d{2}\b"),
    "quarter_year": re.compile(r"\bQ[1-4]\s*(?:of\s+)?(?:19|20)\d{2}\b", re.I),
    "fiscal_year": re.compile(r"\b(?:fiscal|FY)\s*(?:year\s*)?(?:19|20)\d{2}\b", re.I),
}
RELATIONAL_OK = re.compile(r"\bthe (earlier|later|referenced)\b", re.I)


def swap_question(prompt, canonical):
    head, sep, tail = prompt.partition("\n\nQuestion\n\n")
    body, sep2, rest = tail.partition("\n\nSelect the single best answer.")
    return head + sep + canonical.strip() + sep2 + rest


def merge(dicts):
    out = {}
    for d in dicts:
        for k, v in d.items():
            out.setdefault(k, [])
            for x in v:
                if x not in out[k]:
                    out[k].append(x)
    return {k: v[:5] for k, v in out.items()}


def scan(text):
    return {name: sorted({m.group(0) for m in pattern.finditer(text)})[:5]
            for name, pattern in ABSOLUTE.items()
            if pattern.search(text)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="out_locked50")
    args = ap.parse_args()

    proposals = {p["instance_id"]: p for p in
                 json.load(open(PROPOSALS, encoding="utf-8"))["proposals"]}
    loaded = {}
    for cond in ("c1", "c2"):
        with open(os.path.join(args.out_dir, "%s.jsonl" % cond), encoding="utf-8") as f:
            loaded[cond] = {json.loads(l)["instance_id"]: json.loads(l)
                            for l in f if l.strip()}

    results, failures = [], []
    for iid, prop in sorted(proposals.items()):
        canonical = prop["proposed_question_full"]
        sim = {c: swap_question(loaded[c][iid]["prompt"], canonical) for c in ("c1", "c2")}

        q1 = question_block({"prompt": sim["c1"], "ticker": loaded["c1"][iid]["ticker"]})
        q2 = question_block({"prompt": sim["c2"], "ticker": loaded["c2"][iid]["ticker"]})
        arts1 = split_articles(news_block({"prompt": sim["c1"],
                                           "ticker": loaded["c1"][iid]["ticker"]}))
        arts2 = split_articles(news_block({"prompt": sim["c2"],
                                           "ticker": loaded["c2"][iid]["ticker"]}))
        ts1 = ts_block({"prompt": sim["c1"], "ticker": loaded["c1"][iid]["ticker"]})
        ts2 = ts_block({"prompt": sim["c2"], "ticker": loaded["c2"][iid]["ticker"]})

        row = {
            "instance_id": iid,
            "verdict": prop["canonicalization_verdict"],
            "question_identical_c1_c2": q1 == q2,
            "question_absolute_anchors_left": scan(q2),
            "relational_language_used": bool(RELATIONAL_OK.search(q2)),
            "c1_timeseries_timestamped": bool(
                re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| ", ts1.splitlines()[0])),
            "c2_timeseries_positional": ts2.splitlines()[0].startswith("Position 1 | "),
            "c1_articles_show_published": all(p is not None for p, _, _ in arts1),
            "c2_articles_hide_published": all(p is None for p, _, _ in arts2),
            # scanned per article: joining articles invents cross-boundary matches
            "c2_news_absolute_anchors_left": merge(
                [scan(t) for _, t, _ in arts2] + [scan(c) for _, _, c in arts2]),
            "c1_news_retains_anchors": any(scan(c) for _, _, c in arts1),
        }
        row["clean"] = (row["question_identical_c1_c2"]
                        and not row["question_absolute_anchors_left"]
                        and row["c1_timeseries_timestamped"]
                        and row["c2_timeseries_positional"]
                        and row["c1_articles_show_published"]
                        and row["c2_articles_hide_published"]
                        and not row["c2_news_absolute_anchors_left"])
        if not row["clean"]:
            failures.append(row)
        results.append(row)

    summary = {
        "status": "SIMULATION ONLY - no benchmark file was modified",
        "out_dir_used_for_context": args.out_dir,
        "note": "the article pools here are the legacy build's; only the question "
                "block was swapped, so every difference is attributable to the MCQA "
                "canonicalization",
        "n_simulated": len(results),
        "n_clean": sum(1 for r in results if r["clean"]),
        "n_with_findings": len(failures),
        "checks": {
            "question_identical_c1_c2": all(r["question_identical_c1_c2"] for r in results),
            "no_absolute_anchor_in_question": all(
                not r["question_absolute_anchors_left"] for r in results),
            "c1_keeps_timestamps": all(r["c1_timeseries_timestamped"]
                                       and r["c1_articles_show_published"] for r in results),
            "c2_masks_timestamps": all(r["c2_timeseries_positional"]
                                       and r["c2_articles_hide_published"] for r in results),
            "c2_news_free_of_absolute_anchors": all(
                not r["c2_news_absolute_anchors_left"] for r in results),
            "c1_news_still_carries_anchors": sum(1 for r in results
                                                 if r["c1_news_retains_anchors"]),
        },
        "instances": results,
        "findings": failures,
    }
    with open("c2_canonical_mcqa_simulation_audit.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("simulated %d instances | clean: %d | with findings: %d"
          % (len(results), summary["n_clean"], len(failures)))
    for k, v in summary["checks"].items():
        print("  %-38s %s" % (k, v))
    for r in failures[:10]:
        print("  FINDING %d: %s" % (r["instance_id"],
                                    {k: v for k, v in r.items()
                                     if k.endswith("_left") and v}))
    print("wrote c2_canonical_mcqa_simulation_audit.json")


if __name__ == "__main__":
    main()
