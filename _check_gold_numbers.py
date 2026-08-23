"""Scratch: locate every price level named in the gold option inside the window.

For the post-publication audit it is not enough to read an option and form an
impression.  If a gold option says the price went "to below $374 after the
news", the objective question is whether that level occurs in the supplied
series at all, and where.

Prints, for each instance, every number in the gold option that plausibly is a
price, whether it is matched in ts_values, and at what fraction of the window.

Analysis aid only - writes nothing.

Usage:  python _check_gold_numbers.py
"""

import datetime as dt
import json
import re

UTC = dt.timezone.utc


def main():
    data = json.load(open("final50_paper_data.json", encoding="utf-8"))
    for rec in data:
        q = rec["mcqa_question"]
        gold = rec["mcqa_answer"]
        opts = {}
        for part in q.splitlines():
            m = re.match(r"^([A-D])\.\s*(.*)$", part.strip(), re.S)
            if m:
                opts[m.group(1)] = m.group(2)
        text = opts.get(gold, "")
        vals = rec["ts_values"]
        lo, hi = min(vals), max(vals)
        nums = [float(x.replace(",", "")) for x in
                re.findall(r"\$?(\d{1,4}(?:,\d{3})*(?:\.\d+)?)", text)]
        # keep only numbers in the plausible price range for this ticker
        cand = [n for n in nums if lo * 0.8 <= n <= hi * 1.2]
        out = []
        for n in cand:
            best = min(range(len(vals)), key=lambda k: abs(vals[k] - n))
            err = abs(vals[best] - n)
            tol = max(0.02, abs(n) * 0.0015)
            out.append("%s%s@%.0f%%" % (n, "" if err <= tol else "~MISS(%.2f)" % err,
                                        100.0 * best / (len(vals) - 1)))
        print("%-4d %-5s gold=%s  range %.2f-%.2f  %s"
              % (rec["instance_id"], rec["ticker"], gold, lo, hi,
                 ", ".join(out) or "-"))


if __name__ == "__main__":
    main()
