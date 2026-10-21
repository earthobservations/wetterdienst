# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The code samples of the documentation are code that exists (GH-2621).

`test_docs.py` holds the provider pages and the numbers in the prose to the code. This module holds the samples: the
Python blocks, the commands of the command line and the requests of the REST API that the pages and the README show.

Offline (the selection every pull request runs):

- every Python block parses, and every ``wetterdienst`` name it imports is there;
- a call of a class or function it imports names keywords that exist;
- every ``wetterdienst ...`` command is parsed by the command line itself, so an option that was renamed or removed, a
  value outside its choices, or a required option left out is a usage error here;
- every ``http localhost:7890/api/...`` request names a route of the OpenAPI document, query parameters it has and,
  where the document lists the values, one of them.

Remote (`pytest -m remote tests/test_docs_samples.py`): every Python block of a page is run, in order and in one
namespace as the notebook pages are, and a table a sample prints in a comment is compared with what it prints. The
documentation build runs the ``{code-cell}`` blocks as well and warns where one fails; the fenced ``python`` blocks,
which only a reader ever ran, are what this adds.

A block that cannot run is named in `NOT_RUN` with the reason, and a statement that is meant to fail says so in a
comment before it, ``# raises InvalidParameterError``.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlsplit

import click
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
README = ROOT / "README.md"

#: a fenced block, with the number of backticks it opens with so that a longer fence can hold a shorter one
_FENCE = re.compile(r"^(?P<fence>`{3,})(?P<info>[^\n`]*)\n(?P<body>.*?)^(?P=fence)[ \t]*$", re.DOTALL | re.MULTILINE)
#: the header of a ``{code-cell}``: a YAML block between two dashed lines, or lines of ``:key: value``
_CELL_OPTIONS = re.compile(r"\A(?:---\n.*?\n---\n|(?::\w+:.*\n)+)", re.DOTALL)


@dataclass(frozen=True)
class Sample:
    """A fenced block of a page: where it is, what it says it is, and its code."""

    path: Path
    line: int
    kind: str  # "python", "shell", "json" or "other"
    cell: bool  # a ``{code-cell}``, which the documentation build runs
    code: str

    @property
    def where(self) -> str:
        """Give ``docs/usage/page.md:12`` for a message."""
        return f"{self.path.relative_to(ROOT).as_posix()}:{self.line}"


def _sample_files() -> list[Path]:
    """Give the pages with samples: the README and the hand-written pages, not the changelog nor what Sphinx writes."""
    return [
        README,
        *(
            path
            for path in sorted(DOCS.rglob("*.md"))
            if path != DOCS / "changelog.md" and not {"_build", "apidocs"} & set(path.relative_to(DOCS).parts)
        ),
    ]


def _samples(path: Path) -> Iterator[Sample]:
    text = path.read_text(encoding="utf8")
    for match in _FENCE.finditer(text):
        info = match["info"].strip()
        body = match["body"]
        line = text.count("\n", 0, match.start("body")) + 1
        cell = info.startswith("{code-cell}")
        if cell:
            language = info.removeprefix("{code-cell}").strip()
            body = _CELL_OPTIONS.sub("", body, count=1)
            kind = "shell" if language == "bash" else "python"
        elif info in {"python", "py"}:
            kind = "python"
        elif info in {"bash", "sh", "shell", "console"}:
            kind = "shell"
        elif info == "json":
            kind = "json"
        else:
            kind = "other"
        yield Sample(path, line, kind, cell, body)


def _all_samples(kind: str) -> list[Sample]:
    return [sample for path in _sample_files() for sample in _samples(path) if sample.kind == kind]


def _ids(samples: list[Sample]) -> list[str]:
    return [sample.where for sample in samples]


PYTHON = _all_samples("python")
SHELL = _all_samples("shell")


# --- Python ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("sample", PYTHON, ids=_ids(PYTHON))
def test_python_samples_parse(sample: Sample) -> None:
    """A Python block is Python."""
    ast.parse(sample.code, filename=sample.where)


def _imported(tree: ast.Module) -> dict[str, Any]:
    """Run the ``wetterdienst`` imports of a block and give the names they bind."""
    namespace: dict[str, Any] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "wetterdienst":
            exec(compile(ast.Module([node], []), "<import>", "exec"), namespace)  # noqa: S102
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "wetterdienst":
                    exec(compile(ast.Module([ast.Import([alias])], []), "<import>", "exec"), namespace)  # noqa: S102
    return namespace


