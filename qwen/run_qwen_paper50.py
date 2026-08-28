"""Run the frozen Paper50 prompts through a locally served Qwen model.

Model-agnostic: --model names the model sent to the server and recorded in
every result, --run-tag names the output tree.  The defaults reproduce the
original run exactly (Qwen/Qwen3.6-35B-A3B -> results/qwen36/).

The prompts under out_paper50_reviewed/<cond>_cli/ are frozen experimental
inputs.  This script only ever reads them, byte for byte, and sends exactly that
text as the user message.  The system prompt is sent unchanged as the
system message; it is prompts/system.txt unless --system-prompt names
another file.  Nothing under results/paper50_* (the Sonnet runs) is touched.

One structured JSON per instance is written to
results/<run-tag>/<cond>_raw/<instance_id>.json, holding the thinking trace and
the final answer as separate fields plus the full API response for later audit.

Resume:  an instance whose result file already exists is skipped, so an
interrupted job can simply be relaunched.  --redo-malformed re-runs those whose
saved final content does not parse; --redo-truncated re-runs only those that
exhausted the completion ceiling without leaving a usable final answer; --only
re-runs named ids.  A result whose final answer parses is never re-run, whatever
flags are given, so a completed instance cannot be overwritten by a later pass.

Condition order:  C0 is run on its own.  For C1/C2/C3 the work list is
interleaved with the rotation C1,C2,C3 / C2,C3,C1 / C3,C1,C2 by instance rank,
and the resulting plan is written out so the order is auditable.  Note that each
request is a fresh stateless call, so the order cannot influence any answer.

Usage
  python qwen/run_qwen_paper50.py --conditions C0
  python qwen/run_qwen_paper50.py --conditions C1 C2 C3 --balanced
  python qwen/run_qwen_paper50.py --conditions C0 --only 15 --dry-run
  python qwen/run_qwen_paper50.py --conditions C0 --model Qwen/Qwen3.5-9B --run-tag qwen35_9b
  python qwen/run_qwen_paper50.py --conditions C0 --run-tag qwen35_9b --redo-truncated --max-tokens 22000
"""

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qwen_common import (ApiError, add_target_args, build_payload,  # noqa: E402
                         chat_completion, load_index, out_root, raw_dir,
                         read_prompt, result_path, result_record, sha256_file,
                         sha256_text)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CLI_DIR = "out_paper50_reviewed/%s_cli"
PAPER50_CONDITIONS = ("C0", "C1", "C2", "C3")
CLI_DIR = os.path.join(ROOT, DEFAULT_CLI_DIR)
DEFAULT_SYSTEM_PROMPT = os.path.join("prompts", "system.txt")
SYSTEM_PROMPT = os.path.join(ROOT, DEFAULT_SYSTEM_PROMPT)
ROTATIONS = (("C1", "C2", "C3"), ("C2", "C3", "C1"), ("C3", "C1", "C2"))


def utcnow():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def final_json_ok(content):
    """Cheap local check used only to decide whether --redo-malformed applies.

    The authoritative parse lives in qwen/collect_qwen_results.py, which reuses
    the Sonnet collector's own extract_json/validate.
    """
    if not isinstance(content, str) or not content.strip():
        return False
    try:
        sys.path.insert(0, ROOT)
        from collect_c0_results import extract_json, validate
    except Exception:                                        # noqa: BLE001
        return "\"answer\"" in content
    fields, err = validate(extract_json(content))
    return err is None


def should_rerun(out_path, redo_malformed, redo_truncated):
    """Decide what to do with an existing result file -> (rerun, why).

    Invariant: a result whose final answer parses is NEVER rerun, whatever
    flags are given.  Only a file that carries no usable answer can be
    reconsidered, so a completed instance can never be overwritten by a later
    pass.
    """
    try:
        with open(out_path, encoding="utf-8") as f:
            rec = json.load(f)
    except Exception:                                        # noqa: BLE001
        return True, "existing result file is unreadable"
    if final_json_ok(rec.get("content")):
        return False, "valid result"
    if redo_malformed:
        return True, "final JSON does not parse (--redo-malformed)"
    if redo_truncated and rec.get("truncated"):
        return True, ("hit the completion ceiling with no usable final answer "
                      "(--redo-truncated)")
    return False, "no usable answer, but no redo flag covers it"


