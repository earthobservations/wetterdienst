# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Which stations an interpolation or a summary was made from, and where they stand (Part of GH-3134).

The stations and their readings are stubbed below `query()`, the way the rest of this package does it, so that the
frames have a known answer and nothing leaves the machine. Six stations stand around a point, and what each of them
reports at six timestamps is laid out so that the stations an answer is made from change from one timestamp to the
next: a station that has a gap and comes back, one that drops out for good, one that stands within the nearby-station
distance, a timestamp too few of them are left to interpolate, and one that none of them reports.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from types import SimpleNamespace
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from click.testing import CliRunner

from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.model.result import (
    InterpolatedValuesResult,
    StationsFilter,
    StationsResult,
    SummarizedValuesResult,
)
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytest.importorskip("shapely")
pytest.importorskip("utm")

UTC = ZoneInfo("UTC")
LATITUDE, LONGITUDE = 50.0, 8.9
#: the elevation the answers are asked at, in metres
ELEVATION = 450.0
PARAMETER = ("hourly", "temperature_air", "temperature_air_2m")
#: what the stations are called here, and where they stand: latitude and longitude offsets from the point, and the
#: elevation. In the order of their distance from the point, which is the order the core walks them in
STATIONS = {
    # within the nearby-station distance (1 km): answers on its own wherever it has a reading
    "00001": (0.003, 0.0, 460.0),
    # the four that surround the point, SW, SE, NE and NW
    "00002": (-0.030, -0.045, 100.0),
    "00003": (-0.030, 0.046, 300.0),
    "00004": (0.031, 0.047, 500.0),
    "00005": (0.032, -0.048, 200.0),
    # south of the point, which with 00003, 00004 and 00005 surrounds it as well
    "00006": (-0.060, 0.001, 700.0),
}
#: the timestamps (by index) each station has a reading for. 00001 has a gap and is back; 00002 drops out for good after
#: the second; at the fifth only 00005 and 00006 are left, which are too few to interpolate, and at the sixth none
PRESENT = {
    "00001": {0, 3},
    "00002": {0, 1},
    "00003": {0, 1, 2},
    "00004": {0, 1, 2},
    "00005": {0, 1, 2, 4},
    "00006": {0, 1, 2, 4},
}
TIMESTAMPS = [dt.datetime(2021, 2, 1, hour, tzinfo=UTC) for hour in range(6)]
#: what each station reads, whatever the hour
READING = {station_id: 5.0 + index for index, station_id in enumerate(STATIONS)}
#: the stations an interpolation is made from at each timestamp, by hand: the nearby one answers alone, the others by
#: the first four around the point that all have a reading
INTERPOLATED_FROM = [
    ["00001"],
    ["00002", "00003", "00004", "00005"],
    ["00003", "00004", "00005", "00006"],
    ["00001"],
    [],
    [],
]
#: the station a summary takes each timestamp from: the nearest with a reading
SUMMARIZED_FROM = ["00001", "00002", "00003", "00001", "00005", None]


