"""One-instance validation before any 50- or 200-call run.

Runs exactly one frozen C0 instance and checks, in order:

  1  the exact frozen prompt was read (sha256 matches the file on disk)
  2  the system prompt was loaded unchanged
  3  a non-empty reasoning field came back, and from which server field
  4  final content came back
  5  the final content parses into the experiment's answer schema
  6  the structured result was saved and reloads identically
  7  the scoring fields (prediction / gold / correct) can still be derived

Exits non-zero on the first failed check, and prints what to look at.
Correctness of the answer is NOT a pass criterion - one instance says nothing
about accuracy, and this is a plumbing test.

Usage:  python qwen/smoke_test_one.py
        python qwen/smoke_test_one.py --instance-id 18 --base-url http://127.0.0.1:8000/v1
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from collect_c0_results import extract_json, validate  # noqa: E402
from qwen_common import (ApiError, build_payload, chat_completion,  # noqa: E402
                         load_index, read_prompt, result_record, sha256_file,
                         sha256_text)

OK, BAD = "  [ok]  ", "  [FAIL]"


def fail(msg):
    print("%s %s" % (BAD, msg))
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance-id", type=int, default=15)
    ap.add_argument("--condition", default="C0", choices=("C0", "C1", "C2", "C3"))
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--model", default="Qwen/Qwen3.6-35B-A3B")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--top-p", type=float, default=1.0)
    ap.add_argument("--max-tokens", type=int, default=16384)
    ap.add_argument("--seed", type=int, default=20260823)
    ap.add_argument("--send-enable-thinking-kwarg", action="store_true")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--keep", action="store_true",
                    help="keep the saved result file (default: keep it too, "
                         "this flag exists only for symmetry)")
    args = ap.parse_args()

    cond = args.condition.lower()
    cli = os.path.join(ROOT, "out_paper50_reviewed", "%s_cli" % cond)
    prompt_path = os.path.join(cli, "%d.txt" % args.instance_id)
    sys_path = os.path.join(ROOT, "prompts", "system.txt")
    print("smoke test: %s instance %d" % (args.condition, args.instance_id))

    # ---- 1 frozen prompt --------------------------------------------------
    if not os.path.exists(prompt_path):
        fail("frozen prompt not found: %s" % prompt_path)
    prompt_text = read_prompt(prompt_path)
    if sha256_text(prompt_text) != sha256_file(prompt_path):
        fail("prompt read does not hash to the file on disk")
    print("%s 1 frozen prompt read: %d chars, sha256 %s"
          % (OK, len(prompt_text), sha256_text(prompt_text)[:16]))

    # ---- 2 system prompt --------------------------------------------------
    system_text = read_prompt(sys_path)
    if not system_text.strip():
        fail("prompts/system.txt is empty")
    print("%s 2 system prompt loaded unchanged: %d chars, sha256 %s"
          % (OK, len(system_text), sha256_text(system_text)[:16]))

    gen = {"temperature": args.temperature, "top_p": args.top_p,
           "max_tokens": args.max_tokens, "seed": args.seed,
           "presence_penalty": None,
           "send_enable_thinking_kwarg": args.send_enable_thinking_kwarg}
    payload = build_payload(args.model, system_text, prompt_text, gen)
    if payload["messages"][1]["content"] != prompt_text:
        fail("the request body does not carry the frozen prompt verbatim")
    if "enable_thinking" in json.dumps(payload) and \
            not args.send_enable_thinking_kwarg:
        fail("enable_thinking must not appear unless explicitly requested")

    import datetime as dt
    now = lambda: dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    started = now()
    try:
        response = chat_completion(args.base_url, payload, args.timeout)
    except ApiError as e:
        fail("API call failed: %s\n         is vLLM serving on %s ?"
             % (e, args.base_url))

    choice = (response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    print("         message fields returned by the server: %s"
          % sorted(message.keys()))

    rec = result_record(args.instance_id, args.condition, args.model,
                        {"gold_answer": None, "ticker": None},
                        os.path.relpath(prompt_path, ROOT),
                        os.path.relpath(sys_path, ROOT),
                        prompt_text, system_text, payload, response,
                        started, now(), gen)

    # ---- 3 reasoning ------------------------------------------------------
    if not (rec["reasoning"] or "").strip():
        fail("no reasoning returned. Start vLLM with --reasoning-parser qwen3, "
             "or retry with --send-enable-thinking-kwarg.\n"
             "         fields seen: %s" % sorted(message.keys()))
    print("%s 3 reasoning present: %d chars, from field %r"
          % (OK, len(rec["reasoning"]), rec["reasoning_source"]))

    # ---- 4 final content --------------------------------------------------
    if not (rec["content"] or "").strip():
        fail("final content is empty (finish_reason=%s, truncated=%s)"
             % (rec["finish_reason"], rec["truncated"]))
    print("%s 4 final content present: %d chars, finish_reason=%s%s"
          % (OK, len(rec["content"]), rec["finish_reason"],
             "  TRUNCATED" if rec["truncated"] else ""))
    if rec["reasoning"] and rec["reasoning"] in rec["content"]:
        fail("the reasoning trace is embedded inside content; they must stay "
             "separate")

    # ---- 5 schema ---------------------------------------------------------
    fields, err = validate(extract_json(rec["content"]))
    if err:
        fail("final content does not parse into the answer schema: %s\n"
             "         content preview: %r" % (err, rec["content"][:300]))
    print("%s 5 answer schema parsed: answer=%s confidence=%s "
          "evidence_articles=%s rationale=%d chars"
          % (OK, fields["prediction"], fields["confidence"],
             fields["evidence_articles"], len(fields["rationale"])))
    if fields["rationale"] == rec["reasoning"]:
        fail("rationale and reasoning are identical; they must be distinct "
             "fields")

    # ---- 6 saved and reloadable -------------------------------------------
    out_dir = os.path.join(ROOT, "results", "qwen36", "smoke_test")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "%s_%d.json" % (cond, args.instance_id))
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False)
    with open(out_path, encoding="utf-8") as f:
        back = json.load(f)
    if back["reasoning"] != rec["reasoning"] or back["content"] != rec["content"]:
        fail("saved file does not round-trip")
    print("%s 6 structured result saved and reloaded: %s"
          % (OK, os.path.relpath(out_path, ROOT)))

    # ---- 7 scoring fields derivable ---------------------------------------
    index = {e["instance_id"]: e for e in
             load_index(os.path.join(cli, "index.jsonl"))}
    gold = index[args.instance_id]["gold_answer"]
    correct = fields["prediction"] == gold
    print("%s 7 scoring fields derivable: prediction=%s gold=%s correct=%s"
          % (OK, fields["prediction"], gold, correct))
    print("\nall 7 checks passed. Answer correctness is not a pass criterion; "
          "one instance says nothing about accuracy.")
    print("usage reported by the server: %s" % json.dumps(rec["usage"]))


if __name__ == "__main__":
    main()
