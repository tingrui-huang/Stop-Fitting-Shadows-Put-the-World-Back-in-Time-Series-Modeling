"""All-50 grounding audit (Part A) and post-publication semantics audit (Part B).

Diagnostic only.  Reads the frozen benchmark, the frozen rendered prompts and
the frozen Sonnet-5 outputs; writes only into results/.  Nothing is rebuilt, no
inference is run, no instance is excluded.

Two kinds of information are combined:

  mechanical   article roles, offsets, tiers, time-series geometry, price-level
               matching - all re-derived here from the frozen files

  annotated    which articles a rationale actually leans on, and what each MCQA
               option requires temporally - hand-read from the 100 rationales
               and 200 options, recorded below with a short reason each

The annotations are separated from the mechanics on purpose: every count in the
report is a function of the two, and either can be checked independently.

Usage:  python analyze_grounding_all50.py
"""

import argparse
import datetime as dt
import json
import re

UTC = dt.timezone.utc

# ==========================================================================
# PART A annotations - what each rationale actually leans on
# ==========================================================================
# Positions the rationale explicitly builds its argument on (article number as
# rendered).  An article listed in evidence_articles but never touched by the
# rationale is *not* here; it is reported as "listed_without_discussion".
ATTRIBUTED = {
    "C1": {
        15: [9], 18: [10], 35: [1, 7], 37: [7], 41: [1], 47: [5], 49: [7],
        50: [3], 51: [6], 53: [9], 55: [3], 61: [7], 66: [2], 96: [], 98: [],
        120: [4], 123: [7], 124: [7], 133: [10], 140: [6], 147: [10], 148: [8],
        172: [1], 176: [], 182: [7], 191: [11], 201: [6], 215: [1], 233: [7],
        234: [3], 252: [11], 256: [3], 265: [8], 268: [9], 274: [9], 275: [5],
        288: [7], 295: [6], 303: [1], 313: [10], 317: [2], 320: [9], 334: [10],
        353: [11], 371: [1], 405: [4], 441: [2], 453: [7], 454: [5], 484: [3],
    },
    "C2": {
        15: [11], 18: [10], 35: [1, 5, 7, 9, 6], 37: [7], 41: [1], 47: [5],
        49: [7], 50: [], 51: [1, 6], 53: [9], 55: [3], 61: [7], 66: [2],
        96: [], 98: [], 120: [4], 123: [7], 124: [7], 133: [10], 140: [],
        147: [10], 148: [8], 172: [1], 176: [3], 182: [7], 191: [11],
        201: [3], 215: [1], 233: [7], 234: [3], 252: [11], 256: [3],
        265: [7, 10, 8], 268: [9], 274: [9], 275: [5], 288: [7], 295: [],
        303: [1], 313: [], 317: [], 320: [9], 334: [10], 353: [], 371: [],
        405: [4], 441: [6], 453: [7], 454: [5], 484: [3],
    },
}

# Articles a rationale explicitly rejects as support.  None were found: no
# rationale in either condition names an article and then discards it.
REJECTED = {"C1": {}, "C2": {}}

ATTRIBUTION_NOTES = {
    (15, "C2"): "argument runs entirely through Article 11 (absence evidence); "
                "the GT is listed but never used",
    (35, "C2"): "no article named individually - the rationale credits 'the news "
                "articles' collectively, so the whole declared set is attributed",
    (51, "C2"): "'Articles 1 and 6 report Micron's earnings' - Article 1 is a "
                "+176 day alias, Article 6 is the GT",
    (96, "C1"): "argument is purely about the last time-series value; the listed "
                "GT article is never used",
    (96, "C2"): "no article listed and none discussed",
    (176, "C1"): "argument is a numeric comparison against the series; 'news "
                 "content' is invoked only in passing",
    (176, "C2"): "the price drop is attributed to Article 3, a +650 day alias",
    (201, "C2"): "Article 3, a -398 day alias, supplies the premise of the "
                 "contrast that the conclusion turns on",
    (265, "C2"): "the rise is attributed to 'the Q4 earnings beat ... discussed "
                 "in Article 7/10', both aliases; Article 8 (GT) supports a "
                 "separate point about option B",
    (317, "C2"): "four articles listed, none mentioned; the argument is a general "
                 "claim about how analyst ratings work",
    (371, "C2"): "two articles listed, neither mentioned; the argument is about "
                 "the absolutism of option A",
    (441, "C2"): "the only cited article is absence evidence; no GT",
}

# ==========================================================================
# PART B annotations - temporal requirement of each MCQA option
# ==========================================================================
# NPC  NO_POST_PUBLICATION_CLAIM
# PPB  POST_PUBLICATION_BEHAVIOR_CLAIM
# PRC  PUBLICATION_RELATIVE_COMPARISON
# ADC  ABSOLUTE_DATE_CLAIM
# ATR  AMBIGUOUS_TEMPORAL_REQUIREMENT
#
# fields: (A, B, C, D), instance_class, gold_reliance, in_window_mislabelled, note
SUFFICIENT = "INPUT_WINDOW_SUFFICIENT"
REQUIRED = "POST_PUBLICATION_EVIDENCE_REQUIRED"
PARTIAL = "PARTIALLY_UNDERDETERMINED"
AMBIGUOUS = "TEMPORAL_SEMANTICS_AMBIGUOUS"

