"""Resolve the 10 distractor slots per pilot anchor from the local article corpus.

Slot taxonomy (per anchor): 6 x temporal_aliasing, 2 x near_time_competing,
1 x future_retrospective, 1 x absence_no_valid_cause.

Every candidate is a real article from the local corpus (see news_corpus.py):
exact text, exact publication timestamp, provenance id kept.  Nothing is
generated, rewritten or re-dated.  A slot that no real article can fill under
its constraints stays UNRESOLVED and is reported with the reason - it is never
padded with a weaker candidate.

Writes pilot10_distractors.jsonl (one line per slot, resolved or not) and
pilot10_distractor_manifest.json (per-anchor summary + corpus diagnostics).

Usage:  python build_pilot_distractors.py
"""

import json

from build_final_hard50 import load_json
from news_corpus import event_type, load_corpus, parse_article, parse_utc

SLOTS = ([("temporal_aliasing", i) for i in range(1, 7)]
         + [("near_time_competing", i) for i in range(7, 9)]
         + [("future_retrospective", 9)]
         + [("absence_no_valid_cause", 10)])

ALIAS_MIN_OFFSET_DAYS = 90     # wrong world episode, per the pilot spec
NEAR_TIME_MAX_DAYS = 30        # "close in time" for competing evidence
ABSENCE_MIN_DAYS = 30          # keep absence slots away from the near-time band

# Event types that cannot by themselves explain a price episode for the anchor.
NON_EXPLANATORY = {"executive", "dividend_buyback", "product_launch", "other"}


def days(a, b):
    return (a - b).total_seconds() / 86400.0


def candidates_for(anchor, corpus, used):
    """Same-ticker, non-GT, unused articles - the only pool the spec allows."""
    return [a for a in corpus.values()
            if a["ticker"] == anchor["ticker"]
            and a["article_id"] != anchor["gt_article_id"]
            and a["title"] != anchor["gt_title"]
            and a["article_id"] not in used]


def rank(kind, anchor, cands):
    """Deterministic ordering of eligible candidates for a slot kind."""
    gt = anchor["gt_dt"]
    out = []
    for a in cands:
        off = days(a["published_dt"], gt)
        same_event = a["event_type"] == anchor["gt_event_type"]
        if kind == "temporal_aliasing":
            if abs(off) < ALIAS_MIN_OFFSET_DAYS or not same_event:
                continue
            key = (0, abs(off), a["article_id"])
        elif kind == "near_time_competing":
            if abs(off) > NEAR_TIME_MAX_DAYS or same_event or off > 0:
                continue
            key = (0, abs(off), a["article_id"])
        elif kind == "future_retrospective":
            if off <= 0:
                continue
            key = (0 if same_event else 1, abs(off), a["article_id"])
        elif kind == "absence_no_valid_cause":
            if same_event or a["event_type"] not in NON_EXPLANATORY \
                    or abs(off) < ABSENCE_MIN_DAYS:
                continue
            key = (0, abs(off), a["article_id"])
        else:
            raise ValueError(kind)
        out.append((key, a))
    return [a for _, a in sorted(out, key=lambda t: t[0])]


def why_unresolved(kind, anchor, pool):
    n = len(pool)
    if n == 0:
        return ("no other article for ticker %s exists in the local corpus "
                "(%d articles total)" % (anchor["ticker"], anchor["n_corpus"]))
    detail = {
        "temporal_aliasing": "same ticker + same event type (%s) + |offset| >= %dd"
                             % (anchor["gt_event_type"], ALIAS_MIN_OFFSET_DAYS),
        "near_time_competing": "same ticker + different event type + within %dd before GT"
                               % NEAR_TIME_MAX_DAYS,
        "future_retrospective": "same ticker + published after the GT article",
        "absence_no_valid_cause": "same ticker + non-explanatory event type + |offset| >= %dd"
                                  % ABSENCE_MIN_DAYS,
    }[kind]
    return ("no same-ticker article satisfies %s; %d same-ticker candidate(s) "
            "available and none qualify" % (detail, n))


