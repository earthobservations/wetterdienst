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
    bench.py run MODEL URL NAME PROMPT OUT [--timeout S] [--max-usd N]   one tested agent, headless (run_subject.sh)
    bench.py probe URL | tools-size [--server URL]                   does the server answer / what tools/list costs
    bench.py cleanup                                                 remove the project dirs headless runs leave
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
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
CASES_PATH = SKILL_DIR / "cases.json"
PROMPT_PATH = SKILL_DIR / "prompt.md"
#: tool calls of the harness that are no step and no violation: loading deferred tools, the subagent's hand-back
HARNESS_TOOLS = {"ToolSearch", "SubagentHandback"}
SIGNIFICANCE = 0.05
#: how much lower the pass rate of the new run may be than the previous one and still be "no worse"
NON_INFERIORITY_MARGIN = 0.10
#: the share of invalid runs (the server was not reachable) above which two files are not compared
MAX_INVALID_SHARE = 0.03
#: bump it when the arithmetic changes (what counts as a step, a checkpoint, a violation, an aggregate or a verdict):
#: two results files of another logic version are not compared
LOGIC_VERSION = 3
UTC = dt.timezone.utc  # noqa: UP017 - the script also runs on the python3 of a Mac, which is older than 3.11
#: Claude Code puts a tool result that exceeds its limit in a file and answers with this notice; no Read tool to open it
SPILL_RE = re.compile(r"^Error: result \(([\d,]+) characters\) exceeds maximum allowed")
HOSTED_MCP_URL = "https://wetterdienst.eobs.org/mcp/v1"
SAFE_NAME = re.compile(r"^[A-Za-z0-9_]{1,40}$")
SAFE_URL = re.compile(r"^https?://[A-Za-z0-9.\-]+(:\d{1,5})?(/[A-Za-z0-9._~\-/]*)?$")


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
        "defaults": digest(data.get("defaults", {})),
        "logic": LOGIC_VERSION,
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
        if "on_date" in rule:
            return any(_on_date(str(item), rule["on_date"]) for item in items)
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
    """Turn a `timestamp` argument (a date, a year, an instant or an interval of them) into its start and end.

    A date, month or year runs to the end of what it names; an instant is a point, and so is the end of an
    interval written as an instant (`2025-12-26T00:00:00Z/2025-12-26T23:59:59Z` ends at 23:59:59).
    """
    first, sep, second = text.partition("/")
    try:
        return _bound(first, end=False), _bound(second if sep else first, end=True)
    except ValueError:
        return None


def _on_date(timestamp: str, day: str) -> bool:
    """Tell whether a `timestamp` argument reaches into a day: an interval overlaps it, an instant falls on it."""
    span = _span(timestamp)
    if span is None:
        return False
    start, end = _bound(day, end=False), _bound(day, end=True)
    if span[0] == span[1]:
        return start <= span[0] < end
    return span[0] < end and span[1] > start


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


def result_metadata(text: str) -> dict[str, Any]:
    """Parse a tool result and give its `metadata` block, whatever the layout of the JSON (compact, pretty, wrapped)."""
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    inner = data.get("result") if isinstance(data.get("result"), dict) else data
    meta = inner.get("metadata") if isinstance(inner.get("metadata"), dict) else data.get("metadata")
    return meta if isinstance(meta, dict) else {}


