"""Phase 1: induce a failure-mode taxonomy from Qwen3.6-35B's reasoning traces.

Run:  uv run docent_analyses/2026-08-29_16-53-26_failure-modes/failure_modes.py
"""
from docent import Docent
from docent.data_models.context_config import AgentRunContextConfig
from docent.data_models.metadata_util import GlobFilter

COLLECTION_ID = "93a92e18-857e-4f1f-9950-db427b9730a0"
SEED = "tsr-phase1-seed"
SAMPLE_N = 48
MODEL = "openai/gpt-5.6-sol"

client = Docent()
client.plan_name = "TSRBench failure modes - Qwen3.6-35B"

# The reading sees which condition a run was in, because what counts as a flaw
# depends on what information the prompt actually contained. It does not see the
# gold answer, the prediction, or the score: a judge that knows a run was wrong
# will find a flaw to explain it, and these flaw rates are meant to be
# comparable between the runs that happened to be right and the ones that were not.
BLIND_TO_OUTCOME = AgentRunContextConfig(
    agent_run_metadata=GlobFilter(include=("condition", "condition_gloss", "n_events")),
)

TASK_BACKGROUND = """
Background you need in order to read these traces.

Each run is one attempt at a multiple-choice question built from TSRBench. The
model is given 6 to 8 GDELT news-event summaries, labelled (1), (2), (3) and so
on, and asked to put them in the order they actually happened, choosing between
four candidate orderings. Depending on the condition it is also given a
GoldSteinScale time series and a list of the event timestamps.

Four facts about how these questions are built. They are not stated in the
prompt the model saw, and they decide whether a line of reasoning could ever
have worked:

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
4. The conditions differ in what temporal material is present. FULL has the
   timestamped series and the event times. NO_TS has every timestamp deleted, so
   the series is positions and values only. SHUFFLED keeps the timestamps but
   deranges which value sits at which moment. RELATIVE replaces the calendar
   dates with unitless indices, preserving order but removing every calendar
   fact. A flaw that is impossible in one condition should simply not be
   reported there.
""".strip()

client.plan_markdown(
    "How Qwen3.6-35B reasons about event ordering, and where that reasoning breaks",
    """## Behavior
We are studying how a model reasons when it is asked to do something the prompt
does not contain enough information to do. Each run gives Qwen3.6-35B-A3B six to
eight GDELT news events and asks for their chronological order, offering four
candidate orderings. The prompt hands it a list of the event timestamps but
states outright that the list is in a random order and never says which time
belongs to which event. Recovering that pairing is the whole task, and nothing
in the prompt determines it.

Two routes out of this are already known to be dead ends, and we want to know how
often the model takes them. The first is positional: assume the k-th listed
timestamp belongs to event (k). That ordering was the correct answer in 0 of 49
items checked earlier and never appeared among the four options, yet the model
chose the option closest to it in 45 percent of those items against a 25 percent
chance rate. The second is semantic: try to read the GoldSteinScale numbers
backwards into what kind of event must have produced them. That cannot work
either, because the scale is a fixed lookup from an action-type code rather than
a measure of how severe or positive the news was, and two candidate timestamps
share a value in 40 of 50 items.

The model answers 30 percent of these questions correctly, against a 25 percent
chance floor and a 30 percent rate for simply answering the same letter every
time. So the question is not really why it fails - it is what it does instead of
solving the task, and whether the substitute changes when the temporal
information is taken away.

## Measurement
This phase induces the vocabulary; it does not yet measure anything. We take a
reproducible sample of 48 of the 608 runs, hashed on run id with a fixed seed so
the same 48 come back on re-runs, spread across the four conditions that vary
what temporal material the prompt contains: FULL keeps everything, NO_TS deletes
every timestamp, SHUFFLED deranges which series value sits at which moment, and
RELATIVE swaps calendar dates for unitless indices.

For each sampled run we write a short account of the strategy the trace actually
commits to - the line of reasoning that produced the final answer, as opposed to
lines it raised and abandoned - and of the specific flaws visible in the
reasoning. These accounts are free text on purpose: fixing a category list before
looking at the traces would only confirm what we already suspect and would hide
any third pattern.

The judge is shown which condition each run was in, because whether a step is a
mistake depends on what the prompt actually contained. It is not shown the gold
answer, the model's answer, or whether the run was correct. A judge that knows a
run was wrong will find a flaw to justify that, and we need the flaw rates to
mean the same thing for the runs that happened to land on the right letter as
for the ones that did not.

The accounts are then read together to propose five to ten recurring failure
modes, each with a name, a description precise enough that two readers would
label a trace the same way, and a note on which conditions it can occur in at
all. These become the rows of the comparison table built in the next phase, where
every run is labelled against the agreed vocabulary and the rates are compared
across the four conditions. Failure modes are deliberately not mutually
exclusive - one trace can exhibit several - so this phase produces a checklist,
not a partition.
""",
)

