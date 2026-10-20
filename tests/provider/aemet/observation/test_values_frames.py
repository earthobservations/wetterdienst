# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frames the core hands out for AEMET's monthly and annual values and for its empty answers (GH-2627).

The daily and hourly values are held by the stubs of `test_value_stubs.py`; the monthly and annual endpoint, which one
response serves both of, had only remote tests, and the empty answers of the reader had a test for three of them. The
responses are the shapes AEMET writes, served through the provider's own reader, and
`tests/provider/frames.snapshot.json` records what the core made of each: the net under moving the shaping of the frame
out of the provider.
"""

from __future__ import annotations

import datetime as dt
import json

import polars as pl
import pytest

from tests.provider.value_stubs import _options, _settings, stations_result
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.aemet.observation import AemetObservationRequest
from wetterdienst.provider.aemet.observation import api as aemet_api

STATION = "3195"
UTC = dt.UTC
START = dt.datetime(2020, 1, 1, tzinfo=UTC)
END = dt.datetime(2020, 12, 31, tzinfo=UTC)

# "fecha" is a month as YYYY-MM and the year's aggregate as YYYY-13; the extremes carry the day they were reached in
# parentheses, a trace is `Ip`, and the annual aggregate has no humidity (the remote tests of test_api.py)
_MONTH_1 = {
    "fecha": "2020-1",
    "tm_mes": "7.0",
    "tm_max": "10.4",
    "tm_min": "3.6",
    "ta_max": "15.7(31)",
    "ta_min": "-0.7(10)",
    "p_mes": "16.4",
    "p_max": "5.4(12)",
    "hr": "66",
}
_MONTH_2 = {"fecha": "2020-2", "tm_mes": "9.1", "tm_max": "13.0", "p_mes": "Ip", "p_max": "Ip", "hr": "60"}
_YEAR = {
    "fecha": "2020-13",
    "tm_mes": "16.0",
    "tm_max": "20.9",
    "tm_min": "11.1",
    "ta_max": "39.4(27/jul)",
    "ta_min": "-1.3(10/ene)",
    "p_mes": "474.4",
    "p_max": "37.8(5/nov)",
}


def _serve(monkeypatch: pytest.MonkeyPatch, records: list[dict[str, object]]) -> None:
    payload = json.dumps(records).encode("latin-1")
    monkeypatch.setattr(aemet_api, "_fetch_datos", lambda *args, **kwargs: payload)  # noqa: ARG005


def _values(resolution: str, *, drop_nulls: bool = True) -> pl.DataFrame:
    request = AemetObservationRequest(
        parameters=[(resolution, "data")],
        start=START,
        end=END,
        settings=_settings(auth={"aemet": "stub"}),
        options=_options(drop_nulls),
    )
    return stations_result(request, resolution, "data", STATION).values().all().df


def _assert_the_long_form(df: pl.DataFrame, *, resolution: str) -> None:
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df["resolution"].unique().to_list() == [resolution]
    assert df["dataset"].unique().to_list() == ["data"]
    assert df["station_id"].unique().to_list() == [STATION]
    assert df["timestamp"].dtype == pl.Datetime("us", "UTC")


def test_aemet_monthly_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The months of the response are the monthly rows, stamped at the first of the month; the aggregate is left out."""
    _serve(monkeypatch, [_MONTH_1, _MONTH_2, _YEAR])
    df = _values("monthly")
    _assert_the_long_form(df, resolution="monthly")
    assert sorted(df["timestamp"].unique().to_list()) == [
        dt.datetime(2020, 1, 1, tzinfo=UTC),
        dt.datetime(2020, 2, 1, tzinfo=UTC),
    ]
    trace = _values("monthly", drop_nulls=False).filter(
        pl.col("parameter").eq("precipitation_amount"), pl.col("timestamp").dt.month().eq(2)
    )
    assert trace["value"].to_list() == [0.0]
    assert trace["quality_flags"].to_list() == ["raw:Ip"]


def test_aemet_annual_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The aggregate of the response (`-13`) is the annual row, stamped at the first of January."""
    _serve(monkeypatch, [_MONTH_1, _MONTH_2, _YEAR])
    df = _values("annual")
    _assert_the_long_form(df, resolution="annual")
    assert df["timestamp"].unique().to_list() == [dt.datetime(2020, 1, 1, tzinfo=UTC)]
    assert df.filter(pl.col("parameter").eq("temperature_air_max_2m"))["value"].to_list() == [39.4]


@pytest.mark.parametrize(
    ("resolution", "records"),
    [
        pytest.param("hourly", [{"ta": 14.2}], id="hourly-no-time-column"),
        pytest.param("annual", [_MONTH_1, _MONTH_2], id="annual-without-the-aggregate"),
        pytest.param("monthly", [_YEAR], id="monthly-without-a-month"),
    ],
)
def test_aemet_without_a_reading_comes_out_as_the_empty_long_form(
    monkeypatch: pytest.MonkeyPatch, resolution: str, records: list[dict[str, object]]
) -> None:
    """A response that holds no row of the resolution, or one without its time column: no rows."""
    _serve(monkeypatch, records)
    df = _values(resolution)
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()
