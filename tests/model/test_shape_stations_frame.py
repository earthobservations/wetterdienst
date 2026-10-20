# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The core shapes the frame a provider hands it as its stations into the stations frame (GH-2627)."""

from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.exceptions import ProviderContractError
from wetterdienst.model.request import TimeseriesRequest, shape_stations_frame
from wetterdienst.model.schema import STATIONS_SCHEMA, TIMESTAMP_DTYPE
from wetterdienst.provider.dwd.observation import DwdObservationRequest

UTC = ZoneInfo("UTC")
BERLIN = ZoneInfo("Europe/Berlin")
COLUMNS = tuple(STATIONS_SCHEMA)
NOON = dt.datetime(2026, 1, 1, 12, tzinfo=UTC)


def _frame(**columns: object) -> pl.DataFrame:
    """Build a one-row frame of a provider, a column at a time, with the minimum a provider must deliver."""
    base = {"resolution": ["daily"], "dataset": ["data"], "station_id": ["01048"]}
    return pl.DataFrame({**base, **columns})


def _shape(df: pl.DataFrame, columns: tuple[str, ...] = COLUMNS) -> pl.DataFrame:
    return shape_stations_frame(df, columns=columns, provider="TestRequest")


def test_the_minimum_a_provider_delivers_becomes_the_stations_frame() -> None:
    """What is not delivered is a typed null, and the order is the schema's."""
    result = _shape(_frame())

    assert result.schema == STATIONS_SCHEMA
    assert result.row(0, named=True) == {
        "resolution": "daily",
        "dataset": "data",
        "station_id": "01048",
        "start_timestamp": None,
        "end_timestamp": None,
        "latitude": None,
        "longitude": None,
        "elevation": None,
        "name": None,
        "region": None,
    }


def test_a_stations_frame_comes_out_unchanged() -> None:
    """Shaping what is shaped already changes nothing, so a provider can keep its own shaping until it drops it."""
    first = _shape(
        _frame(
            start_timestamp=[NOON],
            end_timestamp=[None],
            latitude=[53.6332],
            longitude=[9.99],
            elevation=[11.0],
            name=["Hamburg"],
            region=["HH"],
        ).with_columns(pl.col("end_timestamp").cast(TIMESTAMP_DTYPE)),
    )

    again = _shape(first)

    assert_frame_equal(again, first)
    assert again.schema == STATIONS_SCHEMA


def test_the_columns_are_the_ones_named_in_their_order() -> None:
    """The order of the request's own columns wins over the one the provider wrote, and its extra column is kept."""
    columns = (*COLUMNS, "gauge_zero")
    df = _frame(gauge_zero=[1.5], name=["Hamburg"]).select("gauge_zero", "name", "station_id", "dataset", "resolution")

    result = _shape(df, columns)

    assert result.columns == list(columns)
    assert result.schema["gauge_zero"] == pl.Float64
    assert result.row(0, named=True)["gauge_zero"] == 1.5


def test_a_column_of_the_request_the_provider_left_out_is_a_null() -> None:
    """The schema's column has its dtype; the provider's own, which no schema declares, is an untyped null as before."""
    result = _shape(_frame(), (*COLUMNS, "country"))

    assert result.schema["country"] == pl.Null
    assert result.schema["latitude"] == pl.Float64
    assert result.get_column("country").null_count() == 1


def test_a_surplus_column_is_dropped_with_a_debug_line(caplog: pytest.LogCaptureFixture) -> None:
    """The columns the request does not list are dropped, and one debug line names them."""
    with caplog.at_level(logging.DEBUG, logger="wetterdienst.model.request"):
        result = _shape(_frame(created=["2026-01-01"], icao_id=["EDDH"]))

    assert result.columns == list(COLUMNS)
    assert [record.getMessage() for record in caplog.records if "dropped" in record.getMessage()] == [
        "TestRequest: dropped the column(s) created, icao_id, which the stations frame does not have",
    ]


@pytest.mark.parametrize(
    "empty",
    [
        pl.DataFrame(),
        pl.DataFrame(schema={"station_id": pl.String}),
        pl.DataFrame({"station_id": [], "latitude": [], "start_timestamp": []}),
        pl.DataFrame(schema={"resolution": pl.Int64, "start_timestamp": pl.String}),
    ],
    ids=["bare", "one column typed", "null columns", "wrong types"],
)
def test_a_frame_without_a_row_is_the_empty_frame_of_the_columns(empty: pl.DataFrame) -> None:
    """Whatever the frame holds, no row is no stations, and the empty frame has the dtypes of the schema."""
    result = _shape(empty, (*COLUMNS, "country"))

    assert result.is_empty()
    assert result.schema == pl.Schema({**STATIONS_SCHEMA, "country": pl.String})


@pytest.mark.parametrize("missing", ["resolution", "dataset", "station_id"])
def test_a_required_column_that_is_missing_is_a_contract_error(missing: str) -> None:
    """The core cannot make up which dataset a station belongs to, nor its id."""
    with pytest.raises(ProviderContractError, match=f"TestRequest returned stations without the column.*{missing}"):
        _shape(_frame().drop(missing))


