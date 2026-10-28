#!/usr/bin/env python3
"""The deterministic half of the MCP benchmark: prompts, transcripts, checkpoints, aggregates, comparison.

Standard library only; run it as `python3 -I bench.py <command>`. The orchestrating Claude judges what needs
reading (is it an answer, are the facts right); everything that can be counted is counted here, so that two runs
are compared on the same arithmetic.

    bench.py prompt <case-id> --today YYYY-MM-DD [--tools TEXT]      the prompt of the tested agent
    bench.py analyze <transcript.jsonl> --case <id> --server <prefix> [--cases PATH]
                                                                     steps, checkpoints, violations, size, tokens
    bench.py report <results.json>                                   the table and the aggregates
    bench.py compare <previous.json> <results.json>                  what changed beyond noise
    bench.py unit --case ID --fact ID --truth V [V2] --answer TEXT   the unit fact of a case against an answer
    bench.py hashes [--cases PATH]                                   hash of the cases file and of each case

A transcript is the stream-json of `claude -p` (headless) or the JSONL of a subagent (the `output_file` the Agent
tool returns, or `subagents/agent-<id>.jsonl` under the session directory, a detail of the harness): both hold
`assistant` and `user` messages with `tool_use` and `tool_result` blocks, which is all that is read.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
CASES_PATH = SKILL_DIR / "cases.json"
PROMPT_PATH = SKILL_DIR / "prompt.md"
#: tool calls of the harness that are no step and no violation: loading deferred tools, the subagent's hand-back
HARNESS_TOOLS = {"ToolSearch", "SubagentHandback"}
SIGNIFICANCE = 0.05
UTC = dt.timezone.utc  # noqa: UP017 - the script also runs on the python3 of a Mac, which is older than 3.11
VERSION_RE = re.compile(r'"producer":\{"name":"wetterdienst","version":"([^"]+)"')
UPDATED_RE = re.compile(r'"data_updated_at":"([^"]+)"')
RETRIEVED_RE = re.compile(r'"retrieved_at":"([^"]+)"')


# ---------------------------------------------------------------------------------------------- files and hashes


def load_cases(path: Path = CASES_PATH) -> dict[str, Any]:
    """Read the cases file."""
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value: Any) -> str:  # noqa: ANN401
    """Hash a JSON value by its canonical text, 12 hex digits."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def prompt_version() -> str:
    """Hash the prompt template: a changed prompt makes two runs incomparable."""
    return hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest()[:8]


def hashes(data: dict[str, Any]) -> dict[str, Any]:
    """Hash the whole file, each case, and the prompt."""
    return {
        "cases_file": digest(data),
        "prompt": prompt_version(),
        "cases": {case["id"]: digest(case) for case in data["cases"]},
    }


def find_case(data: dict[str, Any], case_id: str) -> dict[str, Any]:
    """Find a case by id."""
    for case in data["cases"]:
        if case["id"] == case_id:
            return case
    msg = f"no case {case_id!r}"
    raise SystemExit(msg)


def render_prompt(case: dict[str, Any], today: str, tools: str) -> str:
    """Fill the prompt template for one case."""
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.format(today=today, question=case["question"], max_steps=case["max_steps"], tools=tools)


# ------------------------------------------------------------------------------------------------ matching calls


