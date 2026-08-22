"""Audit EVERY temporal channel of the rendered C2 prompt, not just article text.

Sections checked for all 50 locked anchors: the time-series block, article
publication metadata, article titles, article bodies, the question stem, each
answer option, and the static headers/labels.

Question and options are NOT masked by the builder unless --mask-question is
passed, so any temporal token there survives into C2.  Affected instances are
split into SAFE_TO_MASK and POTENTIAL_AMBIGUITY - nothing is rewritten here.

Writes c2_full_prompt_temporal_audit.json.

Usage:  python audit_c2_prompt_temporal.py [--out-dir out_locked50]
"""

import argparse
import collections
import difflib
import json
import os
import re

from audit_challenge import options_of
from build_final_hard50 import load_json
from temporal_mask import RULES, mask_temporal
from verify_conditions import news_block, question_block, split_articles, ts_block

DATA = "final50_locked_data.json"

KINDS = {
    "explicit_year": re.compile(r"\b(?:19|20)\d{2}\b"),
    "month": re.compile(r"\b(January|February|March|April|May|June|July|August|"
                        r"September|October|November|December|Jan\.|Feb\.|Mar\.|"
                        r"Apr\.|Jun\.|Jul\.|Aug\.|Sept?\.|Oct\.|Nov\.|Dec\.)\b"),
    "calendar_date": re.compile(r"\b(?:(?:19|20)\d{2}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/"
                                r"(?:\d{2}|\d{4})|(?:January|February|March|April|May|"
                                r"June|July|August|September|October|November|December)"
                                r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*(?:19|20)\d{2})?)"),
    "quarter_plus_year": re.compile(r"\bQ[1-4]\s*(?:of\s+)?(?:FY\s*)?(?:19|20)\d{2}\b"
                                    r"|\b(first|second|third|fourth)[\s-]quarter\s+of\s+"
                                    r"(?:fiscal\s+)?(?:19|20)\d{2}\b", re.I),
    "fiscal_period_plus_year": re.compile(r"\b(?:fiscal|FY)\s*(?:year\s*)?(?:19|20)?\d{2}\b",
                                          re.I),
    "bare_quarter": re.compile(r"\bQ[1-4]\b|\b(first|second|third|fourth)[\s-]quarter\b",
                               re.I),
    "weekday": re.compile(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b"),
}
# A relative phrase that is only interpretable via an explicit date elsewhere.
RELATIVE_TIED = re.compile(r"\b(since|as of|following|after|before|by)\s+the\s+"
                           r"(?:(?:19|20)\d{2}-\d{2}-\d{2}|\w+\s+\d{1,2},?\s*(?:19|20)?\d{0,4})"
                           r"\s*(timestamp|date|publication)?", re.I)


def _numeric_context(text, m):
    """True when a 4-digit 'year' is really part of a number such as 2071.12."""
    before = text[m.start() - 1] if m.start() else ""
    after = text[m.end()] if m.end() < len(text) else ""
    return before.isdigit() or before == "." or after.isdigit() or after == "."


def detect(text):
    found = {}
    for name, pattern in KINDS.items():
        hits = sorted({m.group(0) for m in pattern.finditer(text)
                       if not (name == "explicit_year" and _numeric_context(text, m))})
        if name == "month":
            # the masker deliberately leaves the bare word "May" alone (modal-verb
            # collision); that is documented behaviour, not leakage
            hits = [h for h in hits if h != "May"]
        if hits:
            found[name] = hits[:6]
    if RELATIVE_TIED.search(text):
        found["relative_phrase_tied_to_date"] = sorted(
            {m.group(0).strip() for m in RELATIVE_TIED.finditer(text)})[:4]
    return found


def merge_hits(dicts):
    """Union per-article detections (never scan concatenated articles)."""
    merged = {}
    for d in dicts:
        for k, v in d.items():
            merged.setdefault(k, [])
            for x in v:
                if x not in merged[k]:
                    merged[k].append(x)
    return {k: v[:6] for k, v in merged.items()}


