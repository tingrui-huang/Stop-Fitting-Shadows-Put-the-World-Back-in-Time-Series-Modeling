"""Check the cross-condition invariance requirements on the built prompt files.

Run after build_conditions.py.  Every check re-derives its claim from the
rendered prompts themselves (not from the builder's bookkeeping), so it catches
a builder bug rather than restating it.

Usage:  python verify_conditions.py [--out out]
"""

import argparse
import json
import os
import re
import sys

from temporal_mask import mask_temporal

FAILURES = []


def check(name, ok, detail=""):
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  <- " + detail))
    if not ok:
        FAILURES.append(name)


def load(out, cond):
    path = os.path.join(out, "%s.jsonl" % cond)
    with open(path, encoding="utf-8") as f:
        return {json.loads(l)["instance_id"]: json.loads(l) for l in f}


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
    """-> list of (published_or_None, title, content)."""
    out = []
    for chunk in re.split(r"\n\nArticle \d+\n", "\n\n" + news)[1:]:
        pub = None
        m = re.match(r"Published: (.+)\n", chunk)
        if m:
            pub, chunk = m.group(1), chunk[m.end():]
        title, _, content = chunk.partition("\n")
        assert title.startswith("Title: "), title[:60]
        content = content[len("Content:\n"):]
        out.append((pub, title[len("Title: "):], content))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    C = {c: load(args.out, c) for c in ("c0", "c1", "c2", "c3")}
    ids = sorted(C["c0"])
    meta = json.load(open(os.path.join(args.out, "manifest.json"), encoding="utf-8"))
    man = {m["instance_id"]: m for m in meta["instances"]}
    mask_q = meta.get("mask_question", False)
    mode = meta.get("distractor_mode", "legacy")
    print("distractor mode: %s" % mode)
    print("")

    check("all conditions cover the same instances",
          all(sorted(C[c]) == ids for c in C))

    art = {c: {i: split_articles(news_block(C[c][i])) for i in ids} for c in C}

    # ---- article counts ---------------------------------------------------
    check("C0 has exactly 1 article", all(len(art["c0"][i]) == 1 for i in ids))
    check("C1 has 11 articles (GT + 10 distractors)",
          all(len(art["c1"][i]) == 11 for i in ids))
    check("C2 has 11 articles", all(len(art["c2"][i]) == 11 for i in ids))
    check("C3 has 10 articles", all(len(art["c3"][i]) == 10 for i in ids))

    # ---- invariants across conditions -------------------------------------
    if mask_q:
        check("question identical in C0/C1/C3, temporally masked in C2",
              all(len({question_block(C[c][i]) for c in ("c0", "c1", "c3")}) == 1
                  and question_block(C["c2"][i])
                  == mask_temporal(question_block(C["c1"][i]))[0] for i in ids))
    else:
        check("question + options identical across C0-C3",
              all(len({question_block(C[c][i]) for c in C}) == 1 for i in ids))
    check("ticker identical across C0-C3",
          all(len({C[c][i]["ticker"] for c in C}) == 1 for i in ids))
    check("gold answer identical across C0-C3",
          all(len({C[c][i]["answer"] for c in C}) == 1 for i in ids))

    check("TS block identical in C0/C1/C3 (timestamped)",
          all(ts_block(C["c0"][i]) == ts_block(C["c1"][i]) == ts_block(C["c3"][i])
              for i in ids))

    def values(block):
        return [ln.split(" | ")[1] for ln in block.splitlines()]

    check("C2 TS values equal C1 TS values in the same order",
          all(values(ts_block(C["c2"][i])) == values(ts_block(C["c1"][i])) for i in ids))
    check("C2 TS uses ordinal positions only",
          all(all(ln.startswith("Position %d | " % (k + 1))
                  for k, ln in enumerate(ts_block(C["c2"][i]).splitlines()))
              for i in ids))

    # ---- C1 vs C2: the primary comparison ---------------------------------
    check("C1/C2 article ids and order identical",
          all(C["c1"][i]["article_order"] == C["c2"][i]["article_order"] for i in ids))
    check("C1/C2 differ only by deterministic temporal masking",
          all(all((mask_temporal(t)[0], mask_temporal(c)[0]) == (t2, c2)
                  for (_, t, c), (_, t2, c2) in zip(art["c1"][i], art["c2"][i]))
              for i in ids),
          "re-masking a C1 article must reproduce the C2 article byte for byte")
    check("C2 shows no publication timestamps",
          all(all(p is None for p, _, _ in art["c2"][i]) for i in ids))
    check("C2 news context has no bare 4-digit year / ISO date / Q-number",
          all(not re.search(r"\b(?:19|20)\d{2}\b|\bQ[1-4]\b", news_block(C["c2"][i]))
              for i in ids))

    # ---- C1 vs C3 ---------------------------------------------------------
    ok, why = True, ""
    for i in ids:
        c1 = [(p, t) for p, t, _ in art["c1"][i]]
        c3 = [(p, t) for p, t, _ in art["c3"][i]]
        gt_title = art["c0"][i][0][1]
        expected = [x for x in c1 if x[1] != gt_title]
        if c3 != expected:
            ok, why = False, "instance %d" % i
            break
    check("C3 = C1 minus the GT article, distractor order preserved", ok, why)
    check("C3 contains no GT article",
          all(art["c0"][i][0][1] not in [t for _, t, _ in art["c3"][i]] for i in ids))
    check("C0 article is the GT article with its real timestamp",
          all(art["c0"][i][0][0] == man[i]["gt_published_utc"] for i in ids))

    # ---- distractor sanity -------------------------------------------------
    if mode == "legacy":
        check("legacy: no distractor shares the instance's ticker",
              all(C["c1"][i]["ticker"] not in
                  {man[j]["ticker"] for j in C["c3"][i]["article_order"]} for i in ids))
    else:
        d = {i: man[i]["distractors"] for i in ids}
        check("reviewed: exactly 10 approved distractors per anchor",
              all(len(d[i]) == 10 for i in ids),
              str({i: len(d[i]) for i in ids if len(d[i]) != 10}))
        check("reviewed: no duplicate distractor id within an anchor",
              all(len({x["article_id"] for x in d[i]}) == len(d[i]) for i in ids))
        check("reviewed: the GT article never appears as a distractor",
              all(C["c1"][i]["gt_source_id"] not in
                  {x["article_id"] for x in d[i]} for i in ids))
        check("reviewed: every distractor is a known type",
              all(x["distractor_type"] in ("temporal_aliasing", "absence_evidence")
                  for i in ids for x in d[i]))
        alias = {i: [x for x in d[i] if x["distractor_type"] == "temporal_aliasing"]
                 for i in ids}
        check("reviewed: type A distractors share the anchor ticker",
              all(x["ticker"] == C["c1"][i]["ticker"] for i in ids for x in alias[i]),
              str([(i, x["article_id"], x["ticker"]) for i in ids for x in alias[i]
                   if x["ticker"] != C["c1"][i]["ticker"]][:3]))
        check("reviewed: type A abs(offset_days) >= 90",
              all(abs(x["offset_days"]) >= 90 for i in ids for x in alias[i]),
              str([(i, x["article_id"], x["offset_days"]) for i in ids
                   for x in alias[i] if abs(x["offset_days"]) < 90][:3]))
        check("reviewed: type A event_match_tier is exact, family or manual_rescue",
              all(x["event_match_tier"] in ("exact", "family", "manual_rescue")
                  for i in ids for x in alias[i]))
        check("reviewed: C3 carries exactly the same 10 distractors",
              all(sorted(map(str, C["c3"][i]["article_order"]))
                  == sorted(str(x["article_id"]) for x in d[i]) for i in ids))
        check("reviewed: every distractor carries provenance",
              all(x.get("provenance") for i in ids for x in d[i]))
        check("reviewed: mask_question is false (MCQA wording held fixed)",
              mask_q is False,
              "the paper protocol keeps the original question and answer options "
              "byte-identical across C0-C3; this build masked them")
    check("no duplicate articles inside an instance's pool",
          all(len(set(map(str, C["c1"][i]["article_order"]))) == 11 for i in ids))
    check("GT position is not fixed across instances",
          len({C["c1"][i]["gt_position"] for i in ids}) > 5)

    # ---- report ------------------------------------------------------------
    lens = {c: sorted(len(C[c][i]["prompt"]) for i in ids) for c in C}
    print("\nprompt chars (median / max): " + ", ".join(
        "%s %d / %d" % (c.upper(), lens[c][len(ids) // 2], lens[c][-1]) for c in
        ("c0", "c1", "c2", "c3")))
    print("temporal masks per C2 instance: min %d, median %d, max %d" % (
        min(m["n_temporal_masks_c2"] for m in man.values()),
        sorted(m["n_temporal_masks_c2"] for m in man.values())[len(ids) // 2],
        max(m["n_temporal_masks_c2"] for m in man.values())))

    print("\n%d/%d checks passed" % (23 - len(FAILURES), 23) if False else "")
    if FAILURES:
        print("FAILED: %s" % ", ".join(FAILURES))
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
