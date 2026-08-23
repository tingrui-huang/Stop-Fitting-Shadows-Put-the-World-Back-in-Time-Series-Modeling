"""PHASES 3-5 - collect, score and compare the sanity conditions.

Uses collect_c0_results.py's parser unchanged, so the JSON-extraction and
validation policy is exactly the one that produced the C0-C3 records.  Evidence
use is classified with the same conservative reading as the all-50 grounding
audit: an article counts as support if the model listed it, and articles a
rationale never mentions are reported separately.

Nothing here modifies the main experiment; C1/C2 records are read only for
descriptive paired comparison, after every sanity prompt was already frozen and
hashed.

Usage:  python sanity/score_sanity.py
"""

import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collect_c0_results import extract_json, read_text, validate  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "results", "sanity")
CONDS = [
    ("S1_QO_ONLY", "s1_qo_only"),
    ("S2_GT_TEXT_ONLY", "s2_gt_text_only"),
    ("S3_POOL_TEXT_ONLY", "s3_pool_text_only"),
    ("S4_TS_ONLY", "s4_ts_only"),
    ("S5_C2_QO_DATE_MASK", "s5_c2_qo_date_mask"),
    ("S6_C1_METADATA_TIMESTAMP_SHUFFLE", "s6_c1_metadata_timestamp_shuffle"),
]
POOL_CONDS = {"S3_POOL_TEXT_ONLY", "S6_C1_METADATA_TIMESTAMP_SHUFFLE"}


def jsonl(path, key="instance_id"):
    with open(path, encoding="utf-8") as f:
        return {json.loads(l)[key]: json.loads(l) for l in f if l.strip()}


def role_table():
    man = json.load(open(os.path.join(ROOT, "out_paper50_reviewed/manifest.json"),
                         encoding="utf-8"))["instances"]
    out = {}
    for m in man:
        d = {x["article_id"]: x for x in m["distractors"]}
        r = {}
        for pos, aid in enumerate(m["article_order"], 1):
            if pos == m["gt_position"]:
                r[pos] = {"role": "GT", "offset_days": 0.0, "alias_direction": None}
            else:
                a = d[aid]
                is_a = a["distractor_type"] == "temporal_aliasing"
                r[pos] = {"role": "TYPE_A" if is_a else "TYPE_B",
                          "offset_days": a["offset_days"],
                          "alias_direction": a["alias_direction"] if is_a else None}
        out[m["instance_id"]] = r
    return out


def collect(slug, cond):
    index = [json.loads(l) for l in open(
        os.path.join(ROOT, "sanity", "cli", slug, "index.jsonl"), encoding="utf-8")
        if l.strip()]
    raw_dir = os.path.join(OUTDIR, "%s_raw" % slug)
    recs, missing, malformed = [], [], []
    for e in index:
        iid = e["instance_id"]
        p = os.path.join(raw_dir, "%d.txt" % iid)
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            missing.append(iid)
            continue
        raw = read_text(p)
        fields, err = validate(extract_json(raw))
        if err:
            malformed.append({"instance_id": iid, "reason": err})
            continue
        recs.append({
            "instance_id": iid, "condition": cond, "model": "sonnet-5",
            "prediction": fields["prediction"], "confidence": fields["confidence"],
            "rationale": fields["rationale"],
            "evidence_articles": fields["evidence_articles"],
            "gold_answer": e["gold_answer"],
            "correct": fields["prediction"] == e["gold_answer"],
            "raw_output": raw,
        })
    recs.sort(key=lambda r: r["instance_id"])
    with open(os.path.join(OUTDIR, "%s.jsonl" % slug), "w", encoding="utf-8",
              newline="\n") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return recs, missing, malformed


