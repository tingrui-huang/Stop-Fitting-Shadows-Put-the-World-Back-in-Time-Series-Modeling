"""Export an already-rendered condition (C1/C2/C3) as one prompt file per instance.

The rendered JSONL is the single source of truth: this script copies the
"prompt" field verbatim and adds nothing.  It never renders, re-masks,
reshuffles or rebuilds anything, so an export can be regenerated at any time
without touching the frozen benchmark.

export_c0_cli.py is deliberately left untouched for reproducibility of the C0
run; this is its generic sibling.

    python export_condition_cli.py --input out_paper50_reviewed/c1.jsonl \
                                   --condition C1 \
                                   --out-dir out_paper50_reviewed/c1_cli
    python export_condition_cli.py --input ... --condition C1 --out-dir ... --check

--check rereads every exported file and requires byte-for-byte equality with
the prompt field it came from.

Usage:  python export_condition_cli.py --input PATH --condition C1|C2|C3
                                       --out-dir DIR [--check]
"""

import argparse
import json
import os
import sys

CONDITIONS = ("C1", "C2", "C3")


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def check(records, out_dir):
    """Reread every exported prompt and compare with the source JSONL."""
    bad = []
    for rec in records:
        path = os.path.join(out_dir, "%d.txt" % rec["instance_id"])
        if not os.path.exists(path):
            bad.append((rec["instance_id"], "missing export"))
            continue
        with open(path, encoding="utf-8", newline="") as f:
            if f.read() != rec["prompt"]:
                bad.append((rec["instance_id"], "differs from the source prompt"))
    for iid, why in bad:
        print("MISMATCH %d: %s" % (iid, why))
    print("%d/%d exported prompts byte-identical to the source JSONL"
          % (len(records) - len(bad), len(records)))
    return not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="rendered condition JSONL")
    ap.add_argument("--condition", required=True, choices=CONDITIONS)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--check", action="store_true",
                    help="only verify an existing export, write nothing")
    args = ap.parse_args()

    records = load(args.input)

    wrong = sorted({r.get("condition") for r in records} - {args.condition})
    if wrong:
        raise SystemExit("condition mismatch: %s contains %s but --condition is %s"
                         % (args.input, wrong, args.condition))
    ids = [r["instance_id"] for r in records]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate instance ids in %s" % args.input)

    if args.check:
        sys.exit(0 if check(records, args.out_dir) else 1)

    os.makedirs(args.out_dir, exist_ok=True)
    index_path = os.path.join(args.out_dir, "index.jsonl")
    with open(index_path, "w", encoding="utf-8", newline="\n") as index:
        for rec in records:
            name = "%d.txt" % rec["instance_id"]
            with open(os.path.join(args.out_dir, name), "w",
                      encoding="utf-8", newline="") as f:
                f.write(rec["prompt"])
            index.write(json.dumps({
                "instance_id": rec["instance_id"],
                "condition": rec["condition"],
                "prompt_file": name,
                "gold_answer": rec["answer"],
                "ticker": rec["ticker"],
            }, ensure_ascii=False) + "\n")

    print("exported %d %s prompts from %s to %s/"
          % (len(records), args.condition, args.input, args.out_dir))
    print("index: %s" % index_path)
    if not check(records, args.out_dir):
        sys.exit(1)


if __name__ == "__main__":
    main()
