# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Find what a change to the OpenAPI document breaks for a client that was written against an earlier one (GH-3131).

`tests/ui/test_openapi_snapshot.py` shows every change of the contract as a diff, and a diff can be approved by
accident. This compares the served document with that of the last release (`tests/ui/openapi.baseline.json`) and
names each thing the release offered that is gone or different, so that an approved removal fails a check.

The rule is that **the document must still offer all the baseline offered**, and must not ask more of a request.
What is offered is, by operation:

- the path and the method, and the `operationId`;
- each parameter by name and place, its type, its enum members, the members of an object, the items of an array, the
  alternatives of a union, and the `style` and `explode` of a list;
- each status of the responses, each media type and header of it, and the schema of its body down to its members,
  their types, enum members, union alternatives, and which of them are required.

A request is asked more of when a parameter is newly required, or becomes required, or a member of an object it takes
does, and when a parameter or a member of a request body takes **less** than it did:

- a changed `default`, as what an omitted parameter means is part of the contract (a missing default and a null one
  are the same);
- a tighter bound: a larger `minimum`, `exclusiveMinimum`, `minLength` or `minItems`, a smaller `maximum`,
  `exclusiveMaximum`, `maxLength` or `maxItems`, or a bound where there was none;
- a `pattern` that was added or changed (which of two patterns is the tighter cannot be told);
- an enum that dropped members, or one where there was none.

Everything else is additive and passes: a new path, operation, optional parameter, member, status, enum member or
media type, and a looser bound or no pattern. The by-convention rule of the compatibility policy is that a tighter
default or bound is a break, and this is what holds it.

Not compared: titles, descriptions, examples and formats, which describe more than they promise, the defaults and
bounds of an answer, and what an answer means. A change of meaning is in the changelog, and the contract tests of the
routes. `info`, `servers` and `tags` are the document's own and are not the contract either.

An approved break is an entry of `ACCEPTED_BREAKS`, with its reason, and is cleared when the baseline is refreshed.
"""

from __future__ import annotations

import json
from typing import Any

#: what an approved break says: the finding as `breaking_changes` words it, then why it is no break of a client
ACCEPTED_BREAKS: dict[str, str] = {}

_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})


class _Document:
    """An OpenAPI document that can resolve its own references."""

    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document

    def resolve(self, node: dict[str, Any]) -> dict[str, Any]:
        """Follow `$ref` until there is none, keeping the other members of a node that has them."""
        seen: set[str] = set()
        while "$ref" in node:
            reference = node["$ref"]
            if reference in seen:
                msg = f"circular reference {reference}"
                raise ValueError(msg)
            seen.add(reference)
            target: Any = self.document
            for part in reference.removeprefix("#/").split("/"):
                target = target[part]
            node = {**target, **{key: value for key, value in node.items() if key != "$ref"}}
        return node


def breaking_changes(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Name each thing that `baseline` offers and `current` does not, or asks more of a request for."""
    old, new = _Document(baseline), _Document(current)
    found: list[str] = []
    for path, old_item in baseline.get("paths", {}).items():
        new_item = current.get("paths", {}).get(path)
        if new_item is None:
            found.append(f"{path} was removed")
            continue
        for method, old_operation in old_item.items():
            if method not in _METHODS:
                continue
            where = f"{method.upper()} {path}"
            new_operation = new_item.get(method)
            if new_operation is None:
                found.append(f"{where} was removed")
                continue
            found += _operation(old, new, where, old_operation, new_operation)
    return sorted(found)


def schema_breaks(
    baseline: dict[str, Any], current: dict[str, Any], where: str, old_node: dict[str, Any], new_node: dict[str, Any]
) -> list[str]:
    """Compare a schema a caller sends, as a request's: the MCP tools take their arguments as one (GH-3131).

    The two documents resolve the `$ref` of the nodes, so that a schema with its own `$defs` is compared whole.
    """
    return _schema(_Document(baseline), _Document(current), where, old_node, new_node, asked=True)


def unaccepted(findings: list[str]) -> list[str]:
    """Leave out the findings that `ACCEPTED_BREAKS` approves."""
    return [finding for finding in findings if finding not in ACCEPTED_BREAKS]


