"""Scratch dump: every C1/C2 rationale with its citations resolved to roles.

Analysis aid only - writes nothing to results/.  Used to hand-annotate
cited_as_support vs cited_but_rejected for the all-50 grounding audit.

Usage:  python _dump_rationales.py [c1|c2]
"""

import json
import re
import sys

MAN = "out_paper50_reviewed/manifest.json"


def roles_by_position():
    man = json.load(open(MAN, encoding="utf-8"))["instances"]
    out = {}
    for m in man:
        dmeta = {x["article_id"]: x for x in m["distractors"]}
        r = {}
        for pos, aid in enumerate(m["article_order"], 1):
            if pos == m["gt_position"]:
                r[pos] = {"role": "GT", "offset_days": 0.0, "dir": None,
                          "tier": None, "id": aid}
            else:
                d = dmeta[aid]
                r[pos] = {
                    "role": "A" if d["distractor_type"] == "temporal_aliasing" else "B",
                    "offset_days": d["offset_days"],
                    "dir": d["alias_direction"] if d["distractor_type"] ==
                    "temporal_aliasing" else None,
                    "tier": d["event_match_tier"] if d["distractor_type"] ==
                    "temporal_aliasing" else None,
                    "id": aid}
        out[m["instance_id"]] = r
    return out


def tag(r):
    if r["role"] == "GT":
        return "GT"
    if r["role"] == "A":
        return "A[%s %+.0fd %s]" % (r["dir"][:4], r["offset_days"], r["tier"][:3])
    return "B[%+.0fd]" % r["offset_days"]


def main():
    cond = (sys.argv[1] if len(sys.argv) > 1 else "c1").lower()
    roles = roles_by_position()
    recs = {}
    with open("results/paper50_%s_sonnet5.jsonl" % cond, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            recs[r["instance_id"]] = r
    data = {r["instance_id"]: r for r in
            json.load(open("final50_paper_data.json", encoding="utf-8"))}

    for i in sorted(recs):
        r, rr = recs[i], roles[i]
        cites = r.get("evidence_articles") or []
        inline = sorted({int(x) for x in re.findall(r"Article\s+(\d+)",
                                                    r["rationale"] or "")})
        def fmt(ns):
            return ", ".join("%d=%s" % (n, tag(rr[n]) if n in rr else "OUT_OF_RANGE")
                             for n in ns) or "-"
        print("### %d %s  gold=%s pred=%s %s conf=%s"
              % (i, data[i]["ticker"], r["gold_answer"], r["prediction"],
                 "OK" if r["correct"] else "XX", r["confidence"]))
        print("    cites : %s" % fmt(cites))
        print("    inline: %s" % fmt(inline))
        print("    why   : %s" % (r["rationale"] or "").replace("\n", " "))
        print("")


if __name__ == "__main__":
    main()
