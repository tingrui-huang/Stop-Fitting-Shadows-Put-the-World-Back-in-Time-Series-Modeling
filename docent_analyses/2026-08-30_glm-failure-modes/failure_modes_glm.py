"""Phase 1: induce a failure-mode taxonomy from GLM-5.3-Flash's reasoning traces.

GLM rather than Qwen3.6-35B, because Qwen sits on the 0.25 chance floor in every
condition (0.294 / 0.287 / 0.312 / 0.212) and a model that is guessing throughout
produces four columns that look alike. GLM separates sharply, and separates on an
axis the accuracy table does not show: it does not answer wrongly when the
calendar is taken away, it fails to stop.

The vocabulary this induces has one job: to be the shared row set of a table
whose columns are the four one-factor conditions, so that a rate rising or
falling from column to column can be attributed to the factor that column
changes. That imposes a constraint on the modes themselves, which the prompt
below spends most of its length on: every mode has to be countable in all four
conditions. A mode that cannot occur in NO_TS leaves a hole rather than a number
there, and a row with a hole in it cannot show how anything varies.

Run:  uv run docent_analyses/2026-08-30_glm-failure-modes/failure_modes_glm.py
"""
import os

from docent import Docent
from docent.data_models.context_config import AgentRunContextConfig
from docent.data_models.metadata_util import GlobFilter

COLLECTION_ID = os.environ.get("TSR_GLM_COLLECTION_ID")
if not COLLECTION_ID:
    raise SystemExit("set TSR_GLM_COLLECTION_ID to the collection ingest printed")

SEED = "tsr-glm-phase1-seed"
PER_STRATUM = 6                       # 4 conditions x terminated -> 48 runs
MODEL = "openai/gpt-5.6-sol"

# QA_ONLY is excluded here on purpose. It carries no series at all, so every
# mode about what the model does with the series is not-applicable rather than
# zero in that column, and a mode that is not-applicable somewhere cannot show
# how it varies with the factor. It stays in the collection and can be labelled
# against the frozen vocabulary afterwards as a side observation.
CONDITIONS = ("FULL", "NO_TS", "SHUFFLED", "RELATIVE")

client = Docent()
client.plan_name = "TSRBench failure modes - GLM-5.3-Flash"

# The reading sees the condition, because what counts as a flaw depends on what
# the prompt contained, and it sees whether the run reached an answer, because
# that is a structural fact about the transcript rather than a result: a trace
# that stops at the ceiling has no final step to describe and the reading has to
# be told to describe what it was circling instead. It does not see the gold
# answer, the prediction or the score. A judge that knows a run was wrong will
# find a flaw to explain it, and these rates have to mean the same thing for the
# runs that landed on the right letter as for the ones that did not.
BLIND_TO_OUTCOME = AgentRunContextConfig(
    agent_run_metadata=GlobFilter(include=(
        "condition", "condition_gloss", "n_events",
        "answered", "truncated", "reasoning_chars_full", "elided_chars",
    )),
)

TASK_BACKGROUND = """
Background you need in order to read these traces.

Each run is one attempt by GLM-5.3-Flash at a multiple-choice question built
from TSRBench. The model is given 6 to 8 GDELT news-event summaries, labelled
(1), (2), (3) and so on, and asked to put them in the order they actually
happened, choosing between four candidate orderings. It is also given a
GoldSteinScale time series and a list of the event timestamps.

Facts about how these questions are built. They are not stated in the prompt the
model saw, and they decide whether a line of reasoning could ever have worked:

1. The list of timestamps is explicitly shuffled and unlabelled. The prompt says
   the times are "presented in a random order" and never says which time belongs
   to which event. Recovering that pairing is the entire difficulty of the task.
2. Position carries no information. Assuming the k-th listed timestamp belongs
   to event (k) is wrong by construction: across the study that ordering was the
   correct answer in 0 of 49 checked items and never even appeared as one of the
   four options.
3. GoldSteinScale is not a sentiment or severity score. It is a fixed lookup
   from the CAMEO code for the type of action reported - "make a statement",
   "appeal for aid", "provide aid" - so it says nothing about how good or bad
   the news was. Across the corpus, 12,340 series points take only 197 distinct
   values, and in 40 of 50 checked items two candidate timestamps share a value.
   Reasoning backwards from a number to what kind of event it must have been
   cannot succeed.
4. The system prompt forbids using outside knowledge about when these events
   really happened. Recalling or estimating a real-world date for a news story
   is a violation of the task, not a legitimate route, however plausible the
   date is.

5. The four conditions are one-factor variants of the same item. They differ
   only in what temporal material the prompt carries, and in nothing else:

     FULL      the timestamped series, and the event times as calendar dates
     NO_TS     every timestamp deleted; the series is positions and values only
     SHUFFLED  the timestamps kept, but which value sits at which moment is
               deranged
     RELATIVE  the calendar dates replaced by unitless indices, so order
               survives and every calendar fact is gone

   Each therefore still offers the model some temporal marker to work from - a
   date, a position, a deranged date, an index - and the study is about what it
   does with whichever marker it was given.

Two things about the traces themselves:

A. Many runs never produced an answer. Generation was capped at 22,000
   completion tokens, and the model ran that ceiling out on 39 per cent of FULL
   items, 38 of SHUFFLED, 79 of NO_TS and 78 of RELATIVE. Those transcripts end
   mid-thought with an empty final message. They are not corrupt and they are
   not being excluded; they are the single most common outcome in two of the
   four conditions and they are here to be read.
B. A trace that ran the ceiling out has had the middle of its reasoning removed
   and replaced by a marker saying how many characters were cut, because such a
   trace duplicates 37 to 43 per cent of its 8-word shingles and its two ends
   carry what a reader needs. Traces that reached an answer are complete and
   uncut. Do not treat the marker as something the model wrote.
""".strip()

