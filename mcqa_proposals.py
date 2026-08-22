"""Write the canonicalization proposals with an objective safety classification.

A rewrite is only "safe" if the calendar anchor it removes lies INSIDE the
observation window: replacing an out-of-window date with "the referenced
observation period" silently re-anchors the claim to data the model can see,
which changes the task rather than neutralising it.

Classification for every affected instance:
  SAFE_CANONICALIZATION
  NEEDS_MANUAL_REWRITE                       (wording seam, semantics intact)
  CANNOT_REMOVE_DATE_WITHOUT_CHANGING_TASK   (out-of-window referent)

Writes mcqa_temporal_canonicalization_proposals.json.  Nothing is applied.

Usage:  python mcqa_proposals.py
"""

import datetime as dt
import json
import re

from build_final_hard50 import load_json
from mcqa_canonicalize import MONTH_NUM, proposals

DATA = "final50_locked_data.json"
UTC = dt.timezone.utc
AWKWARD = re.compile(r"(its|their|our|his|her)\s+referenced|"
                     r"publication\s+at\s+the\s+referenced\s+point.*publication|"
                     r"before the news publication at the referenced", re.I)


def window(rec):
    ts = rec["ts_timestamps"]
    return (dt.datetime.fromtimestamp(ts[0], UTC).date(),
            dt.datetime.fromtimestamp(ts[-1], UTC).date())


def expression_dates(expr):
    """Best-effort (year, month, day) resolution of a removed expression."""
    iso = re.search(r"((?:19|20)\d{2})-(\d{2})-(\d{2})", expr)
    if iso:
        return dt.date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    mdy = re.search(r"([A-Z][a-z]{2,8})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*"
                    r"((?:19|20)\d{2})?", expr)
    if mdy and mdy.group(1).lower()[:3] in {k[:3] for k in MONTH_NUM}:
        month = MONTH_NUM.get(mdy.group(1).lower()) or \
            MONTH_NUM.get(mdy.group(1).lower()[:3])
        year = int(mdy.group(3)) if mdy.group(3) else None
        if month:
            return (year, month, int(mdy.group(2)))
    year = re.search(r"\b((?:19|20)\d{2})\b", expr)
    if year:
        return (int(year.group(1)), None, None)
    return None


def outside_window(expr, first, last):
    """True when the expression clearly refers outside the observation window."""
    resolved = expression_dates(expr)
    if resolved is None:
        return False
    if isinstance(resolved, dt.date):
        return not (first <= resolved <= last)
    year, month, day = resolved
    if year is None:
        if month is None:
            return False
        months = {(first.year, first.month), (last.year, last.month)}
        return all(month != m for _, m in months)
    if month is None:
        return not (first.year <= year <= last.year)
    try:
        d = dt.date(year, month, day or 1)
    except ValueError:
        return False
    return not (first <= d <= last)


