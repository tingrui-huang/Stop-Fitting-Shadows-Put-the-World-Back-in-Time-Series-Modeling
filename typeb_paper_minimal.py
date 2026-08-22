"""Paper-minimal Type-B policy plus a rejection audit for the unresolved anchors.

The paper asks only for "a topically adjacent article documenting no
corresponding target event".  The current pipeline adds several filters of our
own; this module separates the two so the cost of each heuristic is visible.

Rule provenance
  PAPER_REQUIRED          documents_target_event, is_gt_or_duplicate,
                          equally_valid_evidence, entity relevance (defensible)
  IMPLEMENTATION_HEURISTIC same_inferred_event_type, strong_event_class,
                          boilerplate_title, min_content_chars,
                          max_tickers_for_focus, entity_alias_mention_required

Preference tiers
  B1  same ticker (corpus tag) + target event absent
  B2  a different company's article that explicitly names the anchor company
  B3  a different article that explicitly names the anchor's ticker symbol
      (sector / peer / macro pieces that visibly implicate the anchor)
B2 and B3 always carry the matched textual evidence.  Nothing is admitted on an
assumed sector membership.
"""

import re

from distractor_policy import (BOILERPLATE_TITLE, MAX_TICKERS_FOR_FOCUS,
                               MIN_CONTENT_CHARS, STRONG_EVENTS, documents_event,
                               offset_days, specific_aliases)
from entity_alias import entity_check

PAPER_REQUIRED = {"documents_target_event", "is_gt_or_duplicate",
                  "entity_not_defensible"}
IMPLEMENTATION_HEURISTIC = {"same_inferred_event_type", "strong_event_class",
                            "boilerplate_title", "min_content_chars",
                            "max_tickers_for_focus", "entity_alias_mention_required"}


def ticker_symbol_evidence(ticker, article):
    """Textual evidence that the article explicitly names the anchor's ticker."""
    pattern = re.compile(r"[\(\s\"']%s[\)\s\.,;:\"']" % re.escape(ticker))
    for field in ("title", "content"):
        text = article[field]
        m = pattern.search(text if field == "title" else text[:4000])
        if m:
            start = max(0, m.start() - 70)
            return {"kind": "ticker_symbol_in_%s" % field,
                    "match": ticker,
                    "snippet": text[start:m.end() + 70].replace("\n", " ")}
    return None


def company_name_evidence(ticker, article, alias):
    names = specific_aliases(ticker, alias)
    if not names:
        return None
    pattern = re.compile("|".join(re.escape(n) for n in names), re.I)
    for field in ("title", "content"):
        text = article[field]
        m = pattern.search(text if field == "title" else text[:4000])
        if m:
            start = max(0, m.start() - 70)
            return {"kind": "company_name_in_%s" % field,
                    "match": m.group(0),
                    "snippet": text[start:m.end() + 70].replace("\n", " ")}
    return None


def evaluate(article, gt_article, gt_event, gt_dt, gt_title, ticker, alias):
    """-> record describing why the article passes or fails, under both policies."""
    rejections = []
    same_ticker = ticker in article["tickers"]

    if article["title"].strip() == gt_title.strip():
        rejections.append("is_gt_or_duplicate")
    if documents_event(article, gt_event):
        rejections.append("documents_target_event")

    # implementation-only filters, recorded separately
    if article["event_type"] == gt_event:
        rejections.append("same_inferred_event_type")
    if article["event_type"] in STRONG_EVENTS:
        rejections.append("strong_event_class")
    if BOILERPLATE_TITLE.search(article["title"]):
        rejections.append("boilerplate_title")
    if len(article["content"]) < MIN_CONTENT_CHARS:
        rejections.append("min_content_chars")
    if len(article["tickers"]) > MAX_TICKERS_FOR_FOCUS:
        rejections.append("max_tickers_for_focus")

    name_ev = company_name_evidence(ticker, article, alias)
    symbol_ev = ticker_symbol_evidence(ticker, article)
    if same_ticker:
        ent = entity_check(ticker, article["title"], article["content"], alias)
        if not ent["entity_mentioned"]:
            rejections.append("entity_alias_mention_required")

    if same_ticker:
        tier, evidence = "B1", {"kind": "corpus_ticker_tag", "match": ticker,
                                "snippet": "article is tagged with the anchor ticker"}
    elif name_ev:
        tier, evidence = "B2", name_ev
    elif symbol_ev:
        tier, evidence = "B3", symbol_ev
    else:
        tier, evidence = None, None
        rejections.append("entity_not_defensible")

    paper_blockers = [r for r in rejections if r in PAPER_REQUIRED]
    heuristic_blockers = [r for r in rejections if r in IMPLEMENTATION_HEURISTIC]

    return {
        "article_id": article["article_id"],
        "tickers": article["tickers"],
        "title": article["title"],
        "published_utc": article["published_utc"],
        "offset_days": round(offset_days(article, gt_dt), 2),
        "entity_relation": {"B1": "same_ticker", "B2": "anchor_company_named",
                            "B3": "anchor_ticker_named"}.get(tier),
        "entity_relation_evidence": evidence,
        "label_type_explicit": article["label_type"],
        "label_time_explicit": article["label_time"],
        "keywords_explicit": article["keywords"],
        "inferred_event_type": article["event_type"],
        "rejection_rules": rejections,
        "paper_required_blockers": paper_blockers,
        "implementation_only_blockers": heuristic_blockers,
        "passes_current_policy": not rejections,
        "passes_paper_minimal": not paper_blockers and tier is not None,
        "tier": tier,
        "blocked_only_by_heuristics": bool(heuristic_blockers) and not paper_blockers,
        "content_preview": article["content"][:280].replace("\n", " "),
    }


def paper_minimal_pool(records):
    """Ranked B candidates under the paper-minimal test: B1, then B2, then B3."""
    order = {"B1": 0, "B2": 1, "B3": 2}
    keep = [r for r in records if r["passes_paper_minimal"]]
    keep.sort(key=lambda r: (order[r["tier"]], abs(r["offset_days"]), r["article_id"]))
    return keep
