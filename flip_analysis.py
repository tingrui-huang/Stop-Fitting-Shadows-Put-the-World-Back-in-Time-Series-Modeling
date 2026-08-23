"""TASKS 3, 4, 7 - interpret the discordant cases and render the case report.

The mechanical dossier (flip_dossiers.py) is the input.  The judgements below
are hand-authored from the observable record only: the model's answer, its
self-reported rationale, the articles it cited, and the rendered prompt.  No
hidden chain of thought is inferred, and no interpretation is derived from any
aggregate.

Every quoted fragment in "observable_basis" is copied verbatim from the frozen
model output, so a reader can check the judgement against the raw file.

Writes results/c1_c2_flip_analysis.json and results/c1_c2_flip_dossiers.md.

Usage:  python flip_analysis.py
"""

import json

DUMP = "results/_flip_dossier_dump.json"
OUT_JSON = "results/c1_c2_flip_analysis.json"
OUT_MD = "results/c1_c2_flip_dossiers.md"

# --------------------------------------------------------------------------
# hand-authored interpretation, one entry per discordant instance
# --------------------------------------------------------------------------
INTERPRETATION = {
    18: {
        "c1": {
            "temporal_use": "EXPLICIT_TEMPORAL_USE",
            "observable_basis": "rationale states 'rising from ~316 to ~319 in the "
                                "hours leading up to the 16:10 article publication "
                                "on June 2, 2021' and 'the series ends right at the "
                                "publish time'",
            "evidence_class": "GT",
            "evidence_admissible": True,
            "admissibility_note": "cited the ground-truth article only; no alias used",
            "reliance": "TEMPORAL_GATING_VISIBLE",
        },
        "c2": {
            "temporal_use": "NO_VISIBLE_TEMPORAL_USE",
            "observable_basis": "rationale describes the series only by shape - "
                                "'mild upward drift for much of the series before a "
                                "later decline' - and names no date, publication "
                                "time or period",
            "evidence_class": "GT",
            "evidence_admissible": True,
            "admissibility_note": "cited the ground-truth article only",
            "reliance": "SEMANTIC_MATCH_DOMINANT",
        },
        "flip_explanation": "C1_TEMPORAL_HEURISTIC_MISLED",
        "secondary": None,
        "confidence": "HIGH",
        "narrative":
            "The window ends at 2021-06-02 16:10:00 and the ground-truth article "
            "publishes at 16:10:05, so the series contains no post-publication "
            "point at all. In C1 the model saw that alignment, concluded that the "
            "'sharp drop following the news' asserted by option D is not observable, "
            "and answered D. That reasoning is only available when timestamps are "
            "visible, and it steered the model onto a non-gold option. In C2 the "
            "same check is impossible, so the model evaluated option C against the "
            "shape of the whole series and answered C, the gold. The gain here is "
            "not evidence that the model reasons better without time; it is "
            "evidence that precise temporal alignment can expose an answer option "
            "the benchmark's gold label does not treat as the intended one.",
    },
    96: {
        "c1": {
            "temporal_use": "EXPLICIT_TEMPORAL_USE",
            "observable_basis": "rationale states 'the price ending around $148.54 "
                                "on 2021-11-11 (last data point)' - it dates the "
                                "final observation and checks option C's "
                                "'following the news publication on November 12' "
                                "against it",
            "evidence_class": "GT",
            "evidence_admissible": True,
            "admissibility_note": "cited the ground-truth article only",
            "reliance": "TEMPORAL_GATING_VISIBLE",
        },
        "c2": {
            "temporal_use": "NO_VISIBLE_TEMPORAL_USE",
            "observable_basis": "rationale compares options on trend shape only "
                                "('trending downward from ~150.6 to ~148.5') and "
                                "returns an empty evidence_articles list",
            "evidence_class": "NO_CLEAR_ARTICLE",
            "evidence_admissible": None,
            "admissibility_note": "no article cited at all",
            "reliance": "SEMANTIC_MATCH_DOMINANT",
        },
        "flip_explanation": "C1_TEMPORAL_HEURISTIC_MISLED",
        "secondary": None,
        "confidence": "HIGH",
        "narrative":
            "The window ends 2021-11-11 20:55, 17.4 hours before the ground-truth "
            "article publishes. Option C asserts a decline 'following the news "
            "publication on November 12' - a claim the series cannot cover. With "
            "timestamps visible, C1 detected exactly that mismatch and answered C. "
            "With timestamps removed, the date in option C became uncheckable, the "
            "model stopped trying to verify it, and picked D as the speculative "
            "statement, which is the gold. Note the protocol asymmetry this case "
            "exposes: the answer options keep their absolute dates in C2 (this is "
            "one of 26/50 instances whose MCQA text carries absolute temporal "
            "tokens) while the evidence context has none, so a date-anchored option "
            "can no longer be checked against anything.",
    },
    176: {
        "c1": {
            "temporal_use": "EXPLICIT_TEMPORAL_USE",
            "observable_basis": "rationale localises the dip - 'the stock's actual "
                                "intraday low (on 2021-10-01, the session most "
                                "consistent with a dip-then-rebound pattern)'",
            "evidence_class": "GT",
            "evidence_admissible": True,
            "admissibility_note": "cited the ground-truth article only",
            "reliance": "MIXED",
        },
        "c2": {
            "temporal_use": "IMPLICIT_TEMPORAL_USE",
            "observable_basis": "rationale reasons over ordinal positions and a "
                                "before/after split - 'a sharp decline beginning "
                                "around position 155-180', 'the post-news average "
                                "(~126.37) is actually lower than the pre-news "
                                "average (~126.63)' - but fixes the event by "
                                "semantic match: 'aligns with the earnings-day "
                                "sell-off described in Article 3'",
            "evidence_class": "TYPE_A_TEMPORAL_ALIAS",
            "evidence_admissible": False,
            "admissibility_note": "Article 3 is a future temporal alias at "
                                  "+650.2 days (published 2023-07-18) describing a "
                                  "July 2023 session; the window runs 2021-09-29 to "
                                  "2021-10-05, so it cannot describe any move in it",
            "reliance": "SEMANTIC_MATCH_DOMINANT",
        },
        "flip_explanation": "C2_SEMANTIC_SHORTCUT_RECOVERED",
        "secondary": None,
        "confidence": "HIGH",
        "narrative":
            "C2 produced the gold answer, but its stated reason attributes the "
            "price drop in the window to an article published 650 days later. The "
            "answer is scored correct while the evidential chain is temporally "
            "invalid. C1, which could see that Article 3 is dated 2023, never "
            "cited it, and instead lost the item on a numeric-precision argument "
            "about option C (124.29 vs the stated 124.57). This is the clearest "
            "case in the set where accuracy improves while grounding degrades.",
    },
    252: {
        "c1": {
            "temporal_use": "EXPLICIT_TEMPORAL_USE",
            "observable_basis": "rationale anchors the article to the series - "
                                "'Article 11 (Jan 26) ... but the price series "
                                "around Jan 23-25 shows GILD fluctuating in a "
                                "narrow ~$82-84 range'",
            "evidence_class": "GT",
            "evidence_admissible": True,
            "admissibility_note": "cited the ground-truth article only",
            "reliance": "TEMPORAL_GATING_VISIBLE",
        },
        "c2": {
            "temporal_use": "NO_VISIBLE_TEMPORAL_USE",
            "observable_basis": "rationale states the anchor is missing: no "
                                "'skepticism/optimism reaction tied to a specific "
                                "FDA news date', and describes only 'price "
                                "oscillating narrowly between roughly $82-$84 "
                                "throughout the entire period'",
            "evidence_class": "GT",
            "evidence_admissible": True,
            "admissibility_note": "cited the ground-truth article only",
            "reliance": "SEMANTIC_MATCH_DOMINANT",
        },
        "flip_explanation": "CONSISTENT_WITH_TIMESTAMP_HELP",
        "secondary": None,
        "confidence": "HIGH",
        "narrative":
            "Options B and D describe the same price behaviour and differ only in "
            "whether it is read relative to the announcement instant: B calls it "
            "stability, D calls it a muted reaction to the news. The ground-truth "
            "article itself never names the date - it says 'Before the end of last "
            "year' - so the publication timestamp is the only thing that ties the "
            "series to the announcement. C1 used it and chose D; C2's rationale "
            "explicitly reports that it cannot tie any reaction to a news date and "
            "falls back to B. No alias is involved in either condition: the "
            "mechanism is loss of the announcement anchor, not distractor "
            "confusion. One honest caveat: C1's own temporal reasoning was "
            "imperfect (it read Jan 23-25, which precedes publication, as the "
            "reaction), so the timestamp led it to the gold option without a fully "
            "valid inference.",
    },
    265: {
        "c1": {
            "temporal_use": "EXPLICIT_TEMPORAL_USE",
            "observable_basis": "rationale aligns article and series by date - "
                                "'peaking near $73.83 on 2022-08-01 and then "
                                "falling to about $68.50-68.60 by 2022-08-04 13:40 "
                                "... coinciding with the timing of Article 8 "
                                "published 2022-08-04'",
            "evidence_class": "GT",
            "evidence_admissible": True,
            "admissibility_note": "cited the ground-truth article only; the seven "
                                  "aliases in the pool were not used",
            "reliance": "TEMPORAL_GATING_VISIBLE",
        },
        "c2": {
            "temporal_use": "IMPLICIT_TEMPORAL_USE",
            "observable_basis": "rationale reasons over ordinal positions "
                                "('positions ~119-130' to 'positions 154-155') and "
                                "attributes the move to 'the Q4 earnings beat and "
                                "raised estimates discussed in Article 7/10'",
            "evidence_class": "MULTIPLE",
            "evidence_admissible": False,
            "admissibility_note": "of the three cited articles, Article 7 is a "
                                  "historical alias at -125.9 days (2022-03-31) and "
                                  "Article 10 a future alias at +279.1 days "
                                  "(2023-05-10); only Article 8 (GT) is admissible, "
                                  "and the causal claim rests on the two aliases",
            "reliance": "SEMANTIC_MATCH_DOMINANT",
        },
        "flip_explanation": "C2_SEMANTIC_SHORTCUT_RECOVERED",
        "secondary": "C1_TEMPORAL_HEURISTIC_MISLED",
        "confidence": "HIGH",
        "narrative":
            "C2 answered D, the gold, and explained the rise by an earnings beat "
            "described in two articles dated four months before and nine months "
            "after the window. C1, with the dates visible, cited only the "
            "ground-truth article, anchored on the segment immediately preceding "
            "publication, read it as a decline of over $5 and answered A. Both "
            "segments are real: the series both rises earlier and falls at the end. "
            "The timestamp told C1 which segment was 'after the announcement' and "
            "that reading did not match the gold; without it, C2 read the larger "
            "rise and matched. The primary observable mechanism is C2's recovery "
            "through inadmissible evidence; the secondary one is C1 anchoring on "
            "the pre-publication tail.",
    },
    274: {
        "c1": {
            "temporal_use": "IMPLICIT_TEMPORAL_USE",
            "observable_basis": "rationale refers to the reporting cycle only in "
                                "relative terms - 'despite estimates flatlining "
                                "over the past month' - wording that is present "
                                "unchanged in both conditions",
            "evidence_class": "GT",
            "evidence_admissible": True,
            "admissibility_note": "cited the ground-truth article only",
            "reliance": "SEMANTIC_MATCH_DOMINANT",
        },
        "c2": {
            "temporal_use": "EXPLICIT_TEMPORAL_USE",
            "observable_basis": "rationale is a period-attribution argument - "
                                "'$490,000 (a current, not prior-year, figure)' vs "
                                "'a prior-year ASP of $430,000'",
            "evidence_class": "GT",
            "evidence_admissible": True,
            "admissibility_note": "cited the ground-truth article only",
            "reliance": "MIXED",
        },
        "flip_explanation": "POSSIBLY_TIMESTAMP_RELATED",
        "secondary": None,
        "confidence": "LOW",
        "narrative":
            "C2's error is a period-attribution error, and this ground-truth "
            "article is the most heavily masked of any in the discordant set (26 "
            "masked spans, including 'first-quarter 2021' -> '[QUARTER] [YEAR]' and "
            "the Q1/Q2/Q3/Q4-of-2022 community-count sequence), so the article's "
            "period labels are exactly what C2 could no longer see. That makes a "
            "timestamp link plausible. It is not demonstrated, however: the two "
            "sentences C2's rationale actually quotes - 'The average selling price "
            "of homes delivered was $490,000, up 10% year over year' and 'suggesting "
            "an increase from $430,000 in the year-ago period' - are byte-identical "
            "in C1 and C2, so the information the model used was available in both. "
            "Reported as possibly related, with low confidence, rather than as a "
            "timestamp effect.",
    },
}

