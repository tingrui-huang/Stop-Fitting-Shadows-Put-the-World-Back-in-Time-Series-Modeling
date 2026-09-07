"""What the reasoning traces do differently when one factor is changed.

The accuracy tables say the NBA ablations move nothing and the GDELT ablations
move everything. That is a result about outcomes; this file is about the
behaviour behind it, because the interesting claim is not "NBA is easy" but
"NBA encodes its chronology several times over, so deleting one copy costs
nothing".

Two constraints shape the probe set. First, every mode has to be countable in
all four conditions, or it cannot be used for attribution: a mode that only
exists under SHUFFLED explains SHUFFLED and nothing else. Second, the probes
are regexes over the model's own reasoning, so each is a lower bound with a
false-positive rate of its own. They establish prevalence and how prevalence
moves between conditions; they are not a substitute for reading traces, which
is why the paired-flip listing at the end names the items to read.

The scoring rule is the one in analysis/uniform_scoring.py: one attempt per
instance, truncation counted wrong, so a run that never terminated still
contributes its partial trace to the probes.

Usage:  python analysis/trace_diagnosis.py
        python analysis/trace_diagnosis.py --no-figure
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uniform_scoring import first_attempt                    # noqa: E402

CONDS = ("full", "no_ts", "shuffled", "relative")
FIG = "figures/failure_modes_by_setting.png"

# Probes shared by both tasks. The two task-specific entries differ only in the
# words each domain uses for the columns the ablation did not touch.
COMMON_HEAD = [
    ("cited an absolute time as evidence",
     r"\b\d{1,2}:\d{2}-(?:1st|2nd|3rd|4th|OT)\b"
     r"|\b(?:19|20)\d{2}-\d{2}-\d{2}\b", "strategy"),
    ("reasoned from row / list position",
     r"\b(?:row|index|line|entry|position)\s*#?\s*\d+"
     r"|last (?:row|entry|line|play|event)"
     r"|the (?:row|entry) (?:above|below)", "strategy"),
]
COMMON_TAIL = [
    ("flagged the data as out of order",
     r"scrambl|shuffl|out of order|not in (?:chronological )?order"
     r"|mismatch|inconsist|doesn.t match|do not match", "failure"),
    ("enumerated more than 50 numbered rows", None, "failure"),
    ("never terminated (budget exhausted)", "@truncated", "failure"),
]

SPILLOVER_TAIL = (r"(?:also\s+)?(?:appear|seem|look|are|is)\w*\s+"
                  r"(?:to be\s+)?(?:jumbled|scrambl\w*|shuffl\w*|random\w*"
                  r"|mismatch\w*|inconsist\w*|wrong|unreliab\w*|garbl\w*)")

TASKS = [
    dict(tag="GDELT", root="results/tsrbench160_glm53flash_zai", n=160,
         extra=[
             ("read event semantics off GoldSteinScale",
              r"goldstein.{0,120}(?:negative|positive|severe|conflict"
              r"|cooperat|escalat|tone|sentiment)"
              r"|(?:negative|positive|severe|conflict|cooperat|escalat)"
              r".{0,120}goldstein", "strategy"),
             ("distrusted the untouched GoldStein column too",
              r"(?:goldstein|scores?|values?|numbers?|columns?|data)\s+"
              + SPILLOVER_TAIL, "failure"),
         ]),
    dict(tag="NBA", root="results/nba150_glm53flash_zai", n=150,
         extra=[
             ("used domain causality (miss, then rebound)",
              r"rebound.{0,80}(?:then|next|follow|possession)"
              r"|miss\w*.{0,60}rebound"
              r"|possession.{0,60}(?:so|therefore|means)", "strategy"),
             ("distrusted the untouched score / win-prob columns too",
              r"(?:scores?|win prob\w*|numbers?|columns?|data)\s+"
              + SPILLOVER_TAIL +
              r"|(?:scores?|numbers?) (?:attached|assigned)"
              r".{0,40}(?:jumbled|scrambl|shuffl|random|wrong)", "failure"),
         ]),
]
ENUM = re.compile(r"(?m)^\s*(?:Row\s*)?\d{1,3}[.:)]\s")


def probes(task):
    """-> [(label, matcher, kind)], the task's own entries spliced in."""
    return COMMON_HEAD + task["extra"] + COMMON_TAIL


