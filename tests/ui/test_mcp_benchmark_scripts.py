# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The counting half of the manual MCP benchmark (GH-3538): `.claude/skills/mcp-benchmark/scripts/bench.py`.

The orchestrating Claude judges what needs reading; this script counts everything else (steps, checkpoints,
violations, sizes, tokens, aggregates and the comparison of two runs), so that two runs are compared on the same
arithmetic. These tests feed it small transcripts and results, and call no model and no network.
"""

from __future__ import annotations

import http.server
import importlib.util
import json
import math
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from collections.abc import Iterator

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
        ("2025-12-25/2025-12-27", {"on_date": "2025-12-26"}, True),
        ("2025-12-26", {"on_date": "2025-12-26"}, True),
        ("2025-12", {"on_date": "2025-12-26"}, True),
        ("2025", {"on_date": "2025-12-26"}, True),
        ("2025-12-27/2025-12-28", {"on_date": "2025-12-26"}, False),
        ("2025-12-26/2025-12-26T08:00:00Z", {"on_date": "2025-12-26"}, True),
        # ISO instants and intervals of instants: a window that reaches into the day, an instant on it
        ("2025-12-26T00:00:00Z/2025-12-26T23:59:59Z", {"on_date": "2025-12-26"}, True),
        ("2025-12-26T00:00:00Z", {"on_date": "2025-12-26"}, True),
        ("2025-12-26T23:59:59+00:00", {"on_date": "2025-12-26"}, True),
        ("2025-12-25T12:00:00Z/2025-12-26T12:00:00Z", {"on_date": "2025-12-26"}, True),
        ("2025-12-27T00:00:00Z", {"on_date": "2025-12-26"}, False),
        ("2025-12-25/2025-12-26T00:00:00Z", {"on_date": "2025-12-26"}, False),
        ("2025-12-25T00:00:00Z/2025-12-25T23:59:59Z", {"on_date": "2025-12-26"}, False),
        ("not a date", {"on_date": "2025-12-26"}, False),
        (True, True, True),
    ],
)
def test_a_rule_holds_or_not(value: Any, rule: Any, expected: bool) -> None:  # noqa: ANN401, FBT001
    """Literals, `any_of`, `regex`, `between`, `present`, `absent` and `on_date` decide as documented."""
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
    passes: dict[tuple[str, str], int],
    n: int = 5,
    *,
    ns: dict[tuple[str, str], int] | None = None,
    facts: dict[tuple[str, str], int] | None = None,
    violations: dict[tuple[str, str], int] | None = None,
    invalid: dict[tuple[str, str], int] | None = None,
    hashes: dict[str, str] | None = None,
    prompt: str = "p1",
    model: str = "claude-haiku-5-5",
    **meta: Any,  # noqa: ANN401
) -> dict[str, Any]:
    """Build a results file of `passes` passes out of `n` repeats for each (case, tier).

    The facts that held, the runs with a violation and the invalid runs (no server) are given the same way.
    """
    ns = ns or {}
    facts = facts or {}
    violations = violations or {}
    invalid = invalid or {}
    runs = [
        {
            "case": case,
            "tier": tier,
            "model": model,
            "passed": i < k,
            "facts_ok": i < facts.get((case, tier), k),
            "checkpoints": {"k": 1, "n": 2},
            "violations": ["v"] if i < violations.get((case, tier), 0) else [],
            "invalid": i >= ns.get((case, tier), n) - invalid.get((case, tier), 0),
            "steps": 2,
            "max_steps": 4,
            "tool_result_chars_sum": 1000 + 100 * i,
            "tool_result_chars_max": 800,
            "output_tokens": 50,
            "context_tokens_first": 30000,
            "total_tokens": 90000,
        }
        for (case, tier), k in passes.items()
        for i in range(ns.get((case, tier), n))
    ]
    case_hashes = hashes or dict.fromkeys({c for c, _ in passes}, "h1")
    base = {
        "mode": "headless",
        "prompt": prompt,
        "case_hashes": case_hashes,
        "logic": bench.LOGIC_VERSION,
        "defaults": "d1",
    }
    return {"meta": {**base, **meta}, "runs": runs}


def test_the_report_aggregates_repeats_and_pools_per_tier() -> None:
    """Per (case, tier): passes k/N, checkpoints, median and max steps, sizes; then one pooled row per tier."""
    table = bench.report(_results({("a", "small"): 4, ("b", "small"): 2}))

    assert "| a [small] | 4/5 | 2/2 (4) | 5/10 | 0 | 4/5 | 0/0 | 1200 | 50 | 30000 | 90000 | 0 |" in table
    assert "| **all cases [small]** | 6/10 |" in table


def test_the_report_leaves_out_invalid_runs_and_says_so() -> None:
    """A run with no server is no model failure: it is not in the pass rate, and its number and reason are printed."""
    results = _results({("a", "small"): 3}, invalid={("a", "small"): 2})
    for run in results["runs"]:
        run["invalid_reason"] = "the server was 'failed'"

    table = bench.report(results)

    assert "| a [small] | 3/3 |" in table
    assert "2 of 5 runs are invalid (no server)" in table


def test_the_comparison_is_a_non_inferiority_claim_on_the_pooled_rates() -> None:
    """The pool is judged with an interval of the difference against the margin; one run per side proves nothing."""
    full = {("a", "small"): 50, ("b", "small"): 50}
    same = bench.compare(_results(full, n=50), _results(full, n=50))
    worse = bench.compare(
        _results({("a", "small"): 20, ("b", "small"): 20}, n=20),
        _results({("a", "small"): 0, ("b", "small"): 16}, n=20),
    )
    few = bench.compare(_results({("a", "small"): 5}), _results({("a", "small"): 5}))

    assert "=> NO WORSE" in same
    assert "passed 100/100 -> 100/100: difference +0.0%" in same
    assert "=> WORSE" in worse
    assert "=> INCONCLUSIVE" in few
    assert "take about" in few
    assert "(the largest, 75, decides" in few
    assert "there are 5" in few


def test_a_drop_in_facts_or_a_rise_in_violations_is_not_within_noise() -> None:
    """The pass rate alone said nothing about wrong answers or forbidden behaviour: each has its own interval."""
    before = _results({("a", "small"): 40}, n=40)
    after = _results({("a", "small"): 40}, n=40, facts={("a", "small"): 0}, violations={("a", "small"): 30})

    text = bench.compare(before, after)

    assert "passed 40/40 -> 40/40: difference +0.0%" in text
    assert "facts ok 40/40 -> 0/40" in text
    assert "no violation 40/40 -> 10/40" in text
    assert "=> WORSE" in text


def test_the_per_case_fisher_test_is_a_hint_only() -> None:
    """5/5 against 0/5 is flagged for the case as a hint; the verdict is the pooled one."""
    text = bench.compare(_results({("a", "small"): 5}), _results({("a", "small"): 0}))

    assert "hint a [small]: 5/5 -> 0/5 (Fisher p=0.008, a hint): fewer passes" in text


def test_non_inferiority_arithmetic() -> None:
    """The Newcombe interval of two proportions and the runs needed, against hand-computed values."""
    diff, low, high = bench.newcombe_difference(90, 100, 80, 100)

    assert diff == pytest.approx(-0.10)
    assert (low, high) == pytest.approx((-0.19947, -0.000149), abs=1e-4)
    assert bench.wilson(5, 5)[0] == pytest.approx(0.5655, abs=1e-3)
    assert bench.required_runs(0.9) == pytest.approx(142, abs=2)


def test_the_comparison_skips_changed_cases() -> None:
    """Only the cases whose hash is unchanged are compared, and the number skipped is said."""
    before = _results({("a", "small"): 5, ("b", "small"): 5}, hashes={"a": "h1", "b": "h1"})
    after = _results({("a", "small"): 5, ("b", "small"): 5}, hashes={"a": "h1", "b": "h2"})

    text = bench.compare(before, after)

    assert "1 (case, tier) compared; left out: 0 only in the current file, 1 with a changed case" in text
    assert "hint b [small]" not in text


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        ({"prompt": "p2"}, "the prompt differs"),
        ({"mode": "subagent"}, "the mode (headless or subagent) differs"),
        ({"tools_deferred": True}, "whether the tools were deferred differs"),
        ({"logic": 99}, "the logic version of bench.py differs"),
        ({"defaults": "d2"}, "the defaults of the cases file differs"),
    ],
)
def test_the_comparison_refuses_when_the_counting_or_the_prompt_changed(changed: dict[str, Any], expected: str) -> None:
    """A changed prompt, logic version or defaults make two files incomparable: it says so, with no verdict."""
    before = _results({("a", "small"): 5})
    after = _results({("a", "small"): 5})
    after["meta"].update(changed)

    text = bench.compare(before, after)

    assert "not compared" in text
    assert expected in text
    assert "POOLED" not in text


def test_the_comparison_refuses_when_runs_are_invalid() -> None:
    """Runs with no server are no data: a file with more than a few percent of them is not compared."""
    before = _results({("a", "small"): 5}, n=40)
    after = _results({("a", "small"): 5}, n=40, invalid={("a", "small"): 4})

    assert "10% of the 40 compared current runs are 4 invalid (no server), above 3%" in bench.compare(before, after)


def test_the_comparison_compares_the_resolved_model_ids() -> None:
    """The alias `haiku` is not the model: a pool whose resolved ids differ is not compared."""
    before = _results({("a", "small"): 5}, model="claude-haiku-5-5")
    after = _results({("a", "small"): 5}, model="claude-haiku-5-6")

    text = bench.compare(before, after)

    assert "not compared, the resolved model ids differ" in text


def test_the_comparison_names_what_differs_between_the_runs() -> None:
    """A different model, mode or server version is told first, as it explains most differences."""
    before = _results({("a", "small"): 5}, server_version="0.178.0")
    after = _results({("a", "small"): 5}, server_version="0.179.0")

    assert "differs: server_version: '0.178.0' -> '0.179.0'" in bench.compare(before, after)


def test_the_sizes_are_compared_as_paired_differences() -> None:
    """The context and the tool results of each case are compared with themselves, not pooled."""
    before = _results({("a", "small"): 5, ("b", "small"): 5})
    after = _results({("a", "small"): 5, ("b", "small"): 5})
    for run in after["runs"]:
        run["context_tokens_first"] = 20000
        run["tool_result_chars_sum"] = run["tool_result_chars_sum"] // 2

    text = bench.compare(before, after)

    assert (
        "context tokens at the first request: median per case 30000 -> 20000, paired difference (median over 2 "
        "cases) -10000" in text
    )
    assert "tool result chars: median per case 1200 -> 600" in text


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
    # prose with commas is prose, not a table row (a)
    ("units-humidity-percent", {"value": 0.8404}, "The mean relative humidity was 0.84, i.e. 84 %.", True),
    ("units-fahrenheit", {"value": -0.7}, "The mean was -0.7, which is 30.7 °F.", True),
    ("units-fahrenheit", {"value": -0.7}, "On 26.12.2025 the mean at Kiel-Holtenau was 30.7 °F.", True),
    (
        "units-kiel-celsius",
        {"value": -0.7},
        "On Dec 26, 2025 the mean was -0.7 °C, the minimum -3.1 °C and the maximum 1.2 °C.",
        True,
    ),
    ("units-kiel-celsius", {"value": -0.7}, "Kiel-Holtenau, 26 Dec 2025: -0.7 °C.", True),
    ("units-precipitation-mm", {"value": 15.5}, "Unit: mm. (Other networks use inches.)\n15.5", False),
    ("units-precipitation-mm", {"value": 15.5}, "It fell 15.5 mm. (Other networks use inches.)", True),
    # a markdown table without commas, with the unit in the header (a)
    ("units-kiel-celsius", {"value": -0.7}, "| date | mean (°C) |\n|---|---|\n| 2025-12-26 | -0.7 |", True),
    ("units-kiel-celsius", {"value": -0.7}, "| date | mean (K) |\n|---|---|\n| 2025-12-26 | -0.7 |", False),
    # a one-letter unit is only a unit directly after the figure (b)
    ("units-sunshine-seconds", {"value": 14821.2}, "The sun's duration at Hamburg, 16 October 2026, was 14821.", False),
    ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for 14821 at Hamburg.", False),
    ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for 14821, in s.", False),
    # a month name is no mask for a unit word that starts like one (c)
    ("units-humidity-percent", {"value": 0.8404}, "The mean relative humidity was 0.84 decimal.", True),
    ("units-humidity-percent", {"value": 0.8404}, "The mean relative humidity was 0.84 dimensionless.", True),
    # brackets and thousands separators (d)
    ("units-kiel-celsius", {"value": -0.7}, "The mean was -0.7 (°C).", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for 14,821 seconds.", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for 14,821 minutes.", False),
    ("units-wind-speed", {"value": 3.0}, "The mean wind speed was 3,0 m/s.", True),
    ("units-wind-speed", {"value": 3.0}, "Mean wind speed: 3.0 m s-1", True),
    ("units-kiel-celsius", {"value": -0.7}, "Die Tagesmitteltemperatur betrug \N{MINUS SIGN}0,7 °C.", True),
    # a table is read by its value column: another cell that fits another unit does not make it fail (e)
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "date,precipitation_amount\n2026-10-14,0.0\n2026-10-15,1.6\n2026-10-16,15.5\n2026-10-17,2\n\nThe unit is mm.",
        True,
    ),
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "station_id,date,precipitation_amount\n01975,2026-10-16,15.5\n\nThe precipitation column is in cm, not inches.",
        False,
    ),
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "date,precipitation_amount\n2026-10-16,15.5\n\nThe column is in millimetres, as the glossary says.",
        True,
    ),
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "date\tprecipitation_amount (mm)\n2026-10-16\t15.5",
        True,
    ),
    # every temperature of a forecast with a unit must fit the span (f)
    ("units-lax-forecast-celsius", {"min": 14.0, "max": 24.0}, "Tomorrow afternoon 20 °C, at night 45 °C.", False),
    ("units-lax-forecast-celsius", {"min": 14.0, "max": 24.0}, "Tomorrow at 15:00 about 20°C, at 18:00 21 °C.", True),
    ("units-lax-forecast-celsius", {"min": 14.0, "max": 24.0}, "Tomorrow afternoon about 68 °F (20 °C).", True),
    ("units-lax-forecast-celsius", {"min": 14.0, "max": 24.0}, "Tomorrow afternoon 20 °C (293 K).", True),
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

    result = bench.unit_check(answer, fact, {"value": 15.5})

    assert (result["ok"], result["ok_figures"], result["failures"]) == (True, ["15.5"], [])


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


def _stream(tmp_path: Path, *records: dict[str, Any], name: str = "s.jsonl") -> Path:
    """Write records as a transcript."""
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def _use(tool: str, uid: str, **arguments: Any) -> dict[str, Any]:  # noqa: ANN401
    """Build an assistant record that calls a tool of the server."""
    block = {"type": "tool_use", "id": uid, "name": f"{PREFIX}{tool}", "input": arguments}
    return {"type": "assistant", "message": {"id": f"m{uid}", "content": [block], "usage": {"output_tokens": 1}}}


def _result(uid: str, content: Any, *, error: bool = False) -> dict[str, Any]:  # noqa: ANN401
    """Build a user record that answers a tool call."""
    block = {"type": "tool_result", "tool_use_id": uid, "content": content, "is_error": error}
    return {"type": "user", "message": {"content": [block]}}


def test_a_run_against_no_server_is_invalid_not_a_failure(tmp_path: Path) -> None:
    """A server that was not connected, or offered no tool, says nothing about the model."""
    init = {
        "type": "system",
        "subtype": "init",
        "tools": [],
        "mcp_servers": [{"name": "wetterdienst", "status": "failed"}],
    }
    failed = bench.parse_transcript(_stream(tmp_path, init), PREFIX)
    no_tools = bench.parse_transcript(
        _stream(tmp_path, {**init, "mcp_servers": [{"name": "wetterdienst", "status": "connected"}]}, name="n.jsonl"),
        PREFIX,
    )
    fine = bench.parse_transcript(
        _stream(
            tmp_path,
            {**init, "tools": [f"{PREFIX}values"], "mcp_servers": [{"name": "wetterdienst", "status": "connected"}]},
            name="f.jsonl",
        ),
        PREFIX,
    )

    assert failed["invalid"] is True
    assert "not connected" in failed["invalid_reason"]
    assert no_tools["invalid"] is True
    assert "offered no tool" in no_tools["invalid_reason"]
    assert fine["invalid"] is False
    assert (
        bench.evaluate(CASE, {**failed, "calls": [_call("stations", {"name": "Kiel"})], "steps": 1}, DEFAULTS)[
            "mechanical_pass"
        ]
        is False
    )


def test_a_call_without_a_result_is_a_step_and_meets_no_checkpoint(tmp_path: Path) -> None:
    """A budget stop or a timeout leaves a tool_use no result answered: it is not ok, and it reads nothing."""
    run = bench.parse_transcript(_stream(tmp_path, _use("stations", "a", name="Kiel")), PREFIX)
    result = bench.evaluate(CASE, run, DEFAULTS)

    assert run["steps"] == 1
    assert run["calls"][0]["ok"] is False
    assert run["calls"][0]["unanswered"] is True
    assert run["unanswered_calls"] == 1
    assert result["checkpoints"]["k"] == 0
    assert result["mechanical_pass"] is False


def test_a_spilled_result_is_measured_by_its_size_not_its_notice(tmp_path: Path) -> None:
    """A result over the limit is saved to a file the tested agent cannot open; the call carries its real size."""
    notice = "Error: result (358,696 characters) exceeds maximum allowed tokens. Output has been saved to /x/y.txt."
    run = bench.parse_transcript(
        _stream(tmp_path, _use("stations", "a", all=True), _result("a", notice, error=True)), PREFIX
    )

    assert run["calls"][0]["spilled"] is True
    assert run["calls"][0]["result_chars"] == 358696
    assert run["spilled_calls"] == 1
    assert run["tool_result_chars_sum"] == 358696


@pytest.mark.parametrize("indent", [None, 2])
def test_the_metadata_is_read_from_the_json_whatever_its_layout(tmp_path: Path, indent: int | None) -> None:
    """A pretty-printed answer, or one with another key order, gives the same version and snapshot."""
    meta = {
        "data_updated_at": "2026-10-28T11:49:00+00:00",
        "retrieved_at": "2026-10-28T17:00:00+00:00",
        "producer": {"version": "0.178.0", "name": "wetterdienst"},
    }
    body = json.dumps({"alerts": [], "result": {"stations": [], "metadata": meta}}, indent=indent)
    run = bench.parse_transcript(_stream(tmp_path, _use("alerts", "a"), _result("a", body)), PREFIX)

    assert run["server_versions"] == ["0.178.0"]
    assert run["calls"][0]["data_updated_at"] == "2026-10-28T11:49:00+00:00"


def test_a_list_answer_has_no_metadata_and_that_is_fine(tmp_path: Path) -> None:
    """The glossary answers a list: no version, no snapshot, no error."""
    run = bench.parse_transcript(
        _stream(tmp_path, _use("glossary", "a"), _result("a", '{"result": [{"name": "x"}]}')), PREFIX
    )

    assert run["server_versions"] == []
    assert run["calls"][0]["data_updated_at"] is None


def test_a_claim_that_a_network_serves_a_place_is_checked_against_the_subjects_own_stations(tmp_path: Path) -> None:
    """The stations the subject got listed near a place show which network serves it; the answer must name one."""
    fact = next(
        f
        for f in bench.find_case(bench.load_cases(), "providers-brazil")["facts"]
        if f["kind"] == "network_serves_place"
    )
    listing = {
        "result": {
            "stations": [
                {"station_id": "83779", "name": "SAO PAULO CONGONHAS", "latitude": -23.63, "longitude": -46.66}
            ]
        }
    }
    far = {"result": {"stations": [{"station_id": "10147", "name": "HAMBURG", "latitude": 53.6, "longitude": 10.0}]}}
    records = [
        _use("stations", "a", provider="dwd", network="mosmix", latitude=-23.55, longitude=-46.63),
        _result("a", json.dumps(listing)),
        _use("stations", "b", provider="noaa", network="ghcn", name="Hamburg"),
        _result("b", json.dumps(far)),
    ]
    run = bench.parse_transcript(_stream(tmp_path, *records), PREFIX)

    named = bench.network_serves({**run, "answer": "DWD's mosmix network has stations near Sao Paulo."}, fact)
    unnamed = bench.network_serves({**run, "answer": "NOAA ghcn has data for Brazil."}, fact)

    assert named["ok"] is True
    assert named["named"][0]["station"] == "83779"
    assert unnamed["ok"] is False
    assert unnamed["stations_near"][0]["network"] == "mosmix"


def test_the_cases_of_the_brazil_claim_hold_for_the_subjects_stations_only() -> None:
    """No `ground_truth` call the judge cannot follow: the claim is checked by the script, from the transcript."""
    fact = next(
        f
        for f in bench.find_case(bench.load_cases(), "providers-brazil")["facts"]
        if f["kind"] == "network_serves_place"
    )

    assert "ground_truth" not in fact
    assert fact["radius_km"] > 0


class _McpHandler(http.server.BaseHTTPRequestHandler):
    """A tiny streamable-HTTP MCP endpoint: initialize, the initialized notification and tools/list."""

    tools: ClassVar[list[dict[str, Any]]] = []

    def do_POST(self) -> None:
        """Answer one JSON-RPC message."""
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if "id" not in body:
            self.send_response(202)
            self.end_headers()
            return
        result: dict[str, Any] = {"serverInfo": {"name": "Wetterdienst", "version": "9.9.9"}}
        if body["method"] == "tools/list":
            result = {"tools": self.tools}
        payload = (
            f"event: message\ndata: {json.dumps({'jsonrpc': '2.0', 'id': body['id'], 'result': result})}\n\n".encode()
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Mcp-Session-Id", "abc")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        """Answer `/api/version` as the wetterdienst does."""
        payload = b'{"version": "9.9.9"}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object) -> None:
        """Keep the test output quiet."""


@pytest.fixture
def mcp_url() -> Iterator[str]:
    """Serve a fake MCP endpoint with two tools on a free local port."""
    _McpHandler.tools = [
        {
            "name": "values",
            "description": "x" * 10,
            "inputSchema": {"type": "object", "properties": {"a": {}}},
            "outputSchema": {"type": "object"},
        },
        {"name": "glossary", "description": "y" * 5, "inputSchema": {"type": "object"}},
    ]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _McpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/mcp/v1"
    server.shutdown()


def test_a_server_is_probed_and_its_tools_list_measured(mcp_url: str) -> None:
    """`probe` gives the serverInfo, the tool count and the version; `tools-size` the characters of each part."""
    probed = bench.probe(mcp_url)
    size = bench.tools_size(mcp_url)

    assert probed["tools"] == 2
    assert probed["server_info"] == {"name": "Wetterdienst", "version": "9.9.9"}
    assert probed["wetterdienst_version"] == "9.9.9"
    assert "| values | 10 | 39 | 17 |" in size
    assert "| glossary | 5 | 17 | 2 |" in size
    assert "characters in all: " in size


def test_a_run_fails_fast_without_a_server_a_prompt_or_claude(
    tmp_path: Path, mcp_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exit 2 for a bad argument or a missing claude, 3 for a server that does not answer: before any model is paid."""
    prompt = tmp_path / "p.txt"
    prompt.write_text("hi", encoding="utf-8")
    out = str(tmp_path / "o.jsonl")

    monkeypatch.setattr(bench.shutil, "which", lambda _name: None)
    assert bench.run_subject("haiku", mcp_url, "wetterdienst", str(prompt), out, 5, 0.1) == 2
    monkeypatch.setattr(bench.shutil, "which", lambda _name: "/bin/true")
    assert bench.run_subject("haiku", mcp_url, "wetterdienst", str(tmp_path / "missing"), out, 5, 0.1) == 2
    assert bench.run_subject("haiku", "http://x/$(id)", "wetterdienst", str(prompt), out, 5, 0.1) == 2
    assert bench.run_subject("haiku", "http://127.0.0.1:1/mcp/v1", "wetterdienst", str(prompt), out, 5, 0.1) == 3
    assert bench.run_subject("haiku", mcp_url, "bad name", str(prompt), out, 5, 0.1) == 2
    assert bench.run_subject("haiku", mcp_url, "wetterdienst", str(prompt), out, 5, 0.1, label="a b;c") == 2


