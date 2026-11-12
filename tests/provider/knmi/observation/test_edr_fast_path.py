# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The opt-in EDR fast path of the values of KNMI (GH-3928).

With the key of the EDR API set, a range of one station or a few that would take more than `edr.MIN_FILES` files is read
from the EDR API, in chunks of at most 300,000 points. It must give the rows the files give, to the column and the
`raw:` token (`test_the_rows_are_the_files_rows`), and where the API cannot be used, give them from the files.

Served by a local server that stands for the API (`edr_stub`, with the data of real answers where the test says so, made
up where it counts requests) and a stand-in for the files that holds the same data.
"""

from __future__ import annotations

import datetime as dt
import itertools
import logging
import time
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

import pytest
from polars.testing import assert_frame_equal

from tests.provider.knmi.observation.catalogue import catalogue_frame
from tests.provider.knmi.observation.edr_stub import PARAMETERS, EdrStub, World, serve_files
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.knmi.observation import api, edr
from wetterdienst.provider.knmi.observation.api import KnmiObservationRequest
from wetterdienst.provider.knmi.observation.edr import stations_per_request
from wetterdienst.provider.knmi.observation.grid import advance
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    import polars as pl

# the made-up worlds hold numbers that are no readings (a humidity of -10 %), which the check of the ranges stands aside
# from; the real answers are read with it as well (`soft`: the values come back, flagged)
pytestmark = pytest.mark.synthetic_values

UTC = dt.UTC
NOW = dt.datetime(2026, 11, 12, 12, 30, tzinfo=UTC)
FILES_KEY = "knmi-files-key-for-test"
EDR_KEY = "knmi-edr-key-for-test-9f3a"
DE_BILT = "06260"
SCHIPHOL = "06240"
EELDE = "06280"


@pytest.fixture(autouse=True)
def _pinned_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the time that the age of a chunk and the end of the data are taken against."""
    monkeypatch.setattr(api, "_now", lambda: NOW)


def _at(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=UTC)


class Reader:
    """Read the values of stations, with or without the key of the EDR API, as a request does."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Keep the cache of the answers of the API in a directory of the test."""
        self.monkeypatch = monkeypatch
        self.cache = tmp_path / "cache"

    def settings(self, *, edr_key: str | None = EDR_KEY) -> Settings:
        """Give the settings, with the key of the EDR API unless it is left out."""
        auth = {"knmi": FILES_KEY, **({"knmi_edr": edr_key} if edr_key else {})}
        return Settings(auth=auth, cache_dir=self.cache)

    def values(
        self,
        parameters: list[tuple[str, ...]],
        start: dt.datetime,
        end: dt.datetime,
        stations: Sequence[str] = (DE_BILT,),
        *,
        edr_key: str | None = EDR_KEY,
        options: dict | None = None,
        everything: bool = False,
    ) -> api.KnmiObservationValues:
        """Build the reader of the values of the stations, in the catalogue as far as they are."""
        self.monkeypatch.setattr(api, "_station_catalogue", lambda *_args: catalogue_frame(*stations))
        request = KnmiObservationRequest(
            parameters=parameters,
            start=start,
            end=end,
            settings=self.settings(edr_key=edr_key),
            options={"plausibility": "soft", **(options or {})},
        )
        result = request.all() if everything else request.filter_by_station_id(list(stations))
        return result.values()

    def read(
        self,
        parameters: list[tuple[str, ...]],
        start: dt.datetime,
        end: dt.datetime,
        stations: Sequence[str] = (DE_BILT,),
        *,
        edr_key: str | None = EDR_KEY,
        options: dict | None = None,
    ) -> pl.DataFrame:
        """Read the values of the stations."""
        return self.values(parameters, start, end, stations, edr_key=edr_key, options=options).all().df


