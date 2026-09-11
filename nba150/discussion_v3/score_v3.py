"""Score raw CLI outputs of one discussion_v3 condition against the index gold.

Usage:  python nba150/discussion_v3/score_v3.py <cond_lower> [results_root] [first_id] [last_id]
"""
import collections, io, json, os, re, sys

ANSWER = re.compile(r'"answer"\s*:\s*"([ABCD])"')

def main():
    cond = sys.argv[1]
    root = sys.argv[2] if len(sys.argv) > 2 else "results/nba150_v3_sonnet5"
    first = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    last = int(sys.argv[4]) if len(sys.argv) > 4 else 150
    idx = {}
    with io.open("nba150/discussion_v3/indexes/%s.jsonl" % cond, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            idx[r["instance_id"]] = r["gold_answer"]
    rows, missing, malformed = [], [], []
    n_correct = 0
    dist = collections.Counter()
    conf = collections.Counter()  # (gold, pred)
    for i in range(first, last + 1):
        p = os.path.join(root, "%s_raw" % cond, "%d.txt" % i)
        if not os.path.exists(p):
            missing.append(i); continue
        raw = io.open(p, encoding="utf-8").read()
        m = ANSWER.search(raw)
        pred = m.group(1) if m else None
        if pred is None:
            malformed.append(i)
        gold = idx[i]
        ok = int(pred == gold)
        n_correct += ok
        dist[pred or "?"] += 1
        conf[(gold, pred or "?")] += 1
        rows.append({"instance_id": i, "gold": gold, "pred": pred, "correct": ok})
    n = last - first + 1
    n_done = n - len(missing)
    out = {
        "condition": cond, "results_root": root, "instance_ids": "%d-%d" % (first, last),
        "n_total": n, "n_completed": n_done, "n_correct": n_correct,
        "accuracy": n_correct / n if n else None,
        "n_missing": len(missing), "missing_instance_ids": missing,
        "n_malformed": len(malformed), "malformed_instance_ids": malformed,
        "answer_distribution": dict(sorted(dist.items())),
        "gold_distribution": dict(sorted(collections.Counter(idx[i] for i in range(first, last + 1)).items())),
        "confusion_gold_pred": {"%s->%s" % k: v for k, v in sorted(conf.items())},
    }
    with io.open(os.path.join(root, "%s_summary.json" % cond), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with io.open(os.path.join(root, "%s_scored.jsonl" % cond), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(json.dumps(out, indent=2))
    print("\nper-item: " + " ".join("%d:%s%s" % (r["instance_id"], r["pred"], "" if r["correct"] else "x") for r in rows))

if __name__ == "__main__":
    main()
