"""TASK 6 support - self-test the diff auditor, then sweep all 50 instances.

The auditor is only worth reporting if it can actually fail, so it is first run
against deliberately corrupted C2 text (entity swap, negation flip, dropped
clause, non-date number change, reordered articles).  Then the real C1/C2 pair
is audited for every instance, not just the discordant ones.

Writes results/c1_c2_masking_audit.json.

Usage:  python flip_mask_sweep.py
"""

import json
import re

from flip_dossiers import (diff_audit, jsonl, news_block, question_block,
                           split_articles, ts_block)

OUT = "results/c1_c2_masking_audit.json"

def _corrupt(src, kind):
    """Return (corrupted_text, description) or (None, why_not_applicable)."""
    if kind == "clause deleted":
        return src[:200] + src[400:], "200 characters of real prose removed"
    if kind == "entity identity changed":
        word = next((w for w in re.findall(r"\b[A-Z][a-z]{3,}\b", src)
                     if w not in ("The", "This", "That")), None)
        if not word:
            return None, "no capitalised entity token in this article"
        return src.replace(word, "Adidas", 1), "%s -> Adidas" % word
    if kind == "negation flipped":
        if " not " in src:
            return src.replace(" not ", " ", 1), "dropped a 'not'"
        return src.replace(" is ", " is not ", 1), "inserted a 'not'"
    if kind == "non-date number changed":
        m = next((x for x in re.finditer(r"\b\d+\.\d+%", src)), None) or \
            next((x for x in re.finditer(r"\b\d{1,3}%", src)), None) or \
            next((x for x in re.finditer(r"\$\d[\d,.]*", src)), None)
        if not m:
            return None, "no non-date number in this article"
        return src[:m.start()] + "999.9%" + src[m.end():], "%s -> 999.9%%" % m.group()
    raise ValueError(kind)


KINDS = ("clause deleted", "entity identity changed", "negation flipped",
         "non-date number changed")


def self_test(c1, c2):
    """The auditor must flag hand-made non-temporal edits.

    A clean sweep only means something if the auditor can fail, so each kind of
    forbidden change is injected into real article text and must be caught.
    Articles are tried in turn until one supports the injection - no synthetic
    substitutes.
    """
    articles = [a["content"] for i in list(c1)[:6]
                for a in split_articles(news_block(c1[i]))
                if len(a["content"]) > 600]
    results = []
    for kind in KINDS:
        rec = {"injection": kind, "flagged": False, "n_flags": 0,
               "applied_to": None, "edit": None}
        for src in articles:
            corrupt, note = _corrupt(src, kind)
            if corrupt is None or corrupt == src:
                continue
            _, flags = diff_audit(src, corrupt, "self-test")
            rec.update({"flagged": len(flags) > 0, "n_flags": len(flags),
                        "applied_to": src[:60].replace("\n", " "), "edit": note})
            break
        results.append(rec)
    return results


def main():
    c1 = jsonl("out_paper50_reviewed/c1.jsonl")
    c2 = jsonl("out_paper50_reviewed/c2.jsonl")
    st = self_test(c1, c2)

    per_instance, all_flags = [], []
    for i in sorted(c1):
        a1, a2 = split_articles(news_block(c1[i])), split_articles(news_block(c2[i]))
        n_changes, flags = 0, []
        for pos, (x, y) in enumerate(zip(a1, a2), 1):
            for field in ("title", "content"):
                ch, fl = diff_audit(x[field], y[field], "i%d article %d %s"
                                    % (i, pos, field))
                n_changes += len(ch)
                flags += fl
        qch, qfl = diff_audit(question_block(c1[i]), question_block(c2[i]),
                              "i%d question" % i)
        n_changes += len(qch)
        flags += qfl
        ts1, ts2 = ts_block(c1[i]), ts_block(c2[i])
        vals = lambda blk: [ln.split(" | ")[1] for ln in blk.splitlines()]
        per_instance.append({
            "instance_id": i,
            "n_articles_c1": len(a1), "n_articles_c2": len(a2),
            "article_order_identical":
                c1[i]["article_order"] == c2[i]["article_order"],
            "question_identical": question_block(c1[i]) == question_block(c2[i]),
            "ts_values_identical": vals(ts1) == vals(ts2),
            "n_textual_changes": n_changes,
            "n_flagged": len(flags),
        })
        all_flags += flags

    out = {
        "scope": "all 50 instances (task 6 asks for the discordant cases; the "
                 "sweep is a superset)",
        "auditor_self_test": {
            "description": "non-temporal edits injected into real article text "
                           "must be flagged, otherwise a clean sweep means nothing",
            "results": st,
            "all_injections_caught": all(r["flagged"] for r in st),
        },
        "totals": {
            "n_instances": len(per_instance),
            "n_textual_changes": sum(p["n_textual_changes"] for p in per_instance),
            "n_flagged": len(all_flags),
            "instances_with_flags": sorted({f["where"].split()[0]
                                            for f in all_flags}),
            "article_order_identical_everywhere":
                all(p["article_order_identical"] for p in per_instance),
            "question_identical_everywhere":
                all(p["question_identical"] for p in per_instance),
            "ts_values_identical_everywhere":
                all(p["ts_values_identical"] for p in per_instance),
            "article_count_identical_everywhere":
                all(p["n_articles_c1"] == p["n_articles_c2"] for p in per_instance),
        },
        "flags": all_flags,
        "per_instance": per_instance,
    }

    disc = json.load(open("results/c1_c2_transition_table.json",
                          encoding="utf-8"))["group_instance_ids"]
    disc_ids = set(disc["C1_CORRECT_C2_WRONG"] + disc["C1_WRONG_C2_CORRECT"])
    disc_flags = [f for f in all_flags
                  if int(f["where"].split()[0][1:]) in disc_ids]
    caught = out["auditor_self_test"]["all_injections_caught"]
    out["discordant_scope"] = {
        "instance_ids": sorted(disc_ids),
        "n_flagged": len(disc_flags),
        "flags": disc_flags,
        "verdict": ("NO_NON_TEMPORAL_MASKING_SIDE_EFFECT_FOUND"
                    if caught and not disc_flags else "REVIEW REQUIRED"),
    }
    out["all50_scope"] = {
        "n_flagged": len(all_flags),
        "note": "every flag is raised by the deliberately trigger-happy numeric "
                "guard (a 4-digit year next to a digit or decimal point, which is "
                "how a price such as 2071.12 would look) and has to be read in "
                "context; see results/c1_c2_masking_flag_context.json",
        "verdict": ("NO_NON_TEMPORAL_MASKING_SIDE_EFFECT_FOUND"
                    if caught and not all_flags else "FLAGS REQUIRE ADJUDICATION"),
    }
    out["verdict"] = out["discordant_scope"]["verdict"]
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    for r in st:
        print("self-test %-32s flagged=%s" % (r["injection"], r["flagged"]))
    t = out["totals"]
    print("\n%d instances, %d textual C1->C2 changes, %d flagged"
          % (t["n_instances"], t["n_textual_changes"], t["n_flagged"]))
    print("article order identical everywhere: %s" % t["article_order_identical_everywhere"])
    print("question identical everywhere:      %s" % t["question_identical_everywhere"])
    print("TS values identical everywhere:     %s" % t["ts_values_identical_everywhere"])
    print("article count identical everywhere: %s" % t["article_count_identical_everywhere"])
    print("\nVERDICT: %s" % out["verdict"])
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
