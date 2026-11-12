"""The stations of an interpolated or a summarized result are those of the rows it holds (GH-3814).

The list is made of the ids the rows name, so a result cut down by `filtered_by_date` or `filtered_by_sql` lists the
stations of what is left, and not those of the whole answer: two rows from one station were listed with six, and an
empty result with all of them.
"""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from wetterdienst.model.result import (
    InterpolatedValuesResult,
    StationsFilter,
    StationsResult,
    SummarizedValuesResult,
)

UTC = dt.UTC
STATION_IDS = ["00001", "00002", "00003", "00004", "00005", "00006"]
DAY_ONE = dt.datetime(2021, 1, 1, tzinfo=UTC)
DAY_TWO = dt.datetime(2021, 1, 2, tzinfo=UTC)

#: the stations each row was made from: day one from 00001 alone, day two from the other five
INTERPOLATED_FROM = {DAY_ONE: ["00001"], DAY_TWO: STATION_IDS[1:]}
SUMMARIZED_FROM = {DAY_ONE: "00001", DAY_TWO: "00002"}


def _stations(ids: list[str]) -> StationsResult:
    df = pl.DataFrame(
        {
            "resolution": ["daily"] * len(ids),
            "dataset": ["climate_summary"] * len(ids),
            "station_id": ids,
            "start_timestamp": [DAY_ONE] * len(ids),
            "end_timestamp": [None] * len(ids),
            "latitude": [50.0 + i / 100 for i in range(len(ids))],
            "longitude": [8.9] * len(ids),
            "elevation": [100.0] * len(ids),
            "name": [f"Station {station_id}" for station_id in ids],
            "region": [None] * len(ids),
        },
        schema_overrides={
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
        },
    )
    return StationsResult(request=_Request(), df=df, _df_all=df, _stations_filter=StationsFilter.BY_STATION_ID)


class _Request:
    """The request a result needs to describe itself: the provider's metadata."""

    class metadata:  # noqa: N801
        name_local = "Test"
        name_english = "Test"
        country = "Testland"
        copyright = "none"
        url = "https://example.invalid/"
        license = None
        attribution = "none"


def _interpolated() -> InterpolatedValuesResult:
    rows = [
        {
            "station_id": "abc",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": timestamp,
            "value": 1.0 + i,
            "distance_mean": 5.0,
            "taken_station_ids": taken,
        }
        for i, (timestamp, taken) in enumerate(INTERPOLATED_FROM.items())
    ]
    df = pl.DataFrame(rows, schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")})
    return InterpolatedValuesResult(stations=_stations(STATION_IDS), df=df, latlon=(50.0, 8.9))


def _summarized() -> SummarizedValuesResult:
    rows = [
        {
            "station_id": "abc",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": timestamp,
            "value": 1.0 + i,
            "distance": 0.5,
            "taken_station_id": taken,
        }
        for i, (timestamp, taken) in enumerate(SUMMARIZED_FROM.items())
    ]
    df = pl.DataFrame(rows, schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")})
    return SummarizedValuesResult(stations=_stations(["00001", "00002"]), df=df, latlon=(50.0, 8.9))


def _listed(result: InterpolatedValuesResult | SummarizedValuesResult) -> list[str]:
    return [station["station_id"] for station in result.to_dict(with_stations=True)["stations"]]


def _kinds() -> list[pytest.param]:
    return [
        pytest.param(_interpolated, STATION_IDS, ["00001"], id="interpolated"),
        pytest.param(_summarized, ["00001", "00002"], ["00001"], id="summarized"),
    ]


@pytest.mark.parametrize(("make", "whole", "first_day"), _kinds())
def test_a_result_lists_the_stations_of_its_rows_until_it_is_cut(make, whole: list[str], first_day: list[str]) -> None:  # noqa: ANN001, ARG001
    """The starting point: the list is the stations of the rows, the whole answer's."""
    assert _listed(make()) == whole


@pytest.mark.parametrize(("make", "whole", "first_day"), _kinds())
def test_filtered_by_date_lists_the_stations_of_the_rows_left(make, whole: list[str], first_day: list[str]) -> None:  # noqa: ANN001, ARG001
    """A result cut to one day lists the stations that day was made from: 2 rows of 00001 are not 6 stations."""
    cut = make().filtered_by_date("2021-01-01")

    assert cut.df.height == 1
    assert _listed(cut) == first_day
    assert cut.df_stations.get_column("station_id").to_list() == first_day


@pytest.mark.parametrize(("make", "whole", "first_day"), _kinds())
def test_filtered_by_sql_lists_the_stations_of_the_rows_left(make, whole: list[str], first_day: list[str]) -> None:  # noqa: ANN001, ARG001
    """The same for a WHERE clause."""
    cut = make().filtered_by_sql("timestamp < '2021-01-02'")

    assert cut.df.height == 1
    assert _listed(cut) == first_day


@pytest.mark.parametrize(("make", "whole", "first_day"), _kinds())
def test_a_result_cut_to_nothing_lists_no_station(make, whole: list[str], first_day: list[str]) -> None:  # noqa: ANN001, ARG001
    """An empty result lists no station, where it listed all of them."""
    cut = make().filtered_by_sql("value > 1000")

    assert cut.df.is_empty()
    assert _listed(cut) == []
    assert cut.df_stations.is_empty()
    # the formats still render
    assert cut.to_ogc_feature_collection()["data"]["features"][0]["stations"] == []


@pytest.mark.parametrize(("make", "whole", "first_day"), _kinds())
def test_a_cut_that_keeps_every_row_keeps_every_station(make, whole: list[str], first_day: list[str]) -> None:  # noqa: ANN001, ARG001
    """A filter that drops no row leaves the list as it was."""
    cut = make().filtered_by_date("2021-01")

    assert cut.df.height == 2
    assert _listed(cut) == whole


@pytest.mark.parametrize(("make", "whole", "first_day"), _kinds())
def test_the_result_that_was_cut_is_left_as_it_was(make, whole: list[str], first_day: list[str]) -> None:  # noqa: ANN001, ARG001
    """A cut gives a new result: the one it was asked on keeps its rows and its stations."""
    result = make()
    result.filtered_by_date("2021-01-01")

    assert result.df.height == 2
    assert _listed(result) == whole


def test_the_stations_of_a_plain_values_result_were_always_read_off_its_rows() -> None:
    """A result of values reads its stations off the rows too (`df_stations`), which the estimates now do as well."""
    from wetterdienst.model.result import ValuesResult  # noqa: PLC0415

    df = pl.DataFrame(
        {
            "station_id": ["00001", "00002"],
            "resolution": ["daily"] * 2,
            "dataset": ["climate_summary"] * 2,
            "parameter": ["temperature_air_mean_2m"] * 2,
            "timestamp": [DAY_ONE, DAY_TWO],
            "value": [1.0, 2.0],
            "quality_flags": [None, None],
        },
        schema_overrides={"timestamp": pl.Datetime(time_zone="UTC"), "quality_flags": pl.String},
    )
    result = ValuesResult(stations=_stations(["00001", "00002"]), df=df)

    assert result.filtered_by_date("2021-01-01").df_stations.get_column("station_id").to_list() == ["00001"]
