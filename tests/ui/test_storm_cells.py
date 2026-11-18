# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The thunderstorm cells of `dwd/storm_cells` on the REST API, as an MCP tool and on the command line (GH-4090).

A scan is the real ones of DWD and a hand-made one (`tests/provider/dwd/storm_cells/stubs.py`) served in place of the
download, so the request, the parser and the renderers are the ones a live answer goes through, and the three surfaces
are held to answer alike.
"""

from __future__ import annotations

import asyncio
import csv
import datetime as dt
import io
import json
import logging
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.provider.dwd.storm_cells.stubs import (
    BERLIN,
    EMPTY_SCAN,
    TWO_CELLS_SCAN,
    parts_scan,
    serve,
    three_cells_scan,
)
from wetterdienst import exceptions
from wetterdienst.provider.dwd.storm_cells import DwdStormCellsRequest
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli

if TYPE_CHECKING:
    from fastmcp.tools import ToolResult

UTC = ZoneInfo("UTC")
THREE = {"KONRAD3D_20260701T120000.xml": three_cells_scan()}
#: the instant of the scan of `TWO_CELLS_SCAN` plus 4 minutes: as fresh as a scan is
NOW = dt.datetime(2026, 11, 17, 22, 19, tzinfo=UTC)
#: the point of Berlin's cell, and one 8 km north of it
IN_BERLIN = {"latitude": BERLIN[0] + 0.01, "longitude": BERLIN[1]}


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the scan of three cells as the newest, a few minutes old."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api._now", lambda: dt.datetime(2026, 7, 1, 12, 6, tzinfo=UTC)
    )
    serve(monkeypatch, THREE)


@pytest.fixture
def client(served: None) -> TestClient:  # noqa: ARG001
    """Give the client of the REST app, which answers an unhandled exception with its 500."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _ids(response_json: dict[str, Any]) -> list[str]:
    return [cell["cell_id"] for cell in response_json["cells"]]


# --- REST ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["/api/v1", "/api"])
def test_rest_without_a_place_is_every_cell_under_both_prefixes(client: TestClient, prefix: str) -> None:
    """Nothing is filtered, and nothing is told: three cells and the scan they are of."""
    response = client.get(f"{prefix}/storm-cells")

    assert response.status_code == 200
    data = response.json()
    assert _ids(data) == ["1", "2", "3"]
    assert data["reference_time"] == "2026-07-01T12:00:00.000000+00:00"
    assert data["metadata"]["warnings"] == []
    assert data["metadata"]["counts"]["rows"] == 3
    assert data["metadata"]["request"] == {
        "provider": "dwd",
        "network": "storm_cells",
        "parameters": [],
        "periods": [],
        "start": None,
        "end": None,
        "stations": None,
    }


def test_rest_the_block_names_the_licence_the_date_of_the_data_and_what_is_calculated(client: TestClient) -> None:
    """CC BY 4.0 and DWD's credit line, when DWD wrote the file, and the sentence of the direction."""
    metadata = client.get("/api/storm-cells").json()["metadata"]

    assert metadata["provider"]["license"]["spdx_id"] == "CC-BY-4.0"
    assert metadata["provider"]["attribution"] == "Source: Deutscher Wetterdienst"
    assert metadata["provider"]["url"] == "https://opendata.dwd.de/weather/radar/konrad3d"
    assert metadata["data_updated_at"] == "2026-07-01T12:05:10.000000+00:00"
    assert "`direction_degrees` is calculated" in metadata["processing_note"]
    assert "`track` is DWD's forecast" in metadata["processing_note"]


def test_rest_a_point_in_a_cell_finds_it(client: TestClient) -> None:
    """The outline contains the point: a distance of 0 is the default."""
    data = client.get("/api/storm-cells", params=IN_BERLIN).json()

    assert _ids(data) == ["2"]
    assert data["metadata"]["counts"]["rows"] == 1
    assert data["metadata"]["warnings"] == []


def test_rest_a_distance_reaches_the_cells_near_the_point(client: TestClient) -> None:
    """The point is 8 km from the outline of Berlin's cell: 9 km finds it, 7 km does not."""
    point = {"latitude": BERLIN[0] + 0.05 + 0.072, "longitude": BERLIN[1]}

    assert _ids(client.get("/api/storm-cells", params={**point, "distance": 9}).json()) == ["2"]
    assert _ids(client.get("/api/storm-cells", params={**point, "distance": 7}).json()) == []


