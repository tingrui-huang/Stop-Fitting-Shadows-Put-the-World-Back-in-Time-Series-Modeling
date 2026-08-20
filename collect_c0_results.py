"""Collect raw Claude CLI outputs for the C0 pilot into one scored-ready JSONL.

Reads   out/c0_cli/index.jsonl     (instance list + gold answers)
        results/c0_raw/<id>.txt    (one saved CLI stdout per instance)
Writes  results/c0_sonnet5.jsonl   (one parsed record per valid output)
        results/c0_collect_report.json  (missing / malformed instance ids)

The raw text is preserved verbatim in "raw_output"; parsed fields are stored
separately.  Gold answers come from the index and are never overwritten.
Malformed or missing outputs are reported, never guessed at or repaired.

Usage:  python collect_c0_results.py [--raw-dir results/c0_raw]
                                     [--out results/c0_sonnet5.jsonl]
                                     [--model sonnet-5]
"""

import argparse
import json
import os

VALID_ANSWERS = ("A", "B", "C", "D")


def read_text(path):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def json_candidates(text):
    """Yield every balanced {...} span in text, outermost first, left to right."""
    depth, start, in_str, esc = 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth:
                depth -= 1
                if depth == 0:
                    yield text[start:i + 1]


def extract_json(text):
    """Locate the model's JSON object, tolerating markdown fences and stray prose."""
    for candidate in json_candidates(text):
        try:
            obj = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(obj, dict) and "answer" in obj:
            return obj
    return None


def validate(obj):
    """Return (record_fields, error). error is None when the object is usable."""
    if obj is None:
        return None, "no JSON object with an 'answer' field found"

    answer = obj.get("answer")
    if not isinstance(answer, str) or answer.strip().upper() not in VALID_ANSWERS:
        return None, "answer is not one of A/B/C/D: %r" % (answer,)

    conf = obj.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        return None, "confidence is not a number: %r" % (conf,)
    if not 0.0 <= float(conf) <= 1.0:
        return None, "confidence out of [0, 1]: %r" % (conf,)

    rationale = obj.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        return None, "rationale missing or empty"

    evidence = obj.get("evidence_articles")
    if not isinstance(evidence, list):
        return None, "evidence_articles is not a list: %r" % (evidence,)

    return {
        "prediction": answer.strip().upper(),
        "confidence": float(conf),
        "rationale": rationale.strip(),
        "evidence_articles": evidence,
    }, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=os.path.join("out", "c0_cli", "index.jsonl"))
    ap.add_argument("--raw-dir", default=os.path.join("results", "c0_raw"))
    ap.add_argument("--out", default=os.path.join("results", "c0_sonnet5.jsonl"))
    ap.add_argument("--report", default=os.path.join("results", "c0_collect_report.json"))
    ap.add_argument("--model", default="sonnet-5")
    args = ap.parse_args()

    with open(args.index, encoding="utf-8") as f:
        index = [json.loads(line) for line in f if line.strip()]

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    missing, malformed, n_ok = [], [], 0

    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        for entry in index:
            iid = entry["instance_id"]
            raw_path = os.path.join(args.raw_dir, "%d.txt" % iid)
            if not os.path.exists(raw_path):
                missing.append(iid)
                continue

            raw = read_text(raw_path)
            fields, error = validate(extract_json(raw))
            if error:
                malformed.append({"instance_id": iid, "reason": error,
                                  "raw_file": raw_path})
                continue

            gold = entry["gold_answer"]
            out.write(json.dumps({
                "instance_id": iid,
                "model": args.model,
                "prediction": fields["prediction"],
                "confidence": fields["confidence"],
                "rationale": fields["rationale"],
                "evidence_articles": fields["evidence_articles"],
                "gold_answer": gold,
                "correct": fields["prediction"] == gold,
                "raw_output": raw,
            }, ensure_ascii=False) + "\n")
            n_ok += 1

    report = {
        "model": args.model,
        "index": args.index,
        "raw_dir": args.raw_dir,
        "n_total": len(index),
        "n_parsed": n_ok,
        "n_missing": len(missing),
        "n_malformed": len(malformed),
        "missing_instance_ids": missing,
        "malformed": malformed,
    }
    with open(args.report, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("parsed %d/%d raw outputs -> %s" % (n_ok, len(index), args.out))
    if missing:
        print("MISSING raw output for %d instance(s): %s"
              % (len(missing), ", ".join(str(i) for i in missing)))
    for m in malformed:
        print("MALFORMED %d (%s): %s" % (m["instance_id"], m["raw_file"], m["reason"]))
    print("report: %s" % args.report)


if __name__ == "__main__":
    main()
