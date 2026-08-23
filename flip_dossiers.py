"""TASKS 2, 5, 6 - build the mechanical dossier for every C1<->C2 discordant case.

Read-only with respect to the benchmark: it reads the frozen rendered prompts,
the frozen result files and the frozen pool metadata, and writes only
results/c1_c2_flip_cases.jsonl plus a scratch dump for manual reading.

Nothing here interprets the model; interpretation (tasks 3, 4, 7) is done by
hand on top of this output.

Usage:  python flip_dossiers.py
"""

import difflib
import json
import re

from temporal_mask import RULES, mask_temporal

OUT_CASES = "results/c1_c2_flip_cases.jsonl"
OUT_DUMP = "results/_flip_dossier_dump.json"

MASK_TOKENS = ("[DATE]", "[YEAR]", "[QUARTER]")


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------
def jsonl(path, key="instance_id"):
    with open(path, encoding="utf-8") as f:
        return {json.loads(l)[key]: json.loads(l) for l in f if l.strip()}


def jsonl_rows(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


# --------------------------------------------------------------------------
# prompt structure (same parsing as verify_conditions.py)
# --------------------------------------------------------------------------
def section(prompt, start, end=None):
    i = prompt.index(start) + len(start)
    j = prompt.index(end, i) if end else len(prompt)
    return prompt[i:j].strip("\n")


def ts_block(rec):
    return section(rec["prompt"], "\nTicker: %s\n" % rec["ticker"], "\n\nNews Context\n")


def news_block(rec):
    return section(rec["prompt"], "\n\nNews Context\n", "\n\nQuestion\n")


def question_block(rec):
    return section(rec["prompt"], "\n\nQuestion\n", "\n\nSelect the single best answer.")


def split_articles(news):
    """-> list of dict(published, title, content)."""
    out = []
    for chunk in re.split(r"\n\nArticle \d+\n", "\n\n" + news)[1:]:
        pub = None
        m = re.match(r"Published: (.+)\n", chunk)
        if m:
            pub, chunk = m.group(1), chunk[m.end():]
        title, _, content = chunk.partition("\n")
        assert title.startswith("Title: "), title[:60]
        content = content[len("Content:\n"):]
        out.append({"published": pub, "title": title[len("Title: "):],
                    "content": content})
    return out


# --------------------------------------------------------------------------
# task 6 - masking side-effect audit
# --------------------------------------------------------------------------
TOKEN_RE = re.compile(r"\s+|\w+|\W")


def tokenize(text):
    return TOKEN_RE.findall(text)


def is_temporal_span(span):
    """True if the whole deleted span is consumed by the masker's own rules."""
    masked, n = mask_temporal(span)
    if n == 0:
        return False
    stripped = masked
    for tok in MASK_TOKENS:
        stripped = stripped.replace(tok, "")
    # everything that survives must be punctuation/whitespace glue
    return re.fullmatch(r"[\s,.\-/']*", stripped) is not None


NUMERIC_CONTEXT = re.compile(r"[\d.,]")


def numeric_context(text, i, j):
    before = text[max(0, i - 1):i]
    after = text[j:j + 2]
    return bool(NUMERIC_CONTEXT.fullmatch(before or " ")) or \
        bool(re.match(r"\.\d", after))


def merged_opcodes(a, b, opcodes):
    """Join changes separated only by whitespace.

    "First Quarter 2022" -> "[QUARTER] [YEAR]" is one temporal replacement, but
    the token aligner splits it at the shared word "Quarter"; merging across a
    whitespace-only equal run restores the real unit of change.
    """
    out, cur = [], None
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            if cur and "".join(a[i1:i2]).strip():
                out.append(cur)
                cur = None
            continue
        cur = (cur[0], i2, cur[2], j2) if cur else (i1, i2, j1, j2)
    if cur:
        out.append(cur)
    return out


def diff_audit(c1_text, c2_text, where):
    """Every change from C1 to C2 must be temporal-span -> mask token."""
    a, b = tokenize(c1_text), tokenize(c2_text)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    changes, flags = [], []
    for i1, i2, j1, j2 in merged_opcodes(a, b, sm.get_opcodes()):
        tag = "replace"
        removed = "".join(a[i1:i2])
        inserted = "".join(b[j1:j2])
        ins_core = inserted
        for tok in MASK_TOKENS:
            ins_core = ins_core.replace(tok, "")
        rec = {"where": where, "op": tag, "removed": removed,
               "inserted": inserted}
        ok_insert = re.fullmatch(r"[\s,.\-/']*", ins_core) is not None and \
            any(t in inserted for t in MASK_TOKENS)
        ok_remove = is_temporal_span(removed)
        if not (ok_insert and ok_remove):
            rec["flag"] = ("inserted text is not purely mask tokens"
                           if not ok_insert else
                           "removed text is not a pure temporal expression")
            flags.append(rec)
        else:
            char_i = len("".join(a[:i1]))
            if re.fullmatch(r"(?:19|20)\d{2}", removed.strip()) and \
                    numeric_context(c1_text, char_i, char_i + len(removed)):
                rec["flag"] = ("4-digit token masked as a year while sitting in a "
                               "numeric context - possible non-date number")
                flags.append(rec)
        changes.append(rec)
    return changes, flags


# --------------------------------------------------------------------------
def main():
    data = {r["instance_id"]: r for r in
            json.load(open("final50_paper_data.json", encoding="utf-8"))}
    man = {m["instance_id"]: m for m in
           json.load(open("out_paper50_reviewed/manifest.json",
                          encoding="utf-8"))["instances"]}
    pool_rows = jsonl_rows("final50_review_pools.jsonl")
    pool = {}
    for r in pool_rows:
        pool.setdefault(r["anchor_instance_id"], {})[r["distractor_article_id"]] = r
    pools_man = {a["instance_id"]: a for a in
                 json.load(open("final50_review_pools_manifest.json",
                                encoding="utf-8"))["anchors"]}

    c1r = jsonl("out_paper50_reviewed/c1.jsonl")
    c2r = jsonl("out_paper50_reviewed/c2.jsonl")
    c1m = jsonl("results/paper50_c1_sonnet5.jsonl")
    c2m = jsonl("results/paper50_c2_sonnet5.jsonl")

    table = json.load(open("results/c1_c2_transition_table.json", encoding="utf-8"))
    discordant = [r for r in table["instances"]
                  if r["group"] in ("C1_CORRECT_C2_WRONG", "C1_WRONG_C2_CORRECT")]

    cases = []
    for row in discordant:
        i = row["instance_id"]
        d, m = data[i], man[i]
        r1, r2 = c1r[i], c2r[i]
        a1 = split_articles(news_block(r1))
        a2 = split_articles(news_block(r2))
        dmeta = {x["article_id"]: x for x in m["distractors"]}

        # ---- evidence pool in rendered order -----------------------------
        pool_out = []
        for pos, (aid, art1, art2) in enumerate(zip(m["article_order"], a1, a2), 1):
            is_gt = (aid == m["instance_id"]) or (pos == m["gt_position"])
            if is_gt:
                entry = {
                    "position": pos, "article_id": aid, "role": "GT",
                    "ticker": d["ticker"],
                    "published_utc": art1["published"],
                    "title": art1["title"],
                    "event_type": pools_man[i]["event_type"],
                    "event_match_tier": None, "offset_days": 0.0,
                    "alias_direction": None, "type_b_relation_tier": None,
                }
            else:
                md = dmeta[aid]
                pr = pool.get(i, {}).get(aid, {})
                role = ("TYPE_A_TEMPORAL_ALIAS"
                        if md["distractor_type"] == "temporal_aliasing"
                        else "TYPE_B_ABSENCE")
                entry = {
                    "position": pos, "article_id": aid, "role": role,
                    "ticker": md["ticker"],
                    "published_utc": art1["published"],
                    "title": art1["title"],
                    "event_type": pr.get("distractor_event_type"),
                    "event_match_tier": (md["event_match_tier"]
                                         if role.startswith("TYPE_A") else None),
                    "offset_days": md["offset_days"],
                    "alias_direction": (md["alias_direction"]
                                        if role.startswith("TYPE_A") else None),
                    "type_b_relation_tier": (pr.get("entity_relation")
                                             if role == "TYPE_B_ABSENCE" else None),
                    "type_b_relation_evidence": (pr.get("entity_relation_evidence")
                                                 if role == "TYPE_B_ABSENCE" else None),
                }
            entry["published_utc_c1"] = art1["published"]
            entry["published_utc_c2"] = art2["published"]
            entry["n_temporal_masks"] = mask_temporal(
                art1["title"] + "\n" + art1["content"])[1]
            entry["title_c2"] = art2["title"]
            pool_out.append(entry)

        by_pos = {e["position"]: e for e in pool_out}

        def cited(rec):
            out = []
            for n in rec.get("evidence_articles") or []:
                e = by_pos.get(n)
                out.append({"cited_article_number": n,
                            "resolves_to": None if e is None else {
                                "position": e["position"],
                                "article_id": e["article_id"],
                                "role": e["role"],
                                "title": e["title"],
                                "published_utc": e["published_utc"],
                                "offset_days": e["offset_days"],
                                "alias_direction": e["alias_direction"],
                                "event_match_tier": e["event_match_tier"],
                                "type_b_relation_tier": e.get("type_b_relation_tier"),
                            }})
            return out

        # ---- C1 vs C2 input difference ------------------------------------
        ts1, ts2 = ts_block(r1), ts_block(r2)
        vals = lambda blk: [ln.split(" | ")[1] for ln in blk.splitlines()]
        all_changes, all_flags = [], []
        for pos, (art1, art2) in enumerate(zip(a1, a2), 1):
            for field in ("title", "content"):
                ch, fl = diff_audit(art1[field], art2[field],
                                    "article %d %s" % (pos, field))
                all_changes += ch
                all_flags += fl
        qch, qfl = diff_audit(question_block(r1), question_block(r2), "question")
        all_changes += qch
        all_flags += qfl

        invariance = {
            "question_and_options_identical":
                question_block(r1) == question_block(r2),
            "ticker_identical": r1["ticker"] == r2["ticker"],
            "gold_answer_identical": r1["answer"] == r2["answer"],
            "ts_numeric_values_identical": vals(ts1) == vals(ts2),
            "ts_n_points_identical": len(ts1.splitlines()) == len(ts2.splitlines()),
            "article_identities_and_order_identical":
                r1["article_order"] == r2["article_order"],
            "n_articles_identical": len(a1) == len(a2),
            "c2_reproduces_c1_under_the_masker":
                all((mask_temporal(x["title"])[0], mask_temporal(x["content"])[0])
                    == (y["title"], y["content"]) for x, y in zip(a1, a2)),
            "c1_shows_publication_timestamps":
                all(x["published"] for x in a1),
            "c2_shows_no_publication_timestamps":
                all(x["published"] is None for x in a2),
            "c1_ts_shows_absolute_timestamps":
                not ts1.startswith("Position 1 | "),
            "c2_ts_shows_ordinal_positions_only":
                all(ln.startswith("Position %d | " % (k + 1))
                    for k, ln in enumerate(ts2.splitlines())),
        }

        # ---- task 5 - type A / type B exposure -----------------------------
        typea = [e for e in pool_out if e["role"] == "TYPE_A_TEMPORAL_ALIAS"]
        typeb = [e for e in pool_out if e["role"] == "TYPE_B_ABSENCE"]
        offs = sorted(abs(e["offset_days"]) for e in typea)
        exposure = {
            "n_type_a": len(typea), "n_type_b": len(typeb),
            "type_a_tiers": {t: sum(1 for e in typea if e["event_match_tier"] == t)
                             for t in ("exact", "family", "manual_rescue")},
            "type_a_direction": {
                dd: sum(1 for e in typea if e["alias_direction"] == dd)
                for dd in ("historical", "future")},
            "type_a_abs_offset_days": {
                "min": round(offs[0], 2) if offs else None,
                "median": round(offs[len(offs) // 2], 2) if offs else None,
                "max": round(offs[-1], 2) if offs else None},
            "type_b_relation_tiers": {},
        }
        for e in typeb:
            k = str(e.get("type_b_relation_tier"))
            exposure["type_b_relation_tiers"][k] = \
                exposure["type_b_relation_tiers"].get(k, 0) + 1

        q = d["mcqa_question"]
        cases.append({
            "instance_id": i,
            "transition": row["group"],
            "task": {
                "ticker": d["ticker"],
                "gold_answer": d["mcqa_answer"],
                "question_and_options": q,
                "gt_published_utc": d["gt_published_utc"],
                "gt_event_type": pools_man[i]["event_type"],
                "gt_position_in_pool": m["gt_position"],
                "n_ts_points": len(d["ts_values"]),
            },
            "c1": {
                "prediction": c1m[i]["prediction"], "correct": c1m[i]["correct"],
                "confidence": c1m[i]["confidence"], "rationale": c1m[i]["rationale"],
                "evidence_articles": c1m[i]["evidence_articles"],
                "evidence_resolved": cited(c1m[i]),
            },
            "c2": {
                "prediction": c2m[i]["prediction"], "correct": c2m[i]["correct"],
                "confidence": c2m[i]["confidence"], "rationale": c2m[i]["rationale"],
                "evidence_articles": c2m[i]["evidence_articles"],
                "evidence_resolved": cited(c2m[i]),
            },
            "evidence_pool": pool_out,
            "c1_vs_c2_input_difference": {
                "ts_c1_first_two_lines": ts1.splitlines()[:2],
                "ts_c2_first_two_lines": ts2.splitlines()[:2],
                "n_article_publication_timestamps_removed":
                    sum(1 for x in a1 if x["published"]),
                "n_in_article_temporal_masks":
                    sum(e["n_temporal_masks"] for e in pool_out),
                "unchanged": invariance,
            },
            "masking_side_effect_audit": {
                "n_textual_changes": len(all_changes),
                "n_flagged": len(all_flags),
                "flagged": all_flags,
                "sample_changes": all_changes[:12],
            },
            "type_a_exposure": exposure,
        })

    with open(OUT_CASES, "w", encoding="utf-8", newline="\n") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with open(OUT_DUMP, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)

    print("discordant cases: %s" % [c["instance_id"] for c in cases])
    for c in cases:
        inv = c["c1_vs_c2_input_difference"]["unchanged"]
        bad = [k for k, v in inv.items() if not v]
        print("\n%-4d %-5s %s  gold=%s  C1=%s%s  C2=%s%s"
              % (c["instance_id"], c["task"]["ticker"], c["transition"],
                 c["task"]["gold_answer"], c["c1"]["prediction"],
                 "*" if c["c1"]["correct"] else "", c["c2"]["prediction"],
                 "*" if c["c2"]["correct"] else ""))
        print("     A/B = %d/%d   tiers %s   dir %s   |offset| %s"
              % (c["type_a_exposure"]["n_type_a"], c["type_a_exposure"]["n_type_b"],
                 c["type_a_exposure"]["type_a_tiers"],
                 c["type_a_exposure"]["type_a_direction"],
                 c["type_a_exposure"]["type_a_abs_offset_days"]))
        print("     invariance failures: %s" % (bad or "none"))
        print("     masking changes %d, flagged %d"
              % (c["masking_side_effect_audit"]["n_textual_changes"],
                 c["masking_side_effect_audit"]["n_flagged"]))
        print("     C1 cited %s -> %s"
              % (c["c1"]["evidence_articles"],
                 [e["resolves_to"]["role"] if e["resolves_to"] else "OUT_OF_RANGE"
                  for e in c["c1"]["evidence_resolved"]]))
        print("     C2 cited %s -> %s"
              % (c["c2"]["evidence_articles"],
                 [e["resolves_to"]["role"] if e["resolves_to"] else "OUT_OF_RANGE"
                  for e in c["c2"]["evidence_resolved"]]))
    print("\nwrote %s and %s" % (OUT_CASES, OUT_DUMP))


if __name__ == "__main__":
    main()
