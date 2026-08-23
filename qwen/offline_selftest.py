"""Offline self-test: everything except the GPU call.

Exercises the reasoning/content split against the field names different vLLM
builds use, the <think> fallback, the answer-schema parse, the collector and
score_c0.py - end to end, with a synthetic response, on a temporary copy of the
output tree.  No server needed, and nothing is written outside a temp directory.

Usage:  python qwen/offline_selftest.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from collect_c0_results import extract_json, validate  # noqa: E402
from qwen_common import result_record, split_message  # noqa: E402

FINAL = ('{"answer": "C", "confidence": 0.85, "rationale": "short public '
         'explanation", "evidence_articles": [1]}')
THINK = "Let me work through the series step by step. The P/E fell ..."
ok = True


def check(name, cond, detail=""):
    global ok
    print("%-58s %s%s" % (name, "ok" if cond else "FAIL",
                          "" if cond else "  <- " + detail))
    ok = ok and bool(cond)


def main():
    # ---- field-name probing ------------------------------------------------
    for key in ("reasoning_content", "reasoning", "thinking"):
        r, c, src = split_message({key: THINK, "content": FINAL})
        check("split_message picks up %r" % key,
              r == THINK and c == FINAL and src == key)
    r, c, src = split_message({"content": "<think>%s</think>%s" % (THINK, FINAL)})
    check("split_message falls back to a <think> block",
          r == THINK and c.strip() == FINAL and "think" in src)
    check("fallback does not concatenate reasoning into content",
          THINK not in (c or ""))
    r, c, src = split_message({"content": FINAL})
    check("no reasoning present is reported as absent",
          r is None and c == FINAL and src == "absent")

    # ---- answer schema -----------------------------------------------------
    fields, err = validate(extract_json(FINAL))
    check("final content parses with the Sonnet validator", err is None, str(err))
    check("rationale and reasoning stay distinct",
          fields and fields["rationale"] != THINK)

    # ---- end to end on a temp copy ----------------------------------------
    tmp = tempfile.mkdtemp(prefix="qwen_selftest_")
    try:
        idx_src = os.path.join(ROOT, "out_paper50_reviewed", "c0_cli",
                               "index.jsonl")
        entries = [json.loads(l) for l in open(idx_src, encoding="utf-8")
                   if l.strip()]
        entry = entries[0]
        iid = entry["instance_id"]
        prompt_path = os.path.join(ROOT, "out_paper50_reviewed", "c0_cli",
                                   "%d.txt" % iid)
        prompt_text = open(prompt_path, encoding="utf-8", newline="").read()
        system_text = open(os.path.join(ROOT, "prompts", "system.txt"),
                           encoding="utf-8", newline="").read()
        gold = entry["gold_answer"]
        response = {
            "id": "chatcmpl-selftest",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant",
                                     "reasoning_content": THINK,
                                     "content": FINAL.replace('"C"',
                                                              '"%s"' % gold)}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2,
                      "total_tokens": 3},
        }
        gen = {"temperature": 0.0, "top_p": 1.0, "max_tokens": 16384,
               "seed": 20260823, "presence_penalty": None,
               "send_enable_thinking_kwarg": False}
        rec = result_record(iid, "C0", "Qwen/Qwen3.6-35B-A3B", entry,
                            os.path.relpath(prompt_path, ROOT),
                            "prompts/system.txt", prompt_text, system_text,
                            {}, response, "t0", "t1", gen)
        check("record keeps reasoning and content apart",
              rec["reasoning"] == THINK and rec["content"] != THINK)
        check("record carries the prompt sha256 that was sent",
              len(rec["prompt_sha256"]) == 64)
        check("truncation flag follows finish_reason", rec["truncated"] is False)

        raw_dir = os.path.join(tmp, "results", "qwen36", "c0_raw")
        os.makedirs(raw_dir)
        with open(os.path.join(raw_dir, "%d.json" % iid), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)
        shutil.copytree(os.path.join(ROOT, "out_paper50_reviewed", "c0_cli"),
                        os.path.join(tmp, "out_paper50_reviewed", "c0_cli"))
        os.makedirs(os.path.join(tmp, "qwen"), exist_ok=True)
        for f in ("collect_qwen_results.py", "qwen_common.py"):
            shutil.copy(os.path.join(HERE, f), os.path.join(tmp, "qwen", f))
        shutil.copy(os.path.join(ROOT, "collect_c0_results.py"), tmp)
        shutil.copy(os.path.join(ROOT, "score_c0.py"), tmp)

        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        r1 = subprocess.run([sys.executable, "qwen/collect_qwen_results.py",
                             "--condition", "C0"], cwd=tmp, env=env,
                            capture_output=True, text=True)
        check("collector runs", r1.returncode == 0, r1.stderr[-400:])
        out = os.path.join(tmp, "results", "qwen36", "c0_qwen36.jsonl")
        rows = [json.loads(l) for l in open(out, encoding="utf-8") if l.strip()]
        check("collector emits one scored record", len(rows) == 1)
        check("collected record preserves reasoning",
              rows and rows[0]["reasoning"] == THINK)
        check("collected record has the scoring fields",
              rows and all(k in rows[0] for k in
                           ("prediction", "confidence", "rationale",
                            "evidence_articles", "gold_answer", "correct")))
        r2 = subprocess.run(
            [sys.executable, "score_c0.py",
             "--results", "results/qwen36/c0_qwen36.jsonl",
             "--index", "out_paper50_reviewed/c0_cli/index.jsonl",
             "--report", "results/qwen36/c0_collect_report.json",
             "--summary", "results/qwen36/c0_summary.json"],
            cwd=tmp, env=env, capture_output=True, text=True)
        check("unmodified score_c0.py consumes the Qwen JSONL",
              r2.returncode == 0, r2.stderr[-400:])
        summary = json.load(open(os.path.join(tmp, "results", "qwen36",
                                              "c0_summary.json"),
                                 encoding="utf-8"))
        check("summary reports 49 missing of 50 (only one synthetic record)",
              summary["n_total"] == 50 and summary["n_missing"] == 49,
              json.dumps(summary)[:200])

        # malformed final JSON must still keep the thinking trace
        bad = dict(rec, content="I think the answer is probably C.")
        with open(os.path.join(raw_dir, "%d.json" % iid), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(bad, f, indent=2, ensure_ascii=False)
        subprocess.run([sys.executable, "qwen/collect_qwen_results.py",
                        "--condition", "C0"], cwd=tmp, env=env,
                       capture_output=True, text=True)
        rep = json.load(open(os.path.join(tmp, "results", "qwen36",
                                          "c0_collect_report.json"),
                             encoding="utf-8"))
        check("malformed final JSON is reported, not guessed at",
              rep["n_malformed"] == 1)
        check("malformed entry still records the reasoning length",
              rep["malformed"][0]["reasoning_chars"] == len(THINK))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%s" % ("all offline checks passed" if ok else "SOME CHECKS FAILED"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