@pytest.mark.parametrize(
    ("column", "values"),
    [
        ("start_timestamp", ["2026-01-01"]),
        ("end_timestamp", [20260101]),
        ("latitude", [[53.0]]),
        ("elevation", [True]),
        ("name", [[1]]),
        ("station_id", [{"a": 1}]),
    ],
)
def test_a_column_of_impossible_type_is_a_contract_error(column: str, values: list[object]) -> None:
    """A text or a number is no point in time, a list is no number, and what the cast would do is not guessed."""
    df = _frame().drop(column) if column == "station_id" else _frame()
    df = df.with_columns(pl.Series(column, values))

    with pytest.raises(ProviderContractError, match=f"TestRequest returned `{column}` as"):
        _shape(df)


def test_a_number_that_is_a_text_is_read_and_one_that_is_no_number_is_null(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unparsable cells are null, never an error, and one debug line per column counts them."""
    df = pl.DataFrame(
        {
            "resolution": ["daily"] * 4,
            "dataset": ["data"] * 4,
            "station_id": ["1", "2", "3", "4"],
            "latitude": ["53.5", "n/a", "---", None],
            "longitude": ["9.5", "10", "x", "y"],
            "elevation": [1, 2, None, 4],
        },
    )

    with caplog.at_level(logging.DEBUG, logger="wetterdienst.model.request"):
        result = _shape(df)

    assert result.schema == STATIONS_SCHEMA
    assert result.get_column("latitude").to_list() == [53.5, None, None, None]
    assert result.get_column("longitude").to_list() == [9.5, 10.0, None, None]
    assert result.get_column("elevation").to_list() == [1.0, 2.0, None, 4.0]
    messages = [record.getMessage() for record in caplog.records if "no number" in record.getMessage()]
    assert messages == [
        "TestRequest: 2 of 4 latitude cells are no number and are null",
        "TestRequest: 2 of 4 longitude cells are no number and are null",
    ]


def test_a_naive_timestamp_is_read_as_utc_and_a_zoned_one_is_converted() -> None:
    """The stations frame has one timestamp type, UTC to the microsecond, whatever the provider parsed."""
    df = pl.DataFrame(
        {
            "resolution": ["daily"] * 3,
            "dataset": ["data"] * 3,
            "station_id": ["1", "2", "3"],
            "start_timestamp": [NOON.replace(tzinfo=None), None, NOON.replace(tzinfo=None)],
            "end_timestamp": [
                dt.datetime(2026, 1, 1, 13, tzinfo=BERLIN),
                dt.datetime(2026, 1, 1, 13, tzinfo=BERLIN),
                None,
            ],
        },
        schema_overrides={
            "start_timestamp": pl.Datetime("ns"),
            "end_timestamp": pl.Datetime("ns", "Europe/Berlin"),
        },
    )

    result = _shape(df)

    assert result.schema["start_timestamp"] == TIMESTAMP_DTYPE
    assert result.schema["end_timestamp"] == TIMESTAMP_DTYPE
    assert result.get_column("start_timestamp").to_list() == [NOON, None, NOON]
    assert result.get_column("end_timestamp").to_list() == [dt.datetime(2026, 1, 1, 12, tzinfo=UTC), NOON, None]


def test_a_date_is_a_midnight_in_utc() -> None:
    """A provider that knows the day only (a start date) is read as the day's start."""
    result = _shape(_frame(start_timestamp=[dt.date(2026, 1, 1)]))

    assert result.schema["start_timestamp"] == TIMESTAMP_DTYPE
    assert result.item(0, "start_timestamp") == dt.datetime(2026, 1, 1, tzinfo=UTC)


def test_an_integer_id_and_a_category_are_made_a_string() -> None:
    """A provider that read the id as a number gets the text the values step collects by."""
    result = _shape(
        _frame().with_columns(pl.lit(1048).alias("station_id"), pl.lit("EDDH").cast(pl.Categorical).alias("name"))
    )

    assert result.schema["station_id"] == pl.String
    assert result.row(0, named=True)["station_id"] == "1048"
    assert result.schema["name"] == pl.String


@pytest.mark.parametrize("handed", [pl.LazyFrame(), pl.LazyFrame(schema={"station_id": pl.String})])
def test_all_answers_the_empty_stations_frame_for_a_catalogue_without_stations(
    monkeypatch: pytest.MonkeyPatch,
    handed: pl.LazyFrame,
) -> None:
    """`all()` is `_all()` through the shaping, so a provider that has no stations hands over nothing at all."""
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: handed)

    result = DwdObservationRequest(parameters=[("daily", "climate_summary")]).all()

    assert result.df.is_empty()
    assert result.df.schema == STATIONS_SCHEMA


def test_all_names_the_request_in_the_message_of_a_frame_that_does_not_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    """The people who write the provider are told which one it is."""
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: _frame().drop("dataset").lazy())

    with pytest.raises(ProviderContractError, match="DwdObservationRequest returned stations without"):
        DwdObservationRequest(parameters=[("daily", "climate_summary")]).all()


def test_the_columns_the_core_shapes_by_are_the_requests_base_columns() -> None:
    """A provider adds a column of its own to `_base_columns`, and the base columns are the schema's."""
    assert TimeseriesRequest._base_columns == COLUMNS  # noqa: SLF001
