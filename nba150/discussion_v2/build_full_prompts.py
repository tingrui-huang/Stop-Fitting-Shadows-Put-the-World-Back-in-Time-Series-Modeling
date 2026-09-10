"""Generate and verify the NBA150 discussion FULL inputs using local files only.

Run from any working directory. --check verifies existing outputs without writing.
Only this directory's full/*.txt, index.jsonl and validation_report.json are written.
"""

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from string import Template


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "abductive_reasoning.jsonl"
TEMPLATE = HERE / "full_template.txt"
CHANNELS = ("Team A_Score", "Team B_Score", "wp_Team A", "wp_Team B")
LETTERS = "ABCD"
EXPECTED_ITEMS = 150
PERIODS = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "OT": 5, "DO": 6}
SECTIONS = (
    "Task", "Past Events", "Target Moment", "Future Events", "Time Series",
    "Question", "Answer Choices", "Response Format",
)
TABLE_HEADER = (
    "| Position | Game time | Team A score | Team B score | "
    "Team A win probability | Team B win probability |"
)
TABLE_SEPARATOR = "| --- | --- | --- | --- | --- | --- |"
EMPTY_FUTURE = "None recorded."


class NumberToken(str):
    """Keep the source JSON number spelling, including trailing zeros/exponents."""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load_source():
    raw = SOURCE.read_bytes()
    records = []
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if line.strip():
            record = json.loads(line, parse_int=NumberToken, parse_float=NumberToken)
            records.append((line_number, record))
    require(len(records) == EXPECTED_ITEMS, "Expected exactly 150 source records")
    return raw, records


def clock_key(time):
    match = re.fullmatch(r"(?:(\d+):)?(\d+(?:\.\d+)?)-(1st|2nd|3rd|4th|OT|DO)", time)
    require(match is not None, f"Unsupported source game time: {time!r}")
    minutes, seconds, period = match.groups()
    seconds = Decimal(seconds)
    require(seconds < 60, f"Invalid seconds in game time: {time}")
    remaining = Decimal(minutes or "0") * 60 + seconds
    require(remaining <= (720 if PERIODS[period] <= 4 else 300),
            f"Game time exceeds period length: {time}")
    return PERIODS[period], -remaining


def summary_differences(record, item):
    ctx, series = record["context"], record["numerical_time_series"]
    differences = []
    for phase, segment, position in (("before", "history", -1), ("after", "future", 0)):
        summary = record["critical_moment"][phase]
        scores = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", summary["score"])
        require(scores is not None, f"Item {item}: invalid summary score")
        values = (*scores.groups(), summary["win_probability"]["Team A"],
                  summary["win_probability"]["Team B"])
        for channel_index, channel in enumerate(CHANNELS):
            numerical = series[channel][segment][position]
            summarized = values[channel_index]
            if Decimal(numerical) != Decimal(summarized):
                differences.append({
                    "instance_id": item, "summary_phase": phase, "channel": channel,
                    "numerical_path": f"numerical_time_series.{channel}.{segment}[{position}]",
                    "numerical_value": str(numerical), "summary_value": str(summarized),
                })
    if ctx["history_times"][-1] != record["critical_moment"]["before"]["time"]:
        differences.append({
            "instance_id": item, "summary_phase": "before", "channel": "time",
            "numerical_value": ctx["history_times"][-1],
            "summary_value": record["critical_moment"]["before"]["time"],
        })
    return differences


def validate_source(record, item):
    ctx, series, question = (record["context"], record["numerical_time_series"],
                             record["multiple_choice_question"])
    for phase in ("history", "future"):
        events, times = ctx[f"{phase}_events"], ctx[f"{phase}_times"]
        require(isinstance(events, list) and isinstance(times, list),
                f"Item {item}: {phase} events/times must be arrays")
        require(len(events) == len(times), f"Item {item}: {phase} event/time mismatch")
        for value in events + times:
            require(type(value) is str and bool(value) and "\n" not in value and "\r" not in value,
                    f"Item {item}: invalid or multiline event/time")
    history_count, future_count = len(ctx["history_events"]), len(ctx["future_events"])
    require(history_count > 0, f"Item {item}: no history for before-summary comparison")
    require(set(series) == set(CHANNELS), f"Item {item}: unexpected numerical channels")
    for channel in CHANNELS:
        require(set(series[channel]) == {"history", "future"},
                f"Item {item}: unexpected numerical segments in {channel}")
        for phase, expected in (("history", history_count), ("future", future_count + 1)):
            values = series[channel][phase]
            require(isinstance(values, list) and len(values) == expected,
                    f"Item {item}: {channel}.{phase} length must be {expected}")
            require(all(isinstance(v, NumberToken) and Decimal(v).is_finite() for v in values),
                    f"Item {item}: nonnumeric value in {channel}.{phase}")
    choices = question["choices"]
    require(isinstance(choices, list) and len(choices) == 4, f"Item {item}: need four choices")
    require(all(type(c) is str and c and "\n" not in c and "\r" not in c for c in choices),
            f"Item {item}: invalid choice text")
    require(question["answer"] in tuple(LETTERS), f"Item {item}: invalid answer mapping")
    timeline = ctx["history_times"] + [record["critical_moment"]["after"]["time"]] + ctx["future_times"]
    keys = [clock_key(time) for time in timeline]
    require(all(keys[i - 1] <= keys[i] for i in range(1, len(keys))),
            f"Item {item}: game clock goes backward in event order")
    return summary_differences(record, item)