@pytest.fixture
def reader(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Reader:
    """Read values, keeping the cache in the directory of the test."""
    return Reader(monkeypatch, tmp_path)


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


# the real answers, over the stamps of the files they hold: a day, a month and a year are stamped with their first
# moment, so one earlier than the stamps of the API in the answers
REAL = {
    "10_minutes": (_at(2026, 11, 9, 6, 10), _at(2026, 11, 9, 9, 0)),
    "hourly": (_at(2026, 11, 5, 1), _at(2026, 11, 6, 0)),
    "daily": (_at(2019, 12, 29), _at(2020, 1, 4)),
    "monthly": (_at(2019, 12, 1), _at(2020, 3, 1)),
    "annual": (_at(2017, 1, 1), _at(2020, 1, 1)),
}


def _real_world(name: str) -> World:
    """Give the real answer saved for a resolution, with codes of the files laid in that no cell of it holds."""
    world = World.real(name)
    stations = list(world.cells)
    first = world.stamps(stations[0])
    last = first[-1]
    if name == "daily":
        world.set(DE_BILT, "RH", first[1], -1.0)  # a trace of precipitation
        world.set(DE_BILT, "SQ", first[2], -1.0)  # and of sunshine
        world.set(DE_BILT, "NG", first[3], 9.0)  # a sky that is invisible
        world.set(DE_BILT, "TG", last, None)  # a NaN
    if name == "hourly":
        world.set(DE_BILT, "DD", first[1], 0.0)  # a calm
        world.set(DE_BILT, "DD", first[2], 990.0)  # a variable wind
        world.set(DE_BILT, "N", first[3], 9.0)
        world.set(DE_BILT, "RH", first[4], -1.0)
        world.set(DE_BILT, "T", last, None)
    if name == "10_minutes":
        world.set(DE_BILT, "n", first[3], 9.0)
        world.set(DE_BILT, "rh", last, None)
    if name == "monthly":
        world.set(DE_BILT, "DDVEC", first[1], 0.0)
        world.set(DE_BILT, "RH", first[2], -1.0)  # no trace in a sum of days: left as it is
    return world


@pytest.mark.parametrize("drop_nulls", [True, False], ids=["nulls dropped", "nulls kept"])
@pytest.mark.parametrize("name", ["10_minutes", "hourly", "daily", "monthly", "annual"])
def test_the_rows_are_the_files_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    edr_server: EdrStub,
    reader: Reader,
    name: str,
    *,
    drop_nulls: bool,
) -> None:
    """The EDR route gives the rows of the file route: the columns, the dtypes, `quality_flags` and the `raw:` tokens.

    Both read the same data (real answers of the API, with the codes of the files laid in: a trace of rain and of
    sunshine, a calm and a variable wind, an invisible sky, a NaN), the files from NetCDF and the API from
    CoverageJSON. A parameter that De Bilt has no sensor for at 10 minutes (`vv`) is a NaN of the file, and left out
    of its coverage by the API: with the nulls kept it is a row of both.
    """
    monkeypatch.setattr(edr, "MIN_FILES", 0)
    world = _real_world(name)
    _serve(edr_server, world)
    stations = list(world.cells)
    start, end = REAL[name]
    parameters = [(name, "data")]
    options = {"drop_nulls": drop_nulls}

    from_api = reader.read(parameters, start, end, stations, options=options)
    assert edr_server.requests, "the EDR API was not asked"
    asked_of_files = serve_files(monkeypatch, tmp_path, [world])
    from_files = reader.read(parameters, start, end, stations, edr_key=None, options=options)

    assert asked_of_files, "the files were not read"
    assert from_api.height > 0
    assert_frame_equal(from_api, from_files)
    if not drop_nulls:
        # what the source wrote where it has no reading is kept as the `raw:` token, which the two routes share
        flags = from_api.get_column("quality_flags").drop_nulls().unique().to_list()
        assert any("raw:NaN" in flag for flag in flags)
        if name in {"hourly", "daily"}:
            assert any("raw:-1" in flag for flag in flags)
        if name == "hourly":
            assert any("raw:990" in flag for flag in flags)
            assert any("raw:0" in flag for flag in flags)