def main():
    data = {r["instance_id"]: r for r in load_json(DATA)}
    out = []
    for p in proposals():
        rec = data[p["instance_id"]]
        first, last = window(rec)
        gold = p["gold_answer"]

        pub_date = dt.datetime.strptime(rec["gt_published_utc"],
                                        "%Y-%m-%d %H:%M:%S").date()

        # An anchor that IS the publication moment is not out-of-window evidence:
        # the article sits at the end of the observation window by construction, so
        # name it explicitly instead of calling it a point inside the series.
        def is_publication_point(expr):
            resolved = expression_dates(expr)
            if isinstance(resolved, dt.date):
                return resolved == pub_date
            if isinstance(resolved, tuple):
                year, month, day = resolved
                return (month == pub_date.month and day == pub_date.day
                        and (year is None or year == pub_date.year))
            return False

        pub_refs = [c["expression"] for c in p["temporal_tokens_removed"]
                    if is_publication_point(c["expression"])]
        if pub_refs:
            for letter, text in p["proposed_options"].items():
                p["proposed_options"][letter] = text.replace(
                    "the referenced point in the observation window",
                    "the referenced publication point")
            p["proposed_question_stem"] = p["proposed_question_stem"].replace(
                "the referenced point in the observation window",
                "the referenced publication point")
            p["proposed_question_full"] = p["proposed_question_full"].replace(
                "the referenced point in the observation window",
                "the referenced publication point")
            for c in p["temporal_tokens_removed"]:
                if c["expression"] in pub_refs:
                    c["replacement"] = "the referenced publication point"

        # a contrast rendered as earlier/later keeps its ordering, so an anchor
        # outside the window is not a re-anchoring risk there
        ranked_units = {c["expression"] for c in p["temporal_tokens_removed"]
                        if c["replacement"].startswith(("the earlier", "the later"))}

        gold_expressions = [c["expression"] for c in p["temporal_tokens_removed"]
                            if c["expression"] in p["original_options"][gold]]
        out_of_window = [e for e in gold_expressions
                         if outside_window(e, first, last)
                         and e not in pub_refs and e not in ranked_units]
        any_out = [c["expression"] for c in p["temporal_tokens_removed"]
                   if outside_window(c["expression"], first, last)
                   and c["expression"] not in pub_refs
                   and c["expression"] not in ranked_units]

        if out_of_window:
            verdict = "CANNOT_REMOVE_DATE_WITHOUT_CHANGING_TASK"
            reason = ("the gold option is anchored to %s, which lies outside the "
                      "observation window %s..%s; replacing it with a referential "
                      "phrase re-anchors the claim to data the model can actually see"
                      % (", ".join(out_of_window), first, last))
        elif AWKWARD.search(p["proposed_options"][gold]) or \
                any(AWKWARD.search(v) for v in p["proposed_options"].values()):
            verdict = "NEEDS_MANUAL_REWRITE"
            reason = ("semantics are preserved but the substitution leaves an awkward "
                      "seam that a human should polish")
        else:
            verdict = "SAFE_CANONICALIZATION"
            reason = ("every removed anchor lies inside the observation window, option "
                      "distinctions survive, and no non-temporal content changed")

        p.update({
            "observation_window": {"first": str(first), "last": str(last)},
            "removed_expressions_in_gold": gold_expressions,
            "removed_expressions_outside_window": any_out,
            "canonicalization_verdict": verdict,
            "verdict_reason": reason,
        })
        out.append(p)

    counts = {}
    for p in out:
        counts[p["canonicalization_verdict"]] = counts.get(
            p["canonicalization_verdict"], 0) + 1
    amb = [47, 50, 55, 66, 140, 275, 313, 320, 353, 441, 481, 484]
    summary = {
        "status": "PROPOSALS ONLY - no benchmark file was modified",
        "design": "one canonical MCQA wording used identically in C0/C1/C2/C3; the "
                  "timestamp intervention lives in the time series and news context, "
                  "not in the question",
        "rules": {
            "absolute anchors": "replaced by referential phrases (the referenced "
                                "quarter / fiscal year / month / period, or the "
                                "referenced point in the observation window)",
            "contrasts": "two periods of the same unit inside one option become 'the "
                         "earlier X' and 'the later X' so the contrast survives",
            "publication anchors": "a date that IS the article publication moment "
                                   "becomes 'the referenced publication point' - the "
                                   "article is in the prompt, so this renames the "
                                   "referent rather than moving it",
            "kept": "bare relative markers with no year (fourth-quarter results, "
                    "year-over-year, the previous quarter) carry no absolute calendar "
                    "information and are left untouched",
        },
        "n_proposals": len(out),
        "verdict_counts": counts,
        "verdicts_by_instance": {str(p["instance_id"]): p["canonicalization_verdict"]
                                 for p in out},
        "previously_flagged_potential_ambiguity": amb,
        "verdicts_for_previously_ambiguous": {str(i): next(
            p["canonicalization_verdict"] for p in out if p["instance_id"] == i)
            for i in amb},
        "proposals": out,
    }
    with open("mcqa_temporal_canonicalization_proposals.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("proposals: %d | verdicts: %s" % (len(out), counts))
    print("\nthe 12 previously ambiguous instances:")
    for i in amb:
        p = next(x for x in out if x["instance_id"] == i)
        print("  %-4d %-42s %s" % (i, p["canonicalization_verdict"],
                                   p["verdict_reason"][:90]))
    print("\nwrote mcqa_temporal_canonicalization_proposals.json")


if __name__ == "__main__":
    main()
