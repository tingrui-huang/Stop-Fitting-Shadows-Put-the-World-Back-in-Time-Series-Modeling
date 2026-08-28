"""Render the TSRBench-50 raw results as readable per-instance trace files.

The raw files under results/<tag>/<cond>_raw/ are the record of what happened
and stay authoritative: they hold the full API response and nothing in them is
truncated. They are not readable, though - a single reasoning trace runs to
24,000 characters on one JSON line, followed by the whole response object. This
writes the same content as one Markdown file per instance, plus an index, so a
reader can follow what the model actually did without a JSON viewer.

Nothing here is derived or summarised: the reasoning and the final answer are
copied verbatim. Delete the tree and re-run to regenerate it.

Usage:  python make_readable_traces.py --tag tsrbench50_qwen36
"""
import argparse
import glob
import io
import json
import os

NL = chr(10)
CONDS = ("qa_only", "full", "no_ts", "shuffled", "relative")
GLOSS = {
    "qa_only":  "question and the four orderings only - the leakage check",
    "full":     "timestamped series + events with their times - the reference",
    "no_ts":    "every timestamp deleted, series and events",
    "shuffled": "series timestamp-value pairing deranged",
    "relative": "absolute timestamps replaced by unitless relative indices",
}


def predicted(rec):
    c = rec.get("content") or ""
    try:
        return json.loads(c[c.index("{"):c.rindex("}") + 1]).get("answer")
    except Exception:
        return None


def write_trace(rec, path, cond):
    g, p = rec.get("gold_answer"), predicted(rec)
    verdict = "correct" if (p is not None and p == g) else "wrong"
    gen = rec.get("generation") or {}
    usage = rec.get("usage") or {}
    L = [
        "# TSRBench-50 / %s / instance %s" % (cond.upper(), rec["instance_id"]),
        "",
        "| | |",
        "|---|---|",
        "| model | `%s` |" % rec.get("model"),
        "| condition | `%s` - %s |" % (cond.upper(), GLOSS.get(cond, "")),
        "| domain | `%s` |" % rec.get("ticker"),
        "| prompt | [`%s`](../../../../tsrbench50/cli/%s/%s.txt) &nbsp; sha256 `%s` |"
        % ("tsrbench50/cli/%s/%s.txt" % (cond, rec["instance_id"]),
           cond, rec["instance_id"], (rec.get("prompt_sha256") or "")[:16]),
        "| system prompt | `%s` &nbsp; sha256 `%s` |"
        % (rec.get("system_prompt_file"), (rec.get("system_prompt_sha256") or "")[:16]),
        "| decoding | temperature %s, top_p %s, seed %s, max_tokens %s |"
        % (gen.get("temperature"), gen.get("top_p"), gen.get("seed"), gen.get("max_tokens")),
        "| gold | **%s** |" % g,
        "| predicted | **%s** - %s |" % (p if p is not None else "none", verdict),
        "| finish_reason | `%s`%s |"
        % (rec.get("finish_reason"),
           ", hit the completion ceiling" if rec.get("truncated") else ""),
        "| tokens | %s completion, %s prompt |"
        % (usage.get("completion_tokens"), usage.get("prompt_tokens")),
        "",
        "## Reasoning trace",
        "",
        "> Verbatim, as returned in the `reasoning` field. Not edited or truncated.",
        "",
        (rec.get("reasoning") or "*(the model returned no reasoning)*"),
        "",
        "## Final answer",
        "",
        "```json",
        (rec.get("content") or "").strip() or "(the model produced no final content)",
        "```",
        "",
    ]
    with io.open(path, "w", encoding="utf-8", newline=NL) as f:
        f.write(NL.join(L))
    return g, p, verdict, bool(rec.get("truncated"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    root = os.path.join("results", args.tag)
    out = args.out or os.path.join(root, "traces_readable")
    idx = {}
    for cond in CONDS:
        src = os.path.join(root, "%s_raw" % cond)
        if not os.path.isdir(src):
            continue
        d = os.path.join(out, cond)
        os.makedirs(d, exist_ok=True)
        rowset = []
        for p in sorted(glob.glob(os.path.join(src, "*.json")),
                        key=lambda q: int(os.path.basename(q)[:-5])):
            rec = json.load(io.open(p, encoding="utf-8"))
            iid = rec["instance_id"]
            g, pr, v, tr = write_trace(rec, os.path.join(d, "%s.md" % iid), cond)
            rowset.append((iid, g, pr, v, tr, len(rec.get("reasoning") or "")))
        idx[cond] = rowset
        print("%-9s %2d traces -> %s" % (cond, len(rowset), d))

    L = ["# Readable reasoning traces - TSRBench-50",
         "",
         "One Markdown file per instance, rendered from the authoritative raw",
         "results under `results/%s/<cond>_raw/`. The reasoning trace and the" % args.tag,
         "final answer are copied verbatim; regenerate with",
         "`python make_readable_traces.py --tag %s`." % args.tag,
         "",
         "An instance missing from a table produced no final answer at all: the",
         "runner writes no result file in that case, so the instance stays",
         "rerunnable and its partial trace is kept in `failures_<cond>.jsonl`.",
         ""]
    for cond in CONDS:
        if cond not in idx:
            continue
        rows = idx[cond]
        ok = sum(1 for r in rows if r[3] == "correct")
        L += ["## %s" % cond.upper(),
              "",
              "%s. %d of 50 instances answered, %d correct."
              % (GLOSS.get(cond, "").capitalize(), len(rows), ok),
              "",
              "| instance | gold | predicted | | reasoning chars |",
              "|---|---|---|---|---|"]
        for iid, g, pr, v, tr, n in rows:
            L.append("| [%s](%s/%s.md) | %s | %s | %s | %s |"
                     % (iid, cond, iid, g, pr if pr is not None else "-",
                        "ok" if v == "correct" else "x", n))
        L.append("")
    with io.open(os.path.join(out, "INDEX.md"), "w", encoding="utf-8", newline=NL) as f:
        f.write(NL.join(L))
    print("wrote", os.path.join(out, "INDEX.md"))


if __name__ == "__main__":
    main()
