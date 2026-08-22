"""Build final_hard50_data.json: 50 unique anchors mixed from the two C0 datasets.

Sources (never modified):
  c0_data.json        -> selected_source "old"
  hard50_data.json    -> selected_source "new"

C0 result runs (both were run over c0_data.json instances):
  results/old_c0_mtbench50/c0_sonnet5.jsonl  -> old_* fields (44/50)
  results/c0_sonnet5.jsonl                   -> new_* fields (46/50)

10 challenge anchors = every unique instance that Sonnet got wrong in either run
(structurally valid ones only), topped up with deterministic "hard but correct"
fillers.  The other 40 are a deterministic, roughly balanced mix of the two
datasets.  Everything is recorded in final_hard50_manifest.json.

Usage:  python build_final_hard50.py [--seed 20260821]
"""

import argparse
import datetime as dt
import json
import random

OLD_DATA = "c0_data.json"
NEW_DATA = "hard50_data.json"
OLD_RUN = "results/old_c0_mtbench50/c0_sonnet5.jsonl"
NEW_RUN = "results/c0_sonnet5.jsonl"
OUT_DATA = "final_hard50_data.json"
OUT_MANIFEST = "final_hard50_manifest.json"

N_TOTAL = 50
N_CHALLENGE = 10
MIN_TS_POINTS = 30
MIN_ARTICLE_CHARS = 200


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #
def validate(rec):
    """Return dict of check -> bool.  All True means the record is usable."""
    ts, vs = rec.get("ts_timestamps"), rec.get("ts_values")
    q = rec.get("mcqa_question") or ""
    art = rec.get("gt_article_text") or ""

    checks = {}
    checks["instance_id_present"] = isinstance(rec.get("instance_id"), int)
    checks["ticker_present"] = bool(rec.get("ticker"))
    checks["ts_lengths_match"] = (isinstance(ts, list) and isinstance(vs, list)
                                  and len(ts) == len(vs))
    checks["ts_non_empty"] = bool(ts) and len(ts or []) >= MIN_TS_POINTS
    # Non-decreasing, not strictly increasing: four source records carry repeated
    # minute stamps (thin trading).  That is a data quirk, not a broken instance,
    # so it is reported as info (see duplicate_timestamps) rather than gating.
    checks["ts_ordered"] = bool(ts) and all(a <= b for a, b in zip(ts, ts[1:]))
    checks["ts_values_numeric"] = bool(vs) and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) for v in (vs or []))
    checks["gt_article_present"] = art.startswith("Title: ") and " \n Content: " in art
    checks["gt_article_substantial"] = len(art) >= MIN_ARTICLE_CHARS

    published = rec.get("gt_published_utc")
    try:
        dt.datetime.strptime(published, "%Y-%m-%d %H:%M:%S")
        checks["gt_published_parses"] = True
    except (TypeError, ValueError):
        checks["gt_published_parses"] = False

    checks["question_present"] = len(q.strip()) > 0
    checks["answer_valid"] = rec.get("mcqa_answer") in ("A", "B", "C", "D")

    options = {}
    for letter in "ABCD":
        for line in q.splitlines():
            if line.strip().startswith(letter + "."):
                options[letter] = line.strip()[2:].strip()
                break
    checks["four_options_present"] = len(options) == 4
    checks["options_distinct"] = len(set(options.values())) == len(options)
    checks["ticker_in_question"] = rec.get("ticker", "@") in q
    return checks


def valid(rec):
    return all(validate(rec).values())