def test_the_stamp_of_a_day_is_the_day_and_not_the_end_of_it(
    monkeypatch: pytest.MonkeyPatch, edr_server: EdrStub, reader: Reader
) -> None:
    """De Bilt on 2020-01-01 (TG 0.8, TN -0.2, TX 1.8, RH 0.0) is stamped `2020-01-02T00:00Z` by the API (GH-3928).

    The row is dated 2020-01-01, as the file route dates it.
    """
    monkeypatch.setattr(edr, "MIN_FILES", 0)
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
    # one request: the day, which the API stamps with the end of it
    assert [parse_qs(urlsplit(path).query)["datetime"][0] for path in edr_server.asked()] == [
        "2020-01-02T00:00:00Z/2021-01-01T00:00:00Z"
    ]


def _hourly(count: int = 200, stations: Sequence[str] = (DE_BILT,), first: dt.datetime | None = None) -> World:
    return World.generated(Resolution.HOURLY, list(stations), first or _at(2020, 1, 1), count)


@pytest.mark.parametrize(("hours", "from_the_api"), [(48, False), (49, True)])
def test_the_number_of_files_decides_the_route(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    edr_server: EdrStub,
    reader: Reader,
    hours: int,
    *,
    from_the_api: bool,
) -> None:
    """A range that needs 48 files is read from them, one that needs 49 from the API: `edr.MIN_FILES` is the line."""
    world = _hourly()
    _serve(edr_server, world)
    files = serve_files(monkeypatch, tmp_path, [world])
    start = _at(2020, 1, 1, 0)

    df = reader.read([("hourly", "data")], start, start + dt.timedelta(hours=hours - 1))

    assert df.get_column("timestamp").n_unique() == hours
    if from_the_api:
        assert len(edr_server.requests) == 1
        assert files == []
    else:
        assert edr_server.requests == []
        assert len(files) == hours


def test_without_the_key_the_api_is_never_asked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, edr_server: EdrStub, reader: Reader
) -> None:
    """No `knmi_edr`, no EDR: the long range is read from the files as it always was."""
    world = _hourly()
    _serve(edr_server, world)
    files = serve_files(monkeypatch, tmp_path, [world])

    df = reader.read([("hourly", "data")], _at(2020, 1, 1), _at(2020, 1, 3, 11), edr_key=None)

    assert edr_server.requests == []
    assert len(files) == 60
    assert df.get_column("timestamp").n_unique() == 60


def test_the_stations_of_the_whole_network_stay_on_the_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, edr_server: EdrStub, reader: Reader
) -> None:
    """A query of every station is no list of stations: the files hold them all at once, and are read."""
    world = _hourly(stations=[DE_BILT, SCHIPHOL])
    _serve(edr_server, world)
    files = serve_files(monkeypatch, tmp_path, [world])

    values = reader.values(
        [("hourly", "data")], _at(2020, 1, 1), _at(2020, 1, 3, 11), [DE_BILT, SCHIPHOL], everything=True
    )
    df = values.all().df

    assert edr_server.requests == []
    assert len(set(files)) == 60
    assert set(df.get_column("station_id")) == {DE_BILT, SCHIPHOL}


def test_the_stations_of_the_catalogue_are_not_read_from_the_api(
    monkeypatch: pytest.MonkeyPatch, edr_server: EdrStub, reader: Reader
) -> None:
    """The list of the stations is the catalogue of the files, with or without the key."""
    monkeypatch.setattr(api, "_station_catalogue", lambda *_args: catalogue_frame(DE_BILT, SCHIPHOL))
    request = KnmiObservationRequest(parameters=[("hourly", "data")], settings=reader.settings())
    assert request.all().df.get_column("station_id").to_list() == [DE_BILT, SCHIPHOL]
    assert edr_server.requests == []


def test_several_stations_share_a_request(monkeypatch: pytest.MonkeyPatch, edr_server: EdrStub, reader: Reader) -> None:
    """A list of stations is one request for a chunk, `locations/wsi,wsi,wsi`, as far as 300,000 points allow."""
    monkeypatch.setattr(edr, "MIN_FILES", 0)
    world = World.generated(Resolution.DAILY, [DE_BILT, SCHIPHOL, EELDE], _at(2020, 1, 2), 100)
    _serve(edr_server, world)

    df = reader.read([("daily", "data")], _at(2020, 1, 1), _at(2020, 4, 9), [DE_BILT, SCHIPHOL, EELDE])

    assert set(df.get_column("station_id")) == {DE_BILT, SCHIPHOL, EELDE}
    assert [urlsplit(path).path.rsplit("/", 1)[-1] for path in edr_server.asked()] == [
        "0-20000-0-06260,0-20000-0-06240,0-20000-0-06280"
    ]


