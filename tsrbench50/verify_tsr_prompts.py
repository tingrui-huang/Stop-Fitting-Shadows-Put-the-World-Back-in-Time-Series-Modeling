"""Check one condition's frozen prompts against manifest.json.  Read-only.

The prompts are experimental inputs, so a run must never rebuild them under
itself - four array tasks rebuilding the same tree at once would race.  This
verifies instead: every prompt file must hash to what the manifest recorded
when the tree was built, or the job refuses to start.
"""
import argparse
import hashlib
import io
import json
import os
import sys


def sha256_file(path):
    text = io.open(path, encoding="utf-8", newline="").read()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cli", required=True, help="the tree holding manifest.json")
    ap.add_argument("--condition", required=True)
    args = ap.parse_args()

    manifest = json.load(io.open(os.path.join(args.cli, "manifest.json"),
                                 encoding="utf-8"))
    want = manifest["prompts"][args.condition]
    where = os.path.join(args.cli, args.condition.lower())

    bad = []
    for iid in sorted(want, key=int):
        path = os.path.join(where, iid + ".txt")
        if not os.path.exists(path):
            bad.append((iid, "missing"))
        elif sha256_file(path) != want[iid]:
            bad.append((iid, "sha256 differs from the manifest"))

    for iid, why in bad[:10]:
        print("PROMPT %s/%s: %s" % (args.condition, iid, why))
    if bad:
        sys.exit("%d of %d prompts do not match the manifest; refusing to run"
                 % (len(bad), len(want)))
    print("%s: all %d prompts match manifest.json" % (args.condition, len(want)))


if __name__ == "__main__":
    main()
