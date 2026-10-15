# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The output schema snapshot: what the frames of a result look like, column by column (GH-2633, GH-2625).

The schemas are part of what the library promises, so each is written out below as the text of its dtypes. A
change of a column, of its place or of its dtype fails here, and the diff of the test is the diff of the
contract. Nothing needs the network: the frames are built by the code that builds them for a request, from rows
served in place of the provider's.
"""

import datetime as dt
import json
import re
from typing import Any

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Options, Settings
from wetterdienst.model import schema
from wetterdienst.model.result import StationsFilter, StationsResult, ValuesResult
from wetterdienst.model.schema import (
    INTERPOLATED_SCHEMA,
    LONG_SCHEMA,
    STATIONS_SCHEMA,
    SUMMARIZED_SCHEMA,
    WIDE_SCHEMA,
    wide_schema,
)
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues

UTC_US = "Datetime(time_unit='us', time_zone='UTC')"

#: the schemas as committed: column, dtype, in order. Change it in the same commit as the schema, and say in the
#: changelog that a caller's frame changed.
SNAPSHOT: dict[str, list[tuple[str, str]]] = {
    "STATIONS_SCHEMA": [
        ("resolution", "String"),
        ("dataset", "String"),
        ("station_id", "String"),
        ("start_timestamp", UTC_US),
        ("end_timestamp", UTC_US),
        ("latitude", "Float64"),
        ("longitude", "Float64"),
        ("elevation", "Float64"),
        ("name", "String"),
        ("region", "String"),
    ],
    "LONG_SCHEMA": [
        ("station_id", "String"),
        ("resolution", "String"),
        ("dataset", "String"),
        ("parameter", "String"),
        ("timestamp", UTC_US),
        ("value", "Float64"),
        ("quality_flags", "String"),
    ],
    "WIDE_SCHEMA": [
        ("station_id", "String"),
        ("resolution", "String"),
        ("dataset", "String"),
        ("timestamp", UTC_US),
    ],
    "INTERPOLATED_SCHEMA": [
        ("station_id", "String"),
        ("resolution", "String"),
        ("dataset", "String"),
        ("parameter", "String"),
        ("timestamp", UTC_US),
        ("value", "Float64"),
        ("distance_mean", "Float64"),
        ("taken_station_ids", "List(String)"),
    ],
    "SUMMARIZED_SCHEMA": [
        ("station_id", "String"),
        ("resolution", "String"),
        ("dataset", "String"),
        ("parameter", "String"),
        ("timestamp", UTC_US),
        ("value", "Float64"),
        ("distance", "Float64"),
        ("taken_station_id", "String"),
    ],
}


def _written(frame_schema: pl.Schema) -> list[tuple[str, str]]:
    return [(name, str(dtype)) for name, dtype in frame_schema.items()]


@pytest.mark.parametrize("name", sorted(SNAPSHOT))
def test_the_exported_schema_is_the_one_committed(name: str) -> None:
    """Test that a schema's columns, their order and their dtypes are those of the snapshot."""
    assert _written(getattr(schema, name)) == SNAPSHOT[name]


def test_the_wide_schema_names_a_value_and_a_flags_column_per_parameter() -> None:
    """Test that the columns of a parameter follow the fixed ones, the value and then its flags."""
    assert _written(wide_schema(["a", "b"])) == [
        *SNAPSHOT["WIDE_SCHEMA"],
        ("a", "Float64"),
        ("a_quality_flags", "String"),
        ("b", "Float64"),
        ("b_quality_flags", "String"),
    ]
    assert wide_schema([]) == WIDE_SCHEMA


@pytest.mark.parametrize("name", sorted(SNAPSHOT))
def test_the_identity_columns_are_strings_in_every_schema(name: str) -> None:
    """Test that no frame names a series with anything but a String, and a stamp with one type."""
    frame_schema = getattr(schema, name)
    for column in schema.IDENTITY_COLUMNS:
        assert frame_schema.get(column, pl.String) == pl.String
    assert frame_schema.get("timestamp", schema.TIMESTAMP_DTYPE) == schema.TIMESTAMP_DTYPE


# ---------------------------------------------------------------------------
# What the code that builds a frame makes of it
# ---------------------------------------------------------------------------


def _stations_frame(*station_ids: str) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "station_id": station_id,
                "start_timestamp": dt.datetime(1934, 1, 1, tzinfo=dt.UTC),
                "end_timestamp": dt.datetime(2025, 12, 31, tzinfo=dt.UTC),
                "latitude": 51.0 + index,
                "longitude": 13.0,
                "elevation": 228.0,
                "name": f"Station {station_id}",
                "region": "Sachsen",
            }
            for index, station_id in enumerate(station_ids)
        ],
        schema=STATIONS_SCHEMA,
    )


def _request(options: Options | None = None) -> DwdObservationRequest:
    return DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="2020-01-01",
        end="2020-01-03",
        settings=Settings(cache_disable=True),
        options=options,
    )


