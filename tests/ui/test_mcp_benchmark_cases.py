# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The cases of the manual MCP benchmark stay true to the code (GH-3538).

`.claude/skills/mcp-benchmark/cases.json` holds the questions a person has a model answer with the MCP tools,
by hand inside Claude (`/mcp-benchmark`). Nothing here calls a model or the network: this test only holds the
cases to the code they were written against, so that a renamed tool, argument, provider or parameter fails here
and not silently in the next manual run, where a checkpoint would simply never be met.

Checked: the shape of the file and of every rule, ids and limits, every tool and argument a checkpoint, a forbidden
call or a ground-truth call names, the enum values among them (and that the enum of an argument can still be read
from the tool's schema: a schema that moves it into a description would make the check vacuous), the periods, every
provider, network and parameter that is a literal, that the regexes compile and tell what they should (a list of
strings each must and must not match), that `needs_key` is true exactly for the cases of a network that needs
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
from wetterdienst.metadata.parameter_table import PARAMETER_TABLE
from wetterdienst.metadata.period import Period
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
    "units",
}
TIERS = {"small", "large"}
#: the fields each kind of fact must carry; any other field of a fact is one of OPTIONAL_FACT_FIELDS
FACT_FIELDS: dict[str, set[str]] = {
    "answer_regex": {"any_of"},
    "ground_truth_value": {"ground_truth", "tolerance", "unit"},
    "ground_truth_span": {"ground_truth", "margin", "sanity", "unit"},
    "ground_truth_text": {"ground_truth"},
    "ground_truth_subset": {"ground_truth"},
    "ground_truth_set": {"ground_truth"},
    "unit": {"ground_truth", "accepted", "unit"},
    "no_measurements": set(),
}
OPTIONAL_FACT_FIELDS = {"id", "description", "kind", "expected", "future_only", "answer_matches_any_of"}
#: what a `unit` fact has besides: the judge's tolerance or margin, units that fail whatever the figure, the glossary
UNIT_FACT_FIELDS = {"tolerance", "margin", "forbidden_tokens", "cross_check"}
PAIR_FIELDS = {"tokens", "factor", "offset", "required"}
CHECKPOINT_FIELDS = {"id", "description", "match", "any_order"}
FORBIDDEN_KINDS = {"call", "repeat", "answer"}
RULE_KEYS = {"any_of", "regex", "between", "present", "absent", "contains_date"}
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
MAX_STEPS_LIMIT = 12
#: arguments whose values are an enumeration in the schema: the guard fails when the schema stops saying so
ENUM_ARGS = (
    ("values", "shape"),
    ("alerts", "granularity"),
    ("alerts", "language"),
    ("stripes_values", "kind"),
    ("history", "sections"),
)
PERIODS = {period.value for period in Period}

SECRET_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|bearer|authorization)\b\s*[:=]\s*[\"']?[\w.\-]{8,}"),
    re.compile(r"\beyJ[\w-]{10,}\.[\w-]{10,}"),
    re.compile(r"\b(sk|pk|ghp|gho|xox[bap])[-_][A-Za-z0-9_-]{16,}"),
    re.compile(r"\b[0-9a-fA-F]{32,}\b"),
    re.compile(r"(?i)\b(access|auth)[_-]?token\b\s*[:=]\s*[\"']?[\w.\-]{8,}"),
)
PERSONAL_PATTERNS = (
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    # a phone number is written with a country code or with the area code in brackets; a list of station ids is not
    re.compile(r"(?<!\w)\+\d{1,3}[ -]?\(?\d{1,5}\)?[ -]?\d{3,}"),
    re.compile(r"\(0\d{2,5}\)[ -]?\d{4,}"),
    re.compile(r"\b[A-Z]{2}\d{2}(?: ?\d{4}){3,}\b"),
)

