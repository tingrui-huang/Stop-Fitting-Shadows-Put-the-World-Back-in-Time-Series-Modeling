"""Audit the union C0 failures, define the challenge 10, and freeze final50.

Inputs (never modified):
  final_hard50_data.json                     current mother set
  results/old_c0_mtbench50/c0_sonnet5.jsonl  old run 1 over c0_data.json
  results/c0_sonnet5.jsonl                   old run 2 over c0_data.json
  results/final50_c0_sonnet5.jsonl           current run over final_hard50_data.json

Outputs:
  challenge_audit.json, challenge10_manifest.json,
  final50_frozen_data.json, final50_frozen_manifest.json

The 50 anchors are kept as-is except for surgical replacement of anchors judged
INVALID as benchmark questions.  No optimisation toward any target accuracy.

Usage:  python audit_challenge.py [--seed 20260821] [--lenient]

Default rule is STRICT: an anchor is invalid when its gold answer asserts price
behaviour after the article publication time.  --lenient restores the earlier
behaviour (manual verdicts on the failure union only).
"""

import argparse
import datetime as dt
import json
import random
import re

from build_final_hard50 import load_json, load_jsonl, validate
from news_corpus import parse_article

DATA = "final_hard50_data.json"
MANIFEST = "final_hard50_manifest.json"
RUN_OLD1 = "results/old_c0_mtbench50/c0_sonnet5.jsonl"
RUN_OLD2 = "results/c0_sonnet5.jsonl"
RUN_FINAL = "results/final50_c0_sonnet5.jsonl"
POOL = ["c0_data.json", "hard50_data.json"]
UTC = dt.timezone.utc

# An option that asserts price behaviour AFTER publication cannot be checked:
# no instance in this dataset carries a single price point past the GT article's
# publication time (verified below and recorded in the audit file).
POST_PUB = re.compile(
    r"\b(after (the )?(news|announcement|publication|release)|following (the )?"
    r"(news|publication|announcement|release)|subsequently|shortly after|"
    r"immediately after|post[- ]news|since the \d{4}-\d{2}-\d{2})", re.I)

# Manual audit verdicts for the 8 union failures.  Each one is backed by the
# machine-computed evidence written into challenge_audit.json.
VERDICTS = {
    18: ("VALID_MODEL_FAILURE",
         "Gold C is a claim about the PRE-news path, fully covered by the window. "
         "It is false as written (the series is not a consistent decline: it peaks "
         "at 331.22 mid-window before ending at 319.19) and its 'deteriorating "
         "outlook' inference contradicts the article's positive Earnings ESP. The "
         "competing option D asserts a post-publication drop, which is unverifiable "
         "rather than demonstrably true, so the item still has one best answer."),
    19: ("INVALID_AMBIGUOUS_OPTIONS",
         "Two options are demonstrably false in a 'which is incorrect' question. "
         "Gold D is an unsupported overstatement, but option C cites a recovery to "
         "$116.32 'by the end of the following trading session': that figure appears "
         "nowhere in the article (only the $114.33 close does) and is above the "
         "window maximum of 115.36, and the following session is outside the window. "
         "C is therefore just as defensible an answer as D."),
    37: ("VALID_MODEL_FAILURE",
         "Gold A's substance - a significant fall driven by the recall and rate "
         "concerns - is verifiable in-window (-15.9% over the window, -8.7% in the "
         "final session) and the article documents the recall. Its 'after the news "
         "publication' phrasing is loose because the article is published at the end "
         "of the window, but every other option is contradicted: D claims +6%, B "
         "claims rates lift auto sales, C claims minimal effect. Confusing pre- and "
         "post-publication movement is exactly the failure mode under study."),
    47: ("INVALID_TEMPORAL_COVERAGE",
         "Gold B asserts that volatility increased 'since the 2021-07-16 timestamp', "
         "but the series ends 2021-07-15 19:55 - 1030 minutes before the article was "
         "published. No provided data point lies at or after the date the gold "
         "answer refers to, so the gold cannot be established from the prompt, while "
         "option D (no observable response) is at least as defensible."),
    49: ("VALID_MODEL_FAILURE",
         "Gold A is demonstrably false from in-window data: it claims GM 'actually "
         "increased in value' around the downgrade, while the window falls 7.8% "
         "(54.92 high to 49.30 close, -3.5% in the final session). Options B and C "
         "describe that same decline with loose timing but consistent magnitudes, so "
         "A is the single clearly incorrect statement."),
    201: ("INVALID_TEMPORAL_COVERAGE",
          "Gold B claims a gain of over 2% 'within the first trading session after "
          "the news release'. The series ends 125 minutes BEFORE publication, so no "
          "post-release session is present; the in-window path is -0.5% overall and "
          "-0.4% in the final session, and the article's only 2% figure is a +2.44% "
          "one-month return, a different quantity. The gold is unverifiable from the "
          "prompt."),
    265: ("VALID_MODEL_FAILURE",
          "Gold D's price levels (about 67.2 rising to about 70.94) both occur inside "
          "the window (range 64.28-73.89) and the competing options A and C claim a "
          "post-announcement drop of over $5, contradicted by the in-window rise. The "
          "'shortly after' wording is loose, but the substance is checkable and "
          "unique; the model answered it correctly in 2 of 3 runs."),
    274: ("VALID_MODEL_FAILURE",
          "Gold D's premise is present in the article ('estimates review flatlined "
          "during the past month'), so judging its 'diminishing enthusiasm' reading "
          "requires reading the article rather than guessing. Option A attributes the "
          "window's +9.0% move to the period AFTER the news release, which the data "
          "cannot support - the final session is -0.7%. All three runs picked A, "
          "which is the pre/post-publication confusion this benchmark targets."),
}