def test_a_run_leaves_the_probes_answer_and_the_label_next_to_its_transcript(
    tmp_path: Path, mcp_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sidecar holds what the probe said (a glossary run has no metadata block), the label and the mode."""
    fake = tmp_path / "claude"
    fake.write_text(
        '#!/bin/sh\nif [ "$1" = "--version" ]; then echo 9.9.9; exit 0; fi\necho \'{"type":"result","result":"x"}\'\n',
        encoding="utf-8",
    )
    fake.chmod(0o755)
    prompt = tmp_path / "p.txt"
    prompt.write_text("hi", encoding="utf-8")
    out = tmp_path / "o.jsonl"
    monkeypatch.setattr(bench.shutil, "which", lambda _name: str(fake))
    monkeypatch.setattr(bench.Path, "home", classmethod(lambda _cls: tmp_path / "home"))

    code = bench.run_subject("haiku", mcp_url, "wetterdienst", str(prompt), str(out), 20, 0.1, label="abc1234+dirty")

    side = json.loads(Path(f"{out}.meta.json").read_text(encoding="utf-8"))
    assert code == 0
    assert out.read_text(encoding="utf-8").strip() == '{"type":"result","result":"x"}'
    assert side["mode"] == "headless"
    assert side["label"] == "abc1234+dirty"
    assert side["claude_version"] == "9.9.9"
    assert side["server_info"] == {"name": "Wetterdienst", "version": "9.9.9"}
    assert side["wetterdienst_version"] == "9.9.9"


def test_both_sides_count_the_same_repeats_of_every_case() -> None:
    """A repeat that is missing on one side is taken out of the other: real counts, paired by repeat."""
    cases = {(f"c{i}", "small"): 5 for i in range(40)}
    before = _numbered(_results(cases, n=5))
    after = _numbered(_results({**cases, ("c1", "small"): 0}, n=5))
    after["runs"] = [r for r in after["runs"] if not (r["case"] in {"c2", "c3"} and r["repeat"] == 3)]

    text = bench.compare(before, after)

    assert "POOLED small (198 runs on each side" in text
    assert "2 valid runs were left out so that both sides count the same repeats of every case" in text
    assert "big drop in c1 [small]: passed 5/5 -> 0/5" in text


def _numbered(results: dict[str, Any]) -> dict[str, Any]:
    """Give the runs of every case the repeat numbers 1, 2, ... in the order they are in."""
    counts: dict[tuple[str, str], int] = {}
    for run in results["runs"]:
        key = (run["case"], run["tier"])
        counts[key] = counts.get(key, 0) + 1
        run["repeat"] = counts[key]
    return results


def test_a_cold_first_repeat_that_is_invalid_on_one_side_leaves_both_sides_together() -> None:
    """Keeping the first k valid runs would drop a warm repeat of one side and a cold one of the other."""
    cases = [f"c{i}" for i in range(27)]
    before = _numbered(_results(dict.fromkeys(((c, "small") for c in cases), 5), n=5))
    after = _numbered(_results(dict.fromkeys(((c, "small") for c in cases), 5), n=5))
    for results in (before, after):
        for run in results["runs"]:
            if run["case"] in cases[:4] and run["repeat"] == 1:
                run["passed"] = run["facts_ok"] = False  # a cold start fails on both sides
    for run in after["runs"]:
        if run["case"] in cases[:4] and run["repeat"] == 1:
            run["invalid"] = True

    text = bench.compare(before, after)

    assert "difference +0.0%" in text
    assert "4 valid runs were left out" in text
    assert "=> NO WORSE" in text


def test_a_tier_whose_shared_repeats_are_too_few_is_inconclusive() -> None:
    """Invalid runs that depend on the order leave little in common: under 60 % of a case's runs, no verdict."""
    cases = {(f"c{i}", "small"): 5 for i in range(30)}
    before = _numbered(_results(cases, n=5))
    after = _numbered(_results(cases, n=5))
    for run in after["runs"]:
        if run["case"] == "c0" and run["repeat"] in {2, 4, 5}:
            run["invalid"] = True

    text = bench.compare(before, after)

    assert (
        "POOLED small: INCONCLUSIVE, the repeats that are valid on both sides leave fewer than 60 % of the 5 repeats "
        "of 1 "
        "cases (c0 (2 of 5: previous 5 valid, current 2 valid))" in text
    )
    assert "=> NO WORSE" not in text


def test_a_collapsed_case_is_printed_next_to_a_no_worse_pool() -> None:
    """A pool of 20 cases that is no worse can hide one that fell to zero: it is named whatever the verdict says."""
    cases = {(f"c{i}", "small"): 20 for i in range(20)}
    before = _results(cases, n=20)
    after = _results({**cases, ("c0", "small"): 0}, n=20)

    text = bench.compare(before, after)

    assert "=> NO WORSE" in text
    assert "big drop in c0 [small]: passed 20/20 -> 0/20" in text


@pytest.mark.parametrize(
    ("before", "after", "verdict"),
    [
        ((900, 1000), (700, 1000), "WORSE"),
        ((900, 1000), (820, 1000), "inconclusive"),
        ((126, 140), (112, 140), "inconclusive"),
        ((900, 1000), (880, 1000), "no worse"),
    ],
)
def test_the_verdict_is_one_non_inferiority_decision(
    before: tuple[int, int], after: tuple[int, int], verdict: str
) -> None:
    """No worse: the lower bound is above minus the margin. WORSE: the upper bound is below it. Else inconclusive."""
    assert bench._non_inferiority("passed", *before, *after, 0.10)[0] == verdict  # noqa: SLF001


def test_a_drop_within_the_margin_is_visible() -> None:
    """A significant but tolerated drop is no worse and says it is a drop."""
    verdict, text = bench._non_inferiority("passed", 1000, 1000, 950, 1000, 0.10)  # noqa: SLF001

    assert verdict == "no worse"
    assert "(a drop, lower but within the margin)" in text


def test_a_refused_comparison_exits_with_a_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The command line exits non-zero when it refuses, so that no script reads a verdict that is not there."""
    ok = tmp_path / "ok.json"
    other = tmp_path / "other.json"
    ok.write_text(json.dumps(_results({("a", "small"): 5}, label="x")), encoding="utf-8")
    other.write_text(json.dumps(_results({("a", "small"): 5}, mode="subagent", label="y")), encoding="utf-8")

    assert bench.main(["compare", str(ok), str(ok), "--same-server"]) == 0
    assert bench.main(["compare", str(ok), str(other)]) == 4
    assert "the mode (headless or subagent) differs" in capsys.readouterr().out


def test_two_sides_that_report_one_version_must_carry_labels() -> None:
    """Local main and a branch say the same version: without a label that differs, the sides cannot be told apart."""
    plain = _results({("a", "small"): 5}, server_version="0.178.0")
    same_label = _results({("a", "small"): 5}, server_version="0.178.0", label="abc123")
    other_label = _results({("a", "small"): 5}, server_version="0.178.0", label="def456")

    assert "cannot be told apart" in bench.compare(plain, plain)
    assert "cannot be told apart" in bench.compare(same_label, same_label)
    assert "cannot be told apart" not in bench.compare(same_label, other_label)
    assert "cannot be told apart" not in bench.compare(plain, plain, same_server=True)


def test_cases_only_in_the_previous_file_are_counted() -> None:
    """A case that left the file is left out and said so."""
    before = _results({("a", "small"): 5, ("gone", "small"): 5})
    after = _results({("a", "small"): 5})

    assert "left out: 0 only in the current file, 0 with a changed case, 1 only in the previous file" in bench.compare(
        before, after
    )


def test_the_invalid_share_is_counted_over_the_compared_cases_only() -> None:
    """A case that is not compared does not count: 4 invalid runs of a skipped case are no reason to refuse."""
    before = _results({("a", "small"): 40, ("b", "small"): 5}, n=40, hashes={"a": "h1", "b": "h1"})
    after = _results(
        {("a", "small"): 40, ("b", "small"): 5}, n=40, hashes={"a": "h1", "b": "h2"}, invalid={("b", "small"): 30}
    )

    text = bench.compare(before, after)

    assert "not compared" not in text
    assert "1 with a changed case" in text


def test_a_run_that_never_ran_is_an_invalid_record_with_its_reason() -> None:
    """Exit 3 or 124 of a run in the middle of a batch: the run is recorded as invalid, not missing and not failed."""
    case = bench.find_case(bench.load_cases(), "glossary-temperature-air-mean-2m")
    record = bench.failed_run(case, "small", 2, "the server did not answer (exit 3)")
    results = {"meta": {}, "runs": [record, {**record, "repeat": 3}]}

    assert record["invalid"] is True
    assert record["invalid_reason"] == "the server did not answer (exit 3)"
    assert bench.aggregate(results["runs"])["n"] == 0
    assert "2 of 2 runs are invalid" in bench.report(results)


def test_a_subagent_transcript_must_show_the_servers_tools(tmp_path: Path) -> None:
    """A subagent's transcript has no init record: the server's tools must be listed or deferred in it, or called."""
    attached = {
        "type": "attachment",
        "attachment": {"type": "deferred_tools_record", "entries": [{"name": f"{PREFIX}values"}]},
    }
    without = bench.parse_transcript(_stream(tmp_path, {"type": "attachment", "attachment": {"type": "date"}}), PREFIX)
    deferred = bench.parse_transcript(_stream(tmp_path, attached, name="d.jsonl"), PREFIX)
    called = bench.parse_transcript(_stream(tmp_path, _use("values", "a"), name="c.jsonl"), PREFIX)

    assert without["invalid"] is True
    assert "no tool of the server" in without["invalid_reason"]
    assert deferred["invalid"] is False
    assert called["invalid"] is False


def test_a_spill_is_a_call_that_read_nothing_whatever_is_error_says(tmp_path: Path) -> None:
    """The notice of a result saved to a file makes the call not ok and spilled even if `is_error` is false."""
    notice = "Error: result (358,696 characters) exceeds maximum allowed tokens. Output has been saved to /x/y.txt."
    run = bench.parse_transcript(
        _stream(tmp_path, _use("stations", "a", all=True), _result("a", notice, error=False)), PREFIX
    )

    assert run["calls"][0]["spilled"] is True
    assert run["calls"][0]["ok"] is False


def test_an_unrecognised_spill_notice_is_warned_about(tmp_path: Path) -> None:
    """A short result that talks of a file in words bench.py does not know is counted and warned about, not trusted."""
    notice = "The output was too large and was stored at /home/x/.claude/projects/p/tool-results/mcp-stations.txt"
    run = bench.parse_transcript(_stream(tmp_path, _use("stations", "a"), _result("a", notice)), PREFIX)
    results = {
        "meta": {},
        "runs": [
            {
                **bench.failed_run(bench.find_case(bench.load_cases(), "alerts-kiel"), "small", 1, "x"),
                "invalid": False,
                "passed": False,
                "spill_unrecognised_calls": run["spill_unrecognised_calls"],
            }
        ],
    }

    assert run["spill_unrecognised_calls"] == 1
    assert "WARNING: 1 tool results look like a result saved to a file" in bench.report(results)


def _project_dirs(home: Path) -> Path:
    """Make the `.claude/projects` of a fake home."""
    root = home / ".claude" / "projects"
    root.mkdir(parents=True)
    return root


def test_cleanup_removes_only_old_directories_of_this_benchmarks_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anchored to the slug of the temp dir, older than a few minutes, never through a symlink."""
    import os  # noqa: PLC0415
    import time  # noqa: PLC0415

    home = tmp_path / "home"
    root = _project_dirs(home)
    monkeypatch.setattr(bench.Path, "home", classmethod(lambda _cls: home))
    prefix = bench._run_prefix()  # noqa: SLF001
    old, fresh, other_tmp = (
        root / f"{prefix}AbC123",
        root / f"{prefix}FRESH1",
        root / "-Users-x-dev-mcpbench-subject-analysis",
    )
    for directory in (old, fresh, other_tmp):
        (directory / "memory").mkdir(parents=True)
    past = time.time() - 3600
    for directory in (old, other_tmp):
        os.utime(directory, (past, past))
    target = tmp_path / "precious"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    (root / f"{prefix}LINKED").symlink_to(target, target_is_directory=True)
    os.utime(root / f"{prefix}LINKED", (past, past), follow_symlinks=False)

    assert bench.cleanup() == 1
    assert not old.exists()
    assert fresh.exists(), "a younger directory may be a run in progress"
    assert other_tmp.exists(), "a real project whose path holds the word is not a benchmark run"
    assert (target / "keep.txt").exists(), "a symlink is never followed"
    assert (root / f"{prefix}LINKED").is_symlink()
    assert bench._remove_project_dir(f"{prefix}LINKED") is False, "a symlink is refused and not counted"  # noqa: SLF001


def test_the_directory_of_a_run_is_removed_at_once_and_only_that_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After its own run the exact directory goes whatever its age; a name that is not the run's slug does not."""
    home = tmp_path / "home"
    root = _project_dirs(home)
    monkeypatch.setattr(bench.Path, "home", classmethod(lambda _cls: home))
    prefix = bench._run_prefix()  # noqa: SLF001
    ours, theirs = root / f"{prefix}XyZ987", root / "-Users-x-mcpbench-subject-real-project"
    ours.mkdir()
    theirs.mkdir()

    assert bench._remove_project_dir(f"{prefix}XyZ987") is True  # noqa: SLF001
    assert bench._remove_project_dir("-Users-x-mcpbench-subject-real-project") is False  # noqa: SLF001
    assert bench._remove_project_dir(f"../{prefix}XyZ987") is False  # noqa: SLF001
    assert theirs.exists()


#: (case, what the judge read, an answer with RESULT lines, whether the unit check passes): read strictly and alone
RESULT_ANSWERS = [
    (
        "units-kiel-celsius",
        {"value": -0.7},
        "The mean was -0.7 °C.\nRESULT: -0.7 °C | daily mean at Kiel-Holtenau",
        True,
    ),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 degC | daily mean", True),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: \N{MINUS SIGN}0,7 °C | daily mean", True),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 °C | mean\nRESULT: -3.1 °C | the minimum", True),
    ("units-kiel-celsius", {"value": -0.7}, "- RESULT: -0.7 °C | daily mean", True),
    ("units-kiel-celsius", {"value": -0.7}, "It was -0.7 K in prose.\nRESULT: -0.7 °C | daily mean", True),
    ("units-kiel-celsius", {"value": -0.7}, "It was -0.7 °C in prose.\nRESULT: -0.7 K | daily mean", False),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 K | daily mean", False),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: 272.45 K | daily mean", False),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 °F | daily mean", False),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 °C | daily mean\nRESULT: 30.7 °C | daily mean", False),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 degrees | daily mean", False),
    # slips in the unit slot are forgiven
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 °C. | daily mean", True),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 \N{DEGREE CELSIUS} | daily mean", True),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 \N{MASCULINE ORDINAL INDICATOR}C | daily mean", True),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 °C (as returned) | daily mean", True),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 degrees Celsius (°C) | daily mean", True),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 [°C] | daily mean", True),
    ("units-kiel-celsius", {"value": -0.7}, "**RESULT:** -0.7 °C | daily mean", True),
    ("units-kiel-celsius", {"value": -0.7}, "result: -0.7 °C | daily mean", True),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -1 °C | daily mean, rounded", True),
    ("units-humidity-percent", {"value": 0.8404}, "RESULT: 84 %RH | humidity", True),
    ("units-wind-speed", {"value": 3.0}, "RESULT: 3.0 m s\N{SUPERSCRIPT MINUS}\N{SUPERSCRIPT ONE} | wind", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 4 h | sunshine", True),
    # restating the same thing in another unit is no contradiction, a correction is one
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 °C | daily mean\nRESULT: -0.5 °C | daily mean", True),
    (
        "units-kiel-celsius",
        {"value": -0.7},
        "RESULT: 3.2 °C | daily mean air temperature\nRESULT: -0.7 °C | corrected value",
        False,
    ),
    (
        "units-kiel-celsius",
        {"value": -0.7},
        "RESULT: 3.2 °C | Kiel daily mean\nRESULT: -0.7 °C | daily mean air temperature at Kiel-Holtenau",
        False,
    ),
    (
        "units-kiel-celsius",
        {"value": -0.7},
        "RESULT: 3.2 °C | daily mean\nRESULT: -0.7 | daily mean\nIt was -0.7 °C.",
        False,
    ),
    ("units-kiel-celsius", {"value": -0.7}, "1. RESULT: -0.7 °C | daily mean", True),
    (
        "units-precipitation-mm",
        {"value": 15.5},
        "RESULT: 15.5 mm | precipitation\nRESULT: 1.6 mm | the day before",
        True,
    ),
    (
        "units-precipitation-mm",
        {"value": 15.5},
        "RESULT: 15.5 mm | precipitation\nRESULT: 1.6 mm | precipitation on 2026-10-16",
        False,
    ),
    ("units-precipitation-mm", {"value": 15.5}, "RESULT: 2 cm | precipitation", True),
    ("units-precipitation-mm", {"value": 15.5}, "RESULT: 20 mm | precipitation", False),
    ("units-precipitation-mm", {"value": 15.5}, "RESULT: 1 cm | precipitation", False),
    ("units-wind-speed", {"value": 3.0}, "RESULT: 6 kn | wind", True),
    ("units-wind-speed", {"value": 3.0}, "RESULT: 7 kn | wind", False),
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "date,temperature,precipitation\n2026-10-16,15.5,1.6\n\nTABLE-UNIT: precipitation | mm",
        False,
    ),
    (
        "units-csv-with-unit",
        {"value": 15.5},
        (
            "date,precipitation_amount\n2026-10-16,15.5\n\nTABLE-UNIT: precipitation_amount | mm\n"
            "RESULT: 1.6 mm | precipitation on 2026-10-16"
        ),
        False,
    ),
    (
        "units-kiel-celsius",
        {"value": -0.7},
        "RESULT: 3.2 °C | daily mean air temperature\nRESULT: -0.7 °C | daily mean air temperature at Kiel",
        False,
    ),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 °C | daily mean\nRESULT: -3.1 °C | daily minimum", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 14821 s | sunshine\nRESULT: 4.1 h | sunshine", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 14821 s | sunshine\nRESULT: 2.0 h | sunshine", False),
    ("units-fahrenheit", {"value": -0.7}, "RESULT: -0.7 °C | mean\nRESULT: 30.7 °F | mean", True),
    ("units-wind-speed", {"value": 3.0}, "RESULT: 3.0 m/s | wind\nRESULT: 10.8 km/h | wind", True),
    ("units-humidity-percent", {"value": 0.8404}, "RESULT: 0.84 fraction | humidity\nRESULT: 84 % | humidity", True),
    ("units-kiel-celsius", {"value": -0.7}, "RESULT: -0.7 °C | mean\nRESULT: -0.70 °C | mean", True),
    (
        "units-lax-forecast-celsius",
        {"min": 14.0, "max": 24.0},
        "RESULT: 20 °C | forecast\nRESULT: 21 °C | forecast",
        True,
    ),
    ("units-fahrenheit", {"value": -0.7}, "RESULT: 30.7 °F | daily mean", True),
    ("units-fahrenheit", {"value": -0.7}, "RESULT: -0.7 °C | in Celsius\nRESULT: 30.7 °F | in Fahrenheit", True),
    ("units-fahrenheit", {"value": -0.7}, "RESULT: -0.7 °C | daily mean", False),
    ("units-fahrenheit", {"value": -0.7}, "RESULT: 30.7 K | daily mean", False),
    ("units-fahrenheit", {"value": -0.7}, "RESULT: 33.3 °F | daily mean", False),
    ("units-humidity-percent", {"value": 0.8404}, "RESULT: 84 % | mean relative humidity", True),
    ("units-humidity-percent", {"value": 0.8404}, "RESULT: 84 Prozent | mean relative humidity", True),
    ("units-humidity-percent", {"value": 0.8404}, "RESULT: 0.84 fraction | mean relative humidity", True),
    ("units-humidity-percent", {"value": 0.8404}, "RESULT: 0.84 % | mean relative humidity", False),
    ("units-humidity-percent", {"value": 0.8404}, "RESULT: 1 fraction | mean relative humidity", False),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 14821.2 s | sunshine", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 14 821 s | sunshine", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 14,821 seconds | sunshine", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 1.48212e4 s | sunshine", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 14821 Sekunden | sunshine", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 4.1 h | sunshine", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 247 min | sunshine", True),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 14821 minutes | sunshine", False),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 14821 hours | sunshine", False),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 14821 sun | sunshine", False),
    ("units-sunshine-seconds", {"value": 14821.2}, "RESULT: 14821 S | sunshine", True),
    ("units-wind-speed", {"value": 3.0}, "RESULT: 3.0 m/s | mean wind speed", True),
    ("units-wind-speed", {"value": 3.0}, "RESULT: 10.8 km/h | mean wind speed", True),
    ("units-wind-speed", {"value": 3.0}, "RESULT: 3.0 km/h | mean wind speed", False),
    ("units-wind-speed", {"value": 3.0}, "RESULT: 3 Bft | mean wind speed", False),
    ("units-precipitation-mm", {"value": 15.5}, "RESULT: 15.5 mm | precipitation", True),
    (
        "units-precipitation-mm",
        {"value": 15.5},
        "RESULT: 15.5 mm | precipitation\nRESULT: 1.6 mm | the day before",
        True,
    ),
    ("units-precipitation-mm", {"value": 15.5}, "RESULT: 15.5 cm | precipitation", False),
    ("units-precipitation-mm", {"value": 15.5}, "RESULT: 15.5 inches | precipitation", False),
    ("units-lax-forecast-celsius", {"min": 14.0, "max": 24.0}, "RESULT: 20 °C | 15:00\nRESULT: 21 °C | 18:00", True),
    (
        "units-lax-forecast-celsius",
        {"min": 14.0, "max": 24.0},
        "RESULT: 20 °C | 15:00\nRESULT: 45 °C | at night",
        False,
    ),
    ("units-lax-forecast-celsius", {"min": 14.0, "max": 24.0}, "RESULT: 293 K | 15:00", False),
    (
        "units-lax-forecast-celsius",
        {"min": 14.0, "max": 24.0},
        "RESULT: 68 °F | 15:00\nRESULT: 20 °C | 15:00 in Celsius",
        True,
    ),
    # a table, with the unit of its column on a TABLE-UNIT line
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "date,precipitation_amount\n2026-10-15,0.0\n2026-10-16,15.5\nTABLE-UNIT: precipitation_amount | mm",
        True,
    ),
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "| date | precipitation_amount |\n|---|---|\n| 2026-10-16 | 15.5 |\n\nTABLE-UNIT: precipitation_amount | mm",
        True,
    ),
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "date,precipitation_amount\n2026-10-15,1.6\n2026-10-16,15.5\n\nTABLE-UNIT: precipitation_amount | mm",
        True,
    ),
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "date,precipitation_amount\n2026-10-16,15.5\n\nTABLE-UNIT: precipitation_amount | cm",
        False,
    ),
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "date,precipitation_amount\n2026-10-16,15.5\n\nTABLE-UNIT: precipitation_amount | inches",
        False,
    ),
    ("units-csv-with-unit", {"value": 15.5}, "TABLE-UNIT: precipitation_amount | mm", False),
    ("units-csv-with-unit", {"value": 15.5}, "RESULT: 15.5 mm | precipitation on 2026-10-16", True),
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "date,precipitation_amount\n2026-10-16,15.5 mm\n\nTABLE-UNIT: precipitation_amount | mm (millimetres)",
        True,
    ),
    # the tool's own CSV has a column `value`; the figure must be on the date asked for
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "station_id,date,value\n01975,2026-10-15,0.0\n01975,2026-10-16,15.5\n\nTABLE-UNIT: value | mm",
        True,
    ),
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "date,precipitation_amount\n2026-10-15,15.5\n2026-10-16,0.0\n\nTABLE-UNIT: precipitation_amount | mm",
        False,
    ),
    (
        "units-csv-with-unit",
        {"value": 15.5},
        "date,precipitation_amount\n2026-10-16,15.5\n\nTABLE-UNIT: precipitation_amount | mm\nTABLE-UNIT: date | text",
        True,
    ),
]


