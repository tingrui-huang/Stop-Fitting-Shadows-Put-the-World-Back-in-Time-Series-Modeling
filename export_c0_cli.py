"""Export the rendered C0 prompts as one plain-text file per instance.

Reads   out/c0.jsonl      (source of truth, produced by build_conditions.py)
Writes  out/c0_cli/<instance_id>.txt   the C0 prompt, byte for byte
        out/c0_cli/index.jsonl         instance_id / prompt_file / gold_answer

This script adds NOTHING to the prompt: the response-format instruction lives in
build_conditions.py and is already part of the rendered prompt.  Each exported
file must be byte-identical to the "prompt" field it came from; that is asserted
here and re-checked by --check.

Usage:  python export_c0_cli.py [--c0 out/c0.jsonl] [--out-dir out/c0_cli] [--check]
"""

import argparse
import json
import os


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def check(records, out_dir):
    """Re-read the exported files and compare them with out/c0.jsonl."""
    bad = []
    for rec in records:
        path = os.path.join(out_dir, "%d.txt" % rec["instance_id"])
        if not os.path.exists(path):
            bad.append((rec["instance_id"], "missing"))
            continue
        with open(path, encoding="utf-8", newline="") as f:
            if f.read() != rec["prompt"]:
                bad.append((rec["instance_id"], "differs from out/c0.jsonl"))
    for iid, why in bad:
        print("MISMATCH %d: %s" % (iid, why))
    print("%d/%d exported prompts byte-identical to out/c0.jsonl"
          % (len(records) - len(bad), len(records)))
    return not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--c0", default=os.path.join("out", "c0.jsonl"))
    ap.add_argument("--out-dir", default=os.path.join("out", "c0_cli"))
    ap.add_argument("--check", action="store_true",
                    help="only verify existing exports, do not rewrite them")
    args = ap.parse_args()

    records = load(args.c0)
    if args.check:
        raise SystemExit(0 if check(records, args.out_dir) else 1)

    os.makedirs(args.out_dir, exist_ok=True)
    index_path = os.path.join(args.out_dir, "index.jsonl")

    with open(index_path, "w", encoding="utf-8", newline="\n") as index:
        for rec in records:
            assert rec["condition"] == "C0", rec["condition"]
            name = "%d.txt" % rec["instance_id"]
            with open(os.path.join(args.out_dir, name), "w",
                      encoding="utf-8", newline="") as f:
                f.write(rec["prompt"])
            index.write(json.dumps({
                "instance_id": rec["instance_id"],
                "prompt_file": name,
                "gold_answer": rec["answer"],
                "ticker": rec["ticker"],
            }, ensure_ascii=False) + "\n")

    print("exported %d C0 prompts to %s/" % (len(records), args.out_dir))
    print("index: %s" % index_path)
    check(records, args.out_dir)


if __name__ == "__main__":
    main()
