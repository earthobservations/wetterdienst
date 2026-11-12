# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The values of KNMI, read from its EDR API (GH-3928).

Every `values` call goes through the EDR API, in chunks of at most 300,000 points. The rows are those that the Open Data
files route returned (`files/frozen_*.csv`, `test_the_rows_are_the_rows_the_file_route_returned`), and the requests are
as few as the limit allows for the stations asked for.

Served by a local server that stands for the API (`edr_stub`), with the data of real answers where the test says so and
made up where it counts requests.
"""

from __future__ import annotations

import datetime as dt
import itertools
import logging
import math
import time
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from tests.provider.knmi.observation import catalogue
from tests.provider.knmi.observation.catalogue import locations_frame
from tests.provider.knmi.observation.edr_stub import (
    DE_BILT,
    FILES,
    PARAMETERS,
    REAL,
    SCHIPHOL,
    EdrStub,
    World,
    real_world,
)
from wetterdienst.exceptions import CredentialMissingError, CredentialRejectedError, DownloadError, RequestError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.knmi.observation import api, edr
from wetterdienst.provider.knmi.observation.api import KnmiObservationRequest
from wetterdienst.provider.knmi.observation.grid import advance
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

# the made-up worlds hold numbers that are no readings (a humidity of -10 %), which the check of the ranges stands aside
# from; the real answers are read with it as well (`soft`: the values come back, flagged)
pytestmark = pytest.mark.synthetic_values

UTC = dt.UTC
NOW = dt.datetime(2026, 11, 12, 12, 30, tzinfo=UTC)
KEY = "knmi-edr-key-for-test-9f3a"
EELDE = "06280"
ROTTERDAM = "06344"
EINDHOVEN = "06370"
DEELEN = "06275"


@pytest.fixture(autouse=True)
def _pinned_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the time that the age of a chunk and the end of the data are taken against."""
    monkeypatch.setattr(api, "_now", lambda: NOW)


def _at(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=UTC)


class Reader:
    """Read the values of stations from the stand-in of the API, with a key or without one, as a request does."""

    def __init__(self, tmp_path: Path) -> None:
        """Keep the cache of the answers of the API in a directory of the test."""
        self.cache = tmp_path / "cache"

    def settings(self, *, key: str | None = KEY) -> Settings:
        """Give the settings, with the key of the EDR API unless it is left out."""
        return Settings(auth={"knmi_edr": key} if key else {}, cache_dir=self.cache)

    def values(
        self,
        parameters: list[tuple[str, ...]],
        start: dt.datetime,
        end: dt.datetime,
        stations: Sequence[str] = (DE_BILT,),
        *,
        key: str | None = KEY,
        options: dict | None = None,
    ) -> api.KnmiObservationValues:
        """Build the reader of the values of the stations."""
        request = KnmiObservationRequest(
            parameters=parameters,
            start=start,
            end=end,
            settings=self.settings(key=key),
            options={"plausibility": "soft", **(options or {})},
        )
        return request.filter_by_station_id(list(stations)).values()

    def read(
        self,
        parameters: list[tuple[str, ...]],
        start: dt.datetime,
        end: dt.datetime,
        stations: Sequence[str] = (DE_BILT,),
        *,
        key: str | None = KEY,
        options: dict | None = None,
    ) -> pl.DataFrame:
        """Read the values of the stations."""
        return self.values(parameters, start, end, stations, key=key, options=options).all().df


@pytest.fixture
def reader(tmp_path: Path) -> Reader:
    """Read values, keeping the cache in the directory of the test."""
    return Reader(tmp_path)