@pytest.mark.parametrize(
    ("case_id", "truth", "answer", "expected"),
    [pytest.param(*row, id=f"{row[0]}-{i}") for i, row in enumerate(RESULT_ANSWERS)],
)
def test_the_result_lines_are_read_strictly_and_alone(
    case_id: str,
    truth: dict[str, float],
    answer: str,
    expected: bool,  # noqa: FBT001
) -> None:
    """A RESULT line with the right unit passes; the prose around it, right or wrong, does not decide."""
    result = bench.unit_check(answer, _unit_fact(case_id), truth)

    assert result["ok"] is expected, result
    assert result["mode"] == "result"


def test_every_unit_case_is_tried_with_result_lines_good_and_bad() -> None:
    """Each unit case has RESULT-line answers of both kinds, as it has fallback ones."""
    for case_id in {c["id"] for c in bench.load_cases()["cases"] if c["kind"] == "units"}:
        verdicts = {row[3] for row in RESULT_ANSWERS if row[0] == case_id}
        assert verdicts == {True, False}, case_id


def test_an_answer_without_result_lines_is_read_tolerantly_and_reported() -> None:
    """The fallback reads prose and tables, and says so: the format is a metric of its own, not a silent pass."""
    fact = _unit_fact("units-kiel-celsius")
    strict = bench.unit_check("RESULT: -0.7 °C | daily mean", fact, {"value": -0.7})
    fallback = bench.unit_check("The daily mean was -0.7 °C.", fact, {"value": -0.7})
    bare = bench.unit_check("RESULT: -0.7 | daily mean", fact, {"value": -0.7})
    case = bench.find_case(bench.load_cases(), "units-kiel-celsius")
    malformed = bench.unit_check("RESULT: about -0.7 °C | daily mean\nThe mean was -0.7 °C.", fact, {"value": -0.7})

    assert (strict["mode"], strict["format_violation"], strict["ok"]) == ("result", False, True)
    assert (fallback["mode"], fallback["format_violation"], fallback["unit_fallback"], fallback["ok"]) == (
        "fallback",
        True,
        True,
        True,
    )
    assert (bare["mode"], bare["ok"]) == ("fallback", False)
    assert bench.format_violation(case, "RESULT: -0.7 | daily mean") is True
    assert (malformed["mode"], malformed["format_violation"]) == ("fallback", True)


