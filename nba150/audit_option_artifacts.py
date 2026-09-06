"""How far can a solver get on TSRBench's NBA abductive task without the data?

Run before spending anything on this task, and reported whatever it finds.
Every solver below reads only the four option strings and, at most, which
player numbers appear in the game's play-by-play. None reads a timestamp, a
score, or a win probability. Whatever they score is available in every
condition of an ablation, so it is a floor that no ablation can move: if the
floor is above what the models reach, the ablation measures nothing about
timestamps.

The asymmetries these exploit are properties of how the shipped item was
built, not of basketball. The gold option is lifted verbatim from the game's
own play-by-play, so it carries that stream's formatting - the multi-clause
separator, the assist clause - and names only players who are in the game. The
distractors are drawn from elsewhere, so they are shorter, plainer, and two
thirds of them name a player the game never mentions.

Usage:  python nba150/audit_option_artifacts.py
"""
import collections
import io
import json
import re
import statistics

SRC = "nba150/abductive_reasoning.jsonl"
PLAYER = re.compile(r"Player \d+ \(Team [AB]\)")
TEAM = re.compile(r"\(Team ([AB])\)")


def seen_players(rec):
    seen = set()
    for e in rec["context"]["history_events"]:
        seen |= set(PLAYER.findall(e))
    return seen


def score(recs, pick, name):
    """pick(record) -> chosen index, or None to abstain (scored at 1/4)."""
    hit = abstain = 0.0
    for r in recs:
        q = r["multiple_choice_question"]
        g = "ABCD".index(q["answer"])
        i = pick(r)
        if i is None:
            abstain += 1
            hit += 0.25
        else:
            hit += (i == g)
    print("  %-48s %.3f   abstained %3d" % (name, hit / len(recs), abstain))
    return hit / len(recs)


def main():
    recs = [json.loads(l) for l in io.open(SRC, encoding="utf-8") if l.strip()]
    n = len(recs)
    letters = collections.Counter(
        r["multiple_choice_question"]["answer"] for r in recs)
    print("items: %d" % n)
    print("gold letters: %s" % dict(sorted(letters.items())))

    print("\nSOLVERS THAT NEVER READ THE TIME SERIES")
    print("  %-48s %s" % ("", "accuracy"))
    print("  %-48s %.3f" % ("chance", 0.25))
    print("  %-48s %.3f" % ("best constant letter",
                            max(letters.values()) / float(n)))

    def longest(r):
        c = r["multiple_choice_question"]["choices"]
        return max(range(len(c)), key=lambda i: len(c[i]))
    score(recs, longest, "longest option")

    def pipe(r):
        c = r["multiple_choice_question"]["choices"]
        w = [i for i, ch in enumerate(c) if "|" in ch]
        return w[0] if len(w) == 1 else None
    score(recs, pipe, "the one option containing a '|' separator")

    def familiar(r):
        seen = seen_players(r)
        c = r["multiple_choice_question"]["choices"]
        ok = [i for i, ch in enumerate(c) if not (set(PLAYER.findall(ch)) - seen)]
        return ok[0] if len(ok) == 1 else None
    score(recs, familiar, "the one option whose players all appeared")

    def combo(r):
        seen = seen_players(r)
        c = r["multiple_choice_question"]["choices"]
        ok = [i for i, ch in enumerate(c)
              if not (set(PLAYER.findall(ch)) - seen)] or list(range(len(c)))
        return max(ok, key=lambda i: len(c[i]))
    score(recs, combo, "players-all-appeared, then longest")

    print("\nWHERE THE ASYMMETRY COMES FROM")
    rows = {"gold": collections.Counter(), "distractor": collections.Counter()}
    lens = {"gold": [], "distractor": []}
    for r in recs:
        q = r["multiple_choice_question"]
        gi = "ABCD".index(q["answer"])
        seen = seen_players(r)
        for i, ch in enumerate(q["choices"]):
            tag = "gold" if i == gi else "distractor"
            rows[tag]["n"] += 1
            rows[tag]["assist"] += "assist" in ch.lower()
            rows[tag]["pipe"] += "|" in ch
            rows[tag]["unseen"] += bool(set(PLAYER.findall(ch)) - seen)
            rows[tag]["players"] += len(set(PLAYER.findall(ch)))
            lens[tag].append(len(ch))
    print("  %-12s %6s %10s %10s %12s %10s"
          % ("", "n", "mean len", "has '|'", "unseen player", "assist"))
    for tag in ("gold", "distractor"):
        c = rows[tag]
        print("  %-12s %6d %10.1f %9.0f%% %11.0f%% %9.0f%%"
              % (tag, c["n"], statistics.mean(lens[tag]),
                 100.0 * c["pipe"] / c["n"], 100.0 * c["unseen"] / c["n"],
                 100.0 * c["assist"] / c["n"]))
    print("\n  A '|' in an option is a perfect positive tell: %d golds carry one"
          % rows["gold"]["pipe"])
    print("  and %d of the %d distractors do."
          % (rows["distractor"]["pipe"], rows["distractor"]["n"]))


if __name__ == "__main__":
    main()
