# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`region` selects the stations their source lists under it, the same ones on every surface (GH-4418).

Python, REST, the command line and MCP answer alike. The region is the source's: DWD's `Hamburg` also holds the
stations at sea. An unknown region is refused with the ones there are, a network whose stations have no region says
so, and `region` is one of the exclusive selections. Served from memory, so nothing leaves the machine.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import polars as pl
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from wetterdienst import Settings
from wetterdienst.exceptions import NoRegionsError, UnknownRegionError
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.ui.cli import cli
from wetterdienst.ui.restapi import app

PARAMETER = "daily/kl/temperature_air_mean_2m"
_SELECTION = {"provider": "dwd", "network": "observation", "parameters": PARAMETER}
WINDOW = "2020-05-01/2020-05-03"

# the id, the name, the region, the latitude, the longitude: the stations of Hamburg as DWD lists them, among them a
# lightship (UFS Deutsche Bucht) and a buoy (Nordseeboje 2) at sea, and stations of other regions
_ROWS = [
    ("00954", "UFS Deutsche Bucht", "Hamburg", 54.1796, 7.4587),
    ("01975", "Hamburg-Fuhlsbüttel", "Hamburg", 53.6332, 9.9881),
    ("01981", "Hamburg-Neuwiedenthal", "Hamburg", 53.4776, 9.8957),
    ("13904", "Nordseeboje 2", "Hamburg", 55.0, 6.3333),
    ("00691", "Bremen", "Bremen", 53.0451, 8.7979),
    ("00427", "Stuttgart", "Baden-Württemberg", 48.8281, 9.2000),
    ("00183", "Zingst", "Mecklenburg-Vorpommern", 54.4333, 12.7333),
    ("99999", "Without a region", None, 50.0, 10.0),
]


def _stations(regions: list[str | None] | None = None) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "resolution": ["daily"] * len(_ROWS),
            "dataset": ["climate_summary"] * len(_ROWS),
            "station_id": [row[0] for row in _ROWS],
            "name": [row[1] for row in _ROWS],
            "region": regions if regions is not None else [row[2] for row in _ROWS],
            "latitude": [row[3] for row in _ROWS],
            "longitude": [row[4] for row in _ROWS],
            "elevation": [10.0] * len(_ROWS),
        },
        schema_overrides={"region": pl.String},
    )