def render(record, template):
    # Only allowlisted evidence enters the template; the answer key is never read.
    ctx, series = record["context"], record["numerical_time_series"]
    past, future, rows = [], [], []
    for phase, label, event_lines in (("history", "Past", past), ("future", "Future", future)):
        for i in range(len(ctx[f"{phase}_events"])):
            event_lines.append(f"{label} {i + 1} | {ctx[f'{phase}_times'][i]} | {ctx[f'{phase}_events'][i]}")
    for i, time in enumerate(ctx["history_times"]):
        values = [str(series[channel]["history"][i]) for channel in CHANNELS]
        rows.append("| " + " | ".join([f"Past {i + 1}", time, *values]) + " |")
    target_time = record["critical_moment"]["after"]["time"]
    target_values = [str(series[channel]["future"][0]) for channel in CHANNELS]
    rows.append("| " + " | ".join(["Target", target_time, *target_values]) + " |")
    for i, time in enumerate(ctx["future_times"]):
        values = [str(series[channel]["future"][i + 1]) for channel in CHANNELS]
        rows.append("| " + " | ".join([f"Future {i + 1}", time, *values]) + " |")
    choices = record["multiple_choice_question"]["choices"]
    return template.substitute(
        team_a=record["game_info"]["team1"], team_b=record["game_info"]["team2"],
        season=record["game_info"]["season"], past_events="\n".join(past),
        target_time=target_time, future_events="\n".join(future) if future else EMPTY_FUTURE,
        time_series_rows="\n".join(rows),
        answer_choices="\n".join(f"{LETTERS[i]}. {choices[i]}" for i in range(4)),
    )


def split_sections(prompt):
    sections, current, order = {}, None, []
    for line in prompt.splitlines():
        if line in SECTIONS:
            require(line not in sections, f"Duplicate section: {line}")
            sections[line], current = [], line
            order.append(line)
        else:
            require(current is not None, "Text outside prompt sections")
            sections[current].append(line)
    require(tuple(order) == SECTIONS, "Unexpected prompt section order")
    for lines in sections.values():
        while lines and lines[0] == "":
            lines.pop(0)
        while lines and lines[-1] == "":
            lines.pop()
    return sections


