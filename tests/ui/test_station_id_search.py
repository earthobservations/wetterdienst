# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A `wmo_id`, a `wigos_id` or an `icao_id` selects the stations that have it, the same ones on every surface.

Python, REST, the command line and MCP answer alike (GH-4070).

One id may be on several stations (NOAA lists a station under two ids, DWD five ICAO codes twice), so a search answers
every station that matches. Served from memory, so nothing leaves the machine.
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
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.ui.cli import cli
from wetterdienst.ui.restapi import app

PARAMETER = "daily/kl/temperature_air_mean_2m"
_SELECTION = {"provider": "dwd", "network": "observation", "parameters": PARAMETER}
WINDOW = "2020-05-01/2020-05-03"

# the id, the name, the ids the station has besides it: wmo, wigos, icao
_ROWS = [
    ("00001", "Berlin-Dahlem", "10381", None, None),
    # the same WMO number on a second station
    ("00002", "Berlin-Dahlem (alt)", "10381", None, None),
    # a number below block 10, which loses its zero where it is a number; the issuer as the source wrote it
    ("00003", "Jan Mayen", "01001", "0-056-101-01002", "ENJA"),
    ("00004", "Hamburg-Fuhlsbüttel", "10147", "0-20000-0-10147", "EDDH"),
    # the same ICAO code on a second station
    ("00005", "Hamburg-Airport", None, None, "EDDH"),
    ("00006", "Dresden-Klotzsche", None, None, None),
]


