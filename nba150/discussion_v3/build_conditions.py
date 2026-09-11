"""Build and verify all seven NBA150 discussion-v3 prompt conditions locally.

This script uses only the Python standard library. It never calls a model API or
runs an evaluation. Run with --check to compare a fresh deterministic build to
the existing files without writing anything.
"""

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import random
import re
from string import Template


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "abductive_reasoning.jsonl"
TEMPLATE_DIR = HERE / "templates"
PROMPT_DIR = HERE / "prompts"
INDEX_DIR = HERE / "indexes"
CONDITIONS = ("full", "text_only", "series_only", "qa_only", "remove", "shuffle", "relative")
EXPECTED_ITEMS = 150
CHANNELS = ("Team A_Score", "Team B_Score", "wp_Team A", "wp_Team B")
LETTERS = "ABCD"
TARGET_MARKER = "TARGET"
MISSING_MARKER = "[A CRITICAL EVENT HAPPENED HERE]"
EMPTY_FUTURE = "None recorded."
EVENT_ID_NAMESPACE = "nba150-discussion-v3-event-id-v1"
SHUFFLE_MASTER_SEED = "nba150-discussion-v3-shuffle-events-sort-v2-20260911"

TIME_RE = re.compile(r"(?:(\d+):)?(\d+(?:\.\d+)?)-(1st|2nd|3rd|4th|OT|DO)")
STRUCTURED_TIME_RE = re.compile(r"(?<!\w)(?:\d+:)?\d+(?:\.\d+)?-(?:1st|2nd|3rd|4th|OT|DO)(?!\w)")
PERIODS = {
    "1st": (Decimal(0), Decimal(720)),
    "2nd": (Decimal(720), Decimal(720)),
    "3rd": (Decimal(1440), Decimal(720)),
    "4th": (Decimal(2160), Decimal(720)),
    "OT": (Decimal(2880), Decimal(300)),
    "DO": (Decimal(3180), Decimal(300)),
}

EVENT_CONDITIONS = {"full", "text_only", "remove", "shuffle", "relative"}
SERIES_CONDITIONS = {"full", "series_only", "remove", "shuffle", "relative"}
EVENT_TIME_MODE = {
    "full": "game", "text_only": "game", "remove": "none",
    "shuffle": "shuffle_sorted", "relative": "relative",
}
SERIES_TIME_MODE = {
    "full": "game", "series_only": "game", "remove": "none",
    "shuffle": "game", "relative": "relative",
}
SECTION_ORDER = {
    "full": ("Task", "Game", "Past Events", "Target Moment", "Future Events", "Time Series", "Question", "Answer Choices", "Response Format"),
    "text_only": ("Task", "Game", "Past Events", "Target Moment", "Future Events", "Question", "Answer Choices", "Response Format"),
    "series_only": ("Task", "Game", "Time Series", "Question", "Answer Choices", "Response Format"),
    "qa_only": ("Task", "Question", "Answer Choices", "Response Format"),
    "remove": ("Task", "Game", "Past Events", "Target Moment", "Future Events", "Time Series", "Question", "Answer Choices", "Response Format"),
    "shuffle": ("Task", "Game", "Past Events", "Target Moment", "Future Events", "Time Series", "Question", "Answer Choices", "Response Format"),
    "relative": ("Task", "Game", "Past Events", "Target Moment", "Future Events", "Time Series", "Question", "Answer Choices", "Response Format"),
}
ALL_HEADINGS = set().union(*SECTION_ORDER.values())
EVENT_HEADERS = {
    "game": "Event ID | Game time | Event",
    "shuffle_sorted": "Event ID | Game time | Event",
    "none": "Event ID | Event",
    "relative": "Event ID | Seconds relative to target | Event",
}
TABLE_HEADERS = {
    "game": "| Game time | Marker | Team A score | Team B score | Team A win probability | Team B win probability |",
    "relative": "| Seconds relative to target | Marker | Team A score | Team B score | Team A win probability | Team B win probability |",
    "none": "| Marker | Team A score | Team B score | Team A win probability | Team B win probability |",
}
TABLE_SEPARATORS = {
    "game": "| --- | --- | --- | --- | --- | --- |",
    "relative": "| --- | --- | --- | --- | --- | --- |",
    "none": "| --- | --- | --- | --- | --- |",
}
RESPONSE_LINES = [
    "Return exactly one JSON object:",
    "",
    "{",
    '  "answer": "<A|B|C|D>",',
    '  "rationale": "<brief evidence-based justification in 1-3 sentences>",',
    '  "evidence_event_ids": [],',
    '  "evidence_series_times": []',
    "}",
    "",
    "Use only event IDs and time labels that are provided above and that support the answer. Use an empty array when the corresponding evidence type is unavailable or unused. Return only the JSON object.",
]


class NumberToken(str):
    """A JSON number represented by its exact source token."""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def jsonl_bytes(values):
    return ("\n".join(json.dumps(v, ensure_ascii=False, separators=(",", ":")) for v in values) + "\n").encode("utf-8")


def load_source():
    raw = SOURCE.read_bytes()
    records = []
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if line.strip():
            records.append((line_number, json.loads(line, parse_int=NumberToken, parse_float=NumberToken)))
    require(len(records) == EXPECTED_ITEMS, f"Expected {EXPECTED_ITEMS} source records, found {len(records)}")
    return raw, records


def load_templates():
    expected = {f"{condition}.txt" for condition in CONDITIONS}
    require(TEMPLATE_DIR.is_dir(), "Missing templates directory")
    require({path.name for path in TEMPLATE_DIR.iterdir()} == expected, "Templates directory must contain exactly seven condition templates")
    raw = {condition: (TEMPLATE_DIR / f"{condition}.txt").read_bytes() for condition in CONDITIONS}
    for condition, value in raw.items():
        require(b"\r" not in value and not value.startswith(b"\xef\xbb\xbf"), f"{condition}: template must be UTF-8 without BOM and use LF")
    return raw, {condition: Template(value.decode("utf-8")) for condition, value in raw.items()}


