# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for LHMT (Lithuania) observation provider."""

import datetime as dt
import logging
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.provider.lhmt.observation import LhmtObservationRequest
from wetterdienst.provider.lhmt.observation.parser import (
    parse_lhmt_observations,
    parse_lhmt_stations,
)
from wetterdienst.util.network import File

UTC = ZoneInfo("UTC")
VILNIUS = "vilniaus-ams"
KAUNAS = "kauno-ams"


def test_parse_lhmt_stations() -> None:
    """The station list maps to one row per station with coordinates from the nested object."""
    content = (
        b'[{"code": "vilniaus-ams", "name": "Vilniaus AMS", '
        b'"coordinates": {"latitude": 54.625992, "longitude": 25.107064}}]'
    )
    df = parse_lhmt_stations(content)
    assert df.to_dicts() == [
        {
            "station_id": "vilniaus-ams",
            "name": "Vilniaus AMS",
            "latitude": 54.625992,
            "longitude": 25.107064,
        },
    ]


def test_parse_lhmt_observations() -> None:
    """Observations become long rows; unmapped fields are dropped and missing values stay null."""
    content = (
        b'{"station": {"code": "vilniaus-ams"}, "observations": ['
        b'{"observationTimeUtc": "2020-07-01 12:00:00", "airTemperature": 22.3, '
        b'"feelsLikeTemperature": 22.3, "windSpeed": 4.7, "windGust": 12.3, "windDirection": 261, '
        b'"cloudCover": 63, "seaLevelPressure": 1007.4, "relativeHumidity": 52, '
        b'"precipitation": null, "snowDepth": 0, "conditionCode": "cloudy"}]}'
    )
    df = parse_lhmt_observations(content)
    by_param = {row["parameter"]: row["value"] for row in df.to_dicts()}
    assert by_param == {
        "airTemperature": 22.3,
        "windSpeed": 4.7,
        "windGust": 12.3,
        "windDirection": 261.0,
        "cloudCover": 63.0,
        "seaLevelPressure": 1007.4,
        "relativeHumidity": 52.0,
        "precipitation": None,  # null passes through as null (no sentinel)
        "snowDepth": 0.0,
    }
    # feelsLikeTemperature and conditionCode are intentionally not mapped
    assert "feelsLikeTemperature" not in by_param
    assert "conditionCode" not in by_param
    assert df["timestamp"].to_list() == [dt.datetime(2020, 7, 1, 12, 0, tzinfo=UTC)] * len(df)


def test_parse_lhmt_observations_empty() -> None:
    """A day with no observations yields an empty frame with the expected schema."""
    content = b'{"station": {"code": "vilniaus-ams"}, "observations": []}'
    df = parse_lhmt_observations(content)
    assert df.is_empty()
    assert df.columns == ["timestamp", "parameter", "value"]


def test_parse_lhmt_malformed_json_yields_empty() -> None:
    """A malformed 200 body (e.g. an HTML error page) yields an empty frame, not an exception."""
    assert parse_lhmt_observations(b"<html>rate limited</html>").is_empty()
    assert parse_lhmt_stations(b"not json").is_empty()


def test_parse_lhmt_skips_malformed_items() -> None:
    """Valid JSON with malformed items degrades to the good rows rather than raising."""
    # observations: a non-dict entry, one missing the timestamp, and one whose timestamp string is
    # malformed are all dropped; the cleanly-timestamped one stays (no exception for the bad string)
    obs = (
        b'{"station": {"code": "x"}, "observations": ['
        b'"garbage", {"airTemperature": 1.0}, '
        b'{"observationTimeUtc": "not-a-timestamp", "airTemperature": 9.9}, '
        b'{"observationTimeUtc": "2020-07-01 12:00:00", "airTemperature": 22.3}]}'
    )
    df = parse_lhmt_observations(obs)
    assert df["timestamp"].unique().to_list() == [dt.datetime(2020, 7, 1, 12, 0, tzinfo=UTC)]
    temp = df.filter(pl.col("parameter") == "airTemperature")
    assert temp["value"].to_list() == [22.3]

    # stations: entries missing a code or coordinates are skipped; the complete one survives
    stations = (
        b'[{"name": "no code"}, {"code": "y", "coordinates": {}}, '
        b'{"code": "vilniaus-ams", "name": "Vilniaus AMS", '
        b'"coordinates": {"latitude": 54.6, "longitude": 25.1}}]'
    )
    sdf = parse_lhmt_stations(stations)
    assert sdf["station_id"].to_list() == ["vilniaus-ams"]


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        # single UTC day (start == end date) -> one day
        (dt.datetime(2020, 7, 1, tzinfo=UTC), dt.datetime(2020, 7, 1, 23, tzinfo=UTC), [dt.date(2020, 7, 1)]),
        # inclusive multi-day span -> every day incl. both ends
        (
            dt.datetime(2020, 7, 1, tzinfo=UTC),
            dt.datetime(2020, 7, 3, tzinfo=UTC),
            [dt.date(2020, 7, 1), dt.date(2020, 7, 2), dt.date(2020, 7, 3)],
        ),
        # month/year rollover
        (
            dt.datetime(2019, 12, 31, tzinfo=UTC),
            dt.datetime(2020, 1, 1, tzinfo=UTC),
            [dt.date(2019, 12, 31), dt.date(2020, 1, 1)],
        ),
    ],
)
def test_days_covers_range_inclusive(start: dt.datetime, end: dt.datetime, expected: list[dt.date]) -> None:
    """`_days` yields every calendar date in [start, end] inclusive, of bounds in UTC as a request holds them.

    A request in another zone is converted before it gets here, which the Vilnius test below pins.
    """
    from wetterdienst.provider.lhmt.observation.api import _days  # noqa: PLC0415

    assert list(_days(start, end)) == expected