client.plan_markdown(
    "How GLM-5.3-Flash reasons about event ordering, and where that reasoning breaks",
    """## Behavior
We are studying how a model reasons when it is asked to do something the prompt
does not contain enough information to do. Each run gives GLM-5.3-Flash six to
eight GDELT news events and asks for their chronological order, offering four
candidate orderings. The prompt hands it a list of the event timestamps but
states outright that the list is in a random order and never says which time
belongs to which event. Recovering that pairing is the whole task, and nothing
in the prompt determines it.

The headline result is not the accuracy. It is that the model frequently does
not stop. Generation was capped at 22,000 completion tokens, and the share of
runs that hit that ceiling without emitting an answer splits cleanly on whether
the prompt still carried real calendar dates: 39 per cent on FULL and 38 on
SHUFFLED, against 79 on NO_TS and 78 on RELATIVE. Within each pair the two
numbers are almost identical, and between the pairs it is a factor of two. The
below-chance scores in the two calendar-free conditions - 0.125 and 0.081
against a 0.25 floor - are that non-termination being scored as wrong, not the
model choosing badly among four options.

Three routes out of the task are known to be dead ends, and we want to know how
often each is taken. The first is positional: assume the k-th listed timestamp
belongs to event (k). That ordering was the correct answer in 0 of 49 items
checked earlier and never appeared among the four options. The second is
semantic: read the GoldSteinScale numbers backwards into what kind of event must
have produced them. The scale is a fixed lookup from an action-type code rather
than a measure of severity, and two candidate timestamps share a value in 40 of
50 items. The third is to recall when the news really happened, which the system
prompt forbids and which was seen verbatim in these traces.

## Measurement
This phase induces the vocabulary; it does not yet measure anything. We take a
reproducible sample stratified on condition and on whether the run reached an
answer, six per stratum, hashed on run id with a fixed seed. Stratification is
deliberately balanced rather than proportional: a proportional sample of NO_TS
would be four fifths non-terminating traces and would barely show what the model
does when it does finish, and this phase needs to see both shapes. The rates
themselves are estimated in the next phase, over every run.

For each sampled run we write a short account of the strategy the trace commits
to and the specific flaws visible in the reasoning. For a run that reached an
answer, the strategy is the line of reasoning the answer came out of. For a run
that ran the ceiling out there is no final step, so the account instead names
what the trace was still circling when it was cut off, and says what it was
waiting to resolve before it would commit. These accounts are free text on
purpose: fixing a category list before looking at the traces would only confirm
what we already suspect and would hide any third pattern.

The judge is shown which condition each run was in, because whether a step is a
mistake depends on what the prompt contained, and whether the run terminated,
because that changes what there is to describe. It is not shown the gold answer,
the model's answer, or whether the run was correct.

The accounts are then read together to propose five to ten recurring failure
modes. The four conditions are one-factor variants of one item, so the table
they populate is read across a row: a rate that rises from FULL to NO_TS is
attributed to deleting the timestamps, because deleting the timestamps is the
only thing that changed. That reading only works if the row means the same thing
in all four columns, which is a constraint on the modes and not merely on how
they are counted. A mode phrased around material that a condition removes -
misreading the calendar dates, say - has no value at all in NO_TS rather than a
low one, and a row with a hole in it cannot show how anything varies. So the
modes are required to be countable in all four conditions, which in practice
means phrasing them around what the model does with whichever temporal marker it
was given rather than around a particular marker. Failure modes are deliberately
not mutually exclusive - one trace can exhibit several - so this phase produces
a checklist, not a partition.

QA_ONLY, the fifth arm, is left out here. It carries no series at all, so most
of these modes would be not-applicable in it by construction. It can be labelled
against the frozen vocabulary afterwards as a side observation, but it is not
one of the columns the attribution is read across.
""",
)