def test_a_walk_that_stops_where_the_data_says_asks_for_one_station_at_a_time(
    monkeypatch: pytest.MonkeyPatch, edr_server: EdrStub, reader: Reader
) -> None:
    """An interpolation or a summary stops at the first stations that have data: it reads the one in hand only."""
    monkeypatch.setattr(edr, "MIN_FILES", 0)
    world = World.generated(Resolution.DAILY, [DE_BILT, SCHIPHOL], _at(2020, 1, 2), 100)
    _serve(edr_server, world)
    values = reader.values([("daily", "data")], _at(2020, 1, 1), _at(2020, 4, 9), [DE_BILT, SCHIPHOL])
    values._fetch_ahead_allowed = False  # noqa: SLF001

    df = values.all().df

    assert set(df.get_column("station_id")) == {DE_BILT, SCHIPHOL}
    assert [urlsplit(path).path.rsplit("/", 1)[-1] for path in edr_server.asked()] == [
        "0-20000-0-06260",
        "0-20000-0-06240",
    ]


# --- chunking -----------------------------------------------------------------------------------------------------


def _points(path: str, resolution: Resolution) -> int:
    """Count the points a request holds, as the API does: times * parameters * stations."""
    parts = urlsplit(path)
    query = parse_qs(parts.query)
    start, end = (
        dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) for text in query["datetime"][0].split("/")
    )
    stations = len(parts.path.rsplit("/", 1)[-1].split(","))
    return edr.count_stamps(start, end, resolution) * len(query["parameter-name"][0].split(",")) * stations


@pytest.mark.parametrize(
    ("resolution", "start", "end", "stations"),
    [
        pytest.param(Resolution.MINUTE_10, _at(2020, 1, 1), _at(2020, 3, 1), 7, id="10-minute, two months, 7 stations"),
        pytest.param(Resolution.HOURLY, _at(2018, 6, 1), _at(2020, 6, 1), 5, id="hourly, two years, 5 stations"),
        pytest.param(Resolution.DAILY, _at(1960, 1, 1), _at(2020, 1, 1), 70, id="daily, 60 years, 70 stations"),
        pytest.param(Resolution.MONTHLY, _at(1901, 1, 1), _at(2025, 12, 1), 70, id="monthly, 125 years, 70 stations"),
        pytest.param(Resolution.ANNUAL, _at(1901, 1, 1), _at(2025, 1, 1), 70, id="annual, 125 years, 70 stations"),
    ],
)
def test_a_request_holds_at_most_300000_points_and_the_chunks_are_aligned_to_the_calendar(
    resolution: Resolution, start: dt.datetime, end: dt.datetime, stations: int
) -> None:
    """Times * parameters * stations stay at or under 300,000, with as many stations as fit; chunks tile the range."""
    bounds = edr.stamp_bounds(start, end, resolution, NOW)
    assert bounds is not None
    first, last = bounds
    chunks = edr.plan(first, last, resolution, NOW, _at(1901, 1, 1))
    parameters = len(PARAMETERS[resolution])
    assert chunks[0].first <= first
    assert chunks[-1].last >= last
    for before, after in itertools.pairwise(chunks):
        assert after.first == advance(before.last, resolution)
    for chunk in chunks:
        size = stations_per_request(chunk, resolution, parameters)
        times = edr.count_stamps(chunk.first, chunk.last, resolution)
        assert times * parameters * min(size, stations) <= edr.MAX_POINTS
        assert size == 1 or times * parameters * (size + 1) > edr.MAX_POINTS
        # the chunk is a block of the calendar: a month, a year or a decade (cut where the data starts or ends)
        if chunk is not chunks[0]:
            assert (chunk.first.day, chunk.first.hour, chunk.first.minute) == (1, 0, 0)
            assert chunk.first.month == 1 or resolution == Resolution.MINUTE_10
    assert stations_per_request(chunks[-1], resolution, parameters) >= 1


