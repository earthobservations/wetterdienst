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
from tests.provider.value_stubs import stations_result
from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.settings import Settings
from wetterdienst.util.network import File

# Copenhagen (Zealand) — the reference station used across the remote tests.
COPENHAGEN_LANDBOHOJSKOLEN = "06180"
UTC = ZoneInfo("UTC")


def _dates_for(from_value: str, resolution: Resolution, to_value: str | None = None) -> dt.datetime:
    """Evaluate the provider's date expression for a single DMI ``from`` (and ``to``) timestamp."""
    df = pl.DataFrame({"from": [from_value], "to": [to_value]}, schema={"from": pl.String, "to": pl.String}).select(
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
    date = _dates_for("2023-06-02T00:00:00.001000+02:00", Resolution.DAILY, "2023-06-03T00:00:00+02:00")
    assert date == dt.datetime(2023, 6, 2, 0, 0, tzinfo=UTC)


def test_date_expression_daily_greenland_negative_offset() -> None:
    """A Greenland day (``from`` at a negative offset) maps to its civil date at UTC midnight.

    Taking the civil date straight from the ``to`` string keeps this correct regardless of
    the station's timezone, whatever sign its offset has.
    """
    date = _dates_for("2023-06-02T00:00:00.001000-02:00", Resolution.DAILY, "2023-06-03T00:00:00-02:00")
    assert date == dt.datetime(2023, 6, 2, 0, 0, tzinfo=UTC)


def test_date_expression_daily_old_meteorological_day() -> None:
    """A Greenland day of 06:00 UTC to 06:00 UTC is labelled by the date it starts on."""
    date = _dates_for("2025-03-30T06:00:00+00:00", Resolution.DAILY, "2025-03-31T06:00:00+00:00")
    assert date == dt.datetime(2025, 3, 30, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("from_value", "to_value", "day"),
    [
        # the window DMI gives as 23:31 local time of the previous day to 24.00 of the respective day (GH-2676)
        ("2025-03-29T23:31:00+01:00", "2025-03-31T00:00:00+02:00", dt.datetime(2025, 3, 30, tzinfo=UTC)),
        ("2025-03-30T23:31:00+02:00", "2025-04-01T00:00:00+02:00", dt.datetime(2025, 3, 31, tzinfo=UTC)),
        ("2025-03-28T23:31:00+01:00", "2025-03-30T00:00:00+01:00", dt.datetime(2025, 3, 29, tzinfo=UTC)),
    ],
)
def test_date_expression_daily_window_beginning_the_day_before(
    from_value: str, to_value: str, day: dt.datetime
) -> None:
    """``max_precip_30m`` begins at 23:31 of the previous day and belongs to the day it ends on."""
    assert _dates_for(from_value, Resolution.DAILY, to_value) == day


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


def test_iter_station_value_pages_never_asks_for_the_next_link_of_a_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pages are walked by offset, at DMI's own address: the `next` link of an answer is not a request (GH-3339)."""
    monkeypatch.setattr(dmi_api, "_PAGE_LIMIT", 2)
    asked: list[str] = []

    def fake_download_file(*, url: str, **_: object) -> File:
        asked.append(url)
        offset = int(url.split("offset=")[1])
        page = json.loads(_station_value_file(2 if offset < 2 else 1, start=offset).content.read())
        page["links"] = [{"rel": "next", "href": "http://192.0.2.1/latest/meta-data/iam"}]
        return File(url=url, content=BytesIO(json.dumps(page).encode()), status=200)

    monkeypatch.setattr(dmi_api, "download_file", fake_download_file)
    dfs = _iter_pages(object.__new__(dmi_api.DmiObservationValues))
    assert sum(df.height for df in dfs) == 3
    assert len(asked) == 2
    assert all(url.startswith("https://opendataapi.dmi.dk/v2/climateData/collections/") for url in asked)


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


def test_iter_station_value_pages_raises_no_internet(monkeypatch: pytest.MonkeyPatch) -> None:
    """A NoInternetError is raised as it is."""
    monkeypatch.setattr(dmi_api, "_PAGE_LIMIT", 2)

    def fake_download_file(*, url: str, **_: object) -> File:
        return File(url=url, content=NoInternetError("offline"), status=503)

    monkeypatch.setattr(dmi_api, "download_file", fake_download_file)
    with pytest.raises(NoInternetError):
        _iter_pages(object.__new__(dmi_api.DmiObservationValues))


def test_dmi_station_list_gives_the_country_not_a_region(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station's `country` is DMI's three-letter code and its `region` is null, DMI giving no region (GH-2019).

    DMI's `country` is `DNK`, `GRL` or `FRO` (4517, 127 and 22 of the 4666 station records on 2026-10-11), so
    it said which of the three a station is in and nothing about a region within it; the column that holds
    the sub-national region of every other provider held a country for DMI. The current record of a station
    gives its country.
    """

    def feature(station_id: str, name: str, country: str, created: str) -> dict:
        return {
            "geometry": {"coordinates": [12.0, 55.0]},
            "properties": {
                "stationId": station_id,
                "name": name,
                "country": country,
                "stationHeight": 10.0,
                "validFrom": "1948-12-31T00:00:00Z",
                "validTo": None,
                "created": created,
            },
        }

    catalogue = {
        "features": [
            feature("06180", "Landbohøjskolen", "DNK", "2026-09-30T11:59:36Z"),
            feature("04202", "Pituffik", "GRL", "2026-09-30T11:59:36Z"),
            feature("06011", "Tórshavn", "FRO", "2026-09-30T11:59:36Z"),
            feature("04202", "Pituffik", "DNK", "2020-01-01T00:00:00Z"),
        ],
    }
    monkeypatch.setattr(
        dmi_api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(json.dumps(catalogue).encode()), status=200),
    )

    df = dmi_api.DmiObservationRequest(parameters=[("daily", "data", "temperature_air_mean_2m")]).all().df

    assert sorted(df.select("station_id", "country", "region").rows()) == [
        ("04202", "GRL", None),
        ("06011", "FRO", None),
        ("06180", "DNK", None),
    ]


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
    assert row["country"] == "DNK"
    assert row["region"] is None
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
    values = request.values().all().df
    dates = values.get_column("timestamp").sort().to_list()
    assert dates[0] == dt.datetime(2023, 6, 1, tzinfo=UTC)
    assert dates[-1] == dt.datetime(2023, 6, 5, tzinfo=UTC)
    assert "UTC" in str(values.schema["timestamp"])
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_dmi_observation_values_hourly_utc() -> None:
    """Hourly values are UTC-aligned to the start of each hour."""
    request = dmi_api.DmiObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
        start=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end=dt.datetime(2023, 6, 1, 6, tzinfo=UTC),
    ).filter_by_station_id([COPENHAGEN_LANDBOHOJSKOLEN])
    values = request.values().all().df
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
    values = request.values().all().df
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
        request=SimpleNamespace(settings=Settings(cache_disable=True)),
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


@pytest.mark.parametrize(
    ("resolution", "window"),
    [
        # 02:00 to 06:00 in Copenhagen (UTC+2 in June) is 00:00 to 04:00 UTC, which an hourly request sends with an hour
        # more at the start: the 12 and 24 hour values are stamped by their `to`, an hour after their `from`
        ("hourly", "2023-05-31T23:00:00Z/2023-06-01T04:00:00Z"),
        # a daily request is widened by a day on each side, in UTC
        ("daily", "2023-05-31T00:00:00Z/2023-06-02T04:00:00Z"),
    ],
)
def test_collect_sends_the_bounds_of_a_request_in_local_time_as_utc(
    monkeypatch: pytest.MonkeyPatch, resolution: str, window: str
) -> None:
    """A request in Copenhagen time reaches DMI as the UTC instants its bounds stand for (GH-2682)."""
    sent: list[str] = []

    def download_file(*, url: str, **_: object) -> File:
        sent.append(url.split("datetime=", 1)[1].split("&", 1)[0])
        return File(url=url, content=BytesIO(b'{"features": []}'), status=200)

    monkeypatch.setattr(dmi_api, "download_file", download_file)
    copenhagen = ZoneInfo("Europe/Copenhagen")
    request = dmi_api.DmiObservationRequest(
        parameters=[(resolution, "data", "temperature_air_mean_2m")],
        start=dt.datetime(2023, 6, 1, 2, tzinfo=copenhagen),
        end=dt.datetime(2023, 6, 1, 6, tzinfo=copenhagen),
        settings=Settings(cache_disable=True),
    )
    values = dmi_api.DmiObservationValues(
        sr=stations_result(request, resolution, "data", COPENHAGEN_LANDBOHOJSKOLEN),
    )

    values._collect_station_parameter_or_dataset(COPENHAGEN_LANDBOHOJSKOLEN, request.parameters[0])  # noqa: SLF001

    assert sent == [window]


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


def test_collect_raises_at_the_window_without_a_connection(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Without a connection the read raises, asks for no later window, and logs no warning (GH-2640).

    The windows got so far are not returned: a series cut short is not the series that was asked for.
    """
    first = dt.datetime(2023, 1, 1, tzinfo=UTC)
    server = _FakeStationValueServer(first, hours=24 * 35, max_offset=200)
    requests: list[str] = []

    def download_file(*, url: str, **kwargs: object) -> File:
        requests.append(url)
        if len(requests) > 3:  # the first window (3 pages) is read, the second one is offline
            return File(url=url, content=NoInternetError("offline"), status=503)
        return server(url=url, **kwargs)

    monkeypatch.setattr(dmi_api, "_WINDOW_SPAN", {Resolution.HOURLY: dt.timedelta(days=10)})
    with caplog.at_level(logging.WARNING), pytest.raises(NoInternetError):
        _collect_hourly(monkeypatch, server, first, first + dt.timedelta(days=35), download_file)
    assert len(requests) == 4
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_collect_dates_daily_max_precipitation_by_the_day_it_ends_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rows as DMI serves them for 06180 (GH-2676): ``max_precip_30m`` begins the day before its day."""
    rows = [
        # (parameterId, from, to, value)
        ("max_precip_30m", "2025-03-28T23:31:00+01:00", "2025-03-30T00:00:00+01:00", 0.0),
        ("max_precip_30m", "2025-03-29T23:31:00+01:00", "2025-03-31T00:00:00+02:00", 3.8),
        ("max_precip_30m", "2025-03-30T23:31:00+02:00", "2025-04-01T00:00:00+02:00", 0.3),
        ("acc_precip", "2025-03-29T00:00:00.001000+01:00", "2025-03-30T00:00:00+01:00", 0.0),
        ("acc_precip", "2025-03-30T00:00:00.001000+01:00", "2025-03-31T00:00:00+02:00", 9.8),
    ]
    features = [
        {"properties": {"parameterId": parameter, "from": start, "to": end, "value": value}}
        for parameter, start, end, value in rows
    ]
    content = json.dumps({"features": features}).encode()
    monkeypatch.setattr(dmi_api, "download_file", lambda **_: File(url="", content=BytesIO(content), status=200))
    values = object.__new__(dmi_api.DmiObservationValues)
    values.sr = SimpleNamespace(  # ty: ignore[invalid-assignment]
        start=dt.datetime(2025, 3, 28, tzinfo=UTC),
        end=dt.datetime(2025, 4, 1, tzinfo=UTC),
        request=SimpleNamespace(settings=Settings(cache_disable=True)),
    )
    dataset = dmi_api.DmiObservationMetadata["daily"].datasets[0]
    df = values._collect_station_parameter_or_dataset(COPENHAGEN_LANDBOHOJSKOLEN, dataset)  # noqa: SLF001
    by_day = {(row["parameter"], row["timestamp"].date().isoformat()): row["value"] for row in df.iter_rows(named=True)}
    assert by_day == {
        ("max_precip_30m", "2025-03-29"): 0.0,
        ("max_precip_30m", "2025-03-30"): 3.8,
        ("max_precip_30m", "2025-03-31"): 0.3,
        ("acc_precip", "2025-03-29"): 0.0,
        ("acc_precip", "2025-03-30"): 9.8,
    }


def test_collect_nulls_the_wind_direction_of_an_hour_without_wind_and_no_other(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a mean wind direction of 0 is null where the mean wind speed is 0, and a bearing otherwise (GH-2794).

    Rows as DMI serves them for 06070 (checked 2026-10-12): 2020-02-14 02:00 and 04:00 have a direction of 0 beside
    0.3 m/s, 03:00 one of 0 beside 0 m/s, and 2020-05-02 03:00 one of 0 beside 1.2 m/s. The speed decides, and the 0
    it nulls stays as `raw:0` in `quality_flags`. The 250 and 360 at 06:00, and the 0 of 2020-05-02 05:00 that has no
    speed in its hour (an hour not known to be calm), are made up.
    """
    rows = [
        # (parameterId, from, value)
        ("mean_wind_dir", "2020-02-14T02:00:00+00:00", 0.0),
        ("mean_wind_speed", "2020-02-14T02:00:00+00:00", 0.3),
        ("mean_wind_dir", "2020-02-14T03:00:00+00:00", 0.0),
        ("mean_wind_speed", "2020-02-14T03:00:00+00:00", 0.0),
        ("mean_wind_dir", "2020-02-14T04:00:00+00:00", 0.0),
        ("mean_wind_speed", "2020-02-14T04:00:00+00:00", 0.3),
        ("mean_wind_dir", "2020-02-14T06:00:00+00:00", 250.0),
        ("mean_wind_speed", "2020-02-14T06:00:00+00:00", 4.1),
        ("mean_wind_dir", "2020-05-02T03:00:00+00:00", 0.0),
        ("mean_wind_speed", "2020-05-02T03:00:00+00:00", 1.2),
        ("mean_wind_dir", "2020-05-02T05:00:00+00:00", 0.0),
        ("mean_wind_dir", "2020-05-02T06:00:00+00:00", 360.0),
        ("mean_wind_speed", "2020-05-02T06:00:00+00:00", 5.0),
    ]
    features = [
        {
            "properties": {
                "parameterId": parameter,
                "from": start,
                "to": (dt.datetime.fromisoformat(start) + dt.timedelta(hours=1)).isoformat(),
                "value": value,
            }
        }
        for parameter, start, value in rows
    ]
    content = json.dumps({"features": features}).encode()
    monkeypatch.setattr(dmi_api, "download_file", lambda **_: File(url="", content=BytesIO(content), status=200))
    values = object.__new__(dmi_api.DmiObservationValues)
    values.sr = SimpleNamespace(  # ty: ignore[invalid-assignment]
        start=dt.datetime(2020, 2, 14, tzinfo=UTC),
        end=dt.datetime(2020, 5, 2, 6, tzinfo=UTC),
        request=SimpleNamespace(settings=Settings(cache_disable=True)),
    )
    dataset = dmi_api.DmiObservationMetadata["hourly"].datasets[0]
    df = values._collect_station_parameter_or_dataset("06070", dataset)  # noqa: SLF001
    direction = df.filter(pl.col("parameter") == "mean_wind_dir").sort("timestamp")
    assert direction.select("value", "quality_flags").rows() == [
        (0.0, None),
        (None, "raw:0"),
        (0.0, None),
        (250.0, None),
        (0.0, None),
        (0.0, None),
        (360.0, None),
    ]
    speed = df.filter(pl.col("parameter") == "mean_wind_speed").sort("timestamp")
    assert speed.get_column("value").to_list() == [0.3, 0.0, 0.3, 4.1, 1.2, 5.0]
    assert speed.get_column("quality_flags").is_null().all()


def test_collect_carries_qc_status_and_validity_in_quality_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """A flag DMI leaves out is left out; a daily 1978 mm of 04339 is no reading, null with the flags and `raw:1978`."""
    rows = [
        # (parameterId, from, value, qcStatus, validity)
        ("acc_precip", "2011-07-24T06:00:00+00:00", 1978.0, "manual", False),
        ("acc_precip", "2011-07-25T06:00:00+00:00", 3.4, "manual", True),
        ("mean_temp", "2011-07-24T06:00:00+00:00", 5.1, "none", True),
        ("mean_temp", "2011-07-25T06:00:00+00:00", 5.3, None, None),
        ("mean_temp", "2011-07-26T06:00:00+00:00", 5.5, None, False),
    ]
    features = [
        {
            "properties": {
                "parameterId": parameter,
                "from": start,
                "to": start,
                "value": value,
                "qcStatus": qc_status,
                "validity": validity,
            }
        }
        for parameter, start, value, qc_status, validity in rows
    ]
    content = json.dumps({"features": features}).encode()
    monkeypatch.setattr(dmi_api, "download_file", lambda **_: File(url="", content=BytesIO(content), status=200))
    values = object.__new__(dmi_api.DmiObservationValues)
    values.sr = SimpleNamespace(  # ty: ignore[invalid-assignment]
        start=dt.datetime(2011, 7, 24, tzinfo=UTC),
        end=dt.datetime(2011, 7, 27, tzinfo=UTC),
        request=SimpleNamespace(settings=Settings(cache_disable=True)),
    )
    dataset = dmi_api.DmiObservationMetadata["daily"].datasets[0]
    df = values._collect_station_parameter_or_dataset("04339", dataset)  # noqa: SLF001
    assert df.schema["quality_flags"] == pl.String
    flags = {(row["parameter"], row["value"]): row["quality_flags"] for row in df.iter_rows(named=True)}
    assert flags == {
        ("acc_precip", None): "manual,validity:false,rejected:range,raw:1978",
        ("acc_precip", 3.4): "manual,validity:true",
        ("mean_temp", 5.1): "none,validity:true",
        ("mean_temp", 5.3): None,
        ("mean_temp", 5.5): "validity:false",
    }


def _collect_station_values(resolution: str, rows: list[tuple[str, str, float, str, bool]]) -> pl.DataFrame:
    """Read rows as DMI serves them for 04339 through the reader, `(parameterId, from, value, qcStatus, validity)`."""
    features = [
        {
            "properties": {
                "parameterId": parameter,
                "from": start,
                "to": start,
                "value": value,
                "qcStatus": qc_status,
                "validity": validity,
            }
        }
        for parameter, start, value, qc_status, validity in rows
    ]
    content = json.dumps({"features": features}).encode()
    values = object.__new__(dmi_api.DmiObservationValues)
    values.sr = SimpleNamespace(  # ty: ignore[invalid-assignment]
        start=dt.datetime(2011, 7, 24, tzinfo=UTC),
        end=dt.datetime(2015, 1, 1, tzinfo=UTC),
        request=SimpleNamespace(settings=Settings(cache_disable=True)),
    )
    dataset = dmi_api.DmiObservationMetadata[resolution].datasets[0]
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(dmi_api, "download_file", lambda **_: File(url="", content=BytesIO(content), status=200))
        return values._collect_station_parameter_or_dataset("04339", dataset)  # noqa: SLF001


def test_collect_nulls_a_value_outside_the_range_of_its_parameter_and_keeps_what_it_was() -> None:
    """A month of 17,802 mm and one of 3,229.9 mm of 04339 are null with `raw:`; the 1,200 mm beside them is only odd.

    Rows as DMI serves them for 04339 (checked 2026-10-16): the monthly `acc_precip` of 2011-10 is 17802.0 and that of
    2012-10 is 3229.9, both with `qcStatus: manual` and `validity: false`. The 1,200 mm of the month before and the
    4021 degrees of `max_temp_w_date` are made up: the first is within the 1,500 mm bound of a month's precipitation
    (the most DMI validated is 641.8), the second is outside the range of an air temperature, each parameter having
    its own.
    """
    rows = [
        # (parameterId, from, value, qcStatus, validity)
        ("acc_precip", "2011-09-01T06:00:00+00:00", 1200.0, "manual", True),
        ("acc_precip", "2011-10-01T06:00:00+00:00", 17802.0, "manual", False),
        ("acc_precip", "2012-10-01T06:00:00+00:00", 3229.9, "manual", False),
        ("max_temp_w_date", "2011-09-01T06:00:00+00:00", 4021.0, "manual", True),
        ("max_temp_w_date", "2011-10-01T06:00:00+00:00", 8.5, "manual", True),
    ]
    df = _collect_station_values("monthly", rows)
    found = {(row["parameter"], row["timestamp"].year, row["timestamp"].month): row for row in df.iter_rows(named=True)}
    assert {key: (row["value"], row["quality_flags"]) for key, row in found.items()} == {
        ("acc_precip", 2011, 9): (1200.0, "manual,validity:true"),
        ("acc_precip", 2011, 10): (None, "manual,validity:false,rejected:range,raw:17802"),
        ("acc_precip", 2012, 10): (None, "manual,validity:false,rejected:range,raw:3229.9"),
        ("max_temp_w_date", 2011, 9): (None, "manual,validity:true,rejected:range,raw:4021"),
        ("max_temp_w_date", 2011, 10): (8.5, "manual,validity:true"),
    }


@pytest.mark.parametrize(
    ("resolution", "parameter"),
    [("daily", "acc_precip"), ("daily", "max_precip_30m"), ("monthly", "max_precip_24h"), ("hourly", "acc_precip")],
)
def test_collect_reads_the_trace_of_precipitation_as_zero_and_keeps_its_text(resolution: str, parameter: str) -> None:
    """DMI's -0.1 is a trace of precipitation: 0.0 with `raw:-0.1`, as the other providers write one (GH-3621).

    The lower bound of 0 of the range of the parameter read it as out of range and made it null.
    """
    rows = [
        (parameter, "2012-01-01T06:00:00+00:00", -0.1, "manual", True),
        (parameter, "2012-02-01T06:00:00+00:00", 0.0, "manual", True),
        (parameter, "2012-03-01T06:00:00+00:00", 1.2, "manual", True),
        # a negative amount that is no trace stays out of range
        (parameter, "2012-04-01T06:00:00+00:00", -0.5, "manual", True),
    ]
    df = _collect_station_values(resolution, rows).sort("timestamp")
    assert df.select("value", "quality_flags").rows() == [
        (0.0, "manual,validity:true,raw:-0.1"),
        (0.0, "manual,validity:true"),
        (1.2, "manual,validity:true"),
        (None, "manual,validity:true,rejected:range,raw:-0.5"),
    ]


def test_collect_reads_minus_0_1_of_no_precipitation_amount_as_a_trace() -> None:
    """The -0.1 is a trace of precipitation only: the same number of a temperature is a reading."""
    rows = [("mean_temp", "2012-01-01T06:00:00+00:00", -0.1, "manual", True)]
    df = _collect_station_values("monthly", rows)
    assert df.select("value", "quality_flags").rows() == [(-0.1, "manual,validity:true")]


@pytest.mark.parametrize(
    ("resolution", "reading", "no_reading"),
    [
        # `acc_precip` of 04339 (read 2026-10-16): 989 and 1978 mm in a day of 2011; 3,229.9 mm in the month 2012-10;
        # 9,574.3 mm in the year 2014. The readings are what DMI validated at most (183.5, 641.8 and 3,291.3 mm, 04390)
        ("daily", 183.5, 989.0),
        ("daily", 183.5, 1978.0),
        ("monthly", 641.8, 3229.9),
        ("annual", 3291.3, 9574.3),
        # the same number is a reading of a longer span: 989 mm is no day, but a month of rain
        ("monthly", 989.0, 17802.0),
        ("annual", 3229.9, 4178.9),
    ],
)
def test_collect_holds_the_rain_to_the_span_of_the_resolution(
    resolution: str, reading: float, no_reading: float
) -> None:
    """DMI's rain of a span is held to a range that grows with it: a day, a month and a year of 04339 (GH-2797)."""
    rows = [
        ("acc_precip", "2012-01-01T06:00:00+00:00", reading, "manual", True),
        ("acc_precip", "2013-01-01T06:00:00+00:00", no_reading, "manual", False),
    ]
    df = _collect_station_values(resolution, rows).sort("timestamp")
    assert df.select("value", "quality_flags").rows() == [
        (reading, "manual,validity:true"),
        (None, f"manual,validity:false,rejected:range,raw:{no_reading:.15g}"),
    ]


@pytest.mark.parametrize(
    ("resolution", "parameter", "reading", "no_reading"),
    [
        # the largest amount of a day of a month (04339 2011-10: 1978; 04320 2013-09: 999) and of a year (04320: 999)
        ("monthly", "max_precip_24h", 183.5, 1978.0),
        ("monthly", "max_precip_24h", 183.5, 999.0),
        ("annual", "max_precip_24h", 183.5, 999.0),
        # the largest of 30 minutes of the day can be no more than the day
        ("daily", "max_precip_30m", 40.0, 989.0),
    ],
)
def test_collect_holds_the_largest_amount_of_a_part_of_a_day_to_the_day(
    resolution: str, parameter: str, reading: float, no_reading: float
) -> None:
    """A maximum of a day or of half an hour is no more than a day of rain; some `max_precip_24h` has more (GH-2797)."""
    rows = [
        (parameter, "2012-01-01T06:00:00+00:00", reading, "manual", True),
        (parameter, "2013-01-01T06:00:00+00:00", no_reading, "manual", False),
    ]
    df = _collect_station_values(resolution, rows).sort("timestamp")
    assert df.select("value", "quality_flags").rows() == [
        (reading, "manual,validity:true"),
        (None, f"manual,validity:false,rejected:range,raw:{no_reading:.15g}"),
    ]


def test_collect_leaves_a_year_of_rain_that_a_validated_year_equals() -> None:
    """The 3,253.4 mm of 04339 in 2012 (a sum of the month of 3,229.9 mm) stays: 04390 has 3,291.3 mm, validated.

    No range tells the two years apart; `quality_flags` says `validity:false` for the one and `true` for the other.
    """
    rows = [
        ("acc_precip", "2012-01-01T06:00:00+00:00", 3253.4, "none", False),
        ("acc_precip", "2013-01-01T06:00:00+00:00", 3291.3, "manual", True),
    ]
    df = _collect_station_values("annual", rows).sort("timestamp")
    assert df.select("value", "quality_flags").rows() == [
        (3253.4, "none,validity:false"),
        (3291.3, "manual,validity:true"),
    ]


def _dmi_record(
    station_id: str,
    name: str,
    coordinates: tuple[float, float],
    elevation: float | None,
    valid_from: str,
    valid_to: str | None,
    created: str = "2026-09-30T11:59:36Z",
) -> dict:
    """Give a record of ``climateData/collections/station/items`` with the properties the reader reads."""
    return {
        "geometry": {"coordinates": list(coordinates)},
        "properties": {
            "stationId": station_id,
            "name": name,
            "country": "GRL",
            "stationHeight": elevation,
            "validFrom": valid_from,
            "validTo": valid_to,
            "created": created,
        },
    }


# Qaanaaq (04205) and Pituffik (04202) as the station list gave them on 2026-10-15, oldest record first, with the same
# `created` on all records of a station (964 of the 967 stations with several records)
_QAANAAQ = [
    _dmi_record("04205", "Qaanaaq", (-69.2, 77.4833), None, "1964-01-01T00:00:00Z", "1980-07-01T00:00:00Z"),
    _dmi_record(
        "04205", "Mittarfik Qaanaaq", (-69.3744, 77.4853), 16.0, "1980-07-01T00:00:00Z", "2019-01-15T13:34:47Z"
    ),
    _dmi_record("04205", "Mittarfik Qaanaaq", (-69.3744, 77.4853), 16.0, "2019-01-15T13:34:47Z", None),
]
_PITUFFIK = [
    _dmi_record("04202", "Pituffik", (-68.75, 76.5333), None, "1948-12-31T00:00:00Z", "2006-10-16T00:00:00Z"),
    _dmi_record("04202", "Pituffik", (-68.7031, 76.5311), 76.5, "2006-10-16T00:00:00Z", "2019-01-15T13:34:47Z"),
    _dmi_record("04202", "Pituffik", (-68.7031, 76.5311), 77.0, "2019-01-15T13:34:47Z", None),
]


def _dmi_stations(monkeypatch: pytest.MonkeyPatch, records: list[dict]) -> list[tuple]:
    """Read the station list from the records and give name, latitude, longitude and elevation per station."""
    body = json.dumps({"features": records}).encode()
    monkeypatch.setattr(
        dmi_api, "download_file", lambda **kwargs: File(url=kwargs["url"], content=BytesIO(body), status=200)
    )
    df = dmi_api.DmiObservationRequest(parameters=[("daily", "data", "temperature_air_mean_2m")]).all().df
    return sorted(df.select("station_id", "name", "latitude", "longitude", "elevation").rows())


def test_dmi_station_is_listed_with_its_current_record_not_its_oldest(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station with several records takes name, position and elevation of the one still open (GH-2946).

    `created` is the same on all the records of a station and the list has them oldest first, so a sort by it left the
    oldest record: Qaanaaq as `Qaanaaq` at 77.4833 / -69.2 without an elevation, Pituffik without one.
    """
    assert _dmi_stations(monkeypatch, [*_QAANAAQ, *_PITUFFIK]) == [
        ("04202", "Pituffik", 76.5311, -68.7031, 77.0),
        ("04205", "Mittarfik Qaanaaq", 77.4853, -69.3744, 16.0),
    ]


def test_dmi_current_record_does_not_depend_on_the_order_of_the_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """The record is picked by the period it is valid for, wherever the list puts it (GH-2946)."""
    assert _dmi_stations(monkeypatch, list(reversed(_PITUFFIK))) == [("04202", "Pituffik", 76.5311, -68.7031, 77.0)]


def test_dmi_station_without_an_open_record_takes_the_one_that_ended_last(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station whose records are all closed takes the one with the latest `validTo` (GH-2946)."""
    first = _dmi_record("04202", "Old", (-68.0, 76.0), None, "1900-01-01T00:00:00Z", "1948-12-31T00:00:00Z")
    assert _dmi_stations(monkeypatch, [first, *_PITUFFIK[:2]]) == [("04202", "Pituffik", 76.5311, -68.7031, 76.5)]


def test_dmi_records_of_one_period_take_the_one_written_last(monkeypatch: pytest.MonkeyPatch) -> None:
    """Of records with the same period the one with the latest `created` is the current one (GH-2946)."""
    period = ("2019-01-15T13:34:47Z", None)
    records = [
        _dmi_record("04202", "Pituffik", (-68.7, 76.5), None, *period, created="2026-09-30T11:59:36Z"),
        _dmi_record("04202", "Pituffik AB", (-68.7, 76.5), 77.0, *period, created="2026-10-01T00:00:00Z"),
    ]
    assert _dmi_stations(monkeypatch, list(reversed(records))) == [("04202", "Pituffik AB", 76.5, -68.7, 77.0)]


def test_dmi_records_of_one_period_and_one_creation_take_the_one_listed_last(monkeypatch: pytest.MonkeyPatch) -> None:
    """Of records that differ in nothing but their content the one the list gives last is the current one (GH-2946)."""
    period = ("2019-01-15T13:34:47Z", None)
    first = _dmi_record("04202", "Pituffik", (-68.7, 76.5), None, *period)
    last = _dmi_record("04202", "Pituffik AB", (-68.7, 76.5), 77.0, *period)
    assert _dmi_stations(monkeypatch, [first, last]) == [("04202", "Pituffik AB", 76.5, -68.7, 77.0)]
    assert _dmi_stations(monkeypatch, [last, first]) == [("04202", "Pituffik", 76.5, -68.7, None)]