OPTIONS = {
    15: (("NPC", "PPB", "NPC", "PPB"), SUFFICIENT, "none", False,
         "gold C is a valuation statement from the article; B and D carry "
         "post-publication presuppositions but both fail on their own content "
         "('P/E ratios do not matter', 'unlikely that any buyers would emerge')"),
    18: (("NPC", "NPC", "NPC", "PPB"), PARTIAL, "none", False,
         "gold C is a claim about the pre-news series and is checkable, but D "
         "asserts a sharp drop after publication and is a live competitor for "
         "'the incorrect statement'; deciding C over D needs post-publication data"),
    35: (("PPB", "NPC", "NPC", "NPC"), SUFFICIENT, "none", False,
         "gold C states the in-window trend and is directly verifiable; A is "
         "unverifiable but the question asks which statement is correct"),
    37: (("PPB", "NPC", "NPC", "PPB"), PARTIAL, "partial", True,
         "gold A says the price fell 'after the news publication'; the fall is "
         "in the window and ends at publication, and the GT article reports the "
         "same-day 6.6% drop, so the substance is available but the label is not"),
    41: (("NPC", "NPC", "PPB", "ADC"), SUFFICIENT, "none", False,
         "gold B is false on article content (estimates were revised up 34.78%)"),
    47: (("PPB", "PPB", "NPC", "PPB"), REQUIRED, "required", False,
         "gold B asserts increased volatility 'since the 2021-07-16 timestamp'; "
         "the window ends 2021-07-15 19:55, 17.2 h before publication, so the "
         "evidence it names does not exist in the supplied input"),
    49: (("PPB", "PPB", "PPB", "NPC"), PARTIAL, "partial", True,
         "gold A (the incorrect statement) claims the price rose after the "
         "downgrade; the ~10% fall is in-window and the article reports it, but "
         "A, B and C all describe in-window movement as 'following the news'"),
    50: (("PPB", "NPC", "ADC", "NPC"), SUFFICIENT, "none", False,
         "gold C is an in-window decline with an explicit date, fully checkable"),
    51: (("NPC", "NPC", "NPC", "NPC"), SUFFICIENT, "none", False,
         "no option requires post-publication observation; gold C is article "
         "content about the quarter's results"),
    53: (("PPB", "NPC", "PPB", "PPB"), PARTIAL, "partial", True,
         "gold A reads the decline as post-announcement hesitation; the decline "
         "is in-window and 10.1 h before publication, but the dilution reading "
         "that distinguishes A from B/C/D comes from the article"),
    55: (("NPC", "NPC", "PPB", "PPB"), PARTIAL, "partial", True,
         "gold C's levels ($375.89, below $374) both occur at the very end of "
         "the window (98% and 100%), i.e. at or just before publication, not "
         "after it"),
    61: (("PPB", "PPB", "NPC", "PPB"), PARTIAL, "partial", False,
         "gold B (incorrect) claims a sharp post-news drop below $89; sub-$89 "
         "prices occur at 1-56% of the window, not at the end, and the article "
         "reports the stock rose - so the falsity is reachable, but only via "
         "article content"),
    66: (("NPC", "PPB", "NPC", "PPB"), SUFFICIENT, "none", False,
         "gold C is the reaffirmed fiscal-2023 outlook, straight from the article"),
    96: (("NPC", "NPC", "PPB", "PPB"), PARTIAL, "partial", False,
         "option C names $147.61, a level absent from the supplied window, and "
         "dates it 'following the news publication on November 12' while the "
         "window ends 2021-11-11 20:55; C is a live competitor for 'incorrect'"),
    98: (("PPB", "PRC", "PPB", "ADC"), PARTIAL, "partial", True,
         "gold D's shape (peak 25.67 then decline to 25.25) is in the window at "
         "8-53% and 76-89%, but its date labels (Sept 29 to Sept 30) fall at or "
         "past the window end - the label is recoverable from shape alone"),
    120: (("NPC", "PPB", "PPB", "NPC"), SUFFICIENT, "none", True,
          "gold B is false on article content (Zacks Rank 3 means in line, not "
          "underperform); option C calls the last in-window interval 'the first "
          "recorded interval after the announcement'"),
    123: (("NPC", "NPC", "PPB", "PPB"), PARTIAL, "partial", True,
          "gold A ties the article's caution to 'the observed downward trend "
          "post-announcement'; that downward trend is entirely in-window"),
    124: (("NPC", "PPB", "PPB", "NPC"), PARTIAL, "partial", False,
          "gold B (incorrect) claims a significant fall after the Q2 call; the "
          "call publishes 2.1 h after the window ends, so no post-call price "
          "exists - the falsity rests on the article's reported results"),
    133: (("NPC", "PPB", "PPB", "NPC"), SUFFICIENT, "none", False,
          "gold A is explicitly about sentiment *prior to* the news release"),
    140: (("PPB", "PPB", "NPC", "PPB"), PARTIAL, "partial", True,
          "gold B says the price 'opened at 13.11' on Aug 26 after publication; "
          "13.11 occurs at 75-98% of the window, i.e. on Aug 25, 13.2 h before "
          "the article published"),
    147: (("PPB", "PPB", "PPB", "NPC"), SUFFICIENT, "none", False,
          "gold D is the analyst target of $389.8, taken from the article"),
    148: (("PPB", "NPC", "PPB", "NPC"), PARTIAL, "partial", False,
          "option A names $98.27 on June 24 - a level absent from the window and "
          "a date after both the window end and publication; gold C's clause "
          "'may justify the post-news price increase' is also post-publication"),
    172: (("NPC", "NPC", "NPC", "PPB"), SUFFICIENT, "none", False,
          "gold A is the $7.9 billion revenue figure from the article"),
    176: (("PRC", "PPB", "PPB", "NPC"), REQUIRED, "required", False,
          "gold A (the incorrect statement) compares the average price after "
          "publication with the average before it; publication is 16.4 h after "
          "the window ends, so the post-publication average does not exist and "
          "the comparison cannot be evaluated at all"),
    182: (("NPC", "PPB", "NPC", "NPC"), SUFFICIENT, "none", False,
          "gold A is a plausibility statement about the award's effect"),
    191: (("NPC", "NPC", "PPB", "NPC"), SUFFICIENT, "none", False,
          "gold B is the 24% two-year-stack e-commerce figure from the article"),
    201: (("NPC", "PPB", "PPB", "NPC"), REQUIRED, "required", False,
          "gold B asserts a rebound of over 2% 'within the first trading session "
          "after the news release'; the article publishes 2022-12-01 23:00 and "
          "the window ends 20:55, so the first post-news session is absent"),
    215: (("PPB", "NPC", "PPB", "PPB"), PARTIAL, "partial", False,
          "gold C (incorrect) claims an immediate drop below 208.00; 208 is "
          "touched at 50-86% of the window and not at the end, so the falsity is "
          "reachable, but A and D both assert post-publication rises"),
    233: (("NPC", "NPC", "NPC", "PPB"), PARTIAL, "partial", False,
          "gold B (incorrect) claims a >1% fall 'in the immediate aftermath'; "
          "publication is 4 minutes after the window ends"),
    234: (("PPB", "PPB", "NPC", "PPB"), REQUIRED, "required", False,
          "gold B names 180.81 'shortly after the news was published'; that "
          "level is absent from the supplied window, whose last point is 66.2 h "
          "before publication - the gold names data the protocol does not supply"),
    252: (("PPB", "PPB", "PPB", "PPB"), REQUIRED, "required", False,
          "all four options describe post-announcement price action and the "
          "window ends 17.0 h before publication; B ('remained stable ... around "
          "$84') and gold D ('did not rebound strongly') are indistinguishable "
          "from the supplied data"),
    256: (("NPC", "NPC", "PRC", "NPC"), SUFFICIENT, "none", False,
          "gold C (incorrect) is refuted by its pre-news half alone: the series "
          "was already declining before publication, not trending upward"),
    265: (("PPB", "NPC", "PPB", "PPB"), PARTIAL, "partial", True,
          "gold D's move 67.2 -> 70.94 sits at 28-33% and 40-79% of the window, "
          "entirely mid-window; publication is at 100%, so the move it calls "
          "'before the news' to 'shortly after' is wholly pre-publication"),
    268: (("NPC", "NPC", "NPC", "NPC"), SUFFICIENT, "none", False,
          "no option requires post-publication observation"),
    274: (("PPB", "NPC", "NPC", "NPC"), SUFFICIENT, "none", False,
          "gold D (incorrect) is refuted by the article's Zacks Rank #2 and its "
          "own estimate discussion"),
    275: (("NPC", "PPB", "PPB", "PPB"), PARTIAL, "partial", False,
          "gold B says the price began to decline after the earnings release; "
          "the window ends 3.3 h before the article, but the article itself "
          "reports the 3.72% after-hours slip"),
    288: (("NPC", "ADC", "PPB", "NPC"), PARTIAL, "partial", False,
          "gold C (incorrect) claims a significant post-publication increase; "
          "the article's +1.19% is what refutes it, not the series"),
    295: (("NPC", "ADC", "PPB", "NPC"), SUFFICIENT, "none", False,
          "gold D (incorrect) is refuted in-window: the decline from the peak is "
          "not consistent, it rebounds repeatedly"),
    303: (("NPC", "PPB", "PPB", "PPB"), REQUIRED, "required", False,
          "gold D describes a rise 'from 83.67 at the beginning of the "
          "subsequent time series to a peak of 88.22'; 88.22 is absent from the "
          "supplied window (max 87.71) and the phrase names a series the "
          "input-window protocol does not provide"),
    313: (("PPB", "PPB", "NPC", "PPB"), REQUIRED, "required", False,
          "gold D rests on 'the subsequent decrease in stock price on April 19'; "
          "the window ends 2023-04-18 19:55 and publication is 23:20, so April "
          "19 is entirely absent"),
    317: (("PPB", "PPB", "PPB", "NPC"), PARTIAL, "partial", True,
          "gold A (incorrect) fails on its general claim that ratings cause "
          "sell-offs, but B and C - which the gold labels correct - both assert "
          "a post-publication rise, and that rise is in-window"),
    320: (("NPC", "PPB", "PPB", "NPC"), SUFFICIENT, "none", False,
          "gold A is explicitly about the days *prior to* publication and its "
          "levels are in-window at 0-79% and 19-63%"),
    334: (("PPB", "PPB", "NPC", "NPC"), SUFFICIENT, "none", False,
          "gold C compares the analyst target with the close just before the "
          "news - both available"),
    353: (("PPB", "PPB", "PPB", "PPB"), PARTIAL, "partial", True,
          "gold B's peak 381.99 is at 63% of the window; the 'downward trend "
          "following the publication' it describes is the remaining 37% of the "
          "window, which is still 16.3 h before publication"),
    371: (("PRC", "PPB", "PRC", "NPC"), PARTIAL, "partial", True,
          "gold A (incorrect) fails on its absolutist causal claim, but its own "
          "wording and options B and C describe an in-window decline as the "
          "move from a 'pre-news level' to a 'post-news level'"),
    405: (("NPC", "PPB", "PPB", "NPC"), PARTIAL, "partial", True,
          "gold C says prices rose 'following the news announcement'; the rise "
          "is in-window and publication is 2 minutes after the window ends"),
    441: (("ADC", "PPB", "PPB", "PPB"), PARTIAL, "partial", False,
          "gold B (incorrect) claims a consistent rise after November 1st; there "
          "is no post-publication data, and the in-window Nov 1 trend is down"),
    453: (("NPC", "NPC", "NPC", "NPC"), SUFFICIENT, "none", False,
          "gold C is the -15.32% vs -15.56% comparison from the article"),
    454: (("PPB", "PPB", "PPB", "NPC"), PARTIAL, "partial", False,
          "gold C ends with 'leading to a sell-off on the stock post-news'; the "
          "window ends 16.9 h before publication, but the article reports the "
          "drop"),
    484: (("PPB", "NPC", "PPB", "NPC"), SUFFICIENT, "none", False,
          "gold B is the cash cap rate figure from the earnings call transcript"),
}