def verify_prompt(prompt, record, item):
    """Parse rendered fields back to source arrays, independently of row assembly."""
    sections = split_sections(prompt)
    ctx, series = record["context"], record["numerical_time_series"]
    for section, phase, label in (("Past Events", "history", "Past"), ("Future Events", "future", "Future")):
        lines = sections[section]
        if phase == "future" and not ctx["future_events"]:
            require(lines == [EMPTY_FUTURE], f"Item {item}: fabricated future events")
            lines = []
        require(len(lines) == len(ctx[f"{phase}_events"]), f"Item {item}: missing {phase} events")
        for i, line in enumerate(lines):
            fields = line.split(" | ", 2)
            require(fields == [f"{label} {i + 1}", ctx[f"{phase}_times"][i], ctx[f"{phase}_events"][i]],
                    f"Item {item}: changed {phase} event/time at {i}")
    target_time = record["critical_moment"]["after"]["time"]
    require(sections["Target Moment"] == [f"Game time: {target_time}", "[A CRITICAL EVENT HAPPENED HERE]"],
            f"Item {item}: incorrect target time or exposed target description")
    table = sections["Time Series"]
    require(table[:2] == [TABLE_HEADER, TABLE_SEPARATOR], f"Item {item}: invalid table header")
    rows = []
    for line in table[2:]:
        require(line.startswith("| ") and line.endswith(" |"), f"Item {item}: malformed table row")
        fields = line[2:-2].split(" | ")
        require(len(fields) == 6, f"Item {item}: unexpected table columns")
        rows.append(fields)
    history_count = len(ctx["history_events"])
    future_points = len(series[CHANNELS[0]]["future"])
    require(len(rows) == history_count + future_points, f"Item {item}: lost numerical rows")
    expected_times = ctx["history_times"] + [target_time] + ctx["future_times"]
    expected_labels = ([f"Past {i + 1}" for i in range(history_count)] + ["Target"]
                       + [f"Future {i + 1}" for i in range(len(ctx["future_events"]))])
    require([r[0] for r in rows] == expected_labels, f"Item {item}: incorrect target row position")
    require([r[1] for r in rows] == expected_times, f"Item {item}: numerical time mapping changed")
    for column, channel in enumerate(CHANNELS, 2):
        expected = series[channel]["history"] + series[channel]["future"]
        require([r[column] for r in rows] == expected, f"Item {item}: changed precision or lost values in {channel}")
    choices = sections["Answer Choices"]
    require(len(choices) == 4, f"Item {item}: incorrect choice count")
    for i, choice in enumerate(choices):
        require(choice == f"{LETTERS[i]}. {record['multiple_choice_question']['choices'][i]}",
                f"Item {item}: changed choice {LETTERS[i]}")
    require(sections["Response Format"] == [
        "Answer: <A, B, C, or D>",
        "Reason: <a brief justification in 1-3 sentences based on the provided evidence>",
    ], f"Item {item}: response format contains unexpected content")
    require(not re.search(r"gold[_ ]answer|correct[_ ]answer|ground[_ -]?truth|\"answer\"\s*:", prompt, re.I),
            f"Item {item}: answer annotation in prompt")
    require(not re.search(r"^(?:Answer:\s*[ABCD]\s*$|[.]{3}\s*$)", prompt, re.M),
            f"Item {item}: filled answer or truncation marker in prompt")


def make_index(item, line_number, record, raw):
    ctx = record["context"]
    return {
        "instance_id": item, "source_line": line_number, "condition": "FULL",
        "prompt_file": f"full/{item}.txt", "game": record["game_filename"],
        "gold_answer": record["multiple_choice_question"]["answer"],
        "n_history_events": len(ctx["history_events"]), "n_future_events": len(ctx["future_events"]),
        "n_future_numerical_points": len(record["numerical_time_series"][CHANNELS[0]]["future"]),
        "n_time_series_rows": len(ctx["history_events"]) + len(ctx["future_events"]) + 1,
        "prompt_sha256": sha256(raw), "prompt_chars": len(raw.decode("utf-8")), "prompt_bytes": len(raw),
    }