def _serve(server: EdrStub, *worlds: World) -> None:
    """Give the stub of the EDR API the data of the worlds."""
    for world in worlds:
        server.worlds[edr.COLLECTION_BY_RESOLUTION[world.resolution]] = world
        server.known |= set(world.cells)


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Give the WARNING lines of the provider (the core adds its own about stations without rows)."""
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and r.name.startswith("wetterdienst.provider")
    ]


def _frozen(name: str, *, drop_nulls: bool) -> pl.DataFrame:
    """Read the rows that the Open Data files route returned for a real answer, as they were written."""
    path = FILES / f"frozen_{name}_{'dropped' if drop_nulls else 'kept'}.csv"
    return pl.read_csv(
        path, schema_overrides={"station_id": pl.String, "quality_flags": pl.String, "timestamp": pl.String}
    ).with_columns(pl.col("timestamp").str.to_datetime(time_unit="us", time_zone="UTC"))


@pytest.mark.parametrize("drop_nulls", [True, False], ids=["nulls dropped", "nulls kept"])
@pytest.mark.parametrize("name", ["10_minutes", "hourly", "daily", "monthly", "annual"])
def test_the_rows_are_the_rows_the_file_route_returned(
    edr_server: EdrStub, reader: Reader, name: str, *, drop_nulls: bool
) -> None:
    """An answer of the EDR API is made into the rows the Open Data files route made of the same data, until GH-3928.

    The frozen rows (`files/frozen_*.csv`) are what that route returned for the real answers saved for each resolution,
    with the codes of the files laid in (a trace of rain and of sunshine, a calm and a variable wind, an invisible sky,
    a NaN): the columns, the dtypes, `quality_flags` and the `raw:` tokens. A parameter that De Bilt has no sensor for
    at 10 minutes (`vv`) is a NaN of the file and left out of its coverage by the API: with the nulls kept it is a
    row of both. This is the contract of the reader, and the reason the sentinel step is the one that was.
    """
    world = real_world(name)
    _serve(edr_server, world)
    start, end = REAL[name]

    df = reader.read([(name, "data")], start, end, list(world.cells), options={"drop_nulls": drop_nulls})

    assert edr_server.data_requests(), "the EDR API was not asked"
    frozen = _frozen(name, drop_nulls=drop_nulls)
    columns = ["station_id", "parameter", "timestamp"]
    assert_frame_equal(df.sort(columns), frozen.sort(columns))


def test_the_10_minute_tg_has_no_row_before_the_first_file_that_carried_it(edr_server: EdrStub, reader: Reader) -> None:
    """The files held no `tg` before the one named 2020-07-23 07:40, so the file route returned no row of it before.

    The API leaves `tg` out of the answer for those stamps (as for a station with no sensor), which is read as a NaN
    row of every stamp: the empty rows before 07:40 are taken out, so that the nulls kept are the rows the files gave. A
    value the API holds there stays. From 07:40 the NaN is a row, as the variable was in the file.
    """
    world = World.generated(Resolution.MINUTE_10, [DE_BILT], _at(2020, 7, 23, 7, 10), 8)
    del world.cells[DE_BILT]["tg"]
    # a value of `tg` that the API holds before the first file that carried it is data, and stays
    world.cells[DE_BILT]["tg"] = {_at(2020, 7, 23, 7, 20): 14.5}
    _serve(edr_server, world)

    df = reader.read(
        [("10_minutes", "data")],
        _at(2020, 7, 23, 7, 10),
        _at(2020, 7, 23, 8, 20),
        options={"drop_nulls": False, "humanize": False},
    )

    tg = df.filter(pl.col("parameter") == "tg")
    assert tg.get_column("timestamp").to_list() == [_at(2020, 7, 23, 7, 20)] + [
        _at(2020, 7, 23, 7, minute) for minute in (40, 50)
    ] + [_at(2020, 7, 23, 8, minute) for minute in (0, 10, 20)]
    assert tg.get_column("value").to_list()[0] == 14.5
    assert tg.get_column("value").null_count() == tg.height - 1
    assert set(tg.get_column("quality_flags").drop_nulls()) == {"raw:NaN"}
    # every other parameter has a row of every stamp
    assert df.filter(pl.col("parameter") == "ta").height == 8


def test_the_stamp_of_a_day_is_the_day_and_not_the_end_of_it(edr_server: EdrStub, reader: Reader) -> None:
    """De Bilt on 2020-01-01 (TG 0.8, TN -0.2, TX 1.8, RH 0.0) is stamped `2020-01-02T00:00Z` by the API (GH-3928).

    The row is dated 2020-01-01, as the file route dated it.
    """
    world = World.real("daily")
    assert world.cells[DE_BILT]["TG"][_at(2020, 1, 2)] == 0.8
    _serve(edr_server, world)
    parameters = [
        ("daily", "data", name)
        for name in (
            "temperature_air_mean_2m",
            "temperature_air_min_2m",
            "temperature_air_max_2m",
            "precipitation_amount",
        )
    ]
    df = reader.read(parameters, _at(2020, 1, 1), _at(2020, 1, 1), [DE_BILT], options={"humanize": False})
    assert dict(df.select("parameter", "value").iter_rows()) == {"TG": 0.8, "TN": -0.2, "TX": 1.8, "RH": 0.0}
    assert df.get_column("timestamp").unique().to_list() == [_at(2020, 1, 1)]
    # one request for the day, which the API stamps with the end of it: a day is the whole year of its block
    assert [parse_qs(urlsplit(path).query)["datetime"][0] for path in edr_server.data_requests()] == [
        "2020-01-02T00:00:00Z/2021-01-01T00:00:00Z"
    ]


def _hourly(count: int = 200, stations: Sequence[str] = (DE_BILT,), first: dt.datetime | None = None) -> World:
    return World.generated(Resolution.HOURLY, list(stations), first or _at(2020, 1, 1), count)


def _stations(path: str) -> list[str]:
    """Give the stations a request names."""
    return urlsplit(path).path.rsplit("/", 1)[-1].split(",")


def _datetime(path: str) -> tuple[str, str]:
    start, end = parse_qs(urlsplit(path).query)["datetime"][0].split("/")
    return start, end


def _points(path: str, resolution: Resolution) -> int:
    """Count the points a request holds, as the API does: times * parameters * stations."""
    query = parse_qs(urlsplit(path).query)
    start, end = (dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) for text in _datetime(path))
    return edr.count_stamps(start, end, resolution) * len(query["parameter-name"][0].split(",")) * len(_stations(path))


# --- the key ------------------------------------------------------------------------------------------------------


def test_without_the_key_nothing_is_asked_and_the_request_says_which_key(edr_server: EdrStub, reader: Reader) -> None:
    """No `knmi_edr`, no request: the error names the setting, where the key is asked for, and that an old one fails."""
    with pytest.raises(CredentialMissingError) as raised:
        reader.values([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 3), key=None)

    message = str(raised.value)
    assert "WD_AUTH__KNMI_EDR" in message
    assert "https://developer.dataplatform.knmi.nl/edr-api" in message
    assert "Open Data" in message
    assert edr_server.requests == []


@pytest.mark.parametrize("status", [401, 403])
def test_a_key_that_is_refused_is_an_error_that_says_an_edr_key_is_needed(
    caplog: pytest.LogCaptureFixture, edr_server: EdrStub, reader: Reader, status: int
) -> None:
    """A 401 or a 403 says where to get an EDR key, that an Open Data key no longer works, and never the key."""
    _serve(edr_server, _hourly())
    edr_server.statuses.extend([status])

    with caplog.at_level(logging.DEBUG), pytest.raises(CredentialRejectedError) as raised:
        reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 3))

    message = str(raised.value)
    assert f"HTTP {status}" in message
    assert "WD_AUTH__KNMI_EDR" in message
    assert "EDR" in message
    assert "https://developer.dataplatform.knmi.nl/edr-api" in message
    assert "Open Data" in message
    assert KEY not in message
    assert KEY not in caplog.text
    # the first request that carried the key was the last
    assert len(edr_server.requests) == 1


def test_a_gateway_that_refuses_the_key_before_the_stations_is_the_same_error(
    edr_server: EdrStub, reader: Reader
) -> None:
    """The first request of a query is the list of the stations: a key the gateway refuses is met there."""
    edr_server.key = "another-key"

    with pytest.raises(CredentialRejectedError, match="WD_AUTH__KNMI_EDR"):
        reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 3))

    assert [request["status"] for request in edr_server.requests] == [403]


# --- the requests that a query costs ---------------------------------------------------------------------------


def test_one_station_over_a_range_is_asked_for_in_blocks_of_the_calendar(edr_server: EdrStub, reader: Reader) -> None:
    """One station: a month of 10-minute values for each month of the range, so that an overlapping query is a hit."""
    world = World.generated(Resolution.MINUTE_10, [DE_BILT], _at(2026, 9, 30, 23, 0), 6 * 24 * 40)
    _serve(edr_server, world)

    df = reader.read([("10_minutes", "data")], _at(2026, 10, 1, 0, 10), _at(2026, 11, 8))

    assert df.get_column("timestamp").n_unique() == 6 * 24 * 38
    # a 10-minute stamp is the end of its interval, so the month of October is (2026-10-01 00:00, 2026-11-01 00:00]
    assert [_datetime(path) for path in edr_server.data_requests()] == [
        ("2026-10-01T00:10:00Z", "2026-11-01T00:00:00Z"),
        ("2026-11-01T00:10:00Z", "2026-11-12T12:30:00Z"),
    ]


def test_many_stations_for_a_day_are_one_request_of_the_hours_asked_for(edr_server: EdrStub, reader: Reader) -> None:
    """Six stations for a day of hourly values: one request of 24 stamps, where blocks of a year would be three.

    A year of hourly values of one station is 105,408 points, so the blocks of the calendar take two stations a request.
    Asking for the stamps that were asked for takes all six (`/locations/{ids}` and `/cube` cost the same, measured
    2026-11-12).
    """
    stations = [DE_BILT, SCHIPHOL, EELDE, ROTTERDAM, EINDHOVEN, DEELEN]
    _serve(edr_server, _hourly(30, stations))

    df = reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 2, 0), stations)

    assert set(df.get_column("station_id")) == set(stations)
    (path,) = edr_server.data_requests()
    assert len(_stations(path)) == 6
    assert _datetime(path) == ("2020-01-01T01:00:00Z", "2020-01-02T00:00:00Z")


def test_the_cheaper_of_the_blocks_and_the_exact_range_is_taken_for_a_list_of_stations() -> None:
    """The blocks where they cost the same (a cache hit is worth that), the exact range where it costs fewer."""
    first, last = _at(2020, 1, 2), _at(2020, 6, 30)
    # daily: a year of one station is 4,758 points, so three stations are one request of the block, or of the range
    plan = edr.plan_requests(3, first, last, Resolution.DAILY, NOW, 13)
    assert [(chunk.first.year, chunk.last.year, size >= 3) for chunk, size in plan] == [(2020, 2020, True)]
    assert plan[0][0].first == _at(2020, 1, 1)
    assert plan[0][0].last == _at(2020, 12, 31)
    # hourly: a day of six stations is one request, where the year takes three
    plan = edr.plan_requests(6, _at(2020, 1, 1, 1), _at(2020, 1, 2), Resolution.HOURLY, NOW, 12)
    assert [(chunk.first, chunk.last, size) for chunk, size in plan] == [(_at(2020, 1, 1, 1), _at(2020, 1, 2), 6)]


@pytest.mark.parametrize(
    ("resolution", "start", "end", "stations"),
    [
        pytest.param(Resolution.MINUTE_10, _at(2020, 1, 1), _at(2020, 3, 1), 7, id="10-minute, two months, 7 stations"),
        pytest.param(
            Resolution.MINUTE_10, _at(2020, 1, 1), _at(2020, 1, 1, 6), 77, id="10-minute, 6 hours, every station"
        ),
        pytest.param(Resolution.HOURLY, _at(2018, 6, 1), _at(2020, 6, 1), 5, id="hourly, two years, 5 stations"),
        pytest.param(Resolution.HOURLY, _at(2020, 6, 1), _at(2020, 6, 2), 77, id="hourly, a day, every station"),
        pytest.param(Resolution.DAILY, _at(1960, 1, 1), _at(2020, 1, 1), 70, id="daily, 60 years, 70 stations"),
        pytest.param(Resolution.MONTHLY, _at(1901, 1, 1), _at(2025, 12, 1), 70, id="monthly, 125 years, 70 stations"),
        pytest.param(Resolution.ANNUAL, _at(1901, 1, 1), _at(2025, 1, 1), 70, id="annual, 125 years, 70 stations"),
        pytest.param(Resolution.ANNUAL, _at(2024, 1, 1), _at(2025, 1, 1), 1, id="annual, one station"),
    ],
)
def test_a_request_holds_at_most_300000_points_and_the_requests_tile_the_range(
    resolution: Resolution, start: dt.datetime, end: dt.datetime, stations: int
) -> None:
    """Times * parameters * stations stay at or under 300,000, and the chunks of a plan cover the range, none twice."""
    bounds = edr.stamp_bounds(start, end, resolution, NOW)
    assert bounds is not None
    first, last = bounds
    parameters = len(PARAMETERS[resolution])

    plan = edr.plan_requests(stations, first, last, resolution, NOW, parameters)

    ordered = sorted(plan, key=lambda item: item[0].first)
    assert ordered[0][0].first <= first
    assert ordered[-1][0].last >= last
    for (before, _), (after, _) in itertools.pairwise(ordered):
        assert after.first == advance(before.last, resolution)
    for chunk, size in plan:
        times = edr.count_stamps(chunk.first, chunk.last, resolution)
        assert times * parameters * min(size, stations) <= edr.MAX_POINTS
        assert size >= 1
    # never more requests than the blocks alone
    blocks = [
        (chunk, edr.stations_per_request(chunk, resolution, parameters))
        for chunk in edr._aligned(  # noqa: SLF001
            first, last, resolution, NOW
        )
    ]
    assert edr._requests(plan, stations) <= edr._requests(blocks, stations)  # noqa: SLF001


@pytest.mark.parametrize("resolution", list(PARAMETERS))
def test_every_station_for_a_few_stamps_is_one_request_at_any_resolution(resolution: Resolution) -> None:
    """The measured shape of a query of the whole network at one time: one request for its 77 stations."""
    first = _at(2020, 1, 1, 1) if resolution == Resolution.HOURLY else _at(2020, 1, 1)
    last = advance(first, resolution, 2)

    plan = edr.plan_requests(77, first, last, resolution, NOW, len(PARAMETERS[resolution]))

    assert edr._requests(plan, 77) == 1  # noqa: SLF001


def test_a_range_that_the_memory_budget_cannot_hold_for_two_stations_is_read_station_by_station(
    monkeypatch: pytest.MonkeyPatch, edr_server: EdrStub, reader: Reader
) -> None:
    """The readings of the stations that follow are held until the walk comes to them: bounded by `MEMORY_POINTS`."""
    stations = [DE_BILT, SCHIPHOL]
    _serve(edr_server, _hourly(100, stations))
    monkeypatch.setattr(edr, "MEMORY_POINTS", 1_000)

    df = reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 4, 3), stations)

    assert set(df.get_column("station_id")) == set(stations)
    assert [_stations(path) for path in edr_server.data_requests()] == [["0-20000-0-06240"], ["0-20000-0-06260"]]


def test_a_walk_that_stops_where_the_data_says_asks_for_one_station_at_a_time(
    edr_server: EdrStub, reader: Reader
) -> None:
    """An interpolation or a summary stops at the first stations that have data: it reads the one in hand only."""
    stations = [DE_BILT, SCHIPHOL]
    _serve(edr_server, _hourly(100, stations))
    values = reader.values([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 4, 3), stations)
    values._fetch_ahead_allowed = False  # noqa: SLF001

    df = values.all().df

    assert set(df.get_column("station_id")) == set(stations)
    assert [_stations(path) for path in edr_server.data_requests()] == [["0-20000-0-06240"], ["0-20000-0-06260"]]


# --- what the API answers other than data --------------------------------------------------------------------------


def test_a_request_that_the_api_finds_too_big_is_made_in_smaller_parts(
    caplog: pytest.LogCaptureFixture, edr_server: EdrStub, reader: Reader
) -> None:
    """A 413 cuts the stations in two, then a lone station's stamps, until the API answers; nothing is lost."""
    stations = [DE_BILT, SCHIPHOL, EELDE]
    world = _hourly(60, stations)
    _serve(edr_server, world)
    edr_server.max_points = 1000
    start, end = _at(2020, 1, 1), _at(2020, 1, 3, 11)

    with caplog.at_level(logging.WARNING):
        df = reader.read([("hourly", "data")], start, end, stations)

    data = [request for request in edr_server.requests if "/locations/" in request["path"]]
    statuses = [request["status"] for request in data]
    assert statuses[0] == 413
    assert statuses[-1] == 200
    assert _warnings(caplog) == []
    assert df.get_column("timestamp").n_unique() == 60
    assert set(df.get_column("station_id")) == set(stations)
    # three stations of 60 hours is 2,160 points: cut to the 1,000 that the stub takes
    assert len(data) <= 10


