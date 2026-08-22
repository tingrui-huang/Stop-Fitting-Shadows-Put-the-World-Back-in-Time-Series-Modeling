"""Final coverage-based curation: re-screen replacements, simulate, apply, build pools.

Selection uses ONLY corpus coverage and benchmark strata.  No model prediction
or C0 error is read anywhere in this file.

A replacement must be protocol-valid, reach exactly 10 distractors under the
adaptive policy, and instantiate BOTH paper failure modes (selected_A >= 1 and
selected_B >= 1) - a 10A+0B or 0A+10B anchor is rejected.

Writes coverage_replacement_rescreen.json, replacement_composition_simulation.json,
final50_paper_data.json, final50_paper_manifest.json, final50_review_pools.jsonl
and final50_review_pools_manifest.json.

Usage:  python final_curation.py [--apply]
"""

import argparse
import collections
import datetime as dt
import json

from audit_protocol import audit
from build_final_hard50 import load_json
from distractor_policy import (FAMILY, alias_map_from, index_by_ticker,
                               load_corpus_frame, type_a_candidates)
from news_corpus import event_type, parse_article, parse_utc
from paper_minimal_coverage import anchor_company_name, type_b_paper_minimal

LOCKED = "final50_locked_data.json"
LOCKED_MANIFEST = "final50_locked_manifest.json"
COVERAGE = "adaptive_distractor_coverage_paper_minimal.json"
POOL_FILES = ["c0_data.json", "hard50_data.json"]
AUTHORISED_FAILURES = [36, 78, 99, 136, 357, 394]
# Final, manually decided replacements (feasibility + non-degenerate A/B only).
FINAL_REPLACEMENTS = {36: 41, 78: 182, 99: 176, 136: 172, 357: 61, 394: 215, 481: 98}
TARGET_A, TARGET_B, N_TOTAL = 7, 3, 10
STRATA = ("source", "event_family", "gold", "period", "news_volume_bucket")
RESCUES_FILE = "typeA_manual_review_candidates.jsonl"


def volume_bucket(n):
    return "low(<10)" if n < 10 else "mid(10-40)" if n <= 40 else "high(>40)"


def period(stamp):
    d = parse_utc(stamp)
    return "%d-H%d" % (d.year, 1 if d.month <= 6 else 2)


def load_rescues():
    out = collections.defaultdict(set)
    try:
        for line in open(RESCUES_FILE, encoding="utf-8"):
            r = json.loads(line)
            if r.get("manual_semantic_status") == "RESCUED":
                out[r["anchor_instance_id"]].add(r["article_id"])
    except FileNotFoundError:
        pass
    return out


def build_pools(rec, by_ticker, corpus_rows, alias, rescues):
    """-> (anchor info, ranked A pool, ranked B pool) with full provenance."""
    ticker = rec["ticker"]
    title, text = parse_article(rec["gt_article_text"])
    gt_event = event_type(title, text)
    gt_dt = parse_utc(rec["gt_published_utc"])
    anchor = {"ticker": ticker, "gt_title": title, "gt_event": gt_event, "gt_dt": gt_dt}
    same = [a for a in by_ticker.get(ticker, []) if a["title"].strip() != title.strip()]

    a_pool = [dict(c, match_source=c["tier"]) for c in
              type_a_candidates(same, gt_event, gt_dt)]
    known = {c["article"]["article_id"] for c in a_pool}
    for art in same:
        if art["article_id"] in rescues.get(rec["instance_id"], set()) and \
                art["article_id"] not in known:
            off = (art["published_dt"] - gt_dt).total_seconds() / 86400.0
            if abs(off) >= 90:
                a_pool.append({"article": art, "tier": "manual_rescue",
                               "match_source": "manual_rescue", "offset_days": off,
                               "alias_direction": "historical" if off < 0 else "future"})
    rank = {"exact": 0, "family": 1, "manual_rescue": 2}
    a_pool.sort(key=lambda c: (rank[c["match_source"]], abs(c["offset_days"]),
                               c["article"]["article_id"]))

    company = anchor_company_name(title, ticker, alias)
    b_pool = type_b_paper_minimal(anchor, corpus_rows, alias, company)
    a_ids = {c["article"]["article_id"] for c in a_pool}
    b_pool = [c for c in b_pool if c["article"]["article_id"] not in a_ids]

    info = {
        "instance_id": rec["instance_id"], "ticker": ticker, "gold": rec["mcqa_answer"],
        "event_type": gt_event, "event_family": FAMILY.get(gt_event, "other"),
        "period": period(rec["gt_published_utc"]),
        "gt_title": title, "gt_published_utc": rec["gt_published_utc"],
        "corpus_depth": len(same), "news_volume_bucket": volume_bucket(len(same)),
        "anchor_company_used": company,
    }
    return info, a_pool, b_pool


