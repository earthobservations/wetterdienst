# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The `stations` block of a values result lists the stations that have values, as `df_stations` does (GH-3818).

`to_dict(with_stations=True)` and `to_json` through it listed `stations.df`, every station of the request, while
`df_stations` and the GeoJSON name the stations that have a row in `df`. After `filtered_by_date` or
`filtered_by_sql`, or for a request by rank whose walk stopped early, the block therefore listed stations the
`values` have no row of. Served from memory, so nothing leaves the machine.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json

import polars as pl
import pytest

from wetterdienst.model.result import (
    InterpolatedValuesResult,
    StationsFilter,
    StationsResult,
    SummarizedValuesResult,
    ValuesResult,
)
from wetterdienst.provider.dwd.observation import DwdObservationRequest

UTC = dt.UTC
DAY_ONE = dt.datetime(2021, 1, 1, tzinfo=UTC)
DAY_TWO = dt.datetime(2021, 1, 2, tzinfo=UTC)
DATASETS = ("climate_summary", "precipitation_more")
PARAMETERS = {"climate_summary": "temperature_air_mean_2m", "precipitation_more": "precipitation_height"}
STATION_COLUMNS = [
    "resolution",
    "dataset",
    "station_id",
    "start_timestamp",
    "end_timestamp",
    "latitude",
    "longitude",
    "elevation",
    "name",
    "region",
]


def request_of_two_datasets() -> DwdObservationRequest:
    """Give the request the `metadata` block is read off: the two daily datasets the frames below hold, for two days."""
    return DwdObservationRequest(
        parameters=[("daily", dataset) for dataset in DATASETS], start="2021-01-01", end="2021-01-02"
    )


def with_frame(stations: StationsResult, df: pl.DataFrame) -> StationsResult:
    """Give `stations` with another frame, as a listing of stations is built from."""
    return dataclasses.replace(stations, df=df)


def stations_of(
    ids: list[str],
    *,
    datasets: tuple[str, ...] = DATASETS,
    stations_filter: StationsFilter = StationsFilter.BY_STATION_ID,
    rank: int | None = None,
) -> StationsResult:
    """Give the stations of a request: one row per resolution, dataset and station, the nearest station first."""
    rows = [
        {
            "resolution": "daily",
            "dataset": dataset,
            "station_id": station_id,
            "start_timestamp": dt.datetime(1950 + i, 1, 1, tzinfo=UTC),
            "end_timestamp": dt.datetime(2030, 12, 31, tzinfo=UTC) if i % 2 else None,
            "latitude": 50.0 + i / 100,
            "longitude": 8.9,
            "elevation": 100.0 + i,
            "name": f"Station {station_id}",
            "region": "Hessen",
        }
        for i, station_id in enumerate(ids)
        for dataset in datasets
    ]
    df = pl.DataFrame(
        rows,
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
            "region": pl.String,
        },
    )
    return StationsResult(
        request=request_of_two_datasets(), df=df, _df_all=df, _stations_filter=stations_filter, _rank=rank
    )


