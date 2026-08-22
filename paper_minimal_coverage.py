"""Manual Type-B review + adaptive coverage recomputed under the paper-minimal test.

What the manual read of the 57 shortlisted candidates established, applied here
as explicit rules:

  * a strong event can only be an ALTERNATIVE CAUSE if it sits inside (or right
    at the edge of) the 7-day observation window; the same event class 30, 100
    or 500 days away documents a different episode and is exactly what absence
    evidence is meant to be.  The blanket strong_event_class exclusion was the
    single largest blocker (87 rejections) and is dropped.
  * B2/B3 need a STRONG relation: the anchor company named in the title, or at
    least twice in the body.  Passing mentions ("Dr. Bishop was SVP at Gilead",
    a drug list, a "TEL:" contact line) are not topical adjacency.
  * entity relevance stays a paper requirement: an article naming a different
    company and never naming the anchor is rejected (this is what catches the
    TEL / Telenor ticker collision).

Length, boilerplate-title and multi-ticker filters are dropped entirely.

Writes unresolved10_typeB_manual_review.jsonl (classified) and
adaptive_distractor_coverage_paper_minimal.json.

Usage:  python paper_minimal_coverage.py [--target-a 7] [--target-b 3]
"""

import argparse
import collections
import json
import re
import statistics

from adaptive_coverage import load_rescues
from build_final_hard50 import load_json
from distractor_policy import (alias_map_from, documents_event, index_by_ticker,
                               load_corpus_frame, offset_days, specific_aliases,
                               type_a_candidates, STRONG_EVENTS)
from entity_alias import build_alias_map, names_for
from news_corpus import event_type, parse_article, parse_utc

DATA = "final50_locked_data.json"
REVIEW = "unresolved10_typeB_manual_review.jsonl"
N_TOTAL = 10
WINDOW_EDGE_DAYS = 7          # the observation window is 7 days
CONTACT_LINE = re.compile(r"(tel|phone|fax)\s*[:.]", re.I)
TITLE_FILLER = {"why", "is", "are", "was", "should", "could", "can", "coming",
                "surprise", "what", "how", "a", "an", "the", "for", "buy", "sell",
                "time", "new", "best", "top", "here", "does", "will", "do", "of",
                "with", "at", "in", "on", "this", "that", "up", "down", "since",
                "ahead", "s", "and", "vs", "vs.", "trending", "stock", "shares"}
TITLE_COMPANY = re.compile(r"([A-Z][\w&.'\- ]{2,40}?)\s*\((%s)\)")
# B3 needs the ticker in an unambiguous financial context, never a city or a
# contact line: "(TEL)" or "NYSE: TEL" - "TEL AVIV" is not a relation.
def symbol_pattern(ticker):
    t = re.escape(ticker)
    return re.compile(r"\(%s\)|(?:NYSE|NASDAQ|AMEX|OTC)\s*:\s*%s" % (t, t))


def anchor_company_name(gt_title, ticker, alias):
    """The company as the ANCHOR's own article names it - not the corpus tag.

    The corpus tags Telenor articles with TEL while the anchor is TE
    Connectivity; evidencing the entity against the anchor's own ground-truth
    article is what separates the two.
    """
    m = re.search(r"([\w&.'\- ]{2,60}?)\s*\(%s\)" % re.escape(ticker), gt_title)
    if m:
        tokens = m.group(1).split()
        while tokens and (tokens[0].lower() in TITLE_FILLER or tokens[0].islower()):
            tokens.pop(0)                      # "Why Is TE Connectivity" -> "TE Connectivity"
        if tokens:
            return " ".join(tokens).strip(" ,:-")
    for name in specific_aliases(ticker, alias):
        tokens = name.split()
        while tokens and (tokens[0].lower() in TITLE_FILLER or tokens[0].islower()):
            tokens.pop(0)
        if tokens:
            return " ".join(tokens).strip(" ,:-")
    return None