def test_a_request_that_stays_too_big_is_an_error(edr_server: EdrStub, reader: Reader) -> None:
    """One station and one stamp is the least a request can be: a 413 of that is the error, not an endless split."""
    _serve(edr_server, _hourly(60))
    edr_server.max_points = 5

    with pytest.raises(DownloadError, match="one station and one stamp"):
        reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 3, 11))

    assert len(edr_server.data_requests()) <= 2 * 60 + 1


def test_a_404_is_an_empty_chunk_and_no_error(
    caplog: pytest.LogCaptureFixture, edr_server: EdrStub, reader: Reader
) -> None:
    """The API has no data for a station in the range (a 404): no row, no warning, and the next chunk is asked."""
    _serve(edr_server, _hourly(100, [DE_BILT]))
    edr_server.known.add(SCHIPHOL)

    with caplog.at_level(logging.WARNING):
        both = reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 4, 12), [DE_BILT, SCHIPHOL])
        only = reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 4, 12), [SCHIPHOL])

    assert set(both.get_column("station_id")) == {DE_BILT}
    assert only.is_empty()
    assert [r["status"] for r in edr_server.requests if "/locations/" in r["path"]] == [200, 404]
    assert _warnings(caplog) == []


def test_a_quota_that_is_used_up_is_an_error_that_says_so(edr_server: EdrStub, reader: Reader) -> None:
    """A 429 ends the query with an error: a range read in part is not an answer, and there is no other route."""
    world = World.generated(Resolution.DAILY, [DE_BILT], _at(2019, 12, 2), 700)
    _serve(edr_server, world)
    # the list of the stations and the first chunk are answered, the second is the 429
    edr_server.statuses.extend([None, None, None, 429])

    with pytest.raises(DownloadError, match="429") as raised:
        reader.read([("daily", "data")], _at(2019, 12, 1), _at(2020, 12, 31))

    assert "quota" in str(raised.value)
    assert KEY not in str(raised.value)