@pytest.mark.parametrize("sample", PYTHON, ids=_ids(PYTHON))
def test_python_samples_import_names_that_exist(sample: Sample) -> None:
    """Every ``from wetterdienst... import name`` of a block resolves, and its calls name keywords the name has."""
    tree = ast.parse(sample.code)
    namespace = _imported(tree)  # an ImportError is the failure
    wrong = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in namespace):
            continue
        target = namespace[node.func.id]
        if not callable(target):
            continue
        try:
            parameters = inspect.signature(target).parameters
        except (TypeError, ValueError):
            continue
        if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()):
            continue
        wrong.extend(
            f"{node.func.id}() has no keyword {keyword.arg!r}"
            for keyword in node.keywords
            if keyword.arg is not None and keyword.arg not in parameters
        )
    assert not wrong, f"{sample.where}: " + "; ".join(wrong)


# --- the command line -----------------------------------------------------------------------------------------------


def _shell_lines(code: str) -> list[str]:
    """Give the commands of a shell block: continuations joined, comments and the prompt dropped."""
    joined = re.sub(r"\\\n\s*", " ", code)
    lines = []
    for raw in joined.splitlines():
        line = raw.strip().removeprefix("$ ").removeprefix("!")
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


#: an image reference of the registry the project publishes to: the host is the start of it, then the path and tag
_GHCR_IMAGE = re.compile(r"ghcr\.io/[\w.-]+/[\w.-]+(?::[\w.-]+)?")


def _commands(code: str) -> Iterator[tuple[str, list[str]]]:
    """Give each ``wetterdienst`` invocation of a block as (the line, the arguments after the program)."""
    for line in _shell_lines(code):
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError:
            continue
        for position, word in enumerate(tokens):
            # the program, first on a line (or by its path), or after the image a `docker run` starts it in
            first = position == 0 and word.rsplit("/", 1)[-1] == "wetterdienst"
            in_image = (
                word == "wetterdienst" and position > 0 and _GHCR_IMAGE.fullmatch(tokens[position - 1]) is not None
            )
            if (first or in_image) and position + 1 < len(tokens):
                yield line, tokens[position + 1 :]
                break


def _leaf(arguments: list[str]) -> tuple[click.Command, list[str], str]:
    """Walk the command groups to the command the arguments name; give it, its own arguments and its name."""
    from wetterdienst.ui.cli import cli  # noqa: PLC0415

    command: click.Command = cli
    names = ["wetterdienst"]
    rest = list(arguments)
    while isinstance(command, click.Group):
        # the options of a group come first; none of ours takes a value
        index = next((i for i, token in enumerate(rest) if not token.startswith("-")), None)
        if index is None:
            break
        sub = command.get_command(click.Context(command), rest[index])
        if sub is None:
            msg = f"No such command {rest[index]!r}"
            raise click.UsageError(msg)
        names.append(rest[index])
        command, rest = sub, rest[index + 1 :]
    return command, rest, " ".join(names)


def _cli_samples() -> list[tuple[str, str, list[str]]]:
    return [(sample.where, line, arguments) for sample in SHELL for line, arguments in _commands(sample.code)]


CLI_SAMPLES = _cli_samples()


@pytest.mark.parametrize(
    ("where", "line", "arguments"),
    CLI_SAMPLES,
    ids=[f"{where} {line[:60]}" for where, line, _ in CLI_SAMPLES],
)
def test_cli_samples_are_commands_the_cli_parses(where: str, line: str, arguments: list[str]) -> None:
    """A command a page shows is one the command line accepts: its options exist, its values are among the choices."""
    if arguments[0] in {"--version", "--help"}:
        return
    command, rest, name = _leaf(arguments)
    try:
        command.make_context(name, rest, resilient_parsing=False)
    except click.exceptions.Exit:  # --help
        return
    except click.UsageError as error:
        pytest.fail(f"{where}: `{line}` is refused: {error.format_message()}")


