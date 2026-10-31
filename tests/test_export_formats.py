# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The formats of `to_format`, and the table of formats by surface that the export docs hold to the code (GH-3449).

`wetterdienst.io.formats.FORMATS` is the one list of the formats `to_format` renders and the arguments each takes. What
holds it to the results (their formatters take what it says), to the surfaces (the choices of the command line, the
`format` of the REST API and of the MCP tools) and to the documentation (the table "Formats by surface") is here, so a
format added to one place and not the others fails.
"""

from __future__ import annotations

import asyncio
import inspect
import pickle
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import click
import polars as pl
import pytest

from tests.model.test_results import _every_result
from wetterdienst.exceptions import RequestError, UnknownFormatError
from wetterdienst.io.export import ExportMixin
from wetterdienst.io.formats import ARGUMENTS, FORMATS, find_format, names_of
from wetterdienst.io.sinks import FILE_WRITERS
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.alerts.api import DwdWeatherAlertResult
from wetterdienst.provider.dwd.alerts.metadata import DwdWeatherAlertGranularity, DwdWeatherAlertLanguage
from wetterdienst.ui.cli import cli
from wetterdienst.ui.render import render_kwargs

if TYPE_CHECKING:
    from collections.abc import Callable

DOCS = Path(__file__).parent.parent / "docs" / "usage" / "export.md"

#: the results that have the formats, which the history result does not
_WITH_FORMATS = ("stations", "values", "interpolated", "summarized")

#: what "all" in the table stands for: the commands, routes and tools that return a result
_ALL = ("stations", "values", "interpolate", "summarize")

#: the routes of the REST API and the tools of MCP are named as the commands are
_ROUTE_OF = {command: f"/api/v1/{command}" for command in _ALL}


def _keywords(function: Callable[..., object]) -> set[str]:
    """Name the keywords a formatter takes, but for `self` and `fmt`."""
    return {
        name
        for name, parameter in inspect.signature(function).parameters.items()
        if name not in ("self", "fmt") and parameter.kind is not inspect.Parameter.VAR_KEYWORD
    }


def _formatter(result: object, format_name: str) -> Callable[..., object]:
    """Give the method of a result that renders a format: `_to_image` for a chart, whose `fmt` is the format."""
    return getattr(result, "_to_image" if FORMATS[format_name].kind == "chart" else FORMATS[format_name].method)


# --- the registry and the results -------------------------------------------------------------------------------------


def test_the_formats_are_the_ones_the_docs_listed_before_the_registry() -> None:
    """The formats of `to_format`, in the order the surfaces list them, are json, geojson and csv, then the charts."""
    assert list(FORMATS) == ["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"]
    assert names_of("data") == ("json", "geojson", "csv")
    assert names_of("chart") == ("html", "png", "jpg", "webp", "svg", "pdf")


@pytest.mark.parametrize("format_name", list(FORMATS))
def test_a_format_takes_every_argument_one_of_the_results_gives_it(format_name: str) -> None:
    """Across the results the formatter takes `takes` and no less: `with_stations` is of the values results only."""
    results = _every_result()
    taken = set().union(*(_keywords(_formatter(results[name], format_name)) for name in _WITH_FORMATS))
    if format_name == "csv":
        assert FORMATS[format_name].takes == set()
    else:
        assert FORMATS[format_name].takes == taken


def test_the_arguments_are_what_the_formats_take() -> None:
    """The arguments `to_format` accepts are the union of what the formats take."""
    assert {"with_metadata", "with_stations", "indent", "width", "height", "scale", "max_side"} == ARGUMENTS


@pytest.mark.parametrize("name", _WITH_FORMATS)
@pytest.mark.parametrize("format_name", list(names_of("data")))
def test_to_format_takes_every_argument_for_every_data_format(name: str, format_name: str) -> None:
    """One set of every argument is accepted for a data format, and each formatter is given the ones it takes."""
    result: Any = _every_result()[name]
    everything = dict.fromkeys(ARGUMENTS, 2)
    everything.update(with_metadata=True, with_stations=True)
    written = result.to_format(format_name, **everything)
    given = {key: value for key, value in everything.items() if key in FORMATS[format_name].takes}
    expected = getattr(result, FORMATS[format_name].method)(
        **{key: value for key, value in given.items() if key in _keywords(getattr(result, FORMATS[format_name].method))}
    )
    assert written == expected


@pytest.mark.parametrize("name", _WITH_FORMATS)
def test_to_format_drops_a_name_another_format_takes_and_refuses_one_none_takes(name: str) -> None:
    """`indent` is no argument of CSV and is dropped; `separator`, which no format takes, is a `TypeError` (GH-3449)."""
    result: Any = _every_result()[name]
    assert result.to_format("csv", indent=2, width=3, with_metadata=True) == result.to_csv()
    with pytest.raises(TypeError, match="'separator'") as error:
        result.to_format("csv", separator=";")
    # the message lists the names that are valid
    for argument in ARGUMENTS:
        assert argument in str(error.value)
    with pytest.raises(TypeError, match="'with_metdata'"):
        result.to_format("json", with_metdata=True)
    with pytest.raises(TypeError) as both:
        result.to_format("png", wdith=3, separator=";")
    assert "'separator', 'wdith'" in str(both.value)


def test_to_format_names_an_unknown_format_before_an_unknown_argument() -> None:
    """The format is read first: a format nothing renders is the error, whatever else was passed."""
    result: Any = _every_result()["stations"]
    with pytest.raises(UnknownFormatError):
        result.to_format("xlsx", separator=";")


# --- UnknownFormatError -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", _WITH_FORMATS)
def test_an_unknown_format_is_an_unknown_format_error_naming_it_and_the_ones_there_are(name: str) -> None:
    """`to_format` names the format it was given and lists the supported ones; `KeyError` and `ValueError` catch it."""
    result: Any = _every_result()[name]
    with pytest.raises(UnknownFormatError) as error:
        result.to_format("xlsx")
    assert error.value.fmt == "xlsx"
    assert error.value.supported == tuple(FORMATS)
    assert str(error.value) == f"Unknown output format 'xlsx': use one of {', '.join(FORMATS)}"
    assert isinstance(error.value, RequestError)
    for kind in (KeyError, ValueError):
        with pytest.raises(kind):
            result.to_format("xlsx")


@pytest.mark.parametrize("name", _WITH_FORMATS)
def test_a_chart_in_a_format_it_has_not_is_an_unknown_format_error_listing_the_charts(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_to_image` raised a bare `KeyError("Invalid format")`; it names the format and the charts there are."""
    result: Any = _every_result()[name]
    # the figure is built before the format is looked at, and the frame of the fixture has no chart to make of it
    monkeypatch.setattr(type(result), "to_plot", lambda _self: object())
    with pytest.raises(UnknownFormatError, match="'gif'") as error:
        result._to_image("gif")  # noqa: SLF001
    assert error.value.supported == names_of("chart")