def hit(matcher, trace, answered):
    if matcher == "@truncated":
        return not answered
    if matcher is None:
        return len(ENUM.findall(trace)) > 50
    return bool(re.search(matcher, trace, re.I))


def report(task):
    root, n = task["root"], task["n"]
    D = {c: first_attempt(root, c, n) for c in CONDS
         if os.path.isdir(os.path.join(root, "%s_raw" % c))}
    rows = []
    for label, matcher, kind in probes(task):
        cells = [sum(1 for i in range(1, n + 1)
                     if hit(matcher, D[c][i][2], D[c][i][1])) / float(n)
                 for c in CONDS]
        rows.append((label, kind, cells))

    print("=" * 94)
    print("%s   n = %d   share of traces matching each probe" % (task["tag"], n))
    print("=" * 94)
    print("%-56s%s" % ("", "".join("%9s" % c.upper() for c in CONDS)))
    print("-" * 94)
    kind_now = None
    for label, kind, cells in rows:
        if kind != kind_now:
            print("[%s]" % ("what the run leaned on" if kind == "strategy"
                            else "what went wrong"))
            kind_now = kind
        print("%-56s%s" % (label, "".join("%8.0f%%" % (100 * v) for v in cells)))

    print("\npaired outcome flips against FULL")
    for c in ("no_ts", "shuffled", "relative"):
        if c not in D:
            continue
        f, o = D["full"], D[c]
        only_f = [i for i in range(1, n + 1) if f[i][0] and not o[i][0]]
        only_o = [i for i in range(1, n + 1) if o[i][0] and not f[i][0]]
        lost = [i for i in only_f if not o[i][1]]
        print("  FULL vs %-9s  only FULL %3d (of which %2d never terminated)"
              "   only %-9s %3d"
              % (c.upper(), len(only_f), len(lost), c.upper(), len(only_o)))
        if only_f:
            print("      read these: %s" % only_f)
    print()
    return rows


def figure(all_rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    colour = {"FULL": "#3d4a5c", "NO_TS": "#c2694a",
              "SHUFFLED": "#7a9a6d", "RELATIVE": "#b8a44e"}
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.4))
    for ax, (tag, rows) in zip(axes, all_rows):
        labels = [r[0] for r in rows][::-1]
        data = [r[2] for r in rows][::-1]
        y = np.arange(len(labels))
        h = 0.20
        for j, c in enumerate(CONDS):
            ax.barh(y + (1.5 - j) * h, [d[j] for d in data], height=h,
                    color=colour[c.upper()], label=c.upper(), zorder=3)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8.5)
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.6, len(labels) - 0.4)
        ax.set_xlabel("share of traces")
        ax.set_title(tag, fontsize=12, weight="bold", loc="left")
        ax.grid(axis="x", color="#dddddd", zorder=0)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        # the probes above the line are strategies, below are failures
        cut = sum(1 for r in rows if r[1] == "failure") - 0.5
        ax.axhline(cut, color="#999999", lw=0.8, ls=(0, (4, 3)), zorder=4)
        ax.text(0.995, cut + 0.12, "what the run leaned on", ha="right",
                va="bottom", fontsize=7.5, color="#666666")
        ax.text(0.995, cut - 0.12, "what went wrong", ha="right", va="top",
                fontsize=7.5, color="#666666")
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=4, fontsize=9,
               frameon=False, bbox_to_anchor=(0.5, 0.0))
    fig.suptitle("Reasoning behaviour by condition, GLM-5.3-Flash, "
                 "one attempt per item, truncation counted wrong",
                 fontsize=10.5, y=0.995)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(FIG, dpi=200)
    print("wrote %s" % FIG)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-figure", action="store_true")
    args = ap.parse_args()
    all_rows = []
    for task in TASKS:
        if os.path.isdir(task["root"]):
            all_rows.append((task["tag"], report(task)))
    if not args.no_figure and all_rows:
        figure(all_rows)


if __name__ == "__main__":
    main()
