"""Protocol-independent validity audit of the mother set, then lock the 50.

Source of truth is the paper protocol: the benchmark uses the MTBench 7-day
input_window only.  The absence of price observations after the article's
publication time is therefore NOT a validity defect, and the strict
post-publication rule used in the previous session is superseded.

Only defects that remain defects under an input-window-only protocol count:
  A structural failure
  B entity mismatch
  C internal numerical contradiction (gold contradicted by the prompt)
  D ambiguous multiple-answer item
  E other objective malformation

Model predictions are never consulted.

Inputs  : final_hard50_data.json (mother set), c0_data.json + hard50_data.json (pool)
Outputs : final50_protocol_audit.json, final50_locked_data.json,
          final50_locked_manifest.json

Usage:  python audit_protocol.py [--seed 20260821]
"""

import argparse
import json
import random
import re

import pandas as pd

from audit_challenge import evidence_for, options_of
from build_final_hard50 import load_json, validate
from entity_alias import build_alias_map, entity_check
from news_corpus import parse_article

CORPUS = "data/MTBench_finance_news.parquet"
_ALIAS = None


def alias_map():
    """Corpus-derived ticker -> company aliases (loaded once)."""
    global _ALIAS
    if _ALIAS is None:
        _ALIAS = build_alias_map(pd.read_parquet(CORPUS, columns=["title"])["title"])
    return _ALIAS

MOTHER = "final_hard50_data.json"
MOTHER_MANIFEST = "final_hard50_manifest.json"
POOL = ["c0_data.json", "hard50_data.json"]

PRICE = re.compile(r"\$\s?(\d{1,5}(?:,\d{3})*(?:\.\d+)?)")


def impossible_prices(rec):
    """Options citing a dollar figure that is neither in the window nor the article.

    Such a figure cannot be true under the prompt's own information.  Returns
    {option_letter: [figures]}.
    """
    lo, hi = min(rec["ts_values"]), max(rec["ts_values"])
    title, text = parse_article(rec["gt_article_text"])
    article = title + " " + text
    out = {}
    for letter, option in options_of(rec["mcqa_question"]).items():
        for m in PRICE.finditer(option):
            raw = m.group(1)
            val = float(raw.replace(",", ""))
            in_window = lo * 0.995 <= val <= hi * 1.005
            in_article = raw in article
            if not in_window and not in_article:
                out.setdefault(letter, []).append(raw)
    return out


