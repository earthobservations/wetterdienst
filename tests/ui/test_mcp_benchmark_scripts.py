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
            "invalid": i >= n - invalid.get((case, tier), 0),
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

    assert "| a [small] | 4/5 | 2/2 (4) | 5/10 | 0 | 4/5 | 1200 | 50 | 30000 | 90000 |" in table
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
    assert "takes about" in few
    assert "runs per side; there are 5" in few


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

    assert "1 (case, tier) compared, 1 skipped" in text
    assert "hint b [small]" not in text


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        ({"prompt": "p2"}, "the prompt changed"),
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

    assert "10% of the current runs are invalid" in bench.compare(before, after)


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