def bare_may_residuals(arts):
    return sum(1 for _, t, c in arts
               if re.search(r"May", t) or re.search(r"May", c))


def masked_expressions(text):
    n = 0
    work = text
    for pattern, token in RULES:
        work, k = pattern.subn(token, work)
        n += k
    return work, n


def classify(question, options, gold):
    """SAFE_TO_MASK vs POTENTIAL_AMBIGUITY, with the objective reason."""
    stem = question.split("\nA.")[0]
    masked_opts = {k: masked_expressions(v)[0] for k, v in options.items()}
    reasons = []

    # (1) two options collapse onto each other once dates are masked
    letters = sorted(options)
    for i, a in enumerate(letters):
        for b in letters[i + 1:]:
            if not (detect(options[a]) or detect(options[b])):
                continue
            ratio = difflib.SequenceMatcher(None, masked_opts[a], masked_opts[b]).ratio()
            if masked_opts[a] == masked_opts[b] or ratio >= 0.92:
                reasons.append("options %s and %s become %.0f%% identical after "
                               "masking" % (a, b, 100 * ratio))

    # (2) an option compares two periods that collapse to the same token
    for k, v in options.items():
        m, _ = masked_expressions(v)
        for token in ("[YEAR]", "[QUARTER]", "[DATE]"):
            if m.count(token) >= 2:
                reasons.append("option %s contrasts two periods that both become %s"
                               % (k, token))
                break

    # (3) an option points at a date given in the stem
    if RELATIVE_TIED.search(" ".join(options.values())) and detect(stem):
        reasons.append("an option refers back to an explicit date, whose referent "
                       "masking removes")

    # (4) the gold is the only option carrying a date -> masking may flatten the cue
    dated = [k for k, v in options.items() if detect(v)]
    if dated == [gold]:
        reasons.append("only the gold option carries a temporal token, so masking "
                       "removes the feature that distinguishes it")

    return ("POTENTIAL_AMBIGUITY" if reasons else "SAFE_TO_MASK"), reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="out_locked50")
    args = ap.parse_args()

    data = {r["instance_id"]: r for r in load_json(DATA)}
    with open(os.path.join(args.out_dir, "c2.jsonl"), encoding="utf-8") as f:
        c2 = {json.loads(l)["instance_id"]: json.loads(l) for l in f if l.strip()}
    meta = json.load(open(os.path.join(args.out_dir, "manifest.json"), encoding="utf-8"))

    per_instance, section_hits = [], collections.Counter()
    for iid in sorted(data):
        rec, rendered = data[iid], c2[iid]
        question = rec["mcqa_question"].strip()
        options = options_of(question)
        stem = question.split("\nA.")[0]
        gold = rec["mcqa_answer"]

        stem_hits = detect(stem)
        option_hits = {k: detect(v) for k, v in options.items()}
        option_hits = {k: v for k, v in option_hits.items() if v}

        # rendered C2 sections
        ts = ts_block(rendered)
        news = news_block(rendered)
        arts = split_articles(news)
        q_rendered = question_block(rendered)
        headers = "\n".join(["Task", "Time Series", "Ticker: %s" % rendered["ticker"],
                             "News Context", "Question", "Select the single best answer."]
                            + ["Article %d" % i for i in range(1, len(arts) + 1)])

        rendered_sections = {
            "time_series_block": detect(ts),
            "article_publication_metadata": ({"published_lines": [p for p, _, _ in arts
                                                                 if p is not None]}
                                             if any(p for p, _, _ in arts) else {}),
            "article_titles": merge_hits(detect(t) for _, t, _ in arts),
            "article_bodies": merge_hits(detect(c) for _, _, c in arts),
            "question_and_options": detect(q_rendered),
            "headers_and_labels": detect(headers),
        }
        for name, hits in rendered_sections.items():
            if hits:
                section_hits[name] += 1

        verdict, reasons = classify(question, options, gold)
        affected = bool(stem_hits or option_hits)
        per_instance.append({
            "instance_id": iid, "ticker": rec["ticker"], "gold_answer": gold,
            "question_has_temporal": bool(stem_hits),
            "question_stem_hits": stem_hits,
            "options_with_temporal": sorted(option_hits),
            "option_hits": option_hits,
            "gold_option_has_temporal": gold in option_hits,
            "example_before_masking": (stem if stem_hits else
                                       options[sorted(option_hits)[0]]
                                       if option_hits else "")[:300],
            "example_after_masking": masked_expressions(
                stem if stem_hits else options[sorted(option_hits)[0]]
                if option_hits else "")[0][:300],
            "rendered_c2_sections_with_temporal": {k: v for k, v in
                                                   rendered_sections.items() if v},
            "bare_may_articles": bare_may_residuals(arts),
            "affected": affected,
            "masking_verdict": verdict if affected else "NOT_AFFECTED",
            "ambiguity_reasons": reasons if affected else [],
        })

    affected = [p for p in per_instance if p["affected"]]
    safe = [p for p in affected if p["masking_verdict"] == "SAFE_TO_MASK"]
    risky = [p for p in affected if p["masking_verdict"] == "POTENTIAL_AMBIGUITY"]

    summary = {
        "out_dir_audited": args.out_dir,
        "builder_masks_question_and_options": bool(meta.get("mask_question", False)),
        "builder_note": "build_conditions.py masks the question/options only with "
                        "--mask-question; this build was produced without it, so every "
                        "temporal token listed below survives into the C2 prompt",
        "n_instances": len(per_instance),
        "n_questions_with_temporal_expressions":
            sum(1 for p in per_instance if p["question_has_temporal"]),
        "n_instances_with_temporal_options":
            sum(1 for p in per_instance if p["options_with_temporal"]),
        "n_option_texts_with_temporal":
            sum(len(p["options_with_temporal"]) for p in per_instance),
        "n_affected_instances": len(affected),
        "affected_instance_ids": [p["instance_id"] for p in affected],
        "rendered_section_leakage_counts": dict(section_hits),
        "known_deliberate_residuals": {
            "bare_month_word_May": sum(p["bare_may_articles"] for p in per_instance),
            "explanation": "temporal_mask.py excludes the bare word 'May' from the "
                           "bare-month rule because it collides with the modal verb; "
                           "'May 3' and 'May 2022' are still masked. Counted here, "
                           "not reported as leakage.",
        },
        "rendered_section_note": "time_series_block, article_publication_metadata, "
                                 "article_titles, article_bodies and headers_and_labels "
                                 "should all be zero in C2; question_and_options is the "
                                 "only expected non-zero channel while --mask-question "
                                 "is off",
        "safe_to_mask": {"count": len(safe),
                         "instance_ids": [p["instance_id"] for p in safe]},
        "potential_ambiguity": {"count": len(risky),
                                "instance_ids": [p["instance_id"] for p in risky],
                                "issues": [{"instance_id": p["instance_id"],
                                            "reasons": p["ambiguity_reasons"]}
                                           for p in risky]},
        "instances": per_instance,
    }
    with open("c2_full_prompt_temporal_audit.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("builder masks question/options: %s"
          % summary["builder_masks_question_and_options"])
    print("questions with temporal expressions: %d/50"
          % summary["n_questions_with_temporal_expressions"])
    print("instances with temporal options: %d/50 (%d option texts)"
          % (summary["n_instances_with_temporal_options"],
             summary["n_option_texts_with_temporal"]))
    print("affected instances: %d" % len(affected))
    print("rendered C2 section leakage: %s" % dict(section_hits))
    print("SAFE_TO_MASK: %d -> %s" % (len(safe), [p["instance_id"] for p in safe]))
    print("POTENTIAL_AMBIGUITY: %d -> %s" % (len(risky),
                                             [p["instance_id"] for p in risky]))
    print("wrote c2_full_prompt_temporal_audit.json")


if __name__ == "__main__":
    main()