def evidence_use(recs, roles):
    """Declared-evidence reading, plus the rationale-mention subset."""
    out = {"n_citing_gt": 0, "n_citing_type_a": 0, "n_citing_type_b": 0,
           "n_no_clear_evidence": 0, "n_out_of_range": 0,
           "gt_ids": [], "type_a_ids": [], "type_b_ids": [],
           "no_evidence_ids": [],
           "n_citing_gt_rationale_reading": 0,
           "n_citing_type_a_rationale_reading": 0}
    for r in recs:
        i = r["instance_id"]
        rt = roles[i]
        cites = r.get("evidence_articles") or []
        got = [rt[n]["role"] if n in rt else None for n in cites]
        mentioned = {int(x) for x in re.findall(r"Article\s+(\d+)", r["rationale"])}
        got_m = [rt[n]["role"] for n in mentioned if n in rt]
        out["n_out_of_range"] += sum(1 for g in got if g is None)
        if not cites:
            out["n_no_clear_evidence"] += 1
            out["no_evidence_ids"].append(i)
        if "GT" in got:
            out["n_citing_gt"] += 1
            out["gt_ids"].append(i)
        if "TYPE_A" in got:
            out["n_citing_type_a"] += 1
            out["type_a_ids"].append(i)
        if "TYPE_B" in got:
            out["n_citing_type_b"] += 1
            out["type_b_ids"].append(i)
        if "GT" in got_m:
            out["n_citing_gt_rationale_reading"] += 1
        if "TYPE_A" in got_m:
            out["n_citing_type_a_rationale_reading"] += 1
    return out


def score(recs, missing, malformed, roles, cond):
    n = len(recs)
    dist = {}
    for r in recs:
        dist[r["prediction"]] = dist.get(r["prediction"], 0) + 1
    confs = [r["confidence"] for r in recs]
    s = {
        "condition": cond, "n_expected": 50, "n_scored": n,
        "n_correct": sum(r["correct"] for r in recs),
        "accuracy": round(sum(r["correct"] for r in recs) / n, 4) if n else None,
        "correct_ids": sorted(r["instance_id"] for r in recs if r["correct"]),
        "incorrect_ids": sorted(r["instance_id"] for r in recs if not r["correct"]),
        "answer_distribution": dict(sorted(dist.items())),
        "mean_confidence": round(sum(confs) / n, 4) if n else None,
        "n_missing": len(missing), "missing_ids": missing,
        "n_malformed": len(malformed), "malformed": malformed,
    }
    if cond in POOL_CONDS:
        s["evidence_use"] = evidence_use(recs, roles)
    return s


