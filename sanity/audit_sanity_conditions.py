"""PHASE 1 - static cue audit, S5 masking audit and S6 shuffle verification.

Runs before any inference and reads no model output.  Three jobs:

  cue audit      what information sits in the MCQA itself, outside the evidence
                 context that C2 masks
  S5 audit       every C2 -> S5 change must be a genuine absolute calendar or
                 world-index expression, and must leave relational words
                 (before/after/following) and non-temporal numbers alone
  S6 audit       the derangement must change only the Published: lines, keep the
                 article ids, order and timestamp multiset, and have no fixed
                 point

Writes results/sanity/sanity_cue_audit.json.

Usage:  python sanity/audit_sanity_conditions.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build_sanity_conditions import (jsonl, news_block, question_block,  # noqa
                                     section, ts_block)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "results", "sanity")

MASK_TOKENS = ("[DATE]", "[YEAR]", "[QUARTER]")
RELATIONAL = re.compile(
    r"\b(before|after|following|subsequent(?:ly)?|prior|later|since|"
    r"shortly|immediately|preceding|ahead of|leading up to)\b", re.I)

CUES = {
    "absolute_date": re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+\d{1,2}\b|\b\d{4}-\d{2}-\d{2}\b", re.I),
    "year": re.compile(r"\b(?:19|20)\d{2}\b"),
    "quarter": re.compile(r"\bQ[1-4]\b|\b(first|second|third|fourth)[\s-]quarter\b",
                          re.I),
    "fiscal_year": re.compile(r"\bfiscal\s+(?:year\s+)?(?:19|20)?\d{2,4}\b", re.I),
    "publication_reference": re.compile(
        r"\b(news publication|publication of the news|news was published|"
        r"press time|after the news|following the news|post-news|"
        r"the announcement|earnings report|news release)\b", re.I),
    "relational_temporal_language": RELATIONAL,
    "named_price_level": re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?"),
    "percentage": re.compile(r"\d+(?:\.\d+)?\s?%"),
    "ticker_symbol": None,      # filled per instance
    "company_name_like": re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"),
}


def strip_masks(text):
    for t in MASK_TOKENS:
        text = text.replace(t, "")
    return text


def audit_s5(c2, s5, ids):
    """Every change must be an absolute temporal expression -> mask token."""
    per, flags = [], []
    for i in ids:
        before, after = question_block(c2[i]), None
        p = s5[i]["prompt"]
        after = section(p, "\n\nQuestion\n", "\n\nSelect the single best answer.")
        if before == after:
            per.append({"instance_id": i, "changed": False, "n_spans": 0,
                        "spans": []})
            continue
        # align on the mask tokens: reconstruct which source spans vanished
        spans = []
        bi = 0
        for m in re.finditer(r"\[(?:DATE|YEAR|QUARTER)\]", after):
            prefix = after[:m.start()]
            core = strip_masks(prefix)
            # the source text that produced `core` is the same length prefix of
            # `before` after removing already-consumed spans
            spans.append(m.group(0))
        removed = _removed_spans(before, after)
        rel_before = len(RELATIONAL.findall(before))
        rel_after = len(RELATIONAL.findall(after))
        prices_before = CUES["named_price_level"].findall(before)
        prices_after = CUES["named_price_level"].findall(after)
        pct_before = CUES["percentage"].findall(before)
        pct_after = CUES["percentage"].findall(after)
        rec = {
            "instance_id": i, "changed": True, "n_spans": len(removed),
            "spans": removed,
            "relational_words_before": rel_before,
            "relational_words_after": rel_after,
            "relational_words_preserved": rel_before == rel_after,
            "price_levels_preserved": prices_before == prices_after,
            "percentages_preserved": pct_before == pct_after,
            "question_before": before, "question_after": after,
        }
        bad = []
        if not rec["relational_words_preserved"]:
            bad.append("a relational word (before/after/following/...) changed")
        if not rec["price_levels_preserved"]:
            bad.append("a named price level changed")
        if not rec["percentages_preserved"]:
            bad.append("a percentage changed")
        for span, tok in removed:
            if not _is_absolute_temporal(span):
                bad.append("removed span %r is not an absolute temporal "
                           "expression" % span)
            if re.fullmatch(r"(?:19|20)\d{2}", span.strip()):
                ctx = _context(before, span)
                if re.search(r"[\d.,]\s*$", ctx[0]) or re.match(r"\.\d", ctx[1]):
                    bad.append("4-digit token %r masked as a year inside a "
                               "numeric context" % span)
        rec["flags"] = bad
        if bad:
            flags.append(rec)
        per.append(rec)
    return per, flags


def _removed_spans(before, after):
    """Return [(source_span, mask_token)] by walking both strings together."""
    out = []
    bi = ai = 0
    while ai < len(after):
        m = re.compile(r"\[(?:DATE|YEAR|QUARTER)\]").match(after, ai)
        if m:
            # the mask replaced some span of `before` starting at bi; find the
            # next literal anchor after the token and match it in `before`
            tail = after[m.end():m.end() + 24]
            anchor = re.split(r"\[(?:DATE|YEAR|QUARTER)\]", tail)[0]
            j = before.find(anchor, bi) if anchor.strip() else len(before)
            if j < 0:
                j = len(before)
            out.append((before[bi:j].strip(), m.group(0)))
            bi = j
            ai = m.end()
            continue
        if bi < len(before) and before[bi] == after[ai]:
            bi += 1
            ai += 1
        else:
            ai += 1
    return out


ABS_TEMPORAL = re.compile(
    r"^(?:(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|"
    r"Dec)\.?|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
    r"Q[1-4]|(?:first|second|third|fourth)[\s-]quarter|(?:19|20)\d{2}|"
    r"FY\s?\d{2}|\d{1,2}(?:st|nd|rd|th)?|of|fiscal|year|the|quarter|"
    r",|\s|-|/)+$", re.I)


def _is_absolute_temporal(span):
    return bool(span) and bool(ABS_TEMPORAL.match(span))


def _context(text, span):
    k = text.find(span)
    return (text[max(0, k - 20):k], text[k + len(span):k + len(span) + 3]) \
        if k >= 0 else ("", "")


PUBLISHED = re.compile(r"^Published: (.+)$", re.M)


def audit_s6(c1, s6, man):
    per, flags = [], []
    for i in sorted(c1):
        n1, n6 = news_block(c1[i]), news_block(s6[i]["prompt"] and s6[i])
        b, a = PUBLISHED.findall(n1), PUBLISHED.findall(n6)
        perm = s6[i]["timestamp_permutation"]
        stripped_equal = PUBLISHED.sub("Published: X", n1) == \
            PUBLISHED.sub("Published: X", n6)
        ts_c1 = ts_block(c1[i])
        ts_s6 = section(s6[i]["prompt"], "\nTicker: %s\n" % c1[i]["ticker"],
                        "\n\nNews Context\n")
        rec = {
            "instance_id": i,
            "n_articles": len(b),
            "same_article_ids_and_order":
                s6[i]["article_order"] == c1[i]["article_order"] ==
                man[i]["article_order"],
            "timestamp_multiset_unchanged": sorted(b) == sorted(a),
            "zero_fixed_points_in_permutation": all(perm[k] != k
                                                    for k in range(len(perm))),
            "no_article_keeps_its_own_timestamp": all(a[k] != b[k]
                                                      for k in range(len(b))),
            "only_published_lines_changed": stripped_equal,
            "time_series_unchanged": ts_c1 == ts_s6,
            "question_unchanged": question_block(c1[i]) ==
            section(s6[i]["prompt"], "\n\nQuestion\n",
                    "\n\nSelect the single best answer."),
            "gt_position": s6[i]["gt_position"],
            "gt_timestamp_before": b[s6[i]["gt_position"] - 1],
            "gt_timestamp_after": a[s6[i]["gt_position"] - 1],
        }
        bad = [k for k, v in rec.items() if isinstance(v, bool) and not v]
        rec["flags"] = bad
        if bad:
            flags.append(rec)
        per.append(rec)
    return per, flags


def cue_audit(data, c1):
    rows, totals = [], {}
    for i in sorted(c1):
        q = question_block(c1[i])
        tick = c1[i]["ticker"]
        found = {}
        for name, pat in CUES.items():
            if name == "ticker_symbol":
                hits = re.findall(r"\b%s\b" % re.escape(tick), q)
            elif name == "company_name_like":
                continue
            else:
                hits = pat.findall(q)
            found[name] = [h if isinstance(h, str) else "".join(h) for h in hits]
        # article-fact overlap: numbers shared between the MCQA and the GT text
        art = data[i]["gt_article_text"]
        nums_q = set(re.findall(r"\d+(?:\.\d+)?", q))
        shared = sorted(n for n in nums_q
                        if re.search(r"(?<![\d.])%s(?![\d])" % re.escape(n), art))
        found["numbers_shared_with_gt_article"] = shared
        row = {"instance_id": i, "ticker": tick,
               "counts": {k: len(v) for k, v in found.items()},
               "examples": {k: v[:4] for k, v in found.items() if v}}
        rows.append(row)
        for k, v in found.items():
            totals.setdefault(k, {"n_instances_with_any": 0, "n_occurrences": 0})
            totals[k]["n_occurrences"] += len(v)
            totals[k]["n_instances_with_any"] += 1 if v else 0
    return rows, totals


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    data = {r["instance_id"]: r for r in json.load(
        open(os.path.join(ROOT, "final50_paper_data.json"), encoding="utf-8"))}
    man = {m["instance_id"]: m for m in json.load(
        open(os.path.join(ROOT, "out_paper50_reviewed/manifest.json"),
             encoding="utf-8"))["instances"]}
    c1 = jsonl(os.path.join(ROOT, "out_paper50_reviewed/c1.jsonl"))
    c2 = jsonl(os.path.join(ROOT, "out_paper50_reviewed/c2.jsonl"))
    s5 = jsonl(os.path.join(ROOT, "sanity", "s5_c2_qo_date_mask.jsonl"))
    s6 = jsonl(os.path.join(ROOT, "sanity",
                            "s6_c1_metadata_timestamp_shuffle.jsonl"))
    ids = sorted(c1)

    cue_rows, cue_totals = cue_audit(data, c1)
    s5_per, s5_flags = audit_s5(c2, s5, ids)
    s6_per, s6_flags = audit_s6(c1, s6, man)

    out = {
        "scope": "static audit of the 50 frozen MCQA items and of the two "
                 "derived sanity conditions; no model output was read",
        "phase1_cue_audit": {
            "note": "these are counts of what sits in the question and options, "
                    "outside the evidence context that C2 masks. They are not "
                    "labelled leakage - the point is to measure how much "
                    "information survives the intervention.",
            "totals": cue_totals,
            "per_instance": cue_rows,
        },
        "s5_masking_audit": {
            "n_instances_changed": sum(1 for r in s5_per if r["changed"]),
            "n_spans_changed": sum(r["n_spans"] for r in s5_per),
            "n_flagged": len(s5_flags),
            "flags": s5_flags,
            "changes": [r for r in s5_per if r["changed"]],
            "verdict": ("NO_SEMANTICALLY_DESTRUCTIVE_MASK_FOUND" if not s5_flags
                        else "REVIEW REQUIRED"),
        },
        "s6_shuffle_audit": {
            "n_instances": len(s6_per),
            "all_checks_pass": not s6_flags,
            "n_flagged": len(s6_flags),
            "flags": s6_flags,
            "per_instance": s6_per,
        },
    }
    path = os.path.join(OUTDIR, "sanity_cue_audit.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("PHASE 1 cue audit - instances (of 50) whose MCQA contains:")
    for k, v in sorted(cue_totals.items()):
        print("  %-36s %2d instances, %3d occurrences"
              % (k, v["n_instances_with_any"], v["n_occurrences"]))
    a = out["s5_masking_audit"]
    print("\nS5 masking audit: %d/50 instances changed, %d spans, %d flagged -> %s"
          % (a["n_instances_changed"], a["n_spans_changed"], a["n_flagged"],
             a["verdict"]))
    b = out["s6_shuffle_audit"]
    print("S6 shuffle audit: %d instances, all checks pass: %s (%d flagged)"
          % (b["n_instances"], b["all_checks_pass"], b["n_flagged"]))
    print("wrote %s" % path)


if __name__ == "__main__":
    main()