def test_the_alerts_result_raises_it_too_with_its_own_formats() -> None:
    """The alerts result has json, geojson and csv, and raised a `ValueError` that did not name them as this does."""
    result = DwdWeatherAlertResult(
        pl.DataFrame(), DwdWeatherAlertGranularity.COMMUNITY, DwdWeatherAlertLanguage.ENGLISH
    )
    with pytest.raises(UnknownFormatError) as error:
        result.to_format("xml")
    assert error.value.supported == ("json", "geojson", "csv")
    with pytest.raises(ValueError, match="'xml'"):
        result.to_format("xml")


def test_find_format_reads_any_case_and_keeps_to_the_formats_it_is_given() -> None:
    """A format is found in any case, and among the ones a caller names only."""
    assert find_format("PNG") is FORMATS["png"]
    with pytest.raises(UnknownFormatError) as error:
        find_format("png", ("json", "csv"))
    assert error.value.supported == ("json", "csv")


def test_the_error_is_a_str_without_quotes_and_pickles() -> None:
    """A `KeyError` prints its message in quotes, and this one is not printed so; it crosses a process as it is."""
    error = UnknownFormatError("xml", ("json", "csv"))
    assert not str(error).startswith(("'", '"'))
    copy = pickle.loads(pickle.dumps(error))  # noqa: S301
    assert (type(copy), copy.fmt, copy.supported, str(copy)) == (UnknownFormatError, "xml", ("json", "csv"), str(error))


# --- the argument set of the surfaces ---------------------------------------------------------------------------------


@pytest.mark.parametrize("format_name", [*FORMATS, "ndjson"])
@pytest.mark.parametrize("max_side", [None, 4000])
def test_the_arguments_the_surfaces_build_are_all_taken_by_some_format(format_name: str, max_side: int | None) -> None:
    """The command line, the REST API and MCP build one set for every format, and `to_format` refuses none of it.

    All three go through `render_kwargs`, which `render` adds `with_stations` to.
    """
    request = SimpleNamespace(format=format_name, with_metadata=True, pretty=True, width=1, height=2, scale=1.5)
    kwargs = render_kwargs(request, max_side=max_side)  # ty: ignore[invalid-argument-type]
    assert set(kwargs) - {"fmt"} <= ARGUMENTS
    assert {*kwargs, "with_stations"} - {"fmt"} <= ARGUMENTS


@pytest.mark.parametrize("name", ["stations", "values"])
@pytest.mark.parametrize("format_name", ["json", "geojson", "csv", "html"])
def test_a_surface_renders_every_format_through_to_format_without_a_refusal(name: str, format_name: str) -> None:
    """What `render` hands `to_format` for a format is rendered, as for the REST API, the command line and MCP."""
    result: Any = _every_result()[name]
    request = SimpleNamespace(format=format_name, with_metadata=True, pretty=True, width=None, height=None, scale=None)
    kwargs = {**render_kwargs(request), "with_stations": True}  # ty: ignore[invalid-argument-type]
    assert isinstance(result.to_format(**kwargs), str)


# --- if_exists --------------------------------------------------------------------------------------------------------


def _cli_default(command: str) -> object:
    option = next(param for param in cli.commands[command].params if param.name == "if_exists")
    return option.default


