"""TASK 1 - join the final C1 and C2 Sonnet-5 results and classify every instance.

Read-only: touches nothing but the frozen result files, writes only
results/c1_c2_transition_table.json.

Usage:  python flip_task1.py
"""

import json

C1 = "results/paper50_c1_sonnet5.jsonl"
C2 = "results/paper50_c2_sonnet5.jsonl"
OUT = "results/c1_c2_transition_table.json"

GROUPS = ("BOTH_CORRECT", "C1_CORRECT_C2_WRONG", "C1_WRONG_C2_CORRECT", "BOTH_WRONG")


def load(path):
    with open(path, encoding="utf-8") as f:
        return {json.loads(l)["instance_id"]: json.loads(l) for l in f if l.strip()}


def main():
    c1, c2 = load(C1), load(C2)
    assert set(c1) == set(c2), "instance sets differ"
    ids = sorted(c1)

    rows, groups = [], {g: [] for g in GROUPS}
    for i in ids:
        a, b = c1[i], c2[i]
        assert a["gold_answer"] == b["gold_answer"], "gold answer differs at %d" % i
        if a["correct"] and b["correct"]:
            g = "BOTH_CORRECT"
        elif a["correct"]:
            g = "C1_CORRECT_C2_WRONG"
        elif b["correct"]:
            g = "C1_WRONG_C2_CORRECT"
        else:
            g = "BOTH_WRONG"
        groups[g].append(i)
        rows.append({
            "instance_id": i,
            "group": g,
            "gold_answer": a["gold_answer"],
            "c1_answer": a["prediction"], "c1_correct": a["correct"],
            "c1_confidence": a["confidence"],
            "c2_answer": b["prediction"], "c2_correct": b["correct"],
            "c2_confidence": b["confidence"],
            "answer_changed": a["prediction"] != b["prediction"],
        })

    # ticker from the frozen dataset, never from a model output
    tickers = {r["instance_id"]: r["ticker"]
               for r in json.load(open("final50_paper_data.json", encoding="utf-8"))}
    for r in rows:
        r["ticker"] = tickers[r["instance_id"]]

    out = {
        "source": {"c1": C1, "c2": C2, "dataset": "final50_paper_data.json"},
        "n_instances": len(ids),
        "aggregate": {
            "c1_correct": sum(r["c1_correct"] for r in rows),
            "c2_correct": sum(r["c2_correct"] for r in rows),
            "c1_accuracy": round(sum(r["c1_correct"] for r in rows) / len(rows), 4),
            "c2_accuracy": round(sum(r["c2_correct"] for r in rows) / len(rows), 4),
        },
        "transition_matrix": {g: len(groups[g]) for g in GROUPS},
        "group_instance_ids": {g: groups[g] for g in GROUPS},
        "n_answer_changed": sum(r["answer_changed"] for r in rows),
        "answer_changed_ids": [r["instance_id"] for r in rows if r["answer_changed"]],
        "instances": rows,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("C1 %d/50   C2 %d/50" % (out["aggregate"]["c1_correct"],
                                   out["aggregate"]["c2_correct"]))
    for g in GROUPS:
        print("%-22s %2d   %s" % (g, len(groups[g]), groups[g]))
    print("")
    print("answers that changed at all between C1 and C2: %d  %s"
          % (out["n_answer_changed"], out["answer_changed_ids"]))
    print("")
    hdr = "%-6s %-6s %-5s %-4s %-6s %-4s %-6s  %s"
    print(hdr % ("id", "ticker", "gold", "C1", "conf", "C2", "conf", "group"))
    for r in rows:
        if r["group"] in ("C1_CORRECT_C2_WRONG", "C1_WRONG_C2_CORRECT", "BOTH_WRONG"):
            print(hdr % (r["instance_id"], r["ticker"], r["gold_answer"],
                         r["c1_answer"], r["c1_confidence"],
                         r["c2_answer"], r["c2_confidence"], r["group"]))
    print("\nwrote %s" % OUT)


if __name__ == "__main__":
    main()
