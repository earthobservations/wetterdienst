# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The counting half of the manual MCP benchmark (GH-3538): `.claude/skills/mcp-benchmark/scripts/bench.py`.

The orchestrating Claude judges what needs reading; this script counts everything else (steps, checkpoints,
violations, sizes, tokens, aggregates and the comparison of two runs), so that two runs are compared on the same
arithmetic. These tests feed it small transcripts and results, and call no model and no network.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import pytest

SKILL_DIR = Path(__file__).parents[2] / ".claude" / "skills" / "mcp-benchmark"
SPEC = importlib.util.spec_from_file_location("mcp_benchmark_bench", SKILL_DIR / "scripts" / "bench.py")
assert SPEC is not None
assert SPEC.loader is not None
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)

PREFIX = "mcp__wetterdienst__"
DEFAULTS = {"alerts": {"granularity": "community"}, "values": {"shape": "long"}}


def _call(tool: str, arguments: dict[str, Any] | None = None, *, ok: bool = True) -> dict[str, Any]:
    """Build a logged call as `parse_transcript` yields it."""
    return {"n": 1, "tool": tool, "arguments": arguments or {}, "ok": ok}


@pytest.mark.parametrize(
    ("value", "rule", "expected"),
    [
        ("Kiel", "kiel", True),
        ("Kiel", "Hamburg", False),
        (["02564", "02961"], {"any_of": ["02961"]}, True),
        ("02564,02961", {"any_of": ["02961"]}, True),
        ("Frankfurt/Main", {"regex": "(?i)frankfurt"}, True),
        (["a", "b"], {"regex": "^b$"}, True),
        (35.7, {"between": [34.8, 36.5]}, True),
        ("35.7", {"between": [34.8, 36.5]}, True),
        (40.0, {"between": [34.8, 36.5]}, False),
        (None, {"between": [1, 2]}, False),
        (None, {"absent": True}, True),
        ("x", {"absent": True}, False),
        ("x", {"present": True}, True),
        ("2025-12-25/2025-12-27", {"contains_date": "2025-12-26"}, True),
        ("2025-12-26", {"contains_date": "2025-12-26"}, True),
        ("2025-12", {"contains_date": "2025-12-26"}, True),
        ("2025", {"contains_date": "2025-12-26"}, True),
        ("2025-12-27/2025-12-28", {"contains_date": "2025-12-26"}, False),
        ("2025-12-26/2025-12-26T08:00:00Z", {"contains_date": "2025-12-26"}, False),
        (True, True, True),
    ],
)
def test_a_rule_holds_or_not(value: Any, rule: Any, expected: bool) -> None:  # noqa: ANN401, FBT001
    """Literals, `any_of`, `regex`, `between`, `present`, `absent` and `contains_date` decide as documented."""
    assert bench.rule_holds(value, rule) is expected


def test_an_argument_left_out_counts_as_its_default() -> None:
    """`alerts()` is `alerts(granularity="community")`, so a checkpoint on the default is met by the bare call."""
    match = {"tool": "alerts", "args": {"granularity": "community"}}

    assert bench.call_matches(_call("alerts"), match, DEFAULTS)
    assert not bench.call_matches(_call("alerts", {"granularity": "district"}), match, DEFAULTS)
    assert bench.call_matches(_call("alerts", {"granularity": "district"}), {"tool": "alerts"}, DEFAULTS)


def test_a_failed_call_meets_a_checkpoint_only_with_ok_any() -> None:
    """A call that errored is no read of the data, unless the checkpoint says it does not matter."""
    failed = _call("values", ok=False)

    assert not bench.call_matches(failed, {"tool": "values"}, DEFAULTS)
    assert bench.call_matches(failed, {"tool": "values", "ok": "any"}, DEFAULTS)