def test_the_stations_of_a_list_are_split_over_the_requests_that_the_limit_makes_necessary(
    edr_server: EdrStub, reader: Reader
) -> None:
    """Six stations of 10-minute values: a month of one is 71,424 points, so four fit a request and the rest another."""
    stations = [DE_BILT, SCHIPHOL, EELDE, "06344", "06370", "06275"]
    world = World.generated(Resolution.MINUTE_10, stations, _at(2026, 10, 30, 0, 10), 432)
    _serve(edr_server, world)

    df = reader.read([("10_minutes", "data")], _at(2026, 10, 30, 0, 10), _at(2026, 11, 2, 0, 0), stations)

    assert set(df.get_column("station_id")) == set(stations)
    sizes = [len(urlsplit(path).path.rsplit("/", 1)[-1].split(",")) for path in edr_server.asked()]
    # October: four stations and two; November (up to now, 11 days: 25,000 points of a station): all six
    assert sizes == [4, 2, 6]
    assert all(_points(path, Resolution.MINUTE_10) <= edr.MAX_POINTS for path in edr_server.asked())
    chunks = [parse_qs(urlsplit(path).query)["datetime"][0] for path in edr_server.asked()]
    assert chunks == [
        "2026-10-01T00:00:00Z/2026-10-31T23:50:00Z",
        "2026-10-01T00:00:00Z/2026-10-31T23:50:00Z",
        "2026-11-01T00:00:00Z/2026-11-12T12:30:00Z",
    ]


def test_a_request_that_the_api_finds_too_big_is_made_in_smaller_parts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    edr_server: EdrStub,
    reader: Reader,
) -> None:
    """A 413 cuts the stations in two, then a lone station's stamps, until the API answers; nothing is lost."""
    stations = [DE_BILT, SCHIPHOL, EELDE]
    world = _hourly(60, stations)
    _serve(edr_server, world)
    edr_server.max_points = 1000
    files = serve_files(monkeypatch, tmp_path, [world])
    start, end = _at(2020, 1, 1), _at(2020, 1, 3, 11)

    with caplog.at_level(logging.WARNING):
        df = reader.read([("hourly", "data")], start, end, stations)
    from_files = reader.read([("hourly", "data")], start, end, stations, edr_key=None)

    statuses = [request["status"] for request in edr_server.requests]
    assert statuses[0] == 413
    assert statuses.count(413) >= 1
    assert statuses[-1] == 200
    assert len(set(files)) == 60  # by the second read, which is the files'
    assert _warnings(caplog) == []
    assert_frame_equal(df, from_files)


def test_a_request_that_stays_too_big_is_read_from_the_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    edr_server: EdrStub,
    reader: Reader,
) -> None:
    """One station and one stamp is the least a request can be: a 413 of that is read from the files, with a warning."""
    world = _hourly(60)
    _serve(edr_server, world)
    edr_server.max_points = 5
    files = serve_files(monkeypatch, tmp_path, [world])
    start, end = _at(2020, 1, 1), _at(2020, 1, 3, 3)

    with caplog.at_level(logging.WARNING):
        df = reader.read([("hourly", "data")], start, end)
    from_files = reader.read([("hourly", "data")], start, end, edr_key=None)

    assert len(_warnings(caplog)) == 1
    assert "status 413" in _warnings(caplog)[0]
    assert "Open Data files" in _warnings(caplog)[0]
    assert len(set(files)) == 52  # every stamp, from the files
    assert_frame_equal(df, from_files)


# --- what the API answers other than data -------------------------------------------------------------------------


def test_a_404_is_an_empty_chunk_and_no_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    edr_server: EdrStub,
    reader: Reader,
) -> None:
    """The API has no data for a station in the range (a 404): no row, no file read for it, no warning."""
    world = _hourly(100, [DE_BILT])
    _serve(edr_server, world)
    edr_server.known.add(SCHIPHOL)
    files = serve_files(monkeypatch, tmp_path, [world])

    with caplog.at_level(logging.WARNING):
        both = reader.read([("hourly", "data")], _at(2020, 1, 1), _at(2020, 1, 4, 12), [DE_BILT, SCHIPHOL])
        only = reader.read([("hourly", "data")], _at(2020, 1, 1), _at(2020, 1, 4, 12), [SCHIPHOL])

    assert set(both.get_column("station_id")) == {DE_BILT}
    assert only.is_empty()
    assert [request["status"] for request in edr_server.requests] == [200, 404]
    assert files == []
    assert _warnings(caplog) == []