def test_the_three_defaults_of_if_exists_stay() -> None:
    """A result replaces, the reader fails and the command line replaces; each says why in its docstring (GH-3449)."""
    assert inspect.signature(ExportMixin.to_target).parameters["if_exists"].default == "replace"
    assert inspect.signature(TimeseriesValues.to_target).parameters["if_exists"].default == "fail"
    assert {command: _cli_default(command) for command in _ALL} == dict.fromkeys(_ALL, "replace")
    # one sentence each, from docs/usage/export.md: one frame written as a whole, one table filled station by station
    assert "one frame written as a whole" in (ExportMixin.to_target.__doc__ or "")
    assert "one table being filled station by station" in (TimeseriesValues.to_target.__doc__ or "")


# --- the table of docs/usage/export.md --------------------------------------------------------------------------------


def _table() -> dict[str, dict[str, str]]:
    """Read the table "Formats by surface" as a mapping of each format to its columns, which map to the cells."""
    text = DOCS.read_text(encoding="utf8")
    section = text.split("## Formats by surface", 1)[1]
    lines = [line for line in section.splitlines() if line.startswith("|")]
    header = [cell.strip().replace("`", "") for cell in lines[0].strip("|").split("|")]
    rows = {}
    for line in lines[2:]:
        cells = [cell.strip().replace("`", "") for cell in line.strip("|").split("|")]
        rows[cells[0]] = dict(zip(header[1:], cells[1:], strict=True))
    return rows


def _commands_of(cell: str) -> set[str]:
    """Read a cell of a surface: `all`, `no`, or the commands it lists."""
    if cell == "no":
        return set()
    if cell == "all":
        return set(_ALL)
    return {command.strip() for command in cell.split(",")}


def _cli_formats() -> dict[str, set[str]]:
    """Give the formats of `--format` of each command of the four, as the command line has them."""
    found: dict[str, set[str]] = {}
    for command in _ALL:
        option = next(param for param in cli.commands[command].params if param.name == "fmt")
        assert isinstance(option.type, click.Choice)
        found[command] = set(option.type.choices)
    return found


def _rest_formats() -> dict[str, set[str]]:
    """Give the formats of `format` of each route of the four, as the OpenAPI document of the REST API has them."""
    from wetterdienst.ui import restapi  # noqa: PLC0415

    paths = restapi.app.openapi()["paths"]
    found: dict[str, set[str]] = {}
    for command, route in _ROUTE_OF.items():
        parameters = {parameter["name"]: parameter for parameter in paths[route]["get"]["parameters"]}
        found[command] = set(parameters["format"]["schema"]["enum"])
    return found


def _mcp_formats() -> dict[str, set[str]]:
    """Give the formats of `format` of each tool of the four, as the server lists them."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui import restapi  # noqa: PLC0415
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def listed() -> dict[str, set[str]]:
        async with Client(build_mcp_server(restapi.app)) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            return {command: set(tools[command].input_schema["properties"]["format"]["enum"]) for command in _ALL}

    return asyncio.run(listed())


def _expected(surface: dict[str, set[str]]) -> dict[str, set[str]]:
    """Give the commands that take each format, from the formats each command takes."""
    formats = set().union(*surface.values())
    return {fmt: {command for command, taken in surface.items() if fmt in taken} for fmt in formats}


def test_the_table_lists_every_format_once_and_the_ones_of_the_code() -> None:
    """The rows are the formats of `to_format`, the stream, and the file types that are no format."""
    rows = set(_table())
    expected = {*FORMATS, "ndjson", *(extension.removeprefix(".") for extension in FILE_WRITERS)}
    # `.jsonl` is the file of the `ndjson` row
    assert rows == expected - {"jsonl"}


def test_the_table_holds_the_python_column_to_the_registry() -> None:
    """`to_format` takes the formats the registry lists, and the table says yes of those and no of the others."""
    table = _table()
    assert {name for name, row in table.items() if row["to_format"] == "yes"} == set(FORMATS)
    assert {row["to_format"] for row in table.values()} == {"yes", "no"}


def test_the_table_holds_the_file_column_to_the_writers() -> None:
    """A file extension is written when the table says so, and the table lists every writer once."""
    cells = {name: row["to_target file"] for name, row in _table().items() if row["to_target file"] != "no"}
    assert set(cells.values()) == set(FILE_WRITERS)
    # a row that is itself an extension names it
    for name, cell in cells.items():
        if f".{name}" in FILE_WRITERS:
            assert cell == f".{name}"


@pytest.mark.parametrize(
    ("surface", "column"), [("cli", "CLI --format"), ("rest", "REST format"), ("mcp", "MCP format")]
)
def test_the_table_holds_each_surface_to_the_formats_it_takes(surface: str, column: str) -> None:
    """A format a command line, route or tool takes is in the table for it, and the table has none it lacks."""
    taken = {"cli": _cli_formats, "rest": _rest_formats, "mcp": _mcp_formats}[surface]()
    documented = {name: _commands_of(row[column]) for name, row in _table().items() if row[column] != "no"}
    assert documented == _expected(taken)
    # and no surface offers a format `to_format` has not, but the stream
    assert set().union(*taken.values()) <= {*FORMATS, "ndjson"}