@pytest.mark.parametrize(
    ("case_id", "truth", "answer", "expected"),
    [
        # a forecast table or list may carry no temperature outside the span, in the fallback too
        (
            "units-lax-forecast-celsius",
            {"min": 14.0, "max": 24.0},
            "| time | temp (°C) |\n|---|---|\n| 15:00 | 20 |\n| 18:00 | 45 |",
            False,
        ),
        (
            "units-lax-forecast-celsius",
            {"min": 14.0, "max": 24.0},
            "| time | temp |\n|---|---|\n| 15:00 | 20 °C |\n| 18:00 | 45 °C |",
            False,
        ),
        (
            "units-lax-forecast-celsius",
            {"min": 14.0, "max": 24.0},
            "- 15:00: 20 °C, clear\n- 18:00: 45 °C, clear",
            False,
        ),
        (
            "units-lax-forecast-celsius",
            {"min": 14.0, "max": 24.0},
            "| time | temp (°C) |\n|---|---|\n| 15:00 | 20 |\n| 18:00 | 21 |",
            True,
        ),
        # prose over several lines with the same number of commas is prose, not a table
        (
            "units-kiel-celsius",
            {"value": -0.7},
            "- Mean at 2 m: -0.7 °C, the lowest of the week\n- Minimum at 2 m: -3.1 °C, at night",
            True,
        ),
        (
            "units-precipitation-mm",
            {"value": 15.5},
            "Precipitation at Hamburg on 16 October: 15.5 mm, a wet day\nPrevious day at Hamburg: 1.6 mm, light rain",
            True,
        ),
        ("units-kiel-celsius", {"value": -0.7}, "- Mean: -0.7 K, as returned\n- Mean: -0.7 °C, converted", False),
        # the unit in a column of its own, in a row label, or before the figure
        (
            "units-kiel-celsius",
            {"value": -0.7},
            "| Parameter | Value | Unit |\n|---|---|---|\n| temperature_air_mean_2m | -0.7 | °C |",
            True,
        ),
        (
            "units-kiel-celsius",
            {"value": -0.7},
            "| Parameter | Value | Unit |\n|---|---|---|\n| temperature_air_mean_2m | -0.7 | K |",
            False,
        ),
        ("units-precipitation-mm", {"value": 15.5}, "date,precipitation_amount,unit\n2026-10-16,15.5,mm", True),
        ("units-kiel-celsius", {"value": -0.7}, "| Parameter | Value |\n|---|---|\n| Mean (°C) | -0.7 |", True),
        ("units-kiel-celsius", {"value": -0.7}, "Mean temperature (°C): -0.7", True),
        ("units-kiel-celsius", {"value": -0.7}, "Temperature [°C]\n-0.7", True),
        ("units-kiel-celsius", {"value": -0.7}, "Mean temperature [K]: -0.7", False),
        ("units-kiel-celsius", {"value": -0.7}, "The mean was -0.7 (unit °C).", True),
        # the column and the row of the date count in the fallback too
        (
            "units-csv-with-unit",
            {"value": 15.5},
            "date,precipitation_amount\n2026-10-15,15.5\n2026-10-16,0.0\n\nThe unit is mm.",
            False,
        ),
        (
            "units-csv-with-unit",
            {"value": 15.5},
            "date,temperature,precipitation\n2026-10-16,15.5,1.6\n\nThe unit is mm.",
            False,
        ),
        ("units-csv-with-unit", {"value": 15.5}, "date,precipitation_amount\n2026-10-16,15.5\n\nThe unit is mm.", True),
        # a figure with one significant digit is no rounded 0.8404
        ("units-humidity-percent", {"value": 0.8404}, "The mean relative humidity was 1 (as a fraction).", False),
        # thousands separators and exponents
        ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for 14 821 s.", True),
        ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for 14821\N{NARROW NO-BREAK SPACE}s.", True),
        ("units-sunshine-seconds", {"value": 14821.2}, "The sun shone for 1.48212e4 s.", True),
        ("units-sunshine-seconds", {"value": 14821.2}, "Die Sonne schien 14821 Sekunden.", True),
        ("units-humidity-percent", {"value": 0.8404}, "Die Luftfeuchte war 84 Prozent.", True),
    ],
)
def test_the_fallback_reads_the_layouts_models_use(
    case_id: str,
    truth: dict[str, float],
    answer: str,
    expected: bool,  # noqa: FBT001
) -> None:
    """Prose, lists and tables of several layouts, for an answer that left out the RESULT lines."""
    result = bench.unit_check(answer, _unit_fact(case_id), truth)

    assert result["ok"] is expected, result
    assert result["mode"] == "fallback"
    assert result["format_violation"] is True


def test_the_one_letter_rule_holds_in_both_modes() -> None:
    """`s` is a unit only as the unit of a figure: the `s` of `sun's` or a `sun` is none, in both modes."""
    fact = _unit_fact("units-sunshine-seconds")
    truth = {"value": 14821.2}

    assert bench.unit_check("The sun's duration at Hamburg, 16 October 2026, was 14821.", fact, truth)["ok"] is False
    assert bench.unit_check("RESULT: 14821 sun | sunshine", fact, truth)["ok"] is False
    assert bench.unit_check("RESULT: 14821 s | sunshine", fact, truth)["ok"] is True
    assert bench.unit_check("It shone 14821 s.", fact, truth)["ok"] is True
    table = "date,sunshine\n2026-10-16,14821\n\nThe sun's duration, as the server returns it."
    assert bench.unit_check(table, fact, truth)["ok"] is False, "the `s` of `sun's` names no unit of a table column"