def _stations(request: DwdObservationRequest, *station_ids: str) -> StationsResult:
    df = _stations_frame(*station_ids)
    return StationsResult(stations=request, df=df, df_all=df, stations_filter=StationsFilter.BY_STATION_ID)


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve three readings of `tmk` per station, as the source names them, in place of the download."""

    def collect(self: DwdObservationValues, station_id: str, parameter_or_dataset: object) -> pl.DataFrame:  # noqa: ARG001
        return pl.DataFrame(
            [
                {
                    "station_id": station_id,
                    "resolution": "daily",
                    "dataset": "climate_summary",
                    "parameter": "tmk",
                    "timestamp": dt.datetime(2020, 1, day, tzinfo=dt.UTC),
                    "value": float(day),
                    "quality_flags": "10",
                }
                for day in (1, 2, 3)
            ],
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


@pytest.mark.usefixtures("served")
def test_a_long_result_has_the_long_schema_and_is_a_string_throughout() -> None:
    """Test that `values.all().df` is `LONG_SCHEMA`, populated or empty, so two of them concatenate and join.

    The identity columns were `Enum` with the categories of each result, so a populated frame did not
    concatenate with an empty one, nor with another request's, and did not join a stations frame.
    """
    request = _request()
    populated = _stations(request, "01048", "04411").values.all().df
    empty = _stations(request).values.all().df
    assert populated.schema == LONG_SCHEMA
    assert empty.schema == LONG_SCHEMA
    assert populated.height == 6
    assert empty.is_empty()
    assert pl.concat([populated, empty]).height == 6
    other = _stations(request, "00003").values.all().df
    assert pl.concat([populated, other]).get_column("station_id").unique().sort().to_list() == [
        "00003",
        "01048",
        "04411",
    ]
    # joins against a stations frame, and filters by names the result does not hold, without a cast
    joined = populated.join(_stations_frame("01048", "04411"), on="station_id")
    assert joined.height == 6
    assert populated.filter(pl.col("parameter").is_in(["sunshine_duration"])).is_empty()
    assert populated.filter(pl.col("parameter").str.starts_with("temperature")).height == 6


@pytest.mark.usefixtures("served")
def test_a_wide_result_has_the_wide_schema_and_is_a_string_throughout() -> None:
    """Test that the wide frame is `wide_schema` of the parameters asked for, populated or empty."""
    request = _request(Options(shape="wide"))
    populated = _stations(request, "01048", "04411").values.all().df
    empty = _stations(request).values.all().df
    expected = wide_schema(["temperature_air_mean_2m"])
    assert populated.schema == expected
    assert empty.schema == expected
    assert populated.height == 6
    assert pl.concat([populated, empty]).height == 6


@pytest.mark.usefixtures("served")
def test_the_series_of_a_query_have_the_schema_the_aggregated_result_has() -> None:
    """Test that the frame of one station, from `query()`, is the one `all()` puts together."""
    request = _request()
    (first,) = list(_stations(request, "01048").values.query())
    assert first.df.schema == LONG_SCHEMA


def test_a_result_built_from_the_schema_has_nothing_to_cast_to_join() -> None:
    """Test that the schema's own empty frame joins and concatenates with a populated one."""
    empty = pl.DataFrame(schema=LONG_SCHEMA)
    populated = pl.DataFrame(
        {
            "station_id": ["01048"],
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "parameter": ["temperature_air_mean_2m"],
            "timestamp": [dt.datetime(2020, 1, 1, tzinfo=dt.UTC)],
            "value": [1.0],
            "quality_flags": [None],
        },
        schema=LONG_SCHEMA,
    )
    assert_frame_equal(pl.concat([populated, empty]), populated)
    assert ValuesResult(stations=None, values=None, df=empty).df.schema == LONG_SCHEMA  # ty: ignore[invalid-argument-type]


