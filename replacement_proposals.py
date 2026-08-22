"""Replacement PROPOSALS for anchors that cannot reach 10 distractors. Not applied.

For every anchor still unresolved under the paper-minimal policy, unused
candidates from the original 100-anchor pool are screened for
  * protocol validity (the same audit that locked the 50), and
  * enough official-corpus distractors to reach 10 under the same adaptive
    policy (7A+3B target, fill either way),
then matched on source subset, event family, gold label, publication period and
ticker news-volume bucket.  Model predictions are never consulted.

Writes coverage_based_replacement_proposals.json.

Usage:  python replacement_proposals.py
"""

import collections
import json

from audit_protocol import audit
from build_final_hard50 import load_json
from distractor_policy import (FAMILY, alias_map_from, index_by_ticker,
                               load_corpus_frame, type_a_candidates)
from news_corpus import event_type, parse_article, parse_utc
from paper_minimal_coverage import anchor_company_name, type_b_paper_minimal

LOCKED = "final50_locked_data.json"
LOCKED_MANIFEST = "final50_locked_manifest.json"
POOL = ["c0_data.json", "hard50_data.json"]
COVERAGE = "adaptive_distractor_coverage_paper_minimal.json"
TARGET_A, TARGET_B, N_TOTAL = 7, 3, 10


def volume_bucket(n):
    return "low(<10)" if n < 10 else "mid(10-40)" if n <= 40 else "high(>40)"


def period(stamp):
    d = parse_utc(stamp)
    return "%d-H%d" % (d.year, 1 if d.month <= 6 else 2)


def describe(rec, by_ticker, alias, corpus_rows, with_coverage=True):
    title, text = parse_article(rec["gt_article_text"])
    gt_event = event_type(title, text)
    anchor = {"ticker": rec["ticker"], "gt_title": title, "gt_event": gt_event,
              "gt_dt": parse_utc(rec["gt_published_utc"])}
    same = [a for a in by_ticker.get(rec["ticker"], [])
            if a["title"].strip() != title.strip()]
    info = {
        "instance_id": rec["instance_id"], "ticker": rec["ticker"],
        "gold": rec["mcqa_answer"], "event_type": gt_event,
        "event_family": FAMILY.get(gt_event, "other"),
        "period": period(rec["gt_published_utc"]),
        "same_ticker_articles": len(same),
        "news_volume_bucket": volume_bucket(len(same)),
    }
    if with_coverage:
        a_pool = type_a_candidates(same, gt_event, anchor["gt_dt"])
        company = anchor_company_name(title, rec["ticker"], alias)
        b_pool = type_b_paper_minimal(anchor, corpus_rows, alias, company)
        a_ids = {c["article"]["article_id"] for c in a_pool}
        b_pool = [c for c in b_pool if c["article"]["article_id"] not in a_ids]
        sel_a, sel_b = a_pool[:TARGET_A], b_pool[:TARGET_B]
        need = N_TOTAL - len(sel_a) - len(sel_b)
        if need > 0:
            sel_b += b_pool[len(sel_b):len(sel_b) + need]
            need = N_TOTAL - len(sel_a) - len(sel_b)
        if need > 0:
            sel_a += a_pool[len(sel_a):len(sel_a) + need]
        info.update({"n_A_available": len(a_pool), "n_B_available": len(b_pool),
                     "n_A_selected": len(sel_a), "n_B_selected": len(sel_b),
                     "reaches_10": len(sel_a) + len(sel_b) == N_TOTAL})
    return info