def adaptive_select(a_pool, b_pool):
    sel_a, sel_b = a_pool[:TARGET_A], b_pool[:TARGET_B]
    need = N_TOTAL - len(sel_a) - len(sel_b)
    if need > 0:
        sel_b += b_pool[len(sel_b):len(sel_b) + need]
        need = N_TOTAL - len(sel_a) - len(sel_b)
    if need > 0:
        sel_a += a_pool[len(sel_a):len(sel_a) + need]
    return sel_a, sel_b


def summarise(info, a_pool, b_pool):
    sel_a, sel_b = adaptive_select(a_pool, b_pool)
    src = collections.Counter(c["match_source"] for c in sel_a)
    direction = collections.Counter(c["alias_direction"] for c in sel_a)
    tiers = collections.Counter(c["tier"] for c in sel_b)
    out = dict(info)
    out.update({
        "available_A": len(a_pool), "available_B": len(b_pool),
        "selected_A": len(sel_a), "selected_B": len(sel_b),
        "total_selected": len(sel_a) + len(sel_b),
        "reaches_10": len(sel_a) + len(sel_b) == N_TOTAL,
        "both_modes_present": len(sel_a) >= 1 and len(sel_b) >= 1,
        "A_exact": src.get("exact", 0), "A_family": src.get("family", 0),
        "A_manual_rescue": src.get("manual_rescue", 0),
        "A_historical": direction.get("historical", 0),
        "A_future": direction.get("future", 0),
        "B_same_ticker": tiers.get("B1", 0),
        "B_related_entity": tiers.get("B2", 0) + tiers.get("B3", 0),
    })
    return out, sel_a, sel_b