def _distance(station_id: str) -> float:
    """Give the great-circle distance of a station from the point in km, worked out here and not by the core."""
    d_lat, d_lon, _ = STATIONS[station_id]
    lat1, lat2 = math.radians(LATITUDE), math.radians(LATITUDE + d_lat)
    d_phi, d_lambda = lat2 - lat1, math.radians(d_lon)
    a = math.sin(d_phi / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lambda / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _stations_frame(*, elevations: bool = True) -> pl.DataFrame:
    """Give the stations of the stub, as a provider lists them: where they stand, with no distance from anywhere."""
    return pl.DataFrame(
        [
            {
                "resolution": "hourly",
                "dataset": "temperature_air",
                "station_id": station_id,
                "latitude": LATITUDE + d_lat,
                "longitude": LONGITUDE + d_lon,
                "elevation": elevation if elevations else None,
                "name": f"Station {station_id}",
                "region": "Hessen",
                "start_timestamp": dt.datetime(1990, 1, 1, tzinfo=UTC),
                "end_timestamp": None,
            }
            for station_id, (d_lat, d_lon, elevation) in STATIONS.items()
        ],
        schema_overrides={"end_timestamp": pl.Datetime("us", "UTC")},
    )


@pytest.fixture
def stubbed(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    """Serve the six stations and their readings in place of the provider's, and give the stations."""
    stations = _stations_frame()

    def _all(self: DwdObservationRequest) -> StationsResult:
        return StationsResult(request=self, df=stations, _df_all=stations, _stations_filter=StationsFilter.ALL)

    def _query(self: DwdObservationValues) -> Iterator[SimpleNamespace]:  # noqa: ARG001
        # one result per station that has any reading, as the real `query()` yields them
        for station_id in STATIONS:
            rows = [
                {
                    "station_id": station_id,
                    "resolution": "hourly",
                    "dataset": "temperature_air",
                    "parameter": "temperature_air_2m",
                    "timestamp": timestamp,
                    "value": READING[station_id],
                    "quality_flags": "10",
                }
                for index, timestamp in enumerate(TIMESTAMPS)
                if index in PRESENT[station_id]
            ]
            if rows:
                yield SimpleNamespace(df=pl.DataFrame(rows), data_updated_at=None)

    monkeypatch.setattr(DwdObservationRequest, "all", _all)
    monkeypatch.setattr(DwdObservationValues, "query", _query)
    return stations


def _request(**options: object) -> DwdObservationRequest:
    return DwdObservationRequest(
        parameters=[PARAMETER], start=TIMESTAMPS[0], end=TIMESTAMPS[-1], options=options or None
    )


def _stations_of(result: InterpolatedValuesResult | SummarizedValuesResult) -> dict[str, dict]:
    """Give the stations of an answer as the JSON of it lists them, by id."""
    stations = json.loads(result.to_json(with_stations=True))["stations"]
    return {station["station_id"]: station for station in stations}


def test_interpolate_names_the_stations_each_row_was_made_from(stubbed: pl.DataFrame) -> None:  # noqa: ARG001
    """The stations of a row are the ones that gave a value at its timestamp, which change from row to row.

    A gap of the nearby station sends the row to the stations around the point, and when it is back the row is its
    again; a station that drops out is not in a later row; with too few left, or none, a row names none and has no
    value.
    """
    result = _request().interpolate((LATITUDE, LONGITUDE), elevation=ELEVATION)
    rows = result.df.sort("timestamp")

    assert rows.get_column("timestamp").to_list() == TIMESTAMPS
    assert rows.get_column("taken_station_ids").to_list() == INTERPOLATED_FROM
    # a station is in a row only where it has a reading for the timestamp
    for timestamp_index, ids in enumerate(INTERPOLATED_FROM):
        assert all(timestamp_index in PRESENT[station_id] for station_id in ids)
    assert [value is None for value in rows.get_column("value").to_list()] == [
        bool(not ids) for ids in INTERPOLATED_FROM
    ]
    assert rows.get_column("distance_mean").to_list()[4:] == [None, None]


def test_interpolate_lists_each_station_once_with_its_distance(stubbed: pl.DataFrame) -> None:  # noqa: ARG001
    """The stations an interpolation names are the ones its rows were made from, each with how far it is away."""
    result = _request().interpolate((LATITUDE, LONGITUDE), elevation=ELEVATION)
    stations = _stations_of(result)

    used = {station_id for ids in INTERPOLATED_FROM for station_id in ids}
    assert set(stations) == used == set(STATIONS)
    assert result.df_stations.get_column("station_id").to_list() == sorted(used)
    for station_id, station in stations.items():
        assert station["distance"] == pytest.approx(_distance(station_id), abs=0.01)
        assert station["elevation_difference"] == ELEVATION - STATIONS[station_id][2]
    # what the row says of the distances follows from the stations: the mean of its stations' distances, and the
    # distance of the one station where a nearby one answered alone
    for ids, distance_mean in zip(
        INTERPOLATED_FROM, result.df.sort("timestamp").get_column("distance_mean").to_list(), strict=True
    ):
        if ids:
            assert distance_mean == pytest.approx(sum(stations[i]["distance"] for i in ids) / len(ids), abs=0.01)
        else:
            assert distance_mean is None


def test_a_nearby_station_reads_as_the_one_station_a_row_was_made_from(stubbed: pl.DataFrame) -> None:  # noqa: ARG001
    """A station within `geo_use_nearby_station_distance` answers alone: its row has the one id and its distance.

    An interpolation needs four, so one id is how a row made from a nearby station reads. Where the station has no
    reading the row is made from the stations around the point, whatever its distance.
    """
    options = {"geo_use_nearby_station_distance": 1.0}
    result = _request(**options).interpolate((LATITUDE, LONGITUDE), elevation=ELEVATION)
    stations = _stations_of(result)
    rows = result.df.sort("timestamp")

    assert stations["00001"]["distance"] < 1.0
    for index in (0, 3):
        row = rows.row(index, named=True)
        assert row["taken_station_ids"] == ["00001"]
        assert row["distance_mean"] == stations["00001"]["distance"]
    assert {len(ids) for ids in rows.filter(pl.col("value").is_not_null()).get_column("taken_station_ids")} == {1, 4}

    # not asked for, every row with a value is a blend of four stations, 00001 among them where it is the nearest
    blended = _request(geo_use_nearby_station_distance=None).interpolate((LATITUDE, LONGITUDE), elevation=ELEVATION)
    sizes = {len(ids) for ids in blended.df.filter(pl.col("value").is_not_null()).get_column("taken_station_ids")}
    assert sizes == {4}


def test_the_elevation_correction_can_be_read_from_the_answer(stubbed: pl.DataFrame) -> None:  # noqa: ARG001
    """A station's `elevation_difference` is the point's elevation less its own, which the correction follows from.

    The nearby station's row is its reading moved by the rate air temperature falls at, per metre, times that
    difference. Without an elevation nothing is corrected, and the difference is null for every station.
    """
    result = _request().interpolate((LATITUDE, LONGITUDE), elevation=ELEVATION)
    station = _stations_of(result)["00001"]
    rate = PARAMETERS["temperature_air_2m"].lapse_rate
    assert rate is not None
    assert station["elevation_difference"] == -10.0
    assert result.df.sort("timestamp").get_column("value")[0] == pytest.approx(
        READING["00001"] - rate * station["elevation_difference"]
    )

    uncorrected = _request().interpolate((LATITUDE, LONGITUDE))
    assert {station["elevation_difference"] for station in _stations_of(uncorrected).values()} == {None}
    assert uncorrected.df.sort("timestamp").get_column("value")[0] == READING["00001"]


def test_summarize_names_the_station_each_row_was_taken_from(stubbed: pl.DataFrame) -> None:  # noqa: ARG001
    """The station of a row is the nearest with a reading at its timestamp, and the stations are the ones taken."""
    result = _request().summarize((LATITUDE, LONGITUDE), elevation=ELEVATION)
    rows = result.df.sort("timestamp")
    stations = _stations_of(result)

    assert rows.get_column("taken_station_id").to_list() == SUMMARIZED_FROM
    assert set(stations) == {station_id for station_id in SUMMARIZED_FROM if station_id}
    # the stations that have a reading and are farther than the one taken are not named, as nothing was taken from them
    assert "00004" not in stations
    assert "00006" not in stations
    for station_id, station in stations.items():
        assert station["distance"] == pytest.approx(_distance(station_id), abs=0.01)
        assert station["elevation_difference"] == ELEVATION - STATIONS[station_id][2]
    for station_id, distance in zip(SUMMARIZED_FROM, rows.get_column("distance").to_list(), strict=True):
        assert distance == (stations[station_id]["distance"] if station_id else None)


@pytest.mark.parametrize("method", ["interpolate", "summarize"])
def test_no_station_at_all_names_no_station(monkeypatch: pytest.MonkeyPatch, method: str) -> None:
    """Where no station has a reading the answer has no rows and no stations, and the stations hold the columns."""
    stations = _stations_frame()

    def _all(self: DwdObservationRequest) -> StationsResult:
        return StationsResult(request=self, df=stations, _df_all=stations, _stations_filter=StationsFilter.ALL)

    def _query(self: DwdObservationValues) -> Iterator[SimpleNamespace]:  # noqa: ARG001
        return iter(())

    monkeypatch.setattr(DwdObservationRequest, "all", _all)
    monkeypatch.setattr(DwdObservationValues, "query", _query)
    result = getattr(_request(), method)((LATITUDE, LONGITUDE), elevation=ELEVATION)

    assert result.df.is_empty()
    assert json.loads(result.to_json(with_stations=True))["stations"] == []
    assert {"distance", "elevation_difference"} <= set(result.df_stations.columns)
    assert result.df_stations.schema["distance"] == pl.Float64


@pytest.mark.parametrize("method", ["interpolate", "summarize"])
def test_files_hold_the_rows_and_the_stations_a_table_of_their_own(stubbed: pl.DataFrame, method: str) -> None:  # noqa: ARG001
    """A CSV holds the rows, with the station ids of a row joined by commas, as ever; the distances are in the stations.

    A row of a file cannot hold the stations as a list of records, so it names them by id, and the table of the stations
    is the result's `stations`, which has the distance of each.
    """
    result = getattr(_request(), method)((LATITUDE, LONGITUDE), elevation=ELEVATION)
    csv = result.to_csv()
    header = csv.splitlines()[0].split(",")
    if method == "interpolate":
        # the mean distance of a row, and the ids of its stations in one field
        assert header[-2:] == ["distance_mean", "taken_station_ids"]
        assert '"00002,00003,00004,00005"' in csv
    else:
        # a summary has one station to a row, and so its distance and id
        assert header[-2:] == ["distance", "taken_station_id"]

    stations = pl.read_csv(result.stations.to_csv().encode(), schema_overrides={"station_id": pl.String})
    assert {"station_id", "distance", "elevation_difference"} <= set(stations.columns)
    assert stations.get_column("distance").null_count() == 0


@pytest.mark.parametrize(
    ("endpoint", "extra"),
    [("/api/interpolate", "taken_station_ids"), ("/api/summarize", "taken_station_id")],
)
def test_rest_answers_with_the_distances_of_the_stations(stubbed: pl.DataFrame, endpoint: str, extra: str) -> None:  # noqa: ARG001
    """The REST API gives the distances with `with_stations`, and an answer without it is the rows it always was."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from wetterdienst.ui.restapi import app  # noqa: PLC0415

    client = TestClient(app)
    params = {
        "provider": "dwd",
        "network": "observation",
        "parameters": "hourly/temperature_air/temperature_air_2m",
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "elevation": ELEVATION,
        "timestamp": "2021-02-01T00:00:00+00:00/2021-02-01T05:00:00+00:00",
    }
    plain = client.get(endpoint, params=params)
    assert plain.status_code == 200, plain.text
    assert "stations" not in plain.json()
    assert extra in plain.json()["values"][1]

    with_stations = client.get(endpoint, params={**params, "with_stations": "true"})
    assert with_stations.status_code == 200, with_stations.text
    body = with_stations.json()
    assert body["values"] == plain.json()["values"]
    for station in body["stations"]:
        assert station["distance"] == pytest.approx(_distance(station["station_id"]), abs=0.01)
        assert station["elevation_difference"] == ELEVATION - STATIONS[station["station_id"]][2]

    geojson = client.get(endpoint, params={**params, "with_stations": "true", "format": "geojson"})
    assert geojson.status_code == 200, geojson.text
    feature = geojson.json()["data"]["features"][0]
    assert {station["station_id"] for station in feature["stations"]} == {s["station_id"] for s in body["stations"]}
    assert all("distance" in station for station in feature["stations"])


@pytest.mark.parametrize("command", ["interpolate", "summarize"])
def test_cli_answers_with_the_distances_of_the_stations(stubbed: pl.DataFrame, command: str) -> None:  # noqa: ARG001
    """The command gives the distances with `--with-stations`, as the REST API does."""
    from wetterdienst.ui.cli import cli  # noqa: PLC0415

    result = CliRunner().invoke(
        cli,
        [
            command,
            "--provider=dwd",
            "--network=observation",
            "--parameters=hourly/temperature_air/temperature_air_2m",
            f"--latitude={LATITUDE}",
            f"--longitude={LONGITUDE}",
            f"--elevation={ELEVATION}",
            "--start=2021-02-01T00:00:00+00:00",
            "--end=2021-02-01T05:00:00+00:00",
            "--with-stations=true",
        ],
    )
    assert result.exit_code == 0, result.output
    stations = json.loads(result.stdout)["stations"]
    assert stations
    for station in stations:
        assert station["distance"] == pytest.approx(_distance(station["station_id"]), abs=0.01)
        assert station["elevation_difference"] == ELEVATION - STATIONS[station["station_id"]][2]


def _stub_precipitation(
    monkeypatch: pytest.MonkeyPatch,
    request_class: type,
    values_class: type,
    parameter: tuple[str, str, str],
    nearby_elevation: float | None,
) -> object:
    """Serve the six stations for a quantity that does not fall with height, the nearby one at `nearby_elevation`.

    Precipitation is not corrected for height, so a station of unknown elevation is not left out of an answer at an
    elevation, and shows what its difference is.
    """
    stations = _stations_frame().with_columns(
        pl.when(pl.col("station_id") == "00001")
        .then(nearby_elevation)
        .otherwise(pl.col("elevation"))
        .alias("elevation")
    )
    resolution, dataset, name = parameter

    def _all(self: object) -> StationsResult:
        return StationsResult(request=self, df=stations, _df_all=stations, _stations_filter=StationsFilter.ALL)

    def _query(self: object) -> Iterator[SimpleNamespace]:  # noqa: ARG001
        for station_id in STATIONS:
            rows = [
                {
                    "station_id": station_id,
                    "resolution": resolution,
                    "dataset": dataset,
                    "parameter": name,
                    "timestamp": timestamp,
                    "value": 1.0 + index,
                    "quality_flags": "10",
                }
                for index, timestamp in enumerate(TIMESTAMPS[:1])
            ]
            yield SimpleNamespace(df=pl.DataFrame(rows), data_updated_at=None)

    monkeypatch.setattr(request_class, "all", _all)
    monkeypatch.setattr(values_class, "query", _query)
    return request_class(parameters=[parameter], start=TIMESTAMPS[0], end=TIMESTAMPS[0])


@pytest.mark.parametrize("method", ["interpolate", "summarize"])
@pytest.mark.parametrize("network", ["dwd_observation", "noaa_ghcn"])
def test_a_station_with_no_elevation_has_no_elevation_difference(
    monkeypatch: pytest.MonkeyPatch, network: str, method: str
) -> None:
    """A station that has no elevation has a null difference, not the point's elevation as if it stood at sea level.

    The nearby station answers (alone, in an interpolation) a quantity that is not corrected for height, so it is not
    left out of the answer at an elevation. DWD lists none for it; GHCN lists 0.0 for the elevation it does not know
    (GH-3708), which is none here as well. The other stations of the answer keep theirs where they are named.
    """
    from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn.api import NoaaGhcnValues  # noqa: PLC0415

    request_class, values_class, parameter, listed = {
        "dwd_observation": (
            DwdObservationRequest,
            DwdObservationValues,
            ("hourly", "precipitation", "precipitation_amount"),
            None,
        ),
        "noaa_ghcn": (NoaaGhcnRequest, NoaaGhcnValues, ("daily", "data", "precipitation_amount"), 0.0),
    }[network]
    request = _stub_precipitation(monkeypatch, request_class, values_class, parameter, listed)

    result = getattr(request, method)((LATITUDE, LONGITUDE), elevation=ELEVATION)

    stations = _stations_of(result)
    assert set(stations) == {"00001"}
    assert stations["00001"]["elevation"] == listed
    assert stations["00001"]["elevation_difference"] is None
    assert stations["00001"]["distance"] == pytest.approx(_distance("00001"), abs=0.01)
    # and a station that has one is placed against the point, so that the null is the station's and not the answer's
    request = _stub_precipitation(monkeypatch, request_class, values_class, parameter, 460.0)
    stations = _stations_of(getattr(request, method)((LATITUDE, LONGITUDE), elevation=ELEVATION))
    assert stations["00001"]["elevation_difference"] == -10.0


def test_the_stations_table_has_the_two_members_in_csv_and_parquet_and_not_in_its_geojson(
    stubbed: pl.DataFrame,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    """The columns reach the files that hold the frame of the stations, not the GeoJSON of a stations result.

    A stations result writes the properties of a station in a feature, which are the core ones and the provider's own.
    The GeoJSON of the answer of `interpolate` and `summarize` is the one that lists the two (the REST test above).
    """
    result = _request().interpolate((LATITUDE, LONGITUDE), elevation=ELEVATION)

    result.stations.to_target(f"file://{tmp_path / 'stations.csv'}")
    result.stations.to_target(f"file://{tmp_path / 'stations.parquet'}")

    assert {"distance", "elevation_difference"} <= set(pl.read_csv(tmp_path / "stations.csv").columns)
    assert {"distance", "elevation_difference"} <= set(pl.read_parquet(tmp_path / "stations.parquet").columns)
    feature = json.loads(result.stations.to_geojson())["data"]["features"][0]
    assert not {"distance", "elevation_difference"} & set(feature["properties"])