def main():
    df = load_corpus_frame()
    by_ticker = index_by_ticker(df)
    corpus_rows = [a for rows in by_ticker.values() for a in rows]
    alias = alias_map_from(df)

    locked = {r["instance_id"]: r for r in load_json(LOCKED)}
    src = {m["instance_id"]: m["selected_source"] for m in
           json.load(open(LOCKED_MANIFEST, encoding="utf-8"))["instances"]}
    coverage = json.load(open(COVERAGE, encoding="utf-8"))
    unresolved = coverage["unresolved_ids"]
    cov_by_id = {a["instance_id"]: a for a in coverage["anchors"]}

    pool = {}
    for path in POOL:
        for rec in load_json(path):
            if rec["instance_id"] not in locked:
                pool[rec["instance_id"]] = (path, rec)

    # screen the unused pool: protocol-valid AND able to reach 10
    candidates = []
    for iid, (path, rec) in sorted(pool.items()):
        valid, category, _, _ = audit(rec)
        if not valid:
            continue
        info = describe(rec, by_ticker, alias, corpus_rows)
        info["source"] = "old" if path == "c0_data.json" else "new"
        info["protocol_audit"] = category
        candidates.append(info)
    usable = [c for c in candidates if c["reaches_10"]]

    proposals, taken = [], set()
    for old_id in unresolved:
        old = describe(locked[old_id], by_ticker, alias, corpus_rows, with_coverage=False)
        old["source"] = src[old_id]
        cov = cov_by_id[old_id]
        strata = ("source", "event_family", "gold", "period", "news_volume_bucket")

        scored = []
        for c in usable:
            if c["instance_id"] in taken:
                continue
            matched = [k for k in strata if c.get(k) == old.get(k)]
            scored.append((len(matched), -abs(c["n_A_available"] - TARGET_A),
                           -c["instance_id"], c, matched))
        scored.sort(reverse=True)
        if not scored:
            proposals.append({"old_id": old_id, "proposed_new_id": None,
                              "reason": "no unused pool candidate is both "
                                        "protocol-valid and able to reach 10"})
            continue
        _, _, _, best, matched = scored[0]
        taken.add(best["instance_id"])
        proposals.append({
            "old_id": old_id,
            "old_ticker": old["ticker"],
            "old_strata": {k: old.get(k) for k in strata},
            "old_coverage": {"n_A_available": cov["n_A_available"],
                             "n_B_available": cov["n_B_available"],
                             "n_total_selected": cov["n_total_selected"]},
            "reason_old_anchor_unusable": cov.get("failure_class") or
                "reaches only %d of 10 distractors from the official corpus "
                "(A=%d, B=%d)" % (cov["n_total_selected"], cov["n_A_available"],
                                  cov["n_B_available"]),
            "proposed_new_id": best["instance_id"],
            "new_ticker": best["ticker"],
            "new_strata": {k: best.get(k) for k in strata},
            "new_coverage": {"n_A_available": best["n_A_available"],
                             "n_B_available": best["n_B_available"],
                             "n_A_selected": best["n_A_selected"],
                             "n_B_selected": best["n_B_selected"],
                             "reaches_10": best["reaches_10"]},
            "matched_strata": matched,
            "changed_strata": [k for k in strata if k not in matched],
            "selection": "highest stratum match among protocol-valid unused pool "
                         "candidates that reach 10; ties broken by A-pool size then "
                         "instance id. No model prediction was consulted.",
            "applied": False,
        })

    summary = {
        "status": "PROPOSALS ONLY - nothing was applied and final50_locked_data.json "
                  "is unchanged",
        "policy": "adaptive 7A+3B with paper-minimal Type B",
        "n_unused_pool": len(pool),
        "n_pool_protocol_valid": len(candidates),
        "n_pool_reaching_10": len(usable),
        "unresolved_anchors": unresolved,
        "proposals": proposals,
    }
    with open("coverage_based_replacement_proposals.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("unused pool: %d | protocol-valid: %d | reaching 10: %d"
          % (len(pool), len(candidates), len(usable)))
    for p in proposals:
        if p["proposed_new_id"] is None:
            print("  %-4d -> none" % p["old_id"])
            continue
        print("  %-4d %-5s -> %-4d %-5s | matched %s | changed %s | new A/B %d/%d"
              % (p["old_id"], p["old_ticker"], p["proposed_new_id"], p["new_ticker"],
                 ",".join(p["matched_strata"]) or "-",
                 ",".join(p["changed_strata"]) or "-",
                 p["new_coverage"]["n_A_available"], p["new_coverage"]["n_B_available"]))
    print("wrote coverage_based_replacement_proposals.json")


if __name__ == "__main__":
    main()
