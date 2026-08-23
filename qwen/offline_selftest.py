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
from qwen_common import (DEFAULT_MODEL, DEFAULT_RUN_TAG, model_label,  # noqa
                         out_root, raw_dir, result_path, result_record,
                         split_message)

ALT_MODEL = "Qwen/Qwen3.5-9B"
ALT_RUN_TAG = "qwen35_9b"

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

    # ---- two run targets must not collide ----------------------------------
    check("default target is unchanged: %s -> results/%s/"
          % (DEFAULT_MODEL, DEFAULT_RUN_TAG),
          DEFAULT_MODEL == "Qwen/Qwen3.6-35B-A3B"
          and DEFAULT_RUN_TAG == "qwen36"
          and out_root(DEFAULT_RUN_TAG).replace("\\", "/")
          .endswith("results/qwen36"))
    check("alternate target resolves to results/%s/" % ALT_RUN_TAG,
          out_root(ALT_RUN_TAG).replace("\\", "/")
          .endswith("results/%s" % ALT_RUN_TAG))
    check("the two output roots are different directories",
          out_root(DEFAULT_RUN_TAG) != out_root(ALT_RUN_TAG))
    for cond in ("C0", "C1", "C2", "C3"):
        same = raw_dir(DEFAULT_RUN_TAG, cond) == raw_dir(ALT_RUN_TAG, cond)
        check("  %s raw dirs are disjoint" % cond, not same)
    check("per-instance result paths never collide",
          result_path(DEFAULT_RUN_TAG, "C0", 15)
          != result_path(ALT_RUN_TAG, "C0", 15))
    check("neither output root escapes results/",
          all(os.path.dirname(out_root(t)).replace("\\", "/")
              .endswith("/results") for t in (DEFAULT_RUN_TAG, ALT_RUN_TAG)))
    check("default model label reproduces the existing one",
          model_label(DEFAULT_MODEL) == "qwen3.6-35b-a3b",
          model_label(DEFAULT_MODEL))
    check("alternate model label is distinct",
          model_label(ALT_MODEL) == "qwen3.5-9b"
          and model_label(ALT_MODEL) != model_label(DEFAULT_MODEL))
    for bad_tag in ("../escape", "a/b", "", "-x"):
        try:
            out_root(bad_tag)
            rejected = False
        except SystemExit:
            rejected = True
        check("run tag %r is rejected" % bad_tag, rejected)

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
        shutil.copytree(os.path.join(ROOT, "out_paper50_reviewed", "c0_cli"),
                        os.path.join(tmp, "out_paper50_reviewed", "c0_cli"))
        os.makedirs(os.path.join(tmp, "qwen"), exist_ok=True)
        for f in ("collect_qwen_results.py", "qwen_common.py"):
            shutil.copy(os.path.join(HERE, f), os.path.join(tmp, "qwen", f))
        shutil.copy(os.path.join(ROOT, "collect_c0_results.py"), tmp)
        shutil.copy(os.path.join(ROOT, "score_c0.py"), tmp)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")

        # both configurations are driven end to end, in the same sandbox, so a
        # collision between their output trees would show up here
        for model, tag, want_label in (
                (DEFAULT_MODEL, DEFAULT_RUN_TAG, "qwen3.6-35b-a3b"),
                (ALT_MODEL, ALT_RUN_TAG, "qwen3.5-9b")):
            print("  -- %s -> results/%s/" % (model, tag))
            rec = result_record(iid, "C0", model, entry,
                                os.path.relpath(prompt_path, ROOT),
                                "prompts/system.txt", prompt_text, system_text,
                                {}, response, "t0", "t1", gen)
            check("record keeps reasoning and content apart",
                  rec["reasoning"] == THINK and rec["content"] != THINK)
            check("record carries the prompt sha256 that was sent",
                  len(rec["prompt_sha256"]) == 64)
            check("truncation flag follows finish_reason",
                  rec["truncated"] is False)
            check("raw record names the requested model", rec["model"] == model)

            rawd = os.path.join(tmp, "results", tag, "c0_raw")
            os.makedirs(rawd)
            with open(os.path.join(rawd, "%d.json" % iid), "w",
                      encoding="utf-8", newline="\n") as f:
                json.dump(rec, f, indent=2, ensure_ascii=False)

            r1 = subprocess.run([sys.executable, "qwen/collect_qwen_results.py",
                                 "--condition", "C0", "--model", model,
                                 "--run-tag", tag],
                                cwd=tmp, env=env, capture_output=True, text=True)
            check("collector runs", r1.returncode == 0, r1.stderr[-400:])
            out = os.path.join(tmp, "results", tag, "c0_%s.jsonl" % tag)
            check("collector writes results/%s/c0_%s.jsonl" % (tag, tag),
                  os.path.exists(out))
            rows = [json.loads(l) for l in open(out, encoding="utf-8")
                    if l.strip()]
            check("collector emits one scored record", len(rows) == 1)
            check("collected record preserves reasoning",
                  rows and rows[0]["reasoning"] == THINK)
            check("collected record has the scoring fields",
                  rows and all(k in rows[0] for k in
                               ("prediction", "confidence", "rationale",
                                "evidence_articles", "gold_answer", "correct")))
            check("scoring label follows the requested model (%s)" % want_label,
                  rows and rows[0]["model"] == want_label,
                  rows and str(rows[0]["model"]))
            check("model_id preserved verbatim",
                  rows and rows[0]["model_id"] == model)
            r2 = subprocess.run(
                [sys.executable, "score_c0.py",
                 "--results", "results/%s/c0_%s.jsonl" % (tag, tag),
                 "--index", "out_paper50_reviewed/c0_cli/index.jsonl",
                 "--report", "results/%s/c0_collect_report.json" % tag,
                 "--summary", "results/%s/c0_summary.json" % tag],
                cwd=tmp, env=env, capture_output=True, text=True)
            check("unmodified score_c0.py consumes the JSONL",
                  r2.returncode == 0, r2.stderr[-400:])
            summary = json.load(open(os.path.join(tmp, "results", tag,
                                                  "c0_summary.json"),
                                     encoding="utf-8"))
            check("summary reports 49 missing of 50 (one synthetic record)",
                  summary["n_total"] == 50 and summary["n_missing"] == 49,
                  json.dumps(summary)[:200])
            check("summary names the right model", summary["model"] == want_label,
                  str(summary["model"]))

            # a wrong --model against these raw files must be reported
            r3 = subprocess.run([sys.executable, "qwen/collect_qwen_results.py",
                                 "--condition", "C0", "--model", "Qwen/Not-Me",
                                 "--run-tag", tag],
                                cwd=tmp, env=env, capture_output=True, text=True)
            rep = json.load(open(os.path.join(tmp, "results", tag,
                                              "c0_collect_report.json"),
                                 encoding="utf-8"))
            check("a mismatched --model is flagged, not absorbed",
                  r3.returncode == 0 and rep["n_model_mismatch"] == 1)

            # malformed final JSON must still keep the thinking trace
            bad = dict(rec, content="I think the answer is probably C.")
            with open(os.path.join(rawd, "%d.json" % iid), "w",
                      encoding="utf-8", newline="\n") as f:
                json.dump(bad, f, indent=2, ensure_ascii=False)
            subprocess.run([sys.executable, "qwen/collect_qwen_results.py",
                            "--condition", "C0", "--model", model,
                            "--run-tag", tag],
                           cwd=tmp, env=env, capture_output=True, text=True)
            rep = json.load(open(os.path.join(tmp, "results", tag,
                                              "c0_collect_report.json"),
                                 encoding="utf-8"))
            check("malformed final JSON is reported, not guessed at",
                  rep["n_malformed"] == 1)
            check("malformed entry still records the reasoning length",
                  rep["malformed"][0]["reasoning_chars"] == len(THINK))

        # the two runs coexisted without touching each other
        trees = sorted(os.listdir(os.path.join(tmp, "results")))
        check("both output trees exist side by side: %s" % trees,
              trees == sorted([DEFAULT_RUN_TAG, ALT_RUN_TAG]))
        a = json.load(open(os.path.join(tmp, "results", DEFAULT_RUN_TAG,
                                        "c0_summary.json"), encoding="utf-8"))
        b = json.load(open(os.path.join(tmp, "results", ALT_RUN_TAG,
                                        "c0_summary.json"), encoding="utf-8"))
        check("the two summaries record different models",
              a["model"] != b["model"], "%s vs %s" % (a["model"], b["model"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%s" % ("all offline checks passed" if ok else "SOME CHECKS FAILED"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