@pytest.fixture(autouse=True)
def _serve_dwd(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve stations with their regions from memory, and a three-day series for each."""
    stations = _stations()
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: stations.lazy())

    def collect(self: object, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401, ARG001
        import datetime as dt  # noqa: PLC0415

        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        names = [parameter.name_original for parameter in dataset]
        days = [dt.datetime(2020, 5, 1, tzinfo=dt.UTC) + dt.timedelta(days=offset) for offset in range(3)]
        rows = len(days) * len(names)
        return pl.DataFrame(
            {
                "timestamp": [day for day in days for _ in names],
                "parameter": names * len(days),
                "value": [1.0] * rows,
                "quality_flags": ["1"] * rows,
                "resolution": ["daily"] * rows,
                "dataset": [dataset.name] * rows,
            },
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


def _ids(answer: dict[str, Any], kind: str) -> list[str]:
    return list(dict.fromkeys(row["station_id"] for row in answer[kind]))


def _rest(kind: str, **query: str) -> list[str]:
    response = TestClient(app).get(f"/api/{kind}", params={**_SELECTION, **query})
    assert response.status_code == 200, response.text
    return _ids(response.json(), kind)


def _cli(kind: str, **query: str) -> list[str]:
    args = [f"--{key.replace('_', '-')}={value}" for key, value in {**_SELECTION, **query}.items()]
    result = CliRunner().invoke(cli, [kind, *args])
    assert result.exit_code == 0, result.output
    return _ids(json.loads(result.stdout), kind)


def _mcp(kind: str, **query: str) -> list[str]:
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> dict[str, Any]:
        async with Client(build_mcp_server(app)) as client:
            result = await client.call_tool(kind, {**_SELECTION, **query})
            answer = result.structured_content
            assert answer is not None
            return answer.get("result", answer)

    return _ids(asyncio.run(call()), kind)


def _python(kind: str, region: str) -> list[str]:
    request = DwdObservationRequest(parameters=PARAMETER, start="2020-05-01", end="2020-05-03", settings=Settings())
    stations = request.filter_by_region(region.split(","))
    if kind == "stations":
        return list(dict.fromkeys(stations.df.get_column("station_id")))
    return list(dict.fromkeys(row["station_id"] for row in stations.values().all().df.iter_rows(named=True)))


def _every_surface(kind: str, region: str) -> dict[str, list[str]]:
    pytest.importorskip("fastmcp")
    # `values` needs a window, which Python has on its request
    window = {"timestamp": WINDOW} if kind == "values" else {}
    return {
        "python": _python(kind, region),
        "rest": _rest(kind, region=region, **window),
        "cli": _cli(kind, region=region, **window),
        "mcp": _mcp(kind, region=region, **window),
    }


@pytest.mark.parametrize("kind", ["stations", "values"])
@pytest.mark.parametrize(
    ("region", "expected"),
    [
        # the region of the source, the stations at sea included, in the order of the catalogue
        pytest.param("Hamburg", ["00954", "01975", "01981", "13904"], id="a-region-with-stations-at-sea"),
        pytest.param("hamburg", ["00954", "01975", "01981", "13904"], id="any-case"),
        pytest.param("Bremen", ["00691"], id="one-station"),
        # the accent as it is typed without one, in the two ways, and the break between words
        pytest.param("Baden-Wuerttemberg", ["00427"], id="umlaut-written-out"),
        pytest.param("baden wurttemberg", ["00427"], id="umlaut-dropped-and-a-space"),
        # several, comma-separated: each station once, in the order of the catalogue
        pytest.param("Bremen,Hamburg", ["00954", "01975", "01981", "13904", "00691"], id="several-regions"),
        pytest.param("Hamburg,hamburg", ["00954", "01975", "01981", "13904"], id="one-region-twice"),
    ],
)
def test_a_region_selects_every_station_listed_under_it_the_same_everywhere(
    kind: str, region: str, expected: list[str]
) -> None:
    """Python, REST, the command line and MCP find the same stations."""
    answers = _every_surface(kind, region)

    assert answers == dict.fromkeys(answers, expected)


def test_a_region_is_a_list_on_every_surface_as_the_stations_are() -> None:
    """A list as REST's repeated parameter and as MCP's array."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    response = TestClient(app).get(
        "/api/stations", params=[*_SELECTION.items(), ("region", "Bremen"), ("region", "Hamburg")]
    )
    assert response.status_code == 200, response.text
    assert _ids(response.json(), "stations") == ["00954", "01975", "01981", "13904", "00691"]

    async def call() -> dict[str, Any]:
        async with Client(build_mcp_server(app)) as client:
            result = await client.call_tool("stations", {**_SELECTION, "region": ["Bremen", "Hamburg"]})
            assert result.structured_content is not None
            return result.structured_content.get("result", result.structured_content)

    assert _ids(asyncio.run(call()), "stations") == ["00954", "01975", "01981", "13904", "00691"]


def test_the_answer_names_the_stations_at_sea_with_their_positions() -> None:
    """The region is the source's, so the answer holds what the source files there, with where each stands."""
    response = TestClient(app).get("/api/stations", params={**_SELECTION, "region": "Hamburg", "format": "json"})
    stations = {row["station_id"]: row for row in response.json()["stations"]}

    assert (stations["00954"]["name"], stations["00954"]["latitude"], stations["00954"]["longitude"]) == (
        "UFS Deutsche Bucht",
        54.1796,
        7.4587,
    )
    assert {row["region"] for row in stations.values()} == {"Hamburg"}


def test_the_stations_answer_says_the_selection_was_by_region() -> None:
    """The `metadata` block names how the stations were selected."""
    response = TestClient(app).get("/api/stations", params={**_SELECTION, "region": "Bremen", "with_metadata": "true"})

    assert response.json()["metadata"]["request"]["stations"]["filter"] == "by_region"