def test_a_forbidden_unit_is_named_as_forbidden_not_as_unknown() -> None:
    """Kelvin is a unit the case forbids whatever the figure: the verdict says so, in both modes."""
    fact = _unit_fact("units-kiel-celsius")

    strict = bench.unit_check("RESULT: -0.7 K | daily mean", fact, {"value": -0.7})
    loose = bench.unit_check("It was -0.7 K.", fact, {"value": -0.7})

    assert "forbidden unit" in strict["failures"][0]["reason"]
    assert "forbidden unit" in loose["failures"][0]["reason"]


def test_the_big_drop_boundary_is_inclusive() -> None:
    """A case that fell by exactly 40 points (5/5 to 3/5) is named; one that fell by 20 is not."""
    before = _results({("a", "small"): 5, ("b", "small"): 5})

    assert "big drop in a [small]: passed 5/5 -> 3/5" in bench.compare(
        before, _results({("a", "small"): 3, ("b", "small"): 5})
    )
    assert "big drop" not in bench.compare(before, _results({("a", "small"): 4, ("b", "small"): 5}))


def test_a_drop_that_is_likely_worse_is_not_a_plain_inconclusive() -> None:
    """126/140 to 100/140: the interval is below zero but not beyond the margin; it says more runs would decide."""
    verdict, text = bench._non_inferiority("passed", 126, 140, 100, 140, 0.10)  # noqa: SLF001

    assert verdict == "inconclusive"
    assert "dropped: the whole interval is below zero but not beyond the margin" in text
    assert "dropped" not in bench._non_inferiority("passed", 126, 140, 130, 140, 0.10)[1]  # noqa: SLF001


def test_the_format_is_a_rate_of_its_own() -> None:
    """A run that left out the RESULT lines is a format violation, counted and decided like the other rates."""
    before = _results({("a", "small"): 50}, n=50)
    after = _results({("a", "small"): 50}, n=50)
    for run in before["runs"]:
        run["format_violation"] = False
    for i, run in enumerate(after["runs"]):
        run["format_violation"] = i < 30

    text = bench.compare(before, after)

    assert "follows the RESULT format 50/50 -> 20/50" in text
    assert "=> WORSE" in text
    assert "30/50" in bench.report(after)


def test_one_invalid_run_cuts_its_case_by_one_and_says_so() -> None:
    """Invalid runs within the 3 % do not block the tier: the case counts 49 runs on both sides, and it says so."""
    keys = {(f"c{i}", "small"): 50 for i in range(2)}
    before = _results(keys, n=50)
    after = _results(keys, n=50, invalid={("c0", "small"): 1})

    text = bench.compare(before, after)

    assert "POOLED small (99 runs on each side" in text
    assert "1 valid runs were left out" in text
    assert "=> NO WORSE" in text


def test_an_extra_run_on_one_case_is_a_repeat_outside_the_file_and_refused() -> None:
    """27 cases of 5 repeats, one of 40: the file says `repeats` 5, so repeats 6 to 40 are an error, not a weight."""
    names = [(f"c{i}", "small") for i in range(26)]
    big = ("big", "small")
    ns = {**dict.fromkeys(names, 5), big: 40}
    before = _numbered(_results({**dict.fromkeys(names, 5), big: 35}, ns=ns, repeats=5))
    fell = {k: (4 if i < 13 else 5) for i, k in enumerate(names)}
    after = _numbered(_results({**fell, big: 35}, ns=ns, repeats=5))

    text, refused = bench.compare_with_status(before, after)

    assert refused
    assert "the previous file has big [small] with repeat [6, 7, 8" in text
    assert "outside 1..5" in text


def test_a_timeout_is_a_failed_run_and_an_unreachable_server_an_invalid_one() -> None:
    """A strategy that makes the model slower must show as a failure, not disappear from the rates."""
    case = bench.find_case(bench.load_cases(), "glossary-temperature-air-mean-2m")
    timed_out = bench.failed_run(case, "small", 1, "timeout", invalid=False)
    unreachable = bench.failed_run(case, "small", 2, "the server did not answer (exit 3)")

    assert (timed_out["invalid"], timed_out["failure"], timed_out["passed"]) == (False, "timeout", False)
    assert (unreachable["invalid"], unreachable["invalid_reason"]) == (True, "the server did not answer (exit 3)")
    assert bench.aggregate([timed_out, unreachable])["n"] == 1
    assert bench.aggregate([timed_out, unreachable])["passed"] == 0


def test_a_timeout_without_a_transcript_has_no_metrics_not_zeros(tmp_path: Path) -> None:
    """A timed-out run that measured nothing is left out of the medians, so a slow strategy does not look smaller."""
    case = bench.find_case(bench.load_cases(), "glossary-temperature-air-mean-2m")
    nothing = bench.failed_run(case, "small", 1, "timeout", invalid=False)
    real = {
        **bench.failed_run(case, "small", 2, "x", invalid=False),
        "steps": 4,
        "tool_result_chars_sum": 900,
        "tool_result_chars_max": 900,
        "output_tokens": 70,
        "context_tokens_first": 26000,
        "total_tokens": 80000,
    }
    partial = _stream(tmp_path, _use("glossary", "a", parameter="temperature_air_mean_2m"), _result("a", "[]"))
    measured = bench.failed_run(case, "small", 3, "timeout", invalid=False, transcript=partial, defaults=DEFAULTS)

    assert nothing["steps"] is None
    assert nothing["tool_result_chars_sum"] is None
    assert bench.aggregate([nothing, real])["steps_median"] == 4
    assert bench.aggregate([nothing, real])["result_chars_median"] == 900
    assert bench.aggregate([nothing])["steps_median"] is None
    assert (measured["steps"], measured["checkpoints"]["k"], measured["failure"], measured["passed"]) == (
        1,
        1,
        "timeout",
        False,
    )


def test_the_failed_run_command_takes_a_kind(capsys: pytest.CaptureFixture[str]) -> None:
    """`--kind failed` records a timeout as a failed run, `--kind invalid` (the default) an unreachable server."""
    base = ["failed-run", "--case", "glossary-temperature-air-mean-2m", "--tier", "small", "--repeat", "2"]

    assert bench.main([*base, "--reason", "timeout", "--kind", "failed"]) == 0
    failed = json.loads(capsys.readouterr().out)
    assert bench.main([*base, "--reason", "no server"]) == 0
    invalid = json.loads(capsys.readouterr().out)

    assert (failed["invalid"], failed["failure"], failed["steps"]) == (False, "timeout", None)
    assert (invalid["invalid"], invalid["invalid_reason"]) == (True, "no server")


def test_the_timeout_is_capped_below_the_age_cleanup_waits_for(tmp_path: Path, mcp_url: str) -> None:
    """A run may not outlive the 10 minutes a directory must be old for `cleanup`: the cap is 540 s."""
    prompt = tmp_path / "p.txt"
    prompt.write_text("hi", encoding="utf-8")

    assert bench.MAX_TIMEOUT < bench.CLEANUP_MIN_AGE
    assert (
        bench.run_subject(
            "haiku", mcp_url, "wetterdienst", str(prompt), str(tmp_path / "o"), bench.MAX_TIMEOUT + 1, 0.1
        )
        == 2
    )
    assert bench.run_subject("haiku", mcp_url, "wetterdienst", str(prompt), str(tmp_path / "o"), 0, 0.1) == 2


def _subagent_attachment(**names: list[str]) -> dict[str, Any]:
    """Build the `deferred_tools_delta` attachment of a real subagent transcript: its keys, with names only."""
    shape = {
        "type": "deferred_tools_delta",
        "addedNames": [],
        "addedLines": [],
        "removedNames": [],
        "wireHiddenNames": [],
        "readdedNames": [],
        "surfacedNames": [],
        "surfacedDefinitions": [],
    }
    return {"type": "attachment", "attachment": {**shape, **names}}


@pytest.mark.parametrize("key", ["addedNames", "surfacedNames", "readdedNames"])
def test_the_servers_tools_are_visible_in_any_list_of_a_real_subagent_transcript(tmp_path: Path, key: str) -> None:
    """After the judge pre-loads the tools, a subject's tools are `surfaced`, not `added`: it is still a valid run."""
    names = [f"{PREFIX}{tool}" for tool in ("stations", "values", "glossary")]
    shown = bench.parse_transcript(_stream(tmp_path, _subagent_attachment(**{key: names})), PREFIX)
    hidden = bench.parse_transcript(_stream(tmp_path, _subagent_attachment(), name="h.jsonl"), PREFIX)
    other = bench.parse_transcript(
        _stream(tmp_path, _subagent_attachment(addedNames=["WebFetch", "mcp__claude_ai_Gmail__x"]), name="o.jsonl"),
        PREFIX,
    )

    assert shown["invalid"] is False
    assert hidden["invalid"] is True
    assert other["invalid"] is True


def test_a_subject_that_made_no_call_is_not_dropped_as_invalid(tmp_path: Path) -> None:
    """The failure a pass guards against (an answer with no tool call) must reach the rates, not vanish."""
    names = [f"{PREFIX}values"]
    run = bench.parse_transcript(_stream(tmp_path, _subagent_attachment(surfacedNames=names)), PREFIX)
    verdict = bench.evaluate(CASE, {**run, "answer": "From memory: 20 C."}, DEFAULTS)

    assert run["steps"] == 0
    assert run["invalid"] is False
    assert verdict["mechanical_pass"] is False


def test_the_format_violation_is_computed_from_the_answer_for_cases_that_ask_for_it() -> None:
    """A run breaks the format with no usable RESULT line or a malformed one; a case without a unit fact has none."""
    units = bench.find_case(bench.load_cases(), "units-kiel-celsius")
    glossary = bench.find_case(bench.load_cases(), "glossary-temperature-air-mean-2m")

    assert bench.format_violation(units, "It was -0.7 °C.") is True
    assert bench.format_violation(units, "RESULT: -0.7 °C | daily mean") is False
    assert bench.format_violation(units, "**RESULT:** -0.7 °C | daily mean") is False
    assert bench.format_violation(units, "RESULT: -0.7 | daily mean") is True
    assert bench.format_violation(units, "RESULT: -0.7 °C | daily mean\nRESULT: 3 | broken") is True
    assert bench.format_violation(units, "Result: it was cold.\nRESULT: -0.7 °C | daily mean") is False
    assert bench.format_violation(glossary, "mean air temperature, degrees Celsius") is None
    assert (
        bench.evaluate(units, _run([_call("values", {"stations": ["02564"]})], "It was -0.7 °C."), DEFAULTS)[
            "format_violation"
        ]
        is True
    )


def test_a_comparison_refuses_runs_that_still_need_judging() -> None:
    """An unjudged record counts as a failure and would push a side down: refuse, with the exit code."""
    before = _results({("a", "small"): 5})
    after = _results({("a", "small"): 5})
    after["runs"][0]["needs_judging"] = True

    text, refused = bench.compare_with_status(before, after)

    assert refused is True
    assert "1 runs of the current file still need judging" in text


def _add_run_file(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    """Make a headless results file of two judged runs of case `a`, and a record that would fit into it."""
    results = _results(
        {("a", "small"): 2},
        n=2,
        label="L",
        server_version="0.178.0",
        models={"small": "haiku"},
        date="2026-10-28",
    )
    for i, run in enumerate(results["runs"]):
        run["repeat"] = i + 1
    results["meta"]["prompt"] = "p1"
    path = tmp_path / "results.json"
    path.write_text(json.dumps(results), encoding="utf-8")
    run_meta = {
        "mode": "headless",
        "label": "L",
        "model_requested": "haiku",
        "wetterdienst_version": "0.178.0",
        "prompt_template": "p1",
        "prompt_date": "2026-10-28",
    }
    return path, {
        **results["runs"][1],
        "repeat": 2,
        "passed": False,
        "is_answer": True,
        "steps": 3,
        "run_meta": run_meta,
    }


def test_a_run_is_added_to_a_results_file_by_its_repeat(tmp_path: Path) -> None:
    """The replacement workflow: run the repeat like the others, judge it, add it; a valid run stays unless told."""
    path, new = _add_run_file(tmp_path)

    assert bench.add_run(path, new, replace_valid=True) == "replaced a [small] repeat 2: 2 runs"
    assert bench.add_run(path, {**new, "repeat": 3}) == "added a [small] repeat 3: 3 runs"
    runs = json.loads(path.read_text(encoding="utf-8"))["runs"]
    assert sorted((r["repeat"], r["steps"]) for r in runs) == [(1, 2), (2, 3), (3, 3)]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"needs_judging": True}, "needs judging"),
        ({"passed": "false"}, "passed is 'false', not a boolean"),
        ({"repeat": "5"}, "repeat is '5', not a positive integer"),
        ({"repeat": True}, "not a positive integer"),
        ({"invalid": "yes"}, "invalid is 'yes', not a boolean"),
        ({"case": "zzz"}, "the case 'zzz' is not in the file"),
        ({"steps": None}, "steps is None"),
        ({"run_meta": None}, "no `run_meta`"),
        ({"repeat": 2}, "would replace a valid run of a [small] repeat 2"),
        ({"repeat": 3, "run_meta": {"label": "OTHER"}}, "its label is 'OTHER', the file's is 'L'"),
        (
            {"repeat": 3, "run_meta": {"label": "L", "wetterdienst_version": "0.179.0"}},
            "wetterdienst_version is '0.179.0'",
        ),
        (
            {"repeat": 3, "run_meta": {"label": "L", "wetterdienst_version": "0.178.0", "model_requested": "sonnet"}},
            "model_requested is 'sonnet'",
        ),
        (
            {
                "repeat": 3,
                "run_meta": {
                    "label": "L",
                    "wetterdienst_version": "0.178.0",
                    "model_requested": "haiku",
                    "mode": "headless",
                    "prompt_template": "OLD",
                },
            },
            "prompt_template is 'OLD'",
        ),
        (
            {
                "repeat": 3,
                "run_meta": {
                    "label": "L",
                    "wetterdienst_version": "0.178.0",
                    "model_requested": "haiku",
                    "mode": "headless",
                    "prompt_template": "p1",
                    "prompt_date": "2026-10-29",
                },
            },
            "prompt_date is '2026-10-29', the file's is '2026-10-28'",
        ),
    ],
)
def test_add_run_refuses_a_record_that_does_not_belong_to_the_file(
    tmp_path: Path, change: dict[str, Any], message: str
) -> None:
    """A run made under other conditions, of another type, for another case or over a valid run does not go in."""
    path, new = _add_run_file(tmp_path)
    before = path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match=re.escape(message)):
        bench.add_run(path, {**new, **change})

    assert path.read_text(encoding="utf-8") == before