def test_rest_a_box_and_a_severity(client: TestClient) -> None:
    """The box of the whole country with `min_severity` 3 is Munich's cell."""
    box = {"left": 5, "bottom": 47, "right": 15, "top": 55}

    assert _ids(client.get("/api/storm-cells", params=box).json()) == ["1", "2", "3"]
    assert _ids(client.get("/api/storm-cells", params={**box, "min_severity": 3}).json()) == ["3"]


def test_rest_a_place_without_a_cell_is_a_200_with_the_reason(client: TestClient) -> None:
    """Dresden has no cell: an answer with no cells, the `no-storm-cells-for-place` warning and a count of 0."""
    response = client.get("/api/storm-cells", params={"latitude": 51.05, "longitude": 13.74, "distance": 10})

    assert response.status_code == 200
    data = response.json()
    assert data["cells"] == []
    assert data["metadata"]["counts"]["rows"] == 0
    (warning,) = data["metadata"]["warnings"]
    assert warning["code"] == "no-storm-cells-for-place"
    assert "3 cells of the scan left out by the request" in warning["message"]


@pytest.mark.parametrize(("fmt", "key"), [("json", "cells"), ("geojson", "features")])
def test_rest_the_empty_answer_of_a_place_is_empty_in_each_json_format(client: TestClient, fmt: str, key: str) -> None:
    """JSON and GeoJSON have the reason in their `metadata` block."""
    data = client.get("/api/storm-cells", params={"latitude": 51.05, "longitude": 13.74, "format": fmt}).json()

    assert data[key] == []
    assert [warning["code"] for warning in data["metadata"]["warnings"]] == ["no-storm-cells-for-place"]


def test_rest_the_empty_answer_of_a_place_in_csv_has_the_reason_in_a_header(client: TestClient) -> None:
    """CSV has no block: the header row alone is the body, and `X-Wetterdienst-Warnings` says why."""
    response = client.get("/api/storm-cells", params={"latitude": 51.05, "longitude": 13.74, "format": "csv"})

    assert response.status_code == 200
    assert response.text.count("\n") == 1
    assert response.headers["x-wetterdienst-warnings"] == "no-storm-cells-for-place"
    assert response.headers["x-wetterdienst-rows"] == "0"


def test_rest_geojson_is_a_feature_collection_with_the_block_after_its_type(client: TestClient) -> None:
    """One feature for each cell, its outline the geometry, `reference_time` beside the block."""
    response = client.get("/api/storm-cells", params={"format": "geojson"})

    data = response.json()
    assert list(data) == ["type", "metadata", "reference_time", "features"]
    assert [feature["geometry"]["type"] for feature in data["features"]] == ["Polygon"] * 3
    assert "geo+json" in response.headers["content-type"] or "json" in response.headers["content-type"]


def test_rest_csv_is_a_row_a_cell(client: TestClient) -> None:
    """The cells as CSV, the licence and the credit line in the headers."""
    response = client.get("/api/storm-cells", params={"format": "csv"})

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert [row["cell_id"] for row in rows] == ["1", "2", "3"]
    assert json.loads(rows[0]["geometry"])["type"] == "Polygon"
    assert len(json.loads(rows[0]["track"])) == 2
    assert response.headers["x-wetterdienst-license"] == "CC-BY-4.0"
    assert "Deutscher" in response.headers["x-wetterdienst-attribution"]


def test_rest_the_track_and_the_geometry_can_be_left_short(client: TestClient) -> None:
    """`track=false` leaves the track out and `geometry=centroid` gives a point: what makes 30 cells fit a tool."""
    full = client.get("/api/storm-cells")
    short = client.get("/api/storm-cells", params={"track": "false", "geometry": "centroid"})

    cell = short.json()["cells"][0]
    assert "track" not in cell
    assert cell["geometry"]["type"] == "Point"
    assert cell["direction_degrees"] == 0.0  # the hand-made cells move due north
    # the hand-made cells have two forecast positions, not twelve: here the track is a third of a cell, not most
    assert len(json.dumps(short.json()["cells"])) < len(json.dumps(full.json()["cells"])) * 0.7


