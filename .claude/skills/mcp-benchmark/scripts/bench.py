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
    bench.py rerun --results FILE --out-dir DIR [--case ID] [--tier T] [--dry-run]   fill in invalid runs and missing repeats
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
import time
import urllib.parse
import urllib.request
from collections import Counter
from fractions import Fraction
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
#: a (case, tier) whose own rate fell by this much is printed next to the pooled verdict, whatever it says
BIG_DROP = 0.40
#: seconds a project directory of a run must be old before `cleanup` removes it: a younger one may be a run in progress
CLEANUP_MIN_AGE = 600
#: the longest a headless run may take, in seconds: below `CLEANUP_MIN_AGE`, since appending to a file does not move
#: the mtime of the directory that holds it, and `cleanup` must not take a run in progress for an old one
MAX_TIMEOUT = 540
#: bump it when the arithmetic changes (what counts as a step, a checkpoint, a violation, an aggregate or a verdict):
#: two results files of another logic version are not compared
LOGIC_VERSION = 5
UTC = dt.timezone.utc  # noqa: UP017 - the script also runs on the python3 of a Mac, which is older than 3.11
#: Claude Code puts a tool result that exceeds its limit in a file and answers with this notice; no Read tool to open it
SPILL_RE = re.compile(r"^Error: result \(([\d,]+) characters\) exceeds maximum allowed")
#: a short tool result that talks of a file it was saved to, in words bench.py does not know: reported, not trusted
SPILL_HINT = re.compile(r"saved|too large|exceeds", re.IGNORECASE)
SPILL_FILE = re.compile(r"/tool-results/|\.(?:txt|json)\b", re.IGNORECASE)
HOSTED_MCP_URL = "https://wetterdienst.eobs.org/mcp/v1"
SAFE_LABEL = re.compile(r"^[A-Za-z0-9._+\-]{1,60}$")
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


def invalid_reason(
    servers: list[dict[str, Any]] | None, listed: list[str], prefix: str, visible: set[str] | None = None
) -> str | None:
    """Say why a run says nothing about the model: the server was not connected or offered no tool.

    A headless transcript says it in its init record (`mcp_servers`, `tools`). A subagent's has none: the tools of the
    server must then be visible in it, as listed or deferred tools of the session or as calls (`visible`).
    """
    if servers is None:
        if visible is not None and not any(name.startswith(prefix) for name in visible):
            return f"the transcript shows no tool of the server ({prefix}...)"
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
    visible: set[str] = set()
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
            visible.update(listed)
        elif kind == "attachment":
            attached = record.get("attachment") or {}
            attachments[attached.get("type", "?")] += 1
            for key in ("addedNames", "surfacedNames", "readdedNames"):
                visible.update(attached.get(key) or [])
            visible.update(e.get("name", "") for e in attached.get("entries") or [] if isinstance(e, dict))
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
                    visible.add(name)
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
                            # the result is in a file the tested agent cannot open: the notice is what it got, and the
                            # call read nothing, whatever `is_error` says
                            call["spilled"] = True
                            call["ok"] = False
                            call["result_chars"] = int(spill.group(1).replace(",", ""))
                        elif len(text) < 2500 and SPILL_HINT.search(text) and SPILL_FILE.search(text):  # noqa: PLR2004
                            call["spill_unrecognised"] = True
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
    invalid = invalid_reason(servers, listed, server, visible)
    sizes = [call["result_chars"] for call in calls]
    return {
        "invalid": invalid is not None,
        "invalid_reason": invalid,
        "spilled_calls": sum(1 for c in calls if c.get("spilled")),
        "spill_unrecognised_calls": sum(1 for c in calls if c.get("spill_unrecognised")),
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
        "format_runs": sum(1 for r in runs if r.get("format_violation") is not None),
        "format_violations": sum(1 for r in runs if r.get("format_violation")),
        "checkpoints_k": sum(r["checkpoints"]["k"] for r in runs),
        "checkpoints_n": sum(r["checkpoints"]["n"] for r in runs),
        "violations": sum(len(r["violations"]) for r in runs),
        "spilled_calls": sum(r.get("spilled_calls", 0) for r in runs),
        "spill_unrecognised": sum(r.get("spill_unrecognised_calls", 0) for r in runs),
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
        f"| {a['facts_ok']}/{a['n']} | {a['format_violations']}/{a['format_runs']} | {_fmt(a['result_chars_median'])} | {_fmt(a['output_tokens_median'])} "
        f"| {_fmt(a['context_tokens_first_median'])} | {_fmt(a['total_tokens_median'])} | {a['spilled_calls']} |"
    )