def test_the_pages_show_commands_of_every_kind() -> None:
    """The extraction finds the commands (a parser that finds none passes every test above)."""
    shown = {arguments[0] for _, _, arguments in CLI_SAMPLES}
    assert {"stations", "values", "interpolate", "summarize", "history", "stripes", "restapi"} <= shown


# --- the REST API ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Request:
    """An httpie request of a page."""

    where: str
    line: str
    path: str
    query: list[tuple[str, str]]


def _requests() -> list[Request]:
    requests = []
    for sample in SHELL:
        for line in _shell_lines(sample.code):
            try:
                tokens = shlex.split(line, comments=True)
            except ValueError:
                continue
            if not tokens or tokens[0] not in {"http", "curl"}:
                continue
            rest = [token for token in tokens[1:] if not token.startswith("-")]
            url = next((token for token in rest if "/api/" in token or token.endswith("/api")), None)
            if url is None:
                continue
            split = urlsplit(url if "://" in url else f"http://{url}")
            # httpie: `name==value` items; curl: the query string of the URL
            query = [(name, value) for name, value in parse_qsl(split.query, keep_blank_values=True)]
            query += [(name, value) for name, sep, value in (item.partition("==") for item in rest) if sep]
            requests.append(Request(sample.where, line, split.path, query))
    return requests


REQUESTS = _requests()


def _enum_of(schema: dict[str, Any], components: dict[str, Any]) -> set[str] | None:
    """Give the values a parameter schema lists, if it lists any (a list of them or a single one)."""
    if "$ref" in schema:
        schema = components[schema["$ref"].rsplit("/", 1)[1]]
    if "enum" in schema:
        return {str(value) for value in schema["enum"]}
    if schema.get("type") == "array" and "items" in schema:
        return _enum_of(schema["items"], components)
    found: set[str] = set()
    for member in schema.get("anyOf", []):
        values = _enum_of(member, components)
        if values:
            found |= values
    return found or None


@pytest.fixture(scope="module")
def openapi() -> dict[str, Any]:
    """Give the OpenAPI document of the app."""
    from wetterdienst.ui import restapi  # noqa: PLC0415

    return restapi.app.openapi()


@pytest.mark.parametrize("request_", REQUESTS, ids=[f"{r.where} {r.path}" for r in REQUESTS])
def test_rest_samples_are_requests_the_api_takes(request_: Request, openapi: dict[str, Any]) -> None:
    """A request a page shows is a route of the document, with query parameters it has."""
    prefix = "/api/v1"
    assert request_.path.startswith("/api/"), f"{request_.where}: {request_.line} is not under /api"
    route = request_.path if request_.path.startswith(prefix) else prefix + request_.path.removeprefix("/api")
    assert route in openapi["paths"], f"{request_.where}: {request_.path} is no route (`{request_.line}`)"
    operation = openapi["paths"][route]["get"]
    declared = {parameter["name"]: parameter for parameter in operation.get("parameters", [])}
    components = openapi.get("components", {}).get("schemas", {})
    wrong = []
    for name, value in request_.query:
        if name not in declared:
            wrong.append(f"{name} is no query parameter of {route} (it has {sorted(declared)})")
            continue
        allowed = _enum_of(declared[name].get("schema", {}), components)
        if allowed and any(part not in allowed for part in value.split(",")):
            wrong.append(f"{name}=={value} is none of {sorted(allowed)}")
    assert not wrong, f"{request_.where}: `{request_.line}`: " + "; ".join(wrong)


def test_the_pages_show_requests_of_every_kind() -> None:
    """The extraction finds the requests (a parser that finds none passes every test above)."""
    shown = {request_.path.removeprefix("/api/") for request_ in REQUESTS}
    assert {"stations", "values", "coverage", "interpolate", "summarize", "stripes/image"} <= shown


# --- the parameters the samples request -----------------------------------------------------------------------------

#: the pages that show a name on purpose to show what it does now: the old name is refused there
_NAMES_SHOWN_ON_PURPOSE = {"docs/usage/migrating.md"}
#: what a parameter of a sample is made of, so that a placeholder (`<parameter>`, `$PARAMETERS`) is left alone
_PARAMETER_TEXT = re.compile(r"[a-z0-9_/,]+")