def test_add_run_takes_the_record_of_a_run_that_gave_no_answer_and_never_leaves_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A timeout or an unreachable server goes in with its `kind`; every refusal on the command line is exit 2."""
    path, _ = _add_run_file(tmp_path)
    case = bench.find_case(bench.load_cases(), "glossary-temperature-air-mean-2m")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["meta"]["case_hashes"][case["id"]] = "h"
    path.write_text(json.dumps(data), encoding="utf-8")
    failed = bench.failed_run(case, "small", 3, "timeout", invalid=False)
    record = tmp_path / "failed.json"
    record.write_text(json.dumps(failed), encoding="utf-8")
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")

    assert bench.main(["add-run", "--results", str(path), "--run", str(record)]) == 0
    assert bench.main(["add-run", "--results", str(tmp_path / "nope.json"), "--run", str(record)]) == 2
    assert bench.main(["add-run", "--results", str(path), "--run", str(tmp_path / "nope.json")]) == 2
    assert bench.main(["add-run", "--results", str(path), "--run", str(bad)]) == 2
    assert "add-run:" in capsys.readouterr().err
    assert failed["kind"] == "failed"


def test_the_prompts_example_is_no_cases_answer() -> None:
    """A model that copies the prompt's example must not pass a unit check: it is made up, and no case expects it."""
    prompt = (SKILL_DIR / "prompt.md").read_text(encoding="utf-8")
    example = re.search(r"`RESULT: (?P<line>(?P<figure>[-\d.]+) (?P<unit>\S+) \| (?P<what>[^`]+))`", prompt)
    assert example is not None
    data = bench.load_cases()
    text = json.dumps(data, ensure_ascii=False)
    truths = {"units-lax-forecast-celsius": {"min": 14.0, "max": 24.0}}

    assert not re.search(rf"(?<![\d.]){re.escape(example['figure'])}(?!\d)", text), (
        "the example's figure is a number of a case"
    )
    for word in re.findall(r"[A-Z][a-z]{3,}|\d{4}-\d{2}-\d{2}", example["what"]):
        assert word not in text, f"{word} of the example is in a case"
    for case in (c for c in data["cases"] if c["kind"] == "units"):
        fact = next(f for f in case["facts"] if f["kind"] == "unit")
        value = next((r[1] for r in RESULT_ANSWERS if r[0] == case["id"]), {"value": 0})
        assert bench.unit_check(f"RESULT: {example['line']}", fact, truths.get(case["id"], value))["ok"] is False, case[
            "id"
        ]


def test_the_format_rate_is_over_the_cases_that_ask_for_it_and_says_when_it_is_not_compared() -> None:
    """Denominators are the runs of the cases with a unit fact, not all runs; a side with none is named, not skipped."""
    before = _results({("u", "small"): 5, ("g", "small"): 5})
    after = _results({("u", "small"): 5, ("g", "small"): 5})
    for results in (before, after):
        for run in results["runs"]:
            run["format_violation"] = False if run["case"] == "u" else None
    without = _results({("u", "small"): 5, ("g", "small"): 5})

    both = bench.compare(before, after)
    one = bench.compare(before, without)

    assert "follows the RESULT format 5/5 -> 5/5" in both
    assert "format rate not compared: the current file has no run of a case that asks for the format" in one


def test_the_step_maximum_is_none_for_runs_that_measured_no_step_and_the_sizes_use_paired_runs() -> None:
    """A timed-out run without a transcript has no steps: the maximum is not 0. Sizes come from paired repeats."""
    case = bench.find_case(bench.load_cases(), "glossary-temperature-air-mean-2m")
    nothing = bench.failed_run(case, "small", 1, "timeout", invalid=False)
    one = {**nothing, "steps": 3}

    assert bench.aggregate([nothing])["steps_max"] is None
    assert bench.aggregate([nothing, one])["steps_max"] == 3
    before = _numbered(_results({("a", "small"): 35}, n=35))
    after = _numbered(
        _results({("a", "small"): 34}, n=34)
    )  # repeat 35 is missing on this side, so it is left out of both

    text = bench.compare(before, after)

    assert "tool result chars: median per case 2650 -> 2650, paired difference (median over 1 cases) +0" in text


def test_the_default_full_run_is_the_cases_that_need_no_key() -> None:
    """The skill and the docs state how many cases and runs a default full run is; the number is the file's."""
    cases = bench.load_cases()["cases"]
    n = sum(1 for c in cases if not c["needs_key"])
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    docs = (Path(__file__).parents[2] / "docs" / "contribution" / "mcp-benchmark.md").read_text(encoding="utf-8")
    phrase = f"{n} cases, {5 * n} runs a side per tier at 5 repeats, {10 * n} in all"

    assert n < len(cases)
    assert phrase in skill
    assert phrase in docs


# ------------------------------------------------------------------------------- round 7: what the strict check holds

KIEL, FAHRENHEIT, HUMIDITY, SUNSHINE = (
    "units-kiel-celsius",
    "units-fahrenheit",
    "units-humidity-percent",
    "units-sunshine-seconds",
)
WIND, PRECIP, CSV, LAX = (
    "units-wind-speed",
    "units-precipitation-mm",
    "units-csv-with-unit",
    "units-lax-forecast-celsius",
)
TRUTHS = {
    KIEL: {"value": -0.7},
    FAHRENHEIT: {"value": -0.7},
    HUMIDITY: {"value": 0.8404},
    SUNSHINE: {"value": 14821.2},
    WIND: {"value": 3.0},
    PRECIP: {"value": 15.5},
    CSV: {"value": 15.5},
    LAX: {"min": 17.1, "max": 21.8},
}
CSV5 = (
    "```csv\ndate,precipitation_amount\n2026-10-14,0.0\n2026-10-15,1.6\n2026-10-16,15.5\n2026-10-17,0.2\n2026-10-18,0.0\n```\n"
    "The column is in mm.\n"
)
PER_DATE = "\n".join(
    f"RESULT: {v} mm | precipitation on 2026-10-{d}"
    for d, v in [(14, "0.0"), (15, "1.6"), (16, "15.5"), (17, "0.2"), (18, "0.0")]
)
PER_DATE_BARE = "\n".join(
    f"RESULT: {v} mm | 2026-10-{d}" for d, v in [(14, "0.0"), (15, "1.6"), (16, "15.5"), (17, "0.2"), (18, "0.0")]
)


def _csv(header: str, *rows: str) -> str:
    """Make a fenced CSV block of a header and rows."""
    return "```csv\n" + "\n".join([header, *rows]) + "\n```\n"


#: (label, case, whether the answer passes, the answer): answers a model could give once the prompt asks for a RESULT
#: line only for the figure asked. Another figure with a RESULT line is the model's own addition, no failure by its
#: wording; a line that clearly gives a wrong value for the asked quantity still fails the answer.
ADVERSARIAL_ANSWERS = [
    ("a01 K mean + 'daily max'", KIEL, True, "RESULT: -0.7 °C | daily mean\nRESULT: 1.2 °C | daily max"),
    ("a02 K mean + 'Tmin'", KIEL, True, "RESULT: -0.7 °C | daily mean (TMK)\nRESULT: -3.1 °C | Tmin"),
    ("a03 K mean + high/low", KIEL, True, "RESULT: -0.7 °C | daily mean\nRESULT: 1.2 °C | high\nRESULT: -3.1 °C | low"),
    (
        "a04 K mean + 'yesterday'",
        KIEL,
        True,
        "RESULT: -0.7 °C | daily mean on 26 Dec\nRESULT: 0.4 °C | daily mean the day earlier (25 Dec)",
    ),
    (
        "a05 K mean + other date",
        KIEL,
        True,
        "RESULT: -0.7 °C | daily mean on 2025-12-26\nRESULT: 0.4 °C | daily mean on 2025-12-25",
    ),
    (
        "a06 K mean + dew point",
        KIEL,
        True,
        "RESULT: -0.7 °C | daily mean air temperature\nRESULT: -2.4 °C | daily mean dew point",
    ),
    (
        "a07 K mean + climate normal",
        KIEL,
        True,
        "RESULT: -0.7 °C | daily mean\nRESULT: 2.1 °C | December normal 1991-2020",
    ),
    (
        "a08 K wrong only, desc has 'minimum'",
        KIEL,
        False,
        "RESULT: 0.4 °C | daily mean (average of minimum and maximum)",
    ),
    (
        "a09 K hedge wrong labelled 'previous estimate' + right",
        KIEL,
        False,
        "RESULT: 3.2 °C | daily mean (previous estimate)\nRESULT: -0.7 °C | daily mean",
    ),
    (
        "a10 K '5 days | window' context line",
        KIEL,
        True,
        "RESULT: -0.7 °C | daily mean\nRESULT: 5 days | window queried",
    ),
    ("a11 K '1 station | count'", KIEL, True, "RESULT: -0.7 °C | daily mean\nRESULT: 1 station | stations used"),
    ("a12 F + '31 days' context", FAHRENHEIT, True, "RESULT: 30.7 °F | daily mean\nRESULT: 31 days | December"),
    ("a13 F mean + 'daily max' in F", FAHRENHEIT, True, "RESULT: 30.7 °F | daily mean\nRESULT: 34.2 °F | daily max"),
    (
        "a14 F mean + mean in C rounded",
        FAHRENHEIT,
        True,
        "RESULT: 30.7 °F | daily mean\nRESULT: -0.7 °C | daily mean (source unit)",
    ),
    ("a15 H mean + 'max' in %", HUMIDITY, True, "RESULT: 84 % | daily mean relative humidity\nRESULT: 97 % | max"),
    ("a16 H % and bare fraction (malformed)", HUMIDITY, True, "RESULT: 84 % | mean\nRESULT: 0.84 | as a fraction"),
    (
        "a17 H mean + temperature line",
        HUMIDITY,
        True,
        "RESULT: 84 % | mean relative humidity\nRESULT: 9.8 °C | mean air temperature",
    ),
    ("a18 W mean + 'peak'", WIND, True, "RESULT: 3.0 m/s | daily mean\nRESULT: 7.5 m/s | peak wind"),
    (
        "a19 W mean + '11 km' distance",
        WIND,
        True,
        "RESULT: 3.0 m/s | daily mean wind speed\nRESULT: 11 km | distance from the city centre",
    ),
    ("a20 W mean + 'Tagesmaximum'", WIND, True, "RESULT: 3.0 m/s | Tagesmittel\nRESULT: 6.1 m/s | Tagesmaximum"),
    (
        "a21 S + day length",
        SUNSHINE,
        True,
        "RESULT: 4.1 h | sunshine duration\nRESULT: 10.6 h | day length (astronomically possible)",
    ),
    (
        "a22 S + % of possible",
        SUNSHINE,
        True,
        "RESULT: 4.1 h | sunshine duration\nRESULT: 39 % | of the possible sunshine",
    ),
    ("a23 S + 'monthly total'", SUNSHINE, True, "RESULT: 4.1 h | sunshine on 16 Oct\nRESULT: 61.2 h | month so far"),
    ("a24 P + other date", PRECIP, True, "RESULT: 15.5 mm | precipitation on 16 Oct\nRESULT: 0.4 mm | on 15 October"),
    (
        "a25 P + weekly total",
        PRECIP,
        True,
        "RESULT: 15.5 mm | precipitation on 16 Oct\nRESULT: 17.3 mm | total 14-18 October",
    ),
    (
        "a26 P + mm/h intensity",
        PRECIP,
        True,
        "RESULT: 15.5 mm | daily precipitation\nRESULT: 4.2 mm | highest hourly amount",
    ),
    (
        "a27 CSV + per-date RESULT lines",
        CSV,
        True,
        CSV5 + "TABLE-UNIT: precipitation_amount | mm\n" + PER_DATE,
    ),
    (
        "a28 CSV + total RESULT",
        CSV,
        True,
        CSV5 + "TABLE-UNIT: precipitation_amount | mm\nRESULT: 17.3 mm | total precipitation 14-18 October",
    ),
    (
        "a29 CSV + max-day RESULT",
        CSV,
        True,
        CSV5 + "TABLE-UNIT: precipitation_amount | mm\nRESULT: 15.5 mm | wettest day (2026-10-16)",
    ),
    (
        "a30 CSV per-date RESULT only (no TABLE-UNIT)",
        CSV,
        True,
        CSV5 + PER_DATE_BARE,
    ),
    (
        "a31 CSV wrong row but RESULT for 16th right",
        CSV,
        False,
        _csv("date,precipitation_amount", "2026-10-15,15.5", "2026-10-16,1.6")
        + "TABLE-UNIT: precipitation_amount | mm\nRESULT: 15.5 mm | precipitation on 2026-10-16",
    ),
    ("a32 LAX + overnight low", LAX, True, "RESULT: 21 °C | tomorrow afternoon\nRESULT: 14 °C | overnight low"),
    ("a33 LAX + day-after", LAX, True, "RESULT: 21 °C | tomorrow afternoon\nRESULT: 26 °C | Friday afternoon"),
    (
        "a34 K mean + F restatement",
        KIEL,
        True,
        "RESULT: -0.7 °C | daily mean\nRESULT: 30.7 °F | the same in Fahrenheit",
    ),
    (
        "a35 K wrong mean + highest-quality remark + right min??",
        KIEL,
        False,
        "RESULT: -3.1 °C | daily minimum\nRESULT: 2.0 °C | daily mean",
    ),
    ("a36 K 'min.' abbreviation", KIEL, True, "RESULT: -0.7 °C | mean\nRESULT: -3.1 °C | min."),
    ("a37 K 'Minimum' German", KIEL, True, "RESULT: -0.7 °C | Tagesmittel\nRESULT: -3.1 °C | Tagesminimum"),
    (
        "a38 K '20 °C' lines: no; elevation 27 m",
        KIEL,
        True,
        "RESULT: -0.7 °C | daily mean\nRESULT: 27 m | station elevation",
    ),
    # a wrong figure for the asked quantity next to a right one labelled as another quantity (a hedge, not context)
    (
        "s1 days swapped, the right figure labelled day before",
        PRECIP,
        False,
        "RESULT: 1.6 mm | precipitation on 2026-10-16\nRESULT: 15.5 mm | the day before (2026-10-15)",
    ),
    (
        "s2 days swapped, the right figure labelled previous day",
        KIEL,
        False,
        "RESULT: 0.4 °C | daily mean on 2025-12-26\nRESULT: -0.7 °C | daily mean on the previous day",
    ),
    (
        "s3 max read as mean, the right figure labelled minimum",
        KIEL,
        False,
        "RESULT: 1.2 °C | daily mean\nRESULT: -0.7 °C | daily minimum",
    ),
    (
        "s4 wrong mean (highest hourly), the right figure labelled gust",
        WIND,
        False,
        "RESULT: 5.2 m/s | daily mean wind speed (highest hourly)\nRESULT: 3.0 m/s | gust",
    ),
    (
        "s5 wrong station, the right figure labelled another station",
        HUMIDITY,
        False,
        "RESULT: 77 % | mean relative humidity at Hamburg-Fuhlsb\u00fcttel\nRESULT: 84 % | another station nearby",
    ),
    # the table is held to the value in the column and the row whenever one is given
    (
        "c1 shifted table, a RESULT for the 16th, no TABLE-UNIT",
        CSV,
        False,
        _csv("date,precipitation_amount", "2026-10-14,0.0", "2026-10-15,15.5", "2026-10-16,1.6", "2026-10-17,0.2")
        + "RESULT: 15.5 mm | precipitation on 2026-10-16",
    ),
    (
        "c2 shifted table with a precip column, TABLE-UNIT and RESULT",
        CSV,
        False,
        _csv("date,precip", "2026-10-14,0.0", "2026-10-15,15.5", "2026-10-16,1.6", "2026-10-17,0.2")
        + "TABLE-UNIT: precip | mm\nRESULT: 15.5 mm | precipitation on 2026-10-16",
    ),
    (
        "c3 shifted table with a precip column, TABLE-UNIT only",
        CSV,
        False,
        _csv("date,precip", "2026-10-14,0.0", "2026-10-15,15.5", "2026-10-16,1.6", "2026-10-17,0.2")
        + "TABLE-UNIT: precip | mm",
    ),
    (
        "c6 right table with a precip column and TABLE-UNIT precip",
        CSV,
        True,
        _csv("date,precip", "2026-10-14,0.0", "2026-10-15,1.6", "2026-10-16,15.5", "2026-10-17,0.2")
        + "TABLE-UNIT: precip | mm",
    ),
    (
        "c7 right table with a dotted date and a precip column, RESULT only",
        CSV,
        True,
        "date,precip\n15.10.2026,1.6\n16.10.2026,15.5\nRESULT: 15.5 mm | precipitation on 16.10.2026",
    ),
    (
        "c8 shifted table with a dotted date, RESULT only",
        CSV,
        False,
        "date,precip\n15.10.2026,15.5\n16.10.2026,1.6\nRESULT: 15.5 mm | precipitation on 16.10.2026",
    ),
    (
        "c9 a table that is right in the wrong column, RESULT right",
        CSV,
        False,
        "date,temperature,precipitation\n2026-10-16,15.5,1.6\nRESULT: 15.5 mm | precipitation on 2026-10-16",
    ),
]