def test_a_quota_that_is_used_up_makes_the_rest_come_from_the_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    edr_server: EdrStub,
    reader: Reader,
) -> None:
    """A 429 on the second chunk: the first is the API's, the rest of the range is read from the files, one warning."""
    stations = [DE_BILT, SCHIPHOL]
    world = World.generated(Resolution.DAILY, stations, _at(2019, 12, 2), 51)
    _serve(edr_server, world)
    edr_server.statuses.extend([None, 429])
    files = serve_files(monkeypatch, tmp_path, [world])
    start, end = _at(2019, 12, 1), _at(2020, 1, 20)

    with caplog.at_level(logging.WARNING):
        df = reader.read([("daily", "data")], start, end, stations)
    from_files = reader.read([("daily", "data")], start, end, stations, edr_key=None)

    assert [request["status"] for request in edr_server.requests] == [200, 429]
    assert len(_warnings(caplog)) == 1
    assert "429" in _warnings(caplog)[0]
    assert EDR_KEY not in _warnings(caplog)[0]
    assert set(files) >= {f"daily-observations-validated-202001{day:02d}.nc" for day in range(1, 21)}
    assert_frame_equal(df, from_files)


@pytest.mark.parametrize("status", [401, 403])
def test_a_key_that_is_refused_makes_the_files_answer_and_names_the_setting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    edr_server: EdrStub,
    reader: Reader,
    status: int,
) -> None:
    """A 401 or a 403 (the key of the Open Data API is refused by the EDR API): files, one warning, never the key."""
    world = World.generated(Resolution.DAILY, [DE_BILT], _at(2019, 12, 2), 51)
    _serve(edr_server, world)
    edr_server.statuses.extend([status])
    files = serve_files(monkeypatch, tmp_path, [world])
    start, end = _at(2019, 12, 1), _at(2020, 1, 20)

    with caplog.at_level(logging.DEBUG):
        df = reader.read([("daily", "data")], start, end)
    from_files = reader.read([("daily", "data")], start, end, edr_key=None)

    warnings = _warnings(caplog)
    assert len(warnings) == 1
    assert "WD_AUTH__KNMI_EDR" in warnings[0]
    assert str(status) in warnings[0]
    assert [request["status"] for request in edr_server.requests] == [status]
    assert len(files) >= 51
    assert_frame_equal(df, from_files)
    assert not [
        record for record in caplog.records if EDR_KEY in record.getMessage() or FILES_KEY in record.getMessage()
    ]


def test_an_answer_that_is_no_coverage_json_makes_the_files_answer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    edr_server: EdrStub,
    reader: Reader,
) -> None:
    """A 200 that is a page of the gateway: warned about once, the files answer, and the page is not kept."""
    world = World.generated(Resolution.DAILY, [DE_BILT], _at(2019, 12, 2), 51)
    _serve(edr_server, world)
    edr_server.raw = b"<html>maintenance</html>"
    serve_files(monkeypatch, tmp_path, [world])
    start, end = _at(2019, 12, 1), _at(2020, 1, 20)

    with caplog.at_level(logging.WARNING):
        df = reader.read([("daily", "data")], start, end)

    assert len(_warnings(caplog)) == 1
    assert "no CoverageJSON" in _warnings(caplog)[0]
    assert df.get_column("timestamp").n_unique() == 51
    # not served again from the cache
    edr_server.raw = None
    again = reader.read([("daily", "data")], start, end)
    assert len(edr_server.requests) == 3
    assert again.get_column("timestamp").n_unique() == 51


