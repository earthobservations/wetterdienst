# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The cases of the manual MCP benchmark stay true to the code (GH-3538).

`.claude/skills/mcp-benchmark/cases.json` holds the questions a person has a model answer with the MCP tools,
by hand inside Claude (`/mcp-benchmark`). Nothing here calls a model or the network: this test only holds the
cases to the code they were written against, so that a renamed tool, argument, provider or parameter fails here
and not silently in the next manual run, where a checkpoint would simply never be met.

Checked: the shape of the file, ids and limits, every tool and argument a checkpoint, a forbidden call or a
ground-truth call names (and the enum values among them), every provider, network and parameter that is a
literal, that the regexes compile, that `needs_key` is true exactly for the cases of a network that needs
credentials, and that nothing that looks like a credential or personal data is in the cases or the skill.
"""

from __future__ import annotations

import asyncio
import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastmcp")

from fastmcp import Client

from wetterdienst import Wetterdienst
from wetterdienst.model.metadata import parse_parameters
from wetterdienst.ui import restapi
from wetterdienst.ui.mcp import build_mcp_server

SKILL_DIR = Path(__file__).parents[2] / ".claude" / "skills" / "mcp-benchmark"
CASES_FILE = SKILL_DIR / "cases.json"

KINDS = {
    "forecast",
    "observation",
    "discovery",
    "glossary",
    "licence",
    "interpolate",
    "summarize",
    "alerts",
    "stripes",
    "history",
    "coverage",
    "unanswerable",
}
TIERS = {"small", "large"}
FACT_KINDS = {
    "answer_regex",
    "ground_truth_value",
    "ground_truth_span",
    "ground_truth_text",
    "ground_truth_subset",
    "no_measurements",
}
FORBIDDEN_KINDS = {"call", "repeat", "answer"}
RULE_KEYS = {"any_of", "regex", "between", "present", "absent"}
CASE_KEYS = {
    "id",
    "question",
    "kind",
    "max_steps",
    "checkpoints",
    "forbidden",
    "facts",
    "tiers",
    "needs_key",
    "notes",
}
#: arguments that carry the name of a provider, a network or parameters, which are checked against the code
CODE_ARGS = ("provider", "network", "parameters")
MAX_STEPS_LIMIT = 12

SECRET_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|bearer|authorization)\b\s*[:=]\s*[\"']?[\w.\-]{8,}"),
    re.compile(r"\beyJ[\w-]{10,}\.[\w-]{10,}"),
    re.compile(r"\b(sk|pk|ghp|gho|xox[bap])[-_][A-Za-z0-9_-]{16,}"),
    re.compile(r"\b[0-9a-fA-F]{32,}\b"),
    re.compile(r"(?i)\b(access|auth)[_-]?token\b\s*[:=]\s*[\"']?[\w.\-]{8,}"),
)
PERSONAL_PATTERNS = (
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    re.compile(r"(?<!\d)\+?\d{2,3}[ -]?\(?\d{2,5}\)?[ -]\d{3,}[ -]?\d{2,}(?!\d)"),
    re.compile(r"\b[A-Z]{2}\d{2}(?: ?\d{4}){3,}\b"),
)


def load_cases() -> dict[str, Any]:
    """Read the file the skill reads."""
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))


def _schema(tool: Any) -> dict[str, Any]:  # noqa: ANN401
    """Tell a listed tool's input schema, by the attribute newer MCP SDKs have or the one older ones have."""
    schema = getattr(tool, "input_schema", None)
    return schema if schema is not None else tool.inputSchema


@pytest.fixture(scope="module")
def tools() -> dict[str, dict[str, Any]]:
    """Give the input schema of every tool the server lists, by tool name."""

    async def listed() -> dict[str, dict[str, Any]]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return {tool.name: _schema(tool) for tool in await client.list_tools()}

    return asyncio.run(listed())


