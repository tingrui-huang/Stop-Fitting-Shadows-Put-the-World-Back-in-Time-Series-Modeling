"""Run the frozen Paper50 prompts through a locally served Qwen3.6 model.

The prompts under out_paper50_reviewed/<cond>_cli/ are frozen experimental
inputs.  This script only ever reads them, byte for byte, and sends exactly that
text as the user message.  prompts/system.txt is sent unchanged as the system
message.  Nothing under results/paper50_* (the Sonnet runs) is touched.

One structured JSON per instance is written to
results/qwen36/<cond>_raw/<instance_id>.json, holding the thinking trace and the
final answer as separate fields plus the full API response for later audit.

Resume:  an instance whose result file already exists is skipped, so an
interrupted job can simply be relaunched.  --redo-malformed re-runs only those
whose saved final content does not parse into the expected schema; --only re-runs
named ids.

Condition order:  C0 is run on its own.  For C1/C2/C3 the work list is
interleaved with the rotation C1,C2,C3 / C2,C3,C1 / C3,C1,C2 by instance rank,
and the resulting plan is written out so the order is auditable.  Note that each
request is a fresh stateless call, so the order cannot influence any answer.

Usage
  python qwen/run_qwen_paper50.py --conditions C0
  python qwen/run_qwen_paper50.py --conditions C1 C2 C3 --balanced
  python qwen/run_qwen_paper50.py --conditions C0 --only 15 --dry-run
"""

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qwen_common import (ApiError, build_payload, chat_completion,  # noqa: E402
                         load_index, read_prompt, result_record, sha256_file,
                         sha256_text)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI_DIR = os.path.join(ROOT, "out_paper50_reviewed", "%s_cli")
SYSTEM_PROMPT = os.path.join(ROOT, "prompts", "system.txt")
OUT_ROOT = os.path.join(ROOT, "results", "qwen36")
ROTATIONS = (("C1", "C2", "C3"), ("C2", "C3", "C1"), ("C3", "C1", "C2"))


def utcnow():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def raw_dir(cond):
    return os.path.join(OUT_ROOT, "%s_raw" % cond.lower())


def result_path(cond, iid):
    return os.path.join(raw_dir(cond), "%d.json" % iid)


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
                    choices=("C0", "C1", "C2", "C3"))
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--model", default="Qwen/Qwen3.6-35B-A3B")
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
    ap.add_argument("--send-enable-thinking-kwarg", action="store_true",
                    help="additionally send chat_template_kwargs="
                         "{'enable_thinking': true}; only needed if the served "
                         "chat template does not enable thinking by default")
    # ---- run control -------------------------------------------------------
    ap.add_argument("--only", type=int, nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--redo-malformed", action="store_true")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--dry-run", action="store_true",
                    help="build the work list and show what would be sent")
    args = ap.parse_args()

    gen = {"temperature": args.temperature, "top_p": args.top_p,
           "max_tokens": args.max_tokens, "seed": args.seed,
           "presence_penalty": args.presence_penalty,
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

    os.makedirs(OUT_ROOT, exist_ok=True)
    for c in args.conditions:
        os.makedirs(raw_dir(c), exist_ok=True)

    meta = {
        "model": args.model, "base_url": args.base_url,
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
    mpath = os.path.join(OUT_ROOT, "run_metadata_%s.json"
                         % "_".join(c.lower() for c in args.conditions))
    with open(mpath, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print("plan: %d calls  ->  %s" % (len(plan), mpath))

    done = skipped = failed = 0
    failures = []
    for i, cond in plan:
        out_path = result_path(cond, i)
        if os.path.exists(out_path):
            if not args.redo_malformed:
                skipped += 1
                continue
            try:
                with open(out_path, encoding="utf-8") as f:
                    if final_json_ok(json.load(f).get("content")):
                        skipped += 1
                        continue
            except Exception:                                # noqa: BLE001
                pass

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
        fpath = os.path.join(OUT_ROOT, "failures_%s.jsonl"
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