@pytest.mark.parametrize(
    ("timestamp", "days"),
    [
        ("2026-10-20", 1),
        ("2026-10-20/2026-10-27", 8),
        ("2026-10-20T00:00:00Z/2026-10-20T12:00:00Z", 0.5),
        ("2026-10", 31),
        ("2026-12", 31),
        ("2026", 365),
    ],
)
def test_the_window_of_a_timestamp(timestamp: str, days: float) -> None:
    """A date is a day, a month its days, an interval from its start to the end of its last date."""
    assert bench.window_days(timestamp) == pytest.approx(days)


def test_no_timestamp_is_an_unbounded_window() -> None:
    """Without a timestamp the server's default window applies, which is longer than any limit."""
    assert bench.window_days(None) == math.inf
    assert bench.window_days("not a date") == math.inf


def _message(kind: str, content: list[dict[str, Any]], **extra: Any) -> str:  # noqa: ANN401
    """Build one line of a transcript."""
    return json.dumps({"type": kind, "message": {"role": kind, "content": content, **extra}})


def _transcript(tmp_path: Path) -> Path:
    """Write a small transcript: a tool search, two calls of the server, a Bash call, a hand-back and a result."""
    usage = {"input_tokens": 10, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 0, "output_tokens": 20}
    later = {"input_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 200, "output_tokens": 30}
    lines = [
        json.dumps({"type": "system", "subtype": "init", "tools": [f"{PREFIX}stations"], "model": "m"}),
        json.dumps({"type": "attachment", "attachment": {"type": "instructions"}}),
        _message(
            "assistant",
            [{"type": "tool_use", "id": "a", "name": "ToolSearch", "input": {"query": "x"}}],
            id="m1",
            usage=usage,
        ),
        _message("user", [{"type": "tool_result", "tool_use_id": "a", "content": "refs"}]),
        # one request, two blocks: its usage counts once
        _message(
            "assistant",
            [{"type": "tool_use", "id": "b", "name": f"{PREFIX}stations", "input": {"name": "Kiel"}}],
            id="m2",
            usage=later,
        ),
        _message("assistant", [{"type": "text", "text": "looking"}], id="m2", usage=later),
        _message(
            "user", [{"type": "tool_result", "tool_use_id": "b", "content": [{"type": "text", "text": "x" * 40}]}]
        ),
        _message(
            "assistant",
            [{"type": "tool_use", "id": "c", "name": f"{PREFIX}values", "input": {"stations": ["02564"]}}],
            id="m3",
            usage=later,
        ),
        _message("user", [{"type": "tool_result", "tool_use_id": "c", "content": "boom", "is_error": True}]),
        _message(
            "assistant",
            [{"type": "tool_use", "id": "d", "name": "Bash", "input": {"command": "ls"}}],
            id="m4",
            usage=later,
        ),
        _message("assistant", [{"type": "text", "text": "It was -0.7 C."}], id="m5", usage=later),
        json.dumps({"type": "result", "result": "It was -0.7 C.", "total_cost_usd": 0.01, "duration_ms": 5}),
    ]
    path = tmp_path / "run.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_a_transcript_is_read_into_steps_sizes_and_tokens(tmp_path: Path) -> None:
    """Only the server's tool calls are steps; the tool search is counted apart, any other tool is listed."""
    run = bench.parse_transcript(_transcript(tmp_path), PREFIX)

    assert [c["tool"] for c in run["calls"]] == ["stations", "values"]
    assert run["steps"] == 2
    assert run["tool_searches"] == 1
    assert run["tools_deferred"] is True
    assert run["other_tools"] == ["Bash"]
    assert [c["ok"] for c in run["calls"]] == [True, False]
    assert [c["result_chars"] for c in run["calls"]] == [40, 4]
    assert run["tool_result_chars_sum"] == 44
    assert run["tool_result_chars_max"] == 40
    assert run["answer"] == "It was -0.7 C."
    assert run["output_tokens"] == 20 + 30 * 4
    assert run["context_tokens_first"] == 110
    assert run["context_tokens_last"] == 210
    assert run["context_attachments"] == {"instructions": 1}
    assert run["cost_usd"] == 0.01


def test_a_headless_result_line_gives_the_totals(tmp_path: Path) -> None:
    """The usage of a streamed message is the one at its start; the result line has the output tokens of the session."""
    path = _transcript(tmp_path)
    usage = {
        "input_tokens": 4,
        "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 400,
        "output_tokens": 123,
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"type": "result", "result": "It was -0.7 C.", "usage": usage}) + "\n")

    run = bench.parse_transcript(path, PREFIX)

    assert run["output_tokens"] == 123
    assert run["total_tokens"] == 4 + 100 + 400 + 123


