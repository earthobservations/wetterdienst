# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for geosphere observation API."""

import json
from datetime import datetime, timedelta
from io import BytesIO
from itertools import pairwise
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import pytest
from dirty_equals import IsNumeric
from freezegun import freeze_time

from wetterdienst.exceptions import NoInternetError
from wetterdienst.provider.geosphere.observation import GeosphereObservationRequest, api
from wetterdienst.provider.geosphere.observation.api import _time_windows
from wetterdienst.util.network import File


@pytest.mark.remote
def test_geosphere_observation_api() -> None:
    """Test the correct parsing of data, especially the dates.

    Thanks, @mhuber89, for the discovery and fix!
    """
    stations_at = GeosphereObservationRequest(
        parameters=[("hourly", "data", "wind_speed")],
        start=datetime(2022, 6, 1, tzinfo=ZoneInfo("UTC")),
        end=datetime(2022, 6, 2, tzinfo=ZoneInfo("UTC")),
    )
    station_at = stations_at.filter_by_station_id("4821")
    df = station_at.values.all().df
    assert df.get_column("value").is_not_null().sum() == 25


@pytest.mark.remote
@pytest.mark.parametrize(
    ("resolution", "parameter", "expected_rows", "expected_sum"),
    [
        # cglo, served as irradiance in W / m² and passed through unconverted
        ("minute_10", "radiation_global_intensity", 288, IsNumeric(ge=82770.0, le=82870.0)),
        ("hourly", "radiation_global_intensity", 48, IsNumeric(ge=13790.0, le=13815.0)),
        # cglo_j, a distinct upstream parameter already accumulated over the day in J / cm²
        ("daily", "radiation_global", 2, IsNumeric(ge=4966.2000, le=4972.0000)),
    ],
)
def test_geosphere_observation_api_radiation(
    resolution: str,
    parameter: str,
    expected_rows: int,
    expected_sum: IsNumeric,
) -> None:
    """Test that radiation is reported in the unit the source publishes it in.

    Geosphere serves ``cglo`` as irradiance (W / m²) at 10 minutes and hourly, and ``cglo_j`` as
    irradiation accumulated over the interval (J / cm²) at daily and monthly. The sub-daily values used
    to be multiplied by the interval length in the parser to make them look like the daily ones; they
    now keep their own unit and canonical name instead. The expected sums are equivalent to the former
    J / cm² ones scaled by that interval: 82851 * 0.06 and 13795 * 0.36 both land in the daily range.

    The row count is asserted alongside the sum because the window is a fixed and complete stretch of
    archive, so a sum that drifts because rows went missing should say so rather than read as the unit
    having changed.
    """
    stations_at = GeosphereObservationRequest(
        parameters=[(resolution, "data", parameter)],
        start=datetime(2022, 6, 1, tzinfo=ZoneInfo("UTC")),
        end=datetime(2022, 6, 2, hour=23, minute=50, tzinfo=ZoneInfo("UTC")),
    )
    station_at = stations_at.filter_by_station_id("4821")
    df = station_at.values.all().df
    assert df.get_column("value").is_not_null().sum() == expected_rows
    # the result is slightly different for each resolution
    assert df.get_column("value").sum() == expected_sum


_STATIONS = (
    "id,Stationsname,Länge [°E],Breite [°N],Höhe [m],Startdatum,Enddatum,Bundesland,Sonnenschein,Globalstrahlung\n"
    "4821,Test,16.0,48.0,200,1992-05-20 00:00:00+00:00,2100-01-01 00:00:00+00:00,Wien,True,True\n"
).encode()