def listed_stations(text: str) -> list[dict[str, Any]]:
    """Give the stations a `stations` result lists (id, name, position), at most 200 of them."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    inner = data.get("result") if isinstance(data, dict) and isinstance(data.get("result"), dict) else data
    rows = inner.get("stations") if isinstance(inner, dict) else None
    if not isinstance(rows, list):
        return []
    return [
        {"id": r.get("station_id"), "name": r.get("name"), "lat": r.get("latitude"), "lon": r.get("longitude")}
        for r in rows[:200]
        if isinstance(r, dict)
    ]


def invalid_reason(servers: list[dict[str, Any]] | None, listed: list[str], prefix: str) -> str | None:
    """Say why a run says nothing about the model: the server was not connected or offered no tool (headless init)."""
    if servers is None:
        return None
    name = prefix.removeprefix("mcp__").removesuffix("__")
    found = [s for s in servers if s.get("name") == name]
    if not found:
        return f"the server {name!r} is not among the MCP servers of the session"
    if found[0].get("status") != "connected":
        return f"the server {name!r} was {found[0].get('status')!r}, not connected"
    if not any(tool.startswith(prefix) for tool in listed):
        return f"the server {name!r} offered no tool"
    return None


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
    servers: list[dict[str, Any]] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind = record.get("type")
        if kind == "system" and record.get("subtype") == "init":
            listed = record.get("tools") or []
            model = record.get("model")
            servers = record.get("mcp_servers")
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
                            "answered": False,
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
                        call["answered"] = True
                        call["result_chars"] = len(text)
                        call["result_head"] = text[:1500]
                        call["ok"] = not block.get("is_error", False)
                        spill = SPILL_RE.match(text)
                        if spill:
                            # the result is in a file the tested agent cannot open: the notice is what it got
                            call["spilled"] = True
                            call["result_chars"] = int(spill.group(1).replace(",", ""))
                        meta = result_metadata(text)
                        call["data_updated_at"] = meta.get("data_updated_at")
                        call["retrieved_at"] = meta.get("retrieved_at")
                        if (meta.get("producer") or {}).get("version"):
                            versions.add(meta["producer"]["version"])
                        if call["tool"] == "stations":
                            call["stations"] = listed_stations(text)
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
    for call in calls:
        if not call["answered"]:
            # a call the run ended on (a budget stop, a timeout): it is a step, no read, and meets no checkpoint
            call["ok"] = False
            call["unanswered"] = True
    invalid = invalid_reason(servers, listed, server)
    sizes = [call["result_chars"] for call in calls]
    return {
        "invalid": invalid is not None,
        "invalid_reason": invalid,
        "spilled_calls": sum(1 for c in calls if c.get("spilled")),
        "unanswered_calls": sum(1 for c in calls if c.get("unanswered")),
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
        "end": result_line.get("subtype"),
        "terminal_reason": result_line.get("terminal_reason"),
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
            if calls[index].get("unanswered"):
                continue
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
        "mechanical_pass": 1 <= steps <= case["max_steps"] and first_met and not run.get("invalid"),
        "mechanical_facts": {
            fact["id"]: network_serves(run, fact) for fact in case.get("facts", []) if fact["kind"] == "network_serves_place"
        },
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Give the distance between two points on the earth in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def network_serves(run: dict[str, Any], fact: dict[str, Any]) -> dict[str, Any]:
    """Check a claim that a network serves a place against the stations the subject itself got listed.

    A `stations` call of the run that listed a station within `radius_km` of one of the `places` shows that its provider
    and network serve the place; the claim holds when the answer names the provider or the network of such a call.
    """
    near = []
    for call in run["calls"]:
        if call["tool"] != "stations" or not call["ok"]:
            continue
        for station in call.get("stations") or []:
            if station.get("lat") is None or station.get("lon") is None:
                continue
            for place in fact["places"]:
                km = haversine_km(station["lat"], station["lon"], place["latitude"], place["longitude"])
                if km <= fact["radius_km"]:
                    near.append(
                        {
                            "provider": call["arguments"].get("provider"),
                            "network": call["arguments"].get("network"),
                            "station": station["id"],
                            "name": station["name"],
                            "place": place["name"],
                            "km": round(km),
                        }
                    )
    answer = run["answer"]
    named = [
        n for n in near if any(re.search(rf"(?i)\b{re.escape(str(n[k]))}\b", answer) for k in ("provider", "network") if n[k])
    ]
    return {"ok": bool(named), "named": named[:5], "stations_near": near[:5]}


# ----------------------------------------------------------------------------------- aggregates and comparison


def fisher_two_sided(a: int, n1: int, b: int, n2: int) -> float:
    """Fisher's exact test, two-sided: the chance of a split of passes between two runs at least this uneven."""
    total, passes = n1 + n2, a + b

    def probability(x: int) -> float:
        return math.comb(passes, x) * math.comb(total - passes, n1 - x) / math.comb(total, n1)

    observed = probability(a)
    low, high = max(0, passes - n2), min(passes, n1)
    return min(1.0, sum(p for x in range(low, high + 1) if (p := probability(x)) <= observed * (1 + 1e-9)))


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Give the Wilson score interval of a proportion of k out of n."""
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def newcombe_difference(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float, float]:
    """Give the difference of two proportions (second minus first) with its 95 % interval (Newcombe, method 10)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    diff = p2 - p1
    return diff, diff - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2), diff + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)