def work_list(conditions, balanced, only):
    """-> [(instance_id, condition)] in the order requests will be issued."""
    idx = {c: load_index(os.path.join(CLI_DIR % c.lower(), "index.jsonl"))
           for c in conditions}
    ids = {c: [e["instance_id"] for e in idx[c]] for c in conditions}
    if only:
        ids = {c: [i for i in v if i in set(only)] for c, v in ids.items()}
    if balanced and set(conditions) == {"C1", "C2", "C3"}:
        base = sorted(ids["C1"])
        assert all(sorted(ids[c]) == base for c in conditions), \
            "C1/C2/C3 indexes cover different instances"
        out = []
        for rank, iid in enumerate(base):
            for cond in ROTATIONS[rank % 3]:
                out.append((iid, cond))
        return out, idx
    out = []
    for c in conditions:
        for i in sorted(ids[c]):
            out.append((i, c))
    return out, idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conditions", nargs="+", required=True,
                    help="C0/C1/C2/C3, or any condition whose frozen "
                         "prompts sit under --cli-dir, such as S1_QO_ONLY "
                         "with --cli-dir sanity/cli/%%s")
    ap.add_argument("--cli-dir", default=DEFAULT_CLI_DIR,
                    help="where the frozen prompts live, relative to the "
                         "repository root, with %%s standing for the "
                         "lowercased condition (default: the reviewed "
                         "Paper50 tree)")
    ap.add_argument("--system-prompt", default=DEFAULT_SYSTEM_PROMPT,
                    help="system message file, relative to the "
                         "repository root (default: prompts/system.txt, "
                         "the one every Paper50 run used). Its sha256 is "
                         "recorded in every result, so runs made under "
                         "different system prompts can always be told apart.")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    add_target_args(ap)
    ap.add_argument("--balanced", action="store_true",
                    help="interleave C1/C2/C3 with the rotation "
                         "C1,C2,C3 / C2,C3,C1 / C3,C1,C2 by instance rank")
    # ---- generation settings: explicit, recorded, never silent -------------
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--top-p", type=float, default=1.0)
    ap.add_argument("--max-tokens", type=int, default=16384,
                    help="completion budget covering thinking + final answer")
    ap.add_argument("--seed", type=int, default=20260823)
    ap.add_argument("--presence-penalty", type=float, default=None)
    ap.add_argument("--stream", action="store_true",
                    help="request the completion as a stream and reassemble "
                         "it. Needed when the model sits behind a proxying "
                         "gateway that answers 502 if nothing crosses the "
                         "connection during a long thinking phase. It does "
                         "not change what the model computes, and the stored "
                         "result has the same shape either way.")
    ap.add_argument("--send-enable-thinking-kwarg", action="store_true",
                    help="additionally send chat_template_kwargs="
                         "{'enable_thinking': true}; only needed if the served "
                         "chat template does not enable thinking by default")
    # ---- run control -------------------------------------------------------
    ap.add_argument("--only", type=int, nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--redo-malformed", action="store_true",
                    help="re-run instances whose saved final JSON does not "
                         "parse, whatever the reason")
    ap.add_argument("--redo-truncated", action="store_true",
                    help="re-run only instances that exhausted the completion "
                         "ceiling without leaving a usable final answer; used "
                         "by the length-limit retry pass. A valid result is "
                         "never re-run.")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--dry-run", action="store_true",
                    help="build the work list and show what would be sent")
    args = ap.parse_args()

    global CLI_DIR, SYSTEM_PROMPT
    CLI_DIR = os.path.join(ROOT, args.cli_dir)
    SYSTEM_PROMPT = os.path.join(ROOT, args.system_prompt)
    if not os.path.exists(SYSTEM_PROMPT):
        raise SystemExit("no system prompt at %s" % SYSTEM_PROMPT)
    if args.cli_dir == DEFAULT_CLI_DIR:
        bad = [c for c in args.conditions if c not in PAPER50_CONDITIONS]
        if bad:
            raise SystemExit(
                "%s is not a Paper50 condition. Pass --cli-dir to point at "
                "another frozen prompt tree, e.g. --cli-dir sanity/cli/%%s "
                "--conditions S1_QO_ONLY" % ", ".join(bad))
    for c in args.conditions:
        idx = os.path.join(CLI_DIR % c.lower(), "index.jsonl")
        if not os.path.exists(idx):
            raise SystemExit("no frozen prompt index at %s - check "
                             "--conditions and --cli-dir" % idx)

    gen = {"temperature": args.temperature, "top_p": args.top_p,
           "max_tokens": args.max_tokens, "seed": args.seed,
           "presence_penalty": args.presence_penalty,
           "stream": args.stream,
           "send_enable_thinking_kwarg": args.send_enable_thinking_kwarg}

    system_text = read_prompt(SYSTEM_PROMPT)
    plan, idx = work_list(args.conditions, args.balanced, args.only)
    if args.limit:
        plan = plan[:args.limit]
    entry_by = {c: {e["instance_id"]: e for e in idx[c]} for c in idx}

    if args.dry_run:
        # a dry run inspects the plan and must not touch the filesystem
        print("plan: %d calls (dry run)" % len(plan))
        for i, c in plan[:12]:
            p = os.path.join(CLI_DIR % c.lower(), "%d.txt" % i)
            print("  would send %s/%d  prompt sha256 %s  (%d chars)"
                  % (c, i, sha256_file(p)[:16], len(read_prompt(p))))
        print("  ... (%d total). nothing sent, nothing written." % len(plan))
        return

    os.makedirs(out_root(args.run_tag), exist_ok=True)
    for c in args.conditions:
        os.makedirs(raw_dir(args.run_tag, c), exist_ok=True)

    meta = {
        "model": args.model, "run_tag": args.run_tag,
        "output_root": os.path.relpath(out_root(args.run_tag), ROOT),
        "base_url": args.base_url,
        "conditions": args.conditions, "balanced_order": bool(args.balanced),
        "rotation": [list(r) for r in ROTATIONS] if args.balanced else None,
        "order_balancing_note":
            "the Sonnet Paper50 runs were executed condition by condition; this "
            "rotation is new to the Qwen run, not inherited from them. Each "
            "request is a fresh stateless call, so order cannot affect answers.",
        "generation": dict(gen),
        "thinking": "enabled; enable_thinking=False is never sent",
        "system_prompt_file": os.path.relpath(SYSTEM_PROMPT, ROOT),
        "system_prompt_sha256": sha256_text(system_text),
        "n_planned_calls": len(plan),
        "plan": [{"instance_id": i, "condition": c} for i, c in plan],
        "started_utc": utcnow(),
    }
    mpath = os.path.join(out_root(args.run_tag), "run_metadata_%s.json"
                         % "_".join(c.lower() for c in args.conditions))
    with open(mpath, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print("plan: %d calls  ->  %s" % (len(plan), mpath))

    done = skipped = failed = reran = 0
    failures = []
    for i, cond in plan:
        out_path = result_path(args.run_tag, cond, i)
        if os.path.exists(out_path):
            rerun, why = should_rerun(out_path, args.redo_malformed,
                                      args.redo_truncated)
            if not rerun:
                skipped += 1
                continue
            reran += 1
            print("redo %s/%-4d %s" % (cond, i, why))

        prompt_path = os.path.join(CLI_DIR % cond.lower(), "%d.txt" % i)
        prompt_text = read_prompt(prompt_path)
        payload = build_payload(args.model, system_text, prompt_text, gen)
        started = utcnow()
        try:
            response = chat_completion(args.base_url, payload, args.timeout)
        except ApiError as e:
            failed += 1
            failures.append({"instance_id": i, "condition": cond,
                             "stage": "api_call", "error": str(e),
                             "utc": utcnow()})
            print("FAIL %s/%d  %s" % (cond, i, e))
            continue

        choices = response.get("choices") or []
        if not choices or not isinstance(choices[0].get("message"), dict):
            failed += 1
            failures.append({"instance_id": i, "condition": cond,
                             "stage": "empty_response",
                             "error": "no choices/message in response",
                             "response_preview": json.dumps(response)[:1000],
                             "utc": utcnow()})
            print("FAIL %s/%d  empty response" % (cond, i))
            continue

        rec = result_record(i, cond, args.model,
                            entry_by[cond][i], os.path.relpath(prompt_path, ROOT),
                            os.path.relpath(SYSTEM_PROMPT, ROOT),
                            prompt_text, system_text, payload, response,
                            started, utcnow(), gen)
        if not rec["content"] or not str(rec["content"]).strip():
            # no final answer at all: do not fabricate a result file, keep it
            # rerunnable, but keep the thinking trace in the failure log
            failed += 1
            failures.append({"instance_id": i, "condition": cond,
                             "stage": "missing_final_content",
                             "error": "message content was empty",
                             "finish_reason": rec["finish_reason"],
                             "truncated": rec["truncated"],
                             "reasoning": rec["reasoning"],
                             # An instance that produced no usable answer still
                             # generated tokens, and against a metered endpoint
                             # it is the most expensive kind of instance there
                             # is: it runs the ceiling out by definition. Keep
                             # the usage here or any accounting that reads only
                             # the result files will understate the true spend.
                             "usage": rec["usage"],
                             "utc": utcnow()})
            print("FAIL %s/%d  empty final content (finish_reason=%s)"
                  % (cond, i, rec["finish_reason"]))
            continue

        tmp = out_path + ".part"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)
        os.replace(tmp, out_path)
        done += 1
        print("ok   %s/%-4d finish=%-6s reasoning=%s chars via %s  content=%d chars%s"
              % (cond, i, rec["finish_reason"],
                 len(rec["reasoning"] or ""), rec["reasoning_source"],
                 len(rec["content"] or ""),
                 "  TRUNCATED" if rec["truncated"] else ""))

    if failures:
        fpath = os.path.join(out_root(args.run_tag), "failures_%s.jsonl"
                             % "_".join(c.lower() for c in args.conditions))
        with open(fpath, "a", encoding="utf-8", newline="\n") as f:
            for x in failures:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
        print("logged %d failure(s) to %s (rerun by relaunching the same command)"
              % (len(failures), fpath))

    meta["finished_utc"] = utcnow()
    meta["n_written"] = done
    meta["n_skipped_existing"] = skipped
    meta["n_failed"] = failed
    with open(mpath, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print("\nwritten %d, skipped %d, failed %d" % (done, skipped, failed))


if __name__ == "__main__":
    main()