def parse_game_time(value):
    match = TIME_RE.fullmatch(value)
    require(match is not None, f"Unknown game-time format: {value!r}")
    minutes, seconds, period = match.groups()
    seconds = Decimal(seconds)
    require(seconds < 60, f"Invalid seconds field in game time: {value}")
    remaining = Decimal(minutes or "0") * 60 + seconds
    start, duration = PERIODS[period]
    require(remaining <= duration, f"Game time exceeds {period} duration: {value}")
    return {
        "format": "MM:SS-period" if minutes is not None else "SS-period",
        "period": period,
        "remaining": remaining,
        "elapsed": start + duration - remaining,
    }


def decimal_text(value):
    if value == 0:
        return "0"
    fixed = format(value, "f")
    if "." in fixed:
        fixed = fixed.rstrip("0").rstrip(".")
    return fixed


def relative_time(value, target):
    delta = parse_game_time(value)["elapsed"] - target
    text = decimal_text(delta)
    return "+" + text if delta > 0 else text


def verify_time_parser_contract():
    expected_elapsed = {
        "12:00-1st": "0",
        "57.0-1st": "663",
        "39.1-1st": "680.9",
        "0.0-1st": "720",
        "12:00-2nd": "720",
        "0.0-4th": "2880",
        "5:00-OT": "2880",
        "0.0-OT": "3180",
        "5:00-DO": "3180",
        "4:59-DO": "3181",
    }
    for value, expected in expected_elapsed.items():
        require(decimal_text(parse_game_time(value)["elapsed"]) == expected,
                f"Time parser contract failed for {value}")
    target = parse_game_time("57.0-1st")["elapsed"]
    require(relative_time("39.1-1st", target) == "+17.9", "Fractional relative-time contract failed")
    try:
        parse_game_time("5:00-2OT")
    except ValueError:
        pass
    else:
        raise ValueError("Unknown time suffix was accepted")
    return expected_elapsed


def source_times(record):
    context = record["context"]
    return context["history_times"] + [record["critical_moment"]["after"]["time"]] + context["future_times"]


def source_values(record, channel):
    series = record["numerical_time_series"][channel]
    return series["history"] + series["future"]


def summary_differences(record, item):
    series = record["numerical_time_series"]
    differences = []
    for phase, segment, position in (("before", "history", -1), ("after", "future", 0)):
        summary = record["critical_moment"][phase]
        score = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", summary["score"])
        require(score is not None, f"Item {item}: invalid critical summary score")
        expected = (*score.groups(), summary["win_probability"]["Team A"], summary["win_probability"]["Team B"])
        for index, channel in enumerate(CHANNELS):
            actual = series[channel][segment][position]
            if Decimal(actual) != Decimal(expected[index]):
                differences.append({
                    "instance_id": item,
                    "phase": phase,
                    "channel": channel,
                    "numerical_value": str(actual),
                    "summary_value": str(expected[index]),
                })
    before_time = record["critical_moment"]["before"]["time"]
    history_time = record["context"]["history_times"][-1]
    if before_time != history_time:
        differences.append({
            "instance_id": item,
            "phase": "before",
            "channel": "time",
            "numerical_value": history_time,
            "summary_value": before_time,
        })
    return differences


def validate_source(record, item, audit):
    context = record["context"]
    question = record["multiple_choice_question"]
    series = record["numerical_time_series"]
    history_count = len(context["history_events"])
    future_count = len(context["future_events"])
    require(history_count > 0, f"Item {item}: empty history")
    for phase in ("history", "future"):
        events = context[f"{phase}_events"]
        times = context[f"{phase}_times"]
        require(isinstance(events, list) and isinstance(times, list), f"Item {item}: {phase} context must be arrays")
        require(len(events) == len(times), f"Item {item}: {phase} event/time length mismatch")
        require(all(type(v) is str and v and "\n" not in v and "\r" not in v for v in events + times),
                f"Item {item}: invalid or multiline {phase} value")
    require(set(series) == set(CHANNELS), f"Item {item}: unexpected numerical channels")
    for channel in CHANNELS:
        require(set(series[channel]) == {"history", "future"}, f"Item {item}: unexpected {channel} segments")
        for phase, expected in (("history", history_count), ("future", future_count + 1)):
            values = series[channel][phase]
            require(isinstance(values, list) and len(values) == expected,
                    f"Item {item}: {channel}.{phase} must contain {expected} values")
            require(all(isinstance(v, NumberToken) and Decimal(v).is_finite() for v in values),
                    f"Item {item}: invalid number in {channel}.{phase}")
    choices = question["choices"]
    require(isinstance(choices, list) and len(choices) == 4, f"Item {item}: expected four choices")
    require(all(type(v) is str and v and "\n" not in v and "\r" not in v for v in choices), f"Item {item}: invalid choice text")
    require(question["answer"] in LETTERS, f"Item {item}: invalid gold answer")

    parsed = [parse_game_time(value) for value in source_times(record)]
    elapsed = [value["elapsed"] for value in parsed]
    require(all(elapsed[index - 1] <= elapsed[index] for index in range(1, len(elapsed))), f"Item {item}: source time order goes backward")
    target_index = history_count
    require(all(value < elapsed[target_index] for value in elapsed[:target_index]), f"Item {item}: history is not strictly before target")
    require(all(value > elapsed[target_index] for value in elapsed[target_index + 1:]), f"Item {item}: future is not strictly after target")

    for value in parsed:
        audit["time_formats"][value["format"]] += 1
        audit["period_labels"][value["period"]] += 1
    for index in range(1, len(elapsed)):
        if elapsed[index - 1] == elapsed[index]:
            audit["equal_elapsed_boundaries"].append({
                "instance_id": item,
                "left": source_times(record)[index - 1],
                "right": source_times(record)[index],
                "elapsed_seconds": decimal_text(elapsed[index]),
            })
    target_elapsed = elapsed[target_index]
    relatives = [value - target_elapsed for value in elapsed]
    require(all(relatives[index] - relatives[index - 1] == elapsed[index] - elapsed[index - 1]
                for index in range(1, len(elapsed))), f"Item {item}: relative intervals changed")
    audit["fractional_relative_values"] += sum(value != value.to_integral_value() for value in relatives)
    if any(value["period"] in {"OT", "DO"} for value in parsed):
        audit["overtime_items"].append(item)
    if any(value["period"] == "DO" for value in parsed):
        audit["double_overtime_items"].append(item)
    labels = source_times(record)
    frequencies = Counter(labels)
    if len(frequencies) != len(labels):
        audit["items_with_repeated_time_labels"].append({"instance_id": item, "max_frequency": max(frequencies.values())})
    return summary_differences(record, item)