def _operation(old: _Document, new: _Document, where: str, old_op: dict[str, Any], new_op: dict[str, Any]) -> list[str]:
    found = []
    if old_op.get("operationId") != new_op.get("operationId"):
        found.append(f"{where}: operationId changed from {old_op.get('operationId')} to {new_op.get('operationId')}")
    found += _parameters(old, new, where, old_op.get("parameters", []), new_op.get("parameters", []))
    found += _request_body(old, new, where, old_op.get("requestBody"), new_op.get("requestBody"))
    found += _responses(old, new, where, old_op.get("responses", {}), new_op.get("responses", {}))
    return found


def _parameters(
    old: _Document,
    new: _Document,
    where: str,
    old_parameters: list[dict[str, Any]],
    new_parameters: list[dict[str, Any]],
) -> list[str]:
    found = []
    olds = {(p["in"], p["name"]): p for p in (old.resolve(p) for p in old_parameters)}
    news = {(p["in"], p["name"]): p for p in (new.resolve(p) for p in new_parameters)}
    for key, old_parameter in olds.items():
        name = f"parameter {key[1]} ({key[0]})"
        new_parameter = news.get(key)
        if new_parameter is None:
            found.append(f"{where}: {name} was removed")
            continue
        if new_parameter.get("required", False) and not old_parameter.get("required", False):
            found.append(f"{where}: {name} became required")
        # a list in a query is `form` and exploded unless the document says otherwise
        for member, default in (("style", "form"), ("explode", True)):
            before, after = old_parameter.get(member, default), new_parameter.get(member, default)
            if before != after:
                found.append(f"{where}: {name} {member} changed from {before} to {after}")
        found += _schema(
            old, new, f"{where}: {name}", old_parameter.get("schema", {}), new_parameter.get("schema", {}), asked=True
        )
    found += [
        f"{where}: parameter {key[1]} ({key[0]}) was added and is required"
        for key, parameter in news.items()
        if key not in olds and parameter.get("required", False)
    ]
    return found


def _request_body(
    old: _Document, new: _Document, where: str, old_body: dict[str, Any] | None, new_body: dict[str, Any] | None
) -> list[str]:
    if old_body is None:
        return [f"{where}: a request body was added and is required"] if new_body and new_body.get("required") else []
    if new_body is None:
        return [f"{where}: the request body was removed"]
    old_body, new_body = old.resolve(old_body), new.resolve(new_body)
    found = []
    if new_body.get("required", False) and not old_body.get("required", False):
        found.append(f"{where}: the request body became required")
    for media, old_media in old_body.get("content", {}).items():
        new_media = new_body.get("content", {}).get(media)
        if new_media is None:
            found.append(f"{where}: request media type {media} was removed")
        else:
            found += _schema(
                old,
                new,
                f"{where}: request body {media}",
                old_media.get("schema", {}),
                new_media.get("schema", {}),
                asked=True,
            )
    return found


def _responses(
    old: _Document, new: _Document, where: str, old_responses: dict[str, Any], new_responses: dict[str, Any]
) -> list[str]:
    found = []
    for status, old_response in old_responses.items():
        new_response = new_responses.get(status)
        if new_response is None:
            found.append(f"{where}: response {status} was removed")
            continue
        old_response, new_response = old.resolve(old_response), new.resolve(new_response)
        place = f"{where} {status}"
        for header in old_response.get("headers", {}):
            if header not in new_response.get("headers", {}):
                found.append(f"{place}: header {header} was removed")
        for media, old_media in old_response.get("content", {}).items():
            new_media = new_response.get("content", {}).get(media)
            if new_media is None:
                found.append(f"{place}: media type {media} was removed")
                continue
            found += _schema(
                old, new, f"{place} {media}", old_media.get("schema", {}), new_media.get("schema", {}), asked=False
            )
    return found


def _label(node: dict[str, Any]) -> str:
    """Name a schema for a finding: its reference, else its type, else what it is."""
    if "$ref" in node:
        return node["$ref"].rsplit("/", 1)[-1]
    if "type" in node:
        return str(node["type"])
    return json.dumps(node, sort_keys=True)[:60]