def _elements(value: Any) -> list[Any]:  # noqa: ANN401
    """Split an argument into what it names: a list's items, or the parts of a comma-separated string."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and "," in value:
        return [value, *[part.strip() for part in value.split(",")]]
    return [value]


def _same(a: Any, b: Any) -> bool:  # noqa: ANN401
    """Compare an argument with a literal: strings ignoring case, numbers and booleans by value."""
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().casefold() == b.strip().casefold()
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return a == b


def rule_holds(value: Any, rule: Any) -> bool:  # noqa: ANN401, C901
    """Tell whether an argument's value satisfies a rule: a literal, `any_of`, `regex`, `between`, present, absent."""
    if isinstance(rule, dict):
        if rule.get("absent"):
            return value is None
        if rule.get("present"):
            return value is not None
        if value is None:
            return False
        items = _elements(value)
        if "contains_date" in rule:
            day = rule["contains_date"]
            return any(
                (span := _span(str(item))) is not None
                and span[0] <= _bound(day, end=False)
                and _bound(day, end=True) <= span[1]
                for item in items
            )
        if "any_of" in rule:
            return any(_same(item, wanted) for item in items for wanted in rule["any_of"])
        if "regex" in rule:
            return any(re.search(rule["regex"], str(item)) for item in items)
        if "between" in rule:
            low, high = rule["between"]
            for item in items:
                try:
                    if low <= float(item) <= high:
                        return True
                except (TypeError, ValueError):
                    continue
            return False
        return False
    if value is None:
        return False
    return any(_same(item, rule) for item in _elements(value))


def call_matches(call: dict[str, Any], match: dict[str, Any], defaults: dict[str, Any], *, default_ok: Any = True) -> bool:  # noqa: ANN401
    """Tell whether a logged call satisfies a match: its tool, whether it succeeded, and its argument rules.

    An argument the call left out counts as its default (`defaults` of the cases file), so that `alerts()` is
    the same call as `alerts(granularity="community")`.
    """
    tools = match["tool"] if isinstance(match["tool"], list) else [match["tool"]]
    if call["tool"] not in tools:
        return False
    if match.get("ok", default_ok) is True and not call["ok"]:
        return False
    given = call["arguments"]
    fallback = defaults.get(call["tool"], {})
    return all(rule_holds(given.get(arg, fallback.get(arg)), rule) for arg, rule in match.get("args", {}).items())


def _bound(text: str, *, end: bool) -> dt.datetime:
    """Turn a year, month, date or instant of a `timestamp` into the start or the end of what it names."""
    text = text.strip().replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}", text):
        year = int(text) + (1 if end else 0)
        return dt.datetime(year, 1, 1, tzinfo=UTC)
    if re.fullmatch(r"\d{4}-\d{2}", text):
        year, month = int(text[:4]), int(text[5:])
        if end:
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)  # noqa: PLR2004
        return dt.datetime(year, month, 1, tzinfo=UTC)
    moment = dt.datetime.fromisoformat(text)
    moment = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    if end and re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return moment + dt.timedelta(days=1)
    return moment


def _span(text: str) -> tuple[dt.datetime, dt.datetime] | None:
    """Turn a `timestamp` argument (a date, a year, an instant or an interval of them) into its start and end."""
    first, _, second = text.partition("/")
    try:
        return _bound(first, end=False), _bound(second or first, end=True)
    except ValueError:
        return None


def window_days(timestamp: Any) -> float:  # noqa: ANN401
    """Tell how many days a `timestamp` argument spans; no timestamp (the server's default window) is unbounded."""
    span = _span(str(timestamp)) if timestamp else None
    if span is None:
        return math.inf
    return (span[1] - span[0]).total_seconds() / 86400


# ------------------------------------------------------------------------------------------------- transcripts