def _unknown_parameters(source: tuple[str, str] | type, parameters: object) -> str | None:
    """Give what the metadata of a provider says of the parameters of a sample, or None where it has them all.

    The source is the class a Python sample requests from, or the provider and network a command or a request names.
    """
    from wetterdienst import Wetterdienst  # noqa: PLC0415
    from wetterdienst.exceptions import ApiNotFoundError, InvalidParameterError  # noqa: PLC0415
    from wetterdienst.model.metadata import parse_parameters  # noqa: PLC0415

    if isinstance(source, type):
        metadata = source.metadata  # ty: ignore[unresolved-attribute]
    else:
        try:
            metadata = Wetterdienst.resolve(*source).metadata
        except ApiNotFoundError:  # a standalone network has no parameters of this kind
            return None
    texts = [parameters] if isinstance(parameters, str) else list(parameters)  # ty: ignore[invalid-argument-type]
    flat: list[str] = []
    for text in texts:
        parts = text.split(",")
        if not all(_PARAMETER_TEXT.fullmatch(part) for part in parts):  # a placeholder
            return None
        flat.extend(parts)
    try:
        parse_parameters(flat, metadata)
    except InvalidParameterError as error:
        return str(error)
    return None


def _option(tokens: list[str], name: str) -> str | None:
    """Give the value of ``--name=value`` or ``--name value`` of a command."""
    for position, token in enumerate(tokens):
        if token == name and position + 1 < len(tokens):
            return tokens[position + 1]
        if token.startswith(f"{name}="):
            return token.removeprefix(f"{name}=")
    return None


def _literal_parameters(node: ast.expr) -> list[str] | None:
    """Give the parameters a ``parameters=`` argument spells out, or None where it is no literal of strings."""
    try:
        literal = ast.literal_eval(node)
    except ValueError:  # a name, a call
        return None
    # a tuple of strings is one parameter, `("daily", "kl", "name")`; a list holds one or several
    items = [literal] if isinstance(literal, tuple) and all(isinstance(part, str) for part in literal) else literal
    if isinstance(items, str):
        return [items]
    if not isinstance(items, list):
        return None
    parameters = ["/".join(item) if isinstance(item, tuple) else item for item in items]
    return parameters if all(isinstance(item, str) for item in parameters) else None


_Requested = tuple[str, str, "tuple[str, str] | type", object]


def _python_parameters() -> list[_Requested]:
    """Give the literal ``parameters=`` of the requests the Python samples make, with the class they call."""
    found: list[_Requested] = []
    for sample in PYTHON:
        tree = ast.parse(sample.code)
        namespace = _imported(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in namespace):
                continue
            request_class = namespace[node.func.id]
            if not (isinstance(request_class, type) and hasattr(request_class, "metadata")):
                continue
            # a call meant to fail says so in the comment before it, one that goes on past an unknown name asks to
            if any(keyword.arg == "on_unknown" for keyword in node.keywords) or re.match(
                r"\s*#\s*raises ", sample.code.splitlines()[node.lineno - 2]
            ):
                continue
            for keyword in node.keywords:
                if keyword.arg == "parameters" and (parameters := _literal_parameters(keyword.value)) is not None:
                    found.append((sample.where, f"{node.func.id}(parameters=...)", request_class, parameters))
    return found


def _requested_parameters() -> list[_Requested]:
    """Give (where, what the sample shows, where its provider is, its parameters) of the samples that name a literal."""
    found: list[_Requested] = []
    for where, line, arguments in CLI_SAMPLES:
        provider, network = _option(arguments, "--provider"), _option(arguments, "--network")
        parameters = _option(arguments, "--parameters")
        if provider and network and parameters:
            found.append((where, line, (provider, network), parameters))
    for request_ in REQUESTS:
        query = dict(request_.query)
        if {"provider", "network", "parameters"} <= set(query):
            found.append((request_.where, request_.line, (query["provider"], query["network"]), query["parameters"]))
    found.extend(_python_parameters())
    return [item for item in found if item[0].split(":")[0] not in _NAMES_SHOWN_ON_PURPOSE]


REQUESTED = _requested_parameters()