def test_rest_pretty_indents(client: TestClient) -> None:
    """Four spaces, as the other routes."""
    assert "\n    " in client.get("/api/storm-cells", params={"pretty": "true"}).text
    assert "\n" not in client.get("/api/storm-cells").text.rstrip("\n")


@pytest.mark.parametrize(
    "params",
    [
        {"latitude": 50.0},
        {"longitude": 10.0},
        {"distance": 5},
        {"left": 9, "bottom": 49},
        {"latitude": 50.0, "longitude": 10.0, "left": 9, "bottom": 49, "right": 11, "top": 51},
        {"min_severity": 4},
        {"geometry": "polygon"},
        {"format": "parquet"},
        {"bogus": "x"},
        {"date": "2026-07-01"},
    ],
)
def test_rest_a_request_that_asks_for_no_place_is_refused_before_anything_is_read(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, params: dict[str, Any]
) -> None:
    """Half a point, a distance of no point, half a box, both, a bad severity or geometry, or an unknown name."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        msg = "a refused request reached the request"
        raise AssertionError(msg)

    monkeypatch.setattr("wetterdienst.provider.dwd.storm_cells.DwdStormCellsRequest", refuse)

    assert client.get("/api/storm-cells", params=params).status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"timestamp": "yesterday"},
        {"timestamp": "2026-06-01T00:00:00"},
        {"left": 11, "bottom": 49, "right": 9, "top": 51},
        {"left": 9, "bottom": 51, "right": 11, "top": 49},
    ],
)
def test_rest_a_time_before_the_window_or_a_box_that_is_no_box_is_the_callers(
    client: TestClient, params: dict[str, Any]
) -> None:
    """A 400: a time that does not parse, one before DWD's window, a box with its edges the wrong way."""
    assert client.get("/api/storm-cells", params=params).status_code == 400


