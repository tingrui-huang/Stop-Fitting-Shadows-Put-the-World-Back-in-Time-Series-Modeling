"""Export TSRBench runs as Docent agent runs, one per model x condition x instance.

Docent (https://transluce.org/docent) reads transcripts and lets you search and
cluster behaviour across them. This turns the study's stored results into that
shape without losing anything that makes a run interpretable: the frozen system
prompt and user prompt exactly as sent, the reasoning trace as a reasoning
content block rather than flattened into the answer, and metadata rich enough
to slice by every axis the study varies.

Three models are exported into one collection so they can be compared directly:

    Qwen3.6-35B-A3B   full reasoning traces, from vLLM on two H100s
    GLM-5.3-Flash     full reasoning traces, from the Z.AI endpoint
    Sonnet-5          no trace: the Claude CLI returns thinking blocks whose
                      text is encrypted, so those are marked redacted rather
                      than silently exported as empty

The metadata carries gold, prediction, correctness, the condition, the domain,
the trace length and the token counts, so a Docent search can ask things like
"instances where the model answered correctly from a short trace" or "traces
that mention CAMEO" and get a comparable slice across all three.

Usage
  python export_to_docent.py --dump docent_runs.jsonl          # inspect first
  python export_to_docent.py --upload --collection-name tsrbench
"""
import argparse
import glob
import io
import json
import os
import re

CONDS = ("qa_only", "full", "no_ts", "shuffled", "relative")
GLOSS = {
    "qa_only":  "question and the four orderings only - the leakage check",
    "full":     "timestamped series + events with their times - the reference",
    "no_ts":    "every timestamp deleted, series and events",
    "shuffled": "series timestamp-value pairing deranged",
    "relative": "absolute timestamps replaced by unitless relative indices",
}


def read(path):
    return io.open(path, encoding="utf-8", newline="").read()


def parse_answer(content):
    """The final JSON the model was asked to emit, or {} if it did not."""
    if not content:
        return {}
    try:
        return json.loads(content[content.index("{"):content.rindex("}") + 1])
    except Exception:                                            # noqa: BLE001
        return {}


def elide(text, head, tail):
    """Middle-truncate a long trace. -> (text, chars removed).

    Only worth doing to a run that never terminated. Measured over 25 sampled
    runs per condition, a trace that reached an answer duplicates 2 to 4 per
    cent of its 8-word shingles, while one that ran the 22,000-token ceiling
    out duplicates 37 per cent (FULL), 43 (NO_TS) and 42 (RELATIVE): the loop
    rephrases rather than repeating outright, so whole-sentence matching sees
    only 1 to 3 per cent and badly understates it. The strategy such a run
    committed to is stated near the beginning and the state it was still
    circling in is at the end.

    SHUFFLED is the exception at 10 per cent, so its truncated traces lose
    more real content here than the others do.

    A trace that did reach an answer is dense and must not be cut: its
    decisive step can sit anywhere.
    """
    if head <= 0 or len(text) <= head + tail:
        return text, 0
    cut = len(text) - head - tail
    note = "[... %d characters elided from the middle of a non-terminating trace ...]"
    sep = "\n\n" + note % cut + "\n\n"
    return text[:head] + sep + text[-tail:], cut


def failure_records(tag, cond):
    """Runs that never emitted an answer, from failures_<cond>.jsonl.

    These are not an edge case to drop. GLM-5.3-Flash ran the 22,000-token
    completion ceiling out on 127 of 160 NO_TS items and 124 of 160 RELATIVE
    ones, against 62 and 60 where the prompt still carried real calendar
    dates. Exporting only the runs that finished would silently delete four
    fifths of the two conditions the study exists to test, and would leave
    behind exactly the behaviour that distinguishes them: the model does not
    answer wrongly when the calendar is removed, it fails to stop. The
    reasoning produced before the ceiling is stored in full.
    """
    path = os.path.join("results", tag, "failures_%s.jsonl" % cond)
    if not os.path.exists(path):
        return []
    best = {}
    for line in io.open(path, encoding="utf-8"):
        if not line.strip():
            continue
        rec = json.loads(line)
        iid = int(rec.get("instance_id") or 0)
        prev = best.get(iid)
        # A retry writes a second line for the same instance. Keep the
        # attempt that produced the most reasoning: the analysis reads
        # traces, and the run is one instance either way.
        if prev is None or len(rec.get("reasoning") or "") > len(
                prev.get("reasoning") or ""):
            best[iid] = rec
    return [best[k] for k in sorted(best)]