def _data_window(monkeypatch: pytest.MonkeyPatch, requests: int = 1, **dates: datetime) -> tuple[str, str]:
    """Request one station's values offline and return the start and end the data URLs carry.

    A long window is split, so these run from the first request's start to the last one's end.
    """
    data_urls = []

    def _download(url: str, **_kwargs: object) -> File:
        if url.endswith("/metadata/stations"):
            return File(url=url, content=BytesIO(_STATIONS), status=200)
        data_urls.append(url)
        return File(url=url, content=BytesIO(b'{"timestamps": [], "features": []}'), status=200)

    monkeypatch.setattr(api, "download_file", _download)

    request = GeosphereObservationRequest(parameters=[("10_minutes", "data", "humidity_relative")], **dates)
    request.filter_by_station_id("4821").values.all()

    assert len(data_urls) == requests
    return parse_qs(urlparse(data_urls[0]).query)["start"][0], parse_qs(urlparse(data_urls[-1]).query)["end"][0]


def test_geosphere_observation_request_window_carries_the_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the start and end sent upstream keep the request's minutes.

    The window was formatted with ``%H:%m``, so the minute position carried the month: a request
    starting 13:37 in December sent ``13:12`` (GH-2436). The values are cut to the requested span
    locally, so this showed only in the URL, and with it the cache key.
    """
    start, end = _data_window(
        monkeypatch,
        start=datetime(2020, 12, 2, 13, 37, tzinfo=ZoneInfo("UTC")),
        end=datetime(2020, 12, 3, 8, 45, tzinfo=ZoneInfo("UTC")),
    )
    # one day of buffer on either side of the requested window
    assert start == "2020-12-01T13:37"
    assert end == "2020-12-04T08:45"


@freeze_time(datetime(2020, 12, 2, 13, 37, 21, tzinfo=ZoneInfo("UTC")))
def test_geosphere_observation_open_ended_window_ends_on_the_hour(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a request without dates ends its window on the hour, not on the current minute.

    Without dates the window ends a day after now. Sent to the minute, that URL, and so the cache
    key, would change every minute and a repeat of the whole-record download within the cache's
    five minutes would miss; floored to the hour, a repeat builds the same URL unless an hour
    boundary falls between them (GH-2436).
    """
    # the record from 1992-05-19 to 2020-12-03, in windows of two years
    start, end = _data_window(monkeypatch, requests=15)
    # the 10 minutes record's default start, less the one-day buffer
    assert start == "1992-05-19T00:00"
    assert end == "2020-12-03T13:00"


_API_LIMIT = 1_000_000