def _enums(schema: dict[str, Any]) -> set[str] | None:
    """Collect the values an argument's schema allows, or None where it is no enumeration."""
    found: set[str] = set()

    def walk(node: Any) -> None:  # noqa: ANN401
        if isinstance(node, dict):
            if "enum" in node:
                found.update(str(value) for value in node["enum"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    return found or None


def _literals(rule: Any) -> list[Any]:  # noqa: ANN401
    """Tell the literal values an argument rule names: a literal, or the members of `any_of`; a regex names none."""
    if isinstance(rule, dict):
        return list(rule["any_of"]) if "any_of" in rule else []
    return [rule]


def _regexes(node: Any) -> list[str]:  # noqa: ANN401
    """Collect every regex in a structure: the `regex` of a rule, a fact's `any_of` and `answer_matches_any_of`."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "regex" and isinstance(value, str):
                found.append(value)
            elif key == "answer_matches_any_of" or (key == "any_of" and node.get("kind") == "answer_regex"):
                found.extend(value)
            else:
                found.extend(_regexes(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_regexes(value))
    return found


def _calls(case: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Collect every call the case names, as (where, match): the checkpoints, the forbidden calls, the ground truths."""
    calls = []
    for checkpoint in case.get("checkpoints", []):
        calls.extend((f"checkpoint {checkpoint.get('id')}", match) for match in checkpoint.get("match", []))
    calls.extend(
        (f"forbidden {item.get('id')}", item["match"])
        for item in case.get("forbidden", [])
        if item.get("kind") == "call" and "match" in item
    )
    for fact in case.get("facts", []):
        call = fact.get("ground_truth", {}).get("call")
        if call is not None:
            calls.append((f"fact {fact.get('id')}", {"tool": call.get("tool"), "args": call.get("args", {})}))
    return calls


def _check_match(
    where: str,
    match: dict[str, Any],
    tools: dict[str, dict[str, Any]],
    *,
    ground_truth: bool,
) -> list[str]:
    """Hold one call to the tools: its tool names, its argument names and the enum values among its arguments."""
    found = []
    names = match.get("tool")
    names = [names] if isinstance(names, str) else names
    if not names:
        return [f"{where}: no tool named"]
    unknown = [name for name in names if name not in tools]
    if unknown:
        return [f"{where}: no such tool {unknown} (the server has {sorted(tools)})"]
    for name in names:
        properties = tools[name].get("properties", {})
        for argument, rule in match.get("args", {}).items():
            if argument not in properties:
                found.append(f"{where}: {name} takes no argument {argument!r} (it takes {sorted(properties)})")
                continue
            if not ground_truth and isinstance(rule, dict) and not set(rule) <= RULE_KEYS:
                found.append(f"{where}: {argument} has the unknown rule keys {sorted(set(rule) - RULE_KEYS)}")
            allowed = _enums(properties[argument])
            if allowed is None:
                continue
            found.extend(
                f"{where}: {name}.{argument} takes none of {value!r} (it takes {sorted(allowed)})"
                for value in _flat(_literals(rule))
                if isinstance(value, str) and not value.startswith("$") and value not in allowed
            )
    return found


def _flat(values: list[Any]) -> list[Any]:
    """Flatten a list of literals one level, as an argument given as a list names several."""
    return [item for value in values for item in (value if isinstance(value, list) else [value])]


def _pairs(args: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Tell the provider and the network literals a call names."""
    providers = [v for v in _flat(_literals(args.get("provider", []))) if isinstance(v, str)]
    networks = [v for v in _flat(_literals(args.get("network", []))) if isinstance(v, str)]
    return providers, networks


def _check_code(where: str, args: dict[str, Any]) -> list[str]:
    """Hold the provider, network and parameter literals of a call to the registry and the metadata."""
    found = []
    providers, networks = _pairs(args)
    registry = Wetterdienst.registry
    found.extend(
        f"{where}: no provider {p!r} (the registry has {sorted(registry)})" for p in providers if p not in registry
    )
    known = [p for p in providers if p in registry]
    for network in networks:
        if known and not any(network in registry[p] for p in known):
            found.append(f"{where}: none of {known} has the network {network!r}")
    if len(providers) == 1 and len(networks) == 1 and not found:
        provider, network = providers[0], networks[0]
        if network not in registry[provider]:
            return [f"{where}: {provider} has no network {network!r} (it has {sorted(registry[provider])})"]
        if (provider, network) in Wetterdienst.standalone:
            return found
        metadata = Wetterdienst.resolve(provider, network).metadata
        for parameter in _flat(_literals(args.get("parameters", []))):
            if not isinstance(parameter, str) or parameter.startswith("$"):
                continue
            try:
                parse_parameters(parameter, metadata)
            except Exception as error:  # noqa: BLE001 - whatever the parser refuses is the finding
                found.append(f"{where}: {provider}/{network} has no parameter {parameter!r}: {error}")
    elif args.get("parameters") and any(isinstance(v, str) for v in _flat(_literals(args["parameters"]))):
        # parameters are only checkable against one provider and network; a call that names several says nothing
        pass
    return found


def _check_rules(where: str, args: dict[str, Any]) -> list[str]:
    """Hold a call's `between` rules to being a pair of numbers in order."""
    found = []
    for argument, rule in args.items():
        if isinstance(rule, dict) and "between" in rule:
            bounds = rule["between"]
            if not (isinstance(bounds, list) and len(bounds) == 2 and bounds[0] < bounds[1]):
                found.append(f"{where}: {argument} has the bounds {bounds!r}, not [low, high]")
    return found


def _auth_networks() -> set[tuple[str, str]]:
    """Tell the (provider, network) pairs that need credentials."""
    return {
        (provider, network)
        for provider, networks in Wetterdienst.discover().items()
        for network, info in networks.items()
        if info.get("auth")
    }


def _check_case(case: dict[str, Any], tools: dict[str, dict[str, Any]], auth: set[tuple[str, str]]) -> list[str]:  # noqa: C901
    """List what is wrong with one case, as one line each."""
    cid = case.get("id", "<no id>")
    found = []
    missing = CASE_KEYS - set(case)
    if missing:
        found.append(f"{cid}: missing {sorted(missing)}")
    extra = set(case) - CASE_KEYS
    if extra:
        found.append(f"{cid}: unknown fields {sorted(extra)}")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(cid)):
        found.append(f"{cid}: the id is not kebab-case")
    if case.get("kind") not in KINDS:
        found.append(f"{cid}: kind {case.get('kind')!r} is none of {sorted(KINDS)}")
    steps = case.get("max_steps")
    if not isinstance(steps, int) or isinstance(steps, bool) or not 1 <= steps <= MAX_STEPS_LIMIT:
        found.append(f"{cid}: max_steps {steps!r} is not a positive integer up to {MAX_STEPS_LIMIT}")
    if not str(case.get("question", "")).strip().endswith(("?", ".")):
        found.append(f"{cid}: the question is empty or not a sentence")
    if not case.get("checkpoints"):
        found.append(f"{cid}: no checkpoint")
    if not case.get("facts"):
        found.append(f"{cid}: no fact rule")
    if not isinstance(case.get("needs_key"), bool):
        found.append(f"{cid}: needs_key is no boolean")
    tiers = case.get("tiers")
    if not isinstance(tiers, list) or not set(tiers) <= TIERS:
        found.append(f"{cid}: tiers {tiers!r} is not a list of {sorted(TIERS)}")
    if not str(case.get("notes", "")).strip():
        found.append(f"{cid}: no notes")
    ids = [c.get("id") for c in case.get("checkpoints", [])]
    if len(set(ids)) != len(ids):
        found.append(f"{cid}: checkpoint ids repeat")
    for checkpoint in case.get("checkpoints", []):
        if not checkpoint.get("match") or not isinstance(checkpoint["match"], list):
            found.append(f"{cid}: checkpoint {checkpoint.get('id')} has no list of alternatives in `match`")
    for item in case.get("forbidden", []):
        if item.get("kind") not in FORBIDDEN_KINDS:
            found.append(f"{cid}: forbidden {item.get('id')} has the kind {item.get('kind')!r}")
    for fact in case.get("facts", []):
        if fact.get("kind") not in FACT_KINDS:
            found.append(f"{cid}: fact {fact.get('id')} has the kind {fact.get('kind')!r}")
        elif fact["kind"].startswith("ground_truth") and "call" not in fact.get("ground_truth", {}):
            found.append(f"{cid}: fact {fact.get('id')} has no ground_truth call")
    for where, match in _calls(case):
        full = f"{cid}: {where}"
        ground_truth = where.startswith("fact")
        found.extend(_check_match(full, match, tools, ground_truth=ground_truth))
        found.extend(_check_code(full, match.get("args", {})))
        found.extend(_check_rules(full, match.get("args", {})))
    for pattern in _regexes(case):
        try:
            re.compile(pattern)
        except re.error as error:
            found.append(f"{cid}: the regex {pattern!r} does not compile: {error}")
    found.extend(_check_key(case, auth))
    return found


def _check_key(case: dict[str, Any], auth: set[tuple[str, str]]) -> list[str]:
    """Hold `needs_key` to the networks the case's calls name: true exactly when one of them needs credentials."""
    named: set[tuple[str, str]] = set()
    for _, match in _calls(case):
        providers, networks = _pairs(match.get("args", {}))
        named.update((p, n) for p in providers for n in networks)
    needs = bool(named & auth)
    if bool(case.get("needs_key")) != needs:
        say = sorted(named & auth)
        return [
            f"{case.get('id')}: needs_key is {case.get('needs_key')!r}, but the networks it names {say} say {needs}"
        ]
    return []


def problems(data: dict[str, Any], tools: dict[str, dict[str, Any]], text: str | None = None) -> list[str]:
    """List everything wrong with the cases file, as one line each, so that one assert shows all of it."""
    found = []
    if data.get("schema_version") != 1:
        found.append(f"schema_version is {data.get('schema_version')!r}, not 1")
    if set(data.get("tiers", {})) != TIERS or not all(isinstance(m, str) for m in data.get("tiers", {}).values()):
        found.append("`tiers` does not map small and large to a model")
    cases = data.get("cases", [])
    ids = [case.get("id") for case in cases]
    found.extend(f"id {cid!r} is used {ids.count(cid)} times" for cid in sorted({i for i in ids if ids.count(i) > 1}))
    auth = _auth_networks()
    for case in cases:
        found.extend(_check_case(case, tools, auth))
    haystack = text if text is not None else json.dumps(data, ensure_ascii=False)
    found.extend(f"looks like a credential: {m.group(0)[:40]!r}" for p in SECRET_PATTERNS for m in p.finditer(haystack))
    found.extend(
        f"looks like personal data: {m.group(0)[:40]!r}" for p in PERSONAL_PATTERNS for m in p.finditer(haystack)
    )
    return found


def test_the_cases_are_true_to_the_code(tools: dict[str, dict[str, Any]]) -> None:
    """Every tool, argument, provider, network and parameter the cases name exists, and the file is well formed."""
    assert problems(load_cases(), tools) == []


def test_there_are_enough_cases_and_they_cover_the_tools(tools: dict[str, dict[str, Any]]) -> None:
    """The set asks about the main tools: a tool nobody asks about is a tool no run tests."""
    data = load_cases()
    named = {
        name
        for case in data["cases"]
        for _, m in _calls(case)
        for name in ([m["tool"]] if isinstance(m["tool"], str) else m["tool"])
    }

    assert len(data["cases"]) >= 16
    assert named >= {
        "stations",
        "values",
        "interpolate",
        "summarize",
        "alerts",
        "stripes_values",
        "history",
        "coverage",
        "glossary",
        "providers",
    }
    assert all(name in tools for name in named)
    assert any(case["needs_key"] for case in data["cases"]), "the skipped-by-default case is gone"


def test_the_skill_and_the_cases_hold_no_credential_or_personal_data() -> None:
    """The text of the skill and of the cases has nothing that looks like a secret or a person's data."""
    text = CASES_FILE.read_text(encoding="utf-8") + (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    assert [m.group(0) for p in (*SECRET_PATTERNS, *PERSONAL_PATTERNS) for m in p.finditer(text)] == []


def test_the_skill_is_manual_only() -> None:
    """The skill header keeps the model from starting a run on its own, which costs tokens and calls providers."""
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    header = text.split("---")[1]

    assert re.search(r"(?m)^name: mcp-benchmark$", header)
    assert re.search(r"(?m)^disable-model-invocation: true$", header)
    assert "Costs tokens" in header
    assert "never by CI" in header


def _mutated(data: dict[str, Any], old: str, new: str) -> dict[str, Any]:
    """Return the cases with every occurrence of a string replaced, as a stale name would look."""
    text = json.dumps(data, ensure_ascii=False)
    assert old in text, f"{old!r} is not in the cases, so this mutation tests nothing"
    return json.loads(text.replace(old, new))


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        pytest.param(
            "temperature_air_mean_2m", "temperature_air_average_2m", "has no parameter", id="parameter-renamed"
        ),
        pytest.param(
            '"stations": {"any_of": ["02564"',
            '"station_ids": {"any_of": ["02564"',
            "takes no argument",
            id="argument-renamed",
        ),
        pytest.param('"stripes_values"', '"stripe_values"', "no such tool", id="tool-renamed"),
        pytest.param('"synop"', '"synoptic"', "network", id="network-renamed"),
        pytest.param('"geosphere"', '"geospheres"', "no provider", id="provider-renamed"),
        pytest.param('"granularity": "district"', '"granularity": "county"', "takes none of", id="enum-value-gone"),
        pytest.param('"max_steps": 4', '"max_steps": 0', "max_steps", id="steps-not-positive"),
        pytest.param('"id": "licence-dwd"', '"id": "licence-meteofrance"', "is used 2 times", id="duplicate-id"),
        pytest.param('"needs_key": true', '"needs_key": false', "needs_key", id="key-flag-wrong"),
        pytest.param('"regex": "(?i)kiel"', '"regex": "(?i)kiel("', "does not compile", id="bad-regex"),
        pytest.param("Etalab Open License 2.0", "api_key=abcdef1234567890abcd", "credential", id="secret"),
        pytest.param("Etalab Open License 2.0", "write to someone@example.org", "personal data", id="email"),
    ],
)
def test_a_stale_case_makes_it_fail(tools: dict[str, dict[str, Any]], old: str, new: str, expected: str) -> None:
    """A rename in the code that a case does not follow is found: the checks are not vacuous."""
    mutated = _mutated(load_cases(), old, new)

    found = problems(mutated, tools)

    assert any(expected in line for line in found), found


def test_a_case_without_a_checkpoint_or_a_fact_fails(tools: dict[str, dict[str, Any]]) -> None:
    """Each case needs a checkpoint and a fact rule."""
    data = copy.deepcopy(load_cases())
    data["cases"][0]["checkpoints"] = []
    data["cases"][1]["facts"] = []

    found = problems(data, tools)

    assert any("no checkpoint" in line for line in found)
    assert any("no fact rule" in line for line in found)
