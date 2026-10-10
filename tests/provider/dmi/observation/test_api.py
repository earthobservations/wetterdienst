# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DMI (Danish Meteorological Institute) climate data observation provider."""

import datetime as dt
import json
import logging
from collections.abc import Callable
from io import BytesIO
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import polars as pl
import pytest

import wetterdienst.provider.dmi.observation.api as dmi_api
from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.settings import Settings
from wetterdienst.util.network import File

# Copenhagen (Zealand) — the reference station used across the remote tests.
COPENHAGEN_LANDBOHOJSKOLEN = "06180"
UTC = ZoneInfo("UTC")


def _dates_for(from_value: str, resolution: Resolution) -> dt.datetime:
    """Evaluate the provider's date expression for a single DMI ``from`` timestamp."""
    df = pl.DataFrame({"from": [from_value]}).select(
        dmi_api.DmiObservationValues._date_expression(resolution).alias("timestamp"),  # noqa: SLF001
    )
    return df.get_column("timestamp").to_list()[0]


def test_metadata_resolutions() -> None:
    """DMI exposes hour, day, month and year resolutions."""
    resolutions = {resolution.name for resolution in dmi_api.DmiObservationRequest.metadata}
    assert resolutions == {"hourly", "daily", "monthly", "annual"}


def test_metadata_no_auth() -> None:
    """DMI's open data service requires no authentication."""
    assert dmi_api.DmiObservationRequest.metadata.auth is False


def test_date_expression_hourly_is_utc_aligned() -> None:
    """Hourly aggregates are UTC-aligned and labelled by the start of the hour."""
    date = _dates_for("2023-06-01T00:00:00+00:00", Resolution.HOURLY)
    assert date == dt.datetime(2023, 6, 1, 0, 0, tzinfo=UTC)


def test_date_expression_hourly_tolerates_fractional_seconds() -> None:
    """Hourly parsing must not break if DMI includes fractional seconds in ``from``."""
    date = _dates_for("2023-06-01T00:00:00.000000+00:00", Resolution.HOURLY)
    assert date == dt.datetime(2023, 6, 1, 0, 0, tzinfo=UTC)


def test_date_expression_daily_uses_local_civil_date() -> None:
    """A Danish summer day (``from`` at +02:00) maps to that civil date at UTC midnight."""
    date = _dates_for("2023-06-02T00:00:00.001000+02:00", Resolution.DAILY)
    assert date == dt.datetime(2023, 6, 2, 0, 0, tzinfo=UTC)


def test_date_expression_daily_greenland_negative_offset() -> None:
    """A Greenland day (``from`` at a negative offset) maps to its civil date at UTC midnight.

    Taking the civil date straight from the ``from`` string keeps this correct regardless of
    the station's timezone — a naive UTC conversion would shift it onto the previous day.
    """
    date = _dates_for("2023-06-02T00:00:00.001000-02:00", Resolution.DAILY)
    assert date == dt.datetime(2023, 6, 2, 0, 0, tzinfo=UTC)


def test_date_expression_monthly_truncates_to_first_of_month() -> None:
    """Monthly aggregates are labelled by the first of the civil month at UTC midnight."""
    date = _dates_for("2023-07-01T00:00:00.001000+02:00", Resolution.MONTHLY)
    assert date == dt.datetime(2023, 7, 1, 0, 0, tzinfo=UTC)


def test_date_expression_annual_truncates_to_first_of_year() -> None:
    """Annual aggregates are labelled by the first of the civil year at UTC midnight."""
    date = _dates_for("2021-01-01T00:00:00.001000+01:00", Resolution.ANNUAL)
    assert date == dt.datetime(2021, 1, 1, 0, 0, tzinfo=UTC)


def _station_value_file(count: int, start: int = 0) -> File:
    """Build a DMI stationValue response File with ``count`` feature records."""
    features = [
        {
            "properties": {
                "parameterId": "mean_temp",
                "from": "2023-06-01T00:00:00+00:00",
                "value": float(index),
            },
        }
        for index in range(start, start + count)
    ]
    return File(url="", content=BytesIO(json.dumps({"features": features}).encode()), status=200)