def mcnemar_exact(b, c):
    """Two-sided exact binomial p for the discordant pairs. Descriptive only."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, j) for j in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def paired(a_recs, b_recs, a_name, b_name):
    a = {r["instance_id"]: r for r in a_recs}
    b = {r["instance_id"]: r for r in b_recs}
    ids = sorted(set(a) & set(b))
    cells = {"both_correct": [], "original_correct_sanity_wrong": [],
             "original_wrong_sanity_correct": [], "both_wrong": []}
    changed = []
    for i in ids:
        ac, bc = a[i]["correct"], b[i]["correct"]
        key = ("both_correct" if ac and bc else
               "original_correct_sanity_wrong" if ac else
               "original_wrong_sanity_correct" if bc else "both_wrong")
        cells[key].append(i)
        if a[i]["prediction"] != b[i]["prediction"]:
            changed.append(i)
    nb = len(cells["original_correct_sanity_wrong"])
    nc = len(cells["original_wrong_sanity_correct"])
    return {
        "original": a_name, "sanity": b_name, "n_paired": len(ids),
        "counts": {k: len(v) for k, v in cells.items()},
        "instance_ids": cells,
        "n_answer_changed": len(changed),
        "answer_change_rate": round(len(changed) / len(ids), 4) if ids else None,
        "answer_changed_ids": changed,
        "exact_mcnemar_p_two_sided": round(mcnemar_exact(nb, nc), 4),
        "label": "EXPLORATORY / SANITY-CHECK - not a primary hypothesis test",
    }


def main():
    roles = role_table()
    scores, all_recs = {}, {}
    for cond, slug in CONDS:
        recs, missing, malformed = collect(slug, cond)
        all_recs[cond] = recs
        scores[cond] = score(recs, missing, malformed, roles, cond)

    main_runs = {}
    for c in ("c1", "c2"):
        main_runs[c.upper()] = list(jsonl(
            os.path.join(ROOT, "results", "paper50_%s_sonnet5.jsonl" % c)).values())
    for c in ("c0", "c3"):
        main_runs[c.upper()] = list(jsonl(
            os.path.join(ROOT, "results", "paper50_%s_sonnet5.jsonl" % c)).values())

    ref = {k: {"n": len(v), "n_correct": sum(r["correct"] for r in v),
               "accuracy": round(sum(r["correct"] for r in v) / len(v), 4)}
           for k, v in main_runs.items()}
    ref["C1"]["evidence_use"] = evidence_use(main_runs["C1"], roles)
    ref["C2"]["evidence_use"] = evidence_use(main_runs["C2"], roles)

    out = {
        "note": "diagnostic sanity checks; the official C0-C3 experiment is "
                "untouched and these numbers are not a replacement for it",
        "reference_main_conditions": ref,
        "sanity_conditions": scores,
        "chance_level": 0.25,
    }
    with open(os.path.join(OUTDIR, "sanity_scores.json"), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    pw = {
        "label": "EXPLORATORY / SANITY-CHECK analyses. Exact McNemar p-values "
                 "are reported descriptively on 50 paired items and are not "
                 "primary hypothesis tests.",
        "C1_vs_S3_POOL_TEXT_ONLY": paired(main_runs["C1"],
                                          all_recs["S3_POOL_TEXT_ONLY"],
                                          "C1", "S3_POOL_TEXT_ONLY"),
        "C2_vs_S5_C2_QO_DATE_MASK": paired(main_runs["C2"],
                                           all_recs["S5_C2_QO_DATE_MASK"],
                                           "C2", "S5_C2_QO_DATE_MASK"),
        "C1_vs_S6_C1_METADATA_TIMESTAMP_SHUFFLE": paired(
            main_runs["C1"], all_recs["S6_C1_METADATA_TIMESTAMP_SHUFFLE"],
            "C1", "S6_C1_METADATA_TIMESTAMP_SHUFFLE"),
    }
    with open(os.path.join(OUTDIR, "sanity_pairwise.json"), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(pw, f, indent=2, ensure_ascii=False)

    print("%-34s %5s %8s  %s" % ("condition", "n", "accuracy", "answer dist"))
    for k, v in ref.items():
        print("%-34s %5d %8s  (main run)" % (k, v["n"], v["accuracy"]))
    for cond, _ in CONDS:
        s = scores[cond]
        print("%-34s %5d %8s  %s  missing %d malformed %d"
              % (cond, s["n_scored"], s["accuracy"], s["answer_distribution"],
                 s["n_missing"], s["n_malformed"]))
    print("\nevidence use (declared reading):")
    print("  %-34s GT %2d  A %2d  B %2d  none %2d"
          % ("C1 (main)", ref["C1"]["evidence_use"]["n_citing_gt"],
             ref["C1"]["evidence_use"]["n_citing_type_a"],
             ref["C1"]["evidence_use"]["n_citing_type_b"],
             ref["C1"]["evidence_use"]["n_no_clear_evidence"]))
    print("  %-34s GT %2d  A %2d  B %2d  none %2d"
          % ("C2 (main)", ref["C2"]["evidence_use"]["n_citing_gt"],
             ref["C2"]["evidence_use"]["n_citing_type_a"],
             ref["C2"]["evidence_use"]["n_citing_type_b"],
             ref["C2"]["evidence_use"]["n_no_clear_evidence"]))
    for cond in POOL_CONDS:
        e = scores[cond].get("evidence_use")
        if e:
            print("  %-34s GT %2d  A %2d  B %2d  none %2d"
                  % (cond, e["n_citing_gt"], e["n_citing_type_a"],
                     e["n_citing_type_b"], e["n_no_clear_evidence"]))
    print("\npaired comparisons:")
    for k, v in pw.items():
        if k == "label":
            continue
        print("  %-42s %s  changed %d/%d  exact McNemar p=%.4f"
              % (k, v["counts"], v["n_answer_changed"], v["n_paired"],
                 v["exact_mcnemar_p_two_sided"]))
    print("\nwrote sanity_scores.json and sanity_pairwise.json")
    return out, pw


if __name__ == "__main__":
    main()