def test_rest_a_timestamp_selects_a_scan(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """The newest scan at or before the time."""
    serve(monkeypatch, {"KONRAD3D_20260701T120000.xml": three_cells_scan(), "KONRAD3D_20260701T121000.xml": EMPTY_SCAN})

    assert _ids(client.get("/api/storm-cells", params={"timestamp": "2026-07-01T12:05:00"}).json()) == ["1", "2", "3"]
    assert _ids(client.get("/api/storm-cells", params={"timestamp": "2026-07-01T12:15:00"}).json()) == []


def test_rest_a_stale_scan_says_so_in_the_block_and_the_header(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """DWD's run stopped: the empty answer is no all-clear, and the warning says it where a client reads it."""
    serve(monkeypatch, {"KONRAD3D_20260701T120000.xml": EMPTY_SCAN})
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api._now", lambda: dt.datetime(2026, 7, 1, 13, 0, tzinfo=UTC)
    )

    json_response = client.get("/api/storm-cells")
    csv_response = client.get("/api/storm-cells", params={"format": "csv"})

    assert json_response.json()["cells"] == []
    assert [warning["code"] for warning in json_response.json()["metadata"]["warnings"]] == ["scan-stale"]
    assert csv_response.headers["x-wetterdienst-warnings"] == "scan-stale"


def test_rest_the_point_of_a_request_is_in_no_log_line_and_in_the_answer(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """The point is the requester's location: the answer may say it back, the server's log does not."""
    caplog.set_level(logging.DEBUG)

    response = client.get("/api/storm-cells", params={"latitude": 51.0501, "longitude": 13.7401})

    logged = "\n".join(record.getMessage() for record in caplog.records if record.name.startswith("wetterdienst"))
    assert "51.0501" not in logged
    assert "13.7401" not in logged
    assert "no cell of the scan is for the requested place" in logged
    assert "51.0501" in response.json()["metadata"]["warnings"][0]["message"]


def test_the_route_is_described_in_the_openapi_document(client: TestClient) -> None:
    """The place, the severity and the two switches are optional parameters, and the description says what to pass."""
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/storm-cells"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert operation["tags"] == ["Storm cells"]
    for name in ("timestamp", "latitude", "longitude", "distance", "left", "bottom", "right", "top", "min_severity"):
        assert parameters[name]["required"] is False
    assert {"track", "geometry", "format", "pretty"} <= set(parameters)
    for text in ("distance", "track=false", "geometry=centroid", "no-storm-cells-for-place", "scan-stale"):
        assert text in operation["description"]
    assert "/api/storm-cells" not in schema["paths"]  # the alias is no part of the document


class _Raising:
    """Stand in for the request, raising `error` where the scan is read."""

    def __init__(self, error: BaseException) -> None:
        self.error = error

    def __call__(self, **_kwargs: object) -> _Raising:
        return self

    def query(self) -> None:
        raise self.error


def _download_error() -> exceptions.DownloadError:
    return exceptions.DownloadError("https://opendata.dwd.de/weather/radar/konrad3d/x.xml", "404")


@pytest.mark.parametrize(
    ("error", "status"),
    [
        pytest.param(exceptions.InvalidTimeIntervalError("before the window"), 400, id="interval"),
        pytest.param(exceptions.MetaFileNotFoundError("no scan listed"), 502, id="no-scan"),
        pytest.param(exceptions.MetaFileFormatError("cut short"), 502, id="format"),
        pytest.param(_download_error(), 502, id="download"),
        pytest.param(exceptions.NoInternetError("No internet"), 503, id="no-internet"),
        pytest.param(exceptions.ProviderRateLimitError("https://x/", "rate limited", 7), 503, id="rate-limit"),
        pytest.param(ValueError("a defect of the parser"), 500, id="plain-value-error"),
    ],
)
def test_rest_a_failure_is_answered_by_the_hierarchy_and_its_status_is_declared(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, error: BaseException, status: int
) -> None:
    """Every failure is a problem of the status of its place in the hierarchy, and the document declares that status."""
    monkeypatch.setattr("wetterdienst.provider.dwd.storm_cells.DwdStormCellsRequest", _Raising(error))

    response = client.get("/api/v1/storm-cells")

    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    declared = client.get("/openapi.json").json()["paths"]["/api/v1/storm-cells"]["get"]["responses"]
    assert str(status) in declared or status in (500, 503)


# --- the MCP tool ----------------------------------------------------------------------------------------------------


def _tool_call(arguments: dict[str, Any]) -> ToolResult:
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> ToolResult:
        async with Client(build_mcp_server(restapi.app)) as session:
            return await session.call_tool("storm_cells", arguments, raise_on_error=False)

    return asyncio.run(call())


def test_the_mcp_tool_takes_the_place_and_the_switches_and_says_to_pass_one() -> None:
    """The schema of `storm_cells` has them, and its description asks for a point and a distance, or a box."""
    pytest.importorskip("fastmcp")
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def read() -> Any:  # noqa: ANN401
        tools = await build_mcp_server(restapi.app).list_tools()
        return next(tool for tool in tools if tool.name == "storm_cells")

    tool = asyncio.run(read())

    assert {"latitude", "longitude", "distance", "left", "bottom", "right", "top", "min_severity"} <= set(
        tool.parameters["properties"]
    )
    assert {"track", "geometry"} <= set(tool.parameters["properties"])
    assert tool.title == "Get thunderstorm cells"
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.open_world_hint is True
    assert "pass" in tool.description or "Without a place" in tool.description
    assert "``distance``" in tool.description
    assert "``left``" in tool.description


def test_the_mcp_tool_answers_as_the_route_does(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cells of a point and a distance, and the block with the licence."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api._now", lambda: dt.datetime(2026, 7, 1, 12, 6, tzinfo=UTC)
    )
    serve(monkeypatch, THREE)

    result = _tool_call({**IN_BERLIN, "distance": 5, "track": False, "geometry": "centroid"})

    assert not result.is_error, result.content
    assert result.structured_content is not None
    data = result.structured_content["result"]
    assert _ids(data) == ["2"]
    assert data["cells"][0]["geometry"]["type"] == "Point"
    assert "track" not in data["cells"][0]
    assert data["metadata"]["provider"]["license"]["spdx_id"] == "CC-BY-4.0"


def test_the_mcp_tool_is_not_cut_to_the_budget_of_an_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """The answer of a tool of rows is cut to 40,000 characters (`values`, `stations`); a long list of cells is not."""
    from tests.provider.dwd.storm_cells.stubs import cell_xml, scan_xml  # noqa: PLC0415

    cells = [cell_xml(str(n), latitude=50.0 + n * 0.01, longitude=10.0, polygons=None) for n in range(60)]
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api._now", lambda: dt.datetime(2026, 7, 1, 12, 6, tzinfo=UTC)
    )
    serve(monkeypatch, {"KONRAD3D_20260701T120000.xml": scan_xml(("2026-07-01T12:00:00Z", cells))})

    result = _tool_call({})

    assert not result.is_error, result.content
    assert result.structured_content is not None
    data = result.structured_content["result"]
    assert len(data["cells"]) == 60
    assert len(json.dumps(data)) > 40_000
    assert [warning["code"] for warning in data["metadata"]["warnings"]] == []


# --- the command line ------------------------------------------------------------------------------------------------


def test_cli_prints_the_answer_of_the_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cells of a point, the JSON of the route and its metadata."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api._now", lambda: dt.datetime(2026, 7, 1, 12, 6, tzinfo=UTC)
    )
    serve(monkeypatch, THREE)

    result = CliRunner().invoke(
        cli, ["storm-cells", f"--latitude={IN_BERLIN['latitude']}", f"--longitude={IN_BERLIN['longitude']}"]
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert _ids(data) == ["2"]
    assert data["metadata"]["provider"]["license"]["spdx_id"] == "CC-BY-4.0"


def test_cli_is_the_answer_of_rest(client: TestClient) -> None:
    """The same request on the command line and over REST gives the same cells, in each format."""
    rest = client.get("/api/storm-cells", params={"min_severity": 2, "track": "false"}).json()

    result = CliRunner().invoke(cli, ["storm-cells", "--min-severity=2", "--track=false"])

    assert result.exit_code == 0, result.output
    answered = json.loads(result.output)
    for data in (rest, answered):
        data["metadata"]["retrieved_at"] = ""
    assert answered == rest


@pytest.mark.parametrize("fmt", ["geojson", "csv"])
@pytest.mark.usefixtures("served")
def test_cli_formats(fmt: str) -> None:
    """GeoJSON and CSV on stdout."""
    result = CliRunner().invoke(cli, ["storm-cells", f"--format={fmt}"])

    assert result.exit_code == 0, result.output
    if fmt == "geojson":
        assert json.loads(result.output)["type"] == "FeatureCollection"
    else:
        assert result.output.startswith("reference_time,cell_id")


@pytest.mark.usefixtures("served")
def test_cli_a_place_without_a_cell_says_so_in_its_json() -> None:
    """An empty list and the warning that says why, exit 0."""
    result = CliRunner().invoke(cli, ["storm-cells", "--latitude=51.05", "--longitude=13.74"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["cells"] == []
    assert [warning["code"] for warning in data["metadata"]["warnings"]] == ["no-storm-cells-for-place"]


@pytest.mark.parametrize(
    "options",
    [
        ["--latitude=54.3"],
        ["--distance=5"],
        ["--left=9", "--bottom=49"],
        ["--latitude=50", "--longitude=10", "--left=9", "--bottom=49", "--right=11", "--top=51"],
        ["--min-severity=4"],
        ["--geometry=polygon"],
        ["--left=11", "--bottom=49", "--right=9", "--top=51"],
        ["--timestamp=yesterday"],
        ["--latitude=91", "--longitude=10"],
    ],
)
def test_cli_a_request_that_asks_for_no_place_is_a_usage_error(options: list[str]) -> None:
    """The command line's to fix: exit 2, before anything is read."""
    result = CliRunner().invoke(cli, ["storm-cells", *options])

    assert result.exit_code == 2, result.output


@pytest.mark.usefixtures("served")
def test_cli_names_the_options_of_a_half_a_point() -> None:
    """The error is told in the terms of the options."""
    result = CliRunner().invoke(cli, ["storm-cells", "--latitude=54.3"])

    assert "--longitude" in result.output


@pytest.mark.usefixtures("served")
def test_cli_a_time_before_the_window_is_a_usage_error_naming_the_option() -> None:
    """The one refusal of the request's own `query`."""
    result = CliRunner().invoke(cli, ["storm-cells", "--timestamp=2026-06-01T00:00"])

    assert result.exit_code == 2
    assert "--timestamp" in result.output


@pytest.mark.usefixtures("served")
def test_cli_to_a_file_by_its_extension(tmp_path: Any) -> None:  # noqa: ANN401
    """`--target` writes the answer of the format its extension names, and prints nothing."""
    target = tmp_path / "cells.geojson"

    result = CliRunner().invoke(cli, ["storm-cells", f"--target=file://{target}"])

    assert result.exit_code == 0, result.output
    assert result.output == ""
    assert json.loads(target.read_text(encoding="utf8"))["type"] == "FeatureCollection"


def test_cli_a_format_that_disagrees_with_the_extension_is_a_usage_error(tmp_path: Any) -> None:  # noqa: ANN401
    """The extension decides; an explicit `--format` of another one is refused."""
    result = CliRunner().invoke(cli, ["storm-cells", "--format=csv", f"--target=file://{tmp_path / 'cells.json'}"])

    assert result.exit_code == 2
    assert "--format" in result.output


@pytest.mark.parametrize("target", ["cells.txt", "cells.parquet", "duckdb:///x.duckdb?table=t"])
def test_cli_a_target_that_is_no_file_of_the_three_is_refused(target: str) -> None:
    """A database, or a file type of none of the three: a usage error before the fetch."""
    result = CliRunner().invoke(cli, ["storm-cells", f"--target={target}"])

    assert result.exit_code == 2
    assert "file" in result.output


@pytest.mark.usefixtures("served")
def test_cli_with_metadata_needs_a_target() -> None:
    """`--with-metadata` writes beside a file."""
    assert CliRunner().invoke(cli, ["storm-cells", "--with-metadata"]).exit_code == 2


def test_cli_an_empty_scan_still_writes_its_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:  # noqa: ANN401
    """A schedule that rewrites the file must not keep the cells of the run before."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api._now", lambda: dt.datetime(2026, 11, 15, 22, 24, tzinfo=UTC)
    )
    serve(monkeypatch, {"KONRAD3D_20261115T222000.xml": EMPTY_SCAN})
    target = tmp_path / "cells.json"
    target.write_text("old")

    result = CliRunner().invoke(cli, ["storm-cells", f"--target={target}"])

    assert result.exit_code == 0, result.output
    assert json.loads(target.read_text(encoding="utf8"))["cells"] == []


def test_cli_help_names_the_options_and_has_examples() -> None:
    """The options of a place and of the answer, and the examples that the tests of the examples run."""
    output = CliRunner().invoke(cli, ["storm-cells", "--help"]).output

    for option in ("--latitude", "--longitude", "--distance", "--left", "--min-severity", "--track", "--geometry"):
        assert option in output
    assert "wetterdienst storm-cells --latitude=52.52" in output


# --- the surfaces are one --------------------------------------------------------------------------------------------


def test_the_request_of_the_library_is_the_request_of_the_surfaces() -> None:
    """The names of the REST parameters are the arguments of the library's request, and the other way round."""
    import inspect  # noqa: PLC0415

    from wetterdienst.ui.core import StormCellsRequest  # noqa: PLC0415

    taken = set(inspect.signature(DwdStormCellsRequest.__init__).parameters) - {"self", "settings"}
    offered = set(StormCellsRequest.model_fields) - {"format", "pretty"}

    assert taken == offered


def test_the_cells_of_two_blocks_and_a_hand_made_merger_are_served_by_the_route(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """The hand-made scan through the whole stack: two `cells` blocks, an outline in two parts, a missing gust flag."""
    serve(monkeypatch, {"KONRAD3D_20260701T120000.xml": parts_scan()})

    data = client.get("/api/storm-cells").json()

    assert _ids(data) == ["7", "8"]
    assert data["cells"][0]["geometry"]["type"] == "MultiPolygon"
    assert data["cells"][0]["gust_flag"] is None
    assert data["cells"][0]["merge_event"] is True


def test_a_real_scan_through_the_whole_stack(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """The scan of 2026-11-17 22:15 as DWD wrote it: two cells of severity moderate, moving east-north-east."""
    monkeypatch.setattr("wetterdienst.provider.dwd.storm_cells.api._now", lambda: NOW)
    serve(monkeypatch, {"KONRAD3D_20261117T221500.xml": TWO_CELLS_SCAN})

    data = client.get("/api/storm-cells", params={"latitude": 49.05, "longitude": 6.9}).json()

    assert _ids(data) == ["5"]
    cell = data["cells"][0]
    assert cell["severity_label"] == "moderate"
    assert cell["direction_degrees"] == 71.4
    assert len(cell["track"]) == 12
    assert data["reference_time"] == "2026-11-17T22:15:00.000000+00:00"