def verify_bundle(records, template, entries):
    paths = sorted((HERE / "full").iterdir())
    require({p.name for p in paths} == {f"{i}.txt" for i in range(1, EXPECTED_ITEMS + 1)}
            and all(p.is_file() for p in paths), "full/ must contain exactly 150 prompt files")
    require(len(entries) == EXPECTED_ITEMS, "Index must contain 150 entries")
    for item, (line_number, record) in enumerate(records, 1):
        raw = (HERE / "full" / f"{item}.txt").read_bytes()
        require(b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf"), "Expected UTF-8 without BOM and LF newlines")
        prompt = raw.decode("utf-8")
        verify_prompt(prompt, record, item)
        require(entries[item - 1] == make_index(item, line_number, record, raw),
                f"Item {item}: index, hash, length or answer mapping mismatch")
        require(raw == render(record, template).encode("utf-8"), f"Item {item}: regeneration differs")
        # Removing or changing the source answer must not affect any prompt byte.
        question = {k: v for k, v in record["multiple_choice_question"].items() if k != "answer"}
        without_answer = dict(record, multiple_choice_question=question)
        require(render(without_answer, template) == prompt, f"Item {item}: prompt depends on answer key")
        for letter in LETTERS:
            alternate = dict(record, multiple_choice_question=dict(question, answer=letter))
            require(render(alternate, template) == prompt, f"Item {item}: answer-sensitive input")


def make_report(source_raw, template_raw, records, entries, differences):
    history = sum(e["n_history_events"] for e in entries)
    future = sum(e["n_future_events"] for e in entries)
    rows = sum(e["n_time_series_rows"] for e in entries)
    return {
        "status": "PASS", "scope": "Local file generation and verification only; no models or evaluation",
        "source_file": "nba150/abductive_reasoning.jsonl", "source_sha256": sha256(source_raw),
        "template_file": "full_template.txt", "template_sha256": sha256(template_raw),
        "generator_file": "build_full_prompts.py", "generator_sha256": sha256(Path(__file__).read_bytes()),
        "n_source_items": len(records), "n_full_prompts": len(entries), "n_index_entries": len(entries),
        "checks": {
            "exactly_150_prompts": True,
            "all_4_channel_lengths_checked_for_every_item": True,
            "history_values_events_times_aligned": True,
            "future_values_count_equals_future_events_plus_one": True,
            "future_zero_at_target_with_critical_after_time": True,
            "future_one_onward_aligned_with_future_events_and_times": True,
            "game_clock_order_including_period_transitions": True,
            "table_rows_equal_history_plus_future_numerical_length": True,
            "all_events_and_times_preserved_in_original_order": True,
            "all_numeric_json_tokens_preserved_without_rounding": True,
            "four_choices_and_answer_mapping_unchanged": True,
            "target_has_no_event_description": True,
            "no_gold_annotation_or_filled_answer": True,
            "answer_removed_or_changed_does_not_change_input": True,
            "on_disk_prompts_parsed_and_compared_to_source": True,
            "all_prompt_hashes_character_and_byte_lengths_verified": True,
            "all_on_disk_prompts_equal_fresh_regeneration": True,
        },
        "totals": {
            "history_events": history, "future_events": future, "target_rows": len(entries),
            "future_numerical_rows_including_target": future + len(entries),
            "time_series_rows": rows, "numerical_values": rows * len(CHANNELS),
        },
        "prompt_chars": {"min": min(e["prompt_chars"] for e in entries), "max": max(e["prompt_chars"] for e in entries)},
        "prompt_bytes_total": sum(e["prompt_bytes"] for e in entries),
        "empty_future_event_items": [e["instance_id"] for e in entries if e["n_future_events"] == 0],
        "summary_comparison": {
            "checks_per_item": "history[-1] vs before and future[0] vs after: four values each; history[-1] time vs before.time",
            "scalar_comparisons": 8 * len(records), "before_time_comparisons": len(records),
            "difference_count": len(differences), "differences": differences,
            "policy": "Keep numerical_time_series values unchanged; differences are audit records, not corrections",
        },
        "time_mapping_limit": "Numerical arrays have no separate timestamps. Alignment is checked through array lengths, source order, game-clock chronology and both critical summaries; no external play-by-play was used.",
        "reproducibility": "UTF-8 without BOM, LF newlines, source order, no randomization or timestamps. --check verifies all outputs without writing.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify existing files without writing")
    args = parser.parse_args()
    source_raw, records = load_source()
    template_raw = TEMPLATE.read_bytes()
    template = Template(template_raw.decode("utf-8"))
    differences, generated, entries = [], {}, []
    for item, (line_number, record) in enumerate(records, 1):
        differences.extend(validate_source(record, item))
        prompt = render(record, template)
        verify_prompt(prompt, record, item)
        raw = prompt.encode("utf-8")
        generated[f"{item}.txt"] = raw
        entries.append(make_index(item, line_number, record, raw))
    index_raw = ("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n").encode("utf-8")
    if not args.check:
        full = HERE / "full"
        full.mkdir(exist_ok=True)
        require(not ({p.name for p in full.iterdir()} - set(generated)), "Unexpected files in full/; refusing to remove them")
        for name, raw in generated.items():
            (full / name).write_bytes(raw)
        (HERE / "index.jsonl").write_bytes(index_raw)
    saved_index = (HERE / "index.jsonl").read_bytes()
    require(saved_index == index_raw, "Saved index does not match source and prompts")
    verify_bundle(records, template, [json.loads(line) for line in saved_index.decode("utf-8").splitlines()])
    require(SOURCE.read_bytes() == source_raw, "Source changed during generation/verification")
    report = make_report(source_raw, template_raw, records, entries, differences)
    report_raw = json_bytes(report)
    if args.check:
        require((HERE / "validation_report.json").read_bytes() == report_raw, "Saved validation report is stale")
    else:
        (HERE / "validation_report.json").write_bytes(report_raw)
    print(f"PASS: {len(entries)} FULL prompts, {report['totals']['time_series_rows']} numerical rows, {len(differences)} summary differences")
    print(f"Output: {HERE}")
    print("No model API calls, no evaluation, no Git mutations.")


if __name__ == "__main__":
    main()