def gp_epoch(stamp):
    return dt.datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()


def options_of(question):
    opts = {}
    for letter in "ABCD":
        for line in question.splitlines():
            if line.strip().startswith(letter + "."):
                opts[letter] = line.strip()[2:].strip()
                break
    return opts


def evidence_for(rec):
    """Objective, machine-checkable facts about one anchor."""
    ts, vs = rec["ts_timestamps"], rec["ts_values"]
    gp = gp_epoch(rec["gt_published_utc"])
    title, text = parse_article(rec["gt_article_text"])
    opts = options_of(rec["mcqa_question"])
    gold = rec["mcqa_answer"]
    session = vs[-78:] if len(vs) > 78 else vs
    return {
        "n_points": len(vs),
        "ts_first_utc": dt.datetime.fromtimestamp(ts[0], UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "ts_last_utc": dt.datetime.fromtimestamp(ts[-1], UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "gt_published_utc": rec["gt_published_utc"],
        "minutes_last_point_to_publication": round((ts[-1] - gp) / 60.0, 1),
        "n_points_after_publication": sum(1 for t in ts if t > gp),
        "pct_change_window": round(100 * (vs[-1] / vs[0] - 1), 2),
        "pct_change_last_session": round(100 * (vs[-1] / session[0] - 1), 2),
        "price_min": min(vs), "price_max": max(vs),
        "question_polarity": "incorrect" if "is incorrect" in rec["mcqa_question"].lower()
                             else "correct",
        "gold_option": gold,
        "gold_text": opts.get(gold, ""),
        "gold_asserts_post_publication": bool(POST_PUB.search(opts.get(gold, ""))),
        "options_asserting_post_publication":
            sorted(k for k, v in opts.items() if POST_PUB.search(v)),
        "ticker_mentioned_in_article": rec["ticker"] in (title + text),
        "gt_article_title": title,
        "structural_checks": validate(rec),
    }


def uses_ts_and_news(rationale):
    r = rationale.lower()
    ts_signal = bool(re.search(r"\$|\d+\.\d|time series|price (data|series)|window", r))
    news_signal = bool(re.search(r"article|news|report|states|cites", r))
    return ts_signal and news_signal


def audit_one(i, rec, strict):
    """Return (category, notes, valid) for one anchor under the active rule."""
    ev = evidence_for(rec)
    manual = VERDICTS.get(i)
    if strict and ev["gold_asserts_post_publication"]:
        return ("INVALID_TEMPORAL_COVERAGE",
                "STRICT POST-PUBLICATION RULE: the gold answer asserts price "
                "behaviour after the article was published (matched %r), and no "
                "instance in this dataset carries a price point past publication "
                "(the last point is %.1f minutes before it), so the gold cannot be "
                "established from the prompt."
                % (POST_PUB.search(ev["gold_text"]).group(0),
                   -ev["minutes_last_point_to_publication"]),
                False)
    if manual:
        return (manual[0], manual[1], manual[0] == "VALID_MODEL_FAILURE")
    if not all(ev["structural_checks"].values()):
        return ("INVALID_OTHER", "structural checks failed: %s"
                % [k for k, v in ev["structural_checks"].items() if not v], False)
    if not ev["ticker_mentioned_in_article"]:
        return ("INVALID_ENTITY_MISMATCH",
                "the ticker never appears in the ground-truth article", False)
    return ("VALID", "gold answer does not depend on post-publication prices; "
                     "structure and entity checks pass", True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260821)
    ap.add_argument("--lenient", action="store_true",
                    help="disable the strict post-publication rule (previous "
                         "behaviour: only the manually audited union failures)")
    args = ap.parse_args()
    strict = not args.lenient

    data = {r["instance_id"]: r for r in load_json(DATA)}
    prev = {m["instance_id"]: m for m in json.load(
        open(MANIFEST, encoding="utf-8"))["instances"]}
    old1 = {r["instance_id"]: r for r in load_jsonl(RUN_OLD1)}
    old2 = {r["instance_id"]: r for r in load_jsonl(RUN_OLD2)}
    fin = {r["instance_id"]: r for r in load_jsonl(RUN_FINAL)}

    fail_old = sorted(set(i for i, r in old1.items() if not r["correct"])
                      | set(i for i, r in old2.items() if not r["correct"]))
    fail_fin = sorted(i for i, r in fin.items() if not r["correct"])
    union = sorted(set(fail_old) | set(fail_fin))

    # ---- Step 2: audit EVERY anchor, not only the failures ------------------
    audit = []
    for i in sorted(data):
        rec = data[i]
        ev = evidence_for(rec)
        category, notes, is_valid = audit_one(i, rec, strict)
        o = old1.get(i) or old2.get(i)
        audit.append({
            "instance_id": i,
            "ticker": rec["ticker"],
            "gold_answer": rec["mcqa_answer"],
            "in_failure_union": i in union,
            "valid": is_valid,
            "audit_category": category,
            "audit_notes": notes,
            "manual_verdict_before_strict_rule": VERDICTS[i][0] if i in VERDICTS else None,
            "objective_evidence": ev,
            "failed_old": i in fail_old,
            "failed_final50": i in fail_fin,
            "confidence_old": o["confidence"] if o else None,
            "confidence_final50": fin[i]["confidence"] if i in fin else None,
            "prediction_old_run1": old1[i]["prediction"] if i in old1 else None,
            "prediction_old_run2": old2[i]["prediction"] if i in old2 else None,
            "prediction_final50": fin[i]["prediction"] if i in fin else None,
            "rationale_final50": fin[i]["rationale"] if i in fin else None,
        })

    by_id = {a["instance_id"]: a for a in audit}
    invalid = [a["instance_id"] for a in audit if not a["valid"]]
    valid_failures = [i for i in union if by_id[i]["valid"]]

    def option_flags(rec):
        opts = options_of(rec["mcqa_question"])
        return sorted(k for k, v in opts.items() if POST_PUB.search(v))

    with open("challenge_audit.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({
            "rule": "strict" if strict else "lenient",
            "strict_rule_definition":
                "an anchor is INVALID when its GOLD answer asserts price behaviour "
                "after the article publication time; applied to all 50 anchors",
            "verified_failures": {"old_runs": fail_old, "final50_run": fail_fin,
                                  "union": union},
            "protocol_fact": {
                "instances_with_post_publication_price_points":
                    sum(1 for r in data.values()
                        if any(t > gp_epoch(r["gt_published_utc"])
                               for t in r["ts_timestamps"])),
                "n_instances": len(data),
                "note": "the GT article is published at or after the last price point "
                        "in every instance, so any claim about post-publication price "
                        "behaviour is unverifiable from the prompt",
            },
            "counts": {
                "n_audited": len(audit),
                "n_invalid": len(invalid),
                "n_valid": len(audit) - len(invalid),
                "gold_asserts_post_publication":
                    sorted(i for i in data
                           if by_id[i]["objective_evidence"]["gold_asserts_post_publication"]),
                "anchors_with_a_non_gold_post_publication_option":
                    sorted(i for i, r in data.items()
                           if set(option_flags(r)) - {r["mcqa_answer"]}),
            },
            "valid_model_failures": valid_failures,
            "invalid_instances": invalid,
            "audits": audit,
        }, f, indent=2, ensure_ascii=False)

    # ---- Step 3: challenge 10 ----------------------------------------------
    def filler_eligible(i):
        return (i not in union and i in fin and fin[i]["correct"]
                and by_id[i]["valid"] and bool(fin[i]["evidence_articles"]))

    ranked = sorted((i for i in data if filler_eligible(i)),
                    key=lambda i: (fin[i]["confidence"],
                                   0 if uses_ts_and_news(fin[i]["rationale"]) else 1, i))
    n_fill = 10 - len(valid_failures)
    fillers = ranked[:n_fill]
    challenge = sorted(valid_failures + fillers)
    if len(challenge) != 10:
        print("WARNING: only %d challenge anchors available (%d valid failures, "
              "%d eligible fillers)" % (len(challenge), len(valid_failures), len(ranked)))

    def reason(i):
        if i in fillers:
            return "hard_correct"
        in_old, in_fin = i in fail_old, i in fail_fin
        return ("failed_both" if in_old and in_fin else
                "failed_old_only" if in_old else "failed_final50_only")

    with open("challenge10_manifest.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({
            "rule": "strict" if strict else "lenient",
            "challenge_ids": challenge,
            "from_valid_model_failures": valid_failures,
            "hard_correct_fillers": fillers,
            "n_eligible_fillers": len(ranked),
            "filler_rule": "correct in the final50 C0 run, passes the same validity "
                           "audit (structure, entity match, gold not dependent on "
                           "post-publication prices), evidence_articles non-empty; "
                           "ranked by final50 confidence ascending, then rationale "
                           "using both time series and news, then instance_id",
            "anchors": [{
                "instance_id": i,
                "ticker": data[i]["ticker"],
                "gold_answer": data[i]["mcqa_answer"],
                "challenge_reason": reason(i),
                "final50_confidence": fin[i]["confidence"] if i in fin else None,
                "final50_prediction": fin[i]["prediction"] if i in fin else None,
                "validity": by_id[i]["audit_category"],
                "uses_ts_and_news": uses_ts_and_news(fin[i]["rationale"]) if i in fin else None,
                "notes": by_id[i]["audit_notes"],
            } for i in challenge],
        }, f, indent=2, ensure_ascii=False)

    # ---- Step 4: surgical replacement of invalid anchors --------------------
    pool = {}
    for path in POOL:
        for rec in load_json(path):
            pool[rec["instance_id"]] = (path, rec)

    def candidate_ok(rec):
        ev = evidence_for(rec)
        return (all(ev["structural_checks"].values())
                and ev["ticker_mentioned_in_article"]
                and not (strict and ev["gold_asserts_post_publication"]))

    rng = random.Random(args.seed)
    kept = [i for i in sorted(data) if i not in invalid]
    used = set(data)
    replacements = []
    for bad in invalid:
        src_path = ("c0_data.json" if prev[bad]["selected_source"] == "old"
                    else "hard50_data.json")
        same = sorted(i for i, (p, rec) in pool.items()
                      if p == src_path and i not in used and candidate_ok(rec))
        other = sorted(i for i, (p, rec) in pool.items()
                       if p != src_path and i not in used and candidate_ok(rec))
        if same:
            pick, fallback = rng.choice(same), False
        elif other:
            pick, fallback = rng.choice(other), True
        else:
            pick, fallback = None, False
        if pick is not None:
            used.add(pick)
        replacements.append({
            "replaced_instance_id": bad,
            "replacement_instance_id": pick,
            "replaced_category": by_id[bad]["audit_category"],
            "source_of_replaced": prev[bad]["selected_source"],
            "source_of_replacement": None if pick is None else
                ("old" if pool[pick][0] == "c0_data.json" else "new"),
            "cross_source_fallback": fallback,
            "reason": ("no eligible unused candidate remained" if pick is None else
                       "replaced anchor audited %s; replacement drawn deterministically "
                       "(seed %d) from unused candidates passing the same audit%s; "
                       "model results were not consulted"
                       % (by_id[bad]["audit_category"], args.seed,
                          " - same source dataset exhausted, drawn from the other "
                          "dataset" if fallback else " in the same source dataset")),
        })

    frozen_ids = kept + [r["replacement_instance_id"] for r in replacements
                         if r["replacement_instance_id"]]
    assert len(frozen_ids) == len(set(frozen_ids))

    def record(i):
        return data[i] if i in data else pool[i][1]

    def source_of(i):
        if i in prev:
            return prev[i]["selected_source"]
        return "old" if pool[i][0] == "c0_data.json" else "new"

    with open("final50_frozen_data.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump([record(i) for i in frozen_ids], f, indent=2, ensure_ascii=False)

    frozen_manifest = {
        "selection_policy":
            "Current final50 retained as mother set. Challenge labels are based on "
            "the union of prior valid model failures plus low-confidence valid "
            "correct cases. No optimization to a target accuracy was performed.",
        "validity_rule": "strict" if strict else "lenient",
        "validity_rule_definition":
            "an anchor is INVALID when its gold answer asserts price behaviour after "
            "the article publication time (no instance has post-publication price "
            "data), or when it fails structure/entity checks, or when it was manually "
            "audited as ambiguous",
        "seed": args.seed,
        "n_anchors": len(frozen_ids),
        "final50_ids": sorted(frozen_ids),
        "challenge10_ids": challenge,
        "n_replaced": sum(1 for r in replacements if r["replacement_instance_id"]),
        "surgical_replacements": replacements,
        "source_composition": {
            "old": sum(1 for i in frozen_ids if source_of(i) == "old"),
            "new": sum(1 for i in frozen_ids if source_of(i) == "new"),
        },
        "unevaluated_anchors": sorted(i for i in frozen_ids if i not in fin),
        "instances": [{
            "instance_id": i,
            "ticker": record(i)["ticker"],
            "gold_answer": record(i)["mcqa_answer"],
            "selected_source": source_of(i),
            "challenge_anchor": i in challenge,
            "challenge_reason": reason(i) if i in challenge else "normal",
            "final50_prediction": fin[i]["prediction"] if i in fin else None,
            "final50_correct": fin[i]["correct"] if i in fin else None,
            "final50_confidence": fin[i]["confidence"] if i in fin else None,
            "entered_by_replacement": i not in data,
        } for i in sorted(frozen_ids)],
    }
    with open("final50_frozen_manifest.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(frozen_manifest, f, indent=2, ensure_ascii=False)

    print("rule              : %s" % ("strict post-publication" if strict else "lenient"))
    print("old-run failures  : %s" % fail_old)
    print("final50 failures  : %s" % fail_fin)
    print("union             : %s" % union)
    print("invalid anchors   : %d/50 -> %s" % (len(invalid), invalid))
    print("valid failures    : %s" % valid_failures)
    print("fillers needed    : %d (eligible %d) -> %s" % (n_fill, len(ranked), fillers))
    print("challenge 10      : %s" % challenge)
    print("replacements      : %d (%d cross-source, %d unfilled)"
          % (sum(1 for r in replacements if r["replacement_instance_id"]),
             sum(1 for r in replacements if r["cross_source_fallback"]),
             sum(1 for r in replacements if not r["replacement_instance_id"])))
    print("frozen size       : %d | composition old=%d new=%d"
          % (len(frozen_ids), frozen_manifest["source_composition"]["old"],
             frozen_manifest["source_composition"]["new"]))
    print("anchors with no C0 result yet: %d" % len(frozen_manifest["unevaluated_anchors"]))
    print("wrote challenge_audit.json, challenge10_manifest.json, "
          "final50_frozen_data.json, final50_frozen_manifest.json")


if __name__ == "__main__":
    main()