def test_an_answer_that_is_no_coverage_json_is_an_error_and_is_not_kept(edr_server: EdrStub, reader: Reader) -> None:
    """A 200 that is a page of the gateway: an error, and the page is not served again from the cache."""
    _serve(edr_server, World.generated(Resolution.DAILY, [DE_BILT], _at(2019, 12, 2), 51))
    edr_server.raw = b"<html>maintenance</html>"
    start, end = _at(2019, 12, 1), _at(2020, 1, 20)

    with pytest.raises(DownloadError, match="no CoverageJSON"):
        reader.read([("daily", "data")], start, end)
    edr_server.raw = None
    df = reader.read([("daily", "data")], start, end)

    assert df.get_column("timestamp").n_unique() == 51


def test_a_station_the_api_does_not_know_is_isolated_and_left_out_with_one_warning(
    caplog: pytest.LogCaptureFixture, edr_server: EdrStub, reader: Reader
) -> None:
    """A 400 for a list that holds an unknown station cuts the list in two until it is alone, and it is left out.

    One unknown station of four over three years of daily values, which the four stations take in one request of the
    range (three blocks of a year would be three): the four (400), the first two (200) and the last two (400), whose
    first is alone (400) and is left out, the other (200). Five requests, and no more for the station that is gone.
    """
    stations = [DE_BILT, SCHIPHOL, EELDE, ROTTERDAM]
    world = World.generated(Resolution.DAILY, stations, _at(2018, 1, 2), 1200)
    _serve(edr_server, world)
    edr_server.known.discard(EELDE)

    with caplog.at_level(logging.WARNING):
        df = reader.read([("daily", "data")], _at(2018, 1, 1), _at(2020, 12, 31), stations)

    statuses = [request["status"] for request in edr_server.requests if "/locations/" in request["path"]]
    assert set(df.get_column("station_id")) == {DE_BILT, SCHIPHOL, ROTTERDAM}
    assert statuses == [400, 200, 400, 400, 200]
    assert len(_warnings(caplog)) == 1
    assert EELDE in _warnings(caplog)[0]
    assert "status 400" in _warnings(caplog)[0]


