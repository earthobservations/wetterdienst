# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The core shapes the frame a provider hands it into the long form (GH-2627)."""

from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.exceptions import ProviderContractError, WetterdienstError
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.model.values import shape_provider_frame
from wetterdienst.provider.dwd.observation import DwdObservationRequest

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel

UTC = ZoneInfo("UTC")
BERLIN = ZoneInfo("Europe/Berlin")
NOON = dt.datetime(2026, 1, 1, 12, tzinfo=UTC)


@pytest.fixture(scope="module")
def dataset() -> DatasetModel:
    """Give a dataset whose resolution and name show in the identity columns."""
    return DwdObservationRequest(parameters=[("daily", "climate_summary")]).parameters[0].dataset


def _frame(**columns: object) -> pl.DataFrame:
    """Build a one-row frame of a provider, a column at a time, with the minimum a provider must deliver."""
    base = {"parameter": ["tmk"], "timestamp": [NOON], "value": [1.5]}
    return pl.DataFrame({**base, **columns})


def _shape(df: pl.DataFrame, dataset: DatasetModel) -> pl.DataFrame:
    return shape_provider_frame(df, station_id="01048", dataset=dataset, provider="TestValues")


def test_the_minimum_a_provider_delivers_becomes_the_long_form(dataset: DatasetModel) -> None:
    """The identity columns are added, the flags are a typed null, and the order is the long form's."""
    result = _shape(_frame(), dataset)

    assert result.schema == LONG_SCHEMA
    assert result.row(0, named=True) == {
        "station_id": "01048",
        "resolution": "daily",
        "dataset": "climate_summary",
        "parameter": "tmk",
        "timestamp": NOON,
        "value": 1.5,
        "quality_flags": None,
    }


def test_the_identity_columns_are_the_cores_whatever_the_provider_wrote(dataset: DatasetModel) -> None:
    """A provider's station id (a URL, say) or dataset spelling is replaced."""
    result = _shape(
        _frame(station_id=["https://api.weather.gov/stations/KDEN"], resolution=["x"], dataset=["Climate_Summary"]),
        dataset,
    )

    assert result.select("station_id", "resolution", "dataset").row(0) == ("01048", "daily", "climate_summary")


def test_a_long_form_comes_out_unchanged(dataset: DatasetModel) -> None:
    """Shaping what is shaped already changes nothing, so a provider can keep its own shaping until it drops it."""
    first = _shape(_frame(quality_flags=["G"]), dataset)

    again = _shape(first, dataset)

    assert_frame_equal(again, first)
    assert again.schema == LONG_SCHEMA


def test_the_columns_are_ordered_as_the_long_form_orders_them(dataset: DatasetModel) -> None:
    """A provider that puts the station first, or the value before the parameter, is put in order."""
    df = _frame(station_id=["01048"], quality_flags=["G"]).select(
        "station_id", "value", "quality_flags", "timestamp", "parameter"
    )

    assert _shape(df, dataset).columns == list(LONG_SCHEMA)


def test_a_surplus_column_is_dropped_and_said_so_once(dataset: DatasetModel, caplog: pytest.LogCaptureFixture) -> None:
    """A column the long form does not have leaves, with one debug line naming it."""
    with caplog.at_level(logging.DEBUG, logger="wetterdienst.model.values"):
        result = _shape(_frame(quality=[3.0], extra=["x"]), dataset)

    assert result.columns == list(LONG_SCHEMA)
    lines = [record.getMessage() for record in caplog.records if "dropped" in record.getMessage()]
    assert len(lines) == 1
    assert "quality" in lines[0]
    assert "extra" in lines[0]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(pl.Series([NOON.replace(tzinfo=None)]), NOON, id="naive-is-read-as-utc"),
        pytest.param(pl.Series([dt.datetime(2026, 1, 1, 13, tzinfo=BERLIN)]), NOON, id="zoned-is-converted"),
        pytest.param(pl.Series([NOON]).dt.cast_time_unit("ns"), NOON, id="nanoseconds"),
        pytest.param(pl.Series([NOON]).dt.cast_time_unit("ms"), NOON, id="milliseconds"),
        pytest.param(pl.Series([dt.date(2026, 1, 1)]), dt.datetime(2026, 1, 1, tzinfo=UTC), id="date-is-midnight"),
    ],
)
def test_the_timestamp_becomes_utc_to_the_microsecond(
    dataset: DatasetModel, source: pl.Series, expected: dt.datetime
) -> None:
    """Whatever point in time a provider hands over comes out as the same instant, in the long form's type."""
    result = _shape(_frame().with_columns(timestamp=source), dataset)

    assert result.schema["timestamp"] == LONG_SCHEMA["timestamp"]
    assert result.get_column("timestamp").to_list() == [expected]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(pl.Series([3], dtype=pl.Int32), 3.0, id="integer"),
        pytest.param(pl.Series([1.5], dtype=pl.Float32), 1.5, id="float32"),
        pytest.param(pl.Series(["2.25"]), 2.25, id="text-that-is-a-number"),
        pytest.param(pl.Series([None], dtype=pl.Null), None, id="all-null"),
    ],
)
def test_the_value_becomes_float64(dataset: DatasetModel, source: pl.Series, expected: float | None) -> None:
    """A number, or the text of one, is read as Float64."""
    result = _shape(_frame().with_columns(value=source), dataset)

    assert result.schema["value"] == pl.Float64
    assert result.get_column("value").to_list() == [expected]