def test_the_hand_back_of_a_subagent_is_its_answer(tmp_path: Path) -> None:
    """A subagent that ends with SubagentHandback has its answer in that call, and it is no step and no violation."""
    path = tmp_path / "sub.jsonl"
    path.write_text(
        _message(
            "assistant", [{"type": "tool_use", "id": "z", "name": "SubagentHandback", "input": {"message": "-0.7"}}]
        )
        + "\n",
        encoding="utf-8",
    )

    run = bench.parse_transcript(path, PREFIX)

    assert run["answer"] == "-0.7"
    assert run["steps"] == 0
    assert run["other_tools"] == []


CASE = {
    "id": "c",
    "max_steps": 3,
    "checkpoints": [
        {"id": "find", "match": [{"tool": "stations", "args": {"name": {"regex": "(?i)kiel"}}}]},
        {"id": "read", "match": [{"tool": "values", "args": {"stations": {"any_of": ["02564"]}}}]},
    ],
    "forbidden": [
        {"id": "wide", "kind": "call", "match": {"tool": "values", "args": {"shape": "wide"}}, "window_days_over": 3},
        {"id": "again", "kind": "repeat", "tool": "values", "max_identical": 1},
        {"id": "refuses", "kind": "answer", "regex": "(?i)cannot"},
    ],
}


def _run(calls: list[dict[str, Any]], answer: str = "ok", other: tuple[str, ...] = ()) -> dict[str, Any]:
    """Build the run `parse_transcript` would yield."""
    return {"calls": calls, "steps": len(calls), "answer": answer, "other_tools": list(other)}


def test_checkpoints_are_ordered_and_a_miss_does_not_stop_the_walk() -> None:
    """Each checkpoint is met by a call at or after the one before; the first one missed is named."""
    both = bench.evaluate(
        CASE, _run([_call("stations", {"name": "Kiel"}), _call("values", {"stations": ["02564"]})]), DEFAULTS
    )
    reversed_ = bench.evaluate(
        CASE, _run([_call("values", {"stations": ["02564"]}), _call("stations", {"name": "Kiel"})]), DEFAULTS
    )
    only_second = bench.evaluate(CASE, _run([_call("values", {"stations": ["02564"]})]), DEFAULTS)

    assert both["checkpoints"] == {"k": 2, "n": 2, "met": ["find", "read"], "first_missed": None}
    assert both["mechanical_pass"] is True
    assert reversed_["checkpoints"]["k"] == 1
    assert only_second["checkpoints"]["first_missed"] == "find"
    assert only_second["first_checkpoint_met"] is False
    assert only_second["mechanical_pass"] is False


def test_the_same_call_can_meet_two_checkpoints() -> None:
    """A values call by name may find the station and read it in one step."""
    case = {
        "id": "c",
        "max_steps": 3,
        "checkpoints": [
            {"id": "find", "match": [{"tool": "values", "args": {"name": {"regex": "kiel"}}}]},
            {"id": "read", "match": [{"tool": "values"}]},
        ],
    }

    result = bench.evaluate(case, _run([_call("values", {"name": "kiel"})]), DEFAULTS)

    assert result["checkpoints"]["k"] == 2


def test_no_tool_call_is_no_pass() -> None:
    """An answer from memory reaches no checkpoint: zero steps never pass."""
    result = bench.evaluate(CASE, _run([]), DEFAULTS)

    assert result["within_steps"] is False
    assert result["mechanical_pass"] is False


