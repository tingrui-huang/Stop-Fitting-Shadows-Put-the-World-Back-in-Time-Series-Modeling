"""Scratch: for every option of every instance, locate its price levels in the
supplied window.

A price level named by an option is either present in the supplied series (and
then at some position in it) or absent.  Absent levels are objective evidence
that the option refers to data the input-window protocol does not supply.

Also prints, per instance, where the last window point sits relative to
publication.

Analysis aid only - writes nothing.

Usage:  python _check_option_numbers.py
"""

import datetime as dt
import json
import re

UTC = dt.timezone.utc
POST_WORDS = re.compile(
    r"\b(after|following|subsequent|post-news|post-publication|since|thereafter|"
    r"immediately after|shortly after)\b", re.I)


def main():
    data = json.load(open("final50_paper_data.json", encoding="utf-8"))
    for rec in data:
        vals = rec["ts_values"]
        lo, hi = min(vals), max(vals)
        g = dt.datetime.strptime(rec["gt_published_utc"], "%Y-%m-%d %H:%M:%S") \
            .replace(tzinfo=UTC).timestamp()
        gap = (rec["ts_timestamps"][-1] - g) / 3600.0
        print("=" * 74)
        print("### %d %s gold=%s  window %.2f-%.2f  last point %+.2f h vs publication"
              % (rec["instance_id"], rec["ticker"], rec["mcqa_answer"], lo, hi, gap))
        for part in rec["mcqa_question"].splitlines():
            m = re.match(r"^([A-D])\.\s*(.*)$", part.strip(), re.S)
            if not m:
                continue
            letter, text = m.group(1), m.group(2)
            nums = [float(x.replace(",", "")) for x in
                    re.findall(r"\$?(\d{1,4}(?:,\d{3})*(?:\.\d+)?)", text)]
            notes = []
            for n in nums:
                if not (lo * 0.9 <= n <= hi * 1.1):
                    continue
                tol = max(0.02, abs(n) * 0.0015)
                hits = [k for k, v in enumerate(vals) if abs(v - n) <= tol]
                if hits:
                    notes.append("%g@%s%%" % (n, "/".join(
                        "%.0f" % (100.0 * k / (len(vals) - 1))
                        for k in (hits[0], hits[-1]))))
                else:
                    notes.append("%g=ABSENT_FROM_WINDOW" % n)
            print("  %s%s %s%s"
                  % (letter, "*" if letter == rec["mcqa_answer"] else " ",
                     "[post-words]" if POST_WORDS.search(text) else "[  -  ]",
                     ("  " + ", ".join(notes)) if notes else ""))


if __name__ == "__main__":
    main()
