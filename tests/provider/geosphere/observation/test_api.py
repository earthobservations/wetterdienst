# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for geosphere observation API."""

import json
from datetime import datetime, timedelta
from io import BytesIO
from itertools import pairwise
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from dirty_equals import IsNumeric
from freezegun import freeze_time

from wetterdienst.exceptions import NoInternetError
from wetterdienst.provider.geosphere.observation import GeosphereObservationRequest, api
from wetterdienst.provider.geosphere.observation.api import _time_windows
from wetterdienst.settings import Settings
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
        # windows of ten years from 1880-03-30; the archive runs across the boundary near 1930
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
    # a span beyond the range, even one of centuries, leaves it whole
    assert list(_time_windows(start, end, timedelta(days=365 * 30000))) == [(start, end)]
    # a window that ends before it starts has nothing to ask for
    assert list(_time_windows(end, start, timedelta(days=730))) == []


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


def test_geosphere_observation_windows_of_a_local_time_request_leave_no_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that windows cut from a request in a local time zone still follow each other in UTC.

    Adding two years to 03:00 Vienna time on 2000-10-28 lands on 03:00 on 2002-10-27, the day the
    clocks go back, an hour later in UTC than the 24-hour days it spans, and the hour between the
    windows was never requested.
    """
    vienna = ZoneInfo("Europe/Vienna")
    windows = _serve_archive(
        monkeypatch,
        timedelta(minutes=10),
        datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC")),
        datetime(2000, 1, 2, tzinfo=ZoneInfo("UTC")),
    )
    request = GeosphereObservationRequest(
        parameters=[("10_minutes", "data", "humidity_relative")],
        start=datetime(2000, 10, 28, 3, tzinfo=vienna),
        end=datetime(2003, 1, 1, tzinfo=vienna),
    )
    request.filter_by_station_id("4821").values.all()
    assert len(windows) > 1
    assert all(nxt[0] - prev[1] == timedelta(minutes=1) for prev, nxt in pairwise(windows))


def _parameter_key(name: str) -> int:
    """Return a number that tells one parameter's readings from another's."""
    return sum(map(ord, name))


def _serve_archive_of_parameters(
    monkeypatch: pytest.MonkeyPatch,
    step: timedelta,
    archive_start: datetime,
    archive_end: datetime,
) -> list[tuple[datetime, datetime, list[str], str]]:
    """Serve one station's regular archive of any parameters, refusing slices over the API's limit.

    The upstream API counts timestamps times parameters, and so does this: it fails above 1,000,000
    data points. Reading ``i`` of a parameter is ``i + 1e6 * _parameter_key(parameter)``, so a reading
    that landed on another parameter or timestamp shows. Returns the window, the parameters and the dataset
    of each request.
    """
    requests = []

    def _download(url: str, **_kwargs: object) -> File:
        if url.endswith("/metadata/stations"):
            return File(url=url, content=BytesIO(_STATIONS), status=200)
        query = parse_qs(urlparse(url).query)
        start, end = (
            datetime.strptime(query[key][0], "%Y-%m-%dT%H:%M").replace(tzinfo=ZoneInfo("UTC"))
            for key in ("start", "end")
        )
        names = query["parameters"][0].split(",")
        requests.append((start, end, names, urlparse(url).path.rsplit("/", 1)[-1]))
        if ((end - start) // step + 1) * len(names) > _API_LIMIT:
            return File(url=url, content=FileNotFoundError(url), status=400)
        first = max(0, -((start - archive_start) // -step))
        last = (min(end, archive_end) - archive_start) // step
        timestamps = [archive_start + i * step for i in range(first, last + 1)]
        parameters = {
            # the API answers in alphabetical order, whatever the order asked for
            name: {"data": [float(i + 1e6 * _parameter_key(name)) for i in range(first, last + 1)]}
            for name in sorted(names)
        }
        body = {
            "timestamps": [timestamp.strftime("%Y-%m-%dT%H:%M+00:00") for timestamp in timestamps],
            "features": [{"properties": {"parameters": parameters}}],
        }
        return File(url=url, content=BytesIO(json.dumps(body).encode()), status=200)

    monkeypatch.setattr(api, "download_file", _download)
    return requests


@pytest.mark.parametrize(
    ("resolution", "step", "archive_start", "archive_end", "n_requests"),
    [
        # windows of 17,391 timestamps (about 121 days) for 23 parameters from 1992-05-19
        (
            "10_minutes",
            timedelta(minutes=10),
            datetime(1992, 9, 1, tzinfo=ZoneInfo("UTC")),
            datetime(1992, 12, 1, tzinfo=ZoneInfo("UTC")),
            87,
        ),
        # windows of 21,052 hours (about 877 days) for 19 parameters from 1880-03-30
        (
            "hourly",
            timedelta(hours=1),
            datetime(1882, 6, 1, tzinfo=ZoneInfo("UTC")),
            datetime(1882, 12, 1, tzinfo=ZoneInfo("UTC")),
            59,
        ),
        # windows of 25,000 days (about 68 years) for 16 parameters from 1774-12-30; the whole record
        # of 16 daily parameters is 1.47 million points, which the API refuses in one request
        (
            "daily",
            timedelta(days=1),
            datetime(1843, 1, 1, tzinfo=ZoneInfo("UTC")),
            datetime(1843, 12, 31, tzinfo=ZoneInfo("UTC")),
            4,
        ),
        (
            "monthly",
            timedelta(days=30),
            datetime(1900, 1, 1, tzinfo=ZoneInfo("UTC")),
            datetime(1910, 1, 1, tzinfo=ZoneInfo("UTC")),
            1,
        ),
    ],
)
@freeze_time(datetime(2020, 12, 2, 13, 37, 21, tzinfo=ZoneInfo("UTC")))
def test_geosphere_observation_values_of_a_whole_dataset_batch_the_parameters(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    step: timedelta,
    archive_start: datetime,
    archive_end: datetime,
    n_requests: int,
) -> None:
    """Test that a whole dataset without dates is fetched with all its parameters in each request (GH-2517).

    One request per parameter and window needed 285 to 414 requests for a dataset at 10 minutes or
    hourly, against the 240 an hour the API allows. Each parameter's every reading must still arrive
    once, with its own values, also on the boundaries between windows.
    """
    requests = _serve_archive_of_parameters(monkeypatch, step, archive_start, archive_end)
    request = GeosphereObservationRequest(
        parameters=[(resolution, "data")],
        settings=Settings(ts_humanize=False, ts_convert_units=False),
    )
    names = [parameter.name_original for parameter in request.parameters]
    df = request.filter_by_station_id("4821").values.all().df
    # every request asks for every parameter, and there are few enough of them
    assert all(sorted(asked) == sorted(names) for _, _, asked, _ in requests)
    assert len(requests) == n_requests <= 240
    # a window starts inside the archive, so a reading on a boundary is among those checked
    assert n_requests == 1 or any(archive_start < begin < archive_end for begin, _, _, _ in requests)
    expected = (archive_end - archive_start) // step + 1
    assert df.height == expected * len(names)
    for name in names:
        series = df.filter(pl.col("parameter") == name).sort("timestamp")
        assert series.get_column("timestamp").to_list() == [archive_start + i * step for i in range(expected)]
        assert series.get_column("value").to_list() == [float(i + 1e6 * _parameter_key(name)) for i in range(expected)]


def test_geosphere_observation_values_ask_for_the_requested_parameters_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a request names the parameters asked for, per dataset, and not the rest of the dataset (GH-2517)."""
    start = datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC"))
    end = datetime(2000, 1, 3, tzinfo=ZoneInfo("UTC"))
    requests = _serve_archive_of_parameters(monkeypatch, timedelta(hours=1), start, end)
    request = GeosphereObservationRequest(
        parameters=[
            ("hourly", "data", "temperature_air_mean_2m"),
            ("10_minutes", "data", "humidity_relative"),
            ("hourly", "data", "humidity_relative"),
        ],
        start=start,
        end=end,
        settings=Settings(ts_humanize=False, ts_convert_units=False),
    )
    df = request.filter_by_station_id("4821").values.all().df
    assert [(names, dataset) for _, _, names, dataset in requests] == [
        (["tl", "rf"], "klima-v2-1h"),
        (["rf"], "klima-v2-10min"),
    ]
    assert df.group_by("resolution", "parameter").len().sort("resolution", "parameter").rows() == [
        ("10_minutes", "rf", 49),
        ("hourly", "rf", 49),
        ("hourly", "tl", 49),
    ]


