"""Integrity check: the frozen Paper50 inputs must be bit-identical, always.

Covers all 200 prompt files, the four index files and prompts/system.txt.
First run records a baseline; every later run compares against it, so an
accidental rebuild or edit is caught rather than silently absorbed into a result.

Also cross-checks the Qwen run itself: each saved result stores the sha256 of
the prompt and system prompt that were actually sent, and those must match the
files on disk.  That is what proves the run used the frozen text.

Usage
  python qwen/verify_frozen_inputs.py --write-baseline   # once, before running
  python qwen/verify_frozen_inputs.py                    # before/after any run
  python qwen/verify_frozen_inputs.py --check-results    # also audit sent hashes
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qwen_common import sha256_file  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "qwen", "frozen_inputs_baseline.json")
CONDS = ("c0", "c1", "c2", "c3")


def fingerprint():
    fp = {"prompts/system.txt": sha256_file(os.path.join(ROOT, "prompts",
                                                         "system.txt"))}
    for c in CONDS:
        d = os.path.join(ROOT, "out_paper50_reviewed", "%s_cli" % c)
        for name in sorted(os.listdir(d)):
            if name.endswith(".txt") or name == "index.jsonl":
                rel = "out_paper50_reviewed/%s_cli/%s" % (c, name)
                fp[rel] = sha256_file(os.path.join(d, name))
    return fp


def check_results(fp):
    """Every saved Qwen result must name the frozen text it was given."""
    bad, n = [], 0
    root = os.path.join(ROOT, "results", "qwen36")
    sys_sha = fp["prompts/system.txt"]
    for c in CONDS:
        d = os.path.join(root, "%s_raw" % c)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith(".json"):
                continue
            n += 1
            with open(os.path.join(d, name), encoding="utf-8") as f:
                rec = json.load(f)
            want = fp.get((rec.get("prompt_file") or "").replace("\\", "/"))
            if want is None:
                bad.append((name, "prompt_file %r is not a frozen input"
                            % rec.get("prompt_file")))
            elif rec.get("prompt_sha256") != want:
                bad.append((name, "prompt sha256 sent does not match the frozen "
                                  "file on disk"))
            if rec.get("system_prompt_sha256") != sys_sha:
                bad.append((name, "system prompt sha256 sent does not match "
                                  "prompts/system.txt"))
    return n, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--check-results", action="store_true")
    args = ap.parse_args()

    fp = fingerprint()
    if args.write_baseline:
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"note": "sha256 of every frozen Paper50 input; these "
                               "files must never change",
                       "n_files": len(fp), "files": fp}, f, indent=2)
        print("baseline written: %d files -> %s"
              % (len(fp), os.path.relpath(BASELINE, ROOT)))
        return

    if not os.path.exists(BASELINE):
        raise SystemExit("no baseline yet; run --write-baseline first")
    base = json.load(open(BASELINE, encoding="utf-8"))["files"]
    changed = sorted(k for k in set(base) & set(fp) if base[k] != fp[k])
    added = sorted(set(fp) - set(base))
    removed = sorted(set(base) - set(fp))

    print("frozen inputs: %d files checked" % len(fp))
    for label, xs in (("CHANGED", changed), ("ADDED", added), ("REMOVED", removed)):
        if xs:
            print("  %s (%d):" % (label, len(xs)))
            for x in xs[:20]:
                print("    %s" % x)
    ok = not (changed or added or removed)
    print("  %s" % ("FROZEN INPUTS UNCHANGED" if ok
                    else "FROZEN INPUTS DIFFER FROM BASELINE"))

    if args.check_results:
        n, bad = check_results(fp)
        print("\nsaved Qwen results audited: %d" % n)
        for name, why in bad[:20]:
            print("  MISMATCH %s: %s" % (name, why))
        print("  %s" % ("every result was produced from the frozen text"
                        if not bad else "%d mismatch(es)" % len(bad)))
        ok = ok and not bad
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