def make_event_ids(record, stable_item_id):
    result = {}
    context = record["context"]
    for phase in ("history", "future"):
        result[phase] = []
        for index in range(len(context[f"{phase}_events"])):
            payload = json.dumps([
                EVENT_ID_NAMESPACE,
                stable_item_id,
                phase,
                index,
                context[f"{phase}_times"][index],
                context[f"{phase}_events"][index],
            ], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            result[phase].append("E_" + sha256(payload)[:12])
    return result


def shuffle_time_labels(labels, stable_item_id):
    """Assign each original row a seeded, deranged source time label.

    Grouping equal labels and rotating by the largest group size gives a valid
    label derangement exactly when the largest frequency is at most half of n.
    The seed randomizes group order and within-group row order.
    """
    seed_digest = sha256(f"{SHUFFLE_MASTER_SEED}|{stable_item_id}".encode("utf-8"))
    seed = int(seed_digest[:16], 16)
    rng = random.Random(seed)
    groups = defaultdict(list)
    for index, label in enumerate(labels):
        groups[label].append(index)
    maximum = max(len(indices) for indices in groups.values())
    require(maximum <= len(labels) - maximum,
            f"{stable_item_id}: time-label derangement impossible; max frequency {maximum} of {len(labels)}")
    group_labels = sorted(groups)
    rng.shuffle(group_labels)
    grouped_positions = []
    for label in group_labels:
        positions = list(groups[label])
        rng.shuffle(positions)
        grouped_positions.extend(positions)
    permutation = [None] * len(labels)
    for grouped_index, destination in enumerate(grouped_positions):
        permutation[destination] = grouped_positions[(grouped_index + maximum) % len(labels)]
    shuffled = [labels[source] for source in permutation]
    require(Counter(shuffled) == Counter(labels), f"{stable_item_id}: shuffled time multiset changed")
    require(all(shuffled[index] != labels[index] for index in range(len(labels))), f"{stable_item_id}: a shuffled row retained its label")
    return shuffled, {
        "shuffle_seed_sha256": seed_digest,
        "shuffle_seed_uint64": seed,
        "shuffle_assigned_time_source_row_for_original_event_row_1_based": [value + 1 for value in permutation],
    }


def observed_event_rows(record, event_ids):
    context = record["context"]
    rows = []
    for phase in ("history", "future"):
        for index in range(len(context[f"{phase}_events"])):
            rows.append({
                "event_id": event_ids[phase][index],
                "time": context[f"{phase}_times"][index],
                "event": context[f"{phase}_events"][index],
            })
    return rows


def shuffled_event_lines(record, event_ids, stable_item_id):
    """Derange observed event times, then restore chronological display order."""
    context = record["context"]
    rows = observed_event_rows(record, event_ids)
    original_times = [row["time"] for row in rows]
    assigned_times, metadata = shuffle_time_labels(original_times, stable_item_id)
    output_order = sorted(
        range(len(rows)),
        key=lambda index: (parse_game_time(assigned_times[index])["elapsed"], index),
    )
    output_times = [assigned_times[index] for index in output_order]
    require(Counter(output_times) == Counter(original_times),
            f"{stable_item_id}: sorted SHUFFLE event-time multiset changed")
    output_elapsed = [parse_game_time(value)["elapsed"] for value in output_times]
    require(all(output_elapsed[index - 1] <= output_elapsed[index] for index in range(1, len(output_elapsed))),
            f"{stable_item_id}: sorted SHUFFLE event times are not chronological")

    lines = [
        f"{rows[source]['event_id']} | {assigned_times[source]} | {rows[source]['event']}"
        for source in output_order
    ]
    history_count = len(context["history_events"])
    target_elapsed = parse_game_time(record["critical_moment"]["after"]["time"])["elapsed"]
    require(all(value <= target_elapsed for value in output_elapsed[:history_count]),
            f"{stable_item_id}: SHUFFLE Past Events crossed the target time")
    require(all(value >= target_elapsed for value in output_elapsed[history_count:]),
            f"{stable_item_id}: SHUFFLE Future Events crossed the target time")
    metadata.update({
        "shuffle_source_event_row_for_output_row_1_based": [value + 1 for value in output_order],
        "shuffle_target_time_fixed": True,
        "shuffle_target_excluded_from_event_permutation": True,
        "shuffle_sort_key": "cumulative elapsed game seconds ascending; original event row as deterministic tie-breaker",
    })
    return {
        "history": "\n".join(lines[:history_count]),
        "future": "\n".join(lines[history_count:]) if lines[history_count:] else EMPTY_FUTURE,
    }, metadata


def event_lines(record, event_ids, condition, stable_item_id):
    context = record["context"]
    mode = EVENT_TIME_MODE[condition]
    if mode == "shuffle_sorted":
        return shuffled_event_lines(record, event_ids, stable_item_id)
    target = parse_game_time(record["critical_moment"]["after"]["time"])["elapsed"]
    output = {}
    for phase in ("history", "future"):
        lines = []
        for index in range(len(context[f"{phase}_events"])):
            event = context[f"{phase}_events"][index]
            time = context[f"{phase}_times"][index]
            if mode == "game":
                lines.append(f"{event_ids[phase][index]} | {time} | {event}")
            elif mode == "relative":
                lines.append(f"{event_ids[phase][index]} | {relative_time(time, target)} | {event}")
            else:
                lines.append(f"{event_ids[phase][index]} | {event}")
        output[phase] = "\n".join(lines) if lines else EMPTY_FUTURE
    return output, {}


def series_rows(record, condition, stable_item_id):
    mode = SERIES_TIME_MODE[condition]
    original_times = source_times(record)
    target_index = len(record["context"]["history_events"])
    target_elapsed = parse_game_time(record["critical_moment"]["after"]["time"])["elapsed"]
    if mode == "game":
        displayed_times = original_times
    elif mode == "relative":
        displayed_times = [relative_time(value, target_elapsed) for value in original_times]
    else:
        displayed_times = [None] * len(original_times)
    values = {channel: source_values(record, channel) for channel in CHANNELS}
    rows = []
    for index in range(len(original_times)):
        marker = TARGET_MARKER if index == target_index else ""
        fields = [marker] + [str(values[channel][index]) for channel in CHANNELS]
        if mode != "none":
            fields.insert(0, displayed_times[index])
        rows.append("| " + " | ".join(fields) + " |")
    return "\n".join(rows), {}


def render_prompt(record, condition, template, event_ids, stable_item_id):
    context = record["context"]
    substitutions = {
        "team_a": record["game_info"]["team1"],
        "team_b": record["game_info"]["team2"],
        "season": record["game_info"]["season"],
        "target_time": record["critical_moment"]["after"]["time"],
        "answer_choices": "\n".join(f"{LETTERS[index]}. {record['multiple_choice_question']['choices'][index]}" for index in range(4)),
    }
    metadata = {}
    if condition in EVENT_CONDITIONS:
        lines, event_metadata = event_lines(record, event_ids, condition, stable_item_id)
        metadata.update(event_metadata)
        substitutions.update(past_events=lines["history"], future_events=lines["future"])
    if condition in SERIES_CONDITIONS:
        substitutions["time_series_rows"], series_metadata = series_rows(record, condition, stable_item_id)
        metadata.update(series_metadata)
    prompt = template.substitute(substitutions)
    require(context["history_events"] or condition in {"series_only", "qa_only"}, "Internal context error")
    return prompt, metadata


def split_sections(prompt, condition):
    sections = {}
    order = []
    current = None
    for line in prompt.splitlines():
        if line in ALL_HEADINGS:
            require(line not in sections, f"{condition}: duplicate section {line}")
            current = line
            order.append(line)
            sections[line] = []
        else:
            require(current is not None, f"{condition}: text outside a section")
            sections[current].append(line)
    require(tuple(order) == SECTION_ORDER[condition], f"{condition}: unexpected section order {order}")
    for lines in sections.values():
        while lines and lines[0] == "":
            lines.pop(0)
        while lines and lines[-1] == "":
            lines.pop()
    return sections


def parse_table(lines, condition):
    mode = SERIES_TIME_MODE[condition]
    require(lines[:2] == [TABLE_HEADERS[mode], TABLE_SEPARATORS[mode]], f"{condition}: incorrect numerical table header")
    rows = []
    expected_columns = 5 if mode == "none" else 6
    for line in lines[2:]:
        require(line.startswith("| ") and line.endswith(" |"), f"{condition}: malformed numerical row")
        fields = line[2:-2].split(" | ")
        require(len(fields) == expected_columns, f"{condition}: numerical row has {len(fields)} columns")
        rows.append(fields)
    return rows


def verify_prompt(prompt, record, condition, event_ids, stable_item_id, expected_shuffle):
    sections = split_sections(prompt, condition)
    context = record["context"]
    if condition != "qa_only":
        require(sections["Game"] == [f"{record['game_info']['team1']} versus {record['game_info']['team2']}, season {record['game_info']['season']}."],
                f"{condition}/{stable_item_id}: game metadata changed")
    if condition in EVENT_CONDITIONS:
        mode = EVENT_TIME_MODE[condition]
        expected_events, regenerated_metadata = event_lines(record, event_ids, condition, stable_item_id)
        if condition == "shuffle":
            for key, value in regenerated_metadata.items():
                require(expected_shuffle.get(key) == value,
                        f"{condition}/{stable_item_id}: recorded shuffle metadata changed for {key}")
        for section, phase in (("Past Events", "history"), ("Future Events", "future")):
            lines = sections[section]
            require(lines and lines[0] == EVENT_HEADERS[mode], f"{condition}/{stable_item_id}: incorrect event header")
            body = lines[1:]
            expected_body = expected_events[phase].splitlines()
            require(body == expected_body,
                    f"{condition}/{stable_item_id}: event rows differ from deterministic generation in {phase}")
            expected_count = len(context[f"{phase}_events"])
            require(len(body) == (expected_count or 1), f"{condition}/{stable_item_id}: event count changed")
        target_time = record["critical_moment"]["after"]["time"]
        expected_target = {
            "full": [f"Game time: {target_time}", MISSING_MARKER],
            "text_only": [f"Game time: {target_time}", MISSING_MARKER],
            "remove": [MISSING_MARKER],
            "shuffle": [f"Game time: {target_time}", MISSING_MARKER],
            "relative": ["Time: 0 seconds", MISSING_MARKER],
        }[condition]
        require(sections["Target Moment"] == expected_target, f"{condition}/{stable_item_id}: target moment changed or was filled")
    if condition in SERIES_CONDITIONS:
        rows = parse_table(sections["Time Series"], condition)
        original_times = source_times(record)
        target_index = len(context["history_events"])
        require(len(rows) == len(original_times), f"{condition}/{stable_item_id}: numerical row count changed")
        mode = SERIES_TIME_MODE[condition]
        marker_column = 0 if mode == "none" else 1
        require([row[marker_column] for row in rows] == [TARGET_MARKER if index == target_index else "" for index in range(len(rows))],
                f"{condition}/{stable_item_id}: marker moved or multiplied")
        if mode == "game":
            require([row[0] for row in rows] == original_times, f"{condition}/{stable_item_id}: game times changed")
        elif mode == "relative":
            target = parse_game_time(record["critical_moment"]["after"]["time"])["elapsed"]
            expected = [relative_time(value, target) for value in original_times]
            require([row[0] for row in rows] == expected, f"{condition}/{stable_item_id}: relative times changed")
            require(rows[target_index][0] == "0", f"{condition}/{stable_item_id}: target relative time is not zero")
        value_start = 1 if mode == "none" else 2
        for offset, channel in enumerate(CHANNELS):
            require([row[value_start + offset] for row in rows] == source_values(record, channel),
                    f"{condition}/{stable_item_id}: {channel} changed, rounded or lost")

    choices = sections["Answer Choices"]
    require(choices == [f"{LETTERS[index]}. {record['multiple_choice_question']['choices'][index]}" for index in range(4)],
            f"{condition}/{stable_item_id}: answer choices changed")
    require(sections["Response Format"] == RESPONSE_LINES, f"{condition}/{stable_item_id}: response schema changed")
    require(not re.search(r"gold[_ ]answer|correct[_ ]answer|ground[_ -]?truth", prompt, re.I),
            f"{condition}/{stable_item_id}: gold annotation found in prompt")
    require(not re.search(r'^\s*"answer"\s*:\s*"[ABCD]"\s*,?\s*$', prompt, re.M),
            f"{condition}/{stable_item_id}: filled answer found in prompt")
    if condition == "text_only":
        require("Time Series" not in sections and "win probability" not in prompt.lower() and "Team A score" not in prompt,
                f"{stable_item_id}: TEXT_ONLY contains a numerical table or summary")
    if condition == "series_only":
        require(set(sections) == set(SECTION_ORDER[condition]) and not re.search(r"E_[0-9a-f]{12}", prompt),
                f"{stable_item_id}: SERIES_ONLY contains event context")
    if condition == "qa_only":
        require(set(sections) == set(SECTION_ORDER[condition]) and not STRUCTURED_TIME_RE.search(prompt) and not re.search(r"E_[0-9a-f]{12}", prompt),
                f"{stable_item_id}: QA_ONLY contains game context")
    if condition == "remove":
        contextual = "\n".join(sum((sections[name] for name in ("Past Events", "Target Moment", "Future Events", "Time Series")), []))
        require(not STRUCTURED_TIME_RE.search(contextual), f"{stable_item_id}: REMOVE retained a structured game clock")
        require(not re.search(r"\b(?:Past|Future)\s+\d+\b|\|\s*Position\s*\|", contextual), f"{stable_item_id}: REMOVE added shared sequence labels")
    if condition == "relative":
        contextual = "\n".join(sum((sections[name] for name in ("Past Events", "Target Moment", "Future Events", "Time Series")), []))
        require(not STRUCTURED_TIME_RE.search(contextual), f"{stable_item_id}: RELATIVE retained an original game clock")


def table_payload(sections, condition):
    rows = parse_table(sections["Time Series"], condition)
    mode = SERIES_TIME_MODE[condition]
    if mode == "none":
        return [row[0] for row in rows], [row[1:] for row in rows]
    return [row[1] for row in rows], [row[2:] for row in rows]


def event_payload(sections, condition, section):
    mode = EVENT_TIME_MODE[condition]
    body = sections[section][1:]
    if body == [EMPTY_FUTURE]:
        return []
    result = []
    for line in body:
        if mode == "none":
            event_id, event = line.split(" | ", 1)
        else:
            event_id, _, event = line.split(" | ", 2)
        result.append((event_id, event))
    return result


def event_time_payload(sections, condition, section):
    body = sections[section][1:]
    if body == [EMPTY_FUTURE]:
        return []
    require(EVENT_TIME_MODE[condition] != "none", f"{condition}: event times are unavailable")
    return [line.split(" | ", 2)[1] for line in body]


def verify_cross_condition(prompts, item):
    parsed = {condition: split_sections(prompts[condition], condition) for condition in CONDITIONS}
    for condition in CONDITIONS:
        require(parsed[condition]["Answer Choices"] == parsed["full"]["Answer Choices"], f"Item {item}: choices differ across conditions")
        require(parsed[condition]["Response Format"] == parsed["full"]["Response Format"], f"Item {item}: response format differs across conditions")
    for condition in CONDITIONS:
        if condition != "qa_only":
            require(parsed[condition]["Question"] == parsed["full"]["Question"], f"Item {item}: core question differs")
    for condition in EVENT_CONDITIONS - {"shuffle"}:
        for section in ("Past Events", "Future Events"):
            require(event_payload(parsed[condition], condition, section) == event_payload(parsed["full"], "full", section),
                    f"Item {item}: event IDs, descriptions or order differ in {condition}")
    full_events = sum((event_payload(parsed["full"], "full", section)
                       for section in ("Past Events", "Future Events")), [])
    shuffled_events = sum((event_payload(parsed["shuffle"], "shuffle", section)
                           for section in ("Past Events", "Future Events")), [])
    require(Counter(shuffled_events) == Counter(full_events), f"Item {item}: SHUFFLE event set changed")
    require(shuffled_events != full_events, f"Item {item}: SHUFFLE did not change event order")
    shuffled_times = sum((event_time_payload(parsed["shuffle"], "shuffle", section)
                          for section in ("Past Events", "Future Events")), [])
    full_times = sum((event_time_payload(parsed["full"], "full", section)
                      for section in ("Past Events", "Future Events")), [])
    require(Counter(shuffled_times) == Counter(full_times), f"Item {item}: SHUFFLE event-time multiset changed")
    shuffled_elapsed = [parse_game_time(value)["elapsed"] for value in shuffled_times]
    require(all(shuffled_elapsed[index - 1] <= shuffled_elapsed[index]
                for index in range(1, len(shuffled_elapsed))),
            f"Item {item}: SHUFFLE events are not sorted chronologically")
    full_markers, full_values = table_payload(parsed["full"], "full")
    for condition in SERIES_CONDITIONS:
        markers, values = table_payload(parsed[condition], condition)
        require(markers == full_markers and values == full_values, f"Item {item}: marker or numerical rows differ in {condition}")
    for section in ("Game", "Target Moment", "Time Series", "Question", "Answer Choices", "Response Format"):
        require(parsed["shuffle"][section] == parsed["full"][section], f"Item {item}: SHUFFLE changed {section}")
    require(parsed["shuffle"]["Past Events"][0] == parsed["full"]["Past Events"][0] and
            parsed["shuffle"]["Future Events"][0] == parsed["full"]["Future Events"][0],
            f"Item {item}: SHUFFLE changed event headers")


def index_entry(condition, item, source_line, record, raw, event_ids, metadata):
    context = record["context"]
    entry = {
        "instance_id": item,
        "stable_item_id": f"NBA150_{item:03d}",
        "source_line": source_line,
        "condition": condition.upper(),
        "source_game": record["game_filename"],
        "gold_answer": record["multiple_choice_question"]["answer"],
        "prompt_path": f"prompts/{condition}/{item}.txt",
        "prompt_sha256": sha256(raw),
        "prompt_chars": len(raw.decode("utf-8")),
        "prompt_bytes": len(raw),
        "history_events_in_prompt": len(context["history_events"]) if condition in EVENT_CONDITIONS else 0,
        "future_events_in_prompt": len(context["future_events"]) if condition in EVENT_CONDITIONS else 0,
        "series_rows_in_prompt": len(source_times(record)) if condition in SERIES_CONDITIONS else 0,
        "event_ids_in_prompt": sum(len(event_ids[phase]) for phase in ("history", "future")) if condition in EVENT_CONDITIONS else 0,
    }
    if condition == "shuffle":
        entry.update({"shuffle_master_seed": SHUFFLE_MASTER_SEED, **metadata})
    return entry


def condition_description(condition):
    return {
        "full": "Complete past/future events and four-channel series with game clocks",
        "text_only": "Complete past/future events with game clocks; no numerical table or summary",
        "series_only": "Complete four-channel series with game clocks; no event context",
        "qa_only": "Generic question, choices and response schema only",
        "remove": "FULL evidence with explicit clock fields removed; order, partitions and marker retained",
        "shuffle": "FULL numerical table with observed events reassigned to deranged clocks and sorted chronologically",
        "relative": "FULL evidence with both time surfaces mapped to exact seconds relative to target",
    }[condition]


def make_manifest(source_raw, template_raw, entries):
    return {
        "version": "NBA150 discussion v3",
        "scope": "Local prompt generation and verification only; no retrieval, model calls or evaluation",
        "source_file": "nba150/abductive_reasoning.jsonl",
        "source_sha256": sha256(source_raw),
        "generator_file": "build_conditions.py",
        "generator_sha256": sha256(Path(__file__).read_bytes()),
        "event_id_namespace": EVENT_ID_NAMESPACE,
        "shuffle_master_seed": SHUFFLE_MASTER_SEED,
        "n_source_items": EXPECTED_ITEMS,
        "n_conditions": len(CONDITIONS),
        "n_prompts": sum(len(entries[condition]) for condition in CONDITIONS),
        "conditions": {
            condition: {
                "description": condition_description(condition),
                "template": f"templates/{condition}.txt",
                "template_sha256": sha256(template_raw[condition]),
                "index": f"indexes/{condition}.jsonl",
                "prompt_directory": f"prompts/{condition}",
                "n_prompts": len(entries[condition]),
            }
            for condition in CONDITIONS
        },
    }


def make_report(source_raw, template_raw, audit, entries, summary_diffs, shuffle_stats, event_id_count, parser_examples):
    condition_stats = {}
    for condition in CONDITIONS:
        sizes = [entry["prompt_bytes"] for entry in entries[condition]]
        condition_stats[condition] = {
            "prompts": len(sizes),
            "bytes_min": min(sizes),
            "bytes_max": max(sizes),
            "bytes_total": sum(sizes),
        }
    return {
        "status": "PASS",
        "scope": "Generated and verified local files only; no model API, evaluation, retrieval or event pool",
        "source_file": "nba150/abductive_reasoning.jsonl",
        "source_sha256": sha256(source_raw),
        "generator_sha256": sha256(Path(__file__).read_bytes()),
        "template_sha256": {condition: sha256(template_raw[condition]) for condition in CONDITIONS},
        "counts": {
            "source_items": EXPECTED_ITEMS,
            "conditions": len(CONDITIONS),
            "prompts_total": sum(len(entries[condition]) for condition in CONDITIONS),
            "prompts_by_condition": {condition: len(entries[condition]) for condition in CONDITIONS},
            "source_history_events": sum(entry["history_events_in_prompt"] for entry in entries["full"]),
            "source_future_events": sum(entry["future_events_in_prompt"] for entry in entries["full"]),
            "source_series_rows": sum(entry["series_rows_in_prompt"] for entry in entries["full"]),
            "event_ids_unique": event_id_count,
        },
        "condition_file_stats": condition_stats,
        "checks": {
            "seven_conditions_each_have_150_prompts": True,
            "source_channel_lengths_checked_before_indexed_access": True,
            "no_zip_used_for_event_time_or_numerical_alignment": True,
            "history_values_align_with_history_times": True,
            "future_zero_aligns_with_target_and_after_time": True,
            "future_one_onward_aligns_with_future_times": True,
            "all_four_numerical_channels_and_number_tokens_preserved": True,
            "required_event_text_preserved_and_nonshuffle_event_order_preserved": True,
            "event_ids_stable_across_conditions_and_collision_free": True,
            "no_shared_past_future_position_labels": True,
            "choices_order_and_index_gold_mapping_preserved": True,
            "target_context_never_filled_from_answer": True,
            "no_filled_gold_answer_or_gold_annotation_in_prompts": True,
            "deleting_or_changing_source_answer_does_not_change_prompts": True,
            "text_only_has_no_series_or_score_win_probability_summary": True,
            "series_only_has_no_event_context": True,
            "qa_only_has_no_game_context": True,
            "remove_has_no_structured_clock_fields_or_added_shared_sequence": True,
            "shuffle_reassigns_every_observed_event_time_without_using_gold": True,
            "shuffle_preserves_event_and_time_multisets_then_sorts_events_chronologically": True,
            "shuffle_numerical_table_target_time_and_target_marker_equal_full": True,
            "relative_event_and_series_mapping_identical": True,
            "relative_target_zero_and_exact_intervals_preserved": True,
            "time_parser_contract_covers_cross_period_fractional_ot_and_do": True,
            "unknown_time_format_rejected": True,
            "relative_has_no_original_structured_game_clock": True,
            "all_saved_hashes_and_lengths_match_prompt_bytes": True,
            "on_disk_outputs_equal_fresh_deterministic_regeneration": True,
        },
        "source_time_audit": {
            "tokens": sum(audit["time_formats"].values()),
            "formats": dict(sorted(audit["time_formats"].items())),
            "period_labels": dict(audit["period_labels"]),
            "period_durations_seconds": {"regulation_quarter": 720, "overtime_period": 300},
            "period_start_interpretation": {"1st": 0, "2nd": 720, "3rd": 1440, "4th": 2160, "OT": 2880, "DO": 3180},
            "unknown_formats": [],
            "items_with_repeated_time_labels": audit["items_with_repeated_time_labels"],
            "equal_elapsed_adjacent_boundaries": len(audit["equal_elapsed_boundaries"]),
            "equal_elapsed_examples": audit["equal_elapsed_boundaries"][:10],
            "fractional_relative_values": audit["fractional_relative_values"],
            "overtime_items": audit["overtime_items"],
            "double_overtime_items": audit["double_overtime_items"],
            "parser_contract_elapsed_examples": parser_examples,
        },
        "shuffle_audit": {
            "master_seed": SHUFFLE_MASTER_SEED,
            "per_item_seed_and_permutation_location": "indexes/shuffle.jsonl",
            "permutation_semantics": "Observed target-excluding events receive deranged observed-event time labels, then event/ID/assigned-time triples are sorted by cumulative elapsed game seconds",
            "impossible_items": [],
            "original_events_retaining_original_time_label": 0,
            "time_multiset_mismatches": 0,
            "items_with_changed_event_order": shuffle_stats["changed_event_order_items"],
            "items_with_nonmonotonic_output_event_times": [],
            "target_event_participating": False,
            "target_time_and_numerical_row_fixed": True,
        },
        "critical_summary_comparison": {
            "scalar_comparisons": 8 * EXPECTED_ITEMS,
            "before_time_comparisons": EXPECTED_ITEMS,
            "difference_count": len(summary_diffs),
            "differences": summary_diffs,
            "policy": "Use numerical_time_series tokens unchanged and report, rather than repair, summary differences",
        },
        "known_boundaries": {
            "empty_future_event_items": [entry["instance_id"] for entry in entries["full"] if entry["future_events_in_prompt"] == 0],
            "natural_language_phase_cues_remain": True,
            "remove_retains_order_and_past_future_partitions": True,
            "relative_span_can_reveal_game_progress": True,
            "shuffle_output_times_are_monotonic_but_event_to_series_alignment_is_broken": True,
            "score_deltas_may_make_some_choices_easy_to_eliminate": True,
            "future_observations_are_abductive_evidence_not_causes_of_past_events": True,
        },
        "unresolved_data_issues": [],
        "reproducibility": "UTF-8 without BOM, LF newlines, source order, deterministic event IDs and seeded SHUFFLE. --check performs a no-write fresh build and compares every output byte.",
    }


def verify_output_files(expected_prompts, expected_indexes, manifest_raw, report_raw):
    require(PROMPT_DIR.is_dir() and INDEX_DIR.is_dir(), "Missing generated output directories")
    require({path.name for path in PROMPT_DIR.iterdir()} == set(CONDITIONS), "Unexpected condition directories")
    require({path.name for path in INDEX_DIR.iterdir()} == {f"{condition}.jsonl" for condition in CONDITIONS}, "Unexpected index files")
    expected_names = {f"{item}.txt" for item in range(1, EXPECTED_ITEMS + 1)}
    for condition in CONDITIONS:
        directory = PROMPT_DIR / condition
        require(directory.is_dir() and {path.name for path in directory.iterdir()} == expected_names,
                f"{condition}: prompt directory must contain exactly 150 numbered files")
        for item in range(1, EXPECTED_ITEMS + 1):
            raw = (directory / f"{item}.txt").read_bytes()
            require(raw == expected_prompts[condition][item - 1], f"{condition}/{item}: on-disk prompt differs from fresh generation")
            require(b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf"), f"{condition}/{item}: output encoding/newline mismatch")
        require((INDEX_DIR / f"{condition}.jsonl").read_bytes() == expected_indexes[condition], f"{condition}: on-disk index differs")
    require((HERE / "manifest.json").read_bytes() == manifest_raw, "On-disk manifest differs")
    require((HERE / "validation_report.json").read_bytes() == report_raw, "On-disk validation report differs")


def write_outputs(prompts, indexes, manifest_raw, report_raw):
    PROMPT_DIR.mkdir(exist_ok=True)
    INDEX_DIR.mkdir(exist_ok=True)
    allowed_conditions = set(CONDITIONS)
    require(not ({path.name for path in PROMPT_DIR.iterdir()} - allowed_conditions), "Unexpected entry in prompts/; refusing to delete it")
    require(not ({path.name for path in INDEX_DIR.iterdir()} - {f"{condition}.jsonl" for condition in CONDITIONS}),
            "Unexpected entry in indexes/; refusing to delete it")
    expected_names = {f"{item}.txt" for item in range(1, EXPECTED_ITEMS + 1)}
    for condition in CONDITIONS:
        directory = PROMPT_DIR / condition
        directory.mkdir(exist_ok=True)
        require(not ({path.name for path in directory.iterdir()} - expected_names), f"Unexpected file in {directory}; refusing to delete it")
        for item, raw in enumerate(prompts[condition], 1):
            (directory / f"{item}.txt").write_bytes(raw)
        (INDEX_DIR / f"{condition}.jsonl").write_bytes(indexes[condition])
    (HERE / "manifest.json").write_bytes(manifest_raw)
    (HERE / "validation_report.json").write_bytes(report_raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify a fresh build against existing outputs without writing")
    args = parser.parse_args()

    source_raw, records = load_source()
    template_raw, templates = load_templates()
    parser_examples = verify_time_parser_contract()
    audit = {
        "time_formats": Counter(),
        "period_labels": Counter(),
        "equal_elapsed_boundaries": [],
        "fractional_relative_values": 0,
        "overtime_items": [],
        "double_overtime_items": [],
        "items_with_repeated_time_labels": [],
    }
    summary_diffs = []
    event_id_locations = {}
    event_ids_by_item = []
    for item, (_, record) in enumerate(records, 1):
        summary_diffs.extend(validate_source(record, item, audit))
        stable_item_id = f"NBA150_{item:03d}"
        event_ids = make_event_ids(record, stable_item_id)
        event_ids_by_item.append(event_ids)
        for phase in ("history", "future"):
            for index, event_id in enumerate(event_ids[phase]):
                require(event_id not in event_id_locations, f"Event ID collision: {event_id}")
                event_id_locations[event_id] = (item, phase, index)

    prompts = {condition: [] for condition in CONDITIONS}
    entries = {condition: [] for condition in CONDITIONS}
    shuffle_stats = {"changed_event_order_items": []}
    for item, ((source_line, record), event_ids) in enumerate(zip(records, event_ids_by_item), 1):
        stable_item_id = f"NBA150_{item:03d}"
        item_prompts = {}
        item_metadata = {}
        for condition in CONDITIONS:
            prompt, metadata = render_prompt(record, condition, templates[condition], event_ids, stable_item_id)
            verify_prompt(prompt, record, condition, event_ids, stable_item_id, metadata)
            raw = prompt.encode("utf-8")
            prompts[condition].append(raw)
            entries[condition].append(index_entry(condition, item, source_line, record, raw, event_ids, metadata))
            item_prompts[condition] = prompt
            item_metadata[condition] = metadata

            question_without_answer = {key: value for key, value in record["multiple_choice_question"].items() if key != "answer"}
            no_answer_record = dict(record, multiple_choice_question=question_without_answer)
            require(render_prompt(no_answer_record, condition, templates[condition], event_ids, stable_item_id)[0] == prompt,
                    f"{condition}/{stable_item_id}: deleting source answer changed prompt")
            alternate = next(letter for letter in LETTERS if letter != record["multiple_choice_question"]["answer"])
            changed_record = dict(record, multiple_choice_question=dict(question_without_answer, answer=alternate))
            require(render_prompt(changed_record, condition, templates[condition], event_ids, stable_item_id)[0] == prompt,
                    f"{condition}/{stable_item_id}: changing source answer changed prompt")

        verify_cross_condition(item_prompts, item)
        source_order = item_metadata["shuffle"]["shuffle_source_event_row_for_output_row_1_based"]
        if source_order != list(range(1, len(source_order) + 1)):
            shuffle_stats["changed_event_order_items"].append(item)

    require(shuffle_stats["changed_event_order_items"] == list(range(1, EXPECTED_ITEMS + 1)),
            "SHUFFLE must change the observed event order for every item")
    expected_indexes = {condition: jsonl_bytes(entries[condition]) for condition in CONDITIONS}
    manifest_raw = json_bytes(make_manifest(source_raw, template_raw, entries))
    report_raw = json_bytes(make_report(source_raw, template_raw, audit, entries, summary_diffs, shuffle_stats,
                                        len(event_id_locations), parser_examples))
    if not args.check:
        write_outputs(prompts, expected_indexes, manifest_raw, report_raw)
    verify_output_files(prompts, expected_indexes, manifest_raw, report_raw)

    for condition in CONDITIONS:
        saved_entries = [json.loads(line) for line in (INDEX_DIR / f"{condition}.jsonl").read_text(encoding="utf-8").splitlines()]
        require(saved_entries == entries[condition], f"{condition}: parsed index differs from generated index")
        for item, ((_, record), event_ids) in enumerate(zip(records, event_ids_by_item), 1):
            metadata = entries[condition][item - 1] if condition == "shuffle" else {}
            verify_prompt((PROMPT_DIR / condition / f"{item}.txt").read_text(encoding="utf-8"), record, condition,
                          event_ids, f"NBA150_{item:03d}", metadata)
    require(SOURCE.read_bytes() == source_raw, "Source changed during generation")
    require(sum(len(values) for values in prompts.values()) == 1050, "Expected exactly 1050 prompts")
    print("PASS: 7 conditions x 150 items = 1050 prompts")
    print(f"PASS: {sum(entry['series_rows_in_prompt'] for entry in entries['full'])} FULL rows; {len(event_id_locations)} collision-free event IDs")
    print(f"PASS: {len(summary_diffs)} critical-summary differences; 0 unresolved data issues")
    print(f"Output: {HERE}")
    print("No model API calls, no evaluation, no retrieval, no Git mutations.")


if __name__ == "__main__":
    main()
