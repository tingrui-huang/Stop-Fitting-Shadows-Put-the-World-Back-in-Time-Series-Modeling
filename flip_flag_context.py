"""Adjudicate the flags raised by the C1->C2 masking sweep, with real context.

The sweep's numeric-context test is deliberately trigger-happy: it flags any
4-digit year sitting next to a digit or a decimal point, because a price such as
2071.12 would be masked as a year.  Each flag has to be read in context before
it means anything.

Usage:  python flip_flag_context.py [instance_id ...]
"""

import difflib
import json
import sys

from flip_dossiers import (diff_audit, jsonl, merged_opcodes, news_block,
                           split_articles, tokenize)


def main():
    ids = [int(x) for x in sys.argv[1:]] or [215]
    c1, c2 = jsonl("out_paper50_reviewed/c1.jsonl"), jsonl("out_paper50_reviewed/c2.jsonl")
    out = []
    for i in ids:
        a1 = split_articles(news_block(c1[i]))
        a2 = split_articles(news_block(c2[i]))
        for pos, (x, y) in enumerate(zip(a1, a2), 1):
            for field in ("title", "content"):
                _, flags = diff_audit(x[field], y[field], "i%d article %d %s"
                                      % (i, pos, field))
                if not flags:
                    continue
                a, b = tokenize(x[field]), tokenize(y[field])
                sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
                spans = merged_opcodes(a, b, sm.get_opcodes())
                for f in flags:
                    for i1, i2, j1, j2 in spans:
                        if "".join(a[i1:i2]) != f["removed"]:
                            continue
                        ci = len("".join(a[:i1]))
                        ctx = x[field][max(0, ci - 70):ci + len(f["removed"]) + 70]
                        out.append({"where": f["where"], "removed": f["removed"],
                                    "inserted": f["inserted"], "flag": f["flag"],
                                    "context_c1": ctx.replace("\n", " ")})
                        break
    for r in out:
        print("%s   %r -> %r" % (r["where"], r["removed"], r["inserted"]))
        print("    ...%s..." % r["context_c1"])
        print("")
    with open("results/c1_c2_masking_flag_context.json", "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("wrote results/c1_c2_masking_flag_context.json (%d flags)" % len(out))


if __name__ == "__main__":
    main()
