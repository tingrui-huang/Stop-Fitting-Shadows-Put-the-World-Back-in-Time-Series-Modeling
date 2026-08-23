"""Print one discordant dossier in readable form (analysis aid, writes nothing).

Usage:  python flip_show.py <instance_id>
"""

import json
import sys


def main():
    iid = int(sys.argv[1])
    cases = json.load(open("results/_flip_dossier_dump.json", encoding="utf-8"))
    c = [x for x in cases if x["instance_id"] == iid][0]
    t = c["task"]
    print("=" * 78)
    print("INSTANCE %d  %s   %s" % (iid, t["ticker"], c["transition"]))
    print("=" * 78)
    print("gold=%s  gt_event=%s  gt_published=%s  gt_position=%d  ts_points=%d"
          % (t["gold_answer"], t["gt_event_type"], t["gt_published_utc"],
             t["gt_position_in_pool"], t["n_ts_points"]))
    print("\n--- QUESTION ---")
    print(t["question_and_options"])
    for cond in ("c1", "c2"):
        r = c[cond]
        print("\n--- %s  answer=%s  correct=%s  conf=%s ---"
              % (cond.upper(), r["prediction"], r["correct"], r["confidence"]))
        print(r["rationale"])
        for e in r["evidence_resolved"]:
            rt = e["resolves_to"]
            print("   cites Article %s -> %s" % (
                e["cited_article_number"],
                "OUT OF RANGE" if rt is None else
                "pos %d %s %s off=%+.1fd  %s" % (
                    rt["position"], rt["role"], rt["alias_direction"] or "",
                    rt["offset_days"], rt["title"][:70])))
    print("\n--- EVIDENCE POOL (rendered order) ---")
    for e in c["evidence_pool"]:
        print("%2d %-22s %-6s %-19s %+8.1fd %-8s %-6s %s" % (
            e["position"], e["role"], e["ticker"], e["published_utc"],
            e["offset_days"], e["event_type"] or "-",
            e["event_match_tier"] or e.get("type_b_relation_tier") or "-",
            e["title"][:64]))
    print("\n--- C2 TITLES (masked) ---")
    for e in c["evidence_pool"]:
        if e["title"] != e["title_c2"]:
            print("%2d  %s" % (e["position"], e["title_c2"][:90]))
    d = c["c1_vs_c2_input_difference"]
    print("\n--- C1 vs C2 INPUT DIFFERENCE ---")
    print("TS C1: %s" % d["ts_c1_first_two_lines"])
    print("TS C2: %s" % d["ts_c2_first_two_lines"])
    print("publication timestamps removed: %d" % d["n_article_publication_timestamps_removed"])
    print("in-article temporal masks: %d" % d["n_in_article_temporal_masks"])
    print("unchanged: %s" % json.dumps(d["unchanged"]))
    print("masking audit: %d changes, %d flagged"
          % (c["masking_side_effect_audit"]["n_textual_changes"],
             c["masking_side_effect_audit"]["n_flagged"]))
    print("exposure: %s" % json.dumps(c["type_a_exposure"]))


if __name__ == "__main__":
    main()
