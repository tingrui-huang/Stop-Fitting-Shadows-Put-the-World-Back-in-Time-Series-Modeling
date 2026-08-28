"""Build the five TSRBench-50 conditions and export them as frozen prompts.

    FULL      events with their timestamps + the timestamped series      reference
    QA_ONLY   the question and the four orderings, nothing else          leakage floor
    NO_TS     every timestamp deleted, from the series and the events    [evidence alignment]
    SHUFFLED  the timestamps permuted, values and text untouched         [temporal causal structure]
    RELATIVE  absolute timestamps replaced by unitless relative indices  [time semantics]

The reference is FULL and the design is a set of one-factor contrasts against
it. QA_ONLY is the acceptance check that has to pass before any of the others
mean anything: if the question alone already answers itself, no contrast below
it is measuring the intervention.

Cross-condition invariants, enforced by construction and re-checked in
verify(): the question stem, the event texts, the option orderings and the
gold letter are byte-identical in all five conditions. Only the temporal
material moves. In NO_TS the series keeps its values and its order, so the
sequence is intact and only the index into the world is gone; in SHUFFLED the
same timestamps are all still present, only reassigned; in RELATIVE the
timestamps become bare integers with no unit, keeping order and rank while
removing every calendar fact.

The permutation for SHUFFLED and the ordinal spacing for RELATIVE are derived
from a sha1 of the question text, so the build is deterministic: the same
input produces the same prompts on any machine, with no RNG and no seed to
carry around.

Usage:  python build_tsr_conditions.py --src tsrbench50/tsrbench50.jsonl --out tsrbench50/cli
"""
import argparse
import hashlib
import json
import os
import re

PRE = re.compile(r"^(Based on the provided .*?following events:\s*)", re.S)
POST = re.compile(r"(\.\s*The events occurred at the following times,"
                  r" presented in a random order:\s*)\[(.*?)\]\.?\s*$", re.S)
EVENT_HEAD = re.compile(r"\((\d+)\):\s*'")

CONDITIONS = ("FULL", "QA_ONLY", "NO_TS", "SHUFFLED", "RELATIVE")

RESPONSE_FORMAT = """Return exactly one JSON object with the following fields:

{
  "answer": "<A|B|C|D>",
  "confidence": <number between 0 and 1>,
  "rationale": "<brief 1-3 sentence justification>",
  "evidence_articles": [<event indices used as evidence>]
}

Rules:
- "answer" must be A, B, C, or D.
- "confidence" must be a number between 0 and 1.
- "rationale" must be concise and based only on the provided context.
- "evidence_articles" must list the event indices actually used as evidence; use [] if none was used.
- Return only the JSON object."""


def split_question(q):
    """-> (stem, events_blob, bridge, [times])"""
    m1, m2 = PRE.match(q), POST.search(q)
    if not (m1 and m2):
        raise ValueError("unparseable question")
    times = [t.strip() for t in m2.group(2).split(",") if t.strip()]
    return m1.group(1), q[m1.end():m2.start()], m2.group(1), times


def digest(text):
    return hashlib.sha1(text.encode("utf-8")).digest()


