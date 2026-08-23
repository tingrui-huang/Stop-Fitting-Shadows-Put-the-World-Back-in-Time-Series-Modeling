"""Scratch dump of the ORIGINAL 100 MCQA items with temporal geometry.

Reads only c0_data.json and hard50_data.json.  Writes nothing.

Usage:  python _dump_original100.py <source> <start> <end>
        source: c0 | hard
"""

import datetime as dt
import json
import re
import sys

UTC = dt.timezone.utc
SRC = {"c0": "c0_data.json", "hard": "hard50_data.json"}
POST = re.compile(r"\b(after|following|subsequent|since|thereafter|reaction|"
                  r"by the end|shortly after|post-news|post-publication|"
                  r"immediately)\b", re.I)


def pub_ts(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=UTC).timestamp()


def main():
    which = sys.argv[1]
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    rows = json.load(open(SRC[which], encoding="utf-8"))
    rows.sort(key=lambda r: r["instance_id"])
    for rec in rows[lo:hi]:
        vals, ts = rec["ts_values"], rec["ts_timestamps"]
        g = pub_ts(rec["gt_published_utc"])
        f = lambda t: dt.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d %H:%M")
        print("=" * 76)
        print("### %s %d %s gold=%s | TS %s -> %s (%d pts, %.2f-%.2f) | pub %s "
              "| last-pub %+.2fh | n_after=%d"
              % (which, rec["instance_id"], rec["ticker"], rec["mcqa_answer"],
                 f(ts[0]), f(ts[-1]), len(vals), min(vals), max(vals),
                 rec["gt_published_utc"], (ts[-1] - g) / 3600.0,
                 sum(1 for t in ts if t > g)))
        title = rec["gt_article_text"].split("  |  ")[0]
        print("GT: %s" % title[:120].replace("\n", " "))
        for part in rec["mcqa_question"].splitlines():
            m = re.match(r"^([A-D])\.\s*(.*)$", part.strip(), re.S)
            if not m:
                print("Q: %s" % part.strip())
                continue
            letter, text = m.group(1), m.group(2)
            art = rec["gt_article_text"]
            notes = []
            for x in re.findall(r"\$?(\d{1,5}(?:,\d{3})*(?:\.\d+)?)", text):
                n = float(x.replace(",", ""))
                in_art = "ART" if re.search(r"(?<![\d.])%s(?![\d])"
                                            % re.escape(x), art) else ""
                if not (min(vals) * 0.9 <= n <= max(vals) * 1.1):
                    if in_art:
                        notes.append("%s=inArticle" % x)
                    continue
                tol = max(0.02, abs(n) * 0.0015)
                hits = [k for k, v in enumerate(vals) if abs(v - n) <= tol]
                notes.append(("%g@%.0f-%.0f%%" % (n, 100.0 * hits[0] / (len(vals) - 1),
                                                  100.0 * hits[-1] / (len(vals) - 1))
                              if hits else "%g=ABSENT" % n) + ("+ART" if in_art else ""))
            print("  %s%s %-6s %s%s"
                  % (letter, "*" if letter == rec["mcqa_answer"] else " ",
                     "[POST]" if POST.search(text) else "[   ]", text.strip(),
                     ("   << " + ", ".join(notes)) if notes else ""))
        print("")


if __name__ == "__main__":
    main()