@pytest.mark.parametrize(
    ("where", "shown", "source", "parameters"),
    REQUESTED,
    ids=[f"{where} {shown[:50]}" for where, shown, _, _ in REQUESTED],
)
def test_the_parameters_the_samples_request_are_the_providers(
    where: str, shown: str, source: tuple[str, str] | type, parameters: object
) -> None:
    """A parameter a page shows is one its provider declares: a rename leaves the old name in the sample.

    A name that was renamed is refused and the error says what it is called now, which a sample that is never run
    does not show to anyone (GH-2614). The Python samples name the class they request from, the commands and the
    requests the provider and network.
    """
    problem = _unknown_parameters(source, parameters)
    assert problem is None, f"{where}: `{shown}` names a parameter its provider does not declare: {problem}"


def test_the_pages_request_parameters_of_every_kind_of_sample() -> None:
    """The extraction finds the parameters (a parser that finds none passes the test above)."""
    kinds = {"python": False, "command": False, "request": False}
    for _, shown, source, _ in REQUESTED:
        kinds[
            "python" if isinstance(source, type) else "command" if shown.startswith("wetterdienst") else "request"
        ] = True
    assert all(kinds.values()), kinds


# --- JSON the REST page shows ---------------------------------------------------------------------------------------


def _json_blocks(path: Path) -> list[Sample]:
    return [sample for sample in _samples(path) if sample.kind == "json"]


def _loads(sample: Sample) -> Any:  # noqa: ANN401
    """Parse a JSON sample, an ellipsis ``{...}`` standing for an object that is left out."""
    return json.loads(re.sub(r"\{\.\.\.\}", "{}", sample.code))


def test_the_version_samples_have_the_keys_of_the_answer() -> None:
    """The ``/api/version`` samples of the REST page are shaped as the answer is."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from wetterdienst.ui import restapi  # noqa: PLC0415

    answer = TestClient(restapi.app).get("/api/version").json()
    samples = [
        _loads(sample) for sample in _json_blocks(DOCS / "usage" / "restapi.md") if '"mcp_enabled"' in sample.code
    ]
    assert samples, "the REST page no longer shows the answer of /api/version"
    for sample in samples:
        assert set(sample) == set(answer)
        assert set(sample["limits"]) == set(answer["limits"])


def _members_of(sample: Any, schema: dict[str, Any], defs: dict[str, Any], where: str) -> list[str]:  # noqa: ANN401
    """Compare the keys of a JSON sample with a JSON schema: none the schema lacks, every required one present."""
    if "$ref" in schema:
        schema = defs[schema["$ref"].rsplit("/", 1)[1]]
    for member in schema.get("anyOf", []):
        if member.get("type") != "null":
            return _members_of(sample, member, defs, where)
    wrong: list[str] = []
    if isinstance(sample, dict) and "properties" in schema:
        properties = schema["properties"]
        wrong.extend(f"{where}.{key} is no member" for key in sample if key not in properties)
        wrong.extend(f"{where}.{key} is missing" for key in schema.get("required", []) if key not in sample)
        for key, value in sample.items():
            if key in properties:
                wrong += _members_of(value, properties[key], defs, f"{where}.{key}")
    elif isinstance(sample, list) and sample and "items" in schema:
        wrong += _members_of(sample[0], schema["items"], defs, f"{where}[0]")
    return wrong


def test_the_metadata_sample_has_the_members_of_the_block() -> None:
    """The ``metadata`` sample of the REST page has the members, nested ones too, that the block has, and no other."""
    from wetterdienst.ui.response_metadata import ResponseMetadata  # noqa: PLC0415

    sample = next(
        _loads(sample)
        for sample in _json_blocks(DOCS / "usage" / "restapi.md")
        if '"schema_version"' in sample.code and '"provider"' in sample.code
    )
    schema = ResponseMetadata.model_json_schema()
    wrong = _members_of(sample["metadata"], schema, schema["$defs"], "metadata")
    assert not wrong, "\n".join(wrong)


def _problem_samples() -> list[Any]:
    return [
        _loads(sample)
        for sample in _json_blocks(DOCS / "usage" / "restapi.md")
        if '"urn:wetterdienst:problem:' in sample.code
    ]


def test_the_problem_samples_are_problems_of_the_kinds_the_api_has() -> None:
    """Each problem the REST page shows has a kind of the table and the status that kind is answered with."""
    from wetterdienst.ui.problems import PROBLEMS, ProblemKind  # noqa: PLC0415

    samples = _problem_samples()
    assert samples, "the REST page no longer shows a problem"
    for sample in samples:
        kind = ProblemKind(sample["type"].removeprefix("urn:wetterdienst:problem:"))
        assert sample["status"] == PROBLEMS[kind].status
        assert sample["instance"] == f"urn:wetterdienst:request:{sample['request_id']}"
        assert {"type", "title", "status", "detail", "instance", "request_id"} <= set(sample)


def test_the_mcp_samples_name_the_path_the_app_serves() -> None:
    """The MCP client configuration of the REST page points at the path ``/api/version`` reports."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from wetterdienst.ui import restapi  # noqa: PLC0415

    path = TestClient(restapi.app).get("/api/version").json()["mcp_path"]
    if path is None:
        pytest.skip("the [mcp] extra is not installed")
    configuration = next(
        _loads(sample) for sample in _json_blocks(DOCS / "usage" / "mcp.md") if '"mcpServers"' in sample.code
    )
    assert configuration["mcpServers"]["wetterdienst"]["url"].endswith(path)


