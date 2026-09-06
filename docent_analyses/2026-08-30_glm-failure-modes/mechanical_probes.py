"""Cheap, deterministic probes for the failure modes that admit one.

These are not the labelling. They are the vetting step before it: they answer,
for free and over every run rather than a sample of 48, whether a proposed mode
is worth a row in the table at all. A mode is worth a row if its rate moves
between conditions; a row that is near zero everywhere, or near one hundred
everywhere, occupies space in the figure and shows nothing.

Four of the ten proposed modes have a mechanical proxy:

  external_calendar_reconstruction  a year in the trace that does not appear in
                                    that run's own prompt. This has to be
                                    per-run: the event summaries carry years of
                                    their own, so 112 of 160 NO_TS prompts
                                    contain one even though every timestamp was
                                    deleted, and a corpus-wide keyword count
                                    would be meaningless.
  goldstein_valence_matching        a valence word within 120 characters of a
                                    mention of the scale
  goldstein_code_reverse_lookup     the string CAMEO, which appears in no prompt
  mechanical_reasoning_repetition   8-word shingle duplication, the same measure
                                    that decided which traces could be elided

and one behaviour that is not a failure at all but is the baseline the failures
are read against:

  acknowledged_underdetermination   the model saying the pairing cannot be
                                    recovered from what it was given

A proxy is a lower bound with a false-positive rate of its own, so the numbers
here are for deciding which rows to keep, not for the paper. The LLM labelling
is what fills the cells.

Run:  python docent_analyses/2026-08-30_glm-failure-modes/mechanical_probes.py
"""
import glob
import io
import json
import os
import re
import sys

ROOT = "results/tsrbench160_glm53flash_zai"
PROMPTS = "tsrbench160/cli/%s"
CONDS = ("full", "shuffled", "no_ts", "relative")

YEAR = re.compile(r"\b(?:19|20)[0-9]{2}\b")
CAMEO = re.compile(r"\bCAMEO\b", re.I)
SCALE = re.compile(r"goldstein", re.I)
VALENCE = re.compile(
    r"\b(negative|positive|severe|severity|sentiment|tone|conflict|"
    r"cooperat\w*|escalat\w*|violent|violence|hostil\w*|friendly|"
    r"bad news|good news|worse|better)\b", re.I)
UNDET = re.compile(
    r"(cannot|can't|can not|unable to|no way to|impossible to)\s+"
    r"(be\s+)?(determine|know|tell|establish|recover|infer|match|identify)"
    r"|not enough information|insufficient information"
    r"|underdetermined|not determined by|arbitrary(ly)? (choice|order|guess)"
    r"|no basis (for|to)|nothing (in the prompt|here) (tells|says|determines)",
    re.I)


def shingle_dup(text, k=8):
    w = re.findall(r"[a-z0-9()]+", text.lower())
    if len(w) < k + 1:
        return 0.0
    sh = [" ".join(w[i:i + k]) for i in range(len(w) - k + 1)]
    return 1.0 - len(set(sh)) / len(sh)


def valence_near_scale(text, window=120):
    for m in SCALE.finditer(text):
        seg = text[max(0, m.start() - window):m.end() + window]
        if VALENCE.search(seg):
            return True
    return False


def runs(cond):
    """(instance_id, trace, answered) for every run, from both stores."""
    seen = set()
    for p in sorted(glob.glob(os.path.join(ROOT, "%s_raw" % cond, "*.json"))):
        r = json.load(io.open(p, encoding="utf-8"))
        seen.add(int(r["instance_id"]))
        yield int(r["instance_id"]), (r.get("reasoning") or ""), True
    fp = os.path.join(ROOT, "failures_%s.jsonl" % cond)
    if not os.path.exists(fp):
        return
    best = {}
    for line in io.open(fp, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            i = int(r["instance_id"])
            if len(r.get("reasoning") or "") > len(
                    (best.get(i) or {}).get("reasoning") or ""):
                best[i] = r
    for i in sorted(best):
        if i not in seen and (best[i].get("reasoning") or ""):
            yield i, best[i]["reasoning"], False


def main():
    rows = {}
    for cond in CONDS:
        n = imported_year = cameo = valence = undet = repet = 0
        n_nt = nt_undet = 0
        for iid, trace, answered in runs(cond):
            prompt = io.open(os.path.join(PROMPTS % cond, "%d.txt" % iid),
                             encoding="utf-8").read()
            in_prompt = set(YEAR.findall(prompt))
            n += 1
            if set(YEAR.findall(trace)) - in_prompt:
                imported_year += 1
            if CAMEO.search(trace):
                cameo += 1
            if valence_near_scale(trace):
                valence += 1
            hit = bool(UNDET.search(trace))
            if hit:
                undet += 1
            if shingle_dup(trace) >= 0.20:
                repet += 1
            if not answered:
                n_nt += 1
                nt_undet += int(hit)
        rows[cond] = dict(n=n, imported_year=imported_year, cameo=cameo,
                          valence=valence, undet=undet, repet=repet,
                          n_nt=n_nt, nt_undet=nt_undet)

    def line(label, key):
        cells = "".join("%9s" % ("%.0f%%" % (100.0 * rows[c][key] / rows[c]["n"]))
                        for c in CONDS)
        counts = "  (" + " ".join("%d/%d" % (rows[c][key], rows[c]["n"])
                                  for c in CONDS) + ")"
        print("%-34s%s%s" % (label, cells, counts))

    print()
    print("%-34s%s" % ("", "".join("%9s" % c.upper() for c in CONDS)))
    print("-" * 100)
    line("imported a year not in its prompt", "imported_year")
    line("said CAMEO", "cameo")
    line("valence word near GoldStein", "valence")
    line("8-gram duplication >= 20%", "repet")
    print("-" * 100)
    line("acknowledged underdetermination", "undet")
    print()
    print("of the runs that never terminated, the share that had already said")
    print("the pairing was underdetermined:")
    for c in CONDS:
        r = rows[c]
        pct = (100.0 * r["nt_undet"] / r["n_nt"]) if r["n_nt"] else 0.0
        print("  %-9s %3d of %3d  (%.0f%%)" % (c.upper(), r["nt_undet"],
                                               r["n_nt"], pct))
    print()
    print("Proxies, not labels: each is a lower bound with its own false")
    print("positives. Use them to decide which rows earn a place in the table.")


if __name__ == "__main__":
    sys.exit(main())