def test_a_refused_station_is_not_asked_for_in_the_chunks_that_follow(edr_server: EdrStub, reader: Reader) -> None:
    """Once a station is isolated and left out, the later chunks of the query name the others only."""
    stations = [(DE_BILT, "0-20000-0-06260"), (EELDE, "0-20000-0-06280"), (ROTTERDAM, "0-20000-0-06344")]
    _serve(edr_server, World.generated(Resolution.DAILY, [DE_BILT, ROTTERDAM], _at(2018, 1, 2), 1200))
    edr_server.known.discard(EELDE)
    plan = [(chunk, 3) for chunk in edr._aligned(_at(2018, 1, 1), _at(2020, 12, 31), Resolution.DAILY, NOW)]  # noqa: SLF001
    assert len(plan) == 3

    edr_reader = edr.EdrReader(reader.settings(), api._chunk_expiry)  # noqa: SLF001
    reads = edr_reader.read(stations, Resolution.DAILY, PARAMETERS[Resolution.DAILY], plan)

    assert [bool(read.frames) for read in reads.values()] == [True, False, True]
    asked = [_stations(path) for path in edr_server.data_requests()]
    # the first chunk: the three (400), the first (200) and the other two (400), the first of them alone (400)
    # and the other (200)
    assert asked[:5] == [
        ["0-20000-0-06260", "0-20000-0-06280", "0-20000-0-06344"],
        ["0-20000-0-06260"],
        ["0-20000-0-06280", "0-20000-0-06344"],
        ["0-20000-0-06280"],
        ["0-20000-0-06344"],
    ]
    # the other two chunks name the two that are left, once each
    assert asked[5:] == [["0-20000-0-06260", "0-20000-0-06344"]] * 2


def test_two_stations_the_api_refuses_are_two_warnings_and_each_reason_is_said_once(
    caplog: pytest.LogCaptureFixture, edr_server: EdrStub, reader: Reader
) -> None:
    """Each distinct reason is warned about once for the query, so a second refusal is not hidden behind the first."""
    stations = [DE_BILT, EELDE, ROTTERDAM]
    _serve(edr_server, World.generated(Resolution.DAILY, stations, _at(2019, 1, 2), 800))
    edr_server.known -= {EELDE, ROTTERDAM}

    with caplog.at_level(logging.WARNING):
        df = reader.read([("daily", "data")], _at(2019, 1, 1), _at(2021, 2, 1), stations)

    assert set(df.get_column("station_id")) == {DE_BILT}
    warnings = _warnings(caplog)
    assert len(warnings) == 2
    assert EELDE in warnings[0] + warnings[1]
    assert ROTTERDAM in warnings[0] + warnings[1]


# --- what is not asked ---------------------------------------------------------------------------------------------