# ---------------------------------------------------------------------------
# Remote tests -- hit the live (key-less) api.meteo.lt. Historical data is stable, so exact values
# can be asserted. An outage skips the test (the `remote` marker, see `tests/conftest.py`).
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_lhmt_observation_stations() -> None:
    """The station catalogue resolves to Lithuanian stations, including Vilnius."""
    df = LhmtObservationRequest(parameters=[("hourly", "data")]).all().df
    assert df.height > 40
    assert df["resolution"].unique().to_list() == ["hourly"]
    assert VILNIUS in df["station_id"].to_list()
    # Lithuania: latitudes ~53.9-56.4 N, longitudes ~21-26.8 E
    assert df["latitude"].min() > 53.0
    assert df["latitude"].max() < 57.0
    assert df["longitude"].min() > 20.0
    assert df["longitude"].max() < 27.0


@pytest.mark.remote
def test_lhmt_observation_values() -> None:
    """Historical hourly values at Vilnius for 2020-07-01 match the api.meteo.lt reference values."""
    df = (
        LhmtObservationRequest(
            parameters=[("hourly", "data")],
            start=dt.datetime(2020, 7, 1, tzinfo=UTC),
            end=dt.datetime(2020, 7, 1, 23, tzinfo=UTC),
        )
        .filter_by_station_id(VILNIUS)
        .values()
        .all()
        .df
    )
    assert not df.is_empty()
    assert df["resolution"].unique().to_list() == ["hourly"]

    def value_at(parameter: str, hour: int) -> float:
        return df.filter(
            pl.col("parameter") == parameter,
            pl.col("timestamp") == dt.datetime(2020, 7, 1, hour, tzinfo=UTC),
        )["value"].item()

    assert value_at("temperature_air_2m", 12) == pytest.approx(22.3)
    assert value_at("wind_speed", 12) == pytest.approx(4.7)
    assert value_at("wind_direction", 12) == pytest.approx(261.0)
    assert value_at("pressure_air_sea_level", 12) == pytest.approx(1007.4)
    # humidity is converted from percent to the default decimal target (52 % -> 0.52)
    assert value_at("humidity_relative", 12) == pytest.approx(0.52)


_STATIONS_JSON = (
    b'[{"code": "vilniaus-ams", "name": "Vilniaus AMS", '
    b'"coordinates": {"latitude": 54.625992, "longitude": 25.107064}}, '
    b'{"code": "kauno-ams", "name": "Kauno AMS", '
    b'"coordinates": {"latitude": 54.8847, "longitude": 23.8363}}]'
)
_DAY_JSON = (
    b'{"station": {"code": "vilniaus-ams"}, "observations": ['
    b'{"observationTimeUtc": "2020-07-01 12:00:00", "airTemperature": 22.3}]}'
)


def _fake_download_file(monkeypatch: pytest.MonkeyPatch, *answers: bytes | Exception, status: int = 503) -> list[str]:
    """Serve the station list, answer the day requests with `answers` in order, the last for all after.

    A bytes answer is a body (status 200), an exception a failed download with `status`. Returns the
    day URLs requested.
    """
    attempted: list[str] = []

    def fake_download_file(url: str, *_args: object, **_kwargs: object) -> File:
        if url.endswith("/stations"):
            return File(url=url, content=BytesIO(_STATIONS_JSON), status=200)
        attempted.append(url)
        answer = answers[min(len(attempted), len(answers)) - 1]
        if isinstance(answer, Exception):
            return File(url=url, content=answer, status=status)
        return File(url=url, content=BytesIO(answer), status=200)

    monkeypatch.setattr("wetterdienst.provider.lhmt.observation.api.download_file", fake_download_file)
    return attempted


def _lhmt_values(days: int) -> pl.DataFrame:
    start = dt.datetime(2020, 7, 1, tzinfo=UTC)
    return (
        LhmtObservationRequest(
            parameters=[("hourly", "data")],
            start=start,
            end=start + dt.timedelta(days=days - 1),
        )
        .filter_by_station_id(VILNIUS)
        .values()
        .all()
        .df
    )