sample = client.query(
    COLLECTION_ID,
    """
    SELECT run, condition, terminated, trace_chars
    FROM (
        SELECT agent_runs.id AS run,
               agent_runs.metadata_json->>'condition' AS condition,
               agent_runs.metadata_json->>'answered' AS terminated,
               CAST(agent_runs.metadata_json->>'reasoning_chars' AS INTEGER)
                   AS trace_chars,
               -- balanced across condition x terminated, reproducible on the
               -- seed, and not ordered on the id column itself, which would
               -- return the same rows every time and force an index scan
               ROW_NUMBER() OVER (
                   PARTITION BY agent_runs.metadata_json->>'condition',
                                agent_runs.metadata_json->>'answered'
                   ORDER BY md5(CONCAT(agent_runs.id, '%s'))
               ) AS rn
        FROM agent_runs
        WHERE agent_runs.metadata_json->>'condition' IN (%s)
    ) AS strata
    WHERE rn <= %d
    """ % (SEED, ", ".join("'%s'" % c for c in CONDITIONS), PER_STRATUM),
    name="Sample %d runs per condition x termination stratum" % PER_STRATUM,
)

summarize = client.read(
    prompt_template=[
        TASK_BACKGROUND,
        "\n\nHere is one run.\n\n",
        sample.run.as_type("agent_run"),
        """

Write a short account of this run's reasoning, in two labelled parts.

STRATEGY: what the reasoning committed to.

  If the run produced a final answer, this is the single line of reasoning the
  answer came out of. Traces often raise an approach, abandon it and try
  another; name only the one the answer came out of, and say in one sentence how
  the model got from that approach to the letter it chose.

  If the run ran the token ceiling out and ends mid-thought with no answer, say
  so in the first clause, then name what the trace was still circling when it
  was cut off and what it appeared to be waiting to resolve before it would
  commit. Do not guess which letter it would have chosen.

FLAWS: the specific things wrong with the reasoning, as a short list. Describe
what the model did, not a category label - write "assumed the first listed
timestamp belonged to event (1)" rather than "positional assumption". Include
flaws that did not change the answer, and flaws visible in a run that never
reached one. If a step is only a mistake given something the model could not
have known, say so.

Name the temporal material the step actually used - the calendar dates, the
series positions, the relative indices, the ordering of the timestamp list -
because the conditions differ in which of those exist, and a later reader has to
be able to tell whether the same move was available elsewhere.

If the run did not terminate, also say in one clause what kept it going: the
specific question it kept reopening, or the check it kept redoing.

Judge the reasoning, not the outcome. You have not been told whether this run
was correct, and you should not guess: a trace can reach the right letter
through a broken argument and the wrong letter through a sound one.

Keep the whole thing under 150 words. Cite the parts of the trace you are
describing.
""",
    ],
    context_configs={"run": BLIND_TO_OUTCOME},
    model=MODEL,
    name="Describe each run's strategy and reasoning flaws",
)

accounts = client.query(
    COLLECTION_ID,
    """
    SELECT array_agg(rr.id ORDER BY rr.id) AS accounts
    FROM reading_results rr
    JOIN reading_result_links rrl ON rrl.result_id = rr.id
    WHERE rrl.reading_id = '{}'
    """.format(summarize),
    # format() on a Reading yields its plan alias, "$2", which the server
    # resolves when it runs the plan. Interpolating summarize.id instead
    # would force the reading to flush and finish here, splitting one plan
    # into two submissions.
    name="Collect the run accounts",
)

