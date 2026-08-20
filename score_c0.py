"""Score the collected C0 pilot results against the gold MCQA answers.

Reads   results/c0_sonnet5.jsonl        (from collect_c0_results.py)
        out/c0_cli/index.jsonl          (to know which instances are missing)
        results/c0_collect_report.json  (optional, for the malformed count)
Writes  results/c0_summary.json

Usage:  python score_c0.py [--results results/c0_sonnet5.jsonl]
"""

import argparse
import json
import os

CHOICES = ("A", "B", "C", "D")


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def fmt(x):
    return "n/a" if x is None else "%.3f" % x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join("results", "c0_sonnet5.jsonl"))
    ap.add_argument("--index", default=os.path.join("out", "c0_cli", "index.jsonl"))
    ap.add_argument("--report", default=os.path.join("results", "c0_collect_report.json"))
    ap.add_argument("--summary", default=os.path.join("results", "c0_summary.json"))
    args = ap.parse_args()

    with open(args.results, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    with open(args.index, encoding="utf-8") as f:
        all_ids = [json.loads(line)["instance_id"] for line in f if line.strip()]

    malformed_ids = []
    if os.path.exists(args.report):
        with open(args.report, encoding="utf-8") as f:
            malformed_ids = [m["instance_id"] for m in json.load(f).get("malformed", [])]

    done = {r["instance_id"] for r in rows}
    # missing and malformed are reported as disjoint sets
    missing = [i for i in all_ids if i not in done and i not in set(malformed_ids)]
    correct = [r for r in rows if r["correct"]]
    incorrect = [r for r in rows if not r["correct"]]

    dist = {c: sum(1 for r in rows if r["prediction"] == c) for c in CHOICES}
    models = sorted({r["model"] for r in rows})

    summary = {
        "model": models[0] if len(models) == 1 else models,
        "n_total": len(all_ids),
        "n_completed": len(rows),
        "n_correct": len(correct),
        "accuracy": (len(correct) / len(rows)) if rows else None,
        "n_missing": len(missing),
        "missing_instance_ids": missing,
        "n_malformed": len(malformed_ids),
        "malformed_instance_ids": malformed_ids,
        "answer_distribution": dist,
        "mean_confidence": mean([r["confidence"] for r in rows]),
        "mean_confidence_correct": mean([r["confidence"] for r in correct]),
        "mean_confidence_incorrect": mean([r["confidence"] for r in incorrect]),
    }

    os.makedirs(os.path.dirname(args.summary) or ".", exist_ok=True)
    with open(args.summary, "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("model:        %s" % summary["model"])
    print("completed:    %d / %d" % (summary["n_completed"], summary["n_total"]))
    print("correct:      %d" % summary["n_correct"])
    print("accuracy:     %s" % fmt(summary["accuracy"]))
    print("missing:      %d%s" % (len(missing),
                                  (" -> " + ", ".join(str(i) for i in missing))
                                  if missing else ""))
    if malformed_ids:
        print("malformed:    %d -> %s"
              % (len(malformed_ids), ", ".join(str(i) for i in malformed_ids)))
    print("predictions:  " + "  ".join("%s=%d" % (c, dist[c]) for c in CHOICES))
    print("confidence:   mean %s (correct %s / incorrect %s)"
          % (fmt(summary["mean_confidence"]),
             fmt(summary["mean_confidence_correct"]),
             fmt(summary["mean_confidence_incorrect"])))
    print("summary: %s" % args.summary)


if __name__ == "__main__":
    main()