def _flatten(content: Any) -> str:  # noqa: ANN401
    """Turn the content of a tool result into text: a string, or the text of its blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") if isinstance(b, dict) and b.get("type") == "text" else "" for b in content)
    return ""


def parse_transcript(path: Path, server: str) -> dict[str, Any]:  # noqa: C901, PLR0912, PLR0915
    """Read a transcript into the calls of the server's tools, the harness calls, the answer and the sizes.

    `server` is the prefix of the server's tool names, e.g. `mcp__wetterdienst__`. Every other tool the agent
    called (Bash, WebFetch, Read, ...) is listed in `other_tools`: for a benchmark that is a violation.
    """
    calls: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    searches: list[Any] = []
    search_ids: dict[str, int] = {}
    search_chars = 0
    other_tools: list[str] = []
    attachments: Counter[str] = Counter()
    requests: dict[str, dict[str, Any]] = {}
    answer = ""
    result_line: dict[str, Any] = {}
    listed: list[str] = []
    versions: set[str] = set()
    model = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind = record.get("type")
        if kind == "system" and record.get("subtype") == "init":
            listed = record.get("tools") or []
            model = record.get("model")
        elif kind == "attachment":
            attachments[(record.get("attachment") or {}).get("type", "?")] += 1
        elif kind == "result":
            result_line = record
        elif kind in {"assistant", "user"}:
            message = record.get("message") or {}
            content = message.get("content")
            if kind == "assistant":
                model = model or message.get("model")
                usage = message.get("usage")
                key = message.get("id") or record.get("requestId") or str(len(requests))
                if usage and key not in requests:
                    requests[key] = usage
            if not isinstance(content, list):
                continue
            for block in content:
                btype = block.get("type")
                if btype == "text" and kind == "assistant":
                    answer = block.get("text", "")
                elif btype == "tool_use":
                    name = block.get("name", "")
                    if name.startswith(server):
                        call = {
                            "n": len(calls) + 1,
                            "tool": name[len(server) :],
                            "arguments": block.get("input") or {},
                            "ok": True,
                            "result_chars": 0,
                            "result_head": "",
                        }
                        calls.append(call)
                        by_id[block["id"]] = call
                    elif name == "SubagentHandback":
                        answer = str((block.get("input") or {}).get("message", ""))
                    elif name == "ToolSearch":
                        searches.append(block.get("input"))
                        search_ids[block["id"]] = len(searches)
                    elif name not in HARNESS_TOOLS:
                        other_tools.append(name)
                elif btype == "tool_result":
                    call = by_id.get(block.get("tool_use_id"))
                    if call is not None:
                        text = _flatten(block.get("content"))
                        call["result_chars"] = len(text)
                        call["result_head"] = text[:1500]
                        call["ok"] = not block.get("is_error", False)
                        call["data_updated_at"] = (UPDATED_RE.search(text) or [None, None])[1]
                        call["retrieved_at"] = (RETRIEVED_RE.search(text) or [None, None])[1]
                        versions.update(VERSION_RE.findall(text))
                    elif block.get("tool_use_id") in search_ids:
                        search_chars += len(json.dumps(block.get("content"), ensure_ascii=False))
    if result_line.get("result"):
        answer = result_line["result"]
    contexts = [
        usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
        for usage in requests.values()
    ]
    output = sum(usage.get("output_tokens", 0) for usage in requests.values())
    total = sum(contexts) + output
    final = result_line.get("usage")
    if final:
        # headless: the result line carries the totals of the whole session; the usage of a streamed message is
        # the one at its start, whose output tokens are not yet counted
        output = final.get("output_tokens", 0)
        total = (
            final.get("input_tokens", 0)
            + final.get("cache_creation_input_tokens", 0)
            + final.get("cache_read_input_tokens", 0)
            + output
        )
    sizes = [call["result_chars"] for call in calls]
    return {
        "calls": calls,
        "steps": len(calls),
        "tool_searches": len(searches),
        "tools_deferred": bool(searches) or "ToolSearch" in listed,
        "tool_search_result_chars": search_chars,
        "other_tools": other_tools,
        "answer": answer.strip(),
        "model": model,
        "server_versions": sorted(versions),
        "tool_result_chars_sum": sum(sizes),
        "tool_result_chars_max": max(sizes, default=0),
        "output_tokens": output,
        "context_tokens_first": contexts[0] if contexts else None,
        "context_tokens_last": contexts[-1] if contexts else None,
        "total_tokens": total,
        "cost_usd": result_line.get("total_cost_usd"),
        "duration_ms": result_line.get("duration_ms"),
        "context_attachments": dict(attachments),
    }


def evaluate(case: dict[str, Any], run: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Count what a transcript allows: steps, ordered checkpoints, forbidden behaviours."""
    calls = run["calls"]
    position = 0
    met: list[str] = []
    missed: list[str] = []
    for checkpoint in case["checkpoints"]:
        # an `any_order` checkpoint is met by any call of the run and does not move the walk
        unordered = bool(checkpoint.get("any_order"))
        for index in range(0 if unordered else position, len(calls)):
            if any(call_matches(calls[index], match, defaults) for match in checkpoint["match"]):
                met.append(checkpoint["id"])
                if not unordered:
                    position = index
                break
        else:
            missed.append(checkpoint["id"])
    violations = [f"non-wetterdienst-tool:{name}" for name in dict.fromkeys(run["other_tools"])]
    for item in case.get("forbidden", []):
        if item["kind"] == "call":
            window = item.get("window_days_over")
            hit = any(
                call_matches(call, item["match"], defaults, default_ok="any")
                and (window is None or window_days(call["arguments"].get("timestamp")) > window)
                for call in calls
            )
        elif item["kind"] == "repeat":
            same = Counter(json.dumps(c["arguments"], sort_keys=True) for c in calls if c["tool"] == item["tool"])
            hit = max(same.values(), default=0) > item["max_identical"]
        else:
            hit = bool(re.search(item["regex"], run["answer"]))
        if hit:
            violations.append(item["id"])
    first_met = bool(case["checkpoints"]) and case["checkpoints"][0]["id"] in met
    steps = run["steps"]
    return {
        "steps": steps,
        "max_steps": case["max_steps"],
        "within_steps": 1 <= steps <= case["max_steps"],
        "checkpoints": {
            "k": len(met),
            "n": len(case["checkpoints"]),
            "met": met,
            "first_missed": missed[0] if missed else None,
        },
        "first_checkpoint_met": first_met,
        "violations": violations,
        "mechanical_pass": 1 <= steps <= case["max_steps"] and first_met,
    }