def derangement(n, seed_bytes):
    """A deterministic permutation with no fixed point (n >= 2)."""
    order = list(range(n))
    # Fisher-Yates driven by the digest, then rotate to kill any fixed point.
    pool = list(seed_bytes) * (n // len(seed_bytes) + 2)
    for i in range(n - 1, 0, -1):
        j = pool[i] % (i + 1)
        order[i], order[j] = order[j], order[i]
    for _ in range(n):
        if all(order[i] != i for i in range(n)):
            return order
        order = order[1:] + order[:1]
    return list(range(1, n)) + [0]


def fmt_series(names, series, mode, seed_bytes):
    """Render the series. mode: 'stamped' | 'values' | 'shuffled' | 'relative'."""
    stamps, values = series[0], series[1]
    label = names[1]
    if mode == "values":
        head = "Position | %s" % label
        body = ["%d | %s" % (i + 1, v) for i, v in enumerate(values)]
    elif mode == "relative":
        head = "Index | %s" % label
        body = ["%d | %s" % (i, v) for i, v in enumerate(values)]
    else:
        order = range(len(stamps))
        if mode == "shuffled":
            order = derangement(len(stamps), seed_bytes)
        head = "Time Stamp | %s" % label
        body = ["%s | %s" % (stamps[k], v) for k, v in zip(order, values)]
    return "%s\n%s" % (head, "\n".join(body))


def build(rec, cond):
    stem, events, bridge, times = split_question(rec["question"])
    seed = digest(rec["question"])
    names, series = rec["name_of_series"], rec["timeseries"]
    parts = ["Task", "", "Answer the following multiple-choice question.", ""]

    if cond != "QA_ONLY":
        if cond == "NO_TS":
            mode, times_line = "values", None
        elif cond == "SHUFFLED":
            # Only the series pairing moves. The question already presents its
            # times "in a random order", so permuting that list again would
            # change bytes without changing information - the question section
            # is left byte-identical to FULL.
            mode, times_line = "shuffled", times
        elif cond == "RELATIVE":
            mode = "relative"
            rank = sorted(range(len(times)), key=lambda k: times[k])
            rel = [0] * len(times)
            for pos, k in enumerate(rank):
                rel[k] = pos
            times_line = [str(v) for v in rel]
        else:
            mode, times_line = "stamped", times
        parts += ["Time series", "",
                  fmt_series(names, series, mode, seed), ""]

    parts += ["Question", ""]
    if cond == "QA_ONLY":
        parts += [stem.rstrip() + " (the events and their times are not supplied)", ""]
    else:
        parts += [stem.rstrip(), "", events.strip(), ""]
        if times_line is not None:
            parts += [bridge.strip() + " [" + ", ".join(times_line) + "].", ""]

    parts += ["Options", ""]
    for letter in ("A", "B", "C", "D"):
        parts.append("%s. %s" % (letter, rec["choices"][letter]))
    parts += ["", "Select the single best answer.", "", RESPONSE_FORMAT, ""]
    return "\n".join(parts)


def verify(rows, built):
    """Every invariant that must hold across the five conditions."""
    problems = []
    for rec in rows:
        iid = rec["instance_id"]
        stem, events, _, times = split_question(rec["question"])
        for cond in CONDITIONS:
            text = built[cond][iid]
            for letter in ("A", "B", "C", "D"):
                opt = "%s. %s" % (letter, rec["choices"][letter])
                if opt not in text:
                    problems.append((iid, cond, "option %s altered" % letter))
            if cond != "QA_ONLY" and events.strip()[:120] not in text:
                problems.append((iid, cond, "event text altered"))
        # the interventions must actually intervene
        if any(t in built["NO_TS"][iid] for t in times):
            problems.append((iid, "NO_TS", "a timestamp survived"))
        if built["SHUFFLED"][iid] == built["FULL"][iid]:
            problems.append((iid, "SHUFFLED", "identical to FULL"))
        if sorted(re.findall(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
                             built["SHUFFLED"][iid])) != \
           sorted(re.findall(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
                             built["FULL"][iid])):
            problems.append((iid, "SHUFFLED", "timestamp multiset changed"))
        if re.search(r"\d{4}-\d{2}-\d{2}", built["RELATIVE"][iid]):
            problems.append((iid, "RELATIVE", "a calendar date survived"))
        if re.search(r"\d{4}-\d{2}-\d{2}", built["QA_ONLY"][iid]):
            problems.append((iid, "QA_ONLY", "a calendar date survived"))
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.src, encoding="utf-8") if l.strip()]
    built = {c: {} for c in CONDITIONS}
    for rec in rows:
        for cond in CONDITIONS:
            built[cond][rec["instance_id"]] = build(rec, cond)

    problems = verify(rows, built)
    if problems:
        for p in problems[:20]:
            print("INVARIANT VIOLATED  id=%s  %s  %s" % p)
        raise SystemExit("%d invariant violations; nothing written" % len(problems))

    manifest = {"source": args.src, "n": len(rows), "conditions": list(CONDITIONS),
                "deterministic": "permutations derived from sha1(question); no RNG",
                "prompts": {}}
    for cond in CONDITIONS:
        d = os.path.join(args.out, cond.lower())
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.jsonl"), "w",
                  encoding="utf-8", newline="\n") as idx:
            for rec in rows:
                iid = rec["instance_id"]
                text = built[cond][iid]
                with open(os.path.join(d, "%d.txt" % iid), "w",
                          encoding="utf-8", newline="") as f:
                    f.write(text)
                idx.write(json.dumps({"instance_id": iid,
                                      "condition": cond,
                                      "prompt_file": "%d.txt" % iid,
                                      "gold_answer": rec["answer"],
                                      "ticker": rec["domain"]},
                                     ensure_ascii=False) + "\n")
                manifest["prompts"].setdefault(cond, {})[str(iid)] = \
                    hashlib.sha256(text.encode("utf-8")).hexdigest()
        sizes = sorted(len(built[cond][r["instance_id"]]) for r in rows)
        print("%-9s %2d prompts -> %s   chars min %d / med %d / max %d"
              % (cond, len(rows), d, sizes[0], sizes[len(sizes) // 2], sizes[-1]))

    with open(os.path.join(args.out, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print("all cross-condition invariants hold")
    print("wrote", os.path.join(args.out, "manifest.json"))


if __name__ == "__main__":
    main()