def test_a_window_cuts_a_listing_by_region_and_never_an_unknown_region() -> None:
    """A region none of whose stations has a record in the window is an empty list, which it is not an error to ask."""
    stations = _stations().with_columns(
        pl.lit(None, pl.Datetime("us", "UTC")).alias("start_timestamp"),
        pl.when(pl.col("region") == "Bremen")
        .then(pl.lit(None, pl.Datetime("us", "UTC")))
        .otherwise(pl.datetime(1960, 1, 1, time_zone="UTC", time_unit="us"))
        .alias("end_timestamp"),
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(DwdObservationRequest, "_all", lambda _self: stations.lazy())
        response = TestClient(app).get("/api/stations", params={**_SELECTION, "region": "Hamburg", "timestamp": "2020"})
        still_open = TestClient(app).get(
            "/api/stations", params={**_SELECTION, "region": "Bremen", "timestamp": "2020"}
        )

    assert response.status_code == 200, response.text
    assert response.json()["stations"] == []
    assert _ids(still_open.json(), "stations") == ["00691"]


# an unknown region is refused, with the regions there are


_KNOWN = "Baden-Württemberg, Bremen, Hamburg, Mecklenburg-Vorpommern"


def test_an_unknown_region_is_refused_on_every_surface_with_the_regions_there_are() -> None:
    """A 400, a usage error, a tool error and an `UnknownRegionError`, each naming the region and the ones there are."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    query = {**_SELECTION, "region": "Hamburgg"}
    rest = TestClient(app).get("/api/stations", params=query)
    assert rest.status_code == 400, rest.text
    assert rest.json()["type"] == "urn:wetterdienst:problem:request-refused"
    assert "no station in the region 'Hamburgg'" in rest.json()["detail"]
    assert "Closest: 'Hamburgg': 'Hamburg'." in rest.json()["detail"]
    assert f"The regions there are: {_KNOWN}." in rest.json()["detail"]

    result = CliRunner().invoke(cli, ["stations", *(f"--{k}={v}" for k, v in query.items())])
    assert result.exit_code == 2, result.output
    assert "no station in the region 'Hamburgg'" in result.output
    assert _KNOWN in result.output

    async def call() -> None:
        async with Client(build_mcp_server(app)) as client:
            await client.call_tool("stations", query)

    with pytest.raises(ToolError, match=f"The regions there are: {_KNOWN}"):
        asyncio.run(call())

    request = DwdObservationRequest(parameters=PARAMETER, settings=Settings())
    with pytest.raises(UnknownRegionError, match="no station in the region 'Hamburgg'") as error:
        request.filter_by_region("Hamburgg")
    assert error.value.known == ["Baden-Württemberg", "Bremen", "Hamburg", "Mecklenburg-Vorpommern"]


def test_an_unknown_region_in_values_is_refused_before_anything_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal is the lookup's, so no value is collected."""
    collected = []
    monkeypatch.setattr(
        DwdObservationValues,
        "_collect_station_parameter_or_dataset",
        lambda *_args: collected.append(1),
    )

    response = TestClient(app).get("/api/values", params={**_SELECTION, "region": "Atlantis", "timestamp": WINDOW})

    assert response.status_code == 400, response.text
    assert "no station in the region 'Atlantis'" in response.json()["detail"]
    assert not collected


def test_one_unknown_region_among_known_ones_refuses_the_request() -> None:
    """The stations of the known ones are not answered with the unknown one dropped without a word."""
    response = TestClient(app).get("/api/stations", params={**_SELECTION, "region": "Hamburg,Atlantis"})

    assert response.status_code == 400, response.text
    assert "'Atlantis'" in response.json()["detail"]
    assert "'Hamburg'" not in response.json()["detail"].split("The regions there are")[0]


@pytest.mark.parametrize("surface", ["rest", "cli"])
def test_a_network_whose_stations_have_no_region_is_refused_with_that_reason(
    monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    """Not 'an unknown region': the network has none, and the answer says what to select by instead."""
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: _stations([None] * len(_ROWS)).lazy())

    if surface == "rest":
        response = TestClient(app).get("/api/stations", params={**_SELECTION, "region": "Hamburg"})
        assert response.status_code == 400, response.text
        detail = response.json()["detail"]
    else:
        result = CliRunner().invoke(
            cli, ["stations", *(f"--{k}={v}" for k, v in {**_SELECTION, "region": "Hamburg"}.items())]
        )
        assert result.exit_code == 2, result.output
        detail = result.output

    assert "lists no region" in detail
    assert "no station in the region" not in detail
    assert "`name`, a point or a bounding box" in detail

    request = DwdObservationRequest(parameters=PARAMETER, settings=Settings())
    with pytest.raises(NoRegionsError, match="lists no region"):
        request.filter_by_region("Hamburg")


@pytest.mark.parametrize("query", [{"region": ""}, {"region": " , "}])
def test_a_blank_region_selects_nothing_so_the_request_makes_no_selection(query: dict[str, str]) -> None:
    """As an empty `stations=` does: it is no selection, and one is required."""
    response = TestClient(app).get("/api/stations", params={**_SELECTION, **query})

    assert response.status_code == 422, response.text
    assert {error["type"] for error in response.json()["errors"]} == {"missing_one_of"}


def test_a_python_region_that_is_blank_or_no_text_is_refused() -> None:
    """A `ValueError` for no region, a `TypeError` for a number."""
    request = DwdObservationRequest(parameters=PARAMETER, settings=Settings())

    with pytest.raises(ValueError, match="region"):
        request.filter_by_region(" ")
    with pytest.raises(TypeError, match="region has to be a text"):
        request.filter_by_region([1])  # ty: ignore[invalid-argument-type]


def test_the_library_selects_among_the_whole_list_whatever_the_window() -> None:
    """As `filter_by_station_id` does: a region with no station in the window is a region, not an unknown one."""
    request = DwdObservationRequest(parameters=PARAMETER, start="1900-01-01", end="1900-01-02", settings=Settings())

    assert request.filter_by_region("Bremen").df.get_column("station_id").to_list() == ["00691"]


# the region is a selection of its own, which none is combined with


@pytest.mark.parametrize(
    "selection",
    [
        pytest.param({"region": "Hamburg", "stations": "01975"}, id="region-and-stations"),
        pytest.param({"region": "Hamburg", "name": "Hamburg"}, id="region-and-name"),
        pytest.param({"region": "Hamburg", "wmo_id": "10147"}, id="region-and-wmo"),
        pytest.param({"region": "Hamburg", "all": "true"}, id="region-and-all"),
        pytest.param({"region": "Hamburg", "latitude": "53", "longitude": "10", "rank": "2"}, id="region-and-a-point"),
        pytest.param(
            {"region": "Hamburg", "left": "9", "bottom": "53", "right": "10", "top": "54"}, id="region-and-a-box"
        ),
    ],
)
@pytest.mark.parametrize("kind", ["stations", "values"])
def test_a_region_cannot_be_combined_with_another_selection_on_any_surface(
    kind: str, selection: dict[str, str]
) -> None:
    """The one refusal of two selections, naming `region` among the alternatives, on every surface."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    window = {"timestamp": WINDOW} if kind == "values" else {}
    rest = TestClient(app).get(f"/api/{kind}", params={**_SELECTION, **window, **selection})
    assert rest.status_code == 422, rest.text
    assert {error["type"] for error in rest.json()["errors"]} == {"mutually_exclusive"}
    assert "name, region, (latitude and longitude)" in rest.json()["detail"]

    args = [f"--{k.replace('_', '-')}={v}" for k, v in {**_SELECTION, **window, **selection}.items()]
    result = CliRunner().invoke(cli, [kind, *args])
    assert result.exit_code == 2, result.output
    assert "'--name', '--region'" in result.output
    assert "cannot be used together" in result.output

    async def call() -> None:
        async with Client(build_mcp_server(app)) as client:
            await client.call_tool(kind, {**_SELECTION, **window, **selection})

    with pytest.raises(ToolError, match="Cannot be combined with"):
        asyncio.run(call())


@pytest.mark.parametrize("extra", [{"rank": "3"}, {"distance": "10"}])
def test_a_rank_and_a_distance_are_no_part_of_a_selection_by_region(extra: dict[str, str]) -> None:
    """`rank` goes with a point or a name, `distance` with a point: neither narrows a region."""
    response = TestClient(app).get("/api/stations", params={**_SELECTION, "region": "Hamburg", **extra})

    assert response.status_code == 422, response.text


@pytest.mark.parametrize("route", ["interpolate", "summarize", "history"])
def test_region_is_not_offered_by_the_routes_that_take_no_selection_of_stations(route: str) -> None:
    """Interpolate and summarize take a point or a station and history ids: `region` is a parameter they do not know."""
    params = {**_SELECTION, "region": "Hamburg", "timestamp": WINDOW, "latitude": "53", "longitude": "10"}
    if route == "history":
        params = {**_SELECTION, "region": "Hamburg", "all": "true"}

    response = TestClient(app).get(f"/api/{route}", params=params)

    assert response.status_code == 422, response.text
    assert any(error["loc"][-1] == "region" for error in response.json()["errors"])