# ----------------------------------------------------------------------------------- aggregates and comparison


def fisher_two_sided(a: int, n1: int, b: int, n2: int) -> float:
    """Fisher's exact test, two-sided: the chance of a split of passes between two runs at least this uneven."""
    total, passes = n1 + n2, a + b

    def probability(x: int) -> float:
        return math.comb(passes, x) * math.comb(total - passes, n1 - x) / math.comb(total, n1)

    observed = probability(a)
    low, high = max(0, passes - n2), min(passes, n1)
    return min(1.0, sum(p for x in range(low, high + 1) if (p := probability(x)) <= observed * (1 + 1e-9)))


def _median(values: list[float]) -> float | None:
    """Take the median, or None for no values."""
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate the repeats of one (case, tier), or a pool of them."""
    n = len(runs)
    return {
        "n": n,
        "passed": sum(bool(r["passed"]) for r in runs),
        "facts_ok": sum(bool(r.get("facts_ok")) for r in runs),
        "checkpoints_k": sum(r["checkpoints"]["k"] for r in runs),
        "checkpoints_n": sum(r["checkpoints"]["n"] for r in runs),
        "violations": sum(len(r["violations"]) for r in runs),
        "steps_median": _median([r["steps"] for r in runs]),
        "steps_max": max((r["steps"] for r in runs), default=None),
        "result_chars_median": _median([r["tool_result_chars_sum"] for r in runs]),
        "result_chars_max": max((r["tool_result_chars_max"] for r in runs), default=None),
        "output_tokens_median": _median([r["output_tokens"] for r in runs]),
        "context_tokens_first_median": _median([r["context_tokens_first"] for r in runs]),
        "total_tokens_median": _median([r["total_tokens"] for r in runs]),
    }


def groups(results: dict[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Group the runs by (case, tier)."""
    found: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for run in results["runs"]:
        found.setdefault((run["case"], run["tier"]), []).append(run)
    return found


def _fmt(value: float | None) -> str:
    """Format a median."""
    return "-" if value is None else f"{value:g}"