@pytest.mark.parametrize(
    ("label", "case_id", "expected", "answer"),
    [pytest.param(*row, id=row[0].split()[0]) for row in ADVERSARIAL_ANSWERS],
)
def test_an_extra_result_line_fails_nothing_by_its_wording_but_a_wrong_asked_figure_does(
    label: str,
    case_id: str,
    expected: bool,  # noqa: FBT001
    answer: str,
) -> None:
    """The prompt asks for a RESULT line only for the asked figure, so another line is context, not a failure."""
    result = bench.unit_check(answer, _unit_fact(case_id), TRUTHS[case_id])

    assert result["ok"] is expected, (label, result["failures"])


@pytest.mark.parametrize(
    ("case_id", "description", "asked"),
    [
        # the asked quantity: the fact's words, whatever else the line says
        (KIEL, "daily mean", True),
        (KIEL, "Mean air temperature at Kiel-Holtenau", True),
        (KIEL, "Tagesmittel", True),
        (KIEL, "daily mean on 26 Dec", True),
        (KIEL, "daily mean on 2025-12-26", True),
        (KIEL, "daily mean (previous estimate)", True),
        (KIEL, "temperature", True),
        # another quantity, day or station: named by the ignore list, or not the asked words at all
        (KIEL, "daily minimum", False),
        (KIEL, "Tmin", False),
        (KIEL, "min.", False),
        (KIEL, "daily max", False),
        (KIEL, "high", False),
        (KIEL, "daily mean dew point", False),
        (KIEL, "December normal 1991-2020", False),
        (KIEL, "daily mean the day earlier (25 Dec)", False),
        (KIEL, "daily mean on 2025-12-25", False),
        (KIEL, "daily mean on the previous day", False),
        (KIEL, "daily mean at another station", False),
        (KIEL, "elevation of the station", False),
        (KIEL, "value", False),
        (PRECIP, "precipitation on 2026-10-16", True),
        (PRECIP, "daily precipitation", True),
        (PRECIP, "Niederschlag", True),
        (PRECIP, "precipitation on 15 October", False),
        (PRECIP, "precipitation on 2026-10-15", False),
        (PRECIP, "highest hourly amount", False),
        (PRECIP, "total precipitation 14-18 October", False),
        (PRECIP, "precipitation the day before", False),
        (HUMIDITY, "mean relative humidity", True),
        (HUMIDITY, "Luftfeuchte", True),
        (HUMIDITY, "mean air temperature", False),
        (HUMIDITY, "humidity maximum", False),
        (HUMIDITY, "dew point", False),
        (SUNSHINE, "sunshine duration", True),
        (SUNSHINE, "Sonnenscheindauer", True),
        (SUNSHINE, "day length (astronomically possible)", False),
        (SUNSHINE, "sunshine, month so far", False),
        (SUNSHINE, "share of the possible sunshine", False),
        (WIND, "daily mean wind speed (highest hourly)", True),
        (WIND, "Tagesmittel", True),
        (WIND, "peak wind", False),
        (WIND, "wind gust", False),
        (WIND, "Tagesmaximum", False),
        (CSV, "precipitation on 2026-10-16", True),
        (CSV, "precipitation on 16 Oct", True),
        (CSV, "precipitation on 16.10.2026", True),
        (CSV, "precipitation on 2026-10-15", False),
        (CSV, "total precipitation 14-18 October", False),
        # a forecast has no asked words: every line is a claim unless it names another time or a minimum
        (LAX, "tomorrow afternoon", True),
        (LAX, "15:00", True),
        (LAX, "forecast air temperature", True),
        (LAX, "overnight low", False),
        (LAX, "Friday afternoon", False),
        (LAX, "daily maximum", False),
    ],
)
def test_the_descriptions_that_make_a_line_a_claim_about_the_asked_quantity(
    case_id: str,
    description: str,
    asked: bool,  # noqa: FBT001
) -> None:
    """Both lists of a fact, tried both ways: what a line is called decides whether a wrong figure on it fails."""
    assert bench._is_asked(description.casefold(), _unit_fact(case_id)) is asked  # noqa: SLF001


def test_an_answer_whose_only_lines_are_exempt_has_a_reason_to_fail() -> None:
    """No right figure and no failing line is still a failure, and the verdict says why."""
    fact = _unit_fact(KIEL)

    exempt = bench.unit_check("RESULT: 1.2 °C | daily max\nRESULT: -3.1 °C | daily minimum", fact, TRUTHS[KIEL])
    unknown = bench.unit_check("RESULT: 5 days | window", fact, TRUTHS[KIEL])
    fallback = bench.unit_check("It was cold.", fact, TRUTHS[KIEL])

    for verdict in (exempt, unknown, fallback):
        assert verdict["ok"] is False
        assert [f["reason"] for f in verdict["failures"]] == [
            "no figure of the answer is the value in one of the accepted units"
        ]


def test_a_unit_the_case_does_not_know_is_no_failure_and_no_pass() -> None:
    """`5 days`, `11 km` and `0.7 degrees` are not the value and not wrong: they neither fail nor pass an answer."""
    fact = _unit_fact(KIEL)
    wind = _unit_fact(WIND)

    assert bench.unit_check("RESULT: -0.7 °C | daily mean\nRESULT: 5 days | window", fact, TRUTHS[KIEL])["ok"] is True
    assert (
        bench.unit_check("RESULT: -0.7 °C | daily mean\nRESULT: -0.7 degrees | daily mean", fact, TRUTHS[KIEL])["ok"]
        is True
    )
    assert bench.unit_check("RESULT: 3.0 m/s | wind\nRESULT: 11 km | distance", wind, TRUTHS[WIND])["ok"] is True
    assert bench.unit_check("RESULT: -0.7 degrees | daily mean", fact, TRUTHS[KIEL])["ok"] is False
    assert bench.unit_check("RESULT: 11 km | distance", wind, TRUTHS[WIND])["ok"] is False


def test_the_value_in_the_unit_it_was_read_in_but_written_with_another_unit_fails_whatever_it_is_called() -> None:
    """`0.84 %` for 84 % and `15.5 cm` for 15.5 mm are the unit error the units cases are for: nothing excuses them."""
    humidity, rain = _unit_fact(HUMIDITY), _unit_fact(PRECIP)

    assert (
        bench.unit_check("RESULT: 84 % | mean\nRESULT: 0.84 % | as returned", humidity, TRUTHS[HUMIDITY])["ok"] is False
    )
    assert (
        bench.unit_check("RESULT: 15.5 mm | precipitation\nRESULT: 15.5 cm | the day before", rain, TRUTHS[PRECIP])[
            "ok"
        ]
        is False
    )
    assert (
        bench.unit_check("RESULT: 15.5 mm | precipitation\nRESULT: 1.6 mm | the day before", rain, TRUTHS[PRECIP])["ok"]
        is True
    )


@pytest.mark.parametrize(
    ("cell", "found"),
    [
        ("2026-10-16", True),
        ("16.10.2026", True),
        ("16. 10. 2026", True),
        ("16.10.26", True),
        ("16.10.", False),
        ("16/10/2026", True),
        ("10/16/2026", True),
        ("16 Oct 2026", True),
        ("16 October 2026", True),
        ("Oct 16, 2026", True),
        ("October 16th, 2026", True),
        ("2026-10-15", False),
        ("15.10.2026", False),
        ("116.10.2026", False),
        ("2026-10-160", False),
    ],
)
def test_the_row_of_a_table_is_found_in_the_forms_a_date_is_written(cell: str, found: bool) -> None:  # noqa: FBT001
    """The CSV case's row is a day; a table may write it as the tool does or as a person does."""
    assert bench._row_has_day(["x", cell], {"row": "2026-10-16"}) is found  # noqa: SLF001


def test_the_prompt_asks_for_a_result_line_only_for_the_figures_the_question_asks_for() -> None:
    """No line for a minimum, a day before, a count or a distance, and one per forecast temperature."""
    prompt = (SKILL_DIR / "prompt.md").read_text(encoding="utf-8")

    assert "one line for each figure the question asks for" in prompt
    assert "Write no RESULT line for any other figure you mention" in prompt
    assert "one for each forecast temperature you name" in prompt
    assert "one line for each figure you give" not in prompt


# ------------------------------------------------------------------- round 7: missing repeats, pairing, the 60 % rule


def _file(
    cases: int = 27,
    repeats: int = 5,
    *,
    gone: set[tuple[str, int]] | None = None,
    bad: set[tuple[str, int]] | None = None,
    fail: set[tuple[str, int]] | None = None,
    first: int = 1,
    **meta: Any,  # noqa: ANN401
) -> dict[str, Any]:
    """Make a results file of `cases` cases with `repeats` numbered repeats, each passing unless it is in `fail`.

    `gone` repeats have no record, `bad` ones are invalid runs; `first` is the number the first repeat gets.
    """
    names = [f"c{i}" for i in range(cases)]
    results = _results(dict.fromkeys(((c, "small") for c in names), repeats), n=repeats, repeats=repeats, **meta)
    runs = []
    seen: dict[str, int] = {}
    for run in results["runs"]:
        position = seen[run["case"]] = seen.get(run["case"], -1) + 1
        run["repeat"] = first + position
        key = (run["case"], run["repeat"])
        if key in (gone or set()):
            continue
        run["invalid"] = key in (bad or set())
        run["passed"] = run["facts_ok"] = key not in (fail or set())
        runs.append(run)
    results["runs"] = runs
    return results


@pytest.mark.parametrize(
    ("gone", "share"),
    [
        ({(f"c{i}", 5) for i in range(27)}, "20%"),
        ({(f"c{i}", n) for i in range(27) for n in (4, 5)}, "40%"),
    ],
)
def test_a_repeat_that_has_no_record_counts_as_missing_and_is_refused_beyond_three_percent(
    gone: set[tuple[str, int]], share: str
) -> None:
    """A timeout nobody recorded must not shrink a side unseen: the file says `repeats`, the records are counted."""
    text, refused = bench.compare_with_status(_file(), _file(gone=gone))

    assert refused
    assert f"{share} of the 135 compared current runs are" in text
    assert "missing (no record of the repeat)" in text
    assert "=> NO WORSE" not in text


def test_a_few_missing_repeats_are_pooled_without_them_and_say_so() -> None:
    """Three runs of 135 missing (2 %) are under the limit: the pairs that remain are compared, and counted."""
    text, refused = bench.compare_with_status(_file(), _file(gone={("c0", 5), ("c1", 5), ("c2", 5)}))

    assert not refused
    assert "POOLED small (132 runs on each side" in text
    assert "3 valid runs were left out" in text