def test_a_period_that_has_not_ended_is_not_asked_for(edr_server: EdrStub, reader: Reader) -> None:
    """The hour and the day that are running are no data: a request ends at the last stamp at or before now."""
    hours = _hourly(100, first=_at(2026, 11, 8, 12))
    days = World.generated(Resolution.DAILY, [DE_BILT], _at(2026, 9, 21), 50)
    _serve(edr_server, hours, days)

    reader.read([("hourly", "data")], _at(2026, 11, 8, 12), _at(2026, 11, 20))
    reader.read([("daily", "data")], _at(2026, 9, 20), _at(2026, 11, 30))

    ends = [_datetime(path)[1] for path in edr_server.data_requests()]
    assert ends == ["2026-11-12T12:00:00Z", "2026-11-12T00:00:00Z"]
    assert all(dt.datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) <= NOW for end in ends)


def test_a_range_wholly_in_the_future_asks_for_nothing(edr_server: EdrStub, reader: Reader) -> None:
    """No hour of December 2026 has ended: no request, and the empty frame."""
    _serve(edr_server, _hourly(10))

    df = reader.read([("hourly", "data")], _at(2026, 12, 1), _at(2026, 12, 2))

    assert df.is_empty()
    assert edr_server.data_requests() == []


def test_the_range_starts_where_the_data_does(edr_server: EdrStub, reader: Reader) -> None:
    """The daily data begins in 1901: a range from 1895 asks for no chunk before it."""
    _serve(edr_server, World.generated(Resolution.DAILY, [DE_BILT], _at(1901, 1, 2), 800))

    df = reader.read([("daily", "data")], _at(1895, 1, 1), _at(1902, 12, 31))

    assert df.get_column("timestamp").min() == _at(1901, 1, 1)
    assert [_datetime(path) for path in edr_server.data_requests()] == [
        ("1901-01-02T00:00:00Z", "1902-01-01T00:00:00Z"),
        ("1902-01-02T00:00:00Z", "1903-01-01T00:00:00Z"),
    ]


def test_a_station_without_a_wigos_identifier_is_not_asked_for(
    monkeypatch: pytest.MonkeyPatch, edr_server: EdrStub, reader: Reader
) -> None:
    """The identifier goes into a URL: a station of a list that has none has no values."""
    _serve(edr_server, _hourly(10))
    monkeypatch.setattr(api, "read_stations", lambda *_args: locations_frame(DE_BILT).drop("wigos_id"))

    df = reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 2))

    assert df.is_empty()
    assert edr_server.data_requests() == []


# --- the cache, and the key ----------------------------------------------------------------------------------------


def _later(monkeypatch: pytest.MonkeyPatch, **delay: float) -> None:
    """Let the clock of the cache, which reads `time.time`, run on by `delay`."""
    later = time.time() + dt.timedelta(**delay).total_seconds()
    monkeypatch.setattr(time, "time", lambda: later)


def test_an_answer_is_kept_by_its_chunk_and_an_overlapping_query_is_served_from_it(
    edr_server: EdrStub, reader: Reader
) -> None:
    """The cache key is the request, whole blocks of the calendar: a query that overlaps an earlier one asks nothing."""
    _serve(edr_server, _hourly(24 * 100))

    first = reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 2, 10))
    again = reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 2, 10))
    overlapping = reader.read([("hourly", "data")], _at(2020, 1, 20), _at(2020, 3, 1))

    assert len(edr_server.data_requests()) == 1
    assert_frame_equal(first, again)
    assert overlapping.get_column("timestamp").min() == _at(2020, 1, 20)


def test_the_cache_does_not_serve_a_list_of_stations_that_names_others_from_a_chunk_of_one(
    edr_server: EdrStub, reader: Reader
) -> None:
    """The cache key holds the stations of the request: `[A, B]` and then `[A]` are two requests."""
    _serve(edr_server, _hourly(24 * 40, [DE_BILT, SCHIPHOL]))

    reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 2, 10), [DE_BILT, SCHIPHOL])
    reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 2, 10), [DE_BILT])
    reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 2, 10), [DE_BILT, SCHIPHOL])

    assert [len(_stations(path)) for path in edr_server.data_requests()] == [2, 1]


def test_a_settled_chunk_is_kept_for_12_hours_and_a_young_one_for_5_minutes(
    monkeypatch: pytest.MonkeyPatch, edr_server: EdrStub, reader: Reader
) -> None:
    """A chunk ending under 6 hours ago is asked again after 5 minutes, any other after 12 hours."""
    old_data = _hourly(24 * 40)
    recent = _hourly(24 * 30, first=_at(2026, 10, 14))
    for station, series in recent.cells.items():
        for name, cells in series.items():
            old_data.cells[station][name].update(cells)
    _serve(edr_server, old_data)
    parameters = [("hourly", "data")]

    def read() -> None:
        reader.read(parameters, _at(2020, 1, 1, 1), _at(2020, 2, 10))  # ended in 2020: settled
        reader.read(parameters, _at(2026, 10, 14), _at(2026, 11, 13))  # ends 30 minutes ago: young

    read()
    assert len(edr_server.data_requests()) == 2
    _later(monkeypatch, minutes=4)
    read()
    assert len(edr_server.data_requests()) == 2
    _later(monkeypatch, minutes=6)
    read()
    assert len(edr_server.data_requests()) == 3  # the young one only
    _later(monkeypatch, hours=11)
    read()
    assert len(edr_server.data_requests()) == 4  # the young one again, the settled one still held
    _later(monkeypatch, hours=12, minutes=1)
    read()
    assert len(edr_server.data_requests()) == 6