def report(results: dict[str, Any]) -> str:
    """Render the table of a results file: one row per (case, tier), then the pooled rows per tier."""
    lines = [
        "| case | tier | passed | steps median/max (limit) | checkpoints | violations | facts ok | result chars median | out tokens median |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    limits = {r["case"]: r["max_steps"] for r in results["runs"]}
    pooled: dict[str, list[dict[str, Any]]] = {}
    for (case, tier), runs in groups(results).items():
        a = aggregate(runs)
        pooled.setdefault(tier, []).extend(runs)
        lines.append(
            f"| {case} | {tier} | {a['passed']}/{a['n']} | {_fmt(a['steps_median'])}/{a['steps_max']} ({limits.get(case, '?')})"
            f" | {a['checkpoints_k']}/{a['checkpoints_n']} | {a['violations']} | {a['facts_ok']}/{a['n']}"
            f" | {_fmt(a['result_chars_median'])} | {_fmt(a['output_tokens_median'])} |"
        )
    for tier, runs in pooled.items():
        a = aggregate(runs)
        lines.append(
            f"| **all cases** | **{tier}** | **{a['passed']}/{a['n']}** | {_fmt(a['steps_median'])}/{a['steps_max']} | "
            f"{a['checkpoints_k']}/{a['checkpoints_n']} | {a['violations']} | {a['facts_ok']}/{a['n']} | "
            f"{_fmt(a['result_chars_median'])} | {_fmt(a['output_tokens_median'])} |"
        )
    return "\n".join(lines)


def _verdict(prev: list[dict[str, Any]], new: list[dict[str, Any]]) -> str:
    """Say how a (case, tier) or a pool changed: beyond noise (Fisher's exact test, p < 0.05) or within it."""
    a, b = aggregate(prev), aggregate(new)
    p = fisher_two_sided(a["passed"], a["n"], b["passed"], b["n"])
    before, after = a["passed"] / a["n"], b["passed"] / b["n"]
    if p < SIGNIFICANCE and after < before:
        word = "REGRESSED"
    elif p < SIGNIFICANCE and after > before:
        word = "improved"
    else:
        word = "within noise"
    return (
        f"{a['passed']}/{a['n']} -> {b['passed']}/{b['n']} (p={p:.3f}): {word}; steps median {_fmt(a['steps_median'])} -> "
        f"{_fmt(b['steps_median'])}; result chars median {_fmt(a['result_chars_median'])} -> {_fmt(b['result_chars_median'])}; "
        f"output tokens median {_fmt(a['output_tokens_median'])} -> {_fmt(b['output_tokens_median'])}"
    )


def compare(previous: dict[str, Any], current: dict[str, Any]) -> str:
    """Compare two results files on the cases whose hash and prompt are unchanged; pool per tier first."""
    meta_p, meta_c = previous["meta"], current["meta"]
    out = []
    for key in ("mode", "models", "server", "server_version", "reference_version", "claude_version", "tools_deferred"):
        if meta_p.get(key) != meta_c.get(key):
            out.append(f"differs: {key}: {meta_p.get(key)!r} -> {meta_c.get(key)!r}")
    same_prompt = meta_p.get("prompt") == meta_c.get("prompt")
    if not same_prompt:
        out.append(f"the prompt changed ({meta_p.get('prompt')} -> {meta_c.get('prompt')}): no case is compared")
    prev_groups, cur_groups = groups(previous), groups(current)
    comparable, skipped = [], 0
    for key in cur_groups:
        same_case = meta_p["case_hashes"].get(key[0]) == meta_c["case_hashes"].get(key[0])
        if key in prev_groups and same_case and same_prompt:
            comparable.append(key)
        else:
            skipped += 1
    out.append(f"{len(comparable)} (case, tier) compared, {skipped} skipped (new, removed or changed case, or prompt)")
    for tier in sorted({t for _, t in comparable}):
        prev = [r for k in comparable if k[1] == tier for r in prev_groups[k]]
        cur = [r for k in comparable if k[1] == tier for r in cur_groups[k]]
        out.append(f"POOLED {tier}: {_verdict(prev, cur)}")
    out.extend(f"{case} [{tier}]: {_verdict(prev_groups[(case, tier)], cur_groups[(case, tier)])}" for case, tier in comparable)
    return "\n".join(out)


# -------------------------------------------------------------------------------------------------------- units

_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
#: what is no figure of a value: dates, times, years and station ids, blanked out before the figures are read
_NOT_A_FIGURE = re.compile(
    r"\d{4}-\d{2}-\d{2}|\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}|\d{1,2}:\d{2}|\b(?:19|20)\d{2}\b|\b0\d{4}\b"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})[a-z]*|\b(?:{_MONTHS})[a-z]*\.?\s+\d{{1,2}}\b",
    re.IGNORECASE,
)
_FIGURE = re.compile(r"(?<![\w.])[-−+]?\d+(?:[.,]\d+)?")
_BLANKS = "   "


