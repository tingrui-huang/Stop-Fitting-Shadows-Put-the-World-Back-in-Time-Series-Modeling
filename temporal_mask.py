"""Deterministic temporal masking used to build condition C2.

Only absolute temporal information is removed: explicit dates, calendar years,
quarters / reporting periods, month names and weekday names.  Everything else in
the article (including relative wording such as "last week" or "year over year",
which does not reveal a real-world date) is left untouched.

The token set is exactly {[DATE], [YEAR], [QUARTER]}, matching the experiment
specification.  The function is pure regex: same input -> same output, always.
"""

import re

_FULL_MONTHS = ("January February March April May June July August September "
                "October November December").split()
_ABBR_MONTHS = ("Jan Feb Mar Apr May Jun Jul Aug Sep Sept Oct Nov Dec").split()
# Bare month names are masked too, but "May" is excluded from the *bare* rule
# because it collides with the modal verb; it is still masked inside date
# expressions ("May 2023", "May 5").
_BARE_MONTHS = [m for m in _FULL_MONTHS if m != "May"] + \
               [m for m in _ABBR_MONTHS if m != "May"]

_MONTH = r"(?:%s)\.?" % "|".join(_FULL_MONTHS + _ABBR_MONTHS)
_BARE_MONTH = r"(?:%s)\.?" % "|".join(_BARE_MONTHS)
_WEEKDAY = (r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
            r"Mon\.|Tues?\.|Wed\.|Thurs?\.|Fri\.|Sat\.|Sun\.)")
_YEAR = r"(?:19|20)\d{2}"
_ORD = r"(?:first|second|third|fourth|1st|2nd|3rd|4th)"

# Applied in order; earlier rules consume the longer expressions.
RULES = [
    # ---- quarters / reporting periods -------------------------------------
    (re.compile(r"\bQ[1-4]\s*(?:of\s+)?(?:FY\s*)?(?:%s)\b" % _YEAR), "[QUARTER]"),
    (re.compile(r"\b%s[\s-]quarter\s+of\s+(?:fiscal\s+)?(?:%s)\b" % (_ORD, _YEAR), re.I), "[QUARTER]"),
    (re.compile(r"\b%s[\s-]quarter\b" % _ORD, re.I), "[QUARTER]"),
    (re.compile(r"\bquarter\s+of\s+(?:fiscal\s+)?(?:%s)\b" % _YEAR, re.I), "[QUARTER]"),
    (re.compile(r"\bQ[1-4]\b"), "[QUARTER]"),
    # ---- explicit dates ----------------------------------------------------
    (re.compile(r"\b%s,?\s+%s\s+\d{1,2}(?:st|nd|rd|th)?,?\s+%s\b" % (_WEEKDAY, _MONTH, _YEAR)), "[DATE]"),
    (re.compile(r"\b%s\s+\d{1,2}(?:st|nd|rd|th)?,?\s+%s\b" % (_MONTH, _YEAR)), "[DATE]"),
    (re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s+%s,?\s+%s\b" % (_MONTH, _YEAR)), "[DATE]"),
    (re.compile(r"\b%s,?\s+%s\s+\d{1,2}(?:st|nd|rd|th)?\b" % (_WEEKDAY, _MONTH)), "[DATE]"),
    (re.compile(r"\b%s\s+\d{1,2}(?:st|nd|rd|th)?\b" % _MONTH), "[DATE]"),
    (re.compile(r"\b%s\s+%s\b" % (_MONTH, _YEAR)), "[DATE]"),
    (re.compile(r"\b%s-\d{2}-\d{2}\b" % _YEAR), "[DATE]"),
    (re.compile(r"\b\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})\b"), "[DATE]"),
    # ---- years -------------------------------------------------------------
    (re.compile(r"\bFY\s?\d{2}\b"), "[YEAR]"),
    (re.compile(r"\b%s\b" % _YEAR), "[YEAR]"),
    # ---- bare month / weekday names ---------------------------------------
    (re.compile(r"\b%s\b" % _BARE_MONTH), "[DATE]"),
    (re.compile(r"\b%s\b" % _WEEKDAY), "[DATE]"),
]


def mask_temporal(text):
    """Return (masked_text, n_substitutions)."""
    n = 0
    for pattern, token in RULES:
        text, k = pattern.subn(token, text)
        n += k
    return text, n
