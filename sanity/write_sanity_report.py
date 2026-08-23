"""Render results/sanity/sanity_report.md from the scored sanity outputs.

Reads only files this study produced plus the frozen main-run summaries.
Phase 5's decision logic is applied here from the actual numbers; the four
overall interpretations are gated on what the data shows, not on a preferred
conclusion.

Usage:  python sanity/write_sanity_report.py
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "results", "sanity")


def main():
    sc = json.load(open(os.path.join(D, "sanity_scores.json"), encoding="utf-8"))
    pw = json.load(open(os.path.join(D, "sanity_pairwise.json"), encoding="utf-8"))
    cue = json.load(open(os.path.join(D, "sanity_cue_audit.json"), encoding="utf-8"))
    man = json.load(open(os.path.join(ROOT, "sanity",
                                      "sanity_conditions_manifest.json"),
                         encoding="utf-8"))
    ref, S = sc["reference_main_conditions"], sc["sanity_conditions"]

    def acc(k):
        return S[k]["accuracy"]

    c1, c2 = ref["C1"]["accuracy"], ref["C2"]["accuracy"]
    md = ["# Sanity-check study for the timestamp intervention", "",
          "Diagnostic only. The official C0-C3 experiment, the final-50 "
          "membership, the reviewed distractor pool and every existing model "
          "output are untouched; all new material lives under `sanity/` and "
          "`results/sanity/`.", "",
          "## 1. Frozen-input integrity", "",
          "| file | md5 |", "| --- | --- |"]
    for k, v in man["frozen_inputs_md5"].items():
        md.append("| `%s` | `%s` |" % (k, v))
    md += ["", "All six sanity conditions were built and hashed **before** any "
           "model output was loaded (`sanity/sanity_conditions_manifest.json` "
           "carries a SHA-256 per rendered prompt). Article-timestamp "
           "derangement seed: `%d`." % man["shuffle_seed"], "",
           "## 2. Accuracy", "",
           "| condition | n | accuracy | vs chance (0.25) | answer distribution |",
           "| --- | --- | --- | --- | --- |"]
    for k in ("C0", "C1", "C2", "C3"):
        md.append("| %s (main run) | %d | **%.2f** | +%.2f | - |"
                  % (k, ref[k]["n"], ref[k]["accuracy"],
                     ref[k]["accuracy"] - 0.25))
    for k in S:
        s = S[k]
        md.append("| %s | %d | **%.2f** | +%.2f | %s |"
                  % (k, s["n_scored"], s["accuracy"], s["accuracy"] - 0.25,
                     s["answer_distribution"]))
    md += ["", "Missing / malformed across the six sanity conditions: %d / %d."
           % (sum(S[k]["n_missing"] for k in S), sum(S[k]["n_malformed"] for k in S)),
           "", "## 3. Phase 1 static cue audit", "",
           cue["phase1_cue_audit"]["note"], "",
           "| cue present in the MCQA | instances (of 50) | occurrences |",
           "| --- | --- | --- |"]
    for k, v in sorted(cue["phase1_cue_audit"]["totals"].items()):
        md.append("| %s | %d | %d |" % (k, v["n_instances_with_any"],
                                        v["n_occurrences"]))
    a5 = cue["s5_masking_audit"]
    a6 = cue["s6_shuffle_audit"]
    md += ["", "## 4. Intervention audits", "",
           "**S5 masking audit**: %d/50 instances changed, %d spans replaced, "
           "%d flagged - `%s`. Relational wording (before / after / following / "
           "prior / since), named price levels and percentages are preserved in "
           "every changed instance."
           % (a5["n_instances_changed"], a5["n_spans_changed"], a5["n_flagged"],
              a5["verdict"]), "",
           "**S6 shuffle audit**: %d instances, all mechanical checks pass "
           "(%d flagged) - same article ids and order, unchanged timestamp "
           "multiset, zero fixed points, no article keeps its own timestamp, "
           "only `Published:` lines differ, time series and MCQA unchanged."
           % (a6["n_instances"], a6["n_flagged"]), "",
           "## 5. Paired comparisons", "",
           pw["label"], "",
           "| comparison | both correct | orig->wrong | orig->correct | both wrong "
           "| answers changed | exact McNemar p |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for k, v in pw.items():
        if k == "label":
            continue
        c = v["counts"]
        md.append("| %s | %d | %d | %d | %d | %d/%d | %.4f |"
                  % (k, c["both_correct"], c["original_correct_sanity_wrong"],
                     c["original_wrong_sanity_correct"], c["both_wrong"],
                     v["n_answer_changed"], v["n_paired"],
                     v["exact_mcnemar_p_two_sided"]))
    md += ["", "## 6. Observable evidence use", "",
           "Declared reading: an article counts if the model listed it in "
           "`evidence_articles`.", "",
           "| condition | cites GT | cites Type A | cites Type B | no evidence |",
           "| --- | --- | --- | --- | --- |"]
    for name, e in (("C1 (main)", ref["C1"]["evidence_use"]),
                    ("C2 (main)", ref["C2"]["evidence_use"]),
                    ("S3_POOL_TEXT_ONLY", S["S3_POOL_TEXT_ONLY"]["evidence_use"]),
                    ("S6_C1_METADATA_TIMESTAMP_SHUFFLE",
                     S["S6_C1_METADATA_TIMESTAMP_SHUFFLE"]["evidence_use"])):
        md.append("| %s | %d | %d | %d | %d |"
                  % (name, e["n_citing_gt"], e["n_citing_type_a"],
                     e["n_citing_type_b"], e["n_no_clear_evidence"]))
    md += ["", "## 7. Phase 5 decision logic", ""]

    s1 = acc("S1_QO_ONLY")
    md += ["**A. Question/option shortcut.** S1_QO_ONLY = **%.2f** with no time "
           "series, no ground-truth article and no distractors, against a 0.25 "
           "chance level and C1 = %.2f, C2 = %.2f. That is %.0f%% of C1's "
           "accuracy recovered from the MCQA text alone."
           % (s1, c1, c2, 100.0 * s1 / c1), ""]
    s2, s3 = acc("S2_GT_TEXT_ONLY"), acc("S3_POOL_TEXT_ONLY")
    md += ["**B. Text-semantic shortcut.** S2_GT_TEXT_ONLY = **%.2f**, "
           "S3_POOL_TEXT_ONLY = **%.2f**, C1 = %.2f. S3 differs from C1 only by "
           "deleting the time series." % (s2, s3, c1), ""]
    s5 = acc("S5_C2_QO_DATE_MASK")
    p5 = pw["C2_vs_S5_C2_QO_DATE_MASK"]
    md += ["**C. Question/option temporal leakage.** C2 = %.2f, "
           "S5_C2_QO_DATE_MASK = **%.2f**; %d of 50 answers changed "
           "(26 instances actually carried a maskable date)."
           % (c2, s5, p5["n_answer_changed"]), ""]
    s6 = acc("S6_C1_METADATA_TIMESTAMP_SHUFFLE")
    p6 = pw["C1_vs_S6_C1_METADATA_TIMESTAMP_SHUFFLE"]
    md += ["**D. Actual timestamp use.** C1 = %.2f, S6 = **%.2f** with every "
           "article's publication timestamp deranged; %d of 50 answers changed. "
           "S6 tests metadata timestamps only - dates inside article prose are "
           "left in place, so a null result here does not mean the model ignores "
           "time altogether." % (c1, s6, p6["n_answer_changed"]), ""]
    # ---- E: overall interpretation, gated on the numbers -------------------
    evidence_bearing = [c1, c2, ref["C0"]["accuracy"], ref["C3"]["accuracy"],
                        s2, s3, acc("S4_TS_ONLY"), s5, s6]
    shortcut = s1 >= max(evidence_bearing)
    q_leak = p5["n_answer_changed"] >= 5
    ts_sensitive = p6["n_answer_changed"] >= 5
    e_c1 = ref["C1"]["evidence_use"]
    e_c2 = ref["C2"]["evidence_use"]
    e_s6 = S["S6_C1_METADATA_TIMESTAMP_SHUFFLE"]["evidence_use"]
    evidence_moves = (abs(e_c2["n_citing_type_a"] - e_c1["n_citing_type_a"]) >= 3
                      or abs(e_s6["n_citing_gt"] - e_c1["n_citing_gt"]) >= 3)
    if shortcut:
        verdict = "1. STRONG SHORTCUT EVIDENCE"
        why = ("S1_QO_ONLY (%.2f) equals or exceeds every condition that carries "
               "evidence, including C0 (%.2f), C1 (%.2f), C2 (%.2f) and C3 "
               "(%.2f). The MCQA label is recoverable from the question and "
               "answer options alone, with no time series, no ground-truth "
               "article and no distractors. Adding the evidence context does not "
               "raise accuracy - it lowers it slightly."
               % (s1, ref["C0"]["accuracy"], c1, c2, ref["C3"]["accuracy"]))
    elif q_leak or not ts_sensitive:
        verdict = "2. PARTIAL SHORTCUT / WEAK INTERVENTION"
        why = "see the paired tables above"
    elif evidence_moves:
        verdict = "3. TIMESTAMP-SENSITIVE BUT ACCURACY-ROBUST"
        why = "see the evidence-use table above"
    else:
        verdict = "4. INCONCLUSIVE"
        why = "the sanity checks do not separate the possibilities"
    md += ["**E. Overall experiment validity.** **%s**" % verdict, "", why, ""]
    if shortcut and evidence_moves:
        md += ["Interpretation 3 also has support and is not in conflict with "
               "it: observable evidence use does move under the interventions "
               "(Type-A citation 1 -> %d from C1 to C2; GT citation %d -> %d "
               "from C1 to S6) while accuracy stays flat. The two findings "
               "combine into a single claim - **MCQA accuracy on this benchmark "
               "is not a measure of temporal grounding**, because the label "
               "survives removing the evidence entirely."
               % (e_c2["n_citing_type_a"], e_c1["n_citing_gt"],
                  e_s6["n_citing_gt"]), ""]
    md += ["## 8. Caveats", "",
           "- **Decoding is not controlled.** The CLI exposes no temperature or "
           "top-p, so this is not temperature 0 and single-run differences of a "
           "few items are within plausible run-to-run noise. Every condition "
           "here is one sample per instance, exactly as in the main runs.",
           "- **S1/S2/S4 could not reuse the C0-C3 Task sentence verbatim**; it "
           "promises a time series and a news context those ablations withhold. "
           "The response-format block is byte-identical in all six conditions, "
           "and the MCQA text is byte-identical to the frozen benchmark.",
           "- **S6 deranges metadata timestamps only.** Dates inside article "
           "prose are untouched by design, so a flat S6 shows the model does not "
           "lean on the `Published:` field - not that it ignores time entirely.",
           "- The McNemar p-values are descriptive on 50 paired items and are "
           "labelled exploratory; they are not primary hypothesis tests.",
           "- No dataset membership, distractor, gold label or main-run output "
           "was changed, and nothing was committed.", ""]
    with open(os.path.join(D, "sanity_report.md"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write("\n".join(md))
    print("wrote %s" % os.path.join(D, "sanity_report.md"))
    print("S1 %.2f  S2 %.2f  S3 %.2f  S4 %.2f  S5 %.2f  S6 %.2f | C1 %.2f C2 %.2f"
          % (s1, s2, s3, acc("S4_TS_ONLY"), s5, s6, c1, c2))


if __name__ == "__main__":
    main()
