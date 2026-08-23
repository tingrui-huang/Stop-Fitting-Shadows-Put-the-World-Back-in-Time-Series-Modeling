"""Descriptive citation statistics for C1 vs C2 over all 50 instances.

Task 5 only asks about the discordant cases, but the discordant numbers mean
little without the denominator: how often does the model cite the GT, a
temporal alias, or absence evidence when timestamps are present versus removed?

Purely descriptive - no significance testing, n = 50.

Writes results/c1_c2_citation_stats.json.

Usage:  python flip_citation_stats.py
"""

import json

from flip_dossiers import jsonl, news_block, split_articles

ROLES = ("GT", "TYPE_A_TEMPORAL_ALIAS", "TYPE_B_ABSENCE")


def main():
    man = {m["instance_id"]: m for m in
           json.load(open("out_paper50_reviewed/manifest.json",
                          encoding="utf-8"))["instances"]}
    c1r = jsonl("out_paper50_reviewed/c1.jsonl")
    models = {"C1": jsonl("results/paper50_c1_sonnet5.jsonl"),
              "C2": jsonl("results/paper50_c2_sonnet5.jsonl")}

    role_by_pos = {}
    for i, m in man.items():
        dmeta = {x["article_id"]: x for x in m["distractors"]}
        roles = {}
        for pos, aid in enumerate(m["article_order"], 1):
            if pos == m["gt_position"]:
                roles[pos] = "GT"
            else:
                roles[pos] = ("TYPE_A_TEMPORAL_ALIAS"
                              if dmeta[aid]["distractor_type"] == "temporal_aliasing"
                              else "TYPE_B_ABSENCE")
        role_by_pos[i] = roles

    out = {"scope": "all 50 instances, descriptive only (n=50, no tests)",
           "conditions": {}, "per_instance": {}}
    for cond, recs in models.items():
        stat = {"n_instances": 0, "n_citing_nothing": 0,
                "n_citing_gt": 0, "n_citing_type_a": 0, "n_citing_type_b": 0,
                "n_citing_only_gt": 0, "n_citing_any_distractor": 0,
                "n_out_of_range_citations": 0,
                "n_citations_total": 0,
                "citations_by_role": {r: 0 for r in ROLES},
                "correct_and_citing_type_a": [],
                "incorrect_and_citing_type_a": []}
        for i, rec in recs.items():
            roles = role_by_pos[i]
            cites = rec.get("evidence_articles") or []
            got = [roles.get(n) for n in cites]
            stat["n_instances"] += 1
            stat["n_citations_total"] += len(cites)
            stat["n_out_of_range_citations"] += sum(1 for g in got if g is None)
            for g in got:
                if g:
                    stat["citations_by_role"][g] += 1
            if not cites:
                stat["n_citing_nothing"] += 1
            if "GT" in got:
                stat["n_citing_gt"] += 1
            if "TYPE_A_TEMPORAL_ALIAS" in got:
                stat["n_citing_type_a"] += 1
                (stat["correct_and_citing_type_a"] if rec["correct"]
                 else stat["incorrect_and_citing_type_a"]).append(i)
            if "TYPE_B_ABSENCE" in got:
                stat["n_citing_type_b"] += 1
            if got and set(got) == {"GT"}:
                stat["n_citing_only_gt"] += 1
            if any(g and g != "GT" for g in got):
                stat["n_citing_any_distractor"] += 1
            out["per_instance"].setdefault(str(i), {})[cond] = {
                "cited": cites, "roles": got, "correct": rec["correct"]}
        out["conditions"][cond] = stat

    with open("results/c1_c2_citation_stats.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    keys = ["n_citing_nothing", "n_citing_gt", "n_citing_only_gt",
            "n_citing_type_a", "n_citing_type_b", "n_citing_any_distractor",
            "n_citations_total", "n_out_of_range_citations"]
    print("%-28s %6s %6s" % ("", "C1", "C2"))
    for k in keys:
        print("%-28s %6s %6s" % (k, out["conditions"]["C1"][k],
                                 out["conditions"]["C2"][k]))
    for cond in ("C1", "C2"):
        s = out["conditions"][cond]
        print("\n%s citations by role: %s" % (cond, s["citations_by_role"]))
        print("%s scored CORRECT while citing a temporal alias: %s"
              % (cond, s["correct_and_citing_type_a"]))
        print("%s scored WRONG while citing a temporal alias:   %s"
              % (cond, s["incorrect_and_citing_type_a"]))
    print("\nwrote results/c1_c2_citation_stats.json")


if __name__ == "__main__":
    main()