def _serve_archive(
    monkeypatch: pytest.MonkeyPatch,
    step: timedelta,
    archive_start: datetime,
    archive_end: datetime,
) -> list[tuple[datetime, datetime]]:
    """Serve one station from a regular archive, refusing slices over the API's data point limit.

    Like the upstream API, a window includes both its ends, counts the points it asks for and not
    the ones the archive holds, and fails above 1,000,000 of them. Returns the windows asked for.
    """
    windows = []

    def _download(url: str, **_kwargs: object) -> File:
        if url.endswith("/metadata/stations"):
            return File(url=url, content=BytesIO(_STATIONS), status=200)
        query = parse_qs(urlparse(url).query)
        start, end = (
            datetime.strptime(query[key][0], "%Y-%m-%dT%H:%M").replace(tzinfo=ZoneInfo("UTC"))
            for key in ("start", "end")
        )
        windows.append((start, end))
        if (end - start) // step + 1 > _API_LIMIT:
            return File(url=url, content=FileNotFoundError(url), status=400)
        first = max(0, -((start - archive_start) // -step))
        last = (min(end, archive_end) - archive_start) // step
        timestamps = [archive_start + i * step for i in range(first, last + 1)]
        body = {
            "timestamps": [timestamp.strftime("%Y-%m-%dT%H:%M+00:00") for timestamp in timestamps],
            "features": [{"properties": {"parameters": {"rf": {"data": [1.0] * len(timestamps)}}}}],
        }
        return File(url=url, content=BytesIO(json.dumps(body).encode()), status=200)

    monkeypatch.setattr(api, "download_file", _download)
    return windows


@pytest.mark.parametrize(
    ("resolution", "step", "archive_start", "archive_end"),
    [
        # the archive runs across the first window boundary, two years after 1992-05-19
        (
            "10_minutes",
            timedelta(minutes=10),
            datetime(1992, 5, 20, tzinfo=ZoneInfo("UTC")),
            datetime(1995, 1, 1, tzinfo=ZoneInfo("UTC")),
        ),
        # windows of ten years from 1880-03-29; the archive runs across the boundary near 1930
        (
            "hourly",
            timedelta(hours=1),
            datetime(1929, 1, 1, tzinfo=ZoneInfo("UTC")),
            datetime(1931, 1, 1, tzinfo=ZoneInfo("UTC")),
        ),
    ],
)
@freeze_time(datetime(2020, 12, 2, 13, 37, 21, tzinfo=ZoneInfo("UTC")))
def test_geosphere_observation_values_without_dates_stay_under_the_api_limit(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    step: timedelta,
    archive_start: datetime,
    archive_end: datetime,
) -> None:
    """Test that a request without dates is split into windows the API accepts (GH-2466).

    The whole record from 1992 at 10 minutes is 1.8 million points, and from 1880 hourly 1.28
    million, so the single request the values asked for was refused with HTTP 400. Every reading
    of the archive must arrive exactly once, also the ones on the boundaries between windows.
    """
    windows = _serve_archive(monkeypatch, step, archive_start, archive_end)
    request = GeosphereObservationRequest(parameters=[(resolution, "data", "humidity_relative")])
    df = request.filter_by_station_id("4821").values.all().df
    # a window starts inside the archive, so a reading on a boundary is among those checked
    assert any(archive_start < begin < archive_end for begin, _ in windows)
    timestamps = df.get_column("timestamp").to_list()
    expected = (archive_end - archive_start) // step + 1
    assert timestamps == [archive_start + i * step for i in range(expected)]


def test_geosphere_observation_values_of_a_long_explicit_window_are_split(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an explicit 10 minutes window beyond the limit is split too (GH-2466)."""
    start = datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC"))
    end = datetime(2025, 1, 1, tzinfo=ZoneInfo("UTC"))
    windows = _serve_archive(monkeypatch, timedelta(minutes=10), start, start + timedelta(days=1))
    request = GeosphereObservationRequest(
        parameters=[("10_minutes", "data", "humidity_relative")], start=start, end=end
    )
    df = request.filter_by_station_id("4821").values.all().df
    assert len(windows) == 13
    assert df.height == 145


def test_geosphere_observation_time_windows_leave_no_gap_and_no_overlap() -> None:
    """Test that the windows cover the span from start to end, each reading in exactly one."""
    start = datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    end = datetime(2022, 3, 5, 13, 40, tzinfo=ZoneInfo("UTC"))
    windows = list(_time_windows(start, end, timedelta(days=730)))
    assert windows[0][0] == start
    assert windows[-1][1] == end
    assert all(stop - begin <= timedelta(days=730) for begin, stop in windows)
    assert all(nxt[0] - prev[1] == timedelta(minutes=1) for prev, nxt in pairwise(windows))
    assert list(_time_windows(start, end, None)) == [(start, end)]


def test_geosphere_observation_values_lost_midway_are_empty_not_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that losing the connection on a later window leaves no series with years missing."""
    start = datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC"))
    end = datetime(2005, 1, 1, tzinfo=ZoneInfo("UTC"))
    windows = _serve_archive(monkeypatch, timedelta(minutes=10), start, end)
    serve = api.download_file

    def _lose_the_third_window(url: str, **kwargs: object) -> File:
        if len(windows) == 2 and not url.endswith("/metadata/stations"):
            return File(url=url, content=NoInternetError(url), status=0)
        return serve(url, **kwargs)

    monkeypatch.setattr(api, "download_file", _lose_the_third_window)
    request = GeosphereObservationRequest(
        parameters=[("10_minutes", "data", "humidity_relative")],
        start=start,
        end=end,
    )
    assert request.filter_by_station_id("4821").values.all().df.is_empty()