def test_the_expiry_of_a_chunk_is_by_the_end_of_the_interval_it_reaches() -> None:
    """The rule is the one of the files': the end of the interval is 6 hours before now, or less."""
    assert api._chunk_expiry(NOW - dt.timedelta(hours=5, minutes=59)) == CacheExpiry.FIVE_MINUTES  # noqa: SLF001
    assert api._chunk_expiry(NOW - dt.timedelta(hours=6)) == CacheExpiry.TWELVE_HOURS  # noqa: SLF001
    assert api._chunk_expiry(None) == CacheExpiry.FIVE_MINUTES  # noqa: SLF001


def test_the_key_goes_in_a_header_and_is_in_no_url_no_log_no_repr_and_no_file_of_the_cache(
    caplog: pytest.LogCaptureFixture, edr_server: EdrStub, reader: Reader, tmp_path: Path
) -> None:
    """The key of the EDR API is sent as `Authorization` and nowhere else; the answer is asked for compressed."""
    _serve(edr_server, _hourly(24 * 40))
    settings = reader.settings()

    with caplog.at_level(logging.DEBUG):
        values = reader.values([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 2, 10))
        values.all()
        shown = " ".join(
            [repr(settings), str(settings), repr(values), repr(values.sr.request), settings.model_dump_json()]
        )

    assert edr_server.requests
    for request in edr_server.requests:
        assert request["headers"]["authorization"] == KEY
        assert "gzip" in request["headers"]["accept-encoding"]
        assert request["headers"]["user-agent"].startswith("wetterdienst/")
        # in no URL, and so in no name that a copy is kept under
        assert KEY not in request["path"]
    assert not [record for record in caplog.records if KEY in record.getMessage()]
    assert KEY not in shown
    cached = [path for path in reader.cache.rglob("*") if path.is_file()]
    assert cached
    for path in cached:
        assert KEY not in str(path)
        assert KEY.encode() not in path.read_bytes(), path
    assert not any(KEY in str(path) for path in tmp_path.rglob("*"))


def test_two_keys_do_not_share_a_cached_answer(edr_server: EdrStub, reader: Reader) -> None:
    """An answer fetched with one key is not served to another: the cache of an authenticated request is the key's."""
    _serve(edr_server, _hourly(24 * 40))

    reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 2, 10))
    reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 2, 10), key="another-key-for-test")

    assert len(edr_server.data_requests()) == 2
    assert [
        request["headers"]["authorization"] for request in edr_server.requests if "/locations/" in request["path"]
    ] == [
        KEY,
        "another-key-for-test",
    ]


# --- the blocks of the end-stamped resolutions, the quota, and a 400 that is no station ------------------------------


def test_a_calendar_year_of_hourly_values_and_a_month_of_10_minutes_are_one_request() -> None:
    """The stamps mark the end of their interval: the blocks are (start, next start], so a year is one request."""
    hourly = edr.stamp_bounds(_at(2020, 1, 1, 1), _at(2021, 1, 1), Resolution.HOURLY, NOW)
    assert hourly is not None
    plan = edr.plan_requests(1, *hourly, Resolution.HOURLY, NOW, 12)
    assert [(chunk.first, chunk.last) for chunk, _ in plan] == [(_at(2020, 1, 1, 1), _at(2021, 1, 1))]
    minutes = edr.stamp_bounds(_at(2020, 2, 1, 0, 10), _at(2020, 3, 1), Resolution.MINUTE_10, NOW)
    assert minutes is not None
    plan = edr.plan_requests(1, *minutes, Resolution.MINUTE_10, NOW, 16)
    assert [(chunk.first, chunk.last) for chunk, _ in plan] == [(_at(2020, 2, 1, 0, 10), _at(2020, 3, 1))]
    # a range over the turn of the year is two blocks, the stamp of midnight in the year that ends (whole blocks)
    over = edr.stamp_bounds(_at(2019, 12, 31, 23), _at(2020, 1, 1, 2), Resolution.HOURLY, NOW)
    assert over is not None
    plan = edr.plan_requests(1, *over, Resolution.HOURLY, NOW, 12)
    assert [(chunk.first.year, chunk.first.hour, chunk.last) for chunk, _ in plan] == [
        (2019, 1, _at(2020, 1, 1, 0)),
        (2020, 1, _at(2021, 1, 1, 0)),
    ]
    # the days, the months and the years are stamped with their start, and their blocks are as before
    daily = edr.stamp_bounds(_at(2020, 1, 1), _at(2020, 12, 31), Resolution.DAILY, NOW)
    assert daily is not None
    plan = edr.plan_requests(1, *daily, Resolution.DAILY, NOW, 13)
    assert [(chunk.first, chunk.last) for chunk, _ in plan] == [(_at(2020, 1, 1), _at(2020, 12, 31))]


def test_a_query_that_takes_more_requests_than_the_quota_is_refused_before_anything_is_asked(
    edr_server: EdrStub, reader: Reader
) -> None:
    """16 stations of 10 years of 10-minute values: 120 requests each, more than the 1,000 an hour of the key."""
    stations = list(catalogue.LOCATIONS)
    start, end = _at(2016, 1, 1), _at(2025, 12, 31)
    first, last = edr.stamp_bounds(start, end, Resolution.MINUTE_10, NOW)
    expected = edr.estimate_requests(len(stations), first, last, Resolution.MINUTE_10, NOW, 16)
    assert expected > edr.MAX_REQUESTS

    with pytest.raises(RequestError) as raised:
        reader.read([("10_minutes", "data")], start, end, stations)

    message = str(raised.value)
    assert f"{expected:,} requests" in message
    assert "1,000" in message
    assert "narrower range or fewer stations" in message
    assert edr_server.data_requests() == []


