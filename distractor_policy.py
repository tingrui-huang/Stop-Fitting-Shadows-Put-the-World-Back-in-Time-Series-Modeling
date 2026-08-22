"""Paper-conformant distractor policy: temporal aliasing and absence evidence.

Temporal aliasing (Type A)
    same ticker, same or clearly analogous event type, abs(offset_days) >= 90,
    a different reporting episode.  BOTH directions are allowed: a future-dated
    article of the same recurring event is a valid alias (timestamps should
    reject it; without timestamps it is confusable).  The signed offset and the
    alias direction are always recorded.

Absence evidence (Type B)
    same ticker, topically about the company, but the target event/mechanism is
    absent, it cannot itself serve as an alternative explanation for the MCQA,
    and it is not generic boilerplate.

Event types are INFERRED from the real article text (news_corpus.event_type);
the corpus label_type/label_time/label_sentiment fields are explicit and are
carried verbatim on every candidate.  Exact type matches always rank before
family matches and the tier is recorded, never silently conflated.
"""

import re

import pandas as pd

from entity_alias import build_alias_map, entity_check, names_for
from news_corpus import EVENT_RULES, event_type

CORPUS = "data/MTBench_finance_news.parquet"
CORPUS_COLS = ["id", "tickers", "published_utc", "title", "content", "description",
               "publisher", "article_url", "keywords", "label_type", "label_time",
               "label_sentiment"]

ALIAS_MIN_DAYS = 90

# Tier 2: clearly analogous event types (earnings <-> earnings preview/guidance,
# upgrade <-> downgrade, product launch <-> business update, ...).
FAMILY = {
    "earnings": "results_outlook", "guidance": "results_outlook",
    "analyst_rating": "analyst",
    "stock_move": "market_move", "macro_market": "market_move",
    "ma_deal": "corporate_action", "product_launch": "corporate_action",
    "executive": "corporate_action", "dividend_buyback": "corporate_action",
    "legal_regulatory": "corporate_action",
    "other": "other",
}

# Event classes that could independently explain a price episode: never allowed
# as absence evidence.
STRONG_EVENTS = {"earnings", "guidance", "analyst_rating", "ma_deal",
                 "legal_regulatory", "executive", "dividend_buyback",
                 "product_launch"}

# The corpus carries NO sector/industry field and every article is tagged with
# exactly one ticker, so "same sector" cannot be read off the data.  The
# strongest available evidence of a closely related entity is that a different
# company's article explicitly discusses the anchor company; that is what tier
# B2 uses, and it is always recorded as inferred.
GENERIC_ALIAS = {"inc", "inc.", "corp", "corp.", "corporation", "company", "co",
                 "group", "holdings", "the", "ltd", "plc", "industries",
                 "international", "technologies", "systems", "financial",
                 "bancorp", "brands", "partners", "resources", "stores",
                 "motors", "energy", "realty", "communications"}

BOILERPLATE_TITLE = re.compile(
    r"(what you should know|zacks\.com featured highlights|"
    r"here is what to know beyond why|stock moves -?\d|company news for|"
    r"new strong (buy|sell) stocks for)", re.I)

EVENT_PATTERNS = dict(EVENT_RULES)
MIN_CONTENT_CHARS = 800
MAX_TICKERS_FOR_FOCUS = 4


def load_corpus_frame():
    return pd.read_parquet(CORPUS, columns=CORPUS_COLS)


def as_list(x):
    return [] if x is None else list(x)


def index_by_ticker(df):
    """-> {ticker: [article dicts]}, event types inferred once."""
    out = {}
    for row in df.itertuples(index=False):
        pub = row.published_utc.to_pydatetime()
        rec = {
            "article_id": row.id,
            "tickers": as_list(row.tickers),
            "published_dt": pub,
            "published_utc": pub.strftime("%Y-%m-%d %H:%M:%S"),
            "title": row.title or "",
            "content": row.content or "",
            "description": row.description or "",
            "publisher": (row.publisher or {}).get("name")
                         if isinstance(row.publisher, dict) else None,
            "article_url": row.article_url,
            "label_type": as_list(row.label_type),
            "label_time": as_list(row.label_time),
            "label_sentiment": as_list(row.label_sentiment),
            "keywords": as_list(row.keywords),
        }
        rec["event_type"] = event_type(rec["title"], rec["content"])
        for t in rec["tickers"]:
            out.setdefault(t, []).append(rec)
    return out


def match_tier(gt_event, cand_event):
    """-> 'exact' | 'family' | None (never conflate the two)."""
    if cand_event == gt_event:
        return "exact"
    if (FAMILY.get(cand_event) == FAMILY.get(gt_event)
            and FAMILY.get(gt_event) not in (None, "other")):
        return "family"
    return None


def documents_event(article, gt_event):
    """True when the article's text matches the GT event class pattern at all."""
    pattern = EVENT_PATTERNS.get(gt_event)
    if pattern is None:
        return False
    blob = (article["title"] + " " + article["content"][:2000]).lower()
    return re.search(pattern, blob) is not None


def offset_days(article, gt_dt):
    return (article["published_dt"] - gt_dt).total_seconds() / 86400.0


def type_a_candidates(pool, gt_event, gt_dt):
    """Temporal aliases, exact tier first, then family; both directions allowed."""
    out = []
    for a in pool:
        tier = match_tier(gt_event, a["event_type"])
        if tier is None:
            continue
        off = offset_days(a, gt_dt)
        if abs(off) < ALIAS_MIN_DAYS:
            continue
        out.append({
            "article": a, "tier": tier, "offset_days": off,
            "alias_direction": "historical" if off < 0 else "future",
        })
    # rank: exact before family, then closest analogous episode, then id
    out.sort(key=lambda c: (0 if c["tier"] == "exact" else 1,
                            abs(c["offset_days"]), c["article"]["article_id"]))
    return out