def source_meta(tree):
    """instance_id -> the fields the sample carries (domain, n_events)."""
    src = os.path.join(os.path.dirname(tree.rstrip("/")),
                       os.path.basename(os.path.dirname(tree.rstrip("/"))) + ".jsonl")
    out = {}
    if os.path.exists(src):
        for line in io.open(src, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                out[r["instance_id"]] = {"domain": r.get("domain"),
                                         "n_events": r.get("n_events")}
    return out


def collect(tag, tree, model_label, system_path, elide_over=0,
            elide_head=8000, elide_tail=4000, elide_scope="truncated"):
    """-> [run dicts] for one run tag. Reads whichever file type it wrote."""
    runs = []
    extra = source_meta(tree)
    system_text = read(system_path) if os.path.exists(system_path) else ""
    for cond in CONDS:
        raw = os.path.join("results", tag, "%s_raw" % cond)
        fails = failure_records(tag, cond)
        if not os.path.isdir(raw) and not fails:
            continue
        gold = {}
        idx = os.path.join(tree, cond, "index.jsonl")
        if os.path.exists(idx):
            for line in io.open(idx, encoding="utf-8"):
                if line.strip():
                    e = json.loads(line)
                    gold[e["instance_id"]] = e.get("gold_answer")
        for path in sorted(glob.glob(os.path.join(raw, "*.json")) +
                           glob.glob(os.path.join(raw, "*.txt")),
                           key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)) or 0)):
            iid = int(re.sub(r"\D", "", os.path.basename(path)) or 0)
            prompt_path = os.path.join(tree, cond, "%d.txt" % iid)
            if not os.path.exists(prompt_path):
                continue
            if path.endswith(".json"):
                rec = json.load(io.open(path, encoding="utf-8"))
                reasoning = rec.get("reasoning") or ""
                content = rec.get("content") or ""
                usage = rec.get("usage") or {}
                meta_extra = {
                    "finish_reason": rec.get("finish_reason"),
                    "truncated": bool(rec.get("truncated")),
                    "reasoning_source": rec.get("reasoning_source"),
                    "prompt_sha256": rec.get("prompt_sha256"),
                    "system_prompt_sha256": rec.get("system_prompt_sha256"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                }
                redacted = False
            else:
                # The Claude CLI writes the final text only. Its thinking blocks
                # come back with an empty string and a signature, so there is no
                # trace to export - say so rather than exporting an empty one.
                content = read(path)
                reasoning = ""
                redacted = True
                meta_extra = {"finish_reason": None, "truncated": False,
                              "reasoning_source": "unavailable_encrypted",
                              "completion_tokens": None, "prompt_tokens": None}
            ans = parse_answer(content)
            pred = ans.get("answer")
            n_chars = len(reasoning)
            skip = (elide_over <= 0 or n_chars <= elide_over
                    or elide_scope == "truncated")
            reasoning, cut = ((reasoning, 0) if skip
                              else elide(reasoning, elide_head, elide_tail))
            meta_extra = dict(meta_extra, elided_chars=cut,
                              reasoning_chars_full=n_chars)
            runs.append({
                "system": system_text,
                "user": read(prompt_path),
                "reasoning": reasoning,
                "reasoning_redacted": redacted,
                "content": content,
                "metadata": dict({
                    "model": model_label,
                    "run_tag": tag,
                    "condition": cond.upper(),
                    "condition_gloss": GLOSS.get(cond, ""),
                    "instance_id": iid,
                    "gold_answer": gold.get(iid),
                    "prediction": pred,
                    "confidence": ans.get("confidence"),
                    "evidence_articles": ans.get("evidence_articles"),
                    "reasoning_chars": len(reasoning),
                    "answered": bool(pred),
                    "scores": {"correct": int(bool(pred) and pred == gold.get(iid))},
                }, **dict(meta_extra, **extra.get(iid, {}))),
            })
        answered_ids = {r["metadata"]["instance_id"] for r in runs
                        if r["metadata"]["condition"] == cond.upper()}
        for rec in fails:
            iid = int(rec.get("instance_id") or 0)
            if iid in answered_ids:
                continue
            prompt_path = os.path.join(tree, cond, "%d.txt" % iid)
            trace = rec.get("reasoning") or ""
            # A request that died before the model wrote anything leaves
            # nothing for a trace analysis to read. It is still wrong in
            # the accuracy table; it is simply not a transcript.
            if not trace or not os.path.exists(prompt_path):
                continue
            n_chars = len(trace)
            trace, cut = ((trace, 0)
                          if elide_over <= 0 or n_chars <= elide_over
                          else elide(trace, elide_head, elide_tail))
            usage = rec.get("usage") or {}
            runs.append({
                "system": system_text,
                "user": read(prompt_path),
                "reasoning": trace,
                "reasoning_redacted": False,
                "content": "",
                "metadata": dict({
                    "model": model_label,
                    "run_tag": tag,
                    "condition": cond.upper(),
                    "condition_gloss": GLOSS.get(cond, ""),
                    "instance_id": iid,
                    "gold_answer": gold.get(iid),
                    "prediction": None,
                    "confidence": None,
                    "evidence_articles": None,
                    "reasoning_chars": len(trace),
                    "reasoning_chars_full": n_chars,
                    "elided_chars": cut,
                    "answered": False,
                    "finish_reason": rec.get("finish_reason"),
                    "truncated": bool(rec.get("truncated")),
                    "failure_stage": rec.get("stage"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "scores": {"correct": 0},
                }, **extra.get(iid, {})),
            })
    return runs


def as_agent_run_dict(run):
    """One agent run, serialised: a transcript of three messages.

    The reasoning is its own content block rather than folded into the
    answer, so a reader can search the trace separately from what the
    model finally said. A run whose trace is unavailable carries redacted
    true instead of an empty string - a different claim, and the honest
    one here.
    """
    blocks = []
    if run["reasoning"] or run["reasoning_redacted"]:
        blocks.append({"type": "reasoning", "reasoning": run["reasoning"],
                       "redacted": run["reasoning_redacted"]})
    blocks.append({"type": "text", "text": run["content"]})
    return {
        "transcripts": [{"messages": [
            {"role": "system", "content": run["system"]},
            {"role": "user", "content": run["user"]},
            {"role": "assistant", "content": blocks},
        ]}],
        "metadata": run["metadata"],
    }


def to_docent(run):
    from docent.data_models import AgentRun, Transcript                # noqa
    from docent.data_models.chat import parse_chat_message             # noqa
    msgs = [parse_chat_message({"role": "system", "content": run["system"]}),
            parse_chat_message({"role": "user", "content": run["user"]})]
    blocks = []
    if run["reasoning"] or run["reasoning_redacted"]:
        blocks.append({"type": "reasoning", "reasoning": run["reasoning"],
                       "redacted": run["reasoning_redacted"]})
    blocks.append({"type": "text", "text": run["content"]})
    msgs.append(parse_chat_message({"role": "assistant", "content": blocks}))
    return AgentRun(transcripts=[Transcript(messages=msgs)],
                    metadata=run["metadata"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", nargs="*", default=[
        "tsrbench160_qwen36:tsrbench160/cli:qwen3.6-35b-a3b",
        "tsrbench160_sonnet5:tsrbench160/cli:claude-sonnet-5",
        "tsrbench160_glm53flash_zai:tsrbench160/cli:glm-5.3-flash",
    ], help="run_tag:prompt_tree:model_label triples")
    ap.add_argument("--system-prompt", default="prompts/system.txt")
    ap.add_argument("--dump", default=None,
                    help="write the runs to this path and upload nothing. "
                         "A .json name writes the JSON array of agent runs "
                         "the Docent Claude Code plugin ingests; any other "
                         "name writes JSONL of the intermediate shape.")
    ap.add_argument("--conditions", nargs="*", default=None,
                    help="restrict to these conditions, e.g. full")
    ap.add_argument("--models", nargs="*", default=None,
                    help="restrict to model labels, matched as a prefix")
    ap.add_argument("--traced-only", action="store_true",
                    help="drop runs with no reasoning trace. Sonnet has "
                         "none - the CLI encrypts them - so it adds bulk "
                         "but nothing a trace analysis can read, and "
                         "ingesting it spends credit for no answer.")
    ap.add_argument("--disagreements", action="store_true",
                    help="keep only instances where the exported models "
                         "did not all predict the same letter: same "
                         "prompt, different outcome, so the traces differ "
                         "for a reason. The densest slice per token.")
    ap.add_argument("--elide-over", type=int, default=0,
                    help="middle-truncate any trace longer than this "
                         "many characters, keeping --elide-head from "
                         "the front and --elide-tail from the back. A "
                         "non-terminating trace is a loop: its median "
                         "length here is 65,408 characters and 45%% of "
                         "its sentences repeat one already written, so "
                         "the middle costs tokens and says nothing the "
                         "two ends do not. 0 disables it.")
    ap.add_argument("--elide-scope", choices=("truncated", "all"),
                    default="truncated",
                    help="which traces --elide-over applies to. The "
                         "default leaves every run that reached an "
                         "answer whole; those duplicate only 2-4%% of "
                         "their 8-word shingles and cutting them would "
                         "drop reasoning the analysis is there to read.")
    ap.add_argument("--elide-head", type=int, default=8000)
    ap.add_argument("--elide-tail", type=int, default=4000)
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--collection-name", default="tsrbench-160")
    ap.add_argument("--collection-id", default=None,
                    help="add to an existing collection instead of creating one")
    args = ap.parse_args()

    runs = []
    for spec in args.sources:
        tag, tree, label = spec.split(":")
        got = collect(tag, tree, label, args.system_prompt,
                      args.elide_over, args.elide_head, args.elide_tail,
                      args.elide_scope)
        print("  %-30s %4d runs" % (tag, len(got)))
        runs.extend(got)
    print("  %-30s %4d runs total" % ("", len(runs)))
    if not runs:
        raise SystemExit("nothing to export")

    if args.conditions:
        want = {c.upper() for c in args.conditions}
        runs = [r for r in runs if r["metadata"]["condition"] in want]
    if args.models:
        runs = [r for r in runs
                if any(r["metadata"]["model"].startswith(m)
                       for m in args.models)]
    if args.traced_only:
        runs = [r for r in runs if r["reasoning"]]
    if args.disagreements:
        by = {}
        for r in runs:
            m = r["metadata"]
            by.setdefault((m["condition"], m["instance_id"]),
                          set()).add(m["prediction"])
        keep = {k for k, v in by.items() if len(v) > 1}
        runs = [r for r in runs
                if (r["metadata"]["condition"],
                    r["metadata"]["instance_id"]) in keep]
    if not runs:
        raise SystemExit("every run was filtered out")
    print("  after filters: %d runs" % len(runs))

    n_traced = sum(1 for r in runs if r["reasoning"])
    print("  with a reasoning trace: %d   redacted/unavailable: %d"
          % (n_traced, len(runs) - n_traced))
    print("  %-9s %6s %6s %6s %9s %9s" % ("condition", "runs", "answ",
                                          "trunc", "med chars", "elided"))
    for cond in CONDS:
        sel = [r for r in runs if r["metadata"]["condition"] == cond.upper()]
        if not sel:
            continue
        lens = sorted(len(r["reasoning"]) for r in sel)
        print("  %-9s %6d %6d %6d %9d %9d"
              % (cond.upper(), len(sel),
                 sum(1 for r in sel if r["metadata"]["answered"]),
                 sum(1 for r in sel if r["metadata"].get("truncated")),
                 lens[len(lens) // 2],
                 sum(r["metadata"].get("elided_chars") or 0 for r in sel)))

    if args.dump:
        with io.open(args.dump, "w", encoding="utf-8", newline="\n") as f:
            if args.dump.endswith(".json"):
                json.dump([as_agent_run_dict(r) for r in runs], f,
                          ensure_ascii=False, indent=1)
            else:
                for r in runs:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("wrote %s  (%d runs, %.1f MB)"
              % (args.dump, len(runs), os.path.getsize(args.dump) / 1e6))
        return

    if not args.upload:
        raise SystemExit("pass --dump to inspect or --upload to send to Docent")

    from docent import Docent                                          # noqa
    client = Docent(api_key=os.environ["DOCENT_API_KEY"])
    cid = args.collection_id or client.create_collection(
        name=args.collection_name,
        description="TSRBench-160: five one-factor conditions over the 160 "
                    "timestamped items, three models, identical prompts.")
    print("collection:", cid)
    batch = []
    for r in runs:
        batch.append(to_docent(r))
        if len(batch) == 100:
            client.add_agent_runs(cid, batch)
            print("  uploaded %d" % len(batch))
            batch = []
    if batch:
        client.add_agent_runs(cid, batch)
        print("  uploaded %d" % len(batch))
    print("done")


if __name__ == "__main__":
    main()