def required_runs(rate: float, margin: float = NON_INFERIORITY_MARGIN) -> int:
    """Give the runs per side that show "no worse than `margin`" with 80 % power when nothing has changed (one-sided 2.5 %)."""
    rate = min(max(rate, 0.05), 0.95)
    return math.ceil(2 * rate * (1 - rate) * (1.959964 + 0.841621) ** 2 / margin**2)


def _median(values: list[float]) -> float | None:
    """Take the median, or None for no values."""
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate the repeats of one (case, tier), or a pool of them; an invalid run (no server) is left out and counted."""
    invalid = sum(1 for r in runs if r.get("invalid"))
    runs = [r for r in runs if not r.get("invalid")]
    n = len(runs)
    return {
        "n": n,
        "invalid": invalid,
        "passed": sum(bool(r["passed"]) for r in runs),
        "facts_ok": sum(bool(r.get("facts_ok")) for r in runs),
        "violation_free": sum(1 for r in runs if not r["violations"]),
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


def _row(label: str, a: dict[str, Any], limit: Any = None) -> str:  # noqa: ANN401
    """Format one row of the report."""
    steps = f"{_fmt(a['steps_median'])}/{a['steps_max']}" + (f" ({limit})" if limit is not None else "")
    return (
        f"| {label} | {a['passed']}/{a['n']} | {steps} | {a['checkpoints_k']}/{a['checkpoints_n']} | {a['violations']} "
        f"| {a['facts_ok']}/{a['n']} | {_fmt(a['result_chars_median'])} | {_fmt(a['output_tokens_median'])} "
        f"| {_fmt(a['context_tokens_first_median'])} | {_fmt(a['total_tokens_median'])} |"
    )


def report(results: dict[str, Any]) -> str:
    """Render the table of a results file: one row per (case, tier), then the pooled rows per tier."""
    lines = [
        "| case / tier | passed | steps median/max (limit) | checkpoints | violations | facts ok "
        "| result chars median | out tokens median | context tokens first median | total tokens median |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    limits = {r["case"]: r["max_steps"] for r in results["runs"]}
    pooled: dict[str, list[dict[str, Any]]] = {}
    for (case, tier), runs in groups(results).items():
        pooled.setdefault(tier, []).extend(runs)
        lines.append(_row(f"{case} [{tier}]", aggregate(runs), limits.get(case, "?")))
    lines.extend(_row(f"**all cases [{tier}]**", aggregate(runs)) for tier, runs in pooled.items())
    invalid = sum(1 for r in results["runs"] if r.get("invalid"))
    if invalid:
        reasons = sorted({r.get("invalid_reason") or "?" for r in results["runs"] if r.get("invalid")})
        lines.append(f"\n{invalid} of {len(results['runs'])} runs are invalid (no server) and left out above: {'; '.join(reasons)}")
    return "\n".join(lines)


def _hint(prev: list[dict[str, Any]], new: list[dict[str, Any]]) -> str:
    """Say what a Fisher test of the passes of one (case, tier) shows: a hint only, since it has little power at 5 runs."""
    a, b = aggregate(prev), aggregate(new)
    if not a["n"] or not b["n"]:
        return "no valid runs"
    p = fisher_two_sided(a["passed"], a["n"], b["passed"], b["n"])
    before, after = a["passed"] / a["n"], b["passed"] / b["n"]
    word = "fewer passes" if p < SIGNIFICANCE and after < before else "more passes" if p < SIGNIFICANCE and after > before else "no clear change"
    return (
        f"{a['passed']}/{a['n']} -> {b['passed']}/{b['n']} (Fisher p={p:.3f}, a hint): {word}; steps median "
        f"{_fmt(a['steps_median'])} -> {_fmt(b['steps_median'])}; result chars median {_fmt(a['result_chars_median'])} -> "
        f"{_fmt(b['result_chars_median'])}"
    )


def _non_inferiority(label: str, k1: int, n1: int, k2: int, n2: int, margin: float) -> tuple[str, str]:
    """Judge one pooled rate (previous k1/n1, new k2/n2) against the margin: 'no worse', 'worse' or 'inconclusive'."""
    diff, low, high = newcombe_difference(k1, n1, k2, n2)
    if low > -margin:
        verdict = "no worse"
    elif high < 0:
        verdict = "WORSE"
    else:
        verdict = "inconclusive"
    text = f"{label} {k1}/{n1} -> {k2}/{n2}: difference {diff:+.1%} (95 % interval {low:+.1%} to {high:+.1%}) -> {verdict}"
    return verdict, text


def _sizes(prev_groups: dict[Any, list[dict[str, Any]]], cur_groups: dict[Any, list[dict[str, Any]]], keys: list[Any]) -> list[str]:
    """Give the paired differences of the sizes per (case, tier): the median of the differences of the medians."""
    lines = []
    for field, label in (
        ("result_chars_median", "tool result chars"),
        ("context_tokens_first_median", "context tokens at the first request"),
        ("total_tokens_median", "total tokens"),
        ("output_tokens_median", "output tokens"),
        ("steps_median", "steps"),
    ):
        deltas, before, after = [], [], []
        for key in keys:
            a, b = aggregate(prev_groups[key]), aggregate(cur_groups[key])
            if a[field] is not None and b[field] is not None:
                deltas.append(b[field] - a[field])
                before.append(a[field])
                after.append(b[field])
        if deltas:
            lines.append(
                f"  {label}: median per case {_fmt(_median(before))} -> {_fmt(_median(after))}, paired difference (median over "
                f"{len(deltas)} cases) {_median(deltas):+g}"
            )
    return lines


def compare(previous: dict[str, Any], current: dict[str, Any], margin: float = NON_INFERIORITY_MARGIN) -> str:  # noqa: C901, PLR0912
    """Compare two results files: "no worse" is a non-inferiority claim on the pooled rates of each tier.

    Only the (case, tier) whose case hash and prompt are unchanged are compared, and only if the logic version, the
    defaults and the resolved model ids agree. Pooled per tier, the passes, the facts and the share of runs without a
    violation are each compared with a Newcombe interval of the difference against the margin ("no worse" needs the
    lower bound above minus the margin for all three). The per (case, tier) Fisher tests are hints only.
    """
    meta_p, meta_c = previous["meta"], current["meta"]
    out = []
    for key in ("mode", "models", "server", "server_version", "reference_version", "claude_version", "tools_deferred", "cases_file"):
        if meta_p.get(key) != meta_c.get(key):
            out.append(f"differs: {key}: {meta_p.get(key)!r} -> {meta_c.get(key)!r}")
    for key, what in (("logic", "the logic version of bench.py"), ("defaults", "the defaults of the cases file")):
        if meta_p.get(key) != meta_c.get(key):
            return "\n".join([*out, f"not compared: {what} differs ({meta_p.get(key)!r} -> {meta_c.get(key)!r}), so the counting does not"])
    for label, results in (("previous", previous), ("current", current)):
        runs = results["runs"]
        share = sum(1 for r in runs if r.get("invalid")) / max(len(runs), 1)
        if share > MAX_INVALID_SHARE:
            return "\n".join([*out, f"not compared: {share:.0%} of the {label} runs are invalid (no server), above {MAX_INVALID_SHARE:.0%}"])
    if meta_p.get("prompt") != meta_c.get("prompt"):
        return "\n".join([*out, f"not compared: the prompt changed ({meta_p.get('prompt')} -> {meta_c.get('prompt')})"])
    prev_groups, cur_groups = groups(previous), groups(current)
    comparable, skipped = [], 0
    for key in cur_groups:
        same_case = meta_p["case_hashes"].get(key[0]) == meta_c["case_hashes"].get(key[0])
        if key in prev_groups and same_case:
            comparable.append(key)
        else:
            skipped += 1
    out.append(f"{len(comparable)} (case, tier) compared, {skipped} skipped (new, removed or changed case)")
    for tier in sorted({t for _, t in comparable}):
        keys = [k for k in comparable if k[1] == tier]
        prev = [r for k in keys for r in prev_groups[k]]
        cur = [r for k in keys for r in cur_groups[k]]
        models_p = sorted({r.get("model") for r in prev if r.get("model")})
        models_c = sorted({r.get("model") for r in cur if r.get("model")})
        if models_p != models_c:
            out.append(f"POOLED {tier}: not compared, the resolved model ids differ: {models_p} -> {models_c}")
            continue
        a, b = aggregate(prev), aggregate(cur)
        if not a["n"] or not b["n"]:
            out.append(f"POOLED {tier}: no valid runs to compare")
            continue
        verdicts = []
        out.append(f"POOLED {tier} ({a['n']} runs before, {b['n']} after; margin {margin:.0%}):")
        for label, field in (("passed", "passed"), ("facts ok", "facts_ok"), ("no violation", "violation_free")):
            verdict, text = _non_inferiority(label, a[field], a["n"], b[field], b["n"], margin)
            verdicts.append(verdict)
            out.append(f"  {text}")
        overall = "WORSE" if "WORSE" in verdicts else "NO WORSE" if all(v == "no worse" for v in verdicts) else "INCONCLUSIVE"
        need = required_runs(a["passed"] / a["n"], margin)
        out.append(
            f"  => {overall}. Power: showing no worse than {margin:.0%} at a pass rate of {a['passed'] / a['n']:.0%} takes about "
            f"{need} runs per side; there are {min(a['n'], b['n'])}. Fewer runs make INCONCLUSIVE the usual answer, which is "
            "not 'no worse'."
        )
        out.extend(_sizes(prev_groups, cur_groups, keys))
    out.extend(f"hint {case} [{tier}]: {_hint(prev_groups[(case, tier)], cur_groups[(case, tier)])}" for case, tier in comparable)
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


# --------------------------------------------------------------------------------------------- the server and runs


def _mcp_post(url: str, payload: dict[str, Any], session: str | None, timeout: float) -> tuple[dict[str, Any], str | None]:
    """POST one JSON-RPC message to a streamable-HTTP MCP endpoint; give the answer and the session id."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "wetterdienst-mcp-benchmark",
        "MCP-Protocol-Version": "2025-06-18",
    }
    if session:
        headers["Mcp-Session-Id"] = session
    request = urllib.request.Request(url, json.dumps(payload).encode(), headers, method="POST")  # noqa: S310 - http(s) only
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read().decode("utf-8")
        sid = response.headers.get("mcp-session-id") or session
        kind = response.headers.get("content-type", "")
    if "id" not in payload or not raw.strip():
        return {}, sid
    if "text/event-stream" in kind:
        raw = next((line[5:].strip() for line in raw.splitlines() if line.startswith("data:")), "{}")
    return json.loads(raw), sid


