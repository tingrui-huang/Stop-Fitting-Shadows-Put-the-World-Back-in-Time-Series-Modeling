"""Report token spend for a run, against the SPIKE weekly budget.

The gateway allows 10,000,000 prompt tokens and 1,000,000 completion tokens per
user per week, reset Monday 00:00 CET. The prompt side is comfortable for this
study - all five TSRBench conditions over 160 items is about 1.8M - but the
completion side is the binding constraint, and a thinking model can spend
several thousand completion tokens on a single item. Run a small pilot, read
this, and only then choose a scope.

Every number here comes from the `usage` object the gateway returned with each
response, which is stored verbatim in the per-instance result files. Nothing is
estimated.

Usage:  python spike_budget.py --run-tag tsrbench160_glm53flash
        python spike_budget.py --run-tag ... --project qa_only:160 full:160
"""
import argparse
import glob
import io
import json
import os

PROMPT_BUDGET = 10_000_000
COMPLETION_BUDGET = 1_000_000


def rows(tag):
    """Every request that reached the model, successful or not.

    Counting only the result files understates the spend badly, and in exactly
    the wrong direction: an instance that produced no usable answer did so by
    running the completion ceiling out, so it is the most expensive kind there
    is. Reading this project's first metered run, the result files accounted
    for 172k completion tokens while the gateway had metered 1,015k - the whole
    gap sat in instances that generated a full ceiling and wrote no file.

    Failures are read from failures_<cond>.jsonl. Records written before the
    runner started storing usage there carry no usage field; they are counted
    separately and reported, never silently treated as free.
    """
    out, unknown = [], 0
    for p in sorted(glob.glob(os.path.join("results", tag, "*_raw", "*.json"))):
        rec = json.load(io.open(p, encoding="utf-8"))
        u = rec.get("usage") or {}
        out.append((os.path.basename(os.path.dirname(p))[:-4], "ok",
                    u.get("prompt_tokens") or 0, u.get("completion_tokens") or 0))
    for p in sorted(glob.glob(os.path.join("results", tag, "failures_*.jsonl"))):
        cond = os.path.basename(p)[len("failures_"):-len(".jsonl")]
        for line in io.open(p, encoding="utf-8"):
            if not line.strip():
                continue
            rec = json.loads(line)
            # A request the endpoint refused outright - a budget or rate error -
            # generated nothing and cost nothing.
            if "429" in str(rec.get("error") or ""):
                continue
            u = rec.get("usage")
            if not u:
                unknown += 1
                continue
            out.append((cond, "failed",
                        u.get("prompt_tokens") or 0, u.get("completion_tokens") or 0))
    return out, unknown


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-tag", required=True)
    ap.add_argument("--project", nargs="*", default=None,
                    help="cond:N pairs to extrapolate this run's per-item cost "
                         "to, e.g. full:160 no_ts:160")
    args = ap.parse_args()

    data, unknown = rows(args.run_tag)
    if not data:
        raise SystemExit("no results under results/%s" % args.run_tag)

    per = {}
    for cond, kind, p, c in data:
        d = per.setdefault(cond, [0, 0, 0, 0])
        d[0] += 1
        d[1] += p
        d[2] += c
        d[3] += (kind == "failed")

    print("token spend for %s, from the usage the endpoint reported for every "
          "request that reached it" % args.run_tag)
    print("  %-10s %5s %7s %12s %12s %12s %12s"
          % ("cond", "n", "failed", "prompt", "completion",
             "prompt/item", "compl/item"))
    tp = tc = 0
    for cond in sorted(per):
        n, p, c, nf = per[cond]
        tp += p
        tc += c
        print("  %-10s %5d %7d %12d %12d %12.0f %12.0f"
              % (cond, n, nf, p, c, p / n, c / n))
    print("  %-10s %5d %7d %12d %12d"
          % ("TOTAL", len(data), sum(v[3] for v in per.values()), tp, tc))
    if unknown:
        print("  NOT COUNTED: %d failed request(s) whose usage was not stored "
              "(runs made before the runner recorded it). Their real cost is "
              "one completion ceiling each, so the totals above are a floor."
              % unknown)
    print()
    print("  against the weekly budget:")
    print("    prompt      %9d / %9d  = %5.1f%%"
          % (tp, PROMPT_BUDGET, 100 * tp / PROMPT_BUDGET))
    print("    completion  %9d / %9d  = %5.1f%%   <- the binding one"
          % (tc, COMPLETION_BUDGET, 100 * tc / COMPLETION_BUDGET))

    if args.project:
        print()
        print("  projected from the per-item cost measured above:")
        gp = gc = 0
        for spec in args.project:
            cond, _, n = spec.partition(":")
            n = int(n)
            if cond not in per:
                print("    %-10s no measurement for this condition yet" % cond)
                continue
            cn, cp, cc = per[cond]
            gp += cp / cn * n
            gc += cc / cn * n
            print("    %-10s x %3d  ->  %9.0f prompt  %9.0f completion"
                  % (cond, n, cp / cn * n, cc / cn * n))
        print("    %-10s      ->  %9.0f prompt  %9.0f completion"
              % ("TOTAL", gp, gc))
        print("    completion would be %5.1f%% of the weekly budget%s"
              % (100 * gc / COMPLETION_BUDGET,
                 "  -- OVER, cut the scope" if gc > COMPLETION_BUDGET else ""))


if __name__ == "__main__":
    main()
