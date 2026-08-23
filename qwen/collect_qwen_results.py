"""Collect the structured Qwen result files into a scored-ready JSONL.

A separate collector, not a change to collect_c0_results.py: the Sonnet path
reads raw .txt stdout, the Qwen path reads structured .json, and the safe way to
support both is to leave the working one alone.  The parsing policy is still
shared - extract_json and validate are imported from collect_c0_results, so an
answer accepted here is accepted by exactly the same rules that produced the
Sonnet records.

Reads   out_paper50_reviewed/<cond>_cli/index.jsonl      (instances + gold answers)
        results/<run-tag>/<cond>_raw/<id>.json           (one per completed call)
Writes  results/<run-tag>/<cond>_<run-tag>.jsonl         (parsed + scored records)
        results/<run-tag>/<cond>_collect_report.json     (missing / malformed)

--run-tag defaults to qwen36, so the default paths and file names are exactly
the ones the Qwen3.6 run already uses.  The scoring "model" label is derived
from the model id recorded in the raw files, which is the model that was
actually requested - it is never assumed from the run tag.

The output records carry every field score_c0.py needs, plus `reasoning` - the
model's thinking trace, kept distinct from `rationale`, the short explanation
inside the final JSON answer.

Usage:  python qwen/collect_qwen_results.py --condition C0
        python qwen/collect_qwen_results.py --condition C1 C2 C3
        python qwen/collect_qwen_results.py --condition C0 --model Qwen/Qwen3.5-9B --run-tag qwen35_9b
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from collect_c0_results import extract_json, validate  # noqa: E402
from qwen_common import (add_target_args, model_label as label_of,  # noqa: E402
                         out_root, raw_dir)


def collect(cond, run_tag, model_label, expect_model):
    index_path = os.path.join(ROOT, "out_paper50_reviewed",
                              "%s_cli" % cond.lower(), "index.jsonl")
    with open(index_path, encoding="utf-8") as f:
        index = [json.loads(l) for l in f if l.strip()]
    rawd = raw_dir(run_tag, cond)
    out_path = os.path.join(out_root(run_tag), "%s_%s.jsonl"
                            % (cond.lower(), run_tag))
    rep_path = os.path.join(out_root(run_tag),
                            "%s_collect_report.json" % cond.lower())

    missing, malformed, truncated, rows = [], [], [], []
    model_ids, model_mismatch = set(), []
    for entry in index:
        iid = entry["instance_id"]
        p = os.path.join(rawd, "%d.json" % iid)
        if not os.path.exists(p):
            missing.append(iid)
            continue
        with open(p, encoding="utf-8") as f:
            rec = json.load(f)
        model_ids.add(rec.get("model"))
        if expect_model and rec.get("model") != expect_model:
            model_mismatch.append({"instance_id": iid,
                                   "recorded_model": rec.get("model"),
                                   "expected_model": expect_model})
        if rec.get("truncated"):
            truncated.append(iid)
        fields, err = validate(extract_json(rec.get("content") or ""))
        if err:
            # the thinking trace is kept even though the final JSON is unusable
            malformed.append({"instance_id": iid, "reason": err,
                              "finish_reason": rec.get("finish_reason"),
                              "truncated": rec.get("truncated"),
                              "reasoning_chars": len(rec.get("reasoning") or ""),
                              "content_preview": (rec.get("content") or "")[:400],
                              "raw_file": os.path.relpath(p, ROOT)})
            continue
        gold = entry["gold_answer"]
        rows.append({
            "instance_id": iid,
            "condition": rec.get("condition", cond),
            "model": None,          # filled in below, once the label is known
            "model_id": rec.get("model"),
            "prediction": fields["prediction"],
            "confidence": fields["confidence"],
            "rationale": fields["rationale"],
            "evidence_articles": fields["evidence_articles"],
            "reasoning": rec.get("reasoning"),
            "reasoning_source": rec.get("reasoning_source"),
            "reasoning_chars": len(rec.get("reasoning") or ""),
            "gold_answer": gold,
            "correct": fields["prediction"] == gold,
            "finish_reason": rec.get("finish_reason"),
            "truncated": rec.get("truncated"),
            "usage": rec.get("usage"),
            "prompt_sha256": rec.get("prompt_sha256"),
            "system_prompt_sha256": rec.get("system_prompt_sha256"),
            "generation": rec.get("generation"),
            "raw_output": rec.get("content"),
            "raw_file": os.path.relpath(p, ROOT),
        })

    # the scoring label follows the model that was actually requested
    if model_label is None:
        concrete = sorted(m for m in model_ids if m)
        model_label = (label_of(concrete[0]) if len(concrete) == 1
                       else (label_of(expect_model) if expect_model else run_tag))
    for r in rows:
        r["model"] = model_label
    rows.sort(key=lambda r: r["instance_id"])
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    report = {
        "model": model_label, "run_tag": run_tag,
        "model_ids_seen": sorted(m for m in model_ids if m),
        "n_model_mismatch": len(model_mismatch),
        "model_mismatch": model_mismatch,
        "condition": cond,
        "index": os.path.relpath(index_path, ROOT),
        "raw_dir": os.path.relpath(rawd, ROOT),
        "n_total": len(index), "n_parsed": len(rows),
        "n_missing": len(missing), "missing_instance_ids": missing,
        "n_malformed": len(malformed), "malformed": malformed,
        "n_truncated": len(truncated), "truncated_instance_ids": truncated,
        "n_with_reasoning": sum(1 for r in rows if r["reasoning_chars"] > 0),
        "reasoning_sources": sorted({r["reasoning_source"] for r in rows}),
    }
    with open(rep_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("%s [%s -> %s]: parsed %d/%d  missing %d  malformed %d  "
          "truncated %d  with reasoning %d"
          % (cond, model_label, run_tag, len(rows), len(index), len(missing),
             len(malformed), len(truncated), report["n_with_reasoning"]))
    if model_mismatch:
        print("   WARNING: %d raw file(s) record a different model than "
              "--model %s" % (len(model_mismatch), expect_model))
    print("   %s" % os.path.relpath(out_path, ROOT))
    print("   %s" % os.path.relpath(rep_path, ROOT))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", nargs="+", required=True,
                    choices=("C0", "C1", "C2", "C3"))
    add_target_args(ap, reads_only=True)
    ap.add_argument("--model-label", default=None,
                    help="scoring label; derived from the model id recorded in "
                         "the raw files when omitted")
    args = ap.parse_args()
    for c in args.condition:
        collect(c, args.run_tag, args.model_label, args.model)


if __name__ == "__main__":
    main()