CATEGORY_SETS = {
    "C1_CORRECT_C2_WRONG": ["CONSISTENT_WITH_TIMESTAMP_HELP",
                            "POSSIBLY_TIMESTAMP_RELATED",
                            "NO_OBSERVABLE_TIMESTAMP_EFFECT", "UNCLEAR"],
    "C1_WRONG_C2_CORRECT": ["C1_TEMPORAL_HEURISTIC_MISLED",
                            "C2_SEMANTIC_SHORTCUT_RECOVERED",
                            "LIKELY_RUN_VARIABILITY", "OTHER_OBSERVABLE_MECHANISM",
                            "UNCLEAR"],
}


def md_table(case):
    lines = ["| pos | role | ticker | published (C1) | offset d | event | tier | title |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for e in case["evidence_pool"]:
        role = {"GT": "**GT**", "TYPE_A_TEMPORAL_ALIAS": "A",
                "TYPE_B_ABSENCE": "B"}[e["role"]]
        tier = e["event_match_tier"] or e.get("type_b_relation_tier") or "-"
        if e["role"] == "TYPE_A_TEMPORAL_ALIAS":
            tier = "%s / %s" % (tier, e["alias_direction"])
        lines.append("| %d | %s | %s | %s | %+.1f | %s | %s | %s |"
                     % (e["position"], role, e["ticker"], e["published_utc"],
                        e["offset_days"], e["event_type"] or "-", tier,
                        e["title"].replace("|", "\\|")))
    return "\n".join(lines)


def cited_md(rec):
    if not rec["evidence_resolved"]:
        return "_no article cited_"
    out = []
    for e in rec["evidence_resolved"]:
        r = e["resolves_to"]
        if r is None:
            out.append("- Article %s -> **out of range**" % e["cited_article_number"])
            continue
        extra = ""
        if r["role"] == "TYPE_A_TEMPORAL_ALIAS":
            extra = " (%s alias, %+.1f days, %s match)" % (
                r["alias_direction"], r["offset_days"], r["event_match_tier"])
        elif r["role"] == "TYPE_B_ABSENCE":
            extra = " (absence evidence, %+.1f days)" % r["offset_days"]
        out.append("- Article %s -> position %d, **%s**%s - %s"
                   % (e["cited_article_number"], r["position"], r["role"], extra,
                      r["title"]))
    return "\n".join(out)


def main():
    cases = json.load(open(DUMP, encoding="utf-8"))
    table = json.load(open("results/c1_c2_transition_table.json", encoding="utf-8"))
    audit = json.load(open("results/c1_c2_masking_audit.json", encoding="utf-8"))
    stats = json.load(open("results/c1_c2_citation_stats.json", encoding="utf-8"))

    analysis = []
    for c in cases:
        i = c["instance_id"]
        it = INTERPRETATION[i]
        assert it["flip_explanation"] in CATEGORY_SETS[c["transition"]], i
        analysis.append({
            "instance_id": i,
            "ticker": c["task"]["ticker"],
            "transition": c["transition"],
            "gold_answer": c["task"]["gold_answer"],
            "c1_answer": c["c1"]["prediction"], "c1_confidence": c["c1"]["confidence"],
            "c2_answer": c["c2"]["prediction"], "c2_confidence": c["c2"]["confidence"],
            "task3_temporal_use": {"C1": it["c1"], "C2": it["c2"]},
            "task4_flip_explanation": it["flip_explanation"],
            "task4_secondary_mechanism": it["secondary"],
            "interpretation_confidence": it["confidence"],
            "narrative": it["narrative"],
            "task5_exposure": c["type_a_exposure"],
            "task6_masking_side_effect": {
                "n_textual_changes": c["masking_side_effect_audit"]["n_textual_changes"],
                "n_flagged": c["masking_side_effect_audit"]["n_flagged"],
                "verdict": ("NO_NON_TEMPORAL_MASKING_SIDE_EFFECT_FOUND"
                            if not c["masking_side_effect_audit"]["n_flagged"]
                            else "REVIEW REQUIRED"),
            },
            "invariants_verified": c["c1_vs_c2_input_difference"]["unchanged"],
        })

    def group(g):
        return [a for a in analysis if a["transition"] == g]

    hurt, helped = group("C1_CORRECT_C2_WRONG"), group("C1_WRONG_C2_CORRECT")

    def agg(rows, field):
        return [rows[0]["task5_exposure"][field] for rows in [rows]] if False else \
            [r["task5_exposure"][field] for r in rows]

    counts = {}
    for g, cats in CATEGORY_SETS.items():
        counts[g] = {c: sum(1 for a in group(g) if a["task4_flip_explanation"] == c)
                     for c in cats}

    out = {
        "scope": "post-hoc error analysis of the frozen Sonnet-5 C1/C2 results; "
                 "no benchmark file, distractor, mask, option or model output was "
                 "modified, and no inference was run",
        "aggregate": table["aggregate"],
        "transition_matrix": table["transition_matrix"],
        "group_instance_ids": table["group_instance_ids"],
        "discordant_instance_ids": [a["instance_id"] for a in analysis],
        "cases": analysis,
        "task4_category_counts": counts,
        "task5_group_comparison": {
            "note": "descriptive only; n = 2 vs 4, no significance testing",
            "C1_CORRECT_C2_WRONG": {
                "instance_ids": [a["instance_id"] for a in hurt],
                "n_type_a": [a["task5_exposure"]["n_type_a"] for a in hurt],
                "n_type_b": [a["task5_exposure"]["n_type_b"] for a in hurt],
                "tiers": [a["task5_exposure"]["type_a_tiers"] for a in hurt],
                "direction": [a["task5_exposure"]["type_a_direction"] for a in hurt],
                "abs_offset_days": [a["task5_exposure"]["type_a_abs_offset_days"]
                                    for a in hurt],
                "n_cases_citing_an_alias_in_c2": sum(
                    1 for a in hurt if a["task3_temporal_use"]["C2"]["evidence_class"]
                    in ("TYPE_A_TEMPORAL_ALIAS", "MULTIPLE")),
            },
            "C1_WRONG_C2_CORRECT": {
                "instance_ids": [a["instance_id"] for a in helped],
                "n_type_a": [a["task5_exposure"]["n_type_a"] for a in helped],
                "n_type_b": [a["task5_exposure"]["n_type_b"] for a in helped],
                "tiers": [a["task5_exposure"]["type_a_tiers"] for a in helped],
                "direction": [a["task5_exposure"]["type_a_direction"] for a in helped],
                "abs_offset_days": [a["task5_exposure"]["type_a_abs_offset_days"]
                                    for a in helped],
                "n_cases_citing_an_alias_in_c2": sum(
                    1 for a in helped if a["task3_temporal_use"]["C2"]["evidence_class"]
                    in ("TYPE_A_TEMPORAL_ALIAS", "MULTIPLE")),
            },
            "answers": {
                "are_timestamp_hurt_cases_exposed_to_more_type_a":
                    "no - both hurt cases carry 7A/3B, the same or slightly more "
                    "than the improvement cases (7,7,6,7 A). Exposure does not "
                    "separate the groups; use does.",
                "are_c2_improvement_cases_dominated_by_type_b":
                    "no - they are 6-7 Type A each, the same as the rest. What "
                    "distinguishes them is that 2 of the 4 actually cited an alias "
                    "in C2 (176, 265), while neither hurt case cited any distractor "
                    "in either condition.",
                "are_future_aliases_disproportionately_involved":
                    "descriptively yes. The improvement group's Type-A pools are "
                    "23 future vs 4 historical, and 2 of the 3 aliases cited in C2 "
                    "are future (+650.2 d in 176, +279.1 d in 265; the third is "
                    "-125.9 d in 265). The one hurt case whose aliases are entirely "
                    "historical (252) saw no alias cited at all. With six cases this "
                    "is a description, not a finding.",
            },
        },
        "supplementary_citation_statistics": {
            "note": "all 50 instances, descriptive; the discordant numbers have no "
                    "meaning without this denominator",
            "C1": {k: stats["conditions"]["C1"][k] for k in
                   ("n_citing_gt", "n_citing_only_gt", "n_citing_type_a",
                    "n_citing_type_b", "n_citing_any_distractor",
                    "n_citing_nothing")},
            "C2": {k: stats["conditions"]["C2"][k] for k in
                   ("n_citing_gt", "n_citing_only_gt", "n_citing_type_a",
                    "n_citing_type_b", "n_citing_any_distractor",
                    "n_citing_nothing")},
            "instances_scored_correct_while_citing_a_temporal_alias": {
                "C1": stats["conditions"]["C1"]["correct_and_citing_type_a"],
                "C2": stats["conditions"]["C2"]["correct_and_citing_type_a"],
            },
        },
        "task6_masking_audit": {
            "self_test": audit["auditor_self_test"],
            "discordant_scope": audit["discordant_scope"],
            "all50_scope": audit["all50_scope"],
            "flag_adjudication": (
                "the four flags in the all-50 sweep are all in instance 215 (not "
                "discordant) and all are genuine calendar years in French-language "
                "articles - 'au niveau de 2019', 'decembre 2021', 'par rapport a "
                "2020'. They were raised by the deliberately over-sensitive numeric "
                "guard, not by a real side effect; contexts are recorded in "
                "results/c1_c2_masking_flag_context.json."),
            "verdict": "NO_NON_TEMPORAL_MASKING_SIDE_EFFECT_FOUND",
        },
        "design_observations": {
            "no_post_publication_price_points":
                "re-derived here: 0 of 50 instances contain any time-series point "
                "after the ground-truth article's publication timestamp, and the "
                "same holds for all six discordant instances (gaps of 0.0 to 17.4 "
                "hours). Answer options that assert a move 'following the news' are "
                "therefore unverifiable from the window - a fact only a "
                "timestamp-grounded reader can notice. This is the mechanism behind "
                "both C1_TEMPORAL_HEURISTIC_MISLED cases (18, 96).",
            "options_retain_absolute_dates_in_c2":
                "26 of 50 instances (including discordant 96, 252, 274) carry "
                "absolute temporal tokens inside the MCQA question or options. By "
                "protocol the MCQA text is byte-identical across C0-C3, so in C2 an "
                "option can name a date that the evidence context no longer "
                "contains. Recorded as an observed asymmetry; nothing was changed.",
            "accuracy_and_grounding_move_in_opposite_directions":
                "C2 scores higher (46/50 vs 44/50) while citing temporal aliases in "
                "8 instances against C1's 1, and citing the ground-truth article "
                "alone in 34 instances against C1's 46. Seven of the eight "
                "alias-citing C2 instances are scored correct.",
        },
        "limitations": [
            "single run per condition per instance; no repeat sampling, so no "
            "within-condition variability estimate exists and 'run variability' "
            "cannot be quantified - it was not needed as an explanation for any of "
            "the six cases",
            "rationales are self-reported and may not reflect the computation that "
            "produced the answer; every judgement here is about what the model "
            "stated and cited, not about what it internally did",
            "six discordant cases out of fifty; all group comparisons are "
            "descriptive",
        ],
    }
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    # ---- markdown ---------------------------------------------------------
    md = ["# C1 <-> C2 discordant cases - Sonnet-5, final frozen benchmark", "",
          "Post-hoc error analysis. No benchmark file, distractor, mask, question, "
          "option or model output was modified, and no inference was run.", "",
          "C1 = 44/50 (0.88) with timestamps. C2 = 46/50 (0.92) with temporal "
          "information removed. Transition matrix: BOTH_CORRECT %d, "
          "C1_CORRECT_C2_WRONG %d %s, C1_WRONG_C2_CORRECT %d %s, BOTH_WRONG %d %s."
          % (table["transition_matrix"]["BOTH_CORRECT"],
             table["transition_matrix"]["C1_CORRECT_C2_WRONG"],
             table["group_instance_ids"]["C1_CORRECT_C2_WRONG"],
             table["transition_matrix"]["C1_WRONG_C2_CORRECT"],
             table["group_instance_ids"]["C1_WRONG_C2_CORRECT"],
             table["transition_matrix"]["BOTH_WRONG"],
             table["group_instance_ids"]["BOTH_WRONG"]), ""]
    for c in cases:
        i = c["instance_id"]
        it = INTERPRETATION[i]
        t, e = c["task"], c["type_a_exposure"]
        arrow = ("C1 correct -> C2 wrong" if c["transition"] == "C1_CORRECT_C2_WRONG"
                 else "C1 wrong -> C2 correct")
        md += ["---", "", "# Instance %d - %s" % (i, t["ticker"]), "",
               "Transition: %s" % arrow, "", "## Task", "",
               "```", t["question_and_options"], "```", "",
               "- gold answer: **%s**" % t["gold_answer"],
               "- ground-truth article: position %d, event `%s`, published %s"
               % (t["gt_position_in_pool"], t["gt_event_type"], t["gt_published_utc"]),
               "- time series: %d points" % t["n_ts_points"], ""]
        for cond in ("c1", "c2"):
            r = c[cond]
            md += ["## %s" % cond.upper(), "",
                   "- answer **%s** (%s), confidence %s"
                   % (r["prediction"], "correct" if r["correct"] else "incorrect",
                      r["confidence"]),
                   "- rationale: %s" % r["rationale"], "",
                   "Cited evidence:", "", cited_md(r), ""]
        md += ["## Evidence pool", "", md_table(c), "",
               "Composition: %dA / %dB; Type-A tiers %s; direction %s; "
               "|offset| min %s / median %s / max %s days."
               % (e["n_type_a"], e["n_type_b"], e["type_a_tiers"],
                  e["type_a_direction"], e["type_a_abs_offset_days"]["min"],
                  e["type_a_abs_offset_days"]["median"],
                  e["type_a_abs_offset_days"]["max"]), "",
               "## What changed between C1 and C2", "",
               "- time series axis: `%s` -> `%s`"
               % (c["c1_vs_c2_input_difference"]["ts_c1_first_two_lines"][0],
                  c["c1_vs_c2_input_difference"]["ts_c2_first_two_lines"][0]),
               "- article publication timestamps: %d shown in C1, 0 in C2"
               % c["c1_vs_c2_input_difference"]["n_article_publication_timestamps_removed"],
               "- in-article temporal expressions masked: %d spans -> "
               "`[DATE]` / `[YEAR]` / `[QUARTER]`"
               % c["c1_vs_c2_input_difference"]["n_in_article_temporal_masks"],
               "",
               "Verified unchanged: question and options (byte-identical), ticker, "
               "gold answer, time-series numeric values and length, article "
               "identities and order, article count, and all non-temporal article "
               "text. Re-masking the C1 articles reproduces the C2 articles byte "
               "for byte. Diff audit: %d textual changes, %d flagged."
               % (c["masking_side_effect_audit"]["n_textual_changes"],
                  c["masking_side_effect_audit"]["n_flagged"]), "",
               "## Interpretation", "",
               "- observable temporal use in C1: **%s** - %s"
               % (it["c1"]["temporal_use"], it["c1"]["observable_basis"]),
               "- observable temporal use in C2: **%s** - %s"
               % (it["c2"]["temporal_use"], it["c2"]["observable_basis"]),
               "- evidence relied on: C1 **%s**, C2 **%s**"
               % (it["c1"]["evidence_class"], it["c2"]["evidence_class"]),
               "- temporal admissibility of the cited evidence: C1 %s; C2 %s"
               % (it["c1"]["admissibility_note"], it["c2"]["admissibility_note"]),
               "- semantic vs temporal reliance: C1 **%s**, C2 **%s**"
               % (it["c1"]["reliance"], it["c2"]["reliance"]),
               "- most likely explanation of the flip: **%s**%s"
               % (it["flip_explanation"],
                  "" if not it["secondary"] else
                  " (secondary: %s)" % it["secondary"]),
               "- confidence in this interpretation: **%s**" % it["confidence"], "",
               it["narrative"], ""]

    md += ["---", "", "# Category counts", ""]
    for g, cats in counts.items():
        md += ["**%s**" % g, ""]
        md += ["- %s: %d" % (k, v) for k, v in cats.items()]
        md += [""]
    md += ["No case required `LIKELY_RUN_VARIABILITY`: each of the four "
           "C1-wrong/C2-correct flips has an observable input-use explanation.", "",
           "# Masking side-effect audit", "",
           "Discordant scope (task 6): **%s** - %d textual changes across the six "
           "cases, 0 flagged."
           % (audit["discordant_scope"]["verdict"],
              sum(c["masking_side_effect_audit"]["n_textual_changes"] for c in cases)),
           "", "All 50 instances (superset): 5902 textual changes, 4 flagged, all "
           "in instance 215 and all adjudicated as genuine calendar years in "
           "French-language articles. The auditor was self-tested against injected "
           "clause deletion, entity substitution, negation flips and non-date "
           "number edits, and caught all four.", ""]

    with open(OUT_MD, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md))

    print("wrote %s" % OUT_JSON)
    print("wrote %s" % OUT_MD)
    for g, cats in counts.items():
        print("%s: %s" % (g, {k: v for k, v in cats.items() if v}))


if __name__ == "__main__":
    main()
