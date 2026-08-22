"""Shared helpers for the distractor pilot: the local article corpus and a
deterministic event-type label derived from the real article text.

The corpus is exactly the ground-truth articles that ship with the two datasets
in this repository (c0_data.json + hard50_data.json).  No article is invented,
rewritten or re-timestamped anywhere in this pipeline; every candidate keeps its
source text, its source publication timestamp and a provenance id of the form
"<dataset>:<instance_id>".
"""

import ast
import datetime as dt
import re

CORPUS_FILES = [("old", "c0_data.json"), ("new", "hard50_data.json")]

# Ordered: the first pattern that matches wins, so specific beats generic.
EVENT_RULES = [
    ("earnings", r"\b(earnings|q[1-4] (results|report)|quarterly results|beats?|misses?|"
                 r"eps|revenue (rose|fell|growth)|reports? (q[1-4]|first|second|third|fourth)"
                 r"[- ]quarter)\b"),
    ("guidance", r"\b(guidance|outlook|forecast|raises? (its )?(full[- ]year|fy)|cuts? (its )?"
                 r"(full[- ]year|fy)|warns?)\b"),
    ("analyst_rating", r"\b(upgrade[sd]?|downgrade[sd]?|price target|initiat(e|es|ed) coverage|"
                       r"analyst[s]? (say|see|rate)|buy rating|sell rating|overweight|underweight)\b"),
    ("ma_deal", r"\b(acquisition|acquires?|merger|takeover|buyout|stake in|divest|spin[- ]?off)\b"),
    ("legal_regulatory", r"\b(lawsuit|sues?|settlement|antitrust|regulator|sec (probe|charges)|"
                         r"investigation|fine[sd]?|subpoena|ftc|doj)\b"),
    ("dividend_buyback", r"\b(dividend|buyback|repurchase|share repurchase|payout)\b"),
    ("product_launch", r"\b(launch(es|ed)?|unveil(s|ed)?|new (chip|model|product|service|iphone)|"
                       r"rollout|debut)\b"),
    ("executive", r"\b(ceo|cfo|chief executive|steps down|resign(s|ed)?|appoint(s|ed)?|"
                  r"names? .{0,20}(ceo|cfo))\b"),
    ("macro_market", r"\b(federal reserve|fed |inflation|cpi|recession|rate hike|jobs report|"
                     r"treasury yield|s&p 500|market (rally|selloff|sell[- ]off)|bear market)\b"),
    ("stock_move", r"\b(shares? (rose|fell|jump|slump|surge|sink|are rising|are falling)|"
                   r"stock (jump|slump|surge|sink|soar|plunge)|why .{0,30}(stock|shares))\b"),
]


def parse_article(raw):
    """'Title: X \\n Content: [...]' -> (title, body).  Same parse as the builder."""
    title, _, body = raw.partition(" \n Content: ")
    title = title[len("Title: "):].strip() if title.startswith("Title: ") else title.strip()
    paragraphs = ast.literal_eval(body)
    return title, "\n".join(p.strip() for p in paragraphs if p and p.strip())


def event_type(title, text=""):
    """Deterministic event label from the real article wording."""
    blob = (title + " " + text[:1200]).lower()
    for label, pattern in EVENT_RULES:
        if re.search(pattern, blob):
            return label
    return "other"


def parse_utc(stamp):
    return dt.datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")


def load_corpus(load_json):
    """-> {article_id: record} over every GT article in the local datasets."""
    corpus = {}
    for tag, path in CORPUS_FILES:
        for rec in load_json(path):
            title, text = parse_article(rec["gt_article_text"])
            aid = "%s:%d" % (tag, rec["instance_id"])
            corpus[aid] = {
                "article_id": aid,
                "dataset": path,
                "source_instance_id": rec["instance_id"],
                "ticker": rec["ticker"],
                "published_utc": rec["gt_published_utc"],
                "published_dt": parse_utc(rec["gt_published_utc"]),
                "title": title,
                "text": text,
                "raw": rec["gt_article_text"],
                "event_type": event_type(title, text),
            }
    return corpus