def score(old, cand):
    matched = [k for k in STRATA if cand.get(k) == old.get(k)]
    composition_gap = abs(cand["selected_A"] - TARGET_A) + abs(cand["selected_B"] - TARGET_B)
    balance = min(cand["selected_A"], cand["selected_B"])       # higher is better
    return (len(matched), -composition_gap, balance, -cand["instance_id"]), matched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true",
                    help="apply the manually decided FINAL_REPLACEMENTS map")
    ap.add_argument("--apply", action="store_true",
                    help="write final50_paper_data.json once the six replacements hold")
    args = ap.parse_args()

    df = load_corpus_frame()
    by_ticker = index_by_ticker(df)
    corpus_rows = [a for rows in by_ticker.values() for a in rows]
    alias = alias_map_from(df)
    rescues = load_rescues()

    locked = {r["instance_id"]: r for r in load_json(LOCKED)}
    src_map = {m["instance_id"]: m["selected_source"] for m in
               json.load(open(LOCKED_MANIFEST, encoding="utf-8"))["instances"]}
    coverage = {a["instance_id"]: a for a in
                json.load(open(COVERAGE, encoding="utf-8"))["anchors"]}
    unresolved_now = sorted(i for i, a in coverage.items() if not a["reaches_10"])

    # ---- current anchors ----------------------------------------------------
    current = {}
    for iid, rec in locked.items():
        info, a_pool, b_pool = build_pools(rec, by_ticker, corpus_rows, alias, rescues)
        info["source"] = src_map[iid]
        summary, sel_a, sel_b = summarise(info, a_pool, b_pool)
        current[iid] = {"summary": summary, "a_pool": a_pool, "b_pool": b_pool,
                        "sel_a": sel_a, "sel_b": sel_b}

    # ---- unused pool screening ---------------------------------------------
    candidates = []
    for path in POOL_FILES:
        for rec in load_json(path):
            if rec["instance_id"] in locked:
                continue
            valid, category, _, _ = audit(rec)
            if not valid:
                continue
            info, a_pool, b_pool = build_pools(rec, by_ticker, corpus_rows, alias, rescues)
            info["source"] = "old" if path == "c0_data.json" else "new"
            info["protocol_audit"] = category
            summary, sel_a, sel_b = summarise(info, a_pool, b_pool)
            candidates.append({"summary": summary, "a_pool": a_pool, "b_pool": b_pool})
    feasible = [c for c in candidates
                if c["summary"]["reaches_10"] and c["summary"]["both_modes_present"]]

    # ---- re-screen per failed anchor ---------------------------------------
    failures = AUTHORISED_FAILURES + [i for i in unresolved_now
                                      if i not in AUTHORISED_FAILURES]
    rescreen, chosen, taken = [], {}, set()
    for old_id in failures:
        old = current[old_id]["summary"]
        ranked = []
        for c in feasible:
            cand = c["summary"]
            if cand["instance_id"] in taken:
                continue
            key, matched = score(old, cand)
            ranked.append((key, matched, cand))
        ranked.sort(key=lambda t: t[0], reverse=True)
        top5 = []
        for key, matched, cand in ranked[:5]:
            top5.append({
                "candidate_id": cand["instance_id"], "ticker": cand["ticker"],
                "source_subset": cand["source"], "event_family": cand["event_family"],
                "event_type": cand["event_type"], "gold_label": cand["gold"],
                "publication_period": cand["period"],
                "corpus_depth": cand["corpus_depth"],
                "news_volume_bucket": cand["news_volume_bucket"],
                "available_A": cand["available_A"], "available_B": cand["available_B"],
                "selected_A": cand["selected_A"], "selected_B": cand["selected_B"],
                "A_exact": cand["A_exact"], "A_family": cand["A_family"],
                "A_manual_rescue": cand["A_manual_rescue"],
                "A_historical": cand["A_historical"], "A_future": cand["A_future"],
                "B_same_ticker": cand["B_same_ticker"],
                "B_related_entity": cand["B_related_entity"],
                "matched_strata": matched,
                "changed_strata": [k for k in STRATA if k not in matched],
                "rank_rationale": "%d/%d strata matched; composition %dA+%dB vs the "
                                  "%dA+%dB target; both modes present"
                                  % (len(matched), len(STRATA), cand["selected_A"],
                                     cand["selected_B"], TARGET_A, TARGET_B),
            })
        if top5:
            taken.add(top5[0]["candidate_id"])
            chosen[old_id] = top5[0]["candidate_id"]
        rescreen.append({
            "old_id": old_id, "old_ticker": old["ticker"],
            "authorised_by_brief": old_id in AUTHORISED_FAILURES,
            "old_strata": {k: old.get(k) for k in STRATA},
            "old_coverage": {"available_A": old["available_A"],
                             "available_B": old["available_B"],
                             "total_selected": old["total_selected"]},
            "reason_unusable": "reaches only %d of 10 distractors from the official "
                               "corpus (A=%d, B=%d)"
                               % (old["total_selected"], old["available_A"],
                                  old["available_B"]),
            "top_candidates": top5,
        })

    with open("coverage_replacement_rescreen.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump({
            "selection_inputs": "corpus coverage and benchmark strata only; no model "
                                "prediction or C0 error was consulted",
            "eligibility": ["protocol-valid MCQA",
                            "exactly 10 distractors under the adaptive policy",
                            "selected_A >= 1 and selected_B >= 1 (both failure modes)",
                            "10A+0B and 0A+10B rejected"],
            "preference_order": ["source subset", "event family", "gold label",
                                 "publication period", "news-volume bucket",
                                 "composition close to %dA+%dB" % (TARGET_A, TARGET_B),
                                 "A/B balance", "instance id"],
            "n_unused_pool_screened": len(candidates),
            "n_feasible": len(feasible),
            "authorised_failures": AUTHORISED_FAILURES,
            "unresolved_after_taxonomy_fix": unresolved_now,
            "anchors": rescreen,
        }, f, indent=2, ensure_ascii=False)

    # ---- composition simulation (authorised six only) ----------------------
    six = (dict(FINAL_REPLACEMENTS) if args.final
           else {old: chosen[old] for old in AUTHORISED_FAILURES if old in chosen})
    cand_by_id = {c["summary"]["instance_id"]: c for c in candidates}

    def profile(rows):
        def dist(key):
            return dict(sorted(collections.Counter(r[key] for r in rows).items()))
        return {"n": len(rows), "source_subset": dist("source"),
                "event_family": dist("event_family"),
                "earnings_vs_non_earnings": dict(sorted(collections.Counter(
                    "earnings" if r["event_type"] == "earnings" else "non_earnings"
                    for r in rows).items())),
                "gold_label": dist("gold"), "publication_period": dist("period"),
                "n_distinct_tickers": len({r["ticker"] for r in rows})}

    before_rows = [current[i]["summary"] for i in sorted(locked)]
    after_rows = [cand_by_id[six[i]]["summary"] if i in six else current[i]["summary"]
                  for i in sorted(locked)]
    before, after = profile(before_rows), profile(after_rows)

    shifts = []
    for key in ("source_subset", "event_family", "earnings_vs_non_earnings",
                "gold_label", "publication_period"):
        for k in set(before[key]) | set(after[key]):
            delta = after[key].get(k, 0) - before[key].get(k, 0)
            if abs(delta) >= 3:
                shifts.append({"dimension": key, "level": k,
                               "before": before[key].get(k, 0),
                               "after": after[key].get(k, 0), "delta": delta})

    with open("replacement_composition_simulation.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump({"status": "simulation - the benchmark was not modified here",
                   "replacements_simulated": six,
                   "before_locked50": before, "after_proposed_final50": after,
                   "material_shifts_ge_3": shifts,
                   "ticker_diversity": {"before": before["n_distinct_tickers"],
                                        "after": after["n_distinct_tickers"]}},
                  f, indent=2, ensure_ascii=False)

    # ---- apply --------------------------------------------------------------
    applied = False
    if (args.apply or args.final) and len(six) >= len(AUTHORISED_FAILURES):
        pool_recs = {}
        for path in POOL_FILES:
            for rec in load_json(path):
                pool_recs[rec["instance_id"]] = rec
        final_ids = [six.get(i, i) for i in sorted(locked)]
        data = [pool_recs[i] if i in six.values() else locked[i] for i in final_ids]
        with open("final50_paper_data.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(sorted(data, key=lambda r: r["instance_id"]), f, indent=2,
                      ensure_ascii=False)
        still_short = [i for i in unresolved_now if i not in AUTHORISED_FAILURES]
        manifest = {
            "mother_set": LOCKED,
            "policy": [
                "Seven anchors were replaced ONLY for intervention feasibility: the "
                "official MTBench finance_news corpus cannot instantiate the required "
                "10-distractor experiment for them under the corrected, mutually "
                "exclusive A/B taxonomy, or could do so only with a degenerate "
                "composition (1A+9B).",
                "All replacement decisions were finalised BEFORE any C1/C2/C3 "
                "inference was run.",
                "No downstream model prediction or error was consulted at any point; "
                "selection used corpus coverage and benchmark strata only.",
                "Replacements were made only for intervention feasibility and to "
                "avoid degenerate distractor compositions.",
                "This is the FINAL anchor freeze.",
                "No future anchor replacement is allowed on the basis of model "
                "results.",
            ],
            "replacement_rationale": {
                "36": "SNA has 3 corpus articles: 0 aliases and 0 absence evidence",
                "78": "VMC has 3 corpus articles (1A+3B); 182 LECO chosen over 142 WAL "
                      "(1A+9B) to keep a non-degenerate 5A+5B representation of both "
                      "failure modes",
                "99": "UMBF has 1 corpus article: no distractors of either type",
                "136": "TEL is a ticker collision - the corpus tags Telenor articles "
                       "with TEL and holds no TE Connectivity article",
                "357": "MMP reaches 3A+0B; 61 TSM chosen over 251 AAP (1A+9B) for a "
                       "7A+3B composition, and over 91 JPM by the deterministic "
                       "instance-id tie break after both tied on every stratum",
                "394": "CASY reaches 2A+6B, short by two",
                "481": "HRB reaches 3A+6B once the A/B taxonomy is mutually exclusive; "
                       "98 preserves ticker, source subset, event family, gold label "
                       "and news-volume bucket at 5A+5B",
            },
            "created_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "replacements": [{"old_id": o, "new_id": n,
                              "old_ticker": current[o]["summary"]["ticker"],
                              "new_ticker": cand_by_id[n]["summary"]["ticker"],
                              "reason": next(r["reason_unusable"] for r in rescreen
                                             if r["old_id"] == o),
                              "matched_strata": next(
                                  c["matched_strata"] for r in rescreen
                                  if r["old_id"] == o for c in r["top_candidates"]
                                  if c["candidate_id"] == n)}
                             for o, n in sorted(six.items())],
            "final50_ids": sorted(r["instance_id"] for r in data),
            "outstanding_infeasible_anchors": still_short,
            "outstanding_note": "these anchors are below 10 distractors under the "
                                "corrected A/B taxonomy but were NOT in the "
                                "authorised replacement list; they need a separate "
                                "decision" if still_short else "",
            "composition_before": before, "composition_after": after,
        }
        with open("final50_paper_manifest.json", "w", encoding="utf-8",
                  newline="\n") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        applied = True

    # ---- final review pools -------------------------------------------------
    if applied:
        final_data = load_json("final50_paper_data.json")
        pools, pool_summary = [], []
        for rec in final_data:
            iid = rec["instance_id"]
            if iid in current and iid in locked:
                a_pool, b_pool = current[iid]["a_pool"], current[iid]["b_pool"]
                info = current[iid]["summary"]
            else:
                c = cand_by_id[iid]
                a_pool, b_pool, info = c["a_pool"], c["b_pool"], c["summary"]
            sel_a, sel_b = adaptive_select(a_pool, b_pool)
            sel_ids = {c["article"]["article_id"] for c in sel_a + sel_b}
            for kind, pool, selected in (("temporal_aliasing", a_pool, sel_a),
                                         ("absence_evidence", b_pool, sel_b)):
                for rank_i, c in enumerate(pool[:max(len(selected) + 4, 8)], 1):
                    art = c["article"]
                    pools.append({
                        "anchor_instance_id": iid, "anchor_ticker": info["ticker"],
                        "gt_published_utc": info["gt_published_utc"],
                        "gt_event_type": info["event_type"],
                        "distractor_type": kind, "candidate_rank": rank_i,
                        "selected_for_final_10": art["article_id"] in sel_ids,
                        "distractor_article_id": art["article_id"],
                        "distractor_ticker": art["tickers"][0] if art["tickers"] else None,
                        "distractor_published_utc": art["published_utc"],
                        "distractor_title": art["title"],
                        "offset_days": round(c["offset_days"], 2),
                        "alias_direction": c.get("alias_direction", "n/a"),
                        "event_match_tier": c.get("match_source", "n/a"),
                        "distractor_event_type": art["event_type"],
                        "entity_relation": c.get("entity_relation"),
                        "entity_relation_evidence": c.get("entity_relation_evidence"),
                        "label_type_explicit": art["label_type"],
                        "provenance": {"dataset": "GGLabYale/MTBench_finance_news",
                                       "corpus_id": art["article_id"],
                                       "article_url": art["article_url"],
                                       "publisher": art["publisher"],
                                       "text_modified": False,
                                       "timestamp_modified": False},
                        "manual_review_required": True,
                    })
            pool_summary.append({k: info[k] for k in
                                 ("instance_id", "ticker", "event_type", "gold",
                                  "available_A", "available_B", "selected_A",
                                  "selected_B", "total_selected", "reaches_10",
                                  "both_modes_present", "A_exact", "A_family",
                                  "A_manual_rescue", "A_historical", "A_future",
                                  "B_same_ticker", "B_related_entity")})
        with open("final50_review_pools.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for r in pools:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open("final50_review_pools_manifest.json", "w", encoding="utf-8",
                  newline="\n") as f:
            json.dump({"status": "REVIEW POOLS - the final 10 per anchor are marked "
                                 "selected_for_final_10 but not locked",
                       "policy": "adaptive %dA+%dB target with fill; total 10; both "
                                 "modes required" % (TARGET_A, TARGET_B),
                       "n_candidates": len(pools),
                       "n_anchors": len(pool_summary),
                       "n_anchors_reaching_10": sum(1 for a in pool_summary
                                                    if a["reaches_10"]),
                       "anchors": pool_summary}, f, indent=2, ensure_ascii=False)

    print("feasible replacement candidates: %d of %d protocol-valid unused anchors"
          % (len(feasible), len(candidates)))
    print("unresolved after taxonomy fix: %s" % unresolved_now)
    for r in rescreen:
        best = r["top_candidates"][0] if r["top_candidates"] else None
        print("  %-4d %-5s%s -> %s"
              % (r["old_id"], r["old_ticker"],
                 "" if r["authorised_by_brief"] else " (NOT in the authorised six)",
                 "none" if not best else
                 "%d %s (%dA+%dB, matched %s)" % (best["candidate_id"], best["ticker"],
                                                  best["selected_A"], best["selected_B"],
                                                  ",".join(best["matched_strata"]) or "-")))
    print("material composition shifts (>=3): %s" % (shifts or "none"))
    print("final50_paper_data.json created: %s" % applied)


if __name__ == "__main__":
    main()