def _iter_pages(values: dmi_api.DmiObservationValues) -> list[pl.DataFrame]:
    return list(
        values._iter_station_value_pages("06180", "hour", "start", "end", Settings(cache_disable=True)),  # noqa: SLF001
    )


def test_iter_station_value_pages_walks_all_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pagination advances the offset until a short (< limit) page and concatenates every page."""
    monkeypatch.setattr(dmi_api, "_PAGE_LIMIT", 2)
    # offset 0 -> full page (2), offset 2 -> full page (2), offset 4 -> short page (1) => stop
    pages = {0: 2, 2: 2, 4: 1}
    offsets: list[int] = []

    def fake_download_file(*, url: str, **_: object) -> File:
        offset = int(url.split("offset=")[1])
        offsets.append(offset)
        return _station_value_file(pages[offset], start=offset)

    monkeypatch.setattr(dmi_api, "download_file", fake_download_file)
    dfs = _iter_pages(object.__new__(dmi_api.DmiObservationValues))
    assert offsets == [0, 2, 4]
    assert len(dfs) == 3
    assert sum(df.height for df in dfs) == 5


def test_iter_station_value_pages_single_short_page_stops_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    """A first page shorter than the limit ends pagination after one request."""
    monkeypatch.setattr(dmi_api, "_PAGE_LIMIT", 100)
    offsets: list[int] = []

    def fake_download_file(*, url: str, **_: object) -> File:
        offsets.append(int(url.split("offset=")[1]))
        return _station_value_file(3)

    monkeypatch.setattr(dmi_api, "download_file", fake_download_file)
    dfs = _iter_pages(object.__new__(dmi_api.DmiObservationValues))
    assert offsets == [0]
    assert [df.height for df in dfs] == [3]


def test_iter_station_value_pages_raises_on_download_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A download error raises, rather than ending pagination with the pages so far read as the whole answer."""
    monkeypatch.setattr(dmi_api, "_PAGE_LIMIT", 2)

    def fake_download_file(*, url: str, **_: object) -> File:
        # first (full) page succeeds, second page errors
        if "offset=0" in url:
            return _station_value_file(2)
        return File(url=url, content=RuntimeError("boom"), status=500)

    monkeypatch.setattr(dmi_api, "download_file", fake_download_file)
    with pytest.raises(DownloadError, match="boom"):
        _iter_pages(object.__new__(dmi_api.DmiObservationValues))


def test_iter_station_value_pages_raises_no_internet_for_the_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    """A NoInternetError is raised as it is, for the caller to end the whole read quietly."""
    monkeypatch.setattr(dmi_api, "_PAGE_LIMIT", 2)

    def fake_download_file(*, url: str, **_: object) -> File:
        return File(url=url, content=NoInternetError("offline"), status=503)

    monkeypatch.setattr(dmi_api, "download_file", fake_download_file)
    with pytest.raises(NoInternetError):
        _iter_pages(object.__new__(dmi_api.DmiObservationValues))


@pytest.mark.remote
def test_dmi_observation_stations() -> None:
    """Station discovery returns deduplicated stations with usable metadata."""
    request = dmi_api.DmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
    ).all()
    assert not request.df.is_empty()
    # DMI lists a station once per validity period; the provider collapses these to one row.
    assert request.df.get_column("station_id").n_unique() == request.df.height
    station = request.df.filter(pl.col("station_id") == COPENHAGEN_LANDBOHOJSKOLEN)
    assert station.height == 1
    row = station.to_dicts()[0]
    assert row["name"]
    assert row["region"] == "DNK"
    assert 54 < row["latitude"] < 58
    assert 8 < row["longitude"] < 16


