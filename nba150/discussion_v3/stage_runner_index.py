"""Stage the discussion_v3 prompts in the layout qwen/run_qwen_paper50.py reads.

The runner expects one directory per condition holding <i>.txt and an
index.jsonl beside them. The v3 bundle keeps its indexes under indexes/, and
its own checker insists that prompts/<cond>/ hold exactly the 150 numbered
files, so the index cannot live there. This builds a separate tree,

    nba150/discussion_v3/cli/<cond>/{1..150}.txt + index.jsonl

by copying, and checks every copied prompt against the sha256 the index
records, so a tree that has been through newline translation or a partial
checkout fails here rather than silently sending the wrong bytes to a model.
The staged tree is derived and is not committed; run this on the machine that
will run the model, at job time.

Usage:  python nba150/discussion_v3/stage_runner_index.py            # all seven
        python nba150/discussion_v3/stage_runner_index.py full remove
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


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check_only = "--check" in sys.argv[1:]
    conds = [a.lower() for a in args] or list(CONDITIONS)
    bad = 0
    for cond in conds:
        if cond not in CONDITIONS:
            raise SystemExit("unknown condition %s" % cond)
        src_dir = os.path.join(HERE, "prompts", cond)
        dst_dir = os.path.join(HERE, "cli", cond)
        rows = [json.loads(l) for l in io.open(
            os.path.join(HERE, "indexes", "%s.jsonl" % cond), encoding="utf-8")
                if l.strip()]
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
        print("%-12s %3d prompts  %s" % (cond, len(rows),
                                         "verified" if not bad else "FAIL"))
    if bad:
        print("FAIL: %d problems" % bad)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