# --- the messages the pages quote ----------------------------------------------------------------------------------

#: sentences a page quotes of what the library writes: found as written in its source
QUOTED_LITERALS: dict[str, tuple[str, ...]] = {
    "docs/usage/scheduling.md": ("No data available for given constraints", "No internet connection: could not reach"),
    "docs/usage/restapi.md": ("Cannot be combined with", "give exactly one of", "HTTP error", "was renamed to"),
}


def _invalid_enumeration() -> str:
    from wetterdienst.metadata.period import Period  # noqa: PLC0415
    from wetterdienst.util.enumeration import parse_enumeration_from_template  # noqa: PLC0415

    with pytest.raises(ValueError, match="could not be parsed") as caught:
        parse_enumeration_from_template("foo", Period)
    return str(caught.value)


def _invalid_parameter() -> str:
    from wetterdienst.exceptions import InvalidParameterError  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    with pytest.raises(InvalidParameterError) as caught:
        DwdObservationRequest(parameters=["daily/kl/temperature_air_mean_2m", "daily/klx"])
    return str(caught.value)


#: sentences a page quotes of an error, with how to make the library raise it: the message starts as quoted
QUOTED_ERRORS = {
    "docs/usage/python-api.md": (
        (_invalid_enumeration, "foo could not be parsed from Period. Valid values: historical, recent, now, future"),
        (_invalid_parameter, "daily/klx not found in DwdObservationMetadata: 'klx'. Did you mean 'kl'?"),
    ),
}


def test_the_sentences_the_pages_quote_are_the_ones_the_library_writes() -> None:
    """A message a page quotes is the one the library raises, so a message that is reworded shows here."""
    source = "\n".join(path.read_text(encoding="utf8") for path in (ROOT / "src" / "wetterdienst").rglob("*.py"))
    wrong = []
    for page, fragments in QUOTED_LITERALS.items():
        text = (ROOT / page).read_text(encoding="utf8")
        for fragment in fragments:
            if fragment not in text:
                wrong.append(f"{page} no longer quotes {fragment!r}")
            if fragment not in source:
                wrong.append(f"{page} quotes {fragment!r}, which the library does not write")
    for page, errors in QUOTED_ERRORS.items():
        text = " ".join((ROOT / page).read_text(encoding="utf8").split())  # a quoted line is wrapped in the page
        for raise_it, quoted in errors:
            if quoted not in text:
                wrong.append(f"{page} no longer quotes {quoted!r}")
            if not raise_it().startswith(quoted):
                wrong.append(f"{page} quotes {quoted!r}, which is not how the library starts the message")
    assert not wrong, "\n".join(wrong)


# --- running the samples (remote) -----------------------------------------------------------------------------------

#: blocks that are not run, by page and a piece of their code, with the reason
NOT_RUN: dict[tuple[str, str], str] = {
    ("docs/usage/export.md", "influxdb://"): "writes to an InfluxDB that is not there",
    (
        "docs/usage/python-api.md",
        "from wetterdienst import RequestError, UpstreamError",
    ): "needs a `request` of its own",
    ("docs/usage/python-api.md", "except NoInternetError"): "shows how to catch an outage",
    ("docs/usage/python-examples.md", "wradlib"): "needs wradlib, which the project does not install",
}

