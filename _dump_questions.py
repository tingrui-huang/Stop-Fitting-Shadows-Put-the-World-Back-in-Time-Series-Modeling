"""Scratch dump: MCQA text plus time-series / publication geometry, all 50.

Analysis aid only - writes nothing to results/.  Used to hand-classify the
post-publication semantics audit.

Usage:  python _dump_questions.py [start] [end]
"""

import datetime as dt
import json
import sys

UTC = dt.timezone.utc


def pub_ts(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()


def fmt(t):
    return dt.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d %H:%M:%S")


def main():
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    data = json.load(open("final50_paper_data.json", encoding="utf-8"))
    for rec in data[lo:hi]:
        g = pub_ts(rec["gt_published_utc"])
        first, last = rec["ts_timestamps"][0], rec["ts_timestamps"][-1]
        n_after = sum(1 for t in rec["ts_timestamps"] if t > g)
        print("=" * 78)
        print("### %d %s   gold=%s" % (rec["instance_id"], rec["ticker"],
                                       rec["mcqa_answer"]))
        print("TS %s -> %s  (%d pts) | GT pub %s | last-pub %+.2f h | n_after=%d"
              % (fmt(first), fmt(last), len(rec["ts_values"]),
                 rec["gt_published_utc"], (last - g) / 3600.0, n_after))
        print("GT title: %s" % rec["gt_article_text"].split("  |  ")[0][:110])
        for part in rec["mcqa_question"].split(" | "):
            print("   " + part.strip())
        print("")


if __name__ == "__main__":
    main()