CLOSE_CALLS = {
    98: "shape matches in-window but both date labels are outside it; could be "
        "argued as REQUIRED on the dates alone",
    120: "kept SUFFICIENT because the gold is refuted by article content, though "
         "option C mislabels the last in-window interval as post-announcement",
    317: "kept PARTIAL rather than SUFFICIENT because two options the gold treats "
         "as correct assert post-publication behaviour",
    371: "kept PARTIAL rather than SUFFICIENT because the gold's own wording is a "
         "before/after-publication comparison",
}


# ==========================================================================
# mechanics
# ==========================================================================
def jsonl(path, key="instance_id"):
    with open(path, encoding="utf-8") as f:
        return {json.loads(l)[key]: json.loads(l) for l in f if l.strip()}


def parse_utc(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()


def role_table():
    man = json.load(open("out_paper50_reviewed/manifest.json",
                         encoding="utf-8"))["instances"]
    out = {}
    for m in man:
        dmeta = {x["article_id"]: x for x in m["distractors"]}
        r = {}
        for pos, aid in enumerate(m["article_order"], 1):
            if pos == m["gt_position"]:
                r[pos] = {"role": "GT", "article_id": aid, "offset_days": 0.0,
                          "alias_direction": None, "event_match_tier": None}
            else:
                d = dmeta[aid]
                is_a = d["distractor_type"] == "temporal_aliasing"
                r[pos] = {
                    "role": "TYPE_A_TEMPORAL_ALIAS" if is_a else "TYPE_B_ABSENCE",
                    "article_id": aid, "offset_days": d["offset_days"],
                    "alias_direction": d["alias_direction"] if is_a else None,
                    "event_match_tier": d["event_match_tier"] if is_a else None}
        out[m["instance_id"]] = r
    return out


def classify_reliance(support_roles):
    if not support_roles:
        return "NO_CLEAR_EVIDENCE"
    has_gt = "GT" in support_roles
    has_a = "TYPE_A_TEMPORAL_ALIAS" in support_roles
    has_b = "TYPE_B_ABSENCE" in support_roles
    if has_gt and not (has_a or has_b):
        return "GT_ONLY"
    if has_gt:
        return "GT_PLUS_INVALID_DISTRACTOR"
    if has_a and has_b:
        return "DISTRACTOR_MIXED"
    return "TYPE_A_ONLY" if has_a else "TYPE_B_ONLY"


GROUNDING = {
    "GT_ONLY": "GROUNDED",
    "GT_PLUS_INVALID_DISTRACTOR": "MIXED_GROUNDING",
    "TYPE_A_ONLY": "TEMPORALLY_INVALID_GROUNDING",
    "TYPE_B_ONLY": "TEMPORALLY_INVALID_GROUNDING",
    "DISTRACTOR_MIXED": "TEMPORALLY_INVALID_GROUNDING",
    "NO_CLEAR_EVIDENCE": "NO_CLEAR_GROUNDING",
}
SHORT = {"GROUNDED": "GROUNDED", "MIXED_GROUNDING": "MIXED",
         "TEMPORALLY_INVALID_GROUNDING": "INVALID",
         "NO_CLEAR_GROUNDING": "UNCLEAR"}


def build_part_a(data, roles, models, ids):
    rows = []
    for i in ids:
        row = {"instance_id": i, "ticker": data[i]["ticker"],
               "gold_answer": data[i]["mcqa_answer"]}
        for cond in ("C1", "C2"):
            rec = models[cond][i]
            declared = list(rec.get("evidence_articles") or [])
            attributed = ATTRIBUTED[cond][i]
            rejected = REJECTED[cond].get(i, [])
            rt = roles[i]

            def describe(ns):
                out = []
                for n in ns:
                    r = rt.get(n)
                    out.append({"article_number": n,
                                "role": None if r is None else r["role"],
                                "article_id": None if r is None else r["article_id"],
                                "offset_days": None if r is None else r["offset_days"],
                                "alias_direction": None if r is None
                                else r["alias_direction"],
                                "event_match_tier": None if r is None
                                else r["event_match_tier"]})
                return out

            listed_only = [n for n in declared if n not in attributed
                           and n not in rejected]
            dec_support = [n for n in declared if n not in rejected]
            dec_roles = {rt[n]["role"] for n in dec_support if n in rt}
            att_roles = {rt[n]["role"] for n in attributed if n in rt}
            dec_cls = classify_reliance(dec_roles)
            att_cls = classify_reliance(att_roles)
            row[cond] = {
                "answer": rec["prediction"], "correct": rec["correct"],
                "confidence": rec["confidence"], "rationale": rec["rationale"],
                "evidence_articles_declared": declared,
                "cited_as_support_declared_reading": dec_support,
                "cited_as_support_rationale_reading": attributed,
                "cited_but_rejected": rejected,
                "listed_without_discussion": listed_only,
                "resolved_declared": describe(dec_support),
                "resolved_attributed": describe(attributed),
                "reliance_declared_reading": dec_cls,
                "reliance_rationale_reading": att_cls,
                "grounding_declared_reading": GROUNDING[dec_cls],
                "grounding_rationale_reading": GROUNDING[att_cls],
                "attribution_note": ATTRIBUTION_NOTES.get((i, cond)),
                "uses_type_a_declared":
                    "TYPE_A_TEMPORAL_ALIAS" in dec_roles,
                "uses_type_a_attributed":
                    "TYPE_A_TEMPORAL_ALIAS" in att_roles,
                "type_a_used": [x for x in describe(attributed)
                                if x["role"] == "TYPE_A_TEMPORAL_ALIAS"],
            }
        rows.append(row)
    return rows


def build_part_b(data, models, ids):
    rows = []
    for i in ids:
        rec = data[i]
        g = parse_utc(rec["gt_published_utc"])
        ts = rec["ts_timestamps"]
        vals = rec["ts_values"]
        cats, cls, gold_rel, mislabel, note = OPTIONS[i]
        opts = {}
        for part in rec["mcqa_question"].splitlines():
            m = re.match(r"^([A-D])\.\s*(.*)$", part.strip(), re.S)
            if m:
                opts[m.group(1)] = m.group(2)
        lo, hi = min(vals), max(vals)
        levels = {}
        for letter, text in opts.items():
            found = []
            for x in re.findall(r"\$?(\d{1,4}(?:,\d{3})*(?:\.\d+)?)", text):
                n = float(x.replace(",", ""))
                if not (lo * 0.9 <= n <= hi * 1.1):
                    continue
                tol = max(0.02, abs(n) * 0.0015)
                hits = [k for k, v in enumerate(vals) if abs(v - n) <= tol]
                found.append({
                    "level": n, "present_in_window": bool(hits),
                    "first_pct": None if not hits
                    else round(100.0 * hits[0] / (len(vals) - 1), 1),
                    "last_pct": None if not hits
                    else round(100.0 * hits[-1] / (len(vals) - 1), 1)})
            if found:
                levels[letter] = found
        rows.append({
            "instance_id": i, "ticker": rec["ticker"],
            "gold_answer": rec["mcqa_answer"],
            "geometry": {
                "first_ts_utc": dt.datetime.fromtimestamp(ts[0], UTC)
                .strftime("%Y-%m-%d %H:%M:%S"),
                "last_ts_utc": dt.datetime.fromtimestamp(ts[-1], UTC)
                .strftime("%Y-%m-%d %H:%M:%S"),
                "gt_publication_utc": rec["gt_published_utc"],
                "last_ts_minus_publication_hours": round((ts[-1] - g) / 3600.0, 2),
                "has_any_ts_point_after_gt_publication": any(t > g for t in ts),
                "n_ts_points_after_gt_publication": sum(1 for t in ts if t > g),
                "n_points": len(vals),
            },
            "options": {L: {"text": opts.get(L, ""), "category": cats[k],
                            "price_levels": levels.get(L, [])}
                        for k, L in enumerate("ABCD")},
            "instance_class": cls,
            "gold_post_publication_reliance": gold_rel,
            "in_window_movement_labelled_post_publication": mislabel,
            "note": note,
            "close_call_note": CLOSE_CALLS.get(i),
            "c1_correct": models["C1"][i]["correct"],
            "c2_correct": models["C2"][i]["correct"],
        })
    return rows


# ATTRIBUTED / REJECTED above were hand-read from the Sonnet-5 rationales: they
# record what *those* rationales lean on.  Part A is a comparison against them,
# so it is only meaningful for the Sonnet-5 outputs.  Part B needs none of it -
# it combines the frozen benchmark, the OPTIONS table (a property of the MCQA
# options, not of any model) and the per-instance `correct` flag - so Part B
# transfers to another model and Part A does not.
ANNOTATED_C1 = "results/paper50_c1_sonnet5.jsonl"
ANNOTATED_C2 = "results/paper50_c2_sonnet5.jsonl"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Grounding audit (Part A) and post-publication semantics "
                    "audit (Part B) over the frozen Paper50 benchmark.")
    ap.add_argument("--c1", default=ANNOTATED_C1,
                    help="scored C1 JSONL (default: the frozen Sonnet-5 run)")
    ap.add_argument("--c2", default=ANNOTATED_C2,
                    help="scored C2 JSONL (default: the frozen Sonnet-5 run)")
    ap.add_argument("--out-prefix", default="results/paper50",
                    help="prefix for every file written")
    ap.add_argument("--label", default="Sonnet-5",
                    help="model name used in the report headings")
    ap.add_argument("--parts", choices=("ab", "b"), default="ab",
                    help="ab = both audits, valid only for the Sonnet-5 outputs "
                         "the Part A annotations were read from; b = the "
                         "post-publication semantics audit alone, which needs no "
                         "annotation and transfers to any model")
    ap.add_argument("--allow-missing", action="store_true",
                    help="analyse the instances that have a result under both C1 "
                         "and C2 instead of requiring all 50")
    args = ap.parse_args(argv)

    if args.parts == "ab" and (args.c1 != ANNOTATED_C1 or args.c2 != ANNOTATED_C2):
        raise SystemExit(
            "Part A cannot run on these outputs.\n"
            "ATTRIBUTED/REJECTED are hand-read from the Sonnet-5 rationales - "
            "they record which articles those rationales lean on. Scoring a "
            "different model against them would compare its declared evidence "
            "with Sonnet-5's reasoning and would silently produce meaningless "
            "numbers.\n"
            "Use --parts b for the post-publication semantics audit, which "
            "needs no annotation.")

    data = {r["instance_id"]: r for r in
            json.load(open("final50_paper_data.json", encoding="utf-8"))}
    roles = role_table()
    models = {"C1": jsonl(args.c1), "C2": jsonl(args.c2)}
    assert set(ATTRIBUTED["C1"]) == set(data) == set(ATTRIBUTED["C2"]) == set(OPTIONS)

    covered = set(models["C1"]) & set(models["C2"])
    missing = sorted(set(data) - covered)
    if missing and not args.allow_missing:
        raise SystemExit(
            "%d of %d instances lack a result under C1, C2 or both: %s\n"
            "Re-run with --allow-missing to analyse the %d that have one. That "
            "missing set is not random - these are the instances the model "
            "failed to answer - so every rate computed on the remainder is "
            "biased upward."
            % (len(missing), len(data), ", ".join(str(i) for i in missing),
               len(data) - len(missing)))

    ids = sorted(set(data) & covered)
    prefix = args.out_prefix
    scope = "All-50" if len(ids) == len(data) else "%d-instance" % len(ids)
    coverage_note = ()
    if missing:
        coverage_note = (
            "## Coverage", "",
            "%d of the %d benchmark instances are analysed. %d are excluded for "
            "lack of a result under C1, C2 or both: %s."
            % (len(ids), len(data), len(missing),
               ", ".join(str(i) for i in missing)), "",
            "The exclusion is **not random**: these are the instances where the "
            "model spent its whole completion budget reasoning and emitted no "
            "final answer. Every rate in this report is therefore computed on "
            "the instances the model could finish, and is biased upward "
            "relative to the full benchmark.", "")

    rows_b = build_part_b(data, models, ids)
    with open(prefix + "_postpublication_audit.jsonl", "w",
              encoding="utf-8", newline="\n") as f:
        for r in rows_b:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("wrote %s_postpublication_audit.jsonl (%d)" % (prefix, len(rows_b)))

    sb = summarise_semantics(rows_b)
    if missing:
        sb["analysis_coverage"] = {
            "n_analysed": len(ids), "n_benchmark": len(data),
            "excluded_instance_ids": missing,
            "note": "excluded for lack of a result under C1, C2 or both; the "
                    "exclusion is not random, so rates here are biased upward"}

    if args.parts == "b":
        with open(prefix + "_postpublication_summary.json", "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(sb, f, indent=2, ensure_ascii=False)
        print("wrote %s_postpublication_summary.json" % prefix)
        write_partb_report(rows_b, sb, prefix, scope, coverage_note)
        print("wrote %s_postpublication_report.md" % prefix)
        return None, rows_b

    rows_a = build_part_a(data, roles, models, ids)
    with open(prefix + "_c1_c2_grounding_all50.jsonl", "w",
              encoding="utf-8", newline="\n") as f:
        for r in rows_a:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("wrote %s_c1_c2_grounding_all50.jsonl (%d)" % (prefix, len(rows_a)))

    sa = summarise_grounding(rows_a)
    syn = synthesise(rows_a, rows_b, sa, sb)
    write_reports(rows_a, rows_b, sa, sb, syn, prefix, args.label, scope,
                  coverage_note)
    report(sa, sb, syn)
    return rows_a, rows_b


# ==========================================================================
# A4 - A7 summaries
# ==========================================================================
READINGS = ("declared", "rationale")


def summarise_grounding(rows):
    out = {
        "readings": {
            "declared": "an article the model listed in evidence_articles counts "
                        "as support unless its rationale rejects it (no rationale "
                        "rejected any article, in either condition)",
            "rationale": "only articles the rationale actually builds on count; "
                         "articles listed but never mentioned are excluded",
        },
        "conditions": {}, "transitions": {}, "type_a_use": {}, "ea_diagnostics": {},
    }
    for cond in ("C1", "C2"):
        n = len(rows)
        acc = sum(r[cond]["correct"] for r in rows)
        cond_out = {"n": n, "n_correct": acc, "accuracy": round(acc / n, 4),
                    "readings": {}}
        for reading in READINGS:
            key = "grounding_%s_reading" % reading
            rkey = "reliance_%s_reading" % reading
            cross, rel_counts, gr_counts = {}, {}, {}
            for r in rows:
                g = r[cond][key]
                rel_counts[r[cond][rkey]] = rel_counts.get(r[cond][rkey], 0) + 1
                gr_counts[g] = gr_counts.get(g, 0) + 1
                k = ("correct" if r[cond]["correct"] else "wrong") + " + " + g
                cross.setdefault(k, []).append(r["instance_id"])
            cond_out["readings"][reading] = {
                "reliance_counts": rel_counts,
                "grounding_counts": gr_counts,
                "grounded_rate": round(gr_counts.get("GROUNDED", 0) / n, 4),
                "invalid_grounding_rate": round(
                    gr_counts.get("TEMPORALLY_INVALID_GROUNDING", 0) / n, 4),
                "mixed_grounding_rate": round(
                    gr_counts.get("MIXED_GROUNDING", 0) / n, 4),
                "answer_by_grounding_counts": {k: len(v) for k, v in
                                               sorted(cross.items())},
                "answer_by_grounding_ids": {k: v for k, v in sorted(cross.items())},
                "correct_but_not_grounded": sorted(
                    [r["instance_id"] for r in rows if r[cond]["correct"]
                     and r[cond][key] in ("MIXED_GROUNDING",
                                          "TEMPORALLY_INVALID_GROUNDING")]),
                "correct_but_temporally_invalid": sorted(
                    [r["instance_id"] for r in rows if r[cond]["correct"]
                     and r[cond][key] == "TEMPORALLY_INVALID_GROUNDING"]),
                "correct_without_any_admissible_evidence": sorted(
                    [r["instance_id"] for r in rows if r[cond]["correct"]
                     and r[cond][key] in ("TEMPORALLY_INVALID_GROUNDING",
                                          "NO_CLEAR_GROUNDING")]),
            }
        out["conditions"][cond] = cond_out

    # A5 grounding transitions
    for reading in READINGS:
        key = "grounding_%s_reading" % reading
        mat, ids = {}, {}
        for r in rows:
            t = "%s -> %s" % (SHORT[r["C1"][key]], SHORT[r["C2"][key]])
            mat[t] = mat.get(t, 0) + 1
            ids.setdefault(t, []).append(r["instance_id"])
        right_wrong = sorted(
            r["instance_id"] for r in rows
            if r["C1"]["correct"] and r["C1"][key] == "GROUNDED"
            and r["C2"]["correct"]
            and r["C2"][key] == "TEMPORALLY_INVALID_GROUNDING")
        grounded_to_invalid = sorted(
            r["instance_id"] for r in rows
            if r["C1"][key] == "GROUNDED"
            and r["C2"][key] == "TEMPORALLY_INVALID_GROUNDING")
        grounded_to_worse = sorted(
            r["instance_id"] for r in rows
            if r["C1"][key] == "GROUNDED"
            and r["C2"][key] in ("MIXED_GROUNDING",
                                 "TEMPORALLY_INVALID_GROUNDING"))
        out["transitions"][reading] = {
            "matrix": dict(sorted(mat.items())),
            "instance_ids": {k: v for k, v in sorted(ids.items())},
            "right_answer_wrong_evidence": right_wrong,
            "grounded_to_invalid": grounded_to_invalid,
            "grounded_to_any_distractor_use": grounded_to_worse,
        }

    # A6 type-A use
    for reading in READINGS:
        flag = "uses_type_a_%s" % ("declared" if reading == "declared"
                                   else "attributed")
        per = {}
        for cond in ("C1", "C2"):
            using = [r["instance_id"] for r in rows if r[cond][flag]]
            fut, hist = [], []
            for r in rows:
                if not r[cond][flag]:
                    continue
                src = (r[cond]["resolved_declared"] if reading == "declared"
                       else r[cond]["resolved_attributed"])
                dirs = {x["alias_direction"] for x in src
                        if x["role"] == "TYPE_A_TEMPORAL_ALIAS"}
                if "future" in dirs:
                    fut.append(r["instance_id"])
                if "historical" in dirs:
                    hist.append(r["instance_id"])
            per[cond] = {
                "n_instances_using_type_a": len(using),
                "instance_ids": using,
                "n_using_future_alias": len(fut), "future_ids": fut,
                "n_using_historical_alias": len(hist), "historical_ids": hist,
                "n_type_a_explicitly_rejected": 0,
                "type_a_rejected_ids": [],
            }
        out["type_a_use"][reading] = per
    out["type_a_use"]["note"] = (
        "no rationale in either condition names an article and then rejects it, "
        "so cited_but_rejected is empty everywhere; the 'declared' and "
        "'rationale' readings differ only by articles listed in "
        "evidence_articles that the rationale never mentions")

    # A7 EA1 / EA2
    ea1 = {c: sorted(r["instance_id"] for r in rows
                     if r[c]["uses_type_a_attributed"]) for c in ("C1", "C2")}
    ea1_dec = {c: sorted(r["instance_id"] for r in rows
                         if r[c]["uses_type_a_declared"]) for c in ("C1", "C2")}
    out["ea_diagnostics"] = {
        "label": "POST-HOC OBSERVABLE DIAGNOSTICS, not primary endpoints",
        "EA1_definition": "the model treats temporally inadmissible context (a "
                          "Type A alias) as valid supporting evidence; scored "
                          "from the rationale, never from a wrong answer",
        "EA1_candidates_rationale_reading": ea1,
        "EA1_candidates_declared_reading": ea1_dec,
        "EA2_definition": "the model attributes its conclusion to invalid "
                          "supplied evidence instead of acknowledging that no "
                          "valid support exists",
        "EA2_candidates": {
            "C1": [],
            "C2": [176, 265],
        },
        "EA2_additional_weaker_candidates": {
            "C1": [],
            "C2": [35, 201],
        },
        "EA2_case_notes": {
            176: "the price drop in the window is attributed to Article 3, a "
                 "+650 day alias describing a July 2023 session",
            265: "the in-window rise is attributed to 'the Q4 earnings beat ... "
                 "discussed in Article 7/10', at -125.9 and +279.1 days",
            35: "weaker: the conclusion is credited to 'the news articles' "
                "collectively, a set containing three aliases and no GT, but no "
                "single article is named",
            201: "weaker: a -398 day alias supplies the premise of the contrast "
                 "the answer turns on, while the conclusion itself rests on the "
                 "price series",
        },
        "absence_evidence_treated_as_sole_support": {
            "C1": sorted(r["instance_id"] for r in rows
                         if r["C1"]["reliance_rationale_reading"] == "TYPE_B_ONLY"),
            "C2": sorted(r["instance_id"] for r in rows
                         if r["C2"]["reliance_rationale_reading"] == "TYPE_B_ONLY"),
            "note": "reported separately from EA1: absence evidence is "
                    "non-probative rather than temporally inadmissible",
        },
    }
    return out


# ==========================================================================
# B1 - B5 summaries
# ==========================================================================
def summarise_semantics(rows):
    gaps = sorted(r["geometry"]["last_ts_minus_publication_hours"] for r in rows)
    n = len(rows)
    by_class = {}
    for r in rows:
        by_class.setdefault(r["instance_class"], []).append(r["instance_id"])
    cross = {}
    for cls, ids in by_class.items():
        sub = [r for r in rows if r["instance_class"] == cls]
        c1 = sum(x["c1_correct"] for x in sub)
        c2 = sum(x["c2_correct"] for x in sub)
        cross[cls] = {
            "n": len(sub), "instance_ids": sorted(ids),
            "c1_correct": c1, "c1_accuracy": round(c1 / len(sub), 4),
            "c2_correct": c2, "c2_accuracy": round(c2 / len(sub), 4),
            "c1_correct_c2_wrong": sorted(x["instance_id"] for x in sub
                                          if x["c1_correct"] and not x["c2_correct"]),
            "c1_wrong_c2_correct": sorted(x["instance_id"] for x in sub
                                          if not x["c1_correct"] and x["c2_correct"]),
            "both_wrong": sorted(x["instance_id"] for x in sub
                                 if not x["c1_correct"] and not x["c2_correct"]),
        }
    opt_counts = {}
    for r in rows:
        for L in "ABCD":
            c = r["options"][L]["category"]
            opt_counts[c] = opt_counts.get(c, 0) + 1
    absent = []
    for r in rows:
        for L in "ABCD":
            for lv in r["options"][L]["price_levels"]:
                if not lv["present_in_window"]:
                    absent.append({"instance_id": r["instance_id"], "option": L,
                                   "is_gold": L == r["gold_answer"],
                                   "level": lv["level"]})
    return {
        "B1_geometry": {
            "n_instances": n,
            "n_with_any_post_publication_ts_point": sum(
                r["geometry"]["has_any_ts_point_after_gt_publication"] for r in rows),
            "n_with_no_post_publication_ts_point": sum(
                not r["geometry"]["has_any_ts_point_after_gt_publication"]
                for r in rows),
            "gap_last_ts_minus_publication_hours": {
                "min": gaps[0], "median": gaps[n // 2], "max": gaps[-1]},
            "reading": "every gap is negative: the window always ends before the "
                       "ground-truth article publishes. This is the official "
                       "input_window-only protocol and is not an error in itself.",
        },
        "B2_option_category_counts": opt_counts,
        "B2_price_levels_absent_from_window": absent,
        "B3_class_counts": {k: len(v) for k, v in sorted(by_class.items())},
        "B3_class_instance_ids": {k: sorted(v) for k, v in sorted(by_class.items())},
        "B4_gold_requires_unavailable_post_publication": sorted(
            r["instance_id"] for r in rows
            if r["gold_post_publication_reliance"] == "required"),
        "B4_gold_partially_relies_on_unavailable_post_publication": sorted(
            r["instance_id"] for r in rows
            if r["gold_post_publication_reliance"] == "partial"),
        "B4_in_window_movement_labelled_post_publication": sorted(
            r["instance_id"] for r in rows
            if r["in_window_movement_labelled_post_publication"]),
        "B5_cross_tab": cross,
        "B5_supplementary_cross_tabs": {
            "by_gold_post_publication_reliance": _tab(
                rows, lambda r: r["gold_post_publication_reliance"]),
            "by_in_window_movement_mislabelled": _tab(
                rows, lambda r: str(
                    r["in_window_movement_labelled_post_publication"])),
        },
        "B5_errors_by_class": {
            "c1_error_ids_by_class": _errors(rows, "c1_correct"),
            "c2_error_ids_by_class": _errors(rows, "c2_correct"),
        },
        "close_calls": {str(k): v for k, v in CLOSE_CALLS.items()},
    }


def _tab(rows, keyfn):
    out = {}
    for r in rows:
        k = keyfn(r)
        d = out.setdefault(k, {"n": 0, "c1_correct": 0, "c2_correct": 0,
                               "instance_ids": []})
        d["n"] += 1
        d["c1_correct"] += bool(r["c1_correct"])
        d["c2_correct"] += bool(r["c2_correct"])
        d["instance_ids"].append(r["instance_id"])
    for d in out.values():
        d["c1_accuracy"] = round(d["c1_correct"] / d["n"], 4)
        d["c2_accuracy"] = round(d["c2_correct"] / d["n"], 4)
    return dict(sorted(out.items()))


def _errors(rows, field):
    out = {}
    for r in rows:
        if not r[field]:
            out.setdefault(r["instance_class"], []).append(r["instance_id"])
    return dict(sorted(out.items()))


# ==========================================================================
# PART C synthesis
# ==========================================================================
def synthesise(rows_a, rows_b, sa, sb):
    a = {r["instance_id"]: r for r in rows_a}
    b = {r["instance_id"]: r for r in rows_b}
    cases = []
    for i in sorted(a):
        labels = {}
        r, s = a[i], b[i]
        if r["C2"]["uses_type_a_attributed"] or r["C1"]["uses_type_a_attributed"]:
            labels["TEMPORAL_GROUNDING_FAILURE"] = "SUPPORTED"
        elif (r["C2"]["reliance_rationale_reading"] == "TYPE_B_ONLY"
              or r["C1"]["reliance_rationale_reading"] == "TYPE_B_ONLY"):
            labels["TEMPORAL_GROUNDING_FAILURE"] = "PLAUSIBLE"
        if (r["C2"]["correct"] and r["C2"]["grounding_rationale_reading"]
                in ("TEMPORALLY_INVALID_GROUNDING", "NO_CLEAR_GROUNDING")):
            labels["SEMANTIC_SHORTCUT"] = (
                "SUPPORTED" if r["C2"]["grounding_rationale_reading"]
                == "TEMPORALLY_INVALID_GROUNDING" else "PLAUSIBLE")
        if s["instance_class"] == REQUIRED:
            labels["INPUT_WINDOW_TASK_SEMANTICS_MISMATCH"] = "SUPPORTED"
        elif s["instance_class"] == PARTIAL:
            labels["INPUT_WINDOW_TASK_SEMANTICS_MISMATCH"] = "PLAUSIBLE"
        if labels:
            cases.append({
                "instance_id": i, "ticker": r["ticker"],
                "c1": {"answer": r["C1"]["answer"], "correct": r["C1"]["correct"],
                       "grounding": r["C1"]["grounding_rationale_reading"]},
                "c2": {"answer": r["C2"]["answer"], "correct": r["C2"]["correct"],
                       "grounding": r["C2"]["grounding_rationale_reading"]},
                "semantics_class": s["instance_class"],
                "gold_post_publication_reliance":
                    s["gold_post_publication_reliance"],
                "labels": labels,
            })
    counts = {}
    for c in cases:
        for k, v in c["labels"].items():
            counts.setdefault(k, {}).setdefault(v, 0)
            counts[k][v] += 1
    return {"phenomena": {
        "TEMPORAL_GROUNDING_FAILURE": "the answer, right or wrong, is explained "
                                      "by evidence that is inadmissible for the "
                                      "anchor",
        "SEMANTIC_SHORTCUT": "the MCQA label is recovered without any admissible "
                             "evidence being used",
        "INPUT_WINDOW_TASK_SEMANTICS_MISMATCH": "the inherited option semantics "
                                                "need information after "
                                                "publication that the "
                                                "input-window protocol does not "
                                                "supply",
    }, "label_counts": counts, "cases": cases,
        "note": "labels are not exclusive; an instance can carry more than one, "
                "and instances with no observable phenomenon are simply absent",
        "headline": {
            "answer_accuracy": {"C1": "44/50 = 0.88", "C2": "46/50 = 0.92"},
            "grounded_rate_rationale_reading": {"C1": "46/50 = 0.92",
                                                "C2": "34/50 = 0.68"},
            "accuracy_on_well_posed_items_only": {
                "class": "INPUT_WINDOW_SUFFICIENT (n=20)",
                "C1": "20/20 = 1.00", "C2": "19/20 = 0.95",
                "reading": "every C1 error falls in a class whose options are "
                           "not decidable from the supplied window; C2's single "
                           "error there is instance 274"},
            "accuracy_where_gold_needs_absent_data": {
                "class": "POST_PUBLICATION_EVIDENCE_REQUIRED (n=7)",
                "C1": "4/7 = 0.57", "C2": "4/7 = 0.57"},
            "where_the_c2_advantage_comes_from":
                "the PARTIALLY_UNDERDETERMINED class alone: C1 20/23, C2 23/23. "
                "Accuracy and grounding move in opposite directions across the "
                "same 50 items.",
        },
        "revisions_to_earlier_flip_analysis": {
            252: "the flip-case audit labelled this CONSISTENT_WITH_TIMESTAMP_HELP "
                 "with HIGH confidence. That still describes what the rationales "
                 "show - C2 states it cannot tie any reaction to a news date - but "
                 "this audit adds that the item's gold is not decidable from the "
                 "supplied window at all: options B and D both describe "
                 "post-announcement price action and publication is 17.0 h after "
                 "the last window point. The timestamp helped C1 pick the gold "
                 "without giving it a valid basis, so the case belongs under "
                 "INPUT_WINDOW_TASK_SEMANTICS_MISMATCH as well.",
            265: "the flip-case audit could only say that C1 'anchored on the "
                 "pre-publication tail'. The price-level check makes it concrete: "
                 "the gold's move 67.2 -> 70.94 sits at 28-33% and 40-79% of the "
                 "window, entirely before publication, so C1's timestamp-aligned "
                 "reading correctly found no such move at the publication instant "
                 "and rejected the gold.",
            18: "unchanged, and now supported by the class assignment: the item "
                "is PARTIALLY_UNDERDETERMINED because option D's post-publication "
                "claim competes with the gold.",
            96: "unchanged, and reinforced: option C names $147.61, a level "
                "absent from the supplied window.",
        }}


# ==========================================================================
# reports
# ==========================================================================
def write_partb_report(rows_b, sb, prefix, scope, coverage_note):
    g = sb["B1_geometry"]
    md = ["# %s post-publication semantics audit" % scope, "",
          "Diagnostic only, and independent of model correctness: every "
          "classification below is made from the question and option wording, "
          "the ground-truth publication time, the supplied window and the "
          "ground-truth article. The cross-tab with C1/C2 results comes last, "
          "after the classification was fixed.", "",
          "## B1 Geometry", "",
          "- instances with at least one time-series point after the "
          "ground-truth publication: **%d / %d**"
          % (g["n_with_any_post_publication_ts_point"], g["n_instances"]),
          "- instances with none: **%d / %d**"
          % (g["n_with_no_post_publication_ts_point"], g["n_instances"]),
          "- gap from last window point to publication: min %.2f h, median "
          "%.2f h, max %.2f h (all negative)"
          % (g["gap_last_ts_minus_publication_hours"]["min"],
             g["gap_last_ts_minus_publication_hours"]["median"],
             g["gap_last_ts_minus_publication_hours"]["max"]),
          "", g["reading"], "",
          "## B2 Option categories (200 options)", ""]
    for k, v in sorted(sb["B2_option_category_counts"].items()):
        md.append("- %s: %d" % (k, v))
    md += ["", "### Price levels named by an option but absent from the window",
           "", "| id | option | gold? | level |", "| --- | --- | --- | --- |"]
    for x in sb["B2_price_levels_absent_from_window"]:
        md.append("| %d | %s | %s | %g |" % (x["instance_id"], x["option"],
                                             "yes" if x["is_gold"] else "", x["level"]))
    md += ["", "Not every absent number is a price: analyst targets, P/E ratios, "
           "percentages and years also appear. The ones that matter are flagged "
           "per instance below.", "",
           "## B3 Instance classification", ""]
    for k, v in sorted(sb["B3_class_instance_ids"].items()):
        md.append("- **%s**: %d - %s" % (k, len(v), v))
    md += ["", "## B4 Gold-answer audit", "",
           "Gold requires post-publication behaviour that is not supplied: "
           "**%s**" % sb["B4_gold_requires_unavailable_post_publication"], "",
           "Gold partially relies on it (label or framing is post-publication, "
           "substance is reachable from the article or the window): %s"
           % sb["B4_gold_partially_relies_on_unavailable_post_publication"], "",
           "Instances where in-window, pre-publication movement is described as "
           "happening after the news: %s"
           % sb["B4_in_window_movement_labelled_post_publication"], "",
           "### Per-instance reasoning", ""]
    for r in rows_b:
        md += ["**%d %s** - gold %s - `%s`, gold reliance `%s`"
               % (r["instance_id"], r["ticker"], r["gold_answer"],
                  r["instance_class"], r["gold_post_publication_reliance"]),
               "", "last window point %+.2f h vs publication. %s"
               % (r["geometry"]["last_ts_minus_publication_hours"], r["note"]), ""]
        if r["close_call_note"]:
            md += ["_close call: %s_" % r["close_call_note"], ""]
    md += ["## B5 Cross-tab with C1/C2 (descriptive, no tests)", "",
           "| class | n | C1 acc | C2 acc | C1->C2 wrong | C1->C2 fixed | both wrong |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    for k, v in sorted(sb["B5_cross_tab"].items()):
        md.append("| %s | %d | %.2f | %.2f | %s | %s | %s |"
                  % (k, v["n"], v["c1_accuracy"], v["c2_accuracy"],
                     v["c1_correct_c2_wrong"] or "-", v["c1_wrong_c2_correct"] or "-",
                     v["both_wrong"] or "-"))
    md += ["", "C1 errors by class: %s" % sb["B5_errors_by_class"]["c1_error_ids_by_class"],
           "", "C2 errors by class: %s" % sb["B5_errors_by_class"]["c2_error_ids_by_class"],
           "", "### Supplementary cross-tabs", "",
           "| split | n | C1 acc | C2 acc |", "| --- | --- | --- | --- |"]
    for name, tab in sb["B5_supplementary_cross_tabs"].items():
        for k, v in tab.items():
            md.append("| %s = %s | %d | %.2f | %.2f |"
                      % (name, k, v["n"], v["c1_accuracy"], v["c2_accuracy"]))
    md += ["", "Post-hoc subgroups on %d items; no significance testing, and no "
           "instance was modified or excluded on the basis of this audit."
           % sb["B1_geometry"]["n_instances"], ""]
    md += list(coverage_note)
    with open(prefix + "_postpublication_report.md", "w", encoding="utf-8",
              newline="\n") as f:
        f.write("\n".join(md))


def write_reports(rows_a, rows_b, sa, sb, syn, prefix="results/paper50",
                  label="Sonnet-5", scope="All-50", coverage_note=()):
    with open(prefix + "_c1_c2_grounding_summary.json", "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(sa, f, indent=2, ensure_ascii=False)
    with open(prefix + "_postpublication_summary.json", "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(sb, f, indent=2, ensure_ascii=False)
    with open(prefix + "_grounding_semantics_synthesis.json", "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(syn, f, indent=2, ensure_ascii=False)

    # ---- grounding report ------------------------------------------------
    md = ["# %s C1/C2 grounding audit - %s, final frozen benchmark"
          % (scope, label), "",
          "Diagnostic only. No benchmark file, distractor, mask, option or model "
          "output was modified and no inference was run.", "",
          "Two readings are reported throughout, because they answer different "
          "questions:", "",
          "- **declared** - an article counts as support if the model listed it in "
          "`evidence_articles`. No rationale in either condition names an article "
          "and then rejects it, so `cited_but_rejected` is empty everywhere.",
          "- **rationale** - only articles the rationale actually builds on count. "
          "Articles listed but never mentioned are excluded.", "",
          "The truth is bracketed by the two.", ""]
    for cond in ("C1", "C2"):
        c = sa["conditions"][cond]
        md += ["## %s - answer accuracy %d/%d = %.2f"
               % (cond, c["n_correct"], c["n"], c["accuracy"]), ""]
        for reading in READINGS:
            rr = c["readings"][reading]
            md += ["### %s reading" % reading, "",
                   "| grounding | n |", "| --- | --- |"]
            for k, v in sorted(rr["grounding_counts"].items()):
                md.append("| %s | %d |" % (k, v))
            md += ["", "grounded rate %.2f, invalid-grounding rate %.2f, "
                   "mixed rate %.2f" % (rr["grounded_rate"],
                                        rr["invalid_grounding_rate"],
                                        rr["mixed_grounding_rate"]), "",
                   "| answer x grounding | n | instances |", "| --- | --- | --- |"]
            for k, v in sorted(rr["answer_by_grounding_ids"].items()):
                md.append("| %s | %d | %s |" % (k, len(v), v))
            md += ["", "correct but temporally invalid: %s"
                   % (rr["correct_but_temporally_invalid"] or "none"), ""]
    md += ["## Grounding transitions C1 -> C2", ""]
    for reading in READINGS:
        t = sa["transitions"][reading]
        md += ["### %s reading" % reading, "", "| transition | n | instances |",
               "| --- | --- | --- |"]
        for k, v in sorted(t["instance_ids"].items()):
            md.append("| %s | %d | %s |" % (k, len(v), v))
        md += ["", "- right answer, wrong evidence (C1 correct+grounded -> C2 "
               "correct+invalid): **%s**" % (t["right_answer_wrong_evidence"] or "none"),
               "- grounded -> invalid regardless of correctness: **%s**"
               % (t["grounded_to_invalid"] or "none"),
               "- grounded -> any distractor use: **%s**"
               % (t["grounded_to_any_distractor_use"] or "none"), ""]
    md += ["## Temporal-alias use", ""]
    for reading in READINGS:
        u = sa["type_a_use"][reading]
        md += ["### %s reading" % reading, "",
               "| | C1 | C2 |", "| --- | --- | --- |",
               "| instances using >=1 Type A | %d | %d |"
               % (u["C1"]["n_instances_using_type_a"],
                  u["C2"]["n_instances_using_type_a"]),
               "| ... future alias | %d | %d |"
               % (u["C1"]["n_using_future_alias"], u["C2"]["n_using_future_alias"]),
               "| ... historical alias | %d | %d |"
               % (u["C1"]["n_using_historical_alias"],
                  u["C2"]["n_using_historical_alias"]),
               "| Type A explicitly rejected | 0 | 0 |", "",
               "C1 ids: %s" % (u["C1"]["instance_ids"] or "none"),
               "", "C2 ids: %s" % (u["C2"]["instance_ids"] or "none"), ""]
    ea = sa["ea_diagnostics"]
    md += ["## EA1 / EA2 - POST-HOC OBSERVABLE DIAGNOSTICS", "",
           "These are diagnostics, not primary endpoints. Neither is inferred "
           "from a wrong answer, and no hidden reasoning is assumed.", "",
           "| | C1 | C2 |", "| --- | --- | --- |",
           "| EA1 candidates (rationale reading) | %d %s | %d %s |"
           % (len(ea["EA1_candidates_rationale_reading"]["C1"]),
              ea["EA1_candidates_rationale_reading"]["C1"] or "",
              len(ea["EA1_candidates_rationale_reading"]["C2"]),
              ea["EA1_candidates_rationale_reading"]["C2"]),
           "| EA1 candidates (declared reading) | %d %s | %d %s |"
           % (len(ea["EA1_candidates_declared_reading"]["C1"]),
              ea["EA1_candidates_declared_reading"]["C1"],
              len(ea["EA1_candidates_declared_reading"]["C2"]),
              ea["EA1_candidates_declared_reading"]["C2"]),
           "| EA2 candidates | %d | %d %s |"
           % (len(ea["EA2_candidates"]["C1"]), len(ea["EA2_candidates"]["C2"]),
              ea["EA2_candidates"]["C2"]),
           "| EA2 weaker candidates | %d | %d %s |"
           % (len(ea["EA2_additional_weaker_candidates"]["C1"]),
              len(ea["EA2_additional_weaker_candidates"]["C2"]),
              ea["EA2_additional_weaker_candidates"]["C2"]), "",
           "Absence evidence used as the sole support: C1 %s, C2 %s (reported "
           "apart from EA1 - absence evidence is non-probative rather than "
           "temporally inadmissible)."
           % (ea["absence_evidence_treated_as_sole_support"]["C1"] or "none",
              ea["absence_evidence_treated_as_sole_support"]["C2"] or "none"), ""]
    md += ["## Per-instance table (rationale reading)", "",
           "| id | ticker | C1 ans | C1 grounding | C2 ans | C2 grounding |",
           "| --- | --- | --- | --- | --- | --- |"]
    for r in rows_a:
        md.append("| %d | %s | %s%s | %s | %s%s | %s |"
                  % (r["instance_id"], r["ticker"], r["C1"]["answer"],
                     "" if r["C1"]["correct"] else " (wrong)",
                     SHORT[r["C1"]["grounding_rationale_reading"]],
                     r["C2"]["answer"], "" if r["C2"]["correct"] else " (wrong)",
                     SHORT[r["C2"]["grounding_rationale_reading"]]))
    md.append("")
    with open(prefix + "_c1_c2_grounding_report.md", "w", encoding="utf-8",
              newline="\n") as f:
        f.write("\n".join(md))

    write_partb_report(rows_b, sb, prefix, scope, coverage_note)

    # ---- synthesis -------------------------------------------------------
    md = ["# Synthesis - grounding, shortcuts and task semantics", "",
          "Three phenomena are separated below. They are not exclusive: an "
          "instance can carry more than one label, and instances where nothing "
          "is observable carry none.", ""]
    for k, v in syn["phenomena"].items():
        md.append("- **%s** - %s" % (k, v))
    h = syn["headline"]
    md += ["", "## Headline", "",
           "- answer accuracy: C1 %s, C2 %s"
           % (h["answer_accuracy"]["C1"], h["answer_accuracy"]["C2"]),
           "- grounded rate (rationale reading): C1 %s, C2 %s"
           % (h["grounded_rate_rationale_reading"]["C1"],
              h["grounded_rate_rationale_reading"]["C2"]),
           "- on %s: C1 %s, C2 %s"
           % (h["accuracy_on_well_posed_items_only"]["class"],
              h["accuracy_on_well_posed_items_only"]["C1"],
              h["accuracy_on_well_posed_items_only"]["C2"]),
           "  - %s" % h["accuracy_on_well_posed_items_only"]["reading"],
           "- on %s: C1 %s, C2 %s"
           % (h["accuracy_where_gold_needs_absent_data"]["class"],
              h["accuracy_where_gold_needs_absent_data"]["C1"],
              h["accuracy_where_gold_needs_absent_data"]["C2"]),
           "- %s" % h["where_the_c2_advantage_comes_from"], "",
           "## Revisions to the earlier flip-case analysis", ""]
    for k, v in syn["revisions_to_earlier_flip_analysis"].items():
        md += ["- **instance %s**: %s" % (k, v)]
    md += ["", "## Label counts", "", "| phenomenon | SUPPORTED | PLAUSIBLE |",
           "| --- | --- | --- |"]
    for k, v in sorted(syn["label_counts"].items()):
        md.append("| %s | %d | %d |" % (k, v.get("SUPPORTED", 0),
                                        v.get("PLAUSIBLE", 0)))
    md += ["", "## Cases", "",
           "| id | ticker | C1 | C2 | semantics | labels |",
           "| --- | --- | --- | --- | --- | --- |"]
    for c in syn["cases"]:
        md.append("| %d | %s | %s/%s | %s/%s | %s | %s |"
                  % (c["instance_id"], c["ticker"], c["c1"]["answer"],
                     SHORT[c["c1"]["grounding"]], c["c2"]["answer"],
                     SHORT[c["c2"]["grounding"]], c["semantics_class"],
                     ", ".join("%s=%s" % (k.split("_")[0], v)
                               for k, v in c["labels"].items())))
    md.append("")
    with open(prefix + "_grounding_semantics_synthesis.md", "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md))


def report(sa, sb, syn):
    for cond in ("C1", "C2"):
        c = sa["conditions"][cond]
        print("\n%s accuracy %d/50 = %.2f" % (cond, c["n_correct"], c["accuracy"]))
        for reading in READINGS:
            rr = c["readings"][reading]
            print("  %-9s grounded %.2f  mixed %.2f  invalid %.2f  %s"
                  % (reading, rr["grounded_rate"], rr["mixed_grounding_rate"],
                     rr["invalid_grounding_rate"],
                     dict(sorted(rr["grounding_counts"].items()))))
            print("            correct-but-invalid: %s"
                  % (rr["correct_but_temporally_invalid"] or "none"))
    for reading in READINGS:
        t = sa["transitions"][reading]
        print("\ntransitions (%s): %s" % (reading, t["matrix"]))
        print("  right answer / wrong evidence: %s"
              % (t["right_answer_wrong_evidence"] or "none"))
        print("  grounded -> invalid: %s" % (t["grounded_to_invalid"] or "none"))
    ea = sa["ea_diagnostics"]
    print("\nEA1 rationale reading: C1 %s   C2 %s"
          % (ea["EA1_candidates_rationale_reading"]["C1"],
             ea["EA1_candidates_rationale_reading"]["C2"]))
    print("EA1 declared reading:  C1 %s   C2 %s"
          % (ea["EA1_candidates_declared_reading"]["C1"],
             ea["EA1_candidates_declared_reading"]["C2"]))
    print("EA2: C1 %s   C2 %s (weaker: %s)"
          % (ea["EA2_candidates"]["C1"], ea["EA2_candidates"]["C2"],
             ea["EA2_additional_weaker_candidates"]["C2"]))
    g = sb["B1_geometry"]
    print("\npost-publication TS points: %d/%d instances have any"
          % (g["n_with_any_post_publication_ts_point"], g["n_instances"]))
    print("gap min/median/max h: %.2f / %.2f / %.2f"
          % (g["gap_last_ts_minus_publication_hours"]["min"],
             g["gap_last_ts_minus_publication_hours"]["median"],
             g["gap_last_ts_minus_publication_hours"]["max"]))
    print("semantics classes: %s" % sb["B3_class_counts"])
    print("gold REQUIRES unavailable post-pub: %s"
          % sb["B4_gold_requires_unavailable_post_publication"])
    print("in-window movement labelled post-publication: %s"
          % sb["B4_in_window_movement_labelled_post_publication"])
    print("\nB5 cross-tab:")
    for k, v in sorted(sb["B5_cross_tab"].items()):
        print("  %-34s n=%2d  C1 %.2f  C2 %.2f" % (k, v["n"], v["c1_accuracy"],
                                                   v["c2_accuracy"]))
    print("\nsynthesis label counts: %s" % syn["label_counts"])


if __name__ == "__main__":
    main()
