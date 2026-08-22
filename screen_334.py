"""Screen replacement candidates for anchor 334 (0 Type-A available). Proposal only."""
import json
from audit_protocol import audit
from build_final_hard50 import load_json
from distractor_policy import alias_map_from, index_by_ticker, load_corpus_frame
from final_curation import (POOL_FILES, STRATA, build_pools, load_rescues, score,
                            summarise)

df = load_corpus_frame()
by_ticker = index_by_ticker(df)
corpus_rows = [a for rows in by_ticker.values() for a in rows]
alias = alias_map_from(df)
rescues = load_rescues()

final = {r["instance_id"]: r for r in load_json("final50_paper_data.json")}
src = {m["instance_id"]: m["selected_source"] for m in
       json.load(open("final50_locked_manifest.json", encoding="utf-8"))["instances"]}

info, a_pool, b_pool = build_pools(final[334], by_ticker, corpus_rows, alias, rescues)
info["source"] = src.get(334, "old")
old, _, _ = summarise(info, a_pool, b_pool)

rows = []
for path in POOL_FILES:
    for rec in load_json(path):
        if rec["instance_id"] in final:
            continue
        valid, _, _, _ = audit(rec)
        if not valid:
            continue
        i2, a2, b2 = build_pools(rec, by_ticker, corpus_rows, alias, rescues)
        i2["source"] = "old" if path == "c0_data.json" else "new"
        s2, _, _ = summarise(i2, a2, b2)
        if s2["reaches_10"] and s2["both_modes_present"]:
            key, matched = score(old, s2)
            rows.append((key, matched, s2))
rows.sort(key=lambda t: t[0], reverse=True)

out = {"old_id": 334, "old_ticker": old["ticker"],
       "old_strata": {k: old.get(k) for k in STRATA},
       "old_coverage": {"available_A": old["available_A"],
                        "available_B": old["available_B"],
                        "selected_A": old["selected_A"], "selected_B": old["selected_B"]},
       "reason": "0 Type-A candidates: the corpus holds no second analyst-rating "
                 "episode for TOL at least 90 days away, so the anchor fills all 10 "
                 "slots with absence evidence and violates selected_A >= 1",
       "top_candidates": [
           {"candidate_id": s["instance_id"], "ticker": s["ticker"],
            "source_subset": s["source"], "event_family": s["event_family"],
            "gold_label": s["gold"], "publication_period": s["period"],
            "news_volume_bucket": s["news_volume_bucket"],
            "selected_A": s["selected_A"], "selected_B": s["selected_B"],
            "available_A": s["available_A"], "available_B": s["available_B"],
            "matched_strata": m, "changed_strata": [k for k in STRATA if k not in m]}
           for _, m, s in rows[:5]], "applied": False}
json.dump(out, open("anchor334_replacement_screen.json", "w", encoding="utf-8",
                    newline="\n"), indent=2, ensure_ascii=False)
print("334 %s strata=%s | availA=%d availB=%d"
      % (old["ticker"], out["old_strata"], old["available_A"], old["available_B"]))
for c in out["top_candidates"]:
    print("  %-4d %-5s %dA+%dB matched=%s changed=%s"
          % (c["candidate_id"], c["ticker"], c["selected_A"], c["selected_B"],
             ",".join(c["matched_strata"]) or "-", ",".join(c["changed_strata"]) or "-"))