# --------------------------------------------------------------------------- #
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260821)
    args = ap.parse_args()

    old = {r["instance_id"]: r for r in load_json(OLD_DATA)}
    new = {r["instance_id"]: r for r in load_json(NEW_DATA)}
    assert not (set(old) & set(new)), "datasets share instance ids"

    old_run = {r["instance_id"]: r for r in load_jsonl(OLD_RUN)}
    new_run = {r["instance_id"]: r for r in load_jsonl(NEW_RUN)}

    checks = {i: validate(r) for i, r in list(old.items()) + list(new.items())}
    invalid = {i for i, c in checks.items() if not all(c.values())}

    # ---- Step 1/2: challenge anchors ---------------------------------------
    fail_old = sorted(i for i, r in old_run.items() if not r["correct"])
    fail_new = sorted(i for i, r in new_run.items() if not r["correct"])
    union = sorted(set(fail_old) | set(fail_new))
    union_valid = [i for i in union if i not in invalid]
    union_dropped = [i for i in union if i in invalid]

    # hard-but-correct fillers: correct in every run that covers them, actually
    # used an article, ranked by mean self-reported confidence ascending,
    # instance_id as tie-breaker.
    def runs_for(i):
        return [r for r in (old_run.get(i), new_run.get(i)) if r is not None]

    eligible = []
    for i in sorted(set(old_run) | set(new_run)):
        if i in union_valid or i in invalid:
            continue
        rs = runs_for(i)
        if not rs or not all(r["correct"] for r in rs):
            continue
        if not all(r["evidence_articles"] for r in rs):   # used the news context
            continue
        eligible.append((sum(r["confidence"] for r in rs) / len(rs), i))
    eligible.sort()

    n_fill = N_CHALLENGE - len(union_valid)
    fillers = [i for _, i in eligible[:n_fill]]
    challenge = union_valid + fillers
    assert len(challenge) == N_CHALLENGE, len(challenge)

    # ---- Step 4: remaining 40, deterministic and roughly balanced ----------
    rng = random.Random(args.seed)
    rest_old = sorted(i for i in old if i not in challenge and i not in invalid)
    rest_new = sorted(i for i in new if i not in challenge and i not in invalid)
    n_rest = N_TOTAL - N_CHALLENGE
    n_from_new = min(len(rest_new), n_rest // 2)
    n_from_old = n_rest - n_from_new
    assert n_from_old <= len(rest_old), "not enough valid old records"
    picked_old = sorted(rng.sample(rest_old, n_from_old))
    picked_new = sorted(rng.sample(rest_new, n_from_new))

    final_ids = challenge + picked_old + picked_new
    assert len(final_ids) == len(set(final_ids)) == N_TOTAL

    # ---- Step 5: write ------------------------------------------------------
    def source_of(i):
        return "old" if i in old else "new"

    def record_of(i):
        return old[i] if i in old else new[i]

    def reason(i):
        if i in fillers:
            return "hard_correct"
        if i in fail_old and i in fail_new:
            return "failed_both"
        if i in fail_old:
            return "failed_old"
        if i in fail_new:
            return "failed_new"
        return "normal"

    data = [record_of(i) for i in final_ids]
    with open(OUT_DATA, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    instances = []
    for i in final_ids:
        o, n = old_run.get(i), new_run.get(i)
        instances.append({
            "instance_id": i,
            "selected_source": source_of(i),
            "ticker": record_of(i)["ticker"],
            "gold_answer": record_of(i)["mcqa_answer"],
            "challenge_anchor": i in challenge,
            "challenge_reason": reason(i),
            "old_prediction": o["prediction"] if o else None,
            "old_correct": o["correct"] if o else None,
            "old_confidence": o["confidence"] if o else None,
            "new_prediction": n["prediction"] if n else None,
            "new_correct": n["correct"] if n else None,
            "new_confidence": n["confidence"] if n else None,
            "validation": checks[i],
            "duplicate_timestamps": sum(
                1 for a, b in zip(record_of(i)["ts_timestamps"],
                                  record_of(i)["ts_timestamps"][1:]) if a == b),
            "notes": ("no C0 result available (instance comes from %s)" % NEW_DATA)
                     if not (o or n) else "",
        })

    manifest = {
        "selection_seed": args.seed,
        "field_semantics": {
            "selected_source": "'old' = %s, 'new' = %s; the two datasets have "
                               "disjoint instance ids, so no instance exists in "
                               "two versions" % (OLD_DATA, NEW_DATA),
            "old_*": "first C0 run (%s), 44/50" % OLD_RUN,
            "new_*": "second C0 run (%s), 46/50" % NEW_RUN,
            "both runs": "were executed over %s instances only; %s has no C0 "
                         "results yet" % (OLD_DATA, NEW_DATA),
        },
        "failures": {
            "old_run_failed_ids": fail_old,
            "new_run_failed_ids": fail_new,
            "unique_union": union,
            "union_size": len(union),
            "union_dropped_as_invalid": union_dropped,
        },
        "hard_correct_fill_rule": (
            "correct in every run covering the instance, evidence_articles "
            "non-empty in every such run, ranked by mean self-reported "
            "confidence ascending, instance_id ascending as tie-breaker"),
        "hard_correct_fillers": [
            {"instance_id": i, "mean_confidence": c} for c, i in eligible[:n_fill]],
        "n_hard_correct_needed": n_fill,
        "composition": {
            "challenge_anchor_ids": challenge,
            "n_from_old": sum(1 for i in final_ids if source_of(i) == "old"),
            "n_from_new": sum(1 for i in final_ids if source_of(i) == "new"),
            "non_challenge_from_old": picked_old,
            "non_challenge_from_new": picked_new,
        },
        "validation_summary": {
            "n_candidates_checked": len(checks),
            "n_invalid_candidates": len(invalid),
            "invalid_candidate_ids": sorted(invalid),
        },
        "instances": instances,
    }
    with open(OUT_MANIFEST, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("old run failures (%d): %s" % (len(fail_old), fail_old))
    print("new run failures (%d): %s" % (len(fail_new), fail_new))
    print("unique union (%d): %s" % (len(union), union))
    print("dropped as structurally invalid: %s" % (union_dropped or "none"))
    print("hard-but-correct fillers needed: %d -> %s" % (n_fill, fillers))
    print("challenge anchors (%d): %s" % (len(challenge), sorted(challenge)))
    print("final 50: %d from old (%s), %d from new (%s)"
          % (manifest["composition"]["n_from_old"], OLD_DATA,
             manifest["composition"]["n_from_new"], NEW_DATA))
    print("invalid candidates across both datasets: %d" % len(invalid))
    print("wrote %s and %s" % (OUT_DATA, OUT_MANIFEST))


if __name__ == "__main__":
    main()