def test_the_stations_of_a_request_have_the_stations_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that `all().df` coerces what a provider builds to `STATIONS_SCHEMA`, rows or none.

    The provider here builds numbers for the ids, milliseconds for the stamps and nothing for the region, as
    a source of such rows would.
    """
    rows = pl.LazyFrame(
        {
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "station_id": [1048],
            "start_timestamp": [dt.datetime(1934, 1, 1)],  # noqa: DTZ001
            "end_timestamp": [dt.datetime(2025, 12, 31)],  # noqa: DTZ001
            "latitude": [51],
            "longitude": [13],
            "elevation": [228],
            "name": ["Dresden-Klotzsche"],
        },
        schema_overrides={
            "start_timestamp": pl.Datetime("ms", "UTC"),
            "end_timestamp": pl.Datetime("ns", "UTC"),
        },
    )
    request = _request()
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: rows)
    populated = request.all().df
    assert populated.schema == STATIONS_SCHEMA
    assert populated.get_column("station_id").to_list() == ["1048"]
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: rows.clear())
    assert request.all().df.schema == STATIONS_SCHEMA


def _estimate(columns: dict[str, Any], schema_of: pl.Schema, drop: str) -> pl.DataFrame:
    """Give what the core hands the request: the estimate's columns, without the point's own `station_id`."""
    return pl.DataFrame(
        {
            "timestamp": [dt.datetime(2020, 1, 1, tzinfo=dt.UTC)],
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "parameter": ["temperature_air_mean_2m"],
            "value": [1.5],
            **columns,
        },
        schema={name: dtype for name, dtype in schema_of.items() if name != drop},
    )


def test_an_interpolated_result_has_the_interpolated_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that `interpolate()` returns `INTERPOLATED_SCHEMA`, with the point's id as a String."""
    pytest.importorskip("shapely")
    from wetterdienst.core import interpolate  # noqa: PLC0415

    request = _request()
    estimate = _estimate({"distance_mean": [12.3], "taken_station_ids": [["01048"]]}, INTERPOLATED_SCHEMA, "station_id")
    monkeypatch.setattr(interpolate, "get_interpolated_df", lambda *_args, **_kwargs: estimate)
    result = request._interpolate((51.0, 13.0), None, df_all=_stations_frame("01048"))  # noqa: SLF001
    assert result.df.schema == INTERPOLATED_SCHEMA
    assert result.df.height == 1
    empty = estimate.clear()
    monkeypatch.setattr(interpolate, "get_interpolated_df", lambda *_args, **_kwargs: empty)
    assert request._interpolate((51.0, 13.0), None, df_all=_stations_frame("01048")).df.schema == INTERPOLATED_SCHEMA  # noqa: SLF001


def test_a_summarized_result_has_the_summarized_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that `summarize()` returns `SUMMARIZED_SCHEMA`, with the point's id as a String."""
    pytest.importorskip("shapely")
    from wetterdienst.core import summarize  # noqa: PLC0415

    request = _request()
    estimate = _estimate({"distance": [12.3], "taken_station_id": ["01048"]}, SUMMARIZED_SCHEMA, "station_id")
    monkeypatch.setattr(summarize, "get_summarized_df", lambda *_args, **_kwargs: estimate)
    result = request._summarize((51.0, 13.0), None, df_all=_stations_frame("01048"))  # noqa: SLF001
    assert result.df.schema == SUMMARIZED_SCHEMA
    assert result.df.height == 1
    empty = estimate.clear()
    monkeypatch.setattr(summarize, "get_summarized_df", lambda *_args, **_kwargs: empty)
    assert request._summarize((51.0, 13.0), None, df_all=_stations_frame("01048")).df.schema == SUMMARIZED_SCHEMA  # noqa: SLF001


def test_the_cores_build_their_frames_from_the_schemas() -> None:
    """Test that the intermediate frames of the cores are the schemas' columns, in the order the cores use."""
    from wetterdienst.core.interpolate import calculate_interpolation  # noqa: PLC0415
    from wetterdienst.core.summarize import calculate_summary  # noqa: PLC0415

    pytest.importorskip("shapely")
    interpolated = calculate_interpolation(0.0, 0.0, {}, {}, None)
    summarized = calculate_summary({}, {})
    # the stamp first, and no station: the point's own id is put in front when the request has the result
    assert list(interpolated.schema) == ["timestamp", *list(INTERPOLATED_SCHEMA)[1:4], *list(INTERPOLATED_SCHEMA)[5:]]
    assert list(summarized.schema) == ["timestamp", *list(SUMMARIZED_SCHEMA)[1:4], *list(SUMMARIZED_SCHEMA)[5:]]
    for frame, frame_schema in ((interpolated, INTERPOLATED_SCHEMA), (summarized, SUMMARIZED_SCHEMA)):
        assert all(dtype == frame_schema[name] for name, dtype in frame.schema.items())


# ---------------------------------------------------------------------------
# One way of writing a timestamp
# ---------------------------------------------------------------------------

TIMESTAMP_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$")


def _timestamps_in(value: object) -> list[str]:
    """Collect the text of every field named like a timestamp in a JSON document."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and ("timestamp" in key or key.startswith("valid_")):
                found.append(item)
            else:
                found.extend(_timestamps_in(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_timestamps_in(item))
    return found


@pytest.mark.usefixtures("served")
def test_values_and_stations_write_their_timestamps_the_one_way() -> None:
    """Test that every JSON body of values and stations, as dict, JSON and GeoJSON, has one format."""
    request = _request()
    stations = _stations(request, "01048")
    values = stations.values.all()
    documents = [
        values.to_dict(with_stations=True),
        json.loads(values.to_json(with_stations=True)),
        values.to_ogc_feature_collection(),
        json.loads(values.to_geojson()),
        stations.to_dict(),
        json.loads(stations.to_json()),
        stations.to_ogc_feature_collection(),
        json.loads(stations.to_geojson()),
    ]
    for document in documents:
        found = _timestamps_in(document)
        assert found
        assert all(TIMESTAMP_TEXT.match(text) for text in found), found
    assert values.to_dict()["values"][0]["timestamp"] == "2020-01-01T00:00:00.000000+00:00"
    assert stations.to_dict()["stations"][0]["start_timestamp"] == "1934-01-01T00:00:00.000000+00:00"