#: the pages that cannot run as a whole, with the reason
PAGES_NOT_RUN: dict[str, str] = {
    "docs/usage/cli.md": "prints the help of the commands, which `test_cli_samples_are_commands_the_cli_parses` holds",
}


def _page_namespace_key(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _statements(sample: Sample) -> Iterator[tuple[ast.stmt, str | None]]:
    """Give the statements of a block with the exception a preceding ``# raises Name`` comment expects."""
    tree = ast.parse(sample.code)
    lines = sample.code.splitlines()
    for statement in tree.body:
        expected = None
        if statement.lineno >= 2:
            match = re.match(r"\s*#\s*raises (\w+)", lines[statement.lineno - 2])
            expected = match[1] if match else None
        yield statement, expected


def _run_page(path: Path) -> None:
    import polars as pl  # noqa: PLC0415

    key = _page_namespace_key(path)
    if key in PAGES_NOT_RUN:
        pytest.skip(PAGES_NOT_RUN[key])
    namespace: dict[str, Any] = {"__name__": "__docs__"}
    failures = []
    for sample in (s for s in _samples(path) if s.kind == "python"):
        reason = next((why for (page, piece), why in NOT_RUN.items() if page == key and piece in sample.code), None)
        if reason:
            continue
        for statement, expected in _statements(sample):
            module = ast.Module([statement], [])
            if isinstance(statement, ast.Expr):  # keep the value of an expression, as a notebook cell does
                assign = ast.Assign([ast.Name("_", ast.Store())], statement.value)
                module = ast.Module([ast.copy_location(assign, statement)], [])
            ast.fix_missing_locations(module)
            try:
                with pl.Config(tbl_cols=-1, tbl_width_chars=1000):
                    exec(compile(module, sample.where, "exec"), namespace)  # noqa: S102
            except Exception as error:  # noqa: BLE001
                if expected is not None and type(error).__name__ == expected:
                    continue
                failures.append(f"{sample.where}:{statement.lineno}: {type(error).__name__}: {str(error)[:200]}")
                continue
            if expected is not None:
                failures.append(f"{sample.where}:{statement.lineno}: did not raise {expected}")
            _compare_printed_table(sample, statement, namespace, failures)
    assert not failures, "\n".join(failures)


_TABLE_ROW = re.compile(r"^#\s*[│┆]")


def _compare_printed_table(sample: Sample, statement: ast.stmt, namespace: dict[str, Any], failures: list[str]) -> None:
    """Compare a table printed in the comment lines after a statement with the value of that statement.

    Every cell the comment shows has to be a cell of the frame, so a number that moved shows. The comment may leave
    columns out (polars shows ``…`` for them), so the frame is not held to the cells of the comment.
    """
    end = getattr(statement, "end_lineno", None)
    if end is None or not isinstance(statement, ast.Expr):
        return
    lines = sample.code.splitlines()[end:]
    table = []
    for line in lines:
        if line.lstrip().startswith("# ┌") or _TABLE_ROW.match(line) or line.lstrip().startswith("# ╞"):
            table.append(line)
        elif table or not line.lstrip().startswith("#"):
            break
    cells = {
        cell.strip()
        for line in table
        if _TABLE_ROW.match(line)
        for cell in re.split(r"[│┆]", line.lstrip("# "))
        if cell.strip() and cell.strip() != "…"
    }
    if not cells:
        return
    import polars as pl  # noqa: PLC0415

    with pl.Config(tbl_cols=-1, tbl_width_chars=1000, fmt_str_lengths=200):
        shown = str(namespace["_"])
    missing = sorted(cell for cell in cells if cell not in shown and cell != "---")
    if missing:
        failures.append(f"{sample.where}:{statement.lineno}: the comment shows cells the result does not: {missing}")


def _pages_with_python() -> list[Path]:
    return [path for path in _sample_files() if any(sample.kind == "python" for sample in _samples(path))]


@pytest.mark.remote
@pytest.mark.slow
@pytest.mark.parametrize("path", _pages_with_python(), ids=lambda path: path.relative_to(ROOT).as_posix())
def test_python_samples_run(path: Path) -> None:
    """Every Python block of a page runs, in order and in one namespace, and a table it prints is the table it shows."""
    _run_page(path)