def test_more_steps_than_the_limit_is_no_pass() -> None:
    """The limit is the headline: one step too many fails, exactly the limit passes."""
    calls = [_call("stations", {"name": "Kiel"}), _call("values", {"stations": ["02564"]}, ok=True)]
    at_limit = bench.evaluate(CASE, _run([*calls, _call("coverage")]), DEFAULTS)
    over = bench.evaluate(CASE, _run([*calls, _call("coverage"), _call("coverage")]), DEFAULTS)

    assert at_limit["mechanical_pass"] is True
    assert over["mechanical_pass"] is False


def test_forbidden_behaviours_are_counted() -> None:
    """A wide shape over a long or unbounded window, a repeat, a refusal and a tool of another kind are violations."""
    wide_long = _call("values", {"shape": "wide", "timestamp": "2026-10-01/2026-10-20"})
    wide_short = _call("values", {"shape": "wide", "timestamp": "2026-10-01"})
    wide_open = _call("values", {"shape": "wide"})

    assert "wide" in bench.evaluate(CASE, _run([wide_long]), DEFAULTS)["violations"]
    assert "wide" not in bench.evaluate(CASE, _run([wide_short]), DEFAULTS)["violations"]
    assert "wide" in bench.evaluate(CASE, _run([wide_open]), DEFAULTS)["violations"]
    assert (
        "again"
        in bench.evaluate(CASE, _run([_call("values", {"a": 1}), _call("values", {"a": 1})]), DEFAULTS)["violations"]
    )
    assert (
        "again"
        not in bench.evaluate(CASE, _run([_call("values", {"a": 1}), _call("values", {"a": 2})]), DEFAULTS)[
            "violations"
        ]
    )
    assert "refuses" in bench.evaluate(CASE, _run([], "I cannot do that"), DEFAULTS)["violations"]
    assert (
        "non-wetterdienst-tool:Bash" in bench.evaluate(CASE, _run([], other=("Bash", "Bash")), DEFAULTS)["violations"]
    )


def test_fisher_exact_test() -> None:
    """Fisher's two-sided exact test on the passes of two runs, against hand-computed values."""
    assert bench.fisher_two_sided(5, 5, 5, 5) == pytest.approx(1.0)
    assert bench.fisher_two_sided(5, 5, 0, 5) == pytest.approx(2 / 252)
    assert bench.fisher_two_sided(5, 5, 4, 5) == pytest.approx(1.0)
    assert bench.fisher_two_sided(5, 5, 1, 5) == pytest.approx(12 / 252)
    assert bench.fisher_two_sided(18, 20, 10, 20) == pytest.approx(
        0.013814, abs=1e-6
    )  # as scipy.stats.fisher_exact says


def _results(
    passes: dict[tuple[str, str], int], n: int = 5, *, hashes: dict[str, str] | None = None, prompt: str = "p1"
) -> dict[str, Any]:
    """Build a results file: `passes` passes out of `n` repeats for each (case, tier)."""
    runs = [
        {
            "case": case,
            "tier": tier,
            "passed": i < k,
            "facts_ok": i < k,
            "checkpoints": {"k": 1, "n": 2},
            "violations": [],
            "steps": 2,
            "max_steps": 4,
            "tool_result_chars_sum": 1000 + 100 * i,
            "tool_result_chars_max": 800,
            "output_tokens": 50,
            "context_tokens_first": 30000,
            "total_tokens": 90000,
        }
        for (case, tier), k in passes.items()
        for i in range(n)
    ]
    case_hashes = hashes or dict.fromkeys({c for c, _ in passes}, "h1")
    return {"meta": {"mode": "headless", "prompt": prompt, "case_hashes": case_hashes}, "runs": runs}


def test_the_report_aggregates_repeats_and_pools_per_tier() -> None:
    """Per (case, tier): passes k/N, checkpoints, median and max steps; then one pooled row per tier."""
    table = bench.report(_results({("a", "small"): 4, ("b", "small"): 2}))

    assert "| a | small | 4/5 | 2/2 (4) | 5/10 | 0 | 4/5 | 1200 | 50 |" in table
    assert "| **all cases** | **small** | **6/10** |" in table