def list_tools(url: str, timeout: float = 30) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Ask a server for its `serverInfo` and its `tools/list`, as a client does (all pages)."""
    reply, sid = _mcp_post(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "mcp-benchmark", "version": "1"}},
        },
        None,
        timeout,
    )
    info = (reply.get("result") or {}).get("serverInfo") or {}
    _mcp_post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid, timeout)
    tools: list[dict[str, Any]] = []
    cursor = None
    for page in range(1, 20):
        params = {"cursor": cursor} if cursor else {}
        reply, sid = _mcp_post(url, {"jsonrpc": "2.0", "id": page + 1, "method": "tools/list", "params": params}, sid, timeout)
        result = reply.get("result") or {}
        tools.extend(result.get("tools") or [])
        cursor = result.get("nextCursor")
        if not cursor:
            break
    return info, tools


def server_version(url: str, timeout: float = 15) -> str | None:
    """Ask the wetterdienst behind an MCP URL for its version (`/api/version` of the same origin), or None."""
    parts = urllib.parse.urlsplit(url)
    request = urllib.request.Request(  # noqa: S310
        f"{parts.scheme}://{parts.netloc}/api/version", headers={"User-Agent": "wetterdienst-mcp-benchmark"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            body = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    return str(body.get("version")) if isinstance(body, dict) and body.get("version") else None


def probe(url: str) -> dict[str, Any]:
    """Check that a server answers and offers tools; give its serverInfo, the number of tools and the wetterdienst version."""
    info, tools = list_tools(url)
    if not tools:
        msg = f"{url} answered but lists no tool"
        raise RuntimeError(msg)
    return {"url": url, "server_info": info, "tools": len(tools), "wetterdienst_version": server_version(url)}


def tools_size(url: str) -> str:
    """Tell what `tools/list` costs on the wire, per tool: the characters of the description, inputSchema and outputSchema.

    A client may send the model less than this: the benchmark measures what the tested agent's context holds
    (`context_tokens_first`), and Claude Code does not appear to send the `outputSchema` to the model, so a change
    that slims the output schemas shows here and not in the benchmark.
    """
    info, tools = list_tools(url)
    rows = []
    for tool in tools:
        sizes = (
            len(tool.get("description") or ""),
            len(json.dumps(tool.get("inputSchema") or {}, separators=(",", ":"), ensure_ascii=False)),
            len(json.dumps(tool.get("outputSchema") or {}, separators=(",", ":"), ensure_ascii=False)),
        )
        rows.append((tool["name"], *sizes))
    lines = [f"{url} ({info.get('name')} {info.get('version')}): {len(tools)} tools", "| tool | description | inputSchema | outputSchema |", "| --- | --- | --- | --- |"]
    lines.extend(f"| {n} | {d} | {i} | {o} |" for n, d, i, o in rows)
    total = [sum(r[k] for r in rows) for k in (1, 2, 3)]
    lines.append(f"| **all** | **{total[0]}** | **{total[1]}** | **{total[2]}** |")
    lines.append(f"characters in all: {sum(total)}")
    return "\n".join(lines)


def _slug(path: str) -> str:
    """Give the name Claude Code gives the project directory of a working directory."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(path))


