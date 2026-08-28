"""Draw a stratified 50 from TSRBench Temporal Relationship Reasoning.

Why this task and no other: of the 4,125 items across TSRBench's twelve task
files, only these 160 carry real-world timestamps. Ten tasks have no time
field at all; etiological_reasoning has a "Time" series but it holds elapsed
seconds (0.0, 110.33, 119.31, ...), an offset rather than an index into the
world, so it cannot support a timestamp intervention either.

Stratification mirrors the Paper50 construction: proportional over the two
factors that are visible in the data and plausibly drive difficulty - the
source domain (8 levels, 20 items each) and the number of events to order
(6, 7 or 8) - with the answer letter balanced as a tiebreak so the draw does
not inherit the pool's D/B skew (48/48 against 34/30).

Selection is deterministic: no RNG. Within a stratum, candidates are ordered
by the answer letter that is furthest behind its target count, then by
timeseries length, then by a sha1 of the question text. Re-running reproduces
the same 50 exactly.

Usage:  python sample_tsrbench50.py --out <dir>
"""
import argparse
import collections
import hashlib
import json
import os

SRC = "reasoning/temporal_relation_reasoning.jsonl"
N_TARGET = 50


def n_events(rec):
    return len(rec["choices"]["A"].split(")("))


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def fingerprint(rec):
    return hashlib.sha1(rec["question"].encode("utf-8")).hexdigest()


def allocate(counts, target):
    """Largest-remainder apportionment: keeps the draw proportional."""
    total = sum(counts.values())
    exact = {k: v * target / total for k, v in counts.items()}
    base = {k: int(v) for k, v in exact.items()}
    short = target - sum(base.values())
    order = sorted(exact, key=lambda k: (-(exact[k] - base[k]), str(k)))
    for k in order[:short]:
        base[k] += 1
    return base


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", required=True, help="directory for the sample")
    ap.add_argument("--n", type=int, default=N_TARGET)
    args = ap.parse_args()

    rows = load(args.src)
    for i, r in enumerate(rows):
        r["_pool_index"] = i
        r["_n_events"] = n_events(r)
        r["_fp"] = fingerprint(r)

    strata = collections.defaultdict(list)
    for r in rows:
        strata[(r["domain"], r["_n_events"])].append(r)
    quota = allocate({k: len(v) for k, v in strata.items()}, args.n)

    letters = ["A", "B", "C", "D"]
    want = {L: args.n / 4.0 for L in letters}
    taken = collections.Counter()
    picked = []

    for key in sorted(strata, key=lambda k: (str(k[0]), k[1])):
        need = quota[key]
        pool = list(strata[key])
        for _ in range(need):
            # prefer the letter furthest below its share, then shorter series,
            # then a stable hash - no randomness anywhere
            pool.sort(key=lambda r: (taken[r["answer"]] - want[r["answer"]],
                                     len(r["timeseries"][0]), r["_fp"]))
            best = pool.pop(0)
            taken[best["answer"]] += 1
            picked.append(best)

    picked.sort(key=lambda r: r["_pool_index"])
    assert len(picked) == args.n, "drew %d, wanted %d" % (len(picked), args.n)
    assert len({r["_pool_index"] for r in picked}) == args.n, "duplicate draw"

    os.makedirs(args.out, exist_ok=True)
    data_path = os.path.join(args.out, "tsrbench%d.jsonl" % args.n)
    with open(data_path, "w", encoding="utf-8", newline="\n") as f:
        for k, r in enumerate(picked):
            out = {kk: vv for kk, vv in r.items() if not kk.startswith("_")}
            out["instance_id"] = k + 1
            out["source_task"] = "Temporal Relationship Reasoning"
            out["source_index"] = r["_pool_index"]
            out["n_events"] = r["_n_events"]
            f.write(json.dumps(out, ensure_ascii=False) + "\n")

    manifest = {
        "source_file": args.src,
        "source_task": "Temporal Relationship Reasoning",
        "source_pool_size": len(rows),
        "n_drawn": args.n,
        "is_census": args.n == len(rows),
        "why_this_task": "the only TSRBench task whose series carry real-world "
                         "timestamps; the other eleven files have no time field "
                         "or hold elapsed seconds rather than dates",
        "stratification": ["domain", "n_events"],
        "balanced_on": "answer letter",
        "deterministic": "no RNG; ties broken by sha1 of the question text",
        "quota": {"%s|%d" % k: v for k, v in sorted(quota.items(),
                                                    key=lambda x: (str(x[0][0]), x[0][1]))},
        "drawn_domain_counts": dict(sorted(collections.Counter(
            r["domain"] for r in picked).items())),
        "drawn_n_events_counts": {str(k): v for k, v in sorted(collections.Counter(
            r["_n_events"] for r in picked).items())},
        "drawn_answer_counts": dict(sorted(taken.items())),
        "pool_answer_counts": dict(sorted(collections.Counter(
            r["answer"] for r in rows).items())),
        "source_indices": [r["_pool_index"] for r in picked],
        "question_sha1": {str(k + 1): r["_fp"] for k, r in enumerate(picked)},
    }
    man_path = os.path.join(args.out, "tsrbench%d_manifest.json" % args.n)
    with open(man_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("pool %d -> drew %d%s" % (len(rows), len(picked),
          "  (the whole pool: this is a census, not a sample)"
          if len(picked) == len(rows) else ""))
    print("  domain  ", manifest["drawn_domain_counts"])
    print("  events  ", manifest["drawn_n_events_counts"])
    print("  answer  ", manifest["drawn_answer_counts"],
          " (pool:", manifest["pool_answer_counts"], ")")
    print("wrote", data_path)
    print("wrote", man_path)


if __name__ == "__main__":
    main()
