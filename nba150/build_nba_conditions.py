"""Build the five conditions of the NBA abductive task and freeze them as prompts.

Source: TSRBench's reasoning/abductive_reasoning.jsonl, all 150 items, a census.
Each item is one NBA game: play-by-play events with their game-clock times, four
numerical channels sampled one-to-one with those events, and a critical moment at
which the model must choose which of four candidate events happened.

The conditions mirror the TSRBench-160 design exactly, so the two tables can be
read side by side:

    QA_ONLY   the question and the four options, nothing else
    FULL      the play-by-play with its game clock, and the numerical channels
    NO_TS     the same, with the time column deleted
    SHUFFLED  the same, with the time column deranged against the rows
    RELATIVE  the same, with the clock replaced by unitless indices

Four things are deliberately withheld from every condition, each because it
answers the question outright:

  critical_moment.after   the score after the event. The delta between before
                          and after identifies exactly one option in 64 of the
                          150 items, and that option is the gold answer in 57
                          of them.
  future_events           the play-by-play continuing past the critical moment.
  future_times            their clock times.
  the future arrays of    284 further values per channel, which encode the same
  the numerical channels  continuation numerically.

QA_ONLY is not only a leakage check here. An audit of the shipped data found
that the option strings alone carry most of the answer: the gold option averages
111 characters against 59 for its distractors, contains a multi-clause "|"
separator in 48 of 150 items and in none of the 450 distractors, and names a
player absent from the game's history in 1 per cent of cases against 67 per cent
for distractors. A solver that keeps only the options whose players have all
appeared and then takes the longest scores 0.820; taking the longest alone
scores 0.540, against a 0.250 chance rate and 0.307 for a constant letter. So
QA_ONLY measures how much of a model's score comes from the option strings
rather than from the game, and FULL minus QA_ONLY is the part that needed the
data at all.

The system prompt is the same frozen file every other run in this study used,
byte for byte. Its opening line names finance, which fits neither this task nor
the GDELT one; it is left alone because holding it constant across both tasks
removes a difference rather than adding one.

Usage:  python nba150/build_nba_conditions.py
        python nba150/build_nba_conditions.py --conditions full qa_only
"""
import argparse
import collections
import hashlib
import io
import json
import os
import random
import re

NL = chr(10)
SRC = "nba150/abductive_reasoning.jsonl"
OUT = "nba150/cli"
SYSTEM = "prompts/system.txt"
SEED = 20260823                      # the seed every other run in the study used
CONDS = ("qa_only", "full", "no_ts", "shuffled", "relative")
GLOSS = {
    "qa_only":  "the question and the four options only - the leakage and "
                "option-artifact check",
    "full":     "play-by-play with its game clock, plus the numerical channels "
                "- the reference",
    "no_ts":    "every game-clock time deleted",
    "shuffled": "the game-clock column deranged against the rows",
    "relative": "the game clock replaced by unitless indices",
}
CHANNELS = [("Team A_Score", "Team A score"),
            ("Team B_Score", "Team B score"),
            ("wp_Team A", "Win prob (A)"),
            ("wp_Team B", "Win prob (B)")]

ANSWER_BLOCK = """Select the single best answer.

Return exactly one JSON object with the following fields:

{
  "answer": "<A|B|C|D>",
  "confidence": <number between 0 and 1>,
  "rationale": "<brief 1-3 sentence justification>",
  "evidence_articles": [<play indices used as evidence>]
}

Rules:
- "answer" must be A, B, C, or D.
- "confidence" must be a number between 0 and 1.
- "rationale" must be concise and based only on the provided context.
- "evidence_articles" must list the play indices actually used as evidence; use [] if none was used.
- Return only the JSON object."""


def derange(seq, rng):
    """A permutation with no fixed point, so no row keeps its own time."""
    n = len(seq)
    if n < 2:
        return list(seq)
    idx = list(range(n))
    while True:
        rng.shuffle(idx)
        if all(idx[i] != i for i in range(n)):
            return [seq[i] for i in idx]


def fmt(v):
    if isinstance(v, float):
        return ("%.3f" % v).rstrip("0").rstrip(".") if v != int(v) else str(int(v))
    return str(v)


def time_column(times, cond, rng):
    if cond == "no_ts":
        return None
    if cond == "relative":
        return [str(i) for i in range(len(times))]
    if cond == "shuffled":
        return derange([str(t) for t in times], rng)
    return [str(t) for t in times]


