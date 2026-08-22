"""Date-neutral canonicalization of the MCQA question/options.

The canonical wording is meant to be used IDENTICALLY in C0, C1, C2 and C3, so
the timestamp intervention lives only in the time series and the news context -
never in the question itself.

Absolute calendar anchors are replaced by referential phrases ("the referenced
quarter", "over the referenced observation period").  When one option contrasts
TWO periods the contrast is preserved by rank ("the earlier quarter" vs "the
later quarter") instead of being collapsed to a single token.

Nothing is written back into the benchmark: this module only proposes.

Usage:  python mcqa_canonicalize.py
"""

import datetime as dt
import difflib
import json
import re

from audit_challenge import options_of
from build_final_hard50 import load_json

DATA = "final50_locked_data.json"
AUDIT = "c2_full_prompt_temporal_audit.json"

MONTHS = ("January February March April May June July August September October "
          "November December").split()
MONTH_NUM = {m.lower(): i + 1 for i, m in enumerate(MONTHS)}
MONTH_NUM.update({m[:3].lower(): i + 1 for i, m in enumerate(MONTHS)})
MONTH_RE = r"(?:January|February|March|April|May|June|July|August|September|" \
           r"October|November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|" \
           r"Aug\.?|Sept?\.?|Oct\.?|Nov\.?|Dec\.?)"
ORD = r"(?:first|second|third|fourth)"