def report(results: dict[str, Any]) -> str:
    """Render the table of a results file: one row per (case, tier), then the pooled rows per tier."""
    lines = [
        "| case / tier | passed | steps median/max (limit) | checkpoints | violations | facts ok | format violations "
        "| result chars median | out tokens median | context tokens first median | total tokens median | spilled calls |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
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
    judging = sum(1 for r in results["runs"] if r.get("needs_judging"))
    if judging:
        lines.append(f"\nWARNING: {judging} runs were re-run and still need judging; they count as failed until then")
    spilled = sum(r.get("spilled_calls", 0) for r in results["runs"])
    if spilled:
        lines.append(
            f"\n{spilled} tool calls had a result above the limit of Claude Code, saved to a file the tested agent cannot open "
            "(a Read-less run reads nothing of it)"
        )
    unrecognised = sum(r.get("spill_unrecognised_calls", 0) for r in results["runs"])
    if unrecognised:
        lines.append(
            f"\nWARNING: {unrecognised} tool results look like a result saved to a file (a short answer that names a file) but "
            "do not have the notice bench.py knows; their sizes are the notice's, not the result's. Check the transcripts."
        )
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
    """Decide one pooled rate (previous k1/n1, new k2/n2) against the margin, as one non-inferiority test.

    "no worse": the lower bound of the difference is above minus the margin. "WORSE": the upper bound is below minus
    the margin (the drop is shown to be larger than tolerated). Otherwise "inconclusive". A drop that is real but
    within the margin (the interval wholly below zero, the lower bound above minus the margin) is said as such.
    """
    diff, low, high = newcombe_difference(k1, n1, k2, n2)
    if high < -margin:
        verdict = "WORSE"
    elif low > -margin:
        verdict = "no worse"
    else:
        verdict = "inconclusive"
    note = " (a drop, lower but within the margin)" if verdict == "no worse" and high < 0 else ""
    if verdict == "inconclusive" and high < 0:
        note = " (dropped: the whole interval is below zero but not beyond the margin: likely worse, more runs would decide)"
    text = f"{label} {k1}/{n1} -> {k2}/{n2}: difference {diff:+.1%} (95 % interval {low:+.1%} to {high:+.1%}) -> {verdict}{note}"
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
        ("spilled_calls", "calls whose result was saved to a file (sum)"),
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


def _big_drops(prev_groups: dict[Any, list[dict[str, Any]]], cur_groups: dict[Any, list[dict[str, Any]]], keys: list[Any]) -> list[str]:
    """List the (case, tier) whose own rate of passes, facts or runs without violation fell by 40 points or more."""
    lines = []
    for key in keys:
        a, b = aggregate(prev_groups[key]), aggregate(cur_groups[key])
        if not a["n"] or not b["n"]:
            continue
        for label, field in (("passed", "passed"), ("facts ok", "facts_ok"), ("no violation", "violation_free")):
            if Fraction(b[field], b["n"]) - Fraction(a[field], a["n"]) <= -Fraction(BIG_DROP).limit_denominator(1000):
                lines.append(f"  big drop in {key[0]} [{key[1]}]: {label} {a[field]}/{a['n']} -> {b[field]}/{b['n']}")
    return lines


def _equal_weight(grouped: dict[Any, list[dict[str, Any]]], keys: list[Any], field: str) -> tuple[int, int]:
    """Pool the cases of a tier with the same weight each: the mean of their rates, as counts of the nominal repeats."""
    nominal = max(len(grouped[k]) for k in keys)
    rates = [aggregate(grouped[k])[field] / aggregate(grouped[k])["n"] for k in keys if aggregate(grouped[k])["n"]]
    return round(sum(rates) / len(rates) * nominal * len(rates)), nominal * len(rates)


def compare_with_status(  # noqa: C901, PLR0911, PLR0912, PLR0915
    previous: dict[str, Any],
    current: dict[str, Any],
    margin: float = NON_INFERIORITY_MARGIN,
    *,
    same_server: bool = False,
) -> tuple[str, bool]:
    """Compare two results files, as a non-inferiority claim on the pooled rates of each tier; give the text and whether it refused.

    It refuses when the counting or the conditions differ: the logic version, the defaults, the prompt, the mode, the
    deferral of the tools, two sides that cannot be told apart (the same server version and no differing `label`), or more
    than a few percent invalid runs among the compared ones. It compares only the (case, tier) whose hash is unchanged
    and says how many it left out; a tier whose resolved model ids differ is not compared. Pooled per tier, the passes,
    the facts and the share of runs without a violation are each decided with a Newcombe interval of the difference
    against the margin, and only if every case has the same number of valid runs on both sides (pooling cases with
    different numbers weights them differently on each side, and a collapsed case can vanish in the pool). The per case
    Fisher tests are hints, and a case that fell by 40 points is printed whatever the verdict.
    """
    meta_p, meta_c = previous["meta"], current["meta"]
    out = []
    for key in ("models", "server", "server_version", "reference_version", "claude_version", "cases_file"):
        if meta_p.get(key) != meta_c.get(key):
            out.append(f"differs: {key}: {meta_p.get(key)!r} -> {meta_c.get(key)!r}")
    reasons = []
    for key, what in (
        ("logic", "the logic version of bench.py"),
        ("defaults", "the defaults of the cases file"),
        ("prompt", "the prompt"),
        ("mode", "the mode (headless or subagent)"),
        ("tools_deferred", "whether the tools were deferred"),
    ):
        if meta_p.get(key) != meta_c.get(key):
            reasons.append(f"{what} differs ({meta_p.get(key)!r} -> {meta_c.get(key)!r})")
    if (
        not same_server
        and meta_p.get("server_version") is not None
        and meta_p.get("server_version") == meta_c.get("server_version")
        and meta_p.get("label") == meta_c.get("label")
    ):
        reasons.append(
            f"the two sides cannot be told apart: both are {meta_p.get('server_version')!r} with the label {meta_p.get('label')!r}; "
            "give each side a label (the SHA of the checkout it serves, and whether it was dirty), or pass --same-server to compare two runs of one server"
        )
    prev_groups, cur_groups = groups(previous), groups(current)
    comparable = [k for k in cur_groups if k in prev_groups and meta_p["case_hashes"].get(k[0]) == meta_c["case_hashes"].get(k[0])]
    for label, results, grouped in (("previous", previous, prev_groups), ("current", current, cur_groups)):
        runs = [r for k in comparable for r in grouped[k]]
        share = sum(1 for r in runs if r.get("invalid")) / max(len(runs), 1)
        if share > MAX_INVALID_SHARE:
            reasons.append(f"{share:.0%} of the compared {label} runs are invalid (no server), above {MAX_INVALID_SHARE:.0%}")
    if reasons:
        return "\n".join([*out, *(f"not compared: {reason}" for reason in reasons)]), True
    new_only = sum(1 for k in cur_groups if k not in prev_groups)
    changed = sum(1 for k in cur_groups if k in prev_groups and k not in comparable)
    gone = sum(1 for k in prev_groups if k not in cur_groups)
    out.append(
        f"{len(comparable)} (case, tier) compared; left out: {new_only} only in the current file, {changed} with a changed case, "
        f"{gone} only in the previous file"
    )
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
        uneven = [k for k in keys if aggregate(prev_groups[k])["n"] != aggregate(cur_groups[k])["n"]]
        weighted = bool(uneven) and all(len(prev_groups[k]) == len(cur_groups[k]) for k in uneven)
        if uneven and not weighted:
            shown = ", ".join(
                f"{k[0]} {aggregate(prev_groups[k])['n']} vs {aggregate(cur_groups[k])['n']}" for k in uneven[:3]
            )
            out.append(
                f"POOLED {tier}: INCONCLUSIVE, the number of valid runs per case differs between the files for {len(uneven)} cases "
                f"({shown}); pooling would weight the cases differently on each side. Run the same repeats (`bench.py rerun` fills "
                "them in), or read the cases one by one."
            )
            out.extend(_big_drops(prev_groups, cur_groups, keys))
            continue
        verdicts = []
        out.append(f"POOLED {tier} ({a['n']} runs before, {b['n']} after; margin {margin:.0%}):")
        needs = []
        if weighted:
            short = sum(len(prev_groups[k]) - aggregate(prev_groups[k])["n"] for k in keys) + sum(
                len(cur_groups[k]) - aggregate(cur_groups[k])["n"] for k in keys
            )
            out.append(
                f"  every case is weighted equally by its valid runs, because {short} runs were invalid (within the "
                f"{MAX_INVALID_SHARE:.0%} tolerated); `bench.py rerun` replaces them"
            )
        for label, field in (("passed", "passed"), ("facts ok", "facts_ok"), ("no violation", "violation_free")):
            if weighted:
                (k1, n1), (k2, n2) = (_equal_weight(prev_groups, keys, field), _equal_weight(cur_groups, keys, field))
            else:
                k1, n1, k2, n2 = a[field], a["n"], b[field], b["n"]
            verdict, text = _non_inferiority(label, k1, n1, k2, n2, margin)
            verdicts.append(verdict)
            out.append(f"  {text}")
            needs.append(required_runs(k1 / n1, margin))
        if a["format_runs"] and b["format_runs"]:
            good_a, good_b = a["format_runs"] - a["format_violations"], b["format_runs"] - b["format_violations"]
            verdict, text = _non_inferiority("follows the RESULT format", good_a, a["format_runs"], good_b, b["format_runs"], margin)
            verdicts.append(verdict)
            out.append(f"  {text}")
        overall = "WORSE" if "WORSE" in verdicts else "NO WORSE" if all(v == "no worse" for v in verdicts) else "INCONCLUSIVE"
        out.append(
            f"  => {overall}. Power: to show no worse than {margin:.0%} each of the three rates takes about {needs} runs per side "
            f"(the largest, {max(needs)}, decides, since NO WORSE needs all three); there are {min(a['n'], b['n'])}. Fewer runs make "
            "INCONCLUSIVE the usual answer, which is not 'no worse'."
        )
        out.extend(_big_drops(prev_groups, cur_groups, keys))
        out.extend(_sizes(prev_groups, cur_groups, keys))
    out.extend(f"hint {case} [{tier}]: {_hint(prev_groups[(case, tier)], cur_groups[(case, tier)])}" for case, tier in comparable)
    return "\n".join(out), False


def compare(previous: dict[str, Any], current: dict[str, Any], margin: float = NON_INFERIORITY_MARGIN, *, same_server: bool = False) -> str:
    """Compare two results files and give the text (see `compare_with_status`)."""
    return compare_with_status(previous, current, margin, same_server=same_server)[0]


# -------------------------------------------------------------------------------------------------------- units

_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
    "|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec"
)
#: what is no figure of a value: dates, times, years and station ids, blanked out before the figures are read
_NOT_A_FIGURE = re.compile(
    r"\d{4}-\d{2}-\d{2}|\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}|\d{1,2}:\d{2}|\b(?:19|20)\d{2}\b|\b0\d{4}\b"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\.?\s+(?:{_MONTHS})\b|\b(?:{_MONTHS})\b\.?\s+\d{{1,2}}\b",
    re.IGNORECASE,
)
#: a figure: thousands separators (`14,821.5`, `14 821`, narrow no-break space), a decimal point or comma, an exponent
_NUMBER = r"[-−+]?(?:\d{1,3}(?:[,   ]\d{3})+(?!\d)(?:\.\d+)?|\d+(?:[.,]\d+)?)(?:[eE][-+]?\d+)?"
_FIGURE = re.compile(rf"(?<![\w.]){_NUMBER}")
_BLANKS = "   "
_SENTENCE_END = re.compile(r"[A-Za-z)°%]\s*[.!?]$")
_RESULT_LINE = re.compile(rf"^RESULT:\s*(?P<figure>{_NUMBER})\s*(?P<unit>[^|]*?)\s*\|\s*(?P<what>.+)$", re.IGNORECASE)
_TABLE_UNIT_LINE = re.compile(r"^TABLE-UNIT:\s*(?P<column>[^|]+?)\s*\|\s*(?P<unit>.+?)\s*$", re.IGNORECASE)