def type_b_candidates(pool, gt_event, gt_dt, alias, ticker, window_days):
    """Absence evidence: same ticker, topical, target event absent, not boilerplate."""
    out = []
    for a in pool:
        off = offset_days(a, gt_dt)
        if window_days is not None and abs(off) > window_days:
            continue
        if a["event_type"] == gt_event:
            continue
        if a["event_type"] in STRONG_EVENTS:
            continue                                    # could explain the episode
        if documents_event(a, gt_event):
            continue                                    # target mechanism present
        if BOILERPLATE_TITLE.search(a["title"]):
            continue                                    # generic wire boilerplate
        if len(a["content"]) < MIN_CONTENT_CHARS:
            continue
        if len(a["tickers"]) > MAX_TICKERS_FOR_FOCUS:
            continue                                    # multi-ticker roundup
        ent = entity_check(ticker, a["title"], a["content"], alias)
        if not ent["entity_mentioned"]:
            continue
        out.append({
            "article": a, "offset_days": off, "entity": ent,
            "topical_relation": "same ticker, company-level %s coverage"
                                % a["event_type"],
        })
    # rank: title-level topicality, then temporal proximity, then id
    out.sort(key=lambda c: (0 if c["entity"]["entity_in_title"] else 1,
                            abs(c["offset_days"]), c["article"]["article_id"]))
    return out


def alias_map_from(df):
    return build_alias_map(df["title"])


def specific_aliases(ticker, alias):
    """Aliases usable for cross-company mention detection (no generic suffixes)."""
    out = []
    for name in names_for(ticker, alias):
        if name == ticker:
            continue
        parts = name.split()
        if len(parts) > 1:
            out.append(name)
        elif len(name) >= 4 and name.lower() not in GENERIC_ALIAS:
            out.append(name)
    return out[:3]


def keyword_overlap(a, b):
    ka, kb = {k.lower() for k in a}, {k.lower() for k in b}
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / len(ka | kb)


def type_b_candidates_v2(gt_article, gt_event, gt_dt, ticker, alias, by_ticker,
                         corpus_rows, max_scan_other=None):
    """Absence evidence, corrected policy.

    Tier B1: same ticker, topically adjacent, target event absent.
    Tier B2: a DIFFERENT company whose article explicitly discusses the anchor
             company (the only closely-related-entity evidence this corpus
             supports), strongly topically adjacent, target event absent.
    Same ticker is preferred, never required.  No time window is imposed;
    temporal proximity is only a late ranking preference.
    """
    gt_keywords = gt_article.get("keywords", []) if gt_article else []

    def usable(a):
        if a["event_type"] == gt_event or a["event_type"] in STRONG_EVENTS:
            return False
        if documents_event(a, gt_event):
            return False
        if BOILERPLATE_TITLE.search(a["title"]):
            return False
        if len(a["content"]) < MIN_CONTENT_CHARS:
            return False
        if len(a["tickers"]) > MAX_TICKERS_FOR_FOCUS:
            return False
        return True

    out = []
    for a in by_ticker.get(ticker, []):
        if not usable(a):
            continue
        ent = entity_check(ticker, a["title"], a["content"], alias)
        if not ent["entity_mentioned"]:
            continue
        out.append({
            "article": a, "offset_days": offset_days(a, gt_dt),
            "entity_relation": "same_ticker",
            "entity_relation_evidence": "the article is tagged with the anchor ticker",
            "entity_in_title": ent["entity_in_title"],
            "keyword_overlap": keyword_overlap(gt_keywords, a.get("keywords", [])),
            "topical_relation": "same ticker, company-level %s coverage" % a["event_type"],
        })

    names = specific_aliases(ticker, alias)
    if names:
        pattern = re.compile("|".join(re.escape(n) for n in names), re.I)
        scanned = 0
        for a in corpus_rows:
            if ticker in a["tickers"]:
                continue
            if max_scan_other is not None and scanned >= max_scan_other:
                break
            scanned += 1
            hit_title = bool(pattern.search(a["title"]))
            hit_body = bool(pattern.search(a["content"][:2500]))
            if not (hit_title or hit_body):
                continue
            if not usable(a):
                continue
            out.append({
                "article": a, "offset_days": offset_days(a, gt_dt),
                "entity_relation": "closely_related_entity",
                "entity_relation_evidence":
                    "a %s article that explicitly discusses the anchor company (%s) "
                    "in its %s" % (a["tickers"][0] if a["tickers"] else "other",
                                   names[0], "title" if hit_title else "body"),
                "entity_in_title": hit_title,
                "keyword_overlap": keyword_overlap(gt_keywords, a.get("keywords", [])),
                "topical_relation": "related company coverage (%s) discussing the "
                                    "anchor company" % a["event_type"],
            })

    # 1 same ticker, 2 related entity, 3 topical similarity, 4 absence clarity
    # (entity named in title), 5 temporal proximity, 6 article id
    out.sort(key=lambda c: (0 if c["entity_relation"] == "same_ticker" else 1,
                            -c["keyword_overlap"],
                            0 if c["entity_in_title"] else 1,
                            abs(c["offset_days"]),
                            c["article"]["article_id"]))
    return out