def render(rec, cond, rng):
    ctx = rec["context"]
    events = ctx["history_events"]
    times = ctx["history_times"]
    ch = rec["numerical_time_series"]
    q = rec["multiple_choice_question"]
    before = rec["critical_moment"]["before"]

    L = ["Task", "", "Answer the following multiple-choice question.", ""]

    if cond != "qa_only":
        info = rec["game_info"]
        L += ["Game", "",
              "%s versus %s, season %s."
              % (info.get("team1"), info.get("team2"), info.get("season")),
              "",
              "Play-by-play up to the critical moment", ""]

        tc = time_column(times, cond, rng)
        head = (["Time"] if tc else []) + ["Play"] + [lab for _, lab in CHANNELS]
        L.append(" | ".join(head))
        for i, ev in enumerate(events):
            row = ([tc[i]] if tc else []) + [str(ev).replace("|", "/")]
            for key, _ in CHANNELS:
                hist = (ch.get(key) or {}).get("history") or []
                row.append(fmt(hist[i]) if i < len(hist) else "")
            L.append(" | ".join(row))
        L.append("")

        L += ["Critical moment", ""]
        when = {"no_ts": "at the next play",
                "relative": "at index %d" % len(events),
                }.get(cond, "at %s" % before.get("time"))
        wp = before.get("win_probability") or {}
        L += ["The question is asked %s, with the score %s and win probability "
              "Team A %s, Team B %s."
              % (when, before.get("score"),
                 fmt(wp.get("Team A")), fmt(wp.get("Team B"))),
              ""]

    L += ["Question", "", str(q["question"]).strip(), "", "Options", ""]
    for letter, choice in zip("ABCD", q["choices"]):
        L.append("%s. %s" % (letter, choice))
    L += ["", ANSWER_BLOCK, ""]
    return NL.join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--conditions", nargs="*", default=list(CONDS))
    args = ap.parse_args()

    recs = [json.loads(l) for l in io.open(args.src, encoding="utf-8")
            if l.strip()]
    print("source items: %d" % len(recs))

    sysraw = io.open(SYSTEM, "rb").read()
    manifest = {
        "source_file": "reasoning/abductive_reasoning.jsonl",
        "source_task": "Abductive Reasoning (NBA play-by-play)",
        "source_sha256": hashlib.sha256(
            io.open(args.src, "rb").read()).hexdigest(),
        "n_items": len(recs),
        "is_census": True,
        "seed": SEED,
        "system_prompt_file": SYSTEM,
        "system_prompt_sha256": hashlib.sha256(sysraw).hexdigest(),
        "withheld": ["critical_moment.after", "context.future_events",
                     "context.future_times",
                     "numerical_time_series.*.future"],
        "conditions": {},
    }

    for cond in args.conditions:
        d = os.path.join(args.out, cond)
        os.makedirs(d, exist_ok=True)
        rng = random.Random("%s-%s" % (SEED, cond))
        index, sizes, letters = [], [], collections.Counter()
        for i, rec in enumerate(recs, 1):
            text = render(rec, cond, rng)
            path = os.path.join(d, "%d.txt" % i)
            with io.open(path, "w", encoding="utf-8", newline=NL) as f:
                f.write(text)
            gold = rec["multiple_choice_question"]["answer"]
            letters[gold] += 1
            sizes.append(len(text))
            index.append({
                "instance_id": i,
                "condition": cond.upper(),
                "prompt_file": "%d.txt" % i,
                "gold_answer": gold,
                "ticker": re.sub(r"_[A-Z][a-z]{2} .*", "",
                                 rec["game_filename"]),
                "game": rec["game_filename"],
                "n_events": len(rec["context"]["history_events"]),
                "prompt_sha256": hashlib.sha256(
                    text.encode("utf-8")).hexdigest(),
            })
        with io.open(os.path.join(d, "index.jsonl"), "w",
                     encoding="utf-8", newline=NL) as f:
            for e in index:
                f.write(json.dumps(e, ensure_ascii=False) + NL)
        sizes.sort()
        manifest["conditions"][cond.upper()] = {
            "gloss": GLOSS[cond],
            "n": len(index),
            "prompt_chars": {"min": sizes[0], "median": sizes[len(sizes) // 2],
                             "max": sizes[-1]},
        }
        print("%-9s %3d prompts   chars min %d median %d max %d -> %s"
              % (cond, len(index), sizes[0], sizes[len(sizes) // 2],
                 sizes[-1], d))

    manifest["gold_answer_counts"] = dict(sorted(letters.items()))
    top = max(letters.values())
    manifest["chance"] = 0.25
    manifest["best_constant_letter"] = round(top / float(len(recs)), 4)
    with io.open("nba150/nba150_manifest.json", "w", encoding="utf-8",
                 newline=NL) as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("gold letters %s   chance 0.250   best constant %.3f"
          % (dict(sorted(letters.items())), top / float(len(recs))))
    print("wrote nba150/nba150_manifest.json")


if __name__ == "__main__":
    main()