def test_a_station_the_api_does_not_know_is_read_from_the_files_and_the_others_from_the_api(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    edr_server: EdrStub,
    reader: Reader,
) -> None:
    """A 400 names a station of a list that does not exist: the stations are asked one by one, and that one is left."""
    world = World.generated(Resolution.DAILY, [DE_BILT, SCHIPHOL], _at(2019, 12, 2), 50)
    _serve(edr_server, world)
    edr_server.known.discard(SCHIPHOL)
    files = serve_files(monkeypatch, tmp_path, [world])
    start, end = _at(2019, 12, 1), _at(2020, 1, 19)

    with caplog.at_level(logging.WARNING):
        df = reader.read([("daily", "data")], start, end, [DE_BILT, SCHIPHOL])
    edr_server.known.add(SCHIPHOL)
    from_files = reader.read([("daily", "data")], start, end, [DE_BILT, SCHIPHOL], edr_key=None)

    assert [request["status"] for request in edr_server.requests][:3] == [400, 200, 400]
    assert len(_warnings(caplog)) == 1
    assert "status 400" in _warnings(caplog)[0]
    assert len(files) >= 50
    assert_frame_equal(df, from_files)


# --- what is not asked --------------------------------------------------------------------------------------------


def test_a_period_that_has_not_ended_is_not_asked_for(edr_server: EdrStub, reader: Reader) -> None:
    """The hour and the day that are running are no data: a request ends at the last stamp at or before now."""
    hours = _hourly(100, first=_at(2026, 11, 8, 12))
    days = World.generated(Resolution.DAILY, [DE_BILT], _at(2026, 9, 21), 50)
    _serve(edr_server, hours, days)
    # the stub holds nothing later than now, as the API does
    reader.read([("hourly", "data")], _at(2026, 11, 8, 12), _at(2026, 11, 20))
    reader.read([("daily", "data")], _at(2026, 9, 20), _at(2026, 11, 30))

    ends = [parse_qs(urlsplit(path).query)["datetime"][0].split("/")[1] for path in edr_server.asked()]
    assert ends == ["2026-11-12T12:00:00Z", "2026-11-12T00:00:00Z"]
    assert all(dt.datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) <= NOW for end in ends)


def test_the_range_starts_where_the_data_does(edr_server: EdrStub, reader: Reader) -> None:
    """The daily files begin in 1901: a range from 1895 asks for no chunk before it, the files would 404 each day."""
    world = World.generated(Resolution.DAILY, [DE_BILT], _at(1901, 1, 2), 800)
    _serve(edr_server, world)

    df = reader.read([("daily", "data")], _at(1895, 1, 1), _at(1902, 12, 31))

    assert df.get_column("timestamp").min() == _at(1901, 1, 1)
    assert [parse_qs(urlsplit(path).query)["datetime"][0] for path in edr_server.asked()] == [
        "1901-01-02T00:00:00Z/1902-01-01T00:00:00Z",
        "1902-01-02T00:00:00Z/1903-01-01T00:00:00Z",
    ]


# --- the cache, and the key ---------------------------------------------------------------------------------------


def _later(monkeypatch: pytest.MonkeyPatch, **delay: float) -> None:
    """Let the clock of the cache, which reads `time.time`, run on by `delay`."""
    later = time.time() + dt.timedelta(**delay).total_seconds()
    monkeypatch.setattr(time, "time", lambda: later)


def test_an_answer_is_kept_by_its_chunk_and_an_overlapping_query_is_served_from_it(
    edr_server: EdrStub, reader: Reader
) -> None:
    """The cache key is the request, whole blocks of the calendar: a query that overlaps an earlier one asks nothing."""
    world = _hourly(24 * 100)
    _serve(edr_server, world)

    first = reader.read([("hourly", "data")], _at(2020, 1, 1), _at(2020, 2, 10))
    asked = len(edr_server.requests)
    again = reader.read([("hourly", "data")], _at(2020, 1, 1), _at(2020, 2, 10))
    overlapping = reader.read([("hourly", "data")], _at(2020, 1, 20), _at(2020, 3, 1))

    assert asked == 1
    assert len(edr_server.requests) == 1
    assert_frame_equal(first, again)
    assert overlapping.get_column("timestamp").min() == _at(2020, 1, 20)