def main():
    corpus = load_corpus(load_json)
    pilot = load_json("pilot10_data.json")
    ids = json.load(open("pilot10_ids.json", encoding="utf-8"))
    challenge = set(ids["challenge_ids"])

    records, per_anchor = [], []
    for rec in pilot:
        title, text = parse_article(rec["gt_article_text"])
        gt_id = next((a["article_id"] for a in corpus.values()
                      if a["title"] == title), None)
        anchor = {
            "instance_id": rec["instance_id"],
            "ticker": rec["ticker"],
            "gt_article_id": gt_id,
            "gt_title": title,
            "gt_published_utc": rec["gt_published_utc"],
            "gt_dt": parse_utc(rec["gt_published_utc"]),
            "gt_event_type": event_type(title, text),
            "n_corpus": len(corpus),
        }

        used, resolved, unresolved = set(), 0, []
        pool_all = candidates_for(anchor, corpus, set())
        for kind, slot in SLOTS:
            pool = candidates_for(anchor, corpus, used)
            ranked = rank(kind, anchor, pool)
            row = {
                "anchor_instance_id": anchor["instance_id"],
                "anchor_ticker": anchor["ticker"],
                "gt_article_id": anchor["gt_article_id"],
                "gt_published_utc": anchor["gt_published_utc"],
                "event_type_gt": anchor["gt_event_type"],
                "distractor_slot": slot,
                "distractor_type": kind,
                "resolved": False,
                "distractor_article_id": None,
                "distractor_ticker": None,
                "distractor_published_utc": None,
                "event_type_distractor": None,
                "time_offset_days": None,
                "same_ticker": None,
                "same_or_similar_event_type": None,
                "temporally_admissible": None,
                "hardness_reason": None,
                "source": None,
                "manual_review_required": True,
                "notes": "",
            }
            if ranked:
                a = ranked[0]
                used.add(a["article_id"])
                off = days(a["published_dt"], anchor["gt_dt"])
                row.update({
                    "resolved": True,
                    "distractor_article_id": a["article_id"],
                    "distractor_ticker": a["ticker"],
                    "distractor_published_utc": a["published_utc"],
                    "event_type_distractor": a["event_type"],
                    "time_offset_days": round(off, 2),
                    "same_ticker": a["ticker"] == anchor["ticker"],
                    "same_or_similar_event_type":
                        a["event_type"] == anchor["gt_event_type"],
                    "temporally_admissible": off <= 0,
                    "hardness_reason": {
                        "temporal_aliasing":
                            "same ticker, same event type, %.0f days from the GT "
                            "episode: stays plausible once dates are masked"
                            % abs(off),
                        "near_time_competing":
                            "same ticker, %.0f days before the GT article, different "
                            "mechanism (%s vs %s): nearest-timestamp heuristic alone "
                            "does not solve it" % (abs(off), a["event_type"],
                                                   anchor["gt_event_type"]),
                        "future_retrospective":
                            "same ticker, published %.0f days AFTER the GT article: "
                            "topically tempting but unavailable at the episode"
                            % off,
                        "absence_no_valid_cause":
                            "same ticker, topically adjacent (%s) but documents no "
                            "mechanism able to explain the episode" % a["event_type"],
                    }[kind],
                    "source": "%s (instance %d GT article, verbatim)"
                              % (a["dataset"], a["source_instance_id"]),
                    "manual_review_required": True,
                    "notes": "auto-selected by rule; needs human confirmation that "
                             "it does not create a second valid answer",
                })
                resolved += 1
            else:
                row["notes"] = why_unresolved(kind, anchor, pool)
                unresolved.append({"slot": slot, "type": kind, "reason": row["notes"]})
            records.append(row)

        per_anchor.append({
            "instance_id": anchor["instance_id"],
            "ticker": anchor["ticker"],
            "challenge_anchor": anchor["instance_id"] in challenge,
            "gt_article_id": anchor["gt_article_id"],
            "gt_published_utc": anchor["gt_published_utc"],
            "gt_event_type": anchor["gt_event_type"],
            "n_resolved": resolved,
            "n_unresolved": 10 - resolved,
            "unresolved_slots": unresolved,
            "corpus_diagnostics": {
                "same_ticker_articles_available": len(pool_all),
                "same_ticker_same_event": sum(
                    1 for a in pool_all if a["event_type"] == anchor["gt_event_type"]),
                "same_ticker_offset_ge_90d": sum(
                    1 for a in pool_all
                    if abs(days(a["published_dt"], anchor["gt_dt"])) >= 90),
                "same_event_any_ticker": sum(
                    1 for a in corpus.values()
                    if a["event_type"] == anchor["gt_event_type"]
                    and a["article_id"] != anchor["gt_article_id"]),
            },
        })

    with open("pilot10_distractors.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    n_res = sum(r["resolved"] for r in records)
    manifest = {
        "corpus": {
            "files": ["c0_data.json", "hard50_data.json"],
            "n_articles": len(corpus),
            "n_tickers": len({a["ticker"] for a in corpus.values()}),
            "note": "the only real finance-news articles available locally are the "
                    "ground-truth articles of these two datasets; no MTBench "
                    "finance_news corpus is present in this repository or on this "
                    "machine, so same-ticker history is at most 3 articles deep",
        },
        "slot_taxonomy": {"temporal_aliasing": 6, "near_time_competing": 2,
                          "future_retrospective": 1, "absence_no_valid_cause": 1},
        "constraints": {
            "same_ticker_required": True,
            "temporal_aliasing_min_offset_days": ALIAS_MIN_OFFSET_DAYS,
            "near_time_max_days": NEAR_TIME_MAX_DAYS,
            "absence_min_offset_days": ABSENCE_MIN_DAYS,
            "fabrication": "not permitted; unfillable slots stay unresolved",
        },
        "totals": {"n_slots": len(records), "n_resolved": n_res,
                   "n_unresolved": len(records) - n_res},
        "anchors": per_anchor,
    }
    with open("pilot10_distractor_manifest.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("corpus: %d real articles, %d tickers" % (len(corpus),
          len({a["ticker"] for a in corpus.values()})))
    print("slots: %d resolved / %d total\n" % (n_res, len(records)))
    for a in per_anchor:
        d = a["corpus_diagnostics"]
        print("  %-4d %-5s %-16s resolved %2d/10 | same-ticker articles %d "
              "(same event %d, >=90d %d)"
              % (a["instance_id"], a["ticker"], a["gt_event_type"], a["n_resolved"],
                 d["same_ticker_articles_available"], d["same_ticker_same_event"],
                 d["same_ticker_offset_ge_90d"]))
    print("\nwrote pilot10_distractors.jsonl and pilot10_distractor_manifest.json")


if __name__ == "__main__":
    main()