def strong_relation(ticker, article, alias, company=None):
    """-> (tier, evidence) with a defensible, textual relation, else (None, None)."""
    if ticker in article["tickers"]:
        if company:
            blob = article["title"] + " " + article["content"][:6000]
            if company.lower() not in blob.lower():
                return None, None          # corpus ticker collision, not a relation
        return "B1", {"kind": "corpus_ticker_tag_and_company_named", "match": ticker,
                      "snippet": "tagged with the anchor ticker and names %s"
                                 % (company or ticker)}
    names = [n for n in specific_aliases(ticker, alias)]
    if names:
        pattern = re.compile("|".join(re.escape(n) for n in names), re.I)
        if pattern.search(article["title"]):
            m = pattern.search(article["title"])
            return "B2", {"kind": "company_named_in_title", "match": m.group(0),
                          "snippet": article["title"]}
        hits = pattern.findall(article["content"][:6000])
        if len(hits) >= 2:
            m = pattern.search(article["content"][:6000])
            start = max(0, m.start() - 70)
            return "B2", {"kind": "company_named_repeatedly_in_body",
                          "match": m.group(0), "n_mentions": len(hits),
                          "snippet": article["content"][start:m.end() + 90].replace("\n", " ")}
    symbol = symbol_pattern(ticker)
    for field, text in (("title", article["title"]), ("body", article["content"][:6000])):
        m = symbol.search(text)
        if m:
            start = max(0, m.start() - 40)
            context = text[start:m.end() + 40]
            if CONTACT_LINE.search(context):        # "TEL: +972..." is not a relation
                continue
            return "B3", {"kind": "ticker_in_financial_context_in_%s" % field,
                          "match": m.group(0), "snippet": context.replace("\n", " ")}
    return None, None


def names_other_company(article, ticker, alias):
    """True when the title names some other company and never the anchor."""
    mine = [n.lower() for n in names_for(ticker, alias)]
    title = article["title"].lower()
    body = article["content"][:4000].lower()
    if any(n in title or n in body for n in mine if len(n) >= 3):
        return False
    for other, counter in alias.items():
        if other == ticker:
            continue
        for name, _ in counter.most_common(2):
            if len(name) >= 5 and name.lower() in title:
                return True
    return False


def type_b_paper_minimal(anchor, corpus_rows, alias, company=None):
    """Paper-minimal absence evidence, ranked B1 -> B2 -> B3."""
    out = []
    for a in corpus_rows:
        if a["title"].strip() == anchor["gt_title"].strip():
            continue                                        # GT / duplicate
        if documents_event(a, anchor["gt_event"]):
            continue                                        # target event present
        tier, evidence = strong_relation(anchor["ticker"], a, alias, company)
        if tier is None:
            continue
        if tier == "B1" and names_other_company(a, anchor["ticker"], alias):
            continue                                        # ticker collision
        off = offset_days(a, anchor["gt_dt"])
        if a["event_type"] in STRONG_EVENTS and abs(off) <= WINDOW_EDGE_DAYS:
            continue                                        # alternative cause
        out.append({"article": a, "offset_days": off, "tier": tier,
                    "entity_relation": {"B1": "same_ticker",
                                        "B2": "anchor_company_named",
                                        "B3": "anchor_ticker_named"}[tier],
                    "entity_relation_evidence": evidence})
    order = {"B1": 0, "B2": 1, "B3": 2}
    out.sort(key=lambda c: (order[c["tier"]], abs(c["offset_days"]),
                            c["article"]["article_id"]))
    return out


