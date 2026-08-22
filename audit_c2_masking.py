"""Audit the C2 temporal masker against the REAL pilot articles.

For every ground-truth and candidate distractor article this records which
temporal expressions the masker found, what they became, and whether any
absolute temporal marker survives.  The masker itself is not modified.

Preserved on purpose (checked, not masked): non-temporal wording, ticker and
company identity, article identity/order, and time-series values - the anonymisation
protocol is a separate question and is reported, not applied here.

Writes pilot10_c2_mask_audit.json.

Usage:  python audit_c2_masking.py
"""

import argparse
import collections
import json
import re

import pandas as pd

from build_final_hard50 import load_json
from news_corpus import parse_article
from temporal_mask import RULES, mask_temporal

CORPUS = "data/MTBench_finance_news.parquet"

# Absolute markers that must NOT survive masking.
RESIDUAL = {
    "year": re.compile(r"\b(?:19|20)\d{2}\b"),
    "quarter": re.compile(r"\bQ[1-4]\b", re.I),
    "iso_date": re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b"),
    "numeric_date": re.compile(r"\b\d{1,2}/\d{1,2}/(?:\d{2}|\d{4})\b"),
    "month_name": re.compile(r"\b(January|February|March|April|June|July|August|"
                             r"September|October|November|December|Jan\.|Feb\.|Mar\.|"
                             r"Apr\.|Jun\.|Jul\.|Aug\.|Sept?\.|Oct\.|Nov\.|Dec\.)\b"),
    "weekday": re.compile(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b"),
}
# Not date-revealing; reported so the decision is visible rather than silent.
TIME_OF_DAY = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\s*(a\.m\.|p\.m\.|AM|PM|ET|EST|UTC)?", re.I)


def detect(text):
    """Replay the masker's ordered rules, recording what each one matched."""
    found, work = [], text
    for pattern, token in RULES:
        for m in pattern.finditer(work):
            found.append({"expression": m.group(0), "masked_as": token})
        work = pattern.sub(token, work)
    return found, work


def audit_article(article_id, kind, title, content):
    det_title, masked_title = detect(title)
    det_body, masked_body = detect(content)
    residual = {}
    for name, pattern in RESIDUAL.items():
        hits = pattern.findall(masked_title + " " + masked_body)
        if hits:
            residual[name] = sorted({h if isinstance(h, str) else h[0] for h in hits})[:5]
    counts = collections.Counter(d["masked_as"] for d in det_title + det_body)
    return {
        "article_id": article_id,
        "role": kind,
        "title_original": title,
        "title_masked": masked_title,
        "n_expressions_detected": len(det_title) + len(det_body),
        "expressions_by_token": dict(counts),
        "detected_examples": (det_title + det_body)[:12],
        "body_masked_preview": masked_body[:400],
        "residual_temporal_leakage": residual,
        "leak_free": not residual,
        "time_of_day_kept": sorted(set(m.group(0).strip() for m in
                                       TIME_OF_DAY.finditer(masked_body)))[:5],
        "publication_timestamp_shown_in_c2": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", default="pilot10_final_data.json")
    ap.add_argument("--candidates", default="pilot10_review_candidates.jsonl")
    ap.add_argument("--out", default="pilot10_review_mask_audit.json")
    args = ap.parse_args()

    pilot = load_json(args.pilot)
    cands = [json.loads(l) for l in
             open(args.candidates, encoding="utf-8") if l.strip()]
    wanted = {c["distractor_article_id"] for c in cands}
    df = pd.read_parquet(CORPUS, columns=["id", "title", "content"])
    corpus = {r["id"]: r for _, r in df[df["id"].isin(wanted)].iterrows()}

    articles = []
    for rec in pilot:
        title, text = parse_article(rec["gt_article_text"])
        articles.append(("anchor:%d" % rec["instance_id"], "ground_truth", title, text,
                         rec["instance_id"]))
    for c in cands:
        row = corpus.get(c["distractor_article_id"])
        if row is None:
            continue
        articles.append((c["distractor_article_id"], c["distractor_type"],
                         row["title"], row["content"] or "", c["anchor_instance_id"]))

    audits = []
    for aid, kind, title, content, anchor in articles:
        a = audit_article(aid, kind, title, content)
        a["anchor_instance_id"] = anchor
        audits.append(a)

    leaky = [a for a in audits if not a["leak_free"]]
    summary = {
        "masker": "temporal_mask.py (deterministic ordered regex, unmodified)",
        "tokens": ["[DATE]", "[YEAR]", "[QUARTER]"],
        "n_articles_audited": len(audits),
        "n_ground_truth": sum(1 for a in audits if a["role"] == "ground_truth"),
        "n_distractor_candidates": sum(1 for a in audits if a["role"] != "ground_truth"),
        "n_leak_free": len(audits) - len(leaky),
        "n_with_residual_leakage": len(leaky),
        "residual_leakage_by_kind": dict(collections.Counter(
            k for a in leaky for k in a["residual_temporal_leakage"])),
        "expressions_masked_total": sum(a["n_expressions_detected"] for a in audits),
        "preserved_by_design": [
            "non-temporal wording", "ticker and company identity (no anonymisation "
            "is applied by the current code - reported separately)",
            "article identity and order", "time-series numerical values",
            "clock times such as '4:00 p.m. ET' (not date-revealing)"],
        "articles": audits,
    }
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("audited %d articles (%d GT + %d candidates)"
          % (len(audits), summary["n_ground_truth"], summary["n_distractor_candidates"]))
    print("temporal expressions masked: %d" % summary["expressions_masked_total"])
    print("leak-free: %d | with residual leakage: %d"
          % (summary["n_leak_free"], summary["n_with_residual_leakage"]))
    for a in leaky[:10]:
        print("   LEAK %s (anchor %s): %s" % (a["article_id"], a["anchor_instance_id"],
                                              a["residual_temporal_leakage"]))
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