def test_lhmt_observation_values_offline_raise_at_the_first_day(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Offline, the day loop raises `NoInternetError` after one request and logs no warning (GH-2640)."""
    attempted = _fake_download_file(monkeypatch, NoInternetError("no route to host"))
    with caplog.at_level(logging.DEBUG, logger="wetterdienst.provider.lhmt"), pytest.raises(NoInternetError):
        _lhmt_values(days=30)
    assert len(attempted) == 1
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_lhmt_observation_values_offline_raise_at_the_first_station(monkeypatch: pytest.MonkeyPatch) -> None:
    """Offline, the request ends at the first download: the second station is not tried (GH-2620)."""
    attempted = _fake_download_file(monkeypatch, NoInternetError("no route to host"))
    start = dt.datetime(2020, 7, 1, tzinfo=UTC)
    request = LhmtObservationRequest(
        parameters=[("hourly", "data")], start=start, end=start + dt.timedelta(days=29)
    ).filter_by_station_id([VILNIUS, KAUNAS])
    with pytest.raises(NoInternetError):
        request.values().all()
    assert len(attempted) == 1


def test_lhmt_observation_values_going_offline_midway_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A network lost after the first day raises, instead of answering with that day's values: they are partial."""
    attempted = _fake_download_file(monkeypatch, _DAY_JSON, NoInternetError("no route to host"))
    with pytest.raises(NoInternetError):
        _lhmt_values(days=30)
    assert len(attempted) == 2


def test_lhmt_observation_values_missing_day_does_not_stop_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 404 (a day before the station's record) contributes no rows; the next days are still read."""
    attempted = _fake_download_file(monkeypatch, Exception("not found"), status=404)
    df = _lhmt_values(days=5)
    assert df.is_empty()
    assert len(attempted) == 5


def test_lhmt_observation_values_of_days_without_observations_are_the_empty_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Days the API answers (200) with no observation, or with no JSON, are no rows (GH-2627)."""
    attempted = _fake_download_file(
        monkeypatch,
        b'{"station": {"code": "vilniaus-ams"}, "observations": []}',
        b"<html>rate limited</html>",
    )
    df = _lhmt_values(days=3)
    assert df.is_empty()
    assert df.schema["value"] == pl.Float64
    assert len(attempted) == 3


def test_lhmt_observation_values_failed_day_still_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failure that is neither a missing day nor a missing network raises, as before (GH-2461)."""
    attempted = _fake_download_file(monkeypatch, Exception("server error"), status=500)
    with pytest.raises(DownloadError):
        _lhmt_values(days=5)
    assert len(attempted) == 1


def _hourly_day_json(day: dt.date) -> bytes:
    """Build the 24 hourly observations of one UTC day, each reading the hour it is stamped with."""
    observations = ", ".join(
        f'{{"observationTimeUtc": "{day.isoformat()} {hour:02d}:00:00", "airTemperature": {hour}.0}}'
        for hour in range(24)
    )
    return f'{{"station": {{"code": "vilniaus-ams"}}, "observations": [{observations}]}}'.encode()


def _serve_hourly_days(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve the station list and a full day of readings for whichever UTC day is asked, returning the days asked."""
    asked: list[str] = []

    def download_file(url: str, *_args: object, **_kwargs: object) -> File:
        if url.endswith("/stations"):
            return File(url=url, content=BytesIO(_STATIONS_JSON), status=200)
        day = url.rsplit("/", 1)[-1]
        asked.append(day)
        return File(url=url, content=BytesIO(_hourly_day_json(dt.date.fromisoformat(day))), status=200)

    monkeypatch.setattr("wetterdienst.provider.lhmt.observation.api.download_file", download_file)
    return asked


@pytest.mark.parametrize(
    ("start", "end"),
    [
        pytest.param(
            dt.datetime(2025, 3, 30, 0, tzinfo=ZoneInfo("Europe/Vilnius")),
            dt.datetime(2025, 3, 30, 23, tzinfo=ZoneInfo("Europe/Vilnius")),
            id="named zone",
        ),
        pytest.param("2025-03-30T00:00+02:00", "2025-03-30T23:00+03:00", id="fixed offset"),
        pytest.param("2025-03-29T22:00:00", "2025-03-30T20:00:00", id="naive"),
    ],
)
def test_lhmt_observation_values_window_in_vilnius_time_across_the_clock_change(
    monkeypatch: pytest.MonkeyPatch,
    start: str | dt.datetime,
    end: str | dt.datetime,
) -> None:
    """A Vilnius day of 23 hours comes back as its 23 UTC hours, however the bounds are written (GH-2682).

    2025-03-30 is the day Vilnius moves to summer time: its midnight is 22:00 UTC on the 29th (UTC+2) and its
    23:00 is 20:00 UTC (UTC+3). A named zone raised a polars `SchemaError` once the days were read.
    """
    asked = _serve_hourly_days(monkeypatch)
    df = (
        LhmtObservationRequest(parameters=[("hourly", "data", "temperature_air_2m")], start=start, end=end)
        .filter_by_station_id(VILNIUS)
        .values()
        .all()
        .df
    )
    assert asked == ["2025-03-29", "2025-03-30"]
    assert df.height == 23
    assert df["timestamp"].dtype == pl.Datetime("us", "UTC")
    assert df["timestamp"].min() == dt.datetime(2025, 3, 29, 22, tzinfo=UTC)
    assert df["timestamp"].max() == dt.datetime(2025, 3, 30, 20, tzinfo=UTC)
