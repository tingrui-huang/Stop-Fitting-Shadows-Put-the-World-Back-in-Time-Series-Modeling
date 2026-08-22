"""Ticker -> company-name aliases, derived from the real MTBench news corpus.

Titles in the corpus overwhelmingly use the form "Company Name (TICKER)", so the
alias table is read straight out of the corpus rather than hand-written.  Index
ETFs, which never appear in that pattern, get a small explicit table that is
marked as manual in the audit output.

Used for the entity check: an anchor is an ENTITY MISMATCH only when its own
company is never mentioned in the article AND another company is named in the
article title.  A merely weak link (no company named at all) is reported, not
treated as a defect.
"""

import collections
import re

TITLE_ALIAS = re.compile(r"([A-Z][\w&.'\- ]{2,40}?)\s*\(([A-Z.]{1,6})\)")
STOPWORDS = {"this", "what", "why", "should", "here", "best", "analysts", "stock",
             "shares", "after", "with", "more", "than", "does", "will", "from",
             "into", "over", "when", "make", "could", "these", "before", "about"}
MANUAL_ALIASES = {"SPY": ["S&P 500", "SPDR", "index"],
                  "IWM": ["Russell 2000"], "QQQ": ["Nasdaq 100"]}


def build_alias_map(titles):
    """-> {ticker: Counter(alias)} from corpus titles."""
    alias = collections.defaultdict(collections.Counter)
    for title in titles:
        for m in TITLE_ALIAS.finditer(title or ""):
            name, ticker = m.group(1).strip(), m.group(2)
            if len(name.split()) > 5:
                continue
            alias[ticker][name] += 1
            first = name.split()[0]
            if len(first) >= 4 and first.lower() not in STOPWORDS:
                alias[ticker][first] += 1
    return alias


def names_for(ticker, alias):
    return [a for a, _ in alias.get(ticker, collections.Counter()).most_common(6)] \
        + MANUAL_ALIASES.get(ticker, []) + [ticker]


def entity_check(ticker, title, text, alias):
    """-> dict with the entity evidence for one anchor."""
    blob = (title + " " + text).lower()
    mine = names_for(ticker, alias)
    mentioned = [n for n in mine if n.lower() in blob]
    in_title = [n for n in mine if n.lower() in title.lower()]
    body_hits = max([len(re.findall(re.escape(n), text, re.I)) for n in mine] or [0])

    others = []
    for other_ticker in alias:
        if other_ticker == ticker:
            continue
        for name in names_for(other_ticker, alias)[:3]:
            if len(name) >= 5 and name.lower() in title.lower():
                others.append({"ticker": other_ticker, "name": name})
                break
    return {
        "aliases_used": mine[:4],
        "entity_mentioned": bool(mentioned),
        "entity_in_title": bool(in_title),
        "entity_body_mentions": body_hits,
        "other_companies_in_title": others[:3],
        "mismatch": (not mentioned) and bool(others),
        "weak_link": bool(mentioned) and not in_title and body_hits < 3,
    }