@pytest.mark.remote
def test_dmi_observation_values_daily() -> None:
    """Daily values include both range boundaries (the local/UTC offset must not drop them)."""
    request = dmi_api.DmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end=dt.datetime(2023, 6, 5, tzinfo=UTC),
    ).filter_by_station_id([COPENHAGEN_LANDBOHOJSKOLEN])
    values = request.values.all().df
    dates = values.get_column("timestamp").sort().to_list()
    assert dates[0] == dt.datetime(2023, 6, 1, tzinfo=UTC)
    assert dates[-1] == dt.datetime(2023, 6, 5, tzinfo=UTC)
    assert "UTC" in str(values.schema["timestamp"])
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_dmi_observation_values_hourly_utc() -> None:
    """Hourly values are UTC-aligned to the start of each hour."""
    request = dmi_api.DmiObservationRequest(
        parameters=[("hourly", "data", "temperature_air_2m")],
        start=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end=dt.datetime(2023, 6, 1, 6, tzinfo=UTC),
    ).filter_by_station_id([COPENHAGEN_LANDBOHOJSKOLEN])
    values = request.values.all().df
    first_date = values.get_column("timestamp").min()
    assert first_date == dt.datetime(2023, 6, 1, 0, 0, tzinfo=UTC)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_dmi_observation_values_empty_for_unknown_station() -> None:
    """An unknown station id yields an empty, well-formed values frame."""
    settings = Settings(cache_disable=True)
    request = dmi_api.DmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end=dt.datetime(2023, 6, 5, tzinfo=UTC),
        settings=settings,
    ).filter_by_station_id(["00000"])
    values = request.values.all().df
    assert values.is_empty()


class _FakeStationValueServer:
    """Stand-in for DMI's stationValue endpoint: one hourly record per hour, newest first.

    Applies the request's closed ``datetime`` window, ``limit`` and ``offset``, and refuses an offset
    above the cap the way DMI does (a 400), recording every offset it was asked for.
    """

    def __init__(self, first: dt.datetime, hours: int, max_offset: int) -> None:
        self.hours = [first + dt.timedelta(hours=hour) for hour in range(hours)]
        self.max_offset = max_offset
        self.offsets: list[int] = []

    def __call__(self, *, url: str, **_: object) -> File:
        query = dict(part.split("=", 1) for part in url.split("?", 1)[1].split("&"))
        offset, limit = int(query["offset"]), int(query["limit"])
        self.offsets.append(offset)
        if offset > self.max_offset:
            return File(url=url, content=RuntimeError("Offset cannot be greater than 500000"), status=400)
        window_start, window_end = (
            dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            for value in query["datetime"].split("/")
        )
        in_window = sorted((hour for hour in self.hours if window_start <= hour <= window_end), reverse=True)
        features = [
            {
                "properties": {
                    "parameterId": "mean_temp",
                    "from": hour.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "value": float(hour.timestamp()),
                },
            }
            for hour in in_window[offset : offset + limit]
        ]
        return File(url=url, content=BytesIO(json.dumps({"features": features}).encode()), status=200)


def _collect_hourly(
    monkeypatch: pytest.MonkeyPatch,
    server: _FakeStationValueServer,
    start: dt.datetime,
    end: dt.datetime,
    download_file: Callable[..., File] | None = None,
) -> pl.DataFrame:
    """Collect hourly mean_temp for one station through the provider, against the fake server."""
    monkeypatch.setattr(dmi_api, "_PAGE_LIMIT", 100)
    monkeypatch.setattr(dmi_api, "_MAX_OFFSET", server.max_offset)
    monkeypatch.setattr(dmi_api, "download_file", download_file or server)
    values = object.__new__(dmi_api.DmiObservationValues)
    values.sr = SimpleNamespace(  # ty: ignore[invalid-assignment]
        start=start,
        end=end,
        stations=SimpleNamespace(settings=Settings(cache_disable=True)),
    )
    dataset = dmi_api.DmiObservationMetadata["hourly"].datasets[0]
    return values._collect_station_parameter_or_dataset(COPENHAGEN_LANDBOHOJSKOLEN, dataset)  # noqa: SLF001


def test_collect_windows_a_long_range_below_the_offset_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """A range of several windows is read window by window; no offset is above the cap, no row is lost or doubled."""
    first = dt.datetime(2023, 1, 1, tzinfo=UTC)
    server = _FakeStationValueServer(first, hours=24 * 35, max_offset=200)
    # three windows of 10 days (241 records, so pages at offsets 0, 100, 200) and a short last one
    monkeypatch.setattr(dmi_api, "_WINDOW_SPAN", {Resolution.HOURLY: dt.timedelta(days=10)})
    df = _collect_hourly(monkeypatch, server, first, first + dt.timedelta(days=35))
    # three windows of three pages each, then the last of two: none had to be halved
    assert server.offsets == [0, 100, 200] * 3 + [0, 100]
    timestamps = df.get_column("timestamp").sort().to_list()
    assert timestamps == [first + dt.timedelta(hours=hour) for hour in range(24 * 35)]