def test_the_comparison_flags_a_regression_only_beyond_noise() -> None:
    """5/5 against 4/5 is noise at this size; 5/5 against 0/5 is not; the pool is judged on its own."""
    before = _results({("a", "small"): 5, ("b", "small"): 5})
    after = _results({("a", "small"): 0, ("b", "small"): 4})

    text = bench.compare(before, after)

    assert "a [small]: 5/5 -> 0/5 (p=0.008): REGRESSED" in text
    assert "b [small]: 5/5 -> 4/5 (p=1.000): within noise" in text
    assert "POOLED small: 10/10 -> 4/10" in text
    assert "REGRESSED" in next(line for line in text.splitlines() if line.startswith("POOLED"))


def test_the_comparison_skips_changed_cases_and_a_changed_prompt() -> None:
    """Only the cases whose hash and prompt are unchanged are compared, and the number skipped is said."""
    before = _results({("a", "small"): 5, ("b", "small"): 5}, hashes={"a": "h1", "b": "h1"})
    after = _results({("a", "small"): 5, ("b", "small"): 5}, hashes={"a": "h1", "b": "h2"})

    text = bench.compare(before, after)

    assert "1 (case, tier) compared, 1 skipped" in text
    assert "b [small]" not in text
    assert "no case is compared" in bench.compare(before, _results({("a", "small"): 5}, prompt="p2"))


def test_the_comparison_names_what_differs_between_the_runs() -> None:
    """A different model, mode or server version is told first, as it explains most differences."""
    before, after = _results({("a", "small"): 5}), _results({("a", "small"): 5})
    before["meta"]["server_version"] = "0.178.0"
    after["meta"]["server_version"] = "0.179.0"

    assert "differs: server_version: '0.178.0' -> '0.179.0'" in bench.compare(before, after)


def test_every_case_renders_a_prompt_and_hashes_are_stable() -> None:
    """The template has all its fields filled for every case, and the hashes change with the case only."""
    data = bench.load_cases()
    for case in data["cases"]:
        prompt = bench.render_prompt(case, "2026-10-28", "tools")
        assert case["question"] in prompt
        assert f"at most {case['max_steps']} steps" in prompt
        assert "{" not in prompt

    first = bench.hashes(data)
    changed = json.loads(json.dumps(data))
    changed["cases"][0]["max_steps"] += 1
    second = bench.hashes(changed)
    assert first["cases"][data["cases"][1]["id"]] == second["cases"][data["cases"][1]["id"]]
    assert first["cases"][data["cases"][0]["id"]] != second["cases"][data["cases"][0]["id"]]
    assert first["cases_file"] != second["cases_file"]


def _unit_fact(case_id: str, fact_id: str = "value-with-its-unit") -> dict[str, Any]:
    """Take a fact of a case of the cases file."""
    case = next(c for c in bench.load_cases()["cases"] if c["id"] == case_id)
    return next(f for f in case["facts"] if f["id"] == fact_id)