@pytest.mark.synthetic_values  # the archive's readings count timestamps and parameters, they are no temperatures
@pytest.mark.parametrize("resolution", ["daily", "monthly"])
@freeze_time(datetime(2020, 12, 2, 13, 37, 21, tzinfo=ZoneInfo("UTC")))
def test_geosphere_observation_values_of_one_daily_or_monthly_parameter_are_one_request(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
) -> None:
    """Test that one parameter at a resolution that never needs windows still asks for the whole record (GH-2517).

    The window is 400,000 timestamps, as many as the API would take, and for months that is 30,000
    years, beyond what a date can hold when added to the start.
    """
    start = datetime(1900, 1, 1, tzinfo=ZoneInfo("UTC"))
    requests = _serve_archive_of_parameters(monkeypatch, timedelta(days=30), start, start + timedelta(days=90))
    request = GeosphereObservationRequest(parameters=[(resolution, "data", "temperature_air_mean_2m")])
    df = request.filter_by_station_id("4821").values.all().df
    assert len(requests) == 1
    assert df.height == 4


def test_geosphere_observation_stations_that_still_report_have_no_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the 2100-12-31 the list gives a station that still reports is no end, and a real end is kept."""
    stations = (
        "id,Stationsname,Länge [°E],Breite [°N],Höhe [m],Startdatum,Enddatum,Bundesland,Sonnenschein,Globalstrahlung\n"
        "1,Aflenz,15.24069,47.54594,783.2,1983-05-01 00:00:00+00:00,2100-12-31 00:00:00+00:00,Steiermark,True,True\n"
        "12,Baden,16.235556,48.011391,244.8,1954-04-01 00:00:00+00:00,2012-05-31 23:59:59+00:00,Niederösterreich,"
        "True,False\n"
    ).encode()
    monkeypatch.setattr(api, "download_file", lambda url, **_: File(url=url, content=BytesIO(stations), status=200))

    df = GeosphereObservationRequest(parameters=[("daily", "data", "temperature_air_mean_2m")]).all().df

    assert dict(zip(df["station_id"], df["end_timestamp"], strict=True)) == {
        "1": None,
        "12": datetime(2012, 5, 31, 23, 59, 59, tzinfo=ZoneInfo("UTC")),
    }