sample = client.query(
    COLLECTION_ID,
    f"""
    SELECT run, condition, trace_chars
    FROM (
        SELECT agent_runs.id AS run,
               agent_runs.metadata_json->>'condition' AS condition,
               CAST(agent_runs.metadata_json->>'reasoning_chars' AS INTEGER) AS trace_chars
        FROM agent_runs
        -- hashed on id with a fixed seed: reproducible across re-runs, and not
        -- ordered on the id column itself, which would return the same rows every
        -- time and force an index scan
        ORDER BY md5(CONCAT(agent_runs.id, '{SEED}'))
        LIMIT {SAMPLE_N}
    ) AS sampled
    """,
    name=f"Sample {SAMPLE_N} runs across the four conditions",
)

summarize = client.read(
    prompt_template=[
        TASK_BACKGROUND,
        "\n\nHere is one run.\n\n",
        sample.run.as_type("agent_run"),
        """

Write a short account of this run's reasoning, in two labelled parts.

STRATEGY: the single line of reasoning that actually produced the final answer.
Traces often raise an approach, abandon it, and try another; name only the one
the answer came out of, and say in one sentence how the model got from that
approach to the letter it chose.

FLAWS: the specific things wrong with the reasoning, as a short list. Describe
what the model did, not a category label - write "assumed the first listed
timestamp belonged to event (1)" rather than "positional assumption". Include
flaws that did not change the answer. If a step is only a mistake given
something the model could not have known, say so.

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
    f"""
    SELECT array_agg(rr.id ORDER BY rr.id) AS accounts
    FROM reading_results rr
    JOIN reading_result_links rrl ON rrl.result_id = rr.id
    WHERE rrl.reading_id = '{summarize}'
    """,
    name="Collect the run accounts",
)

propose = client.read(
    prompt_template=[
        TASK_BACKGROUND,
        """

Below are accounts of how a model reasoned on a sample of these runs, each
naming the strategy the answer came out of and the flaws visible in the
reasoning.

""",
        accounts.accounts.as_type("reading_result", is_list=True),
        """

Propose five to ten recurring failure modes that together cover what you see.

These will become the rows of a table whose columns are the four conditions, so
each one has to be countable on any single run by a reader who has only that
trace and the condition it came from.

They are NOT mutually exclusive. One trace can exhibit several, and it should be
possible for a trace that reached the correct letter to still exhibit one. Do not
add a catch-all "no failure" category; absence is simply zero rows ticked.

For each, give:

- name: short, snake_case
- description: what the model does, concretely enough that two readers looking
  at the same trace would tick it the same way. Say what distinguishes it from
  the neighbouring modes it is easiest to confuse it with.
- decision_rule: one sentence a reader can apply to a trace to decide yes or no
- conditions: which of FULL, NO_TS, SHUFFLED, RELATIVE this can occur in at all.
  Some depend on material that a condition removes - a mode about misreading
  calendar dates cannot occur where the dates are gone - and those must be
  scored as not-applicable there rather than as zero.

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
                        "conditions": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["FULL", "NO_TS", "SHUFFLED", "RELATIVE"],
                            },
                        },
                    },
                    "required": ["name", "description", "decision_rule", "conditions"],
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
    print("- %s  [%s]" % (m["name"], ", ".join(m["conditions"])))
    print("    %s" % m["description"])
    print("    rule: %s\n" % m["decision_rule"])
print("\nOVERVIEW\n%s" % out["overview"])