#: (case, what the judge read, an answer, whether the unit check passes)
UNIT_ANSWERS = [
    # a temperature: degrees Celsius, not kelvin, not Fahrenheit, not a bare number
    ("units-kiel-celsius", {"value": -0.7}, "The daily mean was -0.7 °C at Kiel-Holtenau.", True),
    ("units-kiel-celsius", {"value": -0.7}, "It was \N{MINUS SIGN}0.7 degrees Celsius.", True),
    ("units-kiel-celsius", {"value": -0.7}, "The mean was -0.7C on 26 December 2025.", True),
    ("units-kiel-celsius", {"value": -0.7}, "The daily mean was -0.7 K.", False),
    ("units-kiel-celsius", {"value": -0.7}, "The daily mean was -0.7 kelvin.", False),
    ("units-kiel-celsius", {"value": -0.7}, "The daily mean was -0.7 F.", False),
    ("units-kiel-celsius", {"value": -0.7}, "The daily mean was -0.7 at Kiel-Holtenau (station 02564).", False),
    ("units-kiel-celsius", {"value": -0.7}, "The daily mean was 272.45 K.", False),
    ("units-kiel-celsius", {"value": -0.7}, "On 26 December 2025 the mean was -0.7 °C, so 273 K is wrong.", True),
    # a forecast: a span of the judge's own call, in Celsius
    ("units-lax-forecast-celsius", {"min": 17.1, "max": 21.8}, "Tomorrow afternoon about 20 °C.", True),
    ("units-lax-forecast-celsius", {"min": 17.1, "max": 21.8}, "Tomorrow afternoon about 20 C.", True),
    ("units-lax-forecast-celsius", {"min": 17.1, "max": 21.8}, "Tomorrow afternoon about 293 K.", False),
    ("units-lax-forecast-celsius", {"min": 17.1, "max": 21.8}, "Tomorrow afternoon about 20.", False),
    ("units-lax-forecast-celsius", {"min": 17.1, "max": 21.8}, "Tomorrow afternoon about 20 K.", False),
    ("units-lax-forecast-celsius", {"min": 17.1, "max": 21.8}, "Tomorrow afternoon about 35 °C.", False),
    # a fraction the library returns as 0.84 for 84 %
    ("units-humidity-percent", {"value": 0.8404}, "The mean relative humidity was 84 %.", True),
    ("units-humidity-percent", {"value": 0.8404}, "The mean relative humidity was 84%.", True),
    ("units-humidity-percent", {"value": 0.8404}, "It was 0.84 (a fraction), the source's own unit.", True),
    ("units-humidity-percent", {"value": 0.8404}, "It was 0.84 as a fraction, which is 84 percent.", True),
    ("units-humidity-percent", {"value": 0.8404}, "The mean relative humidity was 0.84 %.", False),
    ("units-humidity-percent", {"value": 0.8404}, "The mean relative humidity was 0.84 percent.", False),
    ("units-humidity-percent", {"value": 0.8404}, "The mean relative humidity was 0.84.", False),
    ("units-humidity-percent", {"value": 0.8404}, "The mean relative humidity was 85 %.", False),
    # a duration in seconds, not minutes or hours
    ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for 14821 s on 16 October 2026.", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for 14821 seconds, about 4.1 hours.", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for about 4.1 hours.", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for 247 minutes.", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for 14821 minutes.", False),
    ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for 14821 hours.", False),
    ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for 14821.", False),
    # a speed in m/s, or km/h converted
    ("units-wind-speed", {"value": 3.0}, "The mean wind speed was 3.0 m/s.", True),
    ("units-wind-speed", {"value": 3.0}, "The mean wind speed was 3 meters per second (10.8 km/h).", True),
    ("units-wind-speed", {"value": 3.0}, "The mean wind speed was 3.0 km/h.", False),
    ("units-wind-speed", {"value": 3.0}, "The mean wind speed was 3.0 mph.", False),
    # a precipitation amount in mm
    ("units-precipitation-mm", {"value": 15.5}, "15.5 mm of precipitation fell.", True),
    ("units-precipitation-mm", {"value": 15.5}, "15.5 l/m² fell.", True),
    ("units-precipitation-mm", {"value": 15.5}, "15.5 cm fell.", False),
    ("units-precipitation-mm", {"value": 15.5}, "15.5 inches fell.", False),
    ("units-precipitation-mm", {"value": 15.5}, "15.5 fell.", False),
    # a CSV table: the unit is in the header of the column, or said in the text
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "date,precipitation_mm\n2026-10-14,0.0\n2026-10-15,0.0\n2026-10-16,15.5\n\nThe column is in millimetres (mm).",
        True,
    ),
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "date,precipitation\n2026-10-14,0.0\n2026-10-16,15.5\n\nThe unit of the precipitation column is mm.",
        True,
    ),
    ("units-csv-with-unit", {"value": 15.5}, "date,precipitation\n2026-10-14,0.0\n2026-10-16,15.5\n", False),
    ("units-csv-with-unit", {"value": 15.5}, "date,precipitation_cm\n2026-10-14,0.0\n2026-10-16,15.5\n", False),
    # a conversion to Fahrenheit: the Fahrenheit figure must be there and right
    ("units-fahrenheit", {"value": -0.7}, "The daily mean was 30.7 °F.", True),
    ("units-fahrenheit", {"value": -0.7}, "That is -0.7 °C, or 30.7 degrees Fahrenheit.", True),
    ("units-fahrenheit", {"value": -0.7}, "The daily mean was about 31 F.", True),
    ("units-fahrenheit", {"value": -0.7}, "The daily mean was -0.7 °C.", False),
    ("units-fahrenheit", {"value": -0.7}, "The daily mean was -0.7 °F.", False),
    ("units-fahrenheit", {"value": -0.7}, "The daily mean was 273 K.", False),
    ("units-fahrenheit", {"value": -0.7}, "The daily mean was 30.7 K.", False),
]