def _remove_project_dir(name: str) -> bool:
    """Remove a project directory of Claude Code that a headless run of this benchmark left (memory, spilled results)."""
    root = Path.home() / ".claude" / "projects"
    target = root / name
    if "mcpbench-subject" not in name or target.parent != root or not target.is_dir():
        return False
    shutil.rmtree(target, ignore_errors=True)
    return True


def cleanup() -> int:
    """Remove every project directory that headless runs of this benchmark left in `~/.claude/projects`."""
    root = Path.home() / ".claude" / "projects"
    names = [p.name for p in root.iterdir()] if root.is_dir() else []
    return sum(_remove_project_dir(n) for n in names if "mcpbench-subject" in n)


def run_subject(model: str, url: str, name: str, prompt_file: str, out: str, timeout: float, max_usd: float) -> int:  # noqa: PLR0913
    """Run one tested agent headless, outside the repository, with only the server under test; write its stream-json.

    Exit codes: 0 the run ended, 2 a bad argument or no `claude`, 3 the server did not answer, 124 the timeout, other
    the exit code of `claude`.
    """
    if not re.fullmatch(r"[A-Za-z0-9._\-\[\]]{1,60}", model) or not SAFE_NAME.match(name) or not SAFE_URL.match(url):
        sys.stderr.write("run: the model, the server name or the URL has characters this script does not pass on\n")
        return 2
    prompt_path, out_path = Path(prompt_file).resolve(), Path(out).resolve()
    if not prompt_path.is_file():
        sys.stderr.write(f"run: the prompt file {prompt_path} does not exist\n")
        return 2
    claude = shutil.which("claude")
    if claude is None:
        sys.stderr.write("run: `claude` is not on the PATH: headless mode needs Claude Code (use mode=subagent otherwise)\n")
        return 2
    try:
        probe(url)
    except (OSError, ValueError, RuntimeError) as error:
        sys.stderr.write(f"run: the MCP server at {url} does not answer: {error}\n")
        return 3
    work = tempfile.mkdtemp(prefix="mcpbench-subject.")
    slug = _slug(work)
    config = Path(work) / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {name: {"type": "http", "url": url}}}), encoding="utf-8")
    command = [
        claude, "-p", prompt_path.read_text(encoding="utf-8"),
        "--model", model,
        "--mcp-config", str(config), "--strict-mcp-config",
        "--tools", "",
        "--allowedTools", f"mcp__{name}",
        "--disable-slash-commands",
        "--setting-sources", "",
        "--no-session-persistence",
        "--max-budget-usd", str(max_usd),
        "--output-format", "stream-json", "--verbose",
    ]  # fmt: skip
    code = 0
    try:
        with out_path.open("w", encoding="utf-8") as stream:
            try:
                code = subprocess.run(command, cwd=work, stdout=stream, stderr=subprocess.PIPE, timeout=timeout, check=False).returncode  # noqa: S603
            except subprocess.TimeoutExpired:
                sys.stderr.write(f"run: stopped after {timeout:g} s (the transcript so far is kept)\n")
                code = 124
    finally:
        shutil.rmtree(work, ignore_errors=True)
        _remove_project_dir(slug)
    return code


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
    p_probe = sub.add_parser("probe")
    p_probe.add_argument("url")
    p_size = sub.add_parser("tools-size")
    p_size.add_argument("--server", default=HOSTED_MCP_URL)
    sub.add_parser("cleanup")
    p_run = sub.add_parser("run")
    for arg in ("model", "url", "name", "prompt", "out"):
        p_run.add_argument(arg)
    p_run.add_argument("--timeout", type=float, default=float(os.environ.get("MCPBENCH_TIMEOUT", "300")))
    p_run.add_argument("--max-usd", type=float, default=float(os.environ.get("MCPBENCH_MAX_USD", "0.50")))
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
    elif args.command == "probe":
        try:
            print(json.dumps(probe(args.url), indent=1))
        except (OSError, ValueError, RuntimeError) as error:
            sys.stderr.write(f"probe: {args.url} does not answer: {error}\n")
            return 3
    elif args.command == "tools-size":
        print(tools_size(args.server))
    elif args.command == "cleanup":
        print(f"removed {cleanup()} project directories of benchmark runs")
    elif args.command == "run":
        return run_subject(args.model, args.url, args.name, args.prompt, args.out, args.timeout, args.max_usd)
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
