"""Stage the discussion_v3 prompts in the layout qwen/run_qwen_paper50.py reads.

The runner expects one directory per condition holding <i>.txt and an
index.jsonl beside them. The v3 bundle keeps its indexes under indexes/, and
its own checker insists that prompts/<cond>/ hold exactly the 150 numbered
files, so the index cannot live there. This builds a separate tree,

    nba150/discussion_v3/cli/<cond>/{1..N}.txt + index.jsonl

by copying, and checks every copied prompt against the sha256 the index
records, so a tree that has been through newline translation or a partial
checkout fails here rather than silently sending the wrong bytes to a model.
The staged tree is derived and is not committed; run this on the machine that
will run the model, at job time.

--limit N stages the first N items instead of all 150, for a pilot. The limit
belongs here rather than in the runner because the collector and scorer read
this index to decide what is missing: an index of 50 makes a 50-item run
complete, where a 150-row index would report it as 100 instances missing. The
first N items are taken in source order, the same N in every condition, so the
conditions stay paired. Raising the limit later and re-running adds the rest;
an instance whose result file exists is never re-sent.

Usage:  python nba150/discussion_v3/stage_runner_index.py            # all seven
        python nba150/discussion_v3/stage_runner_index.py full remove
        python nba150/discussion_v3/stage_runner_index.py --limit 50 full shuffle
        python nba150/discussion_v3/stage_runner_index.py --check    # verify only
"""
import hashlib
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONDITIONS = ("full", "text_only", "series_only", "qa_only",
              "remove", "shuffle", "relative")


def sha(path):
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()


def parse_args(argv):
    conds, limit, check_only, i = [], 0, False, 0
    while i < len(argv):
        a = argv[i]
        if a == "--check":
            check_only = True
        elif a == "--limit":
            i += 1
            if i >= len(argv):
                raise SystemExit("--limit needs a number")
            limit = int(argv[i])
        elif a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])
        elif a.startswith("--"):
            raise SystemExit("unknown option %s" % a)
        else:
            conds.append(a.lower())
        i += 1
    for c in conds:
        if c not in CONDITIONS:
            raise SystemExit("unknown condition %s" % c)
    return (conds or list(CONDITIONS)), limit, check_only


def main():
    conds, limit, check_only = parse_args(sys.argv[1:])
    bad = 0
    for cond in conds:
        src_dir = os.path.join(HERE, "prompts", cond)
        dst_dir = os.path.join(HERE, "cli", cond)
        rows = [json.loads(l) for l in io.open(
            os.path.join(HERE, "indexes", "%s.jsonl" % cond), encoding="utf-8")
                if l.strip()]
        if limit > 0:
            rows = rows[:limit]
        if not check_only:
            os.makedirs(dst_dir, exist_ok=True)
        for r in rows:
            name = "%d.txt" % r["instance_id"]
            src, dst = os.path.join(src_dir, name), os.path.join(dst_dir, name)
            if not check_only:
                shutil.copyfile(src, dst)
            if not os.path.exists(dst) or sha(dst) != r["prompt_sha256"]:
                bad += 1
                print("BAD %s/%s" % (cond, name))
        idx = os.path.join(dst_dir, "index.jsonl")
        if not check_only:
            with io.open(idx, "w", encoding="utf-8", newline="\n") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        elif not os.path.exists(idx):
            bad += 1
            print("MISSING %s" % os.path.relpath(idx))
        print("%-12s %3d prompts  ids %d-%d  %s"
              % (cond, len(rows), rows[0]["instance_id"],
                 rows[-1]["instance_id"], "verified" if not bad else "FAIL"))
    if bad:
        print("FAIL: %d problems" % bad)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