@pytest.mark.parametrize(
    ("current", "message"),
    [
        (_file(first=0), "c0 [small] with repeat [0], outside 1..5"),
        (_file(first=2), "c0 [small] with repeat [6], outside 1..5"),
        (_file(repeats=10), "different repeats (5 -> 10)"),
    ],
)
def test_a_repeat_outside_the_file_or_a_different_design_is_refused(current: dict[str, Any], message: str) -> None:
    """Repeats are numbered 1..`repeats`; two files made with another number of them are not compared."""
    text, refused = bench.compare_with_status(_file(), current)

    assert refused
    assert message in text


def test_a_repeat_given_twice_is_refused() -> None:
    """Five records of repeat 1 are not five repeats."""
    current = _file()
    for run in current["runs"]:
        run["repeat"] = 1

    text, refused = bench.compare_with_status(_file(), current)

    assert refused
    assert "c0 [small] with repeat [1] more than once" in text


def test_a_long_list_of_bad_repeats_is_cut_to_a_few_lines() -> None:
    """27 cases with a repeat 0 are three lines and a count, not 27 lines."""
    text, refused = bench.compare_with_status(_file(), _file(first=0))

    assert refused
    assert "the current file has 24 more cases with a repeat outside 1..5 or given twice" in text
    assert len(text.splitlines()) < 8


def test_the_runs_are_paired_by_the_repeat_they_carry_not_by_their_place_in_the_file() -> None:
    """A file lists repeats out of order, or without a gap-filling one: repeat 3 meets repeat 3."""
    before = _file(cases=1, bad={("c0", 2)})
    after = _file(cases=1)
    after["runs"] = [r for r in after["runs"] if r["repeat"] != 4]
    after["runs"].reverse()
    keys = [("c0", "small")]

    prev_eq, cur_eq, dropped, thin = bench._equalise(bench.groups(before), bench.groups(after), keys, 5)  # noqa: SLF001

    assert [r["repeat"] for r in prev_eq[keys[0]]] == [1, 3, 5]
    assert [r["repeat"] for r in cur_eq[keys[0]]] == [1, 3, 5]
    assert dropped == 2  # 4 valid runs before, 4 after, 3 shared: 4 + 4 - 2 * 3
    assert thin == {}


def test_the_pairing_is_by_repeat_in_the_verdict_too() -> None:
    """A repeat that fails on both sides but at different places in the file is one pair, not two."""
    before = _file(cases=40, fail={("c0", 1)})
    after = _file(cases=40, fail={("c0", 1)}, gone={("c1", 1)})
    after["runs"].reverse()

    text, refused = bench.compare_with_status(before, after)

    assert not refused
    assert "difference +0.0%" in text


@pytest.mark.parametrize(
    ("kept", "thin"),
    [
        (4, True),  # 40 %
        (5, True),  # 50 %: under 60 %, which a threshold of 50 % would let through
        (6, False),  # exactly 60 %
        (7, False),
    ],
)
def test_a_case_that_keeps_under_sixty_percent_of_its_repeats_makes_the_tier_inconclusive(
    kept: int,
    thin: bool,  # noqa: FBT001
) -> None:
    """The boundary of the 60 % rule at ten repeats, with the invalid repeats on both sides."""
    bad = {("c0", n) for n in range(kept + 1, 11)}
    before, after = _file(cases=40, repeats=10, bad=bad), _file(cases=40, repeats=10, bad=bad)

    text, refused = bench.compare_with_status(before, after)

    assert not refused, text
    assert ("INCONCLUSIVE, the repeats that are valid on both sides leave fewer than 60 %" in text) is thin
    assert (f"c0 ({kept} of 10: previous {kept} valid, current {kept} valid)" in text) is thin


def test_the_sixty_percent_message_names_which_side_lacks_the_repeats() -> None:
    """Invalid runs on one side, missing ones on the other: the message gives the valid runs of each."""
    before = _file(cases=40, bad={("c0", 1), ("c0", 2)})
    after = _file(cases=40, gone={("c0", 3), ("c0", 4)})

    text, refused = bench.compare_with_status(before, after)

    assert not refused, text
    assert "c0 (1 of 5: previous 3 valid, current 3 valid)" in text
    assert "a run that is invalid or missing on one side takes its repeat out of the other, " in text
    assert "and what is left would say little\n" in text


def test_the_power_line_counts_the_smaller_side() -> None:
    """The runs there are for the smallest rate are those of the side that has fewer, not always the previous one."""
    before, after = _file(), _file()
    for run in before["runs"]:
        run["format_violation"] = False
    for run in after["runs"]:
        run["format_violation"] = False if run["repeat"] <= 2 else None

    text = bench.compare(before, after)

    assert "there are 54 for the smallest rate" in text


def test_the_comparison_docstring_describes_the_pairing() -> None:
    """The docstring said the first k valid runs of each side were kept; the code pairs by repeat."""
    doc = " ".join((bench.compare_with_status.__doc__ or "").split())

    assert "first k" not in doc
    assert "paired by repeat" in doc


# ---------------------------------------------------------------------------------------- round 7: add-run


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"repeat": 6}, "repeat is 6, but the file was made with repeats=5"),
        ({"repeat": 0}, "not a positive integer"),
        ({"checkpoints": "1/1"}, "checkpoints is '1/1'"),
        ({"checkpoints": {"k": "1", "n": 2}}, "checkpoints is"),
        ({"checkpoints": {"k": 3, "n": 2}}, "k at most n"),
        ({"checkpoints": {"k": True, "n": 2}}, "checkpoints is"),
        ({"violations": "none"}, "violations is 'none', not a list"),
        ({"violations": 0}, "violations is 0, not a list"),
        ({"model": None}, "model is None"),
        ({"model": ""}, "model is ''"),
        ({"steps": "3"}, "steps is '3'"),
    ],
)
def test_add_run_checks_the_types_of_what_aggregate_reads(tmp_path: Path, change: dict[str, Any], message: str) -> None:
    """`aggregate` sums `checkpoints` and counts `violations`; another shape would break the report later."""
    path, new = _add_run_file(tmp_path)
    path.write_text(
        json.dumps(
            {
                **json.loads(path.read_text(encoding="utf-8")),
                "meta": {**json.loads(path.read_text(encoding="utf-8"))["meta"], "repeats": 5},
            }
        ),
        encoding="utf-8",
    )
    new = {**new, "repeat": 3, "model": "claude-haiku-5-5", "violations": [], "checkpoints": {"k": 1, "n": 2}}

    with pytest.raises(ValueError, match=re.escape(message)):
        bench.add_run(path, {**new, **change})


@pytest.mark.parametrize(
    "change",
    [
        {"passed": True},
        {"facts_ok": True},
        {"is_answer": True},
        {"invalid": False, "kind": "invalid"},
        {"invalid": True, "kind": "failed"},
    ],
)
def test_a_record_cannot_declare_a_failed_kind_and_claim_an_answer(tmp_path: Path, change: dict[str, Any]) -> None:
    """`kind: failed` skips the steps and `run_meta` checks, which is only right for what `failed-run` writes."""
    path, _ = _add_run_file(tmp_path)
    case = bench.find_case(bench.load_cases(), "glossary-temperature-air-mean-2m")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["meta"]["case_hashes"][case["id"]] = "h"
    path.write_text(json.dumps(data), encoding="utf-8")
    honest = bench.failed_run(case, "small", 3, "timeout", invalid=False)

    assert bench.add_run(path, honest) == f"added {case['id']} [small] repeat 3: 3 runs"
    with pytest.raises(ValueError, match="declares kind"):
        bench.add_run(path, {**honest, "repeat": 4, **change})


def test_add_run_writes_a_whole_file_or_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A write that fails half way leaves the old file and no temporary file next to it."""
    path, new = _add_run_file(tmp_path)
    before = path.read_text(encoding="utf-8")

    def boom(_descriptor: int) -> None:
        msg = "disk full"
        raise OSError(msg)

    monkeypatch.setattr(bench.os, "fsync", boom)
    with pytest.raises(OSError, match="disk full"):
        bench.add_run(path, {**new, "repeat": 3})

    assert path.read_text(encoding="utf-8") == before
    assert sorted(p.name for p in tmp_path.iterdir()) == (
        ["results.json"] if bench.fcntl is None else ["results.json", "results.json.lock"]
    )


@pytest.mark.skipif(bench.fcntl is None, reason="add-run takes no lock where there is no fcntl (Windows)")
def test_concurrent_add_runs_keep_every_record(tmp_path: Path) -> None:
    """Twelve processes fill twelve repeats of a big results file at once; none may lose another's record."""
    names = [f"c{i}" for i in range(12)]
    results = _file(
        cases=12,
        bad={(c, n) for c in names for n in range(1, 6)},
        label="L",
        server_version="0.178.0",
        models={"small": "haiku"},
        date="2026-10-28",
    )
    run_meta = {
        "mode": "headless",
        "label": "L",
        "model_requested": "haiku",
        "wetterdienst_version": "0.178.0",
        "prompt_template": "p1",
        "prompt_date": "2026-10-28",
    }
    results["meta"]["prompt"] = "p1"
    for run in results["runs"]:
        run["calls"] = [{"tool": "values", "args": {"x": "y" * 200}} for _ in range(40)]
    path = tmp_path / "results.json"
    path.write_text(json.dumps(results), encoding="utf-8")
    processes = []
    for name in names:
        record = {**next(r for r in results["runs"] if r["case"] == name and r["repeat"] == 3)}
        record.update(
            {"invalid": False, "passed": True, "facts_ok": True, "is_answer": True, "steps": 2, "run_meta": run_meta}
        )
        record_path = tmp_path / f"{name}.json"
        record_path.write_text(json.dumps(record), encoding="utf-8")
        processes.append(
            subprocess.Popen(  # noqa: S603
                [
                    sys.executable,
                    "-I",
                    str(SKILL_DIR / "scripts" / "bench.py"),
                    "add-run",
                    "--results",
                    str(path),
                    "--run",
                    str(record_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        )
    codes = [process.wait() for process in processes]

    runs = json.loads(path.read_text(encoding="utf-8"))["runs"]
    assert codes == [0] * 12, [p.stderr.read() for p in processes if p.returncode]
    assert len(runs) == 60
    assert sum(1 for r in runs if r["repeat"] == 3 and not r["invalid"]) == 12


def test_add_run_waits_for_the_lock_on_the_results_file(tmp_path: Path) -> None:
    """While another process holds `<file>.lock`, `add-run` does not read or write the file."""
    fcntl = pytest.importorskip("fcntl")
    path, new = _add_run_file(tmp_path)
    record = tmp_path / "new.json"
    record.write_text(json.dumps({**new, "repeat": 3}), encoding="utf-8")
    command = [
        sys.executable,
        "-I",
        str(SKILL_DIR / "scripts" / "bench.py"),
        "add-run",
        "--results",
        str(path),
        "--run",
        str(record),
    ]

    with Path(f"{path}.lock").open("a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
        try:
            with pytest.raises(subprocess.TimeoutExpired):
                process.wait(timeout=1.0)
            assert len(json.loads(path.read_text(encoding="utf-8"))["runs"]) == 2
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    assert process.wait(timeout=30) == 0
    assert len(json.loads(path.read_text(encoding="utf-8"))["runs"]) == 3


def test_a_repeat_number_that_is_no_number_falls_back_to_the_place_in_the_file() -> None:
    """A record without a usable `repeat` is numbered by its place; a boolean is not a number."""
    assert bench._repeat_of({"repeat": 3}, 0) == 3  # noqa: SLF001
    assert bench._repeat_of({}, 3) == 4  # noqa: SLF001
    assert bench._repeat_of({"repeat": True}, 3) == 4  # noqa: SLF001
    assert bench._repeat_of({"repeat": "2"}, 3) == 4  # noqa: SLF001


def test_a_forecast_figure_outside_the_span_says_so_and_a_shifted_table_is_reported_once() -> None:
    """The reasons of the verdict: a claim outside the span, and one table failure, not one per line of the answer."""
    forecast = bench.unit_check("RESULT: 45 °C | tomorrow afternoon", _unit_fact(LAX), TRUTHS[LAX])
    shifted = bench.unit_check(
        _csv("date,precip", "2026-10-15,15.5", "2026-10-16,1.6") + "TABLE-UNIT: precip | mm",
        _unit_fact(CSV),
        TRUTHS[CSV],
    )

    assert [f["reason"] for f in forecast["failures"]] == [
        "a figure for the asked quantity ('tomorrow afternoon') that is not the value and lies outside the span"
    ]
    assert [f["reason"] for f in shifted["failures"]] == [
        "a table is given, but it does not hold the value in the column the case names in the row of 2026-10-16"
    ]


def test_a_big_drop_is_read_over_the_paired_repeats_only() -> None:
    """Repeats 4 and 5 are invalid before and fail after: unpaired that is a drop of 40 points, paired there is none."""
    before = _file(cases=40, bad={("c0", 4), ("c0", 5)})
    after = _file(cases=40, fail={("c0", 4), ("c0", 5)})

    text, refused = bench.compare_with_status(before, after)

    assert not refused, text
    assert "big drop" not in text
    assert "difference +0.0%" in text


def test_a_record_that_lacks_a_field_is_refused_and_the_wrong_unit_failure_is_named(tmp_path: Path) -> None:
    """`add-run` names the fields a record lacks; the unit check names the unit error it found."""
    path, new = _add_run_file(tmp_path)
    lacking = {k: v for k, v in {**new, "repeat": 3}.items() if k != "facts_ok"}
    wrong = bench.unit_check(
        "RESULT: 84 % | mean\nRESULT: 0.84 % | as returned", _unit_fact(HUMIDITY), TRUTHS[HUMIDITY]
    )

    with pytest.raises(ValueError, match=re.escape("it lacks ['facts_ok']")):
        bench.add_run(path, lacking)
    assert [f["reason"] for f in wrong["failures"]] == [
        "the figure is the value in the unit it was read in, written with another unit ('%')"
    ]