def _starts_with_unit(tail: str, token: str) -> bool:
    """Tell whether the text after a figure starts with a unit token (a whole word where the token ends in one)."""
    text = tail.lstrip(_BLANKS)
    if not text.lower().startswith(token.lower()):
        return False
    following = text[len(token) : len(token) + 1]
    return not (token[-1].isalnum() and following.isalnum())


def _in_text(text: str, token: str) -> bool:
    """Tell whether a unit token is anywhere in a text as a word (so `_mm` of a column name counts)."""
    return re.search(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", text, re.IGNORECASE) is not None


def unit_check(answer: str, fact: dict[str, Any], truth: dict[str, float]) -> dict[str, Any]:  # noqa: C901, PLR0912
    """Check the figure of a value and its unit in an answer against the judge's own reading of the value.

    `truth` is `{"value": v}` or, for a forecast, `{"min": a, "max": b}`. A figure of the answer is a *candidate*
    when it equals the value expressed in one of the `accepted` units (`value * factor + offset`, within the fact's
    `tolerance` or `margin` scaled to that unit, or the rounding of the figure as written, whichever is wider).
    The unit must follow the figure
    directly (after blanks), or, for a figure in a table row, stand in the header or in the text. A candidate fails
    when a unit follows that is a `forbidden_tokens` one or one that belongs to another accepted unit than the one
    its number fits (`0.84 %` fits the fraction, not the percent); a figure with no unit after it is no failure but
    no success either. The check passes with at least one candidate with its right unit, no failing candidate, and
    every `required` unit present.
    """
    accepted = fact["accepted"]
    forbidden = fact.get("forbidden_tokens", [])
    low, high = (truth["value"], truth["value"]) if "value" in truth else (truth["min"], truth["max"])
    slack = fact.get("tolerance", fact.get("margin", 0))
    masked = _NOT_A_FIGURE.sub(lambda m: " " * len(m.group(0)), answer)
    lines = answer.split("\n")
    header = next((line for line in lines if "," in line and re.search("[A-Za-z]", line)), "")
    text_lines = " ".join(line for line in lines if "," not in line)
    ok_pairs: set[int] = set()
    ok_figures: list[str] = []
    failures: list[dict[str, str]] = []
    for found in _FIGURE.finditer(masked):
        raw = found.group(0)
        number = float(raw.replace("−", "-").replace(",", "."))
        decimals = len(re.split(r"[.,]", raw)[1]) if re.search(r"[.,]", raw) else 0
        rounding = 0.5 * 10**-decimals

        def fits_pair(pair: dict[str, Any], number: float = number, rounding: float = rounding) -> bool:
            """The figure is the value in this unit, within the tolerance or the rounding of the figure, whichever is wider."""
            wide = max(slack * abs(pair["factor"]), rounding) + 1e-9
            return low * pair["factor"] + pair.get("offset", 0) - wide <= number <= high * pair["factor"] + pair.get("offset", 0) + wide

        fits = [i for i, pair in enumerate(accepted) if fits_pair(pair)]
        if not fits:
            continue
        tail = answer[found.end() : found.end() + 40].split("\n")[0]
        row = "," in answer[: found.start()].rsplit("\n", 1)[-1] + answer[found.end() :].split("\n")[0]
        present = {i for i, pair in enumerate(accepted) if any(_starts_with_unit(tail, t) for t in pair["tokens"])}
        banned = [t for t in forbidden if _starts_with_unit(tail, t)]
        if row and not present and not banned:
            present = {i for i, pair in enumerate(accepted) if any(_in_text(f"{header} {text_lines}", t) for t in pair["tokens"])}
            banned = [t for t in forbidden if _in_text(f"{header} {text_lines}", t)]
        if banned:
            failures.append({"figure": raw, "reason": f"followed by the forbidden unit {banned[0]!r}"})
        elif present & set(fits):
            ok_pairs |= present & set(fits)
            ok_figures.append(raw)
        elif present:
            failures.append({"figure": raw, "reason": "its unit is not the unit its number is in"})
    required = [i for i, pair in enumerate(accepted) if pair.get("required")]
    missing = [accepted[i]["tokens"][0] for i in required if i not in ok_pairs]
    return {
        "ok": bool(ok_figures) and not failures and not missing,
        "ok_figures": ok_figures,
        "failures": failures,
        "required_missing": missing,
    }


# --------------------------------------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    """Run one command."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_prompt = sub.add_parser("prompt")
    p_prompt.add_argument("case")
    p_prompt.add_argument("--today", required=True)
    p_prompt.add_argument("--tools", default="alerts, auth, coverage, glossary, history, interpolate, issues, providers, stations, stripes_image, stripes_stations, stripes_values, summarize, values")
    p_analyze = sub.add_parser("analyze")
    p_analyze.add_argument("transcript", type=Path)
    p_analyze.add_argument("--case", required=True)
    p_analyze.add_argument("--server", required=True)
    p_unit = sub.add_parser("unit")
    p_unit.add_argument("--case", required=True)
    p_unit.add_argument("--fact", required=True)
    p_unit.add_argument("--truth", type=float, nargs="+", required=True, help="the value, or the min and max of a span")
    p_unit.add_argument("--answer", required=True)
    for name in ("report", "compare"):
        p = sub.add_parser(name)
        p.add_argument("files", nargs="+", type=Path)
    for p in (p_prompt, p_analyze, p_unit, sub.add_parser("hashes")):
        p.add_argument("--cases", type=Path, default=CASES_PATH)
    args = parser.parse_args(argv)
    if args.command == "prompt":
        sys.stdout.write(render_prompt(find_case(load_cases(args.cases), args.case), args.today, args.tools))
    elif args.command == "analyze":
        data = load_cases(args.cases)
        case = find_case(data, args.case)
        run = parse_transcript(args.transcript, args.server)
        verdict = evaluate(case, run, data.get("defaults", {}))
        print(json.dumps({"case": case["id"], **run, **verdict}, indent=1, ensure_ascii=False))
    elif args.command == "unit":
        case = find_case(load_cases(args.cases), args.case)
        fact = next(f for f in case["facts"] if f["id"] == args.fact)
        truth = {"value": args.truth[0]} if len(args.truth) == 1 else {"min": args.truth[0], "max": args.truth[1]}
        print(json.dumps(unit_check(args.answer, fact, truth), indent=1, ensure_ascii=False))
    elif args.command == "hashes":
        print(json.dumps(hashes(load_cases(args.cases)), indent=1))
    elif args.command == "report":
        print(report(json.loads(args.files[0].read_text(encoding="utf-8"))))
    else:
        print(compare(*(json.loads(f.read_text(encoding="utf-8")) for f in args.files[:2])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
