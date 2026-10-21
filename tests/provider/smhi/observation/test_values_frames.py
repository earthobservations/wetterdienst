# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frames the core hands out for SMHI's monthly, 1 minute and overlapping values and its empty answers (GH-2627).

The hourly and daily frames are held by `test_value_stubs.py` and `test_api_daily_stamp.py`. These cover what they leave
out: the monthly file (`Representativ månad`), the 1 minute file (`latest-day`, the one period), the two periods of the
hourly files that overlap by design, and the bodies that are no data file. The files are the shapes SMHI writes, served
through the provider's own reader, and `tests/provider/frames.snapshot.json` records what the core made of each: the net
under moving the shaping of the frame out of the provider.
"""

from __future__ import annotations

import datetime as dt
from io import BytesIO

import polars as pl
import pytest

from tests.provider.value_stubs import _options, _settings, stations_result
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.smhi.observation import SmhiObservationRequest
from wetterdienst.provider.smhi.observation import api as smhi_api
from wetterdienst.util.network import File

STATION = "188790"
UTC = dt.UTC

_MONTHLY_FROM_TO = "Från Datum Tid (UTC);Till Datum Tid (UTC);Representativ månad;Lufttemperatur;Kvalitet\n"
_MONTHLY_TEMPERATURE = (
    _MONTHLY_FROM_TO
    + "2025-01-01 00:00:01;2025-02-01 00:00:00;2025-01;-2.1;G\n"
    + "2025-02-01 00:00:01;2025-03-01 00:00:00;2025-02;0.4;Y\n"
)
# the corrected archive holds the first two hours, the latest months the last two: 11:00 is in both, and the
# corrected archive's copy is the one that stays
_HOURLY_CORRECTED_ARCHIVE = (
    "Datum;Tid (UTC);Lufttemperatur;Kvalitet\n2025-03-01;10:00:00;1.5;G\n2025-03-01;11:00:00;1.8;G\n"
)
_HOURLY_LATEST_MONTHS = (
    "Datum;Tid (UTC);Lufttemperatur;Kvalitet\n2025-03-01;11:00:00;9.9;Y\n2025-03-01;12:00:00;2.4;Y\n"
)
# parameter 48, "Vindriktning, medelvärde 1 min", with a calm as the 0 SMHI writes beside a speed (parameter 47) of 0
_ONE_MINUTE_DIRECTION = (
    "Datum;Tid (UTC);Vindriktning;Kvalitet\n2025-03-01;10:00:00;250.000000;G\n2025-03-01;10:01:00;0.000000;G\n"
)
_ONE_MINUTE_SPEED = (
    "Datum;Tid (UTC);Vindhastighet;Kvalitet\n2025-03-01;10:00:00;3.200000;G\n2025-03-01;10:01:00;0.000000;G\n"
)


def _serve(monkeypatch: pytest.MonkeyPatch, files: dict[str, str]) -> None:
    """Serve the files by a part of the url; any other file is a 404, as for a station without the parameter."""

    def download_file(url: str, **_: object) -> File:
        for part, text in files.items():
            if part in url:
                return File(url=url, content=BytesIO(text.encode()), status=200)
        return File(url=url, content=FileNotFoundError(url), status=404)

    monkeypatch.setattr(smhi_api, "download_file", download_file)


def _values(parameters: list[tuple[str, str, str]], start: dt.datetime, end: dt.datetime) -> pl.DataFrame:
    request = SmhiObservationRequest(
        parameters=parameters, start=start, end=end, settings=_settings(), options=_options(drop_nulls=False)
    )
    resolution = parameters[0][0]
    return stations_result(request, resolution, "data", STATION).values().all().df


def _assert_the_long_form(df: pl.DataFrame, *, resolution: str) -> None:
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df["resolution"].unique().to_list() == [resolution]
    assert df["dataset"].unique().to_list() == ["data"]
    assert df["station_id"].unique().to_list() == [STATION]
    assert df["timestamp"].dtype == pl.Datetime("us", "UTC")


def test_smhi_monthly_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The monthly file names its month, which is the stamp at the first of it."""
    _serve(monkeypatch, {"parameter/22/": _MONTHLY_TEMPERATURE})
    df = _values(
        [("monthly", "data", "temperature_air_mean_2m")],
        dt.datetime(2025, 1, 1, tzinfo=UTC),
        dt.datetime(2025, 2, 1, tzinfo=UTC),
    )
    _assert_the_long_form(df, resolution="monthly")
    assert df.sort("timestamp")["value"].to_list() == [-2.1, 0.4]
    assert df.sort("timestamp")["quality_flags"].to_list() == ["G", "Y"]


def test_smhi_1_minute_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 1 minute file is read from `latest-day` alone, and its calm (a direction of 0) is null beside its text."""
    _serve(
        monkeypatch,
        {
            "parameter/48/station/188790/period/latest-day/": _ONE_MINUTE_DIRECTION,
            "parameter/47/station/188790/period/latest-day/": _ONE_MINUTE_SPEED,
        },
    )
    df = _values(
        [("1_minute", "data", "wind_direction_mean")],
        dt.datetime(2025, 3, 1, 10, tzinfo=UTC),
        dt.datetime(2025, 3, 1, 10, 1, tzinfo=UTC),
    )
    _assert_the_long_form(df, resolution="1_minute")
    assert df.sort("timestamp")["value"].to_list() == [250.0, None]
    assert df.sort("timestamp")["quality_flags"].to_list() == ["G", "G,raw:0.000000"]


def test_smhi_hourly_values_of_the_two_overlapping_periods_come_out_as_one_row_per_hour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The hour both periods hold is read from the corrected archive, which is fetched first."""
    _serve(
        monkeypatch,
        {
            "parameter/1/station/188790/period/corrected-archive/": _HOURLY_CORRECTED_ARCHIVE,
            "parameter/1/station/188790/period/latest-months/": _HOURLY_LATEST_MONTHS,
        },
    )
    df = _values(
        [("hourly", "data", "temperature_air_2m")],
        dt.datetime(2025, 3, 1, 10, tzinfo=UTC),
        dt.datetime(2025, 3, 1, 12, tzinfo=UTC),
    )
    _assert_the_long_form(df, resolution="hourly")
    assert df.sort("timestamp")["value"].to_list() == [1.5, 1.8, 2.4]


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("", id="empty"),
        pytest.param("Stationsnamn;Stationsnummer\nAbisko Aut;188790\n", id="no-data-header"),
        pytest.param("Kvalitet;Lufttemperatur\nG;1.5\n", id="quality-first"),
        pytest.param("Datum;Lufttemperatur;Kvalitet\n2025-03-01;1.5;G\n", id="no-date-columns"),
        pytest.param("Datum;Tid (UTC);Lufttemperatur;Kvalitet\n;;;\n", id="no-row-with-a-date"),
    ],
)
def test_smhi_a_body_without_readings_comes_out_as_the_empty_long_form(
    monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    """A file that is no data file, or that holds no row with a date, is no rows."""
    _serve(monkeypatch, {"parameter/1/": body})
    df = _values(
        [("hourly", "data", "temperature_air_2m")],
        dt.datetime(2025, 3, 1, 10, tzinfo=UTC),
        dt.datetime(2025, 3, 1, 12, tzinfo=UTC),
    )
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()