propose = client.read(
    prompt_template=[
        TASK_BACKGROUND,
        """

Below are accounts of how the model reasoned on a sample of these runs, each
naming what the reasoning committed to and the flaws visible in it. Some of the
runs reached an answer and some ran the token ceiling out without one.

""",
        accounts.accounts.as_type("reading_result", is_list=True),
        """

Propose five to ten recurring failure modes that together cover what you see.

WHAT THESE ARE FOR, WHICH DECIDES HOW THEY MUST BE PHRASED

They become the rows of a table whose four columns are FULL, NO_TS, SHUFFLED and
RELATIVE. Those are one-factor variants of the same items, so the table is read
across a row: if a mode occurs in 12 per cent of FULL runs and 47 per cent of
NO_TS runs, the difference is attributed to the deletion of the timestamps,
because that is the only thing that differs. The question the table answers is
how each failure mode changes as the setting changes.

That only works if a row means the same thing in all four columns. So:

EVERY MODE MUST BE COUNTABLE IN ALL FOUR CONDITIONS. A mode phrased around
material that one condition removes has no value there rather than a low one,
and a row with a hole in it cannot show how anything varies. Do not propose a
mode and mark it inapplicable somewhere; raise it to the level of abstraction at
which it is countable everywhere, or drop it.

The way to do this is to phrase a mode around what the model does with whichever
temporal marker it was given, not around a particular marker. Each condition
gives it one: FULL gives calendar dates, SHUFFLED gives dates whose pairing with
the series is deranged, RELATIVE gives unitless indices, NO_TS gives bare
positions in the series. So a mode like "misread the calendar dates" is not
usable, but "treated the temporal marker it was given as if it determined the
event-to-time pairing" is, and it is the more interesting claim: it can then be
counted in all four and its rate compared.

Test each candidate before you write it down: can a reader who has one trace and
knows only which condition it came from tick this yes or no? Ask that separately
for a FULL trace, a NO_TS trace, a SHUFFLED trace and a RELATIVE trace. If the
answer is not yes four times, rewrite the mode.

OTHER REQUIREMENTS

They are NOT mutually exclusive. One trace can exhibit several, and it should be
possible for a trace that reached the correct letter to still exhibit one. Do not
add a catch-all "no failure" category; absence is simply zero rows ticked.

Non-termination is the outcome in roughly four fifths of the runs in two of the
four conditions, so at least one mode should be about what the reasoning does
that keeps it from committing - and it should distinguish between different ways
of not committing rather than being a single row that restates the token-ceiling
statistic. A mode has to be readable off the trace: "kept reopening the
event-to-timestamp pairing after having settled it" is countable, "ran out of
tokens" is already in the metadata and is not a failure mode.

Every mode must also be tickable on a trace that never terminated, since those
are the majority of two columns. A mode that can only be judged from a final
answer would be missing from four fifths of NO_TS and RELATIVE and would show a
spurious decline there.

For each, give:

- name: short, snake_case
- description: what the model does, concretely enough that two readers looking
  at the same trace would tick it the same way. Say what distinguishes it from
  the neighbouring modes it is easiest to confuse it with. Where the mode is
  about a temporal marker, say what it looks like in each of the four
  conditions, so a reader labelling a NO_TS trace and a reader labelling a FULL
  trace apply the same standard.
- decision_rule: one sentence a reader can apply to a trace to decide yes or no
- why_countable_everywhere: one sentence naming what a reader would look at in a
  NO_TS trace, which has no timestamps at all, to tick this mode

Prefer modes that describe what the model did over modes that describe what it
failed to achieve. "Treated the timestamp list as if it were aligned with the
event numbering" is countable; "did not understand the task" is not.
""",
    ],
    model=MODEL,
    output_schema={
        "type": "object",
        "properties": {
            "overview": {"type": "string", "citations": True},
            "failure_modes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "decision_rule": {"type": "string"},
                        "why_countable_everywhere": {"type": "string"},
                    },
                    "required": ["name", "description", "decision_rule",
                                 "why_countable_everywhere"],
                },
            },
        },
        "required": ["overview", "failure_modes"],
    },
    name="Propose a failure-mode vocabulary from the accounts",
)

out = propose.results[0].output
assert out is not None
modes = out["failure_modes"]
print("\n%d failure modes proposed\n" % len(modes))
for m in modes:
    print("- %s" % m["name"])
    print("    %s" % m["description"])
    print("    rule:   %s" % m["decision_rule"])
    print("    NO_TS:  %s\n" % m["why_countable_everywhere"])
print("\nOVERVIEW\n%s" % out["overview"])