def test_collect_halves_a_window_that_fills_every_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """A window with more records than the pages below the cap carry is halved, not paged past the cap."""
    first = dt.datetime(2023, 1, 1, tzinfo=UTC)
    server = _FakeStationValueServer(first, hours=24 * 30, max_offset=200)
    # the default span of a year puts all 720 records in one window: 3 full pages reach the cap
    df = _collect_hourly(monkeypatch, server, first, first + dt.timedelta(days=30))
    assert max(server.offsets) <= 200
    assert len(server.offsets) > 3
    timestamps = df.get_column("timestamp").sort().to_list()
    assert timestamps == [first + dt.timedelta(hours=hour) for hour in range(24 * 30)]


def test_collect_reads_a_short_range_in_one_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """A range inside one window is one request, as before windows existed."""
    first = dt.datetime(2023, 1, 1, tzinfo=UTC)
    server = _FakeStationValueServer(first, hours=24, max_offset=200)
    df = _collect_hourly(monkeypatch, server, first, first + dt.timedelta(hours=23))
    assert server.offsets == [0]
    assert df.height == 24


def test_fetch_station_value_pages_gives_up_where_a_second_holds_too_many(monkeypatch: pytest.MonkeyPatch) -> None:
    """Halving stops at a span of a second, so a source ignoring the window cannot recurse forever."""
    monkeypatch.setattr(dmi_api, "_PAGE_LIMIT", 2)
    monkeypatch.setattr(dmi_api, "_MAX_OFFSET", 2)
    monkeypatch.setattr(dmi_api, "download_file", lambda **_: _station_value_file(2))
    values = object.__new__(dmi_api.DmiObservationValues)
    start = dt.datetime(2023, 1, 1, tzinfo=UTC)
    with pytest.raises(DownloadError, match="more records than the pages"):
        values._fetch_station_value_pages(  # noqa: SLF001
            "06180", "hour", start, start + dt.timedelta(seconds=3), Settings(cache_disable=True), []
        )


def test_fetch_station_value_pages_drops_the_pages_of_a_halved_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pages read of a window that is then halved are not kept: only halves' boundary instants repeat."""
    monkeypatch.setattr(dmi_api, "_PAGE_LIMIT", 100)
    monkeypatch.setattr(dmi_api, "_MAX_OFFSET", 200)
    first = dt.datetime(2023, 1, 1, tzinfo=UTC)
    server = _FakeStationValueServer(first, hours=24 * 30, max_offset=200)
    monkeypatch.setattr(dmi_api, "download_file", server)
    values = object.__new__(dmi_api.DmiObservationValues)
    records: list[pl.DataFrame] = []
    values._fetch_station_value_pages(  # noqa: SLF001
        "06180", "hour", first, first + dt.timedelta(days=30), Settings(cache_disable=True), records
    )
    df = pl.concat(records)
    # each halving shares one instant at most; keeping the discarded pages would repeat hundreds of rows
    assert df.height - df.unique().height <= 10
    assert df.unique().height == 24 * 30


def test_collect_ends_quietly_at_the_window_without_a_connection(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Without a connection the read keeps the windows got so far, asks for no later one, and logs no warning."""
    first = dt.datetime(2023, 1, 1, tzinfo=UTC)
    server = _FakeStationValueServer(first, hours=24 * 35, max_offset=200)
    requests: list[str] = []

    def download_file(*, url: str, **kwargs: object) -> File:
        requests.append(url)
        if len(requests) > 3:  # the first window (3 pages) is read, the second one is offline
            return File(url=url, content=NoInternetError("offline"), status=503)
        return server(url=url, **kwargs)

    monkeypatch.setattr(dmi_api, "_WINDOW_SPAN", {Resolution.HOURLY: dt.timedelta(days=10)})
    with caplog.at_level(logging.WARNING):
        df = _collect_hourly(monkeypatch, server, first, first + dt.timedelta(days=35), download_file)
    assert len(requests) == 4
    assert df.height == 24 * 10 + 1
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]