@pytest.fixture(autouse=True)
def _serve_dwd(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve stations from memory with ids of the three kinds, as a provider that publishes them hands them over."""
    stations = pl.DataFrame(
        {
            "resolution": ["daily"] * len(_ROWS),
            "dataset": ["climate_summary"] * len(_ROWS),
            "station_id": [row[0] for row in _ROWS],
            "name": [row[1] for row in _ROWS],
            "latitude": [52.0] * len(_ROWS),
            "longitude": [13.0] * len(_ROWS),
            "elevation": [50.0] * len(_ROWS),
            "wmo_id": [row[2] for row in _ROWS],
            "wigos_id": [row[3] for row in _ROWS],
            "icao_id": [row[4] for row in _ROWS],
        },
    )
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


def _python(kind: str, **query: str) -> list[str]:
    request = DwdObservationRequest(parameters=PARAMETER, start="2020-05-01", end="2020-05-03", settings=Settings())
    (column, ids), *_ = query.items()
    stations = getattr(request, f"filter_by_{column}")(ids.split(","))
    if kind == "stations":
        return list(dict.fromkeys(stations.df.get_column("station_id")))
    return list(dict.fromkeys(row["station_id"] for row in stations.values().all().df.iter_rows(named=True)))


def _every_surface(kind: str, **query: str) -> dict[str, list[str]]:
    pytest.importorskip("fastmcp")
    # `values` needs a window, which Python has on its request
    window = {"timestamp": WINDOW} if kind == "values" else {}
    return {
        "python": _python(kind, **query),
        "rest": _rest(kind, **query, **window),
        "cli": _cli(kind, **query, **window),
        "mcp": _mcp(kind, **query, **window),
    }


@pytest.mark.parametrize("kind", ["stations", "values"])
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # the number that is on two stations finds both
        pytest.param({"wmo_id": "10381"}, ["00001", "00002"], id="wmo-on-two-stations"),
        # a number below block 10 loses its zero where it is typed as a number
        pytest.param({"wmo_id": "1001"}, ["00003"], id="wmo-without-its-zero"),
        pytest.param({"wmo_id": "01001"}, ["00003"], id="wmo-with-its-zero"),
        # several numbers: the stations of each, in the order of the catalogue
        pytest.param({"wmo_id": "10147,10381"}, ["00001", "00002", "00004"], id="several-wmo-ids"),
        pytest.param({"icao_id": "EDDH"}, ["00004", "00005"], id="icao-on-two-stations"),
        pytest.param({"icao_id": "eddh"}, ["00004", "00005"], id="icao-in-lower-case"),
        pytest.param({"icao_id": "enja,EDDH"}, ["00003", "00004", "00005"], id="several-icao-ids"),
        pytest.param({"wigos_id": "0-20000-0-10147"}, ["00004"], id="wigos"),
        # the station was listed with the issuer `056`: the column has `56`, and so has the search
        pytest.param({"wigos_id": "0-056-101-01002"}, ["00003"], id="wigos-issuer-with-a-zero"),
        pytest.param({"wigos_id": "0-56-101-01002"}, ["00003"], id="wigos-issuer-without-a-zero"),
    ],
)
def test_an_id_selects_every_station_that_has_it_the_same_everywhere(
    kind: str, query: dict[str, str], expected: list[str]
) -> None:
    """Python, REST, the command line and MCP find the same stations, in the order of the catalogue."""
    answers = _every_surface(kind, **query)

    assert answers == dict.fromkeys(answers, expected)


@pytest.mark.parametrize(
    "query",
    [
        # no station has it
        {"wmo_id": "99999"},
        {"icao_id": "XXXX"},
        {"wigos_id": "0-20000-0-99999"},
        # the id of a provider that publishes it for few: the station without one is not found by anything
        {"wmo_id": "00001"},
    ],
)
def test_an_id_no_station_has_is_an_empty_answer_with_a_warning_and_no_error(query: dict[str, str]) -> None:
    """An empty answer is a 200, as for a `stations` id nobody has, and the `metadata` names what was not found."""
    (column, value), *_ = query.items()
    answers = _every_surface("stations", **query)
    assert all(found == [] for found in answers.values())

    response = TestClient(app).get("/api/stations", params={**_SELECTION, **query, "with_metadata": "true"})
    assert response.status_code == 200, response.text
    (warning,) = response.json()["metadata"]["warnings"]
    assert warning["code"] == "unknown-station"
    assert f"No station with {column} {value.upper() if column == 'icao_id' else value}" in warning["message"]


def test_the_ids_are_columns_of_every_station_whichever_the_provider() -> None:
    """The stations come back with the three ids (null where there is none), in the order after `region`."""
    response = TestClient(app).get("/api/stations", params={**_SELECTION, "all": "true"})
    assert response.status_code == 200, response.text
    stations = {row["station_id"]: row for row in response.json()["stations"]}

    assert list(stations["00003"])[-3:] == ["wmo_id", "wigos_id", "icao_id"]
    assert (stations["00003"]["wmo_id"], stations["00003"]["wigos_id"], stations["00003"]["icao_id"]) == (
        "01001",
        # as the core writes it, whatever the provider handed over
        "0-56-101-01002",
        "ENJA",
    )
    assert (stations["00006"]["wmo_id"], stations["00006"]["wigos_id"], stations["00006"]["icao_id"]) == (
        None,
        None,
        None,
    )


def test_the_geojson_of_the_stations_carries_the_ids_in_the_properties() -> None:
    """A feature has the three ids among its properties, null where the station has none."""
    response = TestClient(app).get("/api/stations", params={**_SELECTION, "icao_id": "ENJA", "format": "geojson"})
    assert response.status_code == 200, response.text

    (feature,) = response.json()["data"]["features"]
    assert (feature["properties"]["wmo_id"], feature["properties"]["icao_id"]) == ("01001", "ENJA")


# what is no id of the column is refused, as a latitude beyond 90 is, and no empty answer


@pytest.mark.parametrize(
    ("query", "named"),
    [
        pytest.param({"wmo_id": "abc"}, "wmo_id", id="wmo-letters"),
        pytest.param({"wmo_id": "123456"}, "wmo_id", id="wmo-six-digits"),
        pytest.param({"wigos_id": "06260"}, "wigos_id", id="wigos-a-number"),
        pytest.param({"icao_id": "ED"}, "icao_id", id="icao-two-letters"),
    ],
)
def test_an_id_that_is_none_of_its_column_is_refused_on_every_surface(query: dict[str, str], named: str) -> None:
    """A 422, a usage error, a tool error and a ValueError, each naming the column."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    rest = TestClient(app).get("/api/stations", params={**_SELECTION, **query})
    assert rest.status_code == 422, rest.text
    assert named in rest.text

    result = CliRunner().invoke(
        cli, ["stations", *(f"--{k}={v}".replace("_", "-") for k, v in {**_SELECTION, **query}.items())]
    )
    assert result.exit_code == 2, result.output
    assert named.replace("_", "-") in result.output

    async def call() -> None:
        async with Client(build_mcp_server(app)) as client:
            await client.call_tool("stations", {**_SELECTION, **query})

    with pytest.raises(ToolError, match=named):
        asyncio.run(call())

    request = DwdObservationRequest(parameters=PARAMETER, settings=Settings())
    with pytest.raises(ValueError, match=named):
        getattr(request, f"filter_by_{named}")(next(iter(query.values())))


# the ids are selections of their own, which none is combined with


@pytest.mark.parametrize(
    "selection",
    [
        pytest.param({"wmo_id": "10381", "icao_id": "EDDH"}, id="wmo-and-icao"),
        pytest.param({"wmo_id": "10381", "wigos_id": "0-20000-0-10381"}, id="wmo-and-wigos"),
        pytest.param({"wmo_id": "10381", "stations": "00001"}, id="wmo-and-stations"),
        pytest.param({"icao_id": "EDDH", "name": "Hamburg"}, id="icao-and-name"),
        pytest.param({"wigos_id": "0-20000-0-10147", "all": "true"}, id="wigos-and-all"),
        pytest.param({"wmo_id": "10381", "sql": "name='x'"}, id="wmo-and-sql"),
        pytest.param({"icao_id": "EDDH", "latitude": "52", "longitude": "13", "rank": "2"}, id="icao-and-a-point"),
    ],
)
@pytest.mark.parametrize("kind", ["stations", "values"])
def test_an_id_cannot_be_combined_with_another_selection_on_any_surface(kind: str, selection: dict[str, str]) -> None:
    """The one refusal of two selections, naming the three ids among the alternatives, on every surface."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    window = {"timestamp": WINDOW} if kind == "values" else {}
    rest = TestClient(app).get(f"/api/{kind}", params={**_SELECTION, **window, **selection})
    assert rest.status_code == 422, rest.text
    assert {error["type"] for error in rest.json()["errors"]} == {"mutually_exclusive"}
    assert "wmo_id, wigos_id, icao_id" in rest.json()["detail"]

    args = [f"--{k.replace('_', '-')}={v}" for k, v in {**_SELECTION, **window, **selection}.items()]
    result = CliRunner().invoke(cli, [kind, *args])
    assert result.exit_code == 2, result.output
    assert "'--wmo-id', '--wigos-id', '--icao-id'" in result.output
    assert "cannot be used together" in result.output

    async def call() -> None:
        async with Client(build_mcp_server(app)) as client:
            await client.call_tool(kind, {**_SELECTION, **window, **selection})

    with pytest.raises(ToolError, match="Cannot be combined with"):
        asyncio.run(call())


def test_the_id_search_ignores_the_window_of_the_request_as_a_search_by_station_id_does() -> None:
    """A window selects among the stations of `filter_by_name`; an id names one station, whatever it covers."""
    request = DwdObservationRequest(parameters=PARAMETER, start="1900-01-01", end="1900-01-02", settings=Settings())

    assert request.filter_by_wmo_id(10381).df.get_column("station_id").to_list() == ["00001", "00002"]


@pytest.mark.parametrize(
    ("column", "value", "empty", "full"),
    [("wmo_id", 10381, "00002", "00001"), ("icao_id", "EDDH", "00005", "00004")],
)
def test_a_station_found_by_an_id_that_returned_no_rows_is_told_as_one_named_by_its_station_id_is(
    monkeypatch: pytest.MonkeyPatch, column: str, value: str | int, empty: str, full: str
) -> None:
    """`values` of a station selected by `wmo_id` or `icao_id` that has no reading while its sibling has."""
    from wetterdienst.util.response_warnings import begin_response, recorded_warnings  # noqa: PLC0415

    original = DwdObservationValues._collect_station_parameter_or_dataset  # noqa: SLF001

    def collect(self: object, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401
        frame = original(self, station_id, parameter_or_dataset)
        return frame.clear() if station_id == empty else frame

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    begin_response()
    request = DwdObservationRequest(parameters=PARAMETER, start="2020-05-01", end="2020-05-03", settings=Settings())

    result = getattr(request, f"filter_by_{column}")(value).values().all()

    assert result.df.get_column("station_id").unique().to_list() == [full]
    (warning,) = [w for w in recorded_warnings() if w["code"] == "station-without-rows"]
    assert empty in warning["message"]
    assert full not in warning["message"]
