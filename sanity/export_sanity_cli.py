"""Export a frozen sanity condition as one prompt file per instance.

Same contract as export_condition_cli.py: the rendered JSONL is the only source
of truth, the prompt is copied verbatim, and every written file is reread and
compared byte for byte.

Usage:  python sanity/export_sanity_cli.py --input sanity/s1_qo_only.jsonl \
                                           --condition S1_QO_ONLY \
                                           --out-dir sanity/cli/s1_qo_only
        ... --check     verify an existing export, write nothing
"""

import argparse
import json
import os
import sys


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def check(records, out_dir):
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
    ap.add_argument("--input", required=True)
    ap.add_argument("--condition", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--check", action="store_true")
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
    with open(os.path.join(args.out_dir, "index.jsonl"), "w", encoding="utf-8",
              newline="\n") as index:
        for rec in records:
            name = "%d.txt" % rec["instance_id"]
            with open(os.path.join(args.out_dir, name), "w", encoding="utf-8",
                      newline="") as f:
                f.write(rec["prompt"])
            index.write(json.dumps({
                "instance_id": rec["instance_id"],
                "condition": rec["condition"],
                "prompt_file": name,
                "gold_answer": rec["answer"],
                "ticker": rec["ticker"],
            }, ensure_ascii=False) + "\n")
    print("exported %d %s prompts to %s/" % (len(records), args.condition,
                                             args.out_dir))
    if not check(records, args.out_dir):
        sys.exit(1)


if __name__ == "__main__":
    main()