def test_a_value_that_is_no_number_is_null_and_counted_once(
    dataset: DatasetModel, caplog: pytest.LogCaptureFixture
) -> None:
    """Three bad cells in a frame of five: three nulls and one debug line saying 3, not one line per cell."""
    df = pl.DataFrame(
        {
            "parameter": ["tmk"] * 5,
            "timestamp": [NOON + dt.timedelta(days=day) for day in range(5)],
            "value": ["1.5", "n/a", None, "---", "x"],
        }
    )

    with caplog.at_level(logging.DEBUG, logger="wetterdienst.model.values"):
        result = _shape(df, dataset)

    assert result.get_column("value").to_list() == [1.5, None, None, None, None]
    lines = [record.getMessage() for record in caplog.records if "no number" in record.getMessage()]
    assert lines == ["TestValues: 3 of 5 value cells are no number and are null"]
    assert all(record.levelno == logging.DEBUG for record in caplog.records)


def test_a_value_column_that_is_numbers_logs_nothing(dataset: DatasetModel, caplog: pytest.LogCaptureFixture) -> None:
    """The nulls a provider hands over itself are no bad cells."""
    with caplog.at_level(logging.DEBUG, logger="wetterdienst.model.values"):
        _shape(_frame(value=[None], quality_flags=[None]).cast({"value": pl.Int64}), dataset)

    assert caplog.records == []


def test_the_flags_become_a_string(dataset: DatasetModel) -> None:
    """A flag a source writes as a number is its text."""
    result = _shape(_frame(quality_flags=[3]), dataset)

    assert result.schema["quality_flags"] == pl.String
    assert result.get_column("quality_flags").to_list() == ["3"]


@pytest.mark.parametrize("column", ["parameter", "timestamp", "value"])
def test_a_frame_without_a_required_column_cannot_be_made_to_fit(dataset: DatasetModel, column: str) -> None:
    """The core cannot make up what was measured, when, or for which parameter."""
    with pytest.raises(ProviderContractError, match=f"TestValues returned a frame without the column.*{column}"):
        _shape(_frame().drop(column), dataset)


@pytest.mark.parametrize(
    ("column", "source"),
    [
        pytest.param("timestamp", pl.Series(["2026-01-01T12:00:00"]), id="timestamp-text"),
        pytest.param("timestamp", pl.Series([1767268800]), id="timestamp-integer"),
        pytest.param("value", pl.Series([[1.0]]), id="value-list"),
        pytest.param("value", pl.Series([{"a": 1.0}]), id="value-struct"),
        pytest.param("value", pl.Series([True]), id="value-boolean"),
        pytest.param("quality_flags", pl.Series([["G"]]), id="flags-list"),
    ],
)
def test_a_column_of_a_type_that_cannot_be_cast_is_an_error(
    dataset: DatasetModel, column: str, source: pl.Series
) -> None:
    """A text or a number is no timestamp, and a list is no value: the error names the provider and the column."""
    with pytest.raises(ProviderContractError, match=f"TestValues returned `{column}` as"):
        _shape(_frame().with_columns(**{column: source}), dataset)


def test_the_error_is_the_librarys_and_a_defect_not_a_request_error() -> None:
    """It derives from the root, and from none of the kinds the REST API answers with a 4xx."""
    from wetterdienst.exceptions import NotFoundError, RequestError  # noqa: PLC0415

    assert issubclass(ProviderContractError, WetterdienstError)
    assert not issubclass(ProviderContractError, RequestError | NotFoundError)