def audit(rec):
    """-> (valid, category, evidence, notes) under the input-window-only protocol."""
    ev = evidence_for(rec)
    title, text = parse_article(rec["gt_article_text"])
    entity = entity_check(rec["ticker"], title, text, alias_map())
    checks = ev["structural_checks"]
    gold = rec["mcqa_answer"]
    polarity = ev["question_polarity"]
    bad_prices = impossible_prices(rec)
    evidence = {
        "structural_checks": checks,
        "entity": entity,
        "question_polarity": polarity,
        "gold_option": gold,
        "options_with_impossible_price": bad_prices,
        "ts_window_min": ev["price_min"], "ts_window_max": ev["price_max"],
        "n_points": ev["n_points"],
        "ts_first_utc": ev["ts_first_utc"], "ts_last_utc": ev["ts_last_utc"],
        "gt_published_utc": ev["gt_published_utc"],
        # recorded for transparency only - NOT a validity criterion any more
        "gold_mentions_post_publication": ev["gold_asserts_post_publication"],
        "n_points_after_publication": ev["n_points_after_publication"],
    }

    if not all(checks.values()):
        return (False, "INVALID_STRUCTURAL", evidence,
                "structural checks failed: %s"
                % [k for k, v in checks.items() if not v])

    if entity["mismatch"]:
        return (False, "INVALID_ENTITY_MISMATCH", evidence,
                "the anchor company is never mentioned in the article while another "
                "company (%s) is named in its title"
                % ", ".join(o["name"] for o in entity["other_companies_in_title"]))

    if gold in bad_prices:
        return (False, "INVALID_NUMERICAL_CONTRADICTION", evidence,
                "the gold option cites %s, which lies outside the observed price "
                "window and appears nowhere in the article"
                % ", ".join("$" + p for p in bad_prices[gold]))

    competing = sorted(set(bad_prices) - {gold})
    if polarity == "incorrect" and competing:
        return (False, "INVALID_AMBIGUOUS_OPTIONS", evidence,
                "in a 'which is incorrect' item, option(s) %s are demonstrably "
                "false under the prompt's own information (citing %s, outside the "
                "observed window and absent from the article), so they are as "
                "defensible an answer as the gold option %s"
                % (", ".join(competing),
                   ", ".join("$" + p for c in competing for p in bad_prices[c]), gold))

    note = "no protocol-independent defect"
    if entity["weak_link"]:
        note += ("; WEAK ENTITY LINK for manual review: the company is mentioned "
                 "only %d time(s) in the body and not in the title - not treated as "
                 "a defect" % entity["entity_body_mentions"])
    if polarity == "correct" and competing:
        note += ("; option(s) %s cite an impossible figure, which is expected of "
                 "distractor options in a 'which is correct' item" % ", ".join(competing))
    if ev["gold_asserts_post_publication"]:
        note += ("; the gold answer mentions post-publication behaviour, which is "
                 "NOT a defect under the input-window-only protocol")
    return (True, "VALID", evidence, note)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260821)
    args = ap.parse_args()

    mother = {r["instance_id"]: r for r in load_json(MOTHER)}
    prev = {m["instance_id"]: m for m in json.load(
        open(MOTHER_MANIFEST, encoding="utf-8"))["instances"]}

    audits = []
    for i in sorted(mother):
        valid, category, evidence, notes = audit(mother[i])
        audits.append({
            "instance_id": i,
            "ticker": mother[i]["ticker"],
            "gold_answer": mother[i]["mcqa_answer"],
            "valid": valid,
            "audit_category": category,
            "evidence": evidence,
            "notes": notes,
        })
    invalid = [a["instance_id"] for a in audits if not a["valid"]]

    with open("final50_protocol_audit.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({
            "protocol": "MTBench 7-day input_window only; output_window is "
                        "deliberately not used and its absence is not a defect",
            "superseded_rule": "the previous strict rule (gold mentions "
                               "post-publication behaviour => invalid) is NOT applied",
            "criteria": ["A structural failure", "B entity mismatch",
                         "C internal numerical contradiction",
                         "D ambiguous multiple-answer item",
                         "E other objective malformation"],
            "model_predictions_used": False,
            "n_audited": len(audits), "n_invalid": len(invalid),
            "invalid_instance_ids": invalid,
            "audits": audits,
        }, f, indent=2, ensure_ascii=False)

    # ---- surgical replacement, only for anchors that failed the audit -------
    pool = {}
    for path in POOL:
        for rec in load_json(path):
            pool[rec["instance_id"]] = (path, rec)

    def candidate_ok(rec):
        return audit(rec)[0] and all(validate(rec).values())

    rng = random.Random(args.seed)
    used = set(mother)
    replacements = []
    for bad in invalid:
        src = "c0_data.json" if prev[bad]["selected_source"] == "old" else "hard50_data.json"
        same = sorted(i for i, (p, rec) in pool.items()
                      if p == src and i not in used and candidate_ok(rec))
        other = sorted(i for i, (p, rec) in pool.items()
                       if p != src and i not in used and candidate_ok(rec))
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
            "replaced_category": next(a["audit_category"] for a in audits
                                      if a["instance_id"] == bad),
            "replaced_notes": next(a["notes"] for a in audits if a["instance_id"] == bad),
            "source_of_replaced": prev[bad]["selected_source"],
            "source_of_replacement": None if pick is None else
                ("old" if pool[pick][0] == "c0_data.json" else "new"),
            "cross_source_fallback": fallback,
            "selection": "deterministic draw (seed %d) from unused candidates that "
                         "pass the same protocol-independent audit; model predictions "
                         "were not consulted and difficulty was not optimised" % args.seed,
        })

    locked_ids = [i for i in sorted(mother) if i not in invalid] + \
                 [r["replacement_instance_id"] for r in replacements
                  if r["replacement_instance_id"]]
    assert len(locked_ids) == len(set(locked_ids))

    def record(i):
        return mother[i] if i in mother else pool[i][1]

    def source_of(i):
        if i in prev:
            return prev[i]["selected_source"]
        return "old" if pool[i][0] == "c0_data.json" else "new"

    with open("final50_locked_data.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump([record(i) for i in sorted(locked_ids)], f, indent=2, ensure_ascii=False)

    manifest = {
        "policy": "Anchor membership was inherited from final_hard50_data.json. "
                  "Only protocol-independent malformed/ambiguous instances, if any, "
                  "were surgically replaced. No anchor selection used model accuracy "
                  "after this point.",
        "protocol": "MTBench 7-day input_window only; output_window is not appended",
        "seed": args.seed,
        "n_anchors": len(locked_ids),
        "mother_set": MOTHER,
        "mother_set_ids": sorted(mother),
        "invalid_ids": invalid,
        "replacements": replacements,
        "locked_ids": sorted(locked_ids),
        "source_composition": {
            "old": sum(1 for i in locked_ids if source_of(i) == "old"),
            "new": sum(1 for i in locked_ids if source_of(i) == "new"),
        },
        "instances": [{
            "instance_id": i,
            "ticker": record(i)["ticker"],
            "gold_answer": record(i)["mcqa_answer"],
            "selected_source": source_of(i),
            "entered_by_replacement": i not in mother,
        } for i in sorted(locked_ids)],
    }
    with open("final50_locked_manifest.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("audited %d anchors under the input-window-only protocol" % len(audits))
    print("invalid: %s" % (invalid or "none"))
    for a in audits:
        if not a["valid"]:
            print("   %d %s: %s" % (a["instance_id"], a["audit_category"], a["notes"]))
    for r in replacements:
        print("replacement: %s -> %s (%s%s)" % (
            r["replaced_instance_id"], r["replacement_instance_id"],
            r["source_of_replaced"], " CROSS-SOURCE" if r["cross_source_fallback"] else ""))
    print("locked %d anchors | composition old=%d new=%d"
          % (len(locked_ids), manifest["source_composition"]["old"],
             manifest["source_composition"]["new"]))
    print("wrote final50_protocol_audit.json, final50_locked_data.json, "
          "final50_locked_manifest.json")


if __name__ == "__main__":
    main()