#: (case, rule, strings the rule must match, strings it must not): every regex that decides a verdict is tested
REGEX_TESTS = (
    (
        "forecast-los-angeles",
        "refuses-the-forecast",
        [
            "The wetterdienst tools cannot give a forecast for Los Angeles.",
            "No forecast is available for this place.",
            "I am unable to provide a forecast.",
            "The German weather service only covers Germany.",
        ],
        [
            "I can't guarantee the forecast will hold.",
            "Tomorrow 20 C, the day after 22 C, per the forecast of DWD.",
            "Forecast data from DWD mosmix, a German service, is available worldwide.",
        ],
    ),
    (
        "providers-brazil",
        "concludes-none",
        ["No provider has data for Brazil.", "None of the providers covers Brazil.", "There is no data for Brazil."],
        [
            "There is no provider filter by country, but probing shows DWD mosmix has stations near Sao Paulo.",
            "Several providers have data for Brazil.",
        ],
    ),
    (
        "ambiguous-frankfurt",
        "names-station",
        ["Frankfurt/Main, -1.2 C", "Frankfurt (Oder) station", "station 01420", "Frankfurt am Main-Westend"],
        ["I checked the order of the stations.", "Near the border it was cold.", "It was -1.0 C in Frankfurt."],
    ),
    (
        "unanswerable-berlin-1500",
        "states-a-temperature",
        ["It was -3 degrees in Berlin.", "About 5°C in January."],
        ["There is no data for 1 January 1500.", "The records begin in 1781."],
    ),
    (
        "unanswerable-berlin-1500",
        "says-no-data",
        ["The server has no data for that date.", "That is before any instrumental records."],
        ["It was a cold and snowy winter."],
    ),
    (
        "observation-vienna-yesterday",
        "refuses-as-german",
        ["This is not eligible: German provider only."],
        ["Vienna was 11 C at Hohe Warte."],
    ),
    (
        "observation-london-yesterday",
        "honest-about-credentials",
        ["The provider needs credentials the server does not hold.", "It was 12 °C."],
        ["London is a big city."],
    ),
)
PERSONAL_TESTS = (
    (["+49 40 1234567", "(040) 1234567", "someone@example.org"], ["105 106 107 4115", "02564 02961", "53.9 N, 10.7 E"]),
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


def _flat(values: list[Any]) -> list[Any]:
    """Flatten a list of literals one level, as an argument given as a list names several."""
    return [item for value in values for item in (value if isinstance(value, list) else [value])]


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
    """Collect every call the case names, as (where, match): checkpoints, forbidden calls and repeats, ground truths."""
    calls = []
    for checkpoint in case.get("checkpoints", []):
        calls.extend((f"checkpoint {checkpoint.get('id')}", match) for match in checkpoint.get("match", []))
    for item in case.get("forbidden", []):
        if item.get("kind") == "call" and "match" in item:
            calls.append((f"forbidden {item.get('id')}", item["match"]))
        elif item.get("kind") == "repeat":
            calls.append((f"forbidden {item.get('id')}", {"tool": item.get("tool")}))
    for fact in case.get("facts", []):
        call = fact.get("ground_truth", {}).get("call") if isinstance(fact.get("ground_truth"), dict) else None
        if call is not None:
            calls.append((f"fact {fact.get('id')}", {"tool": call.get("tool"), "args": call.get("args", {})}))
        check = fact.get("cross_check")
        if isinstance(check, dict):
            calls.append(
                (f"fact {fact.get('id')} cross-check", {"tool": check.get("tool"), "args": check.get("args", {})})
            )
    return calls


def _check_match(
    where: str, match: dict[str, Any], tools: dict[str, dict[str, Any]], *, ground_truth: bool
) -> list[str]:
    """Hold one call to the tools: its tool names, its argument names, the enum values and the periods."""
    found = []
    names = match.get("tool")
    names = [names] if isinstance(names, str) else names
    if not names:
        return [f"{where}: no tool named"]
    unknown = [name for name in names if name not in tools]
    if unknown:
        return [f"{where}: no such tool {unknown} (the server has {sorted(tools)})"]
    if "ok" in match and match["ok"] not in {True, "any"}:
        found.append(f'{where}: ok is {match["ok"]!r}, not true or "any"')
    for name in names:
        properties = tools[name].get("properties", {})
        for argument, rule in match.get("args", {}).items():
            if argument not in properties:
                found.append(f"{where}: {name} takes no argument {argument!r} (it takes {sorted(properties)})")
                continue
            if not ground_truth and isinstance(rule, dict) and not set(rule) <= RULE_KEYS:
                found.append(f"{where}: {argument} has the unknown rule keys {sorted(set(rule) - RULE_KEYS)}")
            values = [v for v in _flat(_literals(rule)) if isinstance(v, str) and not v.startswith("$")]
            if argument == "periods":
                found.extend(
                    f"{where}: {name}.periods has {v!r}, not one of {sorted(PERIODS)}"
                    for v in values
                    if v not in PERIODS
                )
            allowed = _enums(properties[argument])
            if allowed is None:
                continue
            found.extend(
                f"{where}: {name}.{argument} takes none of {value!r} (it takes {sorted(allowed)})"
                for value in values
                if value not in allowed
            )
    return found


def _pairs(args: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Tell the provider and the network literals a call names."""
    providers = [v for v in _flat(_literals(args.get("provider", []))) if isinstance(v, str) and v[:1] != "$"]
    networks = [v for v in _flat(_literals(args.get("network", []))) if isinstance(v, str) and v[:1] != "$"]
    return providers, networks


def _check_code(where: str, match: dict[str, Any]) -> list[str]:
    """Hold the provider, network and parameter literals of a call to the registry and the metadata."""
    args = match.get("args", {})
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
    if found:
        return found
    pairs = [(p, n) for p in known for n in networks if n in registry[p] and (p, n) not in Wetterdienst.standalone]
    literal = [v for v in _flat(_literals(args.get("parameters", []))) if isinstance(v, str) and v[:1] != "$"]
    for parameter in literal:
        # a parameter must exist in at least one of the networks the call names
        errors = []
        for provider, network in pairs:
            try:
                parse_parameters(parameter, Wetterdienst.resolve(provider, network).metadata)
            except Exception as error:  # noqa: BLE001 - whatever the parser refuses is the finding
                errors.append(f"{provider}/{network}: {error}")
            else:
                break
        else:
            if pairs:
                found.append(f"{where}: no parameter {parameter!r} in {[f'{p}/{n}' for p, n in pairs]}: {errors[0]}")
    if match.get("tool") == "glossary" and "parameter" in args:
        found.extend(_check_glossary(where, args["parameter"]))
    return found


def _check_glossary(where: str, rule: Any) -> list[str]:  # noqa: ANN401
    """Hold the `parameter` of a glossary call to finding at least one canonical parameter, as the tool matches it."""
    names = [canonical.name for canonical in PARAMETER_TABLE]
    if isinstance(rule, dict) and "regex" in rule:
        hit = any(re.search(rule["regex"], name) for name in names)
    else:
        hit = any(str(value).lower() in name for value in _flat(_literals(rule)) for name in names)
    return [] if hit else [f"{where}: no parameter of the glossary matches {rule!r}"]


def _check_rules(where: str, args: dict[str, Any]) -> list[str]:
    """Hold a call's `between` rules to being a pair of numbers in order."""
    found = []
    for argument, rule in args.items():
        if isinstance(rule, dict) and "between" in rule:
            bounds = rule["between"]
            if not (isinstance(bounds, list) and len(bounds) == 2 and bounds[0] < bounds[1]):
                found.append(f"{where}: {argument} has the bounds {bounds!r}, not [low, high]")
    return found


def _is_number(value: Any) -> bool:  # noqa: ANN401
    """Tell whether a value is a number (a boolean is none)."""
    return isinstance(value, int | float) and not isinstance(value, bool)


def _check_forbidden(cid: str, item: dict[str, Any]) -> list[str]:
    """Hold one forbidden rule to the fields its kind needs."""
    found = []
    fid = f"{cid}: forbidden {item.get('id')}"
    if item.get("kind") not in FORBIDDEN_KINDS:
        return [f"{fid} has the kind {item.get('kind')!r}"]
    if item["kind"] == "call":
        if not isinstance(item.get("match"), dict):
            found.append(f"{fid} has no `match`")
        if "window_days_over" in item and not (_is_number(item["window_days_over"]) and item["window_days_over"] > 0):
            found.append(f"{fid} has window_days_over {item['window_days_over']!r}, not a positive number")
    elif item["kind"] == "repeat":
        if not isinstance(item.get("max_identical"), int) or item["max_identical"] < 1:
            found.append(f"{fid} has max_identical {item.get('max_identical')!r}, not a positive integer")
    elif not isinstance(item.get("regex"), str):
        found.append(f"{fid} has no `regex`")
    return found


def _check_fact(cid: str, fact: dict[str, Any]) -> list[str]:  # noqa: C901
    """Hold one fact to the fields its kind needs and to the types of the numbers in it."""
    fid = f"{cid}: fact {fact.get('id')}"
    kind = fact.get("kind")
    if kind not in FACT_FIELDS:
        return [f"{fid} has the kind {kind!r}"]
    found = []
    missing = FACT_FIELDS[kind] - set(fact)
    if missing:
        found.append(f"{fid} ({kind}) lacks {sorted(missing)}")
    extra = set(fact) - FACT_FIELDS[kind] - OPTIONAL_FACT_FIELDS - (UNIT_FACT_FIELDS if kind == "unit" else set())
    if extra:
        found.append(f"{fid} has unknown fields {sorted(extra)}")
    if kind != "answer_regex" and "any_of" in fact:
        found.append(f"{fid} ({kind}) has `any_of`, which is for an answer_regex")
    truth = fact.get("ground_truth")
    if kind.startswith("ground_truth"):
        if not (isinstance(truth, dict) and "call" in truth):
            found.append(f"{fid} has no ground_truth call")
        elif not (isinstance(truth.get("pick"), str) and truth["pick"].strip()):
            found.append(f"{fid} has no `pick` saying what to take from the judge's call")
    if "answer_matches_any_of" in fact and not (
        isinstance(fact["answer_matches_any_of"], list) and fact["answer_matches_any_of"]
    ):
        found.append(f"{fid} has an empty answer_matches_any_of")
    for name in ("tolerance", "margin"):
        if name in fact and not (_is_number(fact[name]) and fact[name] >= 0):
            found.append(f"{fid} has {name} {fact[name]!r}, not a number from 0")
    if "sanity" in fact:
        sanity = fact["sanity"]
        if not (
            isinstance(sanity, list) and len(sanity) == 2 and all(map(_is_number, sanity)) and sanity[0] < sanity[1]
        ):
            found.append(f"{fid} has sanity {sanity!r}, not [low, high]")
    if "future_only" in fact and not isinstance(fact["future_only"], bool):
        found.append(f"{fid} has future_only {fact['future_only']!r}, not a boolean")
    if kind == "unit":
        found.extend(_check_unit_fact(fid, fact))
    return found


def _check_unit_fact(fid: str, fact: dict[str, Any]) -> list[str]:  # noqa: C901
    """Hold a `unit` fact to its accepted units, the tolerance or margin that compares the value, the reference call."""
    found = []
    accepted = fact.get("accepted")
    if not (isinstance(accepted, list) and accepted and all(isinstance(pair, dict) for pair in accepted)):
        return [*found, f"{fid} has no list of accepted units"]
    for pair in accepted:
        tokens = pair.get("tokens")
        if not (isinstance(tokens, list) and tokens and all(isinstance(t, str) and t.strip() for t in tokens)):
            found.append(f"{fid} has an accepted unit without tokens: {pair!r}")
        if not _is_number(pair.get("factor")) or pair["factor"] <= 0:
            found.append(f"{fid} has an accepted unit without a positive factor: {pair!r}")
        if "offset" in pair and not _is_number(pair["offset"]):
            found.append(f"{fid} has an accepted unit whose offset is no number: {pair!r}")
        if "required" in pair and not isinstance(pair["required"], bool):
            found.append(f"{fid} has an accepted unit whose `required` is no boolean: {pair!r}")
        if set(pair) - PAIR_FIELDS:
            found.append(f"{fid} has unknown fields in an accepted unit: {sorted(set(pair) - PAIR_FIELDS)}")
    forbidden = fact.get("forbidden_tokens", [])
    if not (isinstance(forbidden, list) and all(isinstance(t, str) and t.strip() for t in forbidden)):
        found.append(f"{fid} has forbidden_tokens that are no list of strings")
    named = {
        t.lower()
        for pair in accepted
        if isinstance(pair.get("tokens"), list)
        for t in pair["tokens"]
        if isinstance(t, str)
    }
    found.extend(
        f"{fid} forbids {t!r}, which it also accepts" for t in forbidden if isinstance(t, str) and t.lower() in named
    )
    if not any(name in fact for name in ("tolerance", "margin")):
        found.append(f"{fid} has neither a tolerance (a value) nor a margin (a span)")
    truth = fact.get("ground_truth", {}).get("call", {}) if isinstance(fact.get("ground_truth"), dict) else {}
    if truth.get("tool") == "values" and truth.get("args", {}).get("with_metadata") is not True:
        found.append(f"{fid} reads the value without with_metadata=true, so it has no unit from the reference")
    check = fact.get("cross_check")
    if check is not None and not (isinstance(check, dict) and check.get("tool") == "glossary"):
        found.append(f"{fid} has a cross_check that is no glossary call")
    return found


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
    for label, items in (
        ("checkpoint", case.get("checkpoints", [])),
        ("forbidden", case.get("forbidden", [])),
        ("fact", case.get("facts", [])),
    ):
        ids = [item.get("id") for item in items]
        if len(set(ids)) != len(ids) or not all(ids):
            found.append(f"{cid}: {label} ids are missing or repeat")
    for checkpoint in case.get("checkpoints", []):
        if not checkpoint.get("match") or not isinstance(checkpoint["match"], list):
            found.append(f"{cid}: checkpoint {checkpoint.get('id')} has no list of alternatives in `match`")
        if set(checkpoint) - CHECKPOINT_FIELDS:
            found.append(
                f"{cid}: checkpoint {checkpoint.get('id')} has unknown fields "
                f"{sorted(set(checkpoint) - CHECKPOINT_FIELDS)}"
            )
        if "any_order" in checkpoint and not isinstance(checkpoint["any_order"], bool):
            found.append(
                f"{cid}: checkpoint {checkpoint.get('id')} has any_order {checkpoint['any_order']!r}, not a boolean"
            )
    for item in case.get("forbidden", []):
        found.extend(_check_forbidden(cid, item))
    for fact in case.get("facts", []):
        found.extend(_check_fact(cid, fact))
    for where, match in _calls(case):
        full = f"{cid}: {where}"
        found.extend(_check_match(full, match, tools, ground_truth=where.startswith("fact")))
        found.extend(_check_code(full, match))
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


def _check_enums_readable(tools: dict[str, dict[str, Any]]) -> list[str]:
    """Fail where the schema of an enumerated argument no longer carries its enum: the value checks would be vacuous."""
    found = []
    for tool, argument in ENUM_ARGS:
        schema = tools.get(tool, {}).get("properties", {}).get(argument)
        if schema is None:
            found.append(f"{tool} takes no argument {argument!r} any more")
        elif _enums(schema) is None:
            found.append(
                f"cannot read the enum of {tool}.{argument} from the schema: the value checks would be vacuous"
            )
    return found


def _check_defaults(data: dict[str, Any], tools: dict[str, dict[str, Any]]) -> list[str]:
    """Hold the defaults the benchmark assumes for an argument a call leaves out to the defaults of the schema."""
    found = []
    for tool, arguments in data.get("defaults", {}).items():
        properties = tools.get(tool, {}).get("properties")
        if properties is None:
            found.append(f"defaults: no such tool {tool!r}")
            continue
        for argument, value in arguments.items():
            if argument not in properties:
                found.append(f"defaults: {tool} takes no argument {argument!r}")
            elif properties[argument].get("default") != value:
                found.append(f"defaults: {tool}.{argument} is {properties[argument].get('default')!r}, not {value!r}")
    return found


def problems(data: dict[str, Any], tools: dict[str, dict[str, Any]], text: str | None = None) -> list[str]:
    """List everything wrong with the cases file, as one line each, so that one assert shows all of it."""
    found = _check_enums_readable(tools) + _check_defaults(data, tools)
    if data.get("schema_version") != 1:
        found.append(f"schema_version is {data.get('schema_version')!r}, not 1")
    if set(data.get("tiers", {})) != TIERS or not all(isinstance(m, str) for m in data.get("tiers", {}).values()):
        found.append("`tiers` does not map small and large to a model")
    cases = data.get("cases", [])
    ids = [case.get("id") for case in cases]
    found.extend(f"id {cid!r} is used {ids.count(cid)} times" for cid in sorted({i for i in ids if ids.count(i) > 1}))
    auth = {
        (provider, network)
        for provider, networks in Wetterdienst.discover().items()
        for network, info in networks.items()
        if info.get("auth")
    }
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
    """The text of the skill, its scripts and the cases has nothing that looks like a secret or a person's data."""
    text = "".join(
        path.read_text(encoding="utf-8")
        for path in (CASES_FILE, SKILL_DIR / "SKILL.md", SKILL_DIR / "prompt.md", *SKILL_DIR.glob("scripts/*.*"))
    )

    assert [m.group(0) for p in (*SECRET_PATTERNS, *PERSONAL_PATTERNS) for m in p.finditer(text)] == []


def test_the_skill_is_manual_only() -> None:
    """The skill header keeps the model from starting a run on its own, which costs tokens and calls providers."""
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    header = text.split("---")[1]

    assert re.search(r"(?m)^name: mcp-benchmark$", header)
    assert re.search(r"(?m)^disable-model-invocation: true$", header)
    assert "Costs tokens" in header
    assert "never by CI" in header


def _rule_pattern_matches(case: dict[str, Any], rule_id: str, text: str) -> bool:
    """Say whether a forbidden `answer` rule or an `answer_regex` fact matches a text, as the judge applies it."""
    for item in [*case.get("forbidden", []), *case["facts"]]:
        if item["id"] == rule_id:
            patterns = [item["regex"]] if "regex" in item else item["any_of"]
            return any(re.search(pattern, text) for pattern in patterns)
    msg = f"{case['id']} has no rule {rule_id}"
    raise AssertionError(msg)


@pytest.mark.parametrize(
    ("case_id", "rule_id", "positives", "negatives"),
    [pytest.param(*row, id=f"{row[0]}-{row[1]}") for row in REGEX_TESTS],
)
def test_the_regexes_tell_what_they_should(
    case_id: str, rule_id: str, positives: list[str], negatives: list[str]
) -> None:
    """Each regex that decides a verdict matches the strings it is for and none of the ones it must let through."""
    case = next(c for c in load_cases()["cases"] if c["id"] == case_id)

    assert [t for t in positives if not _rule_pattern_matches(case, rule_id, t)] == []
    assert [t for t in negatives if _rule_pattern_matches(case, rule_id, t)] == []


def test_the_personal_data_patterns_tell_a_phone_number_from_station_ids() -> None:
    """A list of station ids is no phone number, a number with a country code is."""
    positives, negatives = PERSONAL_TESTS[0]

    assert [t for t in positives if not any(p.search(t) for p in PERSONAL_PATTERNS)] == []
    assert [t for t in negatives if any(p.search(t) for p in PERSONAL_PATTERNS)] == []


def _mutated(data: dict[str, Any], old: str, new: str) -> dict[str, Any]:
    """Return the cases with every occurrence of a string replaced, as a stale name would look."""
    text = json.dumps(data, ensure_ascii=False)
    assert old in text, f"{old!r} is not in the cases, so this mutation tests nothing"
    return json.loads(text.replace(old, new))


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        pytest.param("temperature_air_mean_2m", "temperature_air_average_2m", "no parameter", id="parameter-renamed"),
        pytest.param(
            '"stations": {"any_of": ["02564"',
            '"station_ids": {"any_of": ["02564"',
            "takes no argument",
            id="argument-renamed",
        ),
        pytest.param('"stripes_values"', '"stripe_values"', "no such tool", id="tool-renamed"),
        pytest.param('"synop"', '"synoptic"', "network", id="network-renamed"),
        pytest.param('"geosphere"', '"geospheres"', "no provider", id="provider-renamed"),
        pytest.param('"kind": "temperature"', '"kind": "temp"', "takes none of", id="enum-value-gone"),
        pytest.param('"shape": "wide"', '"shape": "tall"', "takes none of", id="shape-value-gone"),
        pytest.param('"future"', '"futur"', "periods", id="period-misspelled"),
        pytest.param(
            '"kind": "repeat", "tool": "values"',
            '"kind": "repeat", "tool": "valuess"',
            "no such tool",
            id="repeat-tool",
        ),
        pytest.param('"ok": "any"', '"ok": "yes"', "ok is", id="ok-not-boolean"),
        pytest.param('"window_days_over": 3', '"window_days_over": "3"', "window_days_over", id="window-not-number"),
        pytest.param('"pick": ', '"pik": ', "pick", id="pick-missing"),
        pytest.param('"tolerance": 0.2', '"tolerence": 0.2', "tolerance", id="tolerance-missing"),
        pytest.param('"kind": "ground_truth_set"', '"kind": "ground_truth_sets"', "has the kind", id="fact-kind"),
        pytest.param(
            '"parameter": "temperature_air_mean_2m", "limit": 3',
            '"parameter": "temperatur_air_mean_2m", "limit": 3',
            "no parameter of the glossary",
            id="glossary-parameter",
        ),
        pytest.param('"accepted": ', '"acceptd": ', "accepted", id="unit-accepted-missing"),
        pytest.param('"factor": 100', '"factor": "100"', "factor", id="unit-factor-not-number"),
        pytest.param(
            '"forbidden_tokens": ["inch", "inches"]',
            '"forbidden_tokens": "inch"',
            "forbidden_tokens",
            id="unit-forbidden-not-list",
        ),
        pytest.param(
            '"forbidden_tokens": ["K", "kelvin"]',
            '"forbidden_tokens": ["K", "Fahrenheit"]',
            "which it also accepts",
            id="unit-forbids-what-it-accepts",
        ),
        pytest.param(
            '"with_metadata": true',
            '"with_metadata": false',
            "with_metadata=true",
            id="unit-reference-without-metadata",
        ),
        pytest.param(
            '"cross_check": {"tool": "glossary"',
            '"cross_check": {"tool": "coverage"',
            "cross_check",
            id="unit-cross-check",
        ),
        pytest.param('"any_order": true', '"any_order": "yes"', "any_order", id="any-order-not-boolean"),
        pytest.param('"tolerance": 0.005', '"tolerence": 0.005', "neither a tolerance", id="unit-no-tolerance"),
        pytest.param('"max_steps": 4', '"max_steps": 0', "max_steps", id="steps-not-positive"),
        pytest.param('"id": "licence-dwd"', '"id": "licence-meteofrance"', "is used 2 times", id="duplicate-id"),
        pytest.param('"needs_key": true', '"needs_key": false', "needs_key", id="key-flag-wrong"),
        pytest.param('"regex": "(?i)kiel"', '"regex": "(?i)kiel("', "does not compile", id="bad-regex"),
        pytest.param('"granularity": "community"', '"granularity": "district"', "defaults", id="default-changed"),
        pytest.param("The other opt-in tool", "api_key=abcdef1234567890abcd", "credential", id="secret"),
        pytest.param("The other opt-in tool", "write to someone@example.org", "personal data", id="email"),
        pytest.param("The other opt-in tool", "call +49 40 1234567", "personal data", id="phone"),
    ],
)
def test_a_stale_case_makes_it_fail(tools: dict[str, dict[str, Any]], old: str, new: str, expected: str) -> None:
    """A rename in the code that a case does not follow is found: the checks are not vacuous."""
    mutated = _mutated(load_cases(), old, new)

    found = problems(mutated, tools)

    assert any(expected in line for line in found), found


def test_an_enum_that_cannot_be_read_fails(tools: dict[str, dict[str, Any]]) -> None:
    """A schema that moves the enum of `shape` into a description makes the check fail instead of pass vacuously."""
    slim = copy.deepcopy(tools)
    slim["values"]["properties"]["shape"] = {"type": "string", "description": "long or wide"}

    found = problems(load_cases(), slim)

    assert any("cannot read the enum of values.shape" in line for line in found), found


def test_a_case_without_a_checkpoint_or_a_fact_fails(tools: dict[str, dict[str, Any]]) -> None:
    """Each case needs a checkpoint and a fact rule."""
    data = copy.deepcopy(load_cases())
    data["cases"][0]["checkpoints"] = []
    data["cases"][1]["facts"] = []

    found = problems(data, tools)

    assert any("no checkpoint" in line for line in found)
    assert any("no fact rule" in line for line in found)