def test_a_settled_chunk_is_kept_for_12_hours_and_a_young_one_for_5_minutes(
    monkeypatch: pytest.MonkeyPatch, edr_server: EdrStub, reader: Reader
) -> None:
    """As the files are: a chunk ending under 6 hours ago is asked again after 5 minutes, any other after 12 hours."""
    old_data = _hourly(24 * 40)
    recent = _hourly(24 * 30, first=_at(2026, 10, 14))
    for station, series in recent.cells.items():
        for name, cells in series.items():
            old_data.cells[station][name].update(cells)
    _serve(edr_server, old_data)
    parameters = [("hourly", "data")]

    def read() -> None:
        reader.read(parameters, _at(2020, 1, 1), _at(2020, 2, 10))  # ended in 2020: settled
        reader.read(parameters, _at(2026, 10, 14), _at(2026, 11, 13))  # ends 30 minutes ago: young

    read()
    assert len(edr_server.requests) == 2

    _later(monkeypatch, minutes=4)
    read()
    assert len(edr_server.requests) == 2

    _later(monkeypatch, minutes=6)
    read()
    assert len(edr_server.requests) == 3  # the young one only

    _later(monkeypatch, hours=11)
    read()
    assert len(edr_server.requests) == 4  # the young one again, the settled one still held

    _later(monkeypatch, hours=12, minutes=1)
    read()
    assert len(edr_server.requests) == 6


def test_the_expiry_of_a_chunk_is_that_of_a_file_of_the_same_end() -> None:
    """The rule is `_file_expiry`'s: the end of the interval that the chunk reaches, 6 hours before now."""
    assert api._file_expiry(NOW - dt.timedelta(hours=5, minutes=59)) == CacheExpiry.FIVE_MINUTES  # noqa: SLF001
    assert api._file_expiry(NOW - dt.timedelta(hours=6)) == CacheExpiry.TWELVE_HOURS  # noqa: SLF001


def test_the_key_goes_in_a_header_and_is_in_no_url_no_log_no_repr_and_no_file_of_the_cache(
    caplog: pytest.LogCaptureFixture, edr_server: EdrStub, reader: Reader, tmp_path: Path
) -> None:
    """The key of the EDR API is sent as `Authorization` and nowhere else; the answer is asked for compressed."""
    world = _hourly(24 * 40)
    _serve(edr_server, world)
    settings = reader.settings()

    with caplog.at_level(logging.DEBUG):
        values = reader.values([("hourly", "data")], _at(2020, 1, 1), _at(2020, 2, 10))
        values.all()
        shown = " ".join(
            [repr(settings), str(settings), repr(values), repr(values.sr.request), settings.model_dump_json()]
        )

    (request,) = edr_server.requests
    assert request["headers"]["authorization"] == EDR_KEY
    assert "gzip" in request["headers"]["accept-encoding"]
    assert request["headers"]["user-agent"].startswith("wetterdienst/")
    # in no URL, and so in no name that a copy is kept under
    assert EDR_KEY not in request["path"]
    assert not [
        record for record in caplog.records if EDR_KEY in record.getMessage() or FILES_KEY in record.getMessage()
    ]
    assert EDR_KEY not in shown
    assert FILES_KEY not in shown
    cached = [path for path in reader.cache.rglob("*") if path.is_file()]
    assert cached
    for path in cached:
        assert EDR_KEY not in str(path)
        assert EDR_KEY.encode() not in path.read_bytes(), path
    assert not any(EDR_KEY in str(path) for path in tmp_path.rglob("*"))


def test_two_keys_do_not_share_a_cached_answer(edr_server: EdrStub, reader: Reader) -> None:
    """An answer fetched with one key is not served to another: the cache of an authenticated request is the key's."""
    world = _hourly(24 * 40)
    _serve(edr_server, world)

    reader.read([("hourly", "data")], _at(2020, 1, 1), _at(2020, 2, 10))
    reader.read([("hourly", "data")], _at(2020, 1, 1), _at(2020, 2, 10), edr_key="another-key-for-test")

    assert len(edr_server.requests) == 2
    assert [request["headers"]["authorization"] for request in edr_server.requests] == [EDR_KEY, "another-key-for-test"]