def test_a_query_within_the_quota_is_not_refused_and_a_walk_that_stops_where_the_data_says_is_left_alone(
    edr_server: EdrStub, reader: Reader
) -> None:
    """The same query for 5 stations is 600 requests and is read; a walk that stops where the data says is not."""
    stations = list(catalogue.LOCATIONS)[:5]
    values = reader.values([("10_minutes", "data")], _at(2016, 1, 1), _at(2025, 12, 31), stations)
    values._check_quota()  # noqa: SLF001
    big = reader.values([("10_minutes", "data")], _at(2016, 1, 1), _at(2025, 12, 31), list(catalogue.LOCATIONS))
    big._fetch_ahead_allowed = False  # noqa: SLF001
    big._check_quota()  # noqa: SLF001
    assert edr_server.data_requests() == []


def test_the_requests_of_a_walk_are_counted_as_it_makes_them(edr_server: EdrStub, reader: Reader) -> None:
    """The count is the walk's, batch by batch, and the requests of a real walk are as many as were counted."""
    stations = [DE_BILT, SCHIPHOL]
    _serve(edr_server, _hourly(24 * 400, stations))
    first, last = edr.stamp_bounds(_at(2020, 1, 1, 1), _at(2021, 1, 20), Resolution.HOURLY, NOW)
    expected = edr.estimate_requests(2, first, last, Resolution.HOURLY, NOW, 12)

    reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2021, 1, 20), stations)

    assert len(edr_server.data_requests()) == expected


def test_a_400_for_every_request_ends_the_query_with_the_error_and_costs_the_first_station_alone(
    edr_server: EdrStub, reader: Reader
) -> None:
    """An unknown parameter or datetime is a 400 too: isolating took 29 requests for 15 stations and gave 0 rows.

    The first request that is refused down to one station, with nothing answered before, ends the query.
    """
    stations = [station for station in catalogue.LOCATIONS if station != "06233"]
    edr_server.always = 400

    with pytest.raises(DownloadError) as raised:
        reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 2), stations)

    message = str(raised.value)
    assert "400" in message
    assert "check the parameters and the dates" in message
    assert KEY not in message
    # 15, 7, 3 and the one alone, which waits; the next request (the other two of the three) is refused as well
    sizes = [len(_stations(path)) for path in edr_server.data_requests()]
    assert sizes == [15, 7, 3, 1, 2]
    assert len(sizes) <= math.ceil(math.log2(len(stations))) + 2


def test_the_third_station_the_api_refuses_alone_ends_the_query_with_the_error(
    caplog: pytest.LogCaptureFixture, edr_server: EdrStub, reader: Reader
) -> None:
    """Two stations that it does not know are left out with a warning each; a third is more than that."""
    stations = [SCHIPHOL, DE_BILT, EELDE, ROTTERDAM, EINDHOVEN]
    _serve(edr_server, _hourly(24, [SCHIPHOL, DE_BILT]))
    edr_server.known -= {EELDE, ROTTERDAM, EINDHOVEN}

    with caplog.at_level(logging.WARNING), pytest.raises(DownloadError, match="after 2 stations that it refused"):
        reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 1, 12), stations)

    assert len(_warnings(caplog)) == 2


def test_a_refused_station_is_told_as_a_file_let_go_to_the_core(edr_server: EdrStub, reader: Reader) -> None:
    """The station that is left out is `file-skipped` in the answer, and is no station without rows."""
    from wetterdienst.util.response_warnings import begin_response, recorded_warnings  # noqa: PLC0415

    stations = [SCHIPHOL, DE_BILT, EELDE]
    _serve(edr_server, _hourly(24, [SCHIPHOL, DE_BILT]))
    edr_server.known.discard(EELDE)
    begin_response()

    reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 1, 12), stations)

    codes = {warning["code"] for warning in recorded_warnings()}
    assert "file-skipped" in codes
    assert "station-without-rows" not in codes


@pytest.mark.parametrize("unknown", [0, 1, 2, 3], ids=["first", "second", "third", "last"])
def test_an_unknown_station_is_left_out_whatever_its_place_in_the_order(
    caplog: pytest.LogCaptureFixture, edr_server: EdrStub, reader: Reader, unknown: int
) -> None:
    """The same answer for one unknown station of four wherever it comes: the others read, one warning, no error.

    The walk isolates depth first, so an unknown station that comes first is refused alone before anything is answered:
    it waits, the others go on, and once one request is answered it is left out with the warning.
    """
    stations = [SCHIPHOL, DE_BILT, EELDE, ROTTERDAM]
    _serve(edr_server, _hourly(24, stations))
    edr_server.known.discard(stations[unknown])

    with caplog.at_level(logging.WARNING):
        df = reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 1, 12), stations)

    assert set(df.get_column("station_id")) == set(stations) - {stations[unknown]}
    (warning,) = _warnings(caplog)
    assert stations[unknown] in warning
    assert len(edr_server.data_requests()) <= 7


def test_two_unknown_stations_at_the_front_wait_and_are_left_out_when_the_others_answer(
    caplog: pytest.LogCaptureFixture, edr_server: EdrStub, reader: Reader
) -> None:
    """Two refused alone before anything is answered wait, and are left out, each with its warning, once one is."""
    stations = [SCHIPHOL, DE_BILT, EELDE, ROTTERDAM]
    _serve(edr_server, _hourly(24, stations))
    edr_server.known -= {SCHIPHOL, DE_BILT}

    with caplog.at_level(logging.WARNING):
        df = reader.read([("hourly", "data")], _at(2020, 1, 1, 1), _at(2020, 1, 1, 12), stations)

    assert set(df.get_column("station_id")) == {EELDE, ROTTERDAM}
    assert len(_warnings(caplog)) == 2
