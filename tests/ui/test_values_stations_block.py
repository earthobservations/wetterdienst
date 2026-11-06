# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`with_stations` of `values` lists the stations that have values, through REST and the command line (GH-3818).

The block was the stations of the request, every one the selection named, so a station that returned nothing was
listed, and so was one the `sql_values` filter took every row of. It is `df_stations` now, the stations the GeoJSON
and the `metadata` block (`counts.stations`, `request.stations.ids`) name.

Offline: the selection of the stations and the reader that walks them are stood in for, so the route, the real
collection of the frames (`TimeseriesValues.all`), the SQL filter and the renderer are the real ones.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.model.test_values_stations_block import DAY_ONE, DAY_TWO, pairs, stations_of, values_of
from tests.ui.test_operations import _no_ambient_settings  # noqa: F401
from tests.ui.test_restapi import _OBSERVATION
from wetterdienst.model.result import StationsFilter, StationsResult, ValuesResult
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

#: the query of a request for three stations, which the stood-in selection ignores and the route validates
_VALUES = {
    **_OBSERVATION,
    "stations": "00001,00002,00003",
    "with_stations": "true",
}


def _serve(
    monkeypatch: pytest.MonkeyPatch,
    returned: dict[str, list],
    *,
    stations: StationsResult | None = None,
) -> StationsResult:
    """Select `stations` and have the reader return a frame of values for each of the station ids in `returned`.

    A station of the selection that is not in `returned` is one the source has no reading of: the reader yields
    nothing for it.
    """
    stations = stations or stations_of(["00001", "00002", "00003"])
    frames = {station_id: values_of(stations, {station_id: timestamps}) for station_id, timestamps in returned.items()}

    def query(_reader: object) -> Iterator[ValuesResult]:
        yield from frames.values()

    monkeypatch.setattr("wetterdienst.ui.core.get_stations", lambda **_kwargs: stations)
    monkeypatch.setattr(type(stations.request)._values, "query", query)  # noqa: SLF001
    return stations


@pytest.fixture
def client() -> TestClient:
    """Make a client that answers an unhandled exception as the server does, with its 500."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _station_ids(block: list[dict]) -> list[tuple[str, str]]:
    return [(row["station_id"], row["dataset"]) for row in block]


def test_rest_does_not_list_a_station_that_returned_no_values(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The station the source has no reading of is in the selection and not in the block."""
    stations = _serve(monkeypatch, {"00001": [DAY_ONE, DAY_TWO], "00002": [DAY_TWO]})

    response = client.get("/api/values", params=_VALUES)

    assert response.status_code == 200, response.text
    answer = response.json()
    assert list(answer) == ["metadata", "stations", "values"]
    assert _station_ids(answer["stations"]) == pairs("00001", "00002")
    assert {row["station_id"] for row in answer["values"]} == {"00001", "00002"}
    # the stations of the request are what the `stations` endpoint lists, and the block no longer is that
    assert stations.df.get_column("station_id").n_unique() == 3


def test_rest_lists_the_stations_the_geojson_and_the_metadata_name(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One request, three readings of it: the block, the GeoJSON and the `metadata` block name the same stations."""
    _serve(monkeypatch, {"00001": [DAY_ONE], "00002": [DAY_TWO]})

    block = client.get("/api/values", params={**_VALUES, "with_metadata": "true"}).json()
    geojson = client.get("/api/values", params={**_VALUES, "format": "geojson"}).json()

    in_geojson = [
        (feature["properties"]["id"], feature["properties"]["dataset"]) for feature in geojson["data"]["features"]
    ]
    assert sorted(_station_ids(block["stations"])) == sorted(in_geojson) == pairs("00001", "00002")
    assert block["metadata"]["request"]["stations"]["ids"] == ["00001", "00002"]
    assert block["metadata"]["counts"]["stations"] == 2


def test_rest_lists_the_stations_of_the_rows_the_sql_filter_left(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`sql_values` cuts the rows, and so the stations: 00002 is no longer in the answer, nor in the block."""
    monkeypatch.setenv("WD_RESTAPI_SQL", "true")
    _serve(monkeypatch, {"00001": [DAY_ONE], "00002": [DAY_TWO]})

    answer = client.get("/api/values", params={**_VALUES, "sql_values": "timestamp < '2021-01-02'"}).json()

    assert {row["station_id"] for row in answer["values"]} == {"00001"}
    assert _station_ids(answer["stations"]) == pairs("00001")


def test_rest_lists_the_stations_a_walk_by_rank_took(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A request by rank selects every station with a position; the walk stopped at the two that had data."""
    stations = stations_of(
        ["00001", "00002", "00003", "00004", "00005"], stations_filter=StationsFilter.BY_RANK, rank=2
    )
    _serve(monkeypatch, {"00001": [DAY_ONE], "00002": [DAY_ONE]}, stations=stations)

    answer = client.get("/api/values", params=_VALUES).json()

    assert _station_ids(answer["stations"]) == pairs("00001", "00002")


def test_rest_answers_no_rows_with_the_key_and_an_empty_list(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A request that returned nothing is a 200 with `stations` and `values` both empty, and says so in `counts`."""
    _serve(monkeypatch, {})

    response = client.get("/api/values", params={**_VALUES, "with_metadata": "true"})

    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["stations"] == []
    assert answer["values"] == []
    assert answer["metadata"]["counts"] == {"stations": 0, "rows": 0}


def test_rest_without_with_stations_has_no_block(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The block is still the caller's to ask for."""
    _serve(monkeypatch, {"00001": [DAY_ONE]})

    answer = client.get("/api/values", params={**_VALUES, "with_stations": "false"}).json()

    assert list(answer) == ["metadata", "values"]


def test_the_command_line_lists_the_stations_that_returned_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--with-stations` goes through the same renderer, so it lists what REST does."""
    _serve(monkeypatch, {"00001": [DAY_ONE, DAY_TWO], "00002": [DAY_TWO]})

    result = CliRunner().invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--stations=00001,00002,00003",
            "--with-stations=true",
            "--sql-values=timestamp > '2021-01-01'",
        ],
    )

    assert result.exit_code == 0, result.output
    answer = json.loads(result.stdout)
    assert _station_ids(answer["stations"]) == pairs("00001", "00002")
    assert {row["station_id"] for row in answer["values"]} == {"00001", "00002"}