def _schema(
    old: _Document,
    new: _Document,
    where: str,
    old_node: dict[str, Any],
    new_node: dict[str, Any],
    *,
    asked: bool,
    seen: frozenset[tuple[str, str]] = frozenset(),
) -> list[str]:
    """Compare two schemas; `asked` says the schema is a request's, whose new requirements break, not a response's."""
    if "$ref" in old_node and "$ref" in new_node:
        pair = (old_node["$ref"], new_node["$ref"])
        if pair in seen:
            return []
        seen |= {pair}
    old_node, new_node = old.resolve(old_node), new.resolve(new_node)
    old_alternatives = old_node.get("anyOf") or old_node.get("oneOf")
    new_alternatives = new_node.get("anyOf") or new_node.get("oneOf")
    found = _default(where, old_node, new_node) if asked else []
    if old_alternatives or new_alternatives:
        return found + _union(
            old, new, where, old_alternatives or [old_node], new_alternatives or [new_node], asked=asked, seen=seen
        )
    old_type, new_type = old_node.get("type"), new_node.get("type")
    if old_type is not None and new_type is not None and _as_set(old_type) != _as_set(new_type):
        return [*found, f"{where}: type changed from {old_type} to {new_type}"]
    found += _members(where, old_node, new_node, asked=asked)
    found += _object(old, new, where, old_node, new_node, asked=asked, seen=seen)
    if isinstance(old_node.get("items"), dict) and isinstance(new_node.get("items"), dict):
        found += _schema(old, new, f"{where}[]", old_node["items"], new_node["items"], asked=asked, seen=seen)
    return found


def _union(
    old: _Document,
    new: _Document,
    where: str,
    old_alternatives: list[dict[str, Any]],
    new_alternatives: list[dict[str, Any]],
    *,
    asked: bool,
    seen: frozenset[tuple[str, str]],
) -> list[str]:
    """Find each alternative that was offered and is not any more; the others of a union are additions."""
    found = []
    for alternative in old_alternatives:
        results = [_schema(old, new, where, alternative, c, asked=asked, seen=seen) for c in new_alternatives]
        if not all(results):
            continue
        # an alternative that has a single counterpart of its type says what changed of it
        old_type = _as_set(old.resolve(alternative).get("type", ""))
        same_type = [
            result
            for candidate, result in zip(new_alternatives, results, strict=True)
            if old_type == _as_set(new.resolve(candidate).get("type", ""))
        ]
        found += (
            same_type[0]
            if len(same_type) == 1
            else [f"{where}: {_label(alternative)} is no longer one of the alternatives"]
        )
    return found


def _members(where: str, old_node: dict[str, Any], new_node: dict[str, Any], *, asked: bool) -> list[str]:
    """Compare what a value of the schema may be: its enum members and, of a request's, its bounds and its pattern."""
    found = []
    old_members = _enum(old_node)
    new_members = _enum(new_node)
    if old_members and new_members and (gone := sorted(old_members - new_members)):
        found.append(f"{where}: enum members {', '.join(gone)} were removed")
    elif asked and not old_members and new_members:
        found.append(f"{where}: now takes only the enum members {', '.join(sorted(new_members))}")
    if asked:
        found += _bounds(where, old_node, new_node)
        found += _pattern(where, old_node, new_node)
    return found


def _object(
    old: _Document,
    new: _Document,
    where: str,
    old_node: dict[str, Any],
    new_node: dict[str, Any],
    *,
    asked: bool,
    seen: frozenset[tuple[str, str]],
) -> list[str]:
    found = []
    old_properties, new_properties = old_node.get("properties", {}), new_node.get("properties", {})
    for name, old_property in old_properties.items():
        if name not in new_properties:
            found.append(f"{where}: member {name} was removed")
            continue
        found += _schema(old, new, f"{where}.{name}", old_property, new_properties[name], asked=asked, seen=seen)
    old_required, new_required = set(old_node.get("required", ())), set(new_node.get("required", ()))
    if asked:
        found += [f"{where}: member {name} became required" for name in sorted(new_required - old_required)]
    else:
        found += [
            f"{where}: member {name} is no longer always there"
            for name in sorted(old_required - new_required)
            if name in new_properties
        ]
    if isinstance(old_node.get("additionalProperties"), dict) and isinstance(
        new_node.get("additionalProperties"), dict
    ):
        found += _schema(
            old,
            new,
            f"{where}{{}}",
            old_node["additionalProperties"],
            new_node["additionalProperties"],
            asked=asked,
            seen=seen,
        )
    return found