def values_of(stations: StationsResult, rows: dict[str, list[dt.datetime]]) -> ValuesResult:
    """Give the values result of `stations` with a row at each of the timestamps, of each dataset, of each station."""
    frame = pl.DataFrame(
        [
            {
                "station_id": station_id,
                "resolution": "daily",
                "dataset": dataset,
                "parameter": PARAMETERS[dataset],
                "timestamp": timestamp,
                "value": 1.0,
                "quality_flags": None,
            }
            for station_id, timestamps in rows.items()
            for dataset in DATASETS
            for timestamp in timestamps
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
    )
    return ValuesResult(stations=stations, df=frame)


def listed(result: ValuesResult | InterpolatedValuesResult | SummarizedValuesResult) -> list[tuple[str, str]]:
    """Give the (station id, dataset) of each row of the block, in its order."""
    return [(row["station_id"], row["dataset"]) for row in result.to_dict(with_stations=True)["stations"]]


def pairs(*ids: str) -> list[tuple[str, str]]:
    """Give the rows of the block for these stations: one for each dataset, in the order of the stations."""
    return [(station_id, dataset) for station_id in ids for dataset in DATASETS]


def three_stations_one_of_them_empty() -> ValuesResult:
    """Give the values of three stations in two datasets, of the last of which the source has no reading."""
    return values_of(
        stations_of(["00001", "00002", "00003"]),
        {"00001": [DAY_ONE, DAY_TWO], "00002": [DAY_TWO]},
    )


def test_a_station_that_returned_no_values_is_not_listed() -> None:
    """A station of the request with no row is in `stations.df` and not in the block, nor in `df_stations`."""
    result = three_stations_one_of_them_empty()

    assert result.stations.df.get_column("station_id").unique().sort().to_list() == ["00001", "00002", "00003"]
    assert listed(result) == pairs("00001", "00002")
    assert result.df_stations.get_column("station_id").unique(maintain_order=True).to_list() == ["00001", "00002"]


def test_the_block_is_df_stations_written_as_a_listing_of_stations_is() -> None:
    """The rows are those of `df_stations`: the same columns in the same order, the timestamps as text."""
    result = three_stations_one_of_them_empty()

    block = result.to_dict(with_stations=True)["stations"]

    assert block == with_frame(result.stations, result.df_stations).to_dict()["stations"]
    assert [list(row) for row in block] == [STATION_COLUMNS] * 4
    assert block[0]["start_timestamp"] == "1950-01-01T00:00:00.000000+00:00"
    assert block[0]["end_timestamp"] is None
    assert block[2]["end_timestamp"] == "2030-12-31T00:00:00.000000+00:00"


def test_a_station_of_several_datasets_is_listed_once_for_each() -> None:
    """The frame holds a row per resolution, dataset and station, and so does the block: none is dropped or doubled."""
    rows = listed(three_stations_one_of_them_empty())

    assert rows == pairs("00001", "00002")
    assert len(rows) == len(set(rows))


def test_the_block_names_the_stations_the_geojson_does() -> None:
    """The three ways of reading one result name the same stations, a dataset of each at a time."""
    result = three_stations_one_of_them_empty()

    in_geojson = [
        (feature["properties"]["id"], feature["properties"]["dataset"])
        for feature in result.to_ogc_feature_collection()["data"]["features"]
    ]
    in_df_stations = list(result.df_stations.select("station_id", "dataset").iter_rows())

    assert sorted(listed(result)) == sorted(in_geojson) == sorted(in_df_stations) == pairs("00001", "00002")


def test_filtered_by_date_lists_the_stations_of_the_rows_left() -> None:
    """A result cut to a day lists the stations that have a row on it, and not the ones the cut took every row of."""
    result = three_stations_one_of_them_empty()

    cut = result.filtered_by_date("2021-01-01")

    assert cut.df.get_column("station_id").unique().to_list() == ["00001"]
    assert listed(cut) == pairs("00001")
    # the result that was cut is left as it was
    assert listed(result) == pairs("00001", "00002")


def test_filtered_by_sql_lists_the_stations_of_the_rows_left() -> None:
    """The same for a WHERE clause."""
    cut = three_stations_one_of_them_empty().filtered_by_sql("station_id = '00002'")

    assert listed(cut) == pairs("00002")


def test_a_cut_that_keeps_every_row_keeps_every_station() -> None:
    """A filter that drops no row leaves the block as it was."""
    result = three_stations_one_of_them_empty()

    assert listed(result.filtered_by_date("2021-01")) == listed(result) == pairs("00001", "00002")


def test_a_walk_by_rank_that_stopped_early_lists_the_stations_it_took() -> None:
    """A request by rank keeps every station with a position in `stations.df`; the walk stops at the ones with data."""
    stations = stations_of(
        ["00001", "00002", "00003", "00004", "00005"], stations_filter=StationsFilter.BY_RANK, rank=2
    )
    result = values_of(stations, {"00001": [DAY_ONE], "00002": [DAY_ONE]})

    assert stations.df.get_column("station_id").n_unique() == 5
    assert listed(result) == pairs("00001", "00002")


def test_a_result_with_no_rows_has_the_key_and_an_empty_list() -> None:
    """Where nothing returned, the block is there and empty, and `values` too: not a missing key."""
    result = values_of(stations_of(["00001", "00002"]), {})

    answer = result.to_dict(with_stations=True)

    assert list(answer) == ["stations", "values"]
    assert answer["stations"] == []
    assert answer["values"] == []
    assert json.loads(result.to_json(with_stations=True)) == {"stations": [], "values": []}
    # the stations of the request are still there to read
    assert result.stations.df.height == 4


def test_a_result_cut_to_nothing_has_the_key_and_an_empty_list() -> None:
    """A filter that takes every row takes the stations: the block was the whole request's before."""
    cut = three_stations_one_of_them_empty().filtered_by_sql("value > 1000")

    assert cut.df.is_empty()
    assert cut.to_dict(with_stations=True) == {"stations": [], "values": []}


def test_a_frame_with_no_station_column_has_an_empty_block() -> None:
    """A frame that names no station gives an empty block, and not an error."""
    result = ValuesResult(stations=stations_of(["00001"]), df=pl.DataFrame())

    assert result.to_dict(with_stations=True) == {"stations": [], "values": []}


def test_the_block_keeps_its_place_between_the_metadata_and_the_values() -> None:
    """The keys come in the order they did."""
    result = three_stations_one_of_them_empty()

    assert list(result.to_dict(with_metadata=True, with_stations=True)) == ["metadata", "stations", "values"]
    assert list(result.to_dict(with_stations=False)) == ["values"]


def test_to_json_writes_the_block_to_dict_returns() -> None:
    """`to_json` reads the stations through `to_dict`, so it lists the same."""
    result = three_stations_one_of_them_empty().filtered_by_date("2021-01-02")

    written = json.loads(result.to_json(with_stations=True))

    assert written == json.loads(json.dumps(result.to_dict(with_stations=True)))
    assert {row["station_id"] for row in written["stations"]} == {"00001", "00002"}
    first_day = three_stations_one_of_them_empty().filtered_by_date("2021-01-01")
    assert [row["station_id"] for row in json.loads(first_day.to_json(with_stations=True))["stations"]] == [
        "00001",
        "00001",
    ]


def test_to_format_json_lists_the_stations_that_have_values() -> None:
    """The route REST, the command line and the MCP tools write the JSON by."""
    result = three_stations_one_of_them_empty().filtered_by_date("2021-01-01")

    written = json.loads(result.to_format("json", with_stations=True))

    assert [row["station_id"] for row in written["stations"]] == ["00001", "00001"]


# The estimates: their `stations` is already the stations the rows were made from, cut down by the filters (GH-3814),
# so the block is that listing as it was, with the `distance` and the `elevation_difference` of each (GH-3807).


def estimate_stations() -> StationsResult:
    """Give the stations an estimate was made from, each with where it stands against the point."""
    stations = stations_of(["00001", "00002", "00003"], datasets=("climate_summary",))
    return with_frame(
        stations,
        stations.df.with_columns(
            pl.Series("distance", [1.5, 2.5, 3.5]),
            pl.Series("elevation_difference", [10.0, None, -5.0], dtype=pl.Float64),
        ),
    )


def an_interpolation() -> InterpolatedValuesResult:
    """Give two rows, the first made from 00001 alone and the second from the other two."""
    df = pl.DataFrame(
        {
            "station_id": ["abc", "abc"],
            "resolution": ["daily", "daily"],
            "dataset": ["climate_summary", "climate_summary"],
            "parameter": ["temperature_air_mean_2m"] * 2,
            "timestamp": [DAY_ONE, DAY_TWO],
            "value": [1.0, 2.0],
            "distance_mean": [1.5, 3.0],
            "taken_station_ids": [["00001"], ["00002", "00003"]],
        },
        schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")},
    )
    return InterpolatedValuesResult(stations=estimate_stations(), df=df, latlon=(50.0, 8.9))


def a_summary() -> SummarizedValuesResult:
    """Give two rows, the first taken from 00001 and the second from 00003."""
    df = pl.DataFrame(
        {
            "station_id": ["abc", "abc"],
            "resolution": ["daily", "daily"],
            "dataset": ["climate_summary", "climate_summary"],
            "parameter": ["temperature_air_mean_2m"] * 2,
            "timestamp": [DAY_ONE, DAY_TWO],
            "value": [1.0, 2.0],
            "distance": [1.5, 3.5],
            "taken_station_id": ["00001", "00003"],
        },
        schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")},
    )
    return SummarizedValuesResult(stations=estimate_stations(), df=df, latlon=(50.0, 8.9))


@pytest.mark.parametrize("make", [an_interpolation, a_summary])
def test_an_estimate_lists_its_stations_with_their_distance_and_elevation_difference(make) -> None:  # noqa: ANN001
    """An estimate lists its stations as it did: their columns, with the `distance` and the `elevation_difference`."""
    result = make()

    block = result.to_dict(with_stations=True)["stations"]

    assert block == result.stations.to_dict()["stations"]
    assert [list(row) for row in block] == [[*STATION_COLUMNS, "distance", "elevation_difference"]] * 3
    assert [row["distance"] for row in block] == [1.5, 2.5, 3.5]
    assert [row["elevation_difference"] for row in block] == [10.0, None, -5.0]


@pytest.mark.parametrize("make", [an_interpolation, a_summary])
def test_a_cut_estimate_lists_the_stations_of_the_rows_left_with_their_distances(make) -> None:  # noqa: ANN001
    """After a cut the block is the stations of the rows left, with the distances they had."""
    cut = make().filtered_by_date("2021-01-01")

    block = cut.to_dict(with_stations=True)["stations"]

    assert [row["station_id"] for row in block] == ["00001"]
    assert block[0]["distance"] == 1.5
    assert block[0]["elevation_difference"] == 10.0
    assert block == [row for row in make().to_dict(with_stations=True)["stations"] if row["station_id"] == "00001"]