@pytest.mark.parametrize(
    ("case_id", "truth", "answer", "expected"),
    [pytest.param(*row, id=f"{row[0]}-{i}") for i, row in enumerate(UNIT_ANSWERS)],
)
def test_the_unit_check_passes_the_right_unit_and_fails_the_wrong_one(
    case_id: str,
    truth: dict[str, float],
    answer: str,
    expected: bool,  # noqa: FBT001
) -> None:
    """A value stated in its unit passes; the same number with another unit, a bare number or a wrong figure fails."""
    result = bench.unit_check(answer, _unit_fact(case_id), truth)

    assert result["ok"] is expected, result


def test_every_unit_case_is_tried_by_a_good_and_a_bad_answer() -> None:
    """A unit case added without a synthetic answer of each kind is a unit rule nobody has tried."""
    unit_cases = {c["id"] for c in bench.load_cases()["cases"] if c["kind"] == "units"}

    assert len(unit_cases) >= 6
    assert unit_cases == {row[0] for row in UNIT_ANSWERS}
    for case_id in unit_cases:
        verdicts = {row[3] for row in UNIT_ANSWERS if row[0] == case_id}
        assert verdicts == {True, False}, case_id


def test_dates_and_station_ids_are_no_figures_of_a_value() -> None:
    """16 of '16 October' and the digits of '2026-10-16' or '01975' must not count as a precipitation of 16 mm."""
    fact = _unit_fact("units-precipitation-mm")
    answer = "On 16 October 2026 at station 01975 (2026-10-16, 14:00 UTC) it was dry: 15.5 mm fell."

    assert bench.unit_check(answer, fact, {"value": 15.5}) == {
        "ok": True,
        "ok_figures": ["15.5"],
        "failures": [],
        "required_missing": [],
    }


def test_an_any_order_checkpoint_is_met_by_a_call_before_the_ones_it_follows() -> None:
    """The unit may be looked up before or after the values: the checkpoint does not move the walk."""
    case = {
        "id": "c",
        "max_steps": 3,
        "checkpoints": [
            {"id": "read", "match": [{"tool": "values"}]},
            {"id": "unit", "any_order": True, "match": [{"tool": "glossary"}]},
        ],
    }
    strict = {**case, "checkpoints": [case["checkpoints"][0], {**case["checkpoints"][1], "any_order": False}]}

    before = bench.evaluate(case, _run([_call("glossary"), _call("values")]), DEFAULTS)
    after = bench.evaluate(case, _run([_call("values"), _call("glossary")]), DEFAULTS)

    assert before["checkpoints"]["k"] == after["checkpoints"]["k"] == 2
    assert bench.evaluate(strict, _run([_call("glossary"), _call("values")]), DEFAULTS)["checkpoints"]["k"] == 1
