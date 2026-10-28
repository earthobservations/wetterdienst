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
