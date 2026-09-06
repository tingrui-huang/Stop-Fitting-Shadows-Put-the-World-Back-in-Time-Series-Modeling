"""Render a run's raw results as readable per-instance trace files.

The raw files under results/<tag>/<cond>_raw/ are the record of what happened
and stay authoritative: they hold the full API response and nothing in them is
truncated. They are not readable, though - a single reasoning trace runs to
109,000 characters on one JSON line, followed by the whole response object. This
writes the same content as one Markdown file per instance, plus an index, so a
reader can follow what the model actually did without a JSON viewer.

Nothing here is derived or summarised: the reasoning and the final answer are
copied verbatim and are never elided, however long the trace. (The copy sent to
Docent for the failure-mode analysis does elide the middle of a non-terminating
trace; that is a separate artefact and this tree is the place to read the whole
thing.) Delete the tree and re-run to regenerate it.

Runs that produced no final answer are rendered too, from failures_<cond>.jsonl.
They are not an edge case worth dropping: GLM-5.3-Flash ran the completion
ceiling out on 127 of 160 NO_TS items and 124 of 160 RELATIVE ones, so a tree
built only from the answered runs would be missing four fifths of two
conditions, and the reasoning produced before the ceiling is stored in full.

Usage:  python make_readable_traces.py --tag tsrbench50_qwen36
        python make_readable_traces.py --tag tsrbench160_glm53flash_zai \
            --cli-dir "tsrbench160/cli/%s"
"""
import argparse
import glob
import io
import json
import os

NL = chr(10)
SEP = chr(92)                       # Windows path separator, seen in stored paths
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


def rel_prompt(rec, cond, cli_dir):
    """The frozen prompt this run was sent, as a repo-relative path.

    Taken from the record rather than assumed, because the same generator
    renders several studies and the stored path is the only thing that says
    which prompt tree a run actually read.
    """
    p = (rec.get("prompt_file") or "").replace(SEP, "/").lstrip("./")
    if p:
        return p
    # A run that never answered stores no prompt path, so rebuild it from
    # the same frozen tree the runner was pointed at.
    base = (cli_dir % cond).replace(SEP, "/") if cli_dir else cond
    return "%s/%s.txt" % (base, rec.get("instance_id"))


def load_index(cli_dir, cond):
    """instance_id -> (gold, ticker), from the frozen prompt index.

    A run that never answered writes no result file and so carries none of
    this; the index is where a non-terminating run's gold answer comes from.
    """
    out = {}
    if not cli_dir:
        return out
    p = os.path.join(cli_dir % cond, "index.jsonl")
    if os.path.exists(p):
        for line in io.open(p, encoding="utf-8"):
            if line.strip():
                e = json.loads(line)
                out[e["instance_id"]] = (e.get("gold_answer"), e.get("ticker"))
    return out


def load_run_meta(root, cond):
    """The run's own metadata: model and decoding, for records that lack them."""
    p = os.path.join(root, "run_metadata_%s.json" % cond)
    if os.path.exists(p):
        return json.load(io.open(p, encoding="utf-8"))
    return {}


def failure_records(root, cond):
    """One record per instance from failures_<cond>.jsonl, longest attempt kept.

    A retry writes a second line for the same instance; the analysis reads
    traces, so keep whichever attempt produced the most reasoning.
    """
    p = os.path.join(root, "failures_%s.jsonl" % cond)
    if not os.path.exists(p):
        return {}
    best = {}
    for line in io.open(p, encoding="utf-8"):
        if not line.strip():
            continue
        rec = json.loads(line)
        iid = int(rec.get("instance_id") or 0)
        prev = best.get(iid)
        if prev is None or len(rec.get("reasoning") or "") > len(
                prev.get("reasoning") or ""):
            best[iid] = rec
    return best


