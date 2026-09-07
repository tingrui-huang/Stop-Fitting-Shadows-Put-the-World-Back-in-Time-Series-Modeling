"""Score both tasks under one rule, and test the ablations against FULL.

Why this file exists: the stored results were not produced under a uniform
retry policy. The GDELT runs got essentially one attempt per instance; the NBA
runs, through a later pass of mine, got up to four, and SHUFFLED got the fewest
of the four NBA conditions. Comparing those tables directly compares how many
chances I gave each condition, not what the timestamps did.

The rule applied here is the one the GDELT runs already used and the one that
can be stated in a sentence:

    one attempt per instance; an instance that exhausted the completion
    ceiling without leaving a usable answer counts wrong.

Retries are not merely unequal here, they are the wrong instrument: retrying
helps whichever condition truncates most, which is exactly the condition an
ablation is supposed to expose. So the first model-reaching attempt is
reconstructed from the stored records rather than averaged over attempts. A
transport failure - DNS, HTTP 401 - never reached the model and is not an
attempt; only a truncation record or a saved result counts.

Three numbers are reported per condition, because collapsing them hides the
finding:

    accuracy            over the full census, truncation counted wrong
    accuracy | answered choice quality, given the run produced an answer
    truncation rate     an outcome in its own right, not a missing cell

Usage:  python analysis/uniform_scoring.py
"""
import collections
import glob
import io
import json
import math
import os
import re

TASKS = [("GDELT", "results/tsrbench160_glm53flash_zai", 160),
         ("NBA", "results/nba150_glm53flash_zai", 150)]
CONDS = ("qa_only", "full", "no_ts", "shuffled", "relative")
ANSWER = re.compile(r'"answer"\s*:\s*"([ABCD])"')


def first_attempt(root, cond, n):
    """-> {instance_id: (correct, answered, trace)} on the first real attempt."""
    raw = {}
    for p in glob.glob(os.path.join(root, "%s_raw" % cond, "*.json")):
        r = json.load(io.open(p, encoding="utf-8"))
        raw[int(r["instance_id"])] = r

    truncs = collections.defaultdict(list)
    fp = os.path.join(root, "failures_%s.jsonl" % cond)
    if os.path.exists(fp):
        for line in io.open(fp, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                if r.get("truncated"):
                    truncs[int(r["instance_id"])].append(
                        (r["utc"], r.get("reasoning") or ""))

    out = {}
    for i in range(1, n + 1):
        rec = raw.get(i)
        earliest = min(truncs[i]) if truncs.get(i) else None
        # The saved result is the first attempt unless a truncation predates it.
        if rec is None or (earliest and earliest[0] < rec["started_utc"]):
            out[i] = (0, 0, earliest[1] if earliest else "")
        else:
            m = ANSWER.search(rec.get("content") or "")
            ok = int(bool(m and m.group(1) == rec["gold_answer"]))
            out[i] = (ok, 1, rec.get("reasoning") or "")
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / float(n)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4.0 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def exact_mcnemar(a, b, keys):
    """Two-sided exact McNemar on paired binary outcomes."""
    x = sum(1 for i in keys if a[i] and not b[i])
    y = sum(1 for i in keys if b[i] and not a[i])
    n = x + y
    if n == 0:
        return x, y, 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(x, y) + 1))
    return x, y, min(1.0, 2.0 * tail / 2.0 ** n)


def exact_binom(k, n, p0):
    """Two-sided exact binomial, by the method of small p-values."""
    if n == 0:
        return 1.0
    obs = math.comb(n, k) * p0 ** k * (1 - p0) ** (n - k)
    tot = 0.0
    for j in range(n + 1):
        pj = math.comb(n, j) * p0 ** j * (1 - p0) ** (n - j)
        if pj <= obs * (1 + 1e-9):
            tot += pj
    return min(1.0, tot)


def main():
    for tag, root, n in TASKS:
        if not os.path.isdir(root):
            continue
        D = {c: first_attempt(root, c, n) for c in CONDS
             if os.path.isdir(os.path.join(root, "%s_raw" % c))}

        print("=" * 78)
        print("%s   n = %d   one attempt per instance, truncation counted wrong"
              % (tag, n))
        print("=" * 78)
        print("%-10s %16s %16s %18s %14s"
              % ("condition", "accuracy", "95% CI", "accuracy|answered",
                 "truncated"))
        for c in CONDS:
            if c not in D:
                continue
            k = sum(v[0] for v in D[c].values())
            a = sum(v[1] for v in D[c].values())
            lo, hi = wilson(k, n)
            print("%-10s %7d/%3d %.3f  [%.2f, %.2f] %10d/%3d %.3f %8d/%3d %5.1f%%"
                  % (c.upper(), k, n, k / float(n), lo, hi, k, a,
                     (k / float(a) if a else 0.0), n - a, n,
                     100.0 * (n - a) / n))

        if "full" not in D:
            continue
        keys = list(range(1, n + 1))
        full_ok = {i: D["full"][i][0] for i in keys}
        full_ans = {i: D["full"][i][1] for i in keys}

        print("\nexact McNemar vs FULL")
        for c in CONDS:
            if c in ("full",) or c not in D:
                continue
            ok = {i: D[c][i][0] for i in keys}
            x, y, p = exact_mcnemar(full_ok, ok, keys)
            print("  FULL vs %-9s  FULL only %3d   %-9s only %3d   p = %.3g"
                  % (c.upper(), x, c.upper(), y, p))

        print("\nexact McNemar vs FULL, restricted to items both answered")
        for c in CONDS:
            if c in ("full",) or c not in D:
                continue
            ok = {i: D[c][i][0] for i in keys}
            sub = [i for i in keys if full_ans[i] and D[c][i][1]]
            x, y, p = exact_mcnemar(full_ok, ok, sub)
            print("  FULL vs %-9s  n = %3d   FULL only %3d   %-9s only %3d"
                  "   p = %.3g" % (c.upper(), len(sub), x, c.upper(), y, p))

        print("\nexact McNemar vs FULL on truncation itself")
        for c in CONDS:
            if c in ("full",) or c not in D:
                continue
            ft = {i: 1 - full_ans[i] for i in keys}
            ct = {i: 1 - D[c][i][1] for i in keys}
            x, y, p = exact_mcnemar(ft, ct, keys)
            print("  FULL vs %-9s  FULL only %3d   %-9s only %3d   p = %.3g"
                  % (c.upper(), x, c.upper(), y, p))

        print("\nvs chance (0.250), two-sided exact binomial")
        for c in CONDS:
            if c not in D:
                continue
            k = sum(v[0] for v in D[c].values())
            print("  %-9s %3d/%3d   p = %.3g"
                  % (c.upper(), k, n, exact_binom(k, n, 0.25)))
        print()


if __name__ == "__main__":
    main()