# (name, unit, pattern) - ordered, longest constructs first
PATTERNS = [
    ("iso_timestamp_ref", "period",
     re.compile(r"\b(?:since|as of|from|after|before|following)\s+the\s+"
                r"(?:19|20)\d{2}-\d{2}-\d{2}\s*(?:timestamp|date)?", re.I)),
    ("iso_date", "date", re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")),
    ("quarter_year", "quarter",
     re.compile(r"\bQ([1-4])\s*(?:of\s+)?(?:FY\s*)?((?:19|20)\d{2})\b")),
    ("ordinal_quarter_year", "quarter",
     re.compile(r"\b(%s)[\s-]quarter\s+of\s+(?:fiscal\s+)?((?:19|20)\d{2})\b" % ORD, re.I)),
    ("fiscal_year", "fiscal_year",
     re.compile(r"\b(?:fiscal(?:\s+year)?|FY)\s*((?:19|20)\d{2})\b", re.I)),
    ("half_year", "half",
     re.compile(r"\b(first|second)\s+half\s+of\s+((?:19|20)\d{2})\b", re.I)),
    ("month_day_year", "date",
     re.compile(r"\b(%s)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+((?:19|20)\d{2})\b" % MONTH_RE)),
    ("month_year", "month",
     re.compile(r"\b(%s)\s+((?:19|20)\d{2})\b" % MONTH_RE)),
    ("month_day", "date",
     re.compile(r"\b(%s)\s+(\d{1,2})(?:st|nd|rd|th)?\b" % MONTH_RE)),
    ("bare_quarter_year_free", "quarter", re.compile(r"\bQ([1-4])\b")),
    ("bare_year", "year", re.compile(r"\b((?:19|20)\d{2})\b")),
    ("bare_month", "month", re.compile(r"\b(%s)\b" % MONTH_RE)),
]

REFERENTIAL = {
    "period": "over the referenced observation period",
    "date": "the referenced point in the observation window",
    "quarter": "the referenced quarter",
    "fiscal_year": "the referenced fiscal year",
    "half": "the referenced half-year",
    "month": "the referenced month",
    "year": "the referenced period",
}
RANKED = {
    "quarter": ("the earlier quarter", "the later quarter"),
    "year": ("the earlier period", "the later period"),
    "fiscal_year": ("the earlier fiscal year", "the later fiscal year"),
    "month": ("the earlier month", "the later month"),
    "date": ("the earlier point in the observation window",
             "the later point in the observation window"),  # no leading preposition
    "half": ("the earlier half-year", "the later half-year"),
}


def sort_key(name, m):
    """Chronological key so a contrast can be re-expressed as earlier/later."""
    try:
        if name == "quarter_year":
            return (int(m.group(2)), int(m.group(1)))
        if name == "ordinal_quarter_year":
            q = ("first", "second", "third", "fourth").index(m.group(1).lower()) + 1
            return (int(m.group(2)), q)
        if name in ("fiscal_year", "bare_year"):
            return (int(m.group(1)), 0)
        if name == "half_year":
            return (int(m.group(2)), 1 if m.group(1).lower() == "first" else 3)
        if name == "month_day_year":
            return (int(m.group(3)), MONTH_NUM.get(m.group(1).rstrip(".").lower(), 0),
                    int(m.group(2)))
        if name == "month_year":
            return (int(m.group(2)), MONTH_NUM.get(m.group(1).rstrip(".").lower(), 0))
        if name == "month_day":
            return (0, MONTH_NUM.get(m.group(1).rstrip(".").lower(), 0), int(m.group(2)))
        if name == "bare_month":
            return (0, MONTH_NUM.get(m.group(0).rstrip(".").lower(), 0))
        if name == "iso_date":
            d = dt.datetime.strptime(m.group(0), "%Y-%m-%d")
            return (d.year, d.month, d.day)
    except (ValueError, IndexError):
        pass
    return (0, 0)


def canonicalize(text):
    """-> (rewritten text, [{expression, replacement, unit, rule}])."""
    spans, changes = [], []
    consumed = []

    def overlaps(a, b):
        return any(not (b <= s or a >= e) for s, e in consumed)

    for name, unit, pattern in PATTERNS:
        for m in pattern.finditer(text):
            if overlaps(m.start(), m.end()):
                continue
            consumed.append((m.start(), m.end()))
            spans.append({"name": name, "unit": unit, "start": m.start(),
                          "end": m.end(), "text": m.group(0), "key": sort_key(name, m)})

    # a contrast of two periods of the same unit keeps its ordering
    by_unit = {}
    for s in spans:
        by_unit.setdefault(s["unit"], []).append(s)
    replacement = {}
    for unit, group in by_unit.items():
        distinct = sorted({g["key"] for g in group})
        if len(distinct) >= 2 and unit in RANKED:
            early, late = RANKED[unit]
            for g in group:
                replacement[(g["start"], g["end"])] = (
                    early if g["key"] == distinct[0] else late)
        else:
            for g in group:
                replacement[(g["start"], g["end"])] = REFERENTIAL.get(unit,
                                                                     "the referenced period")

    out, last = [], 0
    for s in sorted(spans, key=lambda s: s["start"]):
        rep = replacement[(s["start"], s["end"])]
        out.append(text[last:s["start"]])
        out.append(rep)
        last = s["end"]
        changes.append({"expression": s["text"], "replacement": rep,
                        "unit": s["unit"], "rule": s["name"]})
    out.append(text[last:])
    result = "".join(out)
    # tidy the seams left by substitution
    result = re.sub(r"\bon\s+(the (?:earlier|later|referenced))", r"at \1", result)
    # only collapse an article that collides with an INSERTED phrase
    result = re.sub(r"\b(its|their|our|his|her)\s+the\s+(referenced|earlier|later)\b",
                    r"\1 \2", result)
    result = re.sub(r"\bthe\s+the\s+(referenced|earlier|later)\b", r"the \1", result)
    result = re.sub(r"\s{2,}", " ", result)
    result = re.sub(r"\s+([,.;:])", r"\1", result)
    return result, changes


def rebuild_question(question, new_stem, new_options):
    lines = [new_stem.strip()]
    for letter in "ABCD":
        lines.append("%s. %s" % (letter, new_options[letter]))
    return "\n".join(lines)


def confidence(changes, options_changed, collisions):
    if collisions:
        return "low"
    if any(c["replacement"].startswith(("the earlier", "the later")) for c in changes):
        return "medium"
    if len(changes) <= 2 and options_changed <= 2:
        return "high"
    return "medium"


def proposals():
    data = {r["instance_id"]: r for r in load_json(DATA)}
    audit = json.load(open(AUDIT, encoding="utf-8"))
    affected = {p["instance_id"]: p for p in audit["instances"] if p["affected"]}

    out = []
    for iid, info in sorted(affected.items()):
        rec = data[iid]
        question = rec["mcqa_question"].strip()
        options = options_of(question)
        stem = question.split("\nA.")[0].strip()
        gold = rec["mcqa_answer"]

        new_stem, stem_changes = canonicalize(stem)
        new_options, changes = {}, list(stem_changes)
        for letter, text in options.items():
            new_text, ch = canonicalize(text)
            new_options[letter] = new_text
            changes.extend(ch)

        collisions = []
        letters = sorted(new_options)
        for i, a in enumerate(letters):
            for b in letters[i + 1:]:
                ratio = difflib.SequenceMatcher(None, new_options[a],
                                                new_options[b]).ratio()
                if new_options[a] == new_options[b] or ratio >= 0.92:
                    collisions.append("%s/%s %.0f%%" % (a, b, 100 * ratio))

        n_changed = sum(1 for letter in options if options[letter] != new_options[letter])
        out.append({
            "instance_id": iid, "ticker": rec["ticker"], "gold_answer": gold,
            "original_question_stem": stem,
            "original_options": options,
            "proposed_question_stem": new_stem,
            "proposed_options": new_options,
            "proposed_question_full": rebuild_question(question, new_stem, new_options),
            "temporal_tokens_removed": changes,
            "n_options_changed": n_changed,
            "gold_option_changed": options[gold] != new_options[gold],
            "option_distinctions_preserved": not collisions,
            "option_collisions": collisions,
            "gold_remains_uniquely_supported": (not collisions),
            "gold_uniqueness_check": "structural only: the gold option stays textually "
                                     "distinct from every other option after rewriting "
                                     "and no non-temporal content was removed; semantic "
                                     "uniqueness still needs a human read",
            "rewrite_confidence": confidence(changes, n_changed, collisions),
            "prior_verdict": info["masking_verdict"],
            "manual_review_required": True,
        })
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for p in proposals():
        print("=" * 100)
        print("ID %d gold=%s prior=%s conf=%s collisions=%s"
              % (p["instance_id"], p["gold_answer"], p["prior_verdict"],
                 p["rewrite_confidence"], p["option_collisions"] or "none"))
        for letter in "ABCD":
            if p["original_options"][letter] != p["proposed_options"][letter]:
                print("  %s BEFORE: %s" % (letter, p["original_options"][letter][:150]))
                print("  %s AFTER : %s" % (letter, p["proposed_options"][letter][:150]))