def _mask(text: str) -> str:
    """Blank out the dates, times, years and station ids of a text, keeping every offset."""
    return _NOT_A_FIGURE.sub(lambda m: " " * len(m.group(0)), text)


def _number(raw: str) -> tuple[float, int, int]:
    """Read a figure and give its value, the decimals it was written with and its significant digits.

    Reads the Unicode minus, thousands separators (`14,821`, `14 821`), a decimal comma and an exponent.
    """
    text = raw.replace("−", "-")
    mantissa, _, exponent = re.split(r"([eE])", text, maxsplit=1) if re.search(r"[eE]", text) else (text, "", "0")
    mantissa = re.sub(r"(?<=\d)[   ](?=\d{3})", "", mantissa)
    if re.fullmatch(r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", mantissa):
        mantissa = mantissa.replace(",", "")
    mantissa = mantissa.replace(",", ".")
    decimals = len(mantissa.split(".")[1]) if "." in mantissa else 0
    significant = max(len(re.sub(r"\D", "", mantissa).lstrip("0")), 1)
    return float(mantissa) * 10 ** int(exponent), decimals, significant


def _norm_unit(text: str) -> str:
    """Normalise a unit as written in a RESULT line: no brackets or surrounding blanks, one blank, lower case."""
    return re.sub(r"\s+", " ", text.strip().strip("()[]").strip()).casefold()


def _starts_with_unit(tail: str, token: str) -> bool:
    """Tell whether the text after a figure starts with a unit token (a whole word where the token ends in one).

    The unit may stand in brackets, with the word `unit` (`-0.7 (°C)`, `-0.7 (unit °C)`); nothing else may come
    between the figure and the unit.
    """
    text = tail.lstrip(_BLANKS)
    if text[:1] in "([":
        text = text[1:].lstrip(_BLANKS)
        text = re.sub(r"^units?\s*:?\s*", "", text, flags=re.IGNORECASE)
    if not text.lower().startswith(token.lower()):
        return False
    following = text[len(token) : len(token) + 1]
    return not (token[-1].isalnum() and following.isalnum())


def _token_in(text: str, token: str) -> bool:
    """Tell whether a unit token is in a header or a sentence as a word; a one-letter token only in brackets."""
    if len(token) == 1 and token.isalpha():
        return re.search(rf"[(\[]\s*{re.escape(token)}\s*[)\]]", text) is not None
    return re.search(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", text, re.IGNORECASE) is not None


def _bracketed(text: str, token: str) -> bool:
    """Tell whether a unit token stands in brackets in a text: `Mean (°C)`, `Temperature [K]`."""
    return re.search(rf"[(\[]\s*(?:units?\s*:?\s*)?{re.escape(token)}\s*[)\]]", text, re.IGNORECASE) is not None


def _pairs_in(text: str, accepted: list[dict[str, Any]]) -> set[int]:
    """Give the accepted units that have a token in a text (a header cell, the sentences around a table)."""
    return {i for i, pair in enumerate(accepted) if any(_token_in(text, t) for t in pair["tokens"])}


def _pairs_bracketed(text: str, accepted: list[dict[str, Any]]) -> set[int]:
    """Give the accepted units named in brackets in a text."""
    return {i for i, pair in enumerate(accepted) if any(_bracketed(text, t) for t in pair["tokens"])}


def _fitter(fact: dict[str, Any], truth: dict[str, float]) -> Any:  # noqa: ANN401
    """Make the function that says which accepted units a written figure is the value in.

    A figure fits a unit when it equals the value in it (`value * factor + offset`) within the fact's `tolerance` or
    `margin` scaled to the unit, or within the rounding of the figure as written, whichever is wider. A figure with
    fewer than two significant digits gets no rounding: `1` is not 0.8404 as a fraction.
    """
    accepted = fact["accepted"]
    span = "value" not in truth
    low, high = (truth["min"], truth["max"]) if span else (truth["value"], truth["value"])
    slack = fact.get("tolerance", fact.get("margin", 0))

    def fitting(raw: str) -> tuple[float, list[int]]:
        number, decimals, significant = _number(raw)
        rounding = 0.5 * 10**-decimals if significant >= 2 else 0  # noqa: PLR2004
        fits = []
        for i, pair in enumerate(accepted):
            wide = max(slack * abs(pair["factor"]), rounding) + 1e-9
            if low * pair["factor"] + pair.get("offset", 0) - wide <= number <= high * pair["factor"] + pair.get("offset", 0) + wide:
                fits.append(i)
        return number, fits

    return fitting


def _verdict(accepted: list[dict[str, Any]], ok_pairs: set[int], ok_figures: list[str], failures: list[dict[str, str]], **extra: Any) -> dict[str, Any]:  # noqa: ANN401
    """Put the outcome of a check together: it passes with a right figure, no failure and every `required` unit present."""
    missing = [p["tokens"][0] for i, p in enumerate(accepted) if p.get("required") and i not in ok_pairs]
    return {"ok": bool(ok_figures) and not failures and not missing, "ok_figures": ok_figures, "failures": failures, "required_missing": missing, **extra}


def _split_cells(line: str) -> list[str]:
    """Split a table line into its cells: a markdown row on its pipes, a CSV or TSV row on its commas or tabs."""
    stripped = line.strip()
    if "|" in stripped:
        return [c.strip() for c in stripped.strip("|").split("|")]
    return [c.strip() for c in (stripped.split("\t") if "\t" in stripped else stripped.split(","))]


def _is_format_line(line: str) -> bool:
    """Tell whether a line is a RESULT or TABLE-UNIT line of the answer format, which is no row of a table."""
    return line.strip().lstrip("-*\u2022>` ").upper().startswith(("RESULT:", "TABLE-UNIT:"))


def _is_separator_row(line: str) -> bool:
    """Tell whether a line is the separator row of a markdown table (`|---|:---:|`)."""
    cells = _split_cells(line)
    return len(cells) >= 2 and all(re.fullmatch(r":?-{2,}:?", c) for c in cells)  # noqa: PLR2004


def _tables(lines: list[str]) -> list[tuple[int, int, list[list[str]]]]:
    """Find the real tables of an answer; give (first line, last line, rows) with the header as the first row.

    A table is two or more consecutive lines with the same number of cells (separated by pipes, commas or tabs) and
    either a markdown separator row or a first line without a digit (a header). Prose that happens to have the same
    number of commas in two lines, a bullet list with figures, is no table.
    """
    found = []
    i = 0
    while i < len(lines):
        cells = _split_cells(lines[i]) if lines[i].strip() else []
        if len(cells) < 2 or not any(sep in lines[i] for sep in "|,\t") or _is_format_line(lines[i]):  # noqa: PLR2004
            i += 1
            continue
        j = i
        while (
            j + 1 < len(lines)
            and lines[j + 1].strip()
            and not _is_format_line(lines[j + 1])
            and len(_split_cells(lines[j + 1])) == len(cells)
        ):
            j += 1
        block = lines[i : j + 1]
        if j > i and (any(_is_separator_row(line) for line in block) or not re.search(r"\d", block[0])):
            rows = [_split_cells(line) for line in block if not _is_separator_row(line)]
            found.append((i, j, rows))
        i = j + 1
    return found


def _tables_of(answer: str) -> tuple[list[tuple[int, int, list[list[str]]]], str]:
    """Find the tables of an answer and give them with the prose around them (the table lines blanked)."""
    lines = answer.split("\n")
    tables = _tables(lines)
    in_table = {n for first, last, _ in tables for n in range(first, last + 1)}
    return tables, "\n".join("" if n in in_table else line for n, line in enumerate(lines))


def _result_check(answer: str, fact: dict[str, Any], truth: dict[str, float]) -> dict[str, Any] | None:  # noqa: C901, PLR0912, PLR0915
    """Check the `RESULT:` and `TABLE-UNIT:` lines of an answer; None if it has none the format allows.

    `RESULT: <figure> <unit> | <what it is>` gives one value with its unit, `TABLE-UNIT: <column> | <unit>` the unit of
    a column of a table. The unit must be written as one of the fact's `accepted` tokens (any case), nothing is read
    from the prose. A figure that fits the value in an accepted unit passes with that unit's token and fails with
    another accepted unit's, a forbidden one, an unknown one, or none; a second figure for the same thing fails. For a
    forecast every figure written with an accepted unit must lie in the span.
    """
    accepted = fact["accepted"]
    forbidden = {_norm_unit(t) for t in fact.get("forbidden_tokens", [])}
    tokens = [{_norm_unit(t) for t in pair["tokens"]} for pair in accepted]
    span = "value" not in truth
    fitting = _fitter(fact, truth)
    results: list[dict[str, str]] = []
    column_units: list[tuple[str, str]] = []
    malformed = 0
    for raw in answer.split("\n"):
        line = raw.strip().lstrip("-*•>` ").rstrip("` ")
        if line[:7].upper() == "RESULT:":
            match = _RESULT_LINE.match(line)
            if match:
                results.append(match.groupdict())
            else:
                malformed += 1
        elif line[:11].upper() == "TABLE-UNIT:":
            match = _TABLE_UNIT_LINE.match(line)
            if match:
                column_units.append((match["column"], match["unit"]))
            else:
                malformed += 1
    if not results and not column_units:
        return None
    ok_pairs: set[int] = set()
    ok_figures: list[str] = []
    failures: list[dict[str, str]] = []
    format_violation = malformed > 0
    seen: dict[str, str] = {}
    for item in results:
        figure, unit, what = item["figure"], _norm_unit(item["unit"]), re.sub(r"\s+", " ", item["what"]).strip().casefold()
        number, fits = fitting(figure)
        known = {i for i, t in enumerate(tokens) if unit in t}
        if what in seen and seen[what] != figure:
            failures.append({"figure": figure, "reason": f"a second figure for the same thing ({seen[what]} and {figure})"})
        seen.setdefault(what, figure)
        if not unit:
            format_violation = True
            if fits:
                failures.append({"figure": figure, "reason": "no unit in the RESULT line"})
            continue
        if not fits:
            if span and known:
                failures.append({"figure": figure, "reason": "a figure with a unit that lies outside the span"})
            continue
        if unit in forbidden:
            failures.append({"figure": figure, "reason": f"written with the forbidden unit {item['unit'].strip()!r}"})
        elif known & set(fits):
            ok_pairs |= known & set(fits)
            ok_figures.append(figure)
        elif known:
            if 0 in fits:  # a figure that fits another unit than the first may be another quantity (`1.6 mm`, 1.55 cm)
                failures.append({"figure": figure, "reason": "its unit is not the unit its number is in"})
        else:
            failures.append({"figure": figure, "reason": f"the unit {item['unit'].strip()!r} is not one the case knows"})
    if "column" in fact:
        tables, _ = _tables_of(answer)
        cells = [
            cell
            for _, _, rows in tables
            for row_cells in rows[1:]
            for cell in row_cells
            if _FIGURE.fullmatch(_mask(cell).strip())
        ]
        wanted = [(c, u) for c, u in column_units if re.search(fact["column"], c, re.IGNORECASE)]
        if not wanted and not ok_figures:
            failures.append({"figure": "", "reason": "no TABLE-UNIT line for the column"})
            format_violation = True
        for column, unit in wanted:
            unit_n = _norm_unit(unit)
            known = {i for i, t in enumerate(tokens) if unit_n in t}
            if unit_n in forbidden:
                failures.append({"figure": column, "reason": f"the column is declared in the forbidden unit {unit!r}"})
            elif not known:
                failures.append({"figure": column, "reason": f"the unit {unit!r} of the column is not one the case knows"})
            else:
                hit = next((cell for cell in cells if known & set(fitting(cell)[1])), None)
                if hit is None:
                    failures.append({"figure": column, "reason": "no cell of a table equals the value in the unit declared for the column"})
                else:
                    ok_pairs |= known
                    ok_figures.append(hit)
    return _verdict(accepted, ok_pairs, ok_figures, failures, mode="result", format_violation=format_violation)


def _fallback_check(answer: str, fact: dict[str, Any], truth: dict[str, float]) -> dict[str, Any]:  # noqa: C901, PLR0912, PLR0915
    """Check the figure of a value and its unit in free text and tables, for an answer with no RESULT lines.

    A figure of the answer is a *candidate* when it fits the value in an accepted unit. In prose the unit must follow
    the figure directly (after blanks, in brackets, or as `(unit °C)`), or stand in brackets before it on its line
    (`Mean (°C): -0.7`) or alone on the line above (`Temperature [°C]`). A candidate fails when a unit follows that is a
    `forbidden_tokens` one or one of another accepted unit than the one its number fits, if the number fits the first
    accepted unit (`0.84 %` fits the fraction, not the percent; `1.6 mm` fits 15.5 mm as centimetres and is another
    quantity); a candidate with no unit neither passes nor fails. For a forecast every figure with an accepted
    unit must fit the span, in prose and in tables.

    A real table (see `_tables`) is read by column: the value column is the first column with a cell that fits the first
    accepted unit in which any cell fits; the unit is in the cell, its header, a unit column (`| Unit |`), the label cells
    of its row (`| Mean (°C) | -0.7 |`) or a sentence outside the table that names it.
    """
    accepted = fact["accepted"]
    forbidden = fact.get("forbidden_tokens", [])
    span = "value" not in truth
    fitting = _fitter(fact, truth)
    ok_pairs: set[int] = set()
    ok_figures: list[str] = []
    failures: list[dict[str, str]] = []
    tables, prose = _tables_of(answer)
    masked = _mask(prose)
    prose_lines = prose.split("\n")

    def units_after(tail: str) -> set[int]:
        return {i for i, p in enumerate(accepted) if any(_starts_with_unit(tail, t) for t in p["tokens"])}

    for found in _FIGURE.finditer(masked):
        raw = found.group(0)
        _, fits = fitting(raw)
        tail = prose[found.end() : found.end() + 40].split("\n")[0]
        present = units_after(tail)
        banned = [t for t in forbidden if _starts_with_unit(tail, t)]
        if not present and not banned:
            row_start = prose.rfind("\n", 0, found.start()) + 1
            before = prose[row_start : found.start()]
            above = ""
            line_no = prose[: found.start()].count("\n")
            if line_no > 0 and prose_lines[line_no - 1].strip() and not re.search(r"\d", prose_lines[line_no - 1]):
                above = prose_lines[line_no - 1]
            present = _pairs_bracketed(before, accepted) | _pairs_bracketed(above, accepted)
            banned = [t for t in forbidden if _bracketed(before, t) or _bracketed(above, t)]
        if not fits:
            if span and present:
                failures.append({"figure": raw, "reason": "a figure with a unit that lies outside the span"})
            continue
        if banned:
            failures.append({"figure": raw, "reason": f"followed by the forbidden unit {banned[0]!r}"})
        elif present & set(fits):
            ok_pairs |= present & set(fits)
            ok_figures.append(raw)
        elif present and 0 in fits:
            failures.append({"figure": raw, "reason": "its unit is not the unit its number is in"})
    around = _pairs_in(prose, accepted)
    for _, _, rows in tables:
        header, body = rows[0], rows[1:]
        unit_column = next((i for i, h in enumerate(header) if re.fullmatch(r"units?", h.strip(), re.IGNORECASE)), None)
        for column in range(len(header)):
            if column == unit_column:
                continue
            entries = []
            for row in body:
                if column >= len(row):
                    continue
                cell = _mask(row[column])
                match = _FIGURE.search(cell)
                if not match:
                    continue
                labels = " ".join(c for k, c in enumerate(row) if k != column and not _FIGURE.search(_mask(c)))
                unit_cell = row[unit_column] if unit_column is not None and unit_column < len(row) else ""
                present = {i for i, p in enumerate(accepted) if any(_starts_with_unit(cell[match.end() :], t) or _starts_with_unit(unit_cell, t) for t in p["tokens"])}
                present |= _pairs_in(header[column], accepted) | _pairs_in(labels, accepted)
                banned = [t for t in forbidden if _token_in(header[column], t) or _token_in(labels, t) or _starts_with_unit(cell[match.end() :], t) or _starts_with_unit(unit_cell, t)]
                entries.append((match.group(0), fitting(match.group(0))[1], present, banned))
            if span:
                for raw, fits, present, banned in entries:
                    if fits and banned:
                        failures.append({"figure": raw, "reason": f"in a table with the forbidden unit {banned[0]!r}"})
                    elif fits and present & set(fits):
                        ok_pairs |= present & set(fits)
                        ok_figures.append(raw)
                    elif not fits and present:
                        failures.append({"figure": raw, "reason": "a figure with a unit that lies outside the span"})
                    elif fits and present:
                        failures.append({"figure": raw, "reason": "the unit of its column is not the unit its number is in"})
                continue
            pair = next((i for i in range(len(accepted)) if any(i in fits for _, fits, _, _ in entries)), None)
            if pair is None:
                continue
            for raw, fits, present, banned in entries:
                if pair not in fits:
                    continue
                present = present or around
                if banned:
                    failures.append({"figure": raw, "reason": f"in a column with the forbidden unit {banned[0]!r}"})
                elif pair in present:
                    ok_pairs.add(pair)
                    ok_figures.append(raw)
                elif present and 0 in fits:
                    failures.append({"figure": raw, "reason": "the unit of its column is not the unit its number is in"})
    return _verdict(accepted, ok_pairs, ok_figures, failures, mode="fallback", format_violation=True, unit_fallback=True)


def unit_check(answer: str, fact: dict[str, Any], truth: dict[str, float]) -> dict[str, Any]:
    """Check an answer's value and its unit against the judge's own reading of the value.

    The prompt asks for `RESULT:` lines (and `TABLE-UNIT:` lines for a table), which are read strictly and alone
    (`_result_check`). An answer without them is read tolerantly (`_fallback_check`) and reported as
    `format_violation` and `unit_fallback`: the model's following of the format is a metric of its own, not a pass.
    `truth` is `{"value": v}` or, for a forecast, `{"min": a, "max": b}`.
    """
    strict = _result_check(answer, fact, truth)
    return strict if strict is not None else _fallback_check(answer, fact, truth)


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


def _run_prefix() -> str:
    """Give the start of the project directory names of this benchmark's headless runs: the slug of the temp dir."""
    return f"{_slug(tempfile.gettempdir())}-mcpbench-subject-"


def _remove_project_dir(name: str, *, min_age: float = 0) -> bool:
    """Remove the project directory of Claude Code that one headless run of this benchmark left, if it is that.

    The name must be the slug of a directory the run made in the temp dir (anchored, not merely containing the word),
    the entry must be a real directory (a symlink is never followed or counted), and with `min_age` seconds it must be
    older than that, since a younger one may belong to a run in progress. Give whether it was removed.
    """
    root = Path.home() / ".claude" / "projects"
    target = root / name
    if not name.startswith(_run_prefix()) or "/" in name or target.is_symlink() or not target.is_dir():
        return False
    if min_age and time.time() - target.stat().st_mtime < min_age:
        return False
    shutil.rmtree(target, ignore_errors=True)
    return not target.exists()


def cleanup(min_age: float = CLEANUP_MIN_AGE) -> int:
    """Remove the project directories that headless runs of this benchmark left, if they are older than `min_age` seconds."""
    root = Path.home() / ".claude" / "projects"
    names = [p.name for p in root.iterdir()] if root.is_dir() else []
    return sum(_remove_project_dir(n, min_age=min_age) for n in names)


def _claude_version(claude: str) -> str | None:
    """Ask `claude --version` for its version, or None."""
    try:
        done = subprocess.run([claude, "--version"], capture_output=True, text=True, timeout=20, check=False)  # noqa: S603
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() or None


def failed_run(case: dict[str, Any], tier: str, repeat: int, reason: str, *, invalid: bool = True) -> dict[str, Any]:
    """Make the record of a run that did not give an answer: invalid (no server) or failed (a timeout), with the reason.

    A server that does not answer or lists no tool says nothing about the model, so the run is `invalid`. A run that
    timed out says something about it (a strategy that makes the model slower must show as a failure): it is a failed run.
    """
    return {
        "case": case["id"],
        "tier": tier,
        "repeat": repeat,
        "invalid": invalid,
        "invalid_reason": reason if invalid else None,
        "failure": None if invalid else reason,
        "passed": False,
        "facts_ok": False,
        "is_answer": False,
        "checkpoints": {"k": 0, "n": len(case["checkpoints"]), "met": [], "first_missed": case["checkpoints"][0]["id"]},
        "violations": [],
        "steps": 0,
        "max_steps": case["max_steps"],
        "tool_result_chars_sum": 0,
        "tool_result_chars_max": 0,
        "output_tokens": 0,
        "context_tokens_first": None,
        "total_tokens": 0,
        "calls": [],
    }


def _analysis_record(case: dict[str, Any], tier: str, repeat: int, transcript: Path, defaults: dict[str, Any]) -> dict[str, Any]:
    """Analyse a transcript into a results record that still needs the judge: failed until it has judged it."""
    run = parse_transcript(transcript, "mcp__wetterdienst__")
    verdict = evaluate(case, run, defaults)
    sidecar = Path(f"{transcript}.meta.json")
    calls = [{k: v for k, v in c.items() if k != "result_head"} for c in run["calls"]]
    return {
        **run,
        **verdict,
        "calls": calls,
        "case": case["id"],
        "tier": tier,
        "repeat": repeat,
        "is_answer": False,
        "passed": False,
        "facts_ok": False,
        "needs_judging": True,
        "run_meta": json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.is_file() else None,
    }


def rerun_targets(results: dict[str, Any], case: str | None = None, tier: str | None = None) -> list[tuple[str, str, int]]:
    """List the (case, tier, repeat) a results file lacks: the invalid runs, and the repeats it has fewer of than `repeats`."""
    wanted = int(results["meta"].get("repeats") or 0)
    found = []
    for (name, level), runs in groups(results).items():
        if (case and name != case) or (tier and level != tier):
            continue
        have = {r.get("repeat") for r in runs if not r.get("invalid")}
        found.extend((name, level, n) for n in range(1, max(wanted, len(runs)) + 1) if n not in have)
    return sorted(found)


def rerun(results_path: Path, out_dir: Path, case: str | None, tier: str | None, *, dry_run: bool = False) -> int:  # noqa: C901
    """Re-run the invalid runs and the missing repeats of a headless results file, and put them in it for the judge.

    The prompt is rendered again from the case and the date of the file, the model and the server come from its `meta`.
    A record that replaces an invalid one carries `needs_judging` and counts as failed until the judge has set
    `is_answer`, `facts_ok` and `passed` and removed the flag.
    """
    results = json.loads(results_path.read_text(encoding="utf-8"))
    meta = results["meta"]
    data = load_cases()
    targets = rerun_targets(results, case, tier)
    for line in targets:
        sys.stdout.write(f"{line[0]} [{line[1]}] repeat {line[2]}\n")
    if dry_run or not targets:
        return 0
    if meta.get("mode") != "headless" or not str(meta.get("server", "")).startswith("http"):
        sys.stderr.write("rerun: only a headless results file (a `server` URL in its meta) can be filled in this way\n")
        return 2
    if hashes(data)["cases"].get(targets[0][0]) != meta["case_hashes"].get(targets[0][0]) or prompt_version() != meta.get("prompt"):
        sys.stderr.write("rerun: the cases or the prompt changed since the file was written: a re-run would not be the same run\n")
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    replaced = 0
    for name, level, number in targets:
        the_case = find_case(data, name)
        prompt_file = out_dir / f"{name}-{level}-{number}.prompt"
        prompt_file.write_text(render_prompt(the_case, meta["date"], "the wetterdienst tools"), encoding="utf-8")
        transcript = out_dir / f"{name}-{level}-{number}.jsonl"
        model = (meta.get("models") or {}).get(level, level)
        code = run_subject(model, meta["server"], "wetterdienst", str(prompt_file), str(transcript), 300, 0.5, meta.get("label"))
        if code in {2, 3}:
            sys.stderr.write(f"rerun: {name} [{level}] repeat {number} did not run (exit {code}); the file is left as it is\n")
            continue
        record = _analysis_record(the_case, level, number, transcript, data.get("defaults", {}))
        if code == 124:
            record = {**record, "failure": "timeout"}
        results["runs"] = [
            r for r in results["runs"] if (r["case"], r["tier"], r.get("repeat")) != (name, level, number)
        ] + [record]
        replaced += 1
    results_path.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    sys.stdout.write(f"{replaced} runs re-run; they need judging (`needs_judging`)\n")
    return 0


def run_subject(  # noqa: PLR0913
    model: str, url: str, name: str, prompt_file: str, out: str, timeout: float, max_usd: float, label: str | None = None
) -> int:
    """Run one tested agent headless, outside the repository, with only the server under test; write its stream-json.

    Exit codes: 0 the run ended, 2 a bad argument or no `claude`, 3 the server did not answer, 124 the timeout, other
    the exit code of `claude`.
    """
    if not re.fullmatch(r"[A-Za-z0-9._\-\[\]]{1,60}", model) or not SAFE_NAME.match(name) or not SAFE_URL.match(url):
        sys.stderr.write("run: the model, the server name or the URL has characters this script does not pass on\n")
        return 2
    if not 0 < timeout <= MAX_TIMEOUT:
        sys.stderr.write(
            f"run: the timeout must be 1 to {MAX_TIMEOUT} s: `cleanup` takes a directory older than {CLEANUP_MIN_AGE} s "
            "for a finished run, and appending to a file does not move its mtime\n"
        )
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
        probed = probe(url)
    except (OSError, ValueError, RuntimeError) as error:
        sys.stderr.write(f"run: the MCP server at {url} does not answer: {error}\n")
        return 3
    if label is not None and not SAFE_LABEL.match(label):
        sys.stderr.write("run: the label may only hold letters, digits and . _ + - (the SHA of the checkout, +dirty)\n")
        return 2
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
    side = {"mode": "headless", "label": label, "model_requested": model, "claude_version": _claude_version(claude), **probed}
    Path(f"{out_path}.meta.json").write_text(json.dumps(side, indent=1), encoding="utf-8")
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
    p_probe.add_argument("--label")
    p_rerun = sub.add_parser("rerun")
    p_rerun.add_argument("--results", type=Path, required=True)
    p_rerun.add_argument("--out-dir", type=Path, required=True)
    p_rerun.add_argument("--case")
    p_rerun.add_argument("--tier")
    p_rerun.add_argument("--dry-run", action="store_true")
    p_failed = sub.add_parser("failed-run")
    p_failed.add_argument("--case", required=True)
    p_failed.add_argument("--tier", required=True)
    p_failed.add_argument("--repeat", type=int, default=1)
    p_failed.add_argument("--reason", required=True)
    p_failed.add_argument("--kind", choices=("invalid", "failed"), default="invalid", help="`failed` for a timeout (exit 124)")
    p_failed.add_argument("--cases", type=Path, default=CASES_PATH)
    p_size = sub.add_parser("tools-size")
    p_size.add_argument("--server", default=HOSTED_MCP_URL)
    sub.add_parser("cleanup")
    p_run = sub.add_parser("run")
    for arg in ("model", "url", "name", "prompt", "out"):
        p_run.add_argument(arg)
    p_run.add_argument("--timeout", type=float, default=float(os.environ.get("MCPBENCH_TIMEOUT", "300")))
    p_run.add_argument("--max-usd", type=float, default=float(os.environ.get("MCPBENCH_MAX_USD", "0.50")))
    p_run.add_argument("--label", help="what tells this side apart when two servers report one version: the SHA of the checkout")
    p_unit = sub.add_parser("unit")
    p_unit.add_argument("--case", required=True)
    p_unit.add_argument("--fact", required=True)
    p_unit.add_argument("--truth", type=float, nargs="+", required=True, help="the value, or the min and max of a span")
    p_unit.add_argument("--answer", required=True)
    for name in ("report", "compare"):
        p = sub.add_parser(name)
        p.add_argument("files", nargs="+", type=Path)
        if name == "compare":
            p.add_argument("--margin", type=float, default=NON_INFERIORITY_MARGIN)
            p.add_argument("--same-server", action="store_true", help="compare two runs of one server (no label needed)")
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
        sidecar = Path(f"{args.transcript}.meta.json")
        side = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.is_file() else None
        print(json.dumps({"case": case["id"], **run, **verdict, "run_meta": side}, indent=1, ensure_ascii=False))
    elif args.command == "probe":
        try:
            print(json.dumps({**probe(args.url), "label": args.label}, indent=1))
        except (OSError, ValueError, RuntimeError) as error:
            sys.stderr.write(f"probe: {args.url} does not answer: {error}\n")
            return 3
    elif args.command == "tools-size":
        print(tools_size(args.server))
    elif args.command == "cleanup":
        print(f"removed {cleanup()} project directories of benchmark runs")
    elif args.command == "run":
        return run_subject(args.model, args.url, args.name, args.prompt, args.out, args.timeout, args.max_usd, args.label)
    elif args.command == "rerun":
        return rerun(args.results, args.out_dir, args.case, args.tier, dry_run=args.dry_run)
    elif args.command == "failed-run":
        case = find_case(load_cases(args.cases), args.case)
        print(json.dumps(failed_run(case, args.tier, args.repeat, args.reason, invalid=args.kind == "invalid"), indent=1))
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
        text, refused = compare_with_status(
            *(json.loads(f.read_text(encoding="utf-8")) for f in args.files[:2]), args.margin, same_server=args.same_server
        )
        print(text)
        return 4 if refused else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