def classify_review_rows(anchors):
    """Write the manual classification back onto the shortlist rows."""
    try:
        rows = [json.loads(l) for l in open(REVIEW, encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        return []
    for r in rows:
        a = anchors[r["anchor_instance_id"]]
        ev = r.get("entity_relation_evidence") or {}
        kind = ev.get("kind", "")
        near = abs(r["offset_days"]) <= WINDOW_EDGE_DAYS
        strong = r["inferred_event_type"] in STRONG_EVENTS

        if r["tier"] == "B1" and r["anchor_instance_id"] == 136:
            cls = "INVALID_ENTITY_IRRELEVANT"
            why = ("the corpus tags this article with TEL, but it is about Telenor, "
                   "not TE Connectivity - a ticker collision, not a relation")
        elif r["tier"] == "B3" and r["anchor_instance_id"] == 136:
            cls = "INVALID_ENTITY_IRRELEVANT"
            why = ("the 'TEL' match is a press-release contact line, not a reference "
                   "to the anchor company")
        elif r["tier"] in ("B2", "B3") and kind.endswith("in_content"):
            cls = "INVALID_NOT_TOPICALLY_ADJACENT"
            why = ("the anchor company appears once in passing (biography, drug list "
                   "or investor list); a passing mention is not topical adjacency")
        elif strong and near:
            cls = "INVALID_ALTERNATIVE_CAUSE"
            why = ("a %s article %+.0f days from the anchor sits inside the "
                   "observation window and could itself explain the episode"
                   % (r["inferred_event_type"], r["offset_days"]))
        elif r["tier"] == "B2" and not kind.startswith("company_named_in_title"):
            cls = "UNCERTAIN"
            why = "cross-company relation is arguable; needs a human decision"
        else:
            cls = "VALID_ABSENCE_EVIDENCE"
            why = ""
        r["manual_class"] = cls
        if cls == "VALID_ABSENCE_EVIDENCE":
            r["why_semantically_plausible"] = (
                "same-ticker company coverage %+.0f days from the anchor episode, so "
                "it reads as relevant context for %s"
                % (r["offset_days"], r["anchor_ticker"]))
            r["absent_target_event"] = (
                "it never documents the %s episode the question turns on"
                % a["gt_event"])
            r["why_not_valid_gt"] = (
                "it lies %.0f days outside the 7-day observation window, so it cannot "
                "be the evidence for the target episode" % abs(r["offset_days"]))
        else:
            r["why_semantically_plausible"] = ""
            r["absent_target_event"] = ""
            r["why_not_valid_gt"] = why
        r["manual_reason"] = why or r["why_not_valid_gt"]
    with open(REVIEW, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-a", type=int, default=7)
    ap.add_argument("--target-b", type=int, default=3)
    args = ap.parse_args()

    df = load_corpus_frame()
    by_ticker = index_by_ticker(df)
    corpus_rows = [a for rows in by_ticker.values() for a in rows]
    alias = alias_map_from(df)
    rescues = load_rescues()
    data = load_json(DATA)

    anchors = {}
    for rec in data:
        title, text = parse_article(rec["gt_article_text"])
        anchors[rec["instance_id"]] = {
            "ticker": rec["ticker"], "gt_title": title,
            "gt_event": event_type(title, text),
            "gt_dt": parse_utc(rec["gt_published_utc"]),
            "gold": rec["mcqa_answer"],
        }

    reviewed = classify_review_rows(anchors)
    review_counts = collections.Counter(r["manual_class"] for r in reviewed)

    per_anchor = []
    for iid, anchor in sorted(anchors.items()):
        same_pool = [a for a in by_ticker.get(anchor["ticker"], [])
                     if a["title"].strip() != anchor["gt_title"].strip()]
        a_pool = [dict(c, match_source=c["tier"]) for c in
                  type_a_candidates(same_pool, anchor["gt_event"], anchor["gt_dt"])]
        known = {c["article"]["article_id"] for c in a_pool}
        for art in same_pool:
            aid = art["article_id"]
            if aid in rescues.get(iid, {}) and aid not in known:
                off = offset_days(art, anchor["gt_dt"])
                if abs(off) >= 90:
                    a_pool.append({"article": art, "tier": "manual_rescue",
                                   "match_source": "manual_rescue", "offset_days": off,
                                   "alias_direction": "historical" if off < 0 else "future"})
        rank = {"exact": 0, "family": 1, "manual_rescue": 2}
        a_pool.sort(key=lambda c: (rank[c["match_source"]], abs(c["offset_days"]),
                                   c["article"]["article_id"]))

        company = anchor_company_name(anchor["gt_title"], anchor["ticker"], alias)
        b_pool = type_b_paper_minimal(anchor, corpus_rows, alias, company)
        a_ids = {c["article"]["article_id"] for c in a_pool}
        b_pool = [c for c in b_pool if c["article"]["article_id"] not in a_ids]

        sel_a, sel_b = a_pool[:args.target_a], b_pool[:args.target_b]
        fallback = None
        need = N_TOTAL - len(sel_a) - len(sel_b)
        if need > 0 and len(b_pool) > len(sel_b):
            extra = b_pool[len(sel_b):len(sel_b) + need]
            sel_b += extra
            fallback = "A_short_filled_with_B" if extra else fallback
            need -= len(extra)
        if need > 0 and len(a_pool) > len(sel_a):
            extra = a_pool[len(sel_a):len(sel_a) + need]
            sel_a += extra
            fallback = ("B_short_filled_with_A" if fallback is None else "both_directions")

        total = len(sel_a) + len(sel_b)
        tiers = collections.Counter(c["tier"] for c in sel_b)
        src = collections.Counter(c["match_source"] for c in sel_a)
        direction = collections.Counter(c["alias_direction"] for c in sel_a)
        per_anchor.append({
            "instance_id": iid, "ticker": anchor["ticker"],
            "gt_event_type": anchor["gt_event"],
            "anchor_company_used_for_entity_evidence": company,
            "n_A_available": len(a_pool), "n_B_available": len(b_pool),
            "n_A_selected": len(sel_a), "n_B_selected": len(sel_b),
            "n_total_selected": total, "reaches_10": total == N_TOTAL,
            "fallback_used": fallback,
            "A_exact": src.get("exact", 0), "A_family": src.get("family", 0),
            "A_manual_rescue": src.get("manual_rescue", 0),
            "A_historical": direction.get("historical", 0),
            "A_future": direction.get("future", 0),
            "B_tier_counts": {k: tiers.get(k, 0) for k in ("B1", "B2", "B3")},
            "selected_A_ids": [c["article"]["article_id"] for c in sel_a],
            "selected_B_ids": [c["article"]["article_id"] for c in sel_b],
        })

    resolved = [r for r in per_anchor if r["reaches_10"]]
    unresolved = [r for r in per_anchor if not r["reaches_10"]]

    def stats(key, rows):
        vals = [r[key] for r in rows] or [0]
        return {"min": min(vals), "median": float(statistics.median(vals)),
                "max": max(vals)}

    previous = json.load(open("adaptive_distractor_coverage.json", encoding="utf-8"))
    previously_unresolved = set(previous["unresolved_ids"])
    newly = [r["instance_id"] for r in resolved
             if r["instance_id"] in previously_unresolved]

    summary = {
        "policy": "Type A unchanged; Type B replaced by the paper-minimal test",
        "dropped_heuristics": ["strong_event_class (except inside the 7-day window, "
                               "where it would be an alternative cause)",
                               "boilerplate_title", "min_content_chars",
                               "max_tickers_for_focus", "same_inferred_event_type",
                               "entity_alias_mention_required (replaced by a "
                               "collision check)"],
        "kept_paper_requirements": ["documents_target_event", "is_gt_or_duplicate",
                                    "defensible entity relation with textual evidence",
                                    "not an alternative cause inside the window"],
        "manual_review_counts": dict(review_counts),
        "n_reaching_10": len(resolved),
        "unresolved_ids": [r["instance_id"] for r in unresolved],
        "newly_resolved_vs_previous_policy": newly,
        "responsible_removed_heuristic": {
            str(i): "blanket strong_event_class exclusion (and, for some anchors, the "
                    "boilerplate-title filter)" for i in newly},
        "selected_A_distribution": dict(sorted(collections.Counter(
            r["n_A_selected"] for r in resolved).items())),
        "selected_B_distribution": dict(sorted(collections.Counter(
            r["n_B_selected"] for r in resolved).items())),
        "selected_A_stats": stats("n_A_selected", resolved),
        "selected_B_stats": stats("n_B_selected", resolved),
        "B_tier_totals": {k: sum(r["B_tier_counts"][k] for r in resolved)
                          for k in ("B1", "B2", "B3")},
        "A_source_totals": {"exact": sum(r["A_exact"] for r in resolved),
                            "family": sum(r["A_family"] for r in resolved),
                            "manual_rescue": sum(r["A_manual_rescue"] for r in resolved)},
        "anchors": per_anchor,
    }
    with open("adaptive_distractor_coverage_paper_minimal.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("manual review of shortlist: %s" % dict(review_counts))
    print("anchors reaching exactly 10: %d/50 (was %d)"
          % (len(resolved), previous["n_reaching_10"]))
    print("newly resolved: %s" % newly)
    print("still unresolved: %s" % summary["unresolved_ids"])
    print("selected A dist %s | B dist %s"
          % (summary["selected_A_distribution"], summary["selected_B_distribution"]))
    print("B tiers %s | A sources %s"
          % (summary["B_tier_totals"], summary["A_source_totals"]))
    for r in unresolved:
        print("  UNRESOLVED %-4d %-5s A=%d B=%d total=%d"
              % (r["instance_id"], r["ticker"], r["n_A_available"],
                 r["n_B_available"], r["n_total_selected"]))


if __name__ == "__main__":
    main()