def _default(where: str, old_node: dict[str, Any], new_node: dict[str, Any]) -> list[str]:
    """Find a default that changed: a request that leaves the parameter out means something else now."""
    before, after = old_node.get("default"), new_node.get("default")
    if json.dumps(before, sort_keys=True) == json.dumps(after, sort_keys=True):
        return []
    return [f"{where}: default changed from {json.dumps(before)} to {json.dumps(after)}"]


#: the bounds of a schema from below and from above, each with the keyword that holds an exclusive one
_LOWER = (("minimum", False), ("exclusiveMinimum", True))
_UPPER = (("maximum", False), ("exclusiveMaximum", True))
_COUNTS = (("minLength", "maxLength"), ("minItems", "maxItems"), ("minProperties", "maxProperties"))


def _limit(node: dict[str, Any], keywords: tuple[tuple[str, bool], ...], *, lower: bool) -> tuple[float, bool] | None:
    """Give the bound a schema sets as its value and whether the value itself is out, or None where there is none.

    OpenAPI 3.0 writes an exclusive bound as a boolean beside `minimum`; 3.1 as a number, which is read here.
    """
    found = [
        (node[keyword], exclusive)
        for keyword, exclusive in keywords
        if isinstance(node.get(keyword), (int, float)) and not isinstance(node.get(keyword), bool)
    ]
    if not found:
        return None
    # the tightest of them: the largest lower bound, the smallest upper one, an exclusive one winning a tie
    return max(found, key=lambda bound: (bound[0] if lower else -bound[0], bound[1]))


def _bounds(where: str, old_node: dict[str, Any], new_node: dict[str, Any]) -> list[str]:
    """Find a bound that became tighter, or was added: a value that was taken may be refused now."""
    found = []
    for lower, keywords in ((True, _LOWER), (False, _UPPER)):
        before, after = _limit(old_node, keywords, lower=lower), _limit(new_node, keywords, lower=lower)
        if after is None:
            continue
        if before is None:
            tighter = True
        elif lower:
            tighter = after[0] > before[0] or (after[0] == before[0] and after[1] and not before[1])
        else:
            tighter = after[0] < before[0] or (after[0] == before[0] and after[1] and not before[1])
        if tighter:
            word = "minimum" if lower else "maximum"
            found.append(f"{where}: {word} became {_bound(after, lower=lower)}" + _was(before, lower=lower))
    for minimum, maximum in _COUNTS:
        for keyword, lower in ((minimum, True), (maximum, False)):
            before, after = old_node.get(keyword), new_node.get(keyword)
            if (
                after is None
                or (lower and after == 0)
                or (before is not None and (after <= before if lower else after >= before))
            ):
                continue
            found.append(f"{where}: {keyword} became {after}" + (f" (was {before})" if before is not None else ""))
    return found


def _bound(bound: tuple[float, bool], *, lower: bool) -> str:
    value, exclusive = bound
    return f"{'>' if lower else '<'}{'' if exclusive else '='} {value}"


def _was(bound: tuple[float, bool] | None, *, lower: bool) -> str:
    return "" if bound is None else f" (was {_bound(bound, lower=lower)})"


def _pattern(where: str, old_node: dict[str, Any], new_node: dict[str, Any]) -> list[str]:
    """Find a pattern that was added or changed; which of two is the tighter cannot be told, so a change is one."""
    before, after = old_node.get("pattern"), new_node.get("pattern")
    if after is None or before == after:
        return []
    return [f"{where}: pattern changed from {before} to {after}" if before else f"{where}: now has the pattern {after}"]


def _as_set(type_: Any) -> frozenset[str]:  # noqa: ANN401
    return frozenset(type_ if isinstance(type_, list) else [type_])


def _enum(node: dict[str, Any]) -> set[str]:
    """Give the members an enum or a constant allows, as text."""
    members = node.get("enum", [node["const"]] if "const" in node else [])
    return {json.dumps(member) for member in members}
