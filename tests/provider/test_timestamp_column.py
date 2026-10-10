# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the type of the ``timestamp`` column every provider hands back (GH-2617).

The check that holds the frame of every values result to it lives in ``conftest.py``, where it runs
in every provider test; the tests here show that it can fail, and cover what no provider test builds.
"""

import datetime as dt
from collections.abc import Iterator
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.provider.timestamps import TIMESTAMP_DTYPE, timestamp_problem
from wetterdienst import Settings
from wetterdienst.model import result as results
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest, DwdObservationValues

UTC = ZoneInfo("UTC")


def test_the_declared_schema_is_utc_microseconds() -> None:
    """Test that the schema every provider's long frame is built against has the one timestamp type."""
    assert TimeseriesValues._long_fields["timestamp"] == TIMESTAMP_DTYPE  # noqa: SLF001


@pytest.mark.parametrize(
    "dtype",
    [
        pl.Datetime("ns", "UTC"),
        pl.Datetime("ms", "UTC"),
        pl.Datetime("us"),
        pl.Datetime("us", "Europe/Berlin"),
        pl.Date,
        pl.String,
    ],
)
def test_a_timestamp_of_another_type_is_a_problem(dtype: pl.DataType) -> None:
    """Test that nanoseconds, a coarser unit, a naive stamp, a local zone or a non-datetime are all refused."""
    assert timestamp_problem(pl.DataFrame(schema={"timestamp": dtype})) is not None


def test_utc_microseconds_are_no_problem_and_a_missing_column_is() -> None:
    """Test that the one accepted type passes, and that a frame without the column is reported."""
    assert timestamp_problem(pl.DataFrame(schema={"timestamp": TIMESTAMP_DTYPE})) is None
    assert timestamp_problem(pl.DataFrame()) is not None


@pytest.mark.parametrize("cls", ["ValuesResult", "InterpolatedValuesResult", "SummarizedValuesResult"])
def test_a_result_with_another_timestamp_type_cannot_be_built_in_a_provider_test(cls: str) -> None:
    """Test that the guard in conftest.py refuses a result whose frame carries a local-time stamp."""
    df = pl.DataFrame(schema={"timestamp": pl.Datetime("us", "Europe/Berlin")})
    with pytest.raises(AssertionError, match="timestamp column is Datetime"):
        getattr(results, cls)(
            stations=None, df=df, **({"values": None} if cls == "ValuesResult" else {"latlon": (0, 0)})
        )


@pytest.mark.parametrize("method", ["interpolate", "summarize"])
def test_interpolated_and_summarized_timestamps_are_utc_microseconds(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
) -> None:
    """Test that interpolating or summarizing the readings of four stations keeps the timestamp type.

    The stations and their readings are stubbed, so nothing leaves the machine. The readings are
    stamped on the day the clocks went back in Germany, the 26th of October 2025.
    """
    from wetterdienst.core.interpolate import get_interpolated_df  # noqa: PLC0415
    from wetterdienst.core.summarize import get_summarized_df  # noqa: PLC0415

    latitude, longitude = 50.0, 8.9
    offsets = {"00001": (-0.03, -0.03), "00002": (-0.03, 0.03), "00003": (0.03, 0.03), "00004": (0.03, -0.03)}
    stations = pl.DataFrame(
        [
            {
                "resolution": "hourly",
                "dataset": "temperature_air",
                "station_id": station_id,
                "latitude": latitude + d_lat,
                "longitude": longitude + d_lon,
                "elevation": 100.0,
                "distance": 4.0 + index / 10,
            }
            for index, (station_id, (d_lat, d_lon)) in enumerate(offsets.items())
        ],
    )
    start = dt.datetime(2025, 10, 25, 22, tzinfo=UTC)
    timestamps = [start + dt.timedelta(hours=hour) for hour in range(5)]

    def _filter_by_distance(
        self: DwdObservationRequest,
        latlon: tuple[float, float],  # noqa: ARG001
        distance: float,  # noqa: ARG001
        df_all: pl.DataFrame | None = None,  # noqa: ARG001
    ) -> StationsResult:
        return StationsResult(stations=self, df=stations, df_all=stations, stations_filter=StationsFilter.BY_DISTANCE)

    def _query(self: DwdObservationValues) -> Iterator[object]:  # noqa: ARG001
        for station_id in offsets:
            df = pl.DataFrame(
                [
                    {
                        "station_id": station_id,
                        "resolution": "hourly",
                        "dataset": "temperature_air",
                        "parameter": "temperature_air_2m",
                        "timestamp": timestamp,
                        "value": 280.0 + index,
                        "quality": 10.0,
                    }
                    for index, timestamp in enumerate(timestamps)
                ],
                schema_overrides={"timestamp": TIMESTAMP_DTYPE},
            )
            yield SimpleNamespace(df=df)

    monkeypatch.setattr(DwdObservationRequest, "filter_by_distance", _filter_by_distance)
    monkeypatch.setattr(DwdObservationValues, "query", _query)
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air", "temperature_air_2m")],
        start=timestamps[0],
        end=timestamps[-1],
        settings=Settings(),
    )
    get_df = get_interpolated_df if method == "interpolate" else get_summarized_df
    df = get_df(request, latitude, longitude)
    assert df.height == len(timestamps)
    assert timestamp_problem(df) is None
    assert df.get_column("timestamp").to_list() == timestamps