def write_trace(rec, path, cond, tag, meta, index, cli_dir):
    iid = rec["instance_id"]
    gold_idx, ticker_idx = index.get(iid, (None, None))
    g = rec.get("gold_answer") or gold_idx
    p = predicted(rec)
    answered = p is not None
    verdict = "correct" if (answered and p == g) else "wrong"
    gen = rec.get("generation") or meta.get("generation") or {}
    usage = rec.get("usage") or {}
    trace = rec.get("reasoning") or ""
    L = [
        "# %s / %s / instance %s%s"
        % (tag, cond.upper(), iid, "" if answered else "  (no final answer)"),
        "",
        "| | |",
        "|---|---|",
        "| model | `%s` |" % (rec.get("model") or meta.get("model")),
        "| condition | `%s` - %s |" % (cond.upper(), GLOSS.get(cond, "")),
        "| domain | `%s` |" % (rec.get("ticker") or ticker_idx),
        "| prompt | [`%s`](../../../../%s) &nbsp; sha256 `%s` |"
        % (rel_prompt(rec, cond, cli_dir), rel_prompt(rec, cond, cli_dir),
           (rec.get("prompt_sha256") or "")[:16] or "-"),
        "| system prompt | `%s` &nbsp; sha256 `%s` |"
        % (rec.get("system_prompt_file") or meta.get("system_prompt_file"),
           (rec.get("system_prompt_sha256")
            or meta.get("system_prompt_sha256") or "")[:16]),
        "| decoding | temperature %s, top_p %s, seed %s, max_tokens %s |"
        % (gen.get("temperature"), gen.get("top_p"), gen.get("seed"),
           gen.get("max_tokens")),
        "| gold | **%s** |" % g,
        "| predicted | **%s** - %s |"
        % (p if answered else "none", verdict),
        "| finish_reason | `%s`%s |"
        % (rec.get("finish_reason"),
           ", hit the completion ceiling" if rec.get("truncated") else ""),
        "| tokens | %s completion, %s prompt |"
        % (usage.get("completion_tokens"), usage.get("prompt_tokens")),
        "| trace | %s characters, complete and unelided |" % format(len(trace), ","),
        "",
    ]
    if not answered:
        L += [
            "> **This run produced no final answer.** It ran the %s-token"
            % (gen.get("max_tokens") or "completion"),
            "> completion ceiling out mid-thought, so the trace below stops where",
            "> generation was cut off rather than where the model concluded. It is",
            "> scored wrong in the accuracy tables. The reasoning is whole up to",
            "> that point and nothing has been removed from it.",
            "",
        ]
    L += [
        "## Reasoning trace",
        "",
        "> Verbatim, as returned in the `reasoning` field. Not edited or truncated.",
        "",
        trace or "*(the model returned no reasoning)*",
        "",
        "## Final answer",
        "",
    ]
    if answered or (rec.get("content") or "").strip():
        L += ["```json", (rec.get("content") or "").strip(), "```", ""]
    else:
        L += ["*(none - generation was cut off before the model emitted one)*", ""]
    with io.open(path, "w", encoding="utf-8", newline=NL) as f:
        f.write(NL.join(L))
    return g, p, verdict, bool(rec.get("truncated")), len(trace)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--cli-dir", default=None,
                    help="frozen prompt tree with %s for the condition. Read for "
                         "the study size, and for the gold answer of any run "
                         "that never produced one of its own.")
    ap.add_argument("--answered-only", action="store_true",
                    help="skip runs that hit the completion ceiling. Off by "
                         "default: on GLM those are four fifths of two "
                         "conditions and dropping them hides the main effect.")
    args = ap.parse_args()

    root = os.path.join("results", args.tag)
    total = None
    if args.cli_dir:
        for cond in CONDS:
            idx = os.path.join(args.cli_dir % cond, "index.jsonl")
            if os.path.exists(idx):
                total = sum(1 for l in io.open(idx, encoding="utf-8")
                            if l.strip())
                break
    out = args.out or os.path.join(root, "traces_readable")
    idx = {}
    for cond in CONDS:
        src = os.path.join(root, "%s_raw" % cond)
        fails = {} if args.answered_only else failure_records(root, cond)
        if not os.path.isdir(src) and not fails:
            continue
        meta = load_run_meta(root, cond)
        index = load_index(args.cli_dir, cond)
        d = os.path.join(out, cond)
        os.makedirs(d, exist_ok=True)
        rowset = []
        seen = set()
        for p in sorted(glob.glob(os.path.join(src, "*.json")),
                        key=lambda q: int(os.path.basename(q)[:-5])):
            rec = json.load(io.open(p, encoding="utf-8"))
            iid = rec["instance_id"]
            seen.add(int(iid))
            rowset.append((iid,) + write_trace(
                rec, os.path.join(d, "%s.md" % iid), cond, args.tag, meta,
                index, args.cli_dir))
        n_fail = 0
        for iid in sorted(fails):
            if iid in seen:
                continue          # a retry that later succeeded is already above
            rec = dict(fails[iid], instance_id=iid)
            if not (rec.get("reasoning") or ""):
                continue          # died before writing anything; nothing to read
            rowset.append((iid,) + write_trace(
                rec, os.path.join(d, "%s.md" % iid), cond, args.tag, meta,
                index, args.cli_dir))
            n_fail += 1
        rowset.sort(key=lambda r: int(r[0]))
        idx[cond] = rowset
        print("%-9s %3d traces (%d answered, %d non-terminating) -> %s"
              % (cond, len(rowset), len(rowset) - n_fail, n_fail, d))

    L = ["# Readable reasoning traces - %s" % args.tag,
         "",
         "One Markdown file per instance, rendered from the authoritative raw",
         "results under `results/%s/`. The reasoning trace and the final" % args.tag,
         "answer are copied verbatim and are never elided; regenerate with",
         "`python make_readable_traces.py --tag %s`." % args.tag,
         "",
         "Runs marked **no answer** ran the completion ceiling out without",
         "emitting one. They write no result file, so they are rendered from",
         "`failures_<cond>.jsonl`; their reasoning is whole up to the cut.",
         "They are scored wrong in the accuracy tables.",
         ""]
    for cond in CONDS:
        if cond not in idx:
            continue
        rows = idx[cond]
        ok = sum(1 for r in rows if r[3] == "correct")
        nt = sum(1 for r in rows if r[2] is None)
        L += ["## %s" % cond.upper(),
              "",
              "%s. %d of %d instances rendered, %d correct, %d never answered."
              % (GLOSS.get(cond, "").capitalize(), len(rows),
                 total or len(rows), ok, nt),
              "",
              "| instance | gold | predicted | | reasoning chars |",
              "|---|---|---|---|---|"]
        for iid, g, pr, v, tr, n in rows:
            L.append("| [%s](%s/%s.md) | %s | %s | %s | %s |"
                     % (iid, cond, iid, g,
                        pr if pr is not None else "*no answer*",
                        "ok" if v == "correct" else "x", format(n, ",")))
        L.append("")
    with io.open(os.path.join(out, "INDEX.md"), "w", encoding="utf-8",
                 newline=NL) as f:
        f.write(NL.join(L))
    print("wrote", os.path.join(out, "INDEX.md"))


if __name__ == "__main__":
    main()
