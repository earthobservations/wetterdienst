# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for Eaufrance Hubeau, in particular the interval it measures for each station."""

from __future__ import annotations

import datetime as dt
import json
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.eaufrance.hubeau import HubeauRequest, api
from wetterdienst.provider.eaufrance.hubeau.api import (
    _RESOLUTION_TO_STEP,
    _SNIFF_MIN_INTERVALS,
    _STEP_TO_RESOLUTION,
    _modal_steps,
)
from wetterdienst.util.network import File

ALL_PARAMETERS = [(resolution, "data", "stage") for resolution in _STEP_TO_RESOLUTION.values()]


def _utc(hour: int, minute: int = 0) -> dt.datetime:
    """Build a naive UTC timestamp, the form the provider reads observations into."""
    return dt.datetime(2026, 8, 21, hour, minute, tzinfo=ZoneInfo("UTC")).replace(tzinfo=None)


def _dates(station_id: str, step: int, count: int, *, offset: int = 0) -> list[tuple[str, dt.datetime]]:
    """Build ``count`` observations of one station, ``step`` minutes apart."""
    start = _utc(4, offset)
    return [(station_id, start + dt.timedelta(minutes=step * index)) for index in range(count)]


def _frame(*rows: tuple[str, dt.datetime]) -> pl.DataFrame:
    return pl.DataFrame(
        {"station_id": [row[0] for row in rows], "date": [row[1] for row in rows]},
        schema={"station_id": pl.String, "date": pl.Datetime(time_unit="us")},
    )


def test_modal_steps_reads_the_interval_a_station_transmits_at() -> None:
    """Test that the interval is the spacing of the station's own observations."""
    result = _modal_steps(_frame(*_dates("A", 15, 9)))

    assert result.rows() == [("A", 15)]


def test_modal_steps_survives_a_gap_in_the_series() -> None:
    """Test that a missed transmission does not rename the station.

    A gauge that skips one transmission leaves a double-length interval behind, which is one
    interval among many rather than a different recording interval -- taking the mean, or the
    minimum, or the last of the deltas would each have called this station something it is not.
    """
    rows = [*_dates("A", 10, 5), ("A", _utc(5, 0)), *_dates("A", 10, 4, offset=20)]

    result = _modal_steps(_frame(*rows))

    assert result.rows() == [("A", 10)]


def test_modal_steps_needs_enough_intervals_to_name_a_station() -> None:
    """Test that a station with almost nothing to measure is left unnamed rather than guessed at.

    Two observations are one interval, and one interval is not a majority of anything -- the
    station is quiet, not ten-minutely, and is asked about again over a longer window instead.
    """
    rows = _dates("A", 10, _SNIFF_MIN_INTERVALS)  # one interval short of the minimum

    result = _modal_steps(_frame(*rows))

    assert result.is_empty()


def test_modal_steps_breaks_a_tie_toward_the_shorter_interval() -> None:
    """Test that a station with no majority interval is named the same way on every run."""
    rows = [*_dates("A", 5, 3), *_dates("A", 10, 3, offset=30)]

    result = _modal_steps(_frame(*rows))

    assert result.rows() == [("A", 5)]


def test_modal_steps_measures_each_station_on_its_own() -> None:
    """Test that stations do not borrow each other's intervals."""
    result = _modal_steps(_frame(*_dates("A", 5, 8), *_dates("B", 60, 8))).sort("station_id")

    assert result.rows() == [("A", 5), ("B", 60)]


def test_every_declared_resolution_has_an_interval() -> None:
    """Test that the metadata and the interval table say the same thing.

    The resolutions are built from the table, and the values class reads the table back to size its
    requests, so a resolution that is declared without an interval would fail at collection time
    rather than here.
    """
    declared = {resolution.name for resolution in HubeauRequest.metadata}

    assert declared == set(_RESOLUTION_TO_STEP)


def test_observations_url_asks_for_one_closed_window_and_two_fields() -> None:
    """Test that the sniff query is the cheapest and most repeatable form of itself.

    Closed at both ends and free of anything but the two fields an interval is measured from, so
    that the same window returns the same bytes and the cache can hold them.
    """
    start = _utc(4)
    end = _utc(6)

    url = HubeauRequest._observations_url(start=start, end=end, grandeur="H")  # noqa: SLF001

    assert "date_debut_obs=2026-08-21T04:00:00Z" in url
    assert "date_fin_obs=2026-08-21T06:00:00Z" in url
    assert "fields=code_station,date_obs" in url
    assert "code_entite" not in url


def test_observations_url_names_the_stations_it_asks_about() -> None:
    """Test that the second pass asks about quiet stations by name rather than about everyone."""
    url = HubeauRequest._observations_url(  # noqa: SLF001
        start=_utc(4),
        end=_utc(6),
        grandeur="Q",
        station_ids=["A", "B"],
    )

    assert "code_entite=A,B" in url
    assert "grandeur_hydro=Q" in url


def test_paged_rows_follows_the_cursor_to_the_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a query is read to its last page rather than to its first.

    Every Hubeau endpoint answers a page at a time and hands back a cursor. Reading only the first
    page is how the station list came to hold a thousand of the four thousand gauges, and on the
    values side it would cut a series off mid-window without any error to show for it.
    """
    pages = {
        "https://hubeau/first": {"data": [{"n": 1}], "next": "https://hubeau/second"},
        "https://hubeau/second": {"data": [{"n": 2}], "next": "https://hubeau/third"},
        "https://hubeau/third": {"data": [], "next": None},
    }

    def _download_file(url: str, **_kwargs: object) -> File:
        return File(url=url, content=BytesIO(json.dumps(pages[url]).encode()), status=200)

    monkeypatch.setattr(api, "download_file", _download_file)

    rows = api._paged_rows(  # noqa: SLF001
        "https://hubeau/first",
        Settings(),
        ttl=CacheExpiry.METAINDEX,
        timeout=30,
    )

    assert rows == [{"n": 1}, {"n": 2}]


def _station(station_id: str) -> dict:
    return {
        "code_station": station_id,
        "libelle_station": f"La Seine à {station_id}",
        "longitude_station": 2.35,
        "latitude_station": 48.85,
        "altitude_ref_alti_station": 30.0,
        "libelle_departement": "PARIS",
        "date_ouverture_station": "2012-11-11T00:00:00Z",
        "date_fermeture_station": None,
    }


def _observations(rows: list[tuple[str, dt.datetime]]) -> list[dict]:
    return [{"code_station": station_id, "date_obs": date.strftime("%Y-%m-%dT%H:%M:%SZ")} for station_id, date in rows]


@pytest.fixture
def hubeau_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer every Hubeau query from a small network of five telling stations.

    ``fast`` transmits through the first window; ``unmapped`` transmits at an interval no
    resolution covers; ``quiet`` and ``discharge_only`` are silent there and answer the second
    pass, the latter only for discharge; ``dead`` never transmits at all.
    """
    stations = [_station(name) for name in ("fast", "unmapped", "quiet", "discharge_only", "dead")]

    def _paged_rows(url: str, settings: Settings, *, ttl: object, timeout: int) -> list[dict]:  # noqa: ARG001
        if "referentiel" in url:
            return stations
        if "code_entite" not in url:
            return _observations([*_dates("fast", 5, 8), *_dates("unmapped", 30, 8)])
        if "grandeur_hydro=H" in url:
            return _observations(_dates("quiet", 60, 8))
        return _observations(_dates("discharge_only", 10, 8))

    monkeypatch.setattr(api, "_paged_rows", _paged_rows)


@pytest.mark.usefixtures("hubeau_network")
def test_all_lists_each_station_under_the_interval_it_transmits_at() -> None:
    """Test that a station is listed under its own measured interval and under no other."""
    df = HubeauRequest(parameters=ALL_PARAMETERS, settings=Settings()).all().df

    assert dict(df.select("station_id", "resolution").iter_rows()) == {
        "fast": "5_minutes",
        "quiet": "hourly",
        "discharge_only": "10_minutes",
    }


@pytest.mark.usefixtures("hubeau_network")
def test_all_leaves_out_a_station_whose_interval_no_resolution_covers() -> None:
    """Test that an unmapped interval is served under no resolution rather than a neighbouring one.

    Filing a half-hourly gauge under ``15_minutes`` or ``hourly`` would describe it wrongly for
    every reader downstream, and under ``ts_complete`` would reindex it onto a grid it never
    transmits on.
    """
    df = HubeauRequest(parameters=ALL_PARAMETERS, settings=Settings()).all().df

    assert "unmapped" not in df.get_column("station_id").to_list()


@pytest.mark.usefixtures("hubeau_network")
def test_all_leaves_out_a_station_with_nothing_to_measure() -> None:
    """Test that a station that has published nothing is listed under no resolution.

    The referential still marks a thousand-odd such gauges as in service. Naming an interval for
    one of them would be a guess, and the guess would be indistinguishable from a measurement.
    """
    df = HubeauRequest(parameters=ALL_PARAMETERS, settings=Settings()).all().df

    assert "dead" not in df.get_column("station_id").to_list()


@pytest.mark.usefixtures("hubeau_network")
def test_all_serves_only_the_resolutions_asked_for() -> None:
    """Test that a request for one interval does not list the stations of the others."""
    df = HubeauRequest(parameters=[("hourly", "data", "stage")], settings=Settings()).all().df

    assert df.get_column("station_id").to_list() == ["quiet"]


@pytest.mark.remote
def test_hubeau_station_belongs_to_exactly_one_resolution(default_settings: Settings) -> None:
    """Test that the live network places every station under a single interval.

    A station listed twice would mean two intervals were measured for it, and a request for either
    would then serve the same series under two different names.
    """
    listed: dict[str, str] = {}
    for resolution in _STEP_TO_RESOLUTION.values():
        df = HubeauRequest(parameters=[(resolution, "data", "stage")], settings=default_settings).all().df
        for station_id in df.get_column("station_id"):
            assert station_id not in listed, f"{station_id} is listed as both {listed[station_id]} and {resolution}"
            listed[station_id] = resolution
    assert len(listed) > 1000


@pytest.mark.remote
def test_hubeau_values_arrive_at_the_interval_the_station_is_listed_under(default_settings: Settings) -> None:
    """Test that a station listed at fifteen minutes actually returns a fifteen-minute series."""
    end_date = dt.datetime.now(ZoneInfo("UTC"))
    request = HubeauRequest(
        parameters=[("15_minutes", "data", "stage")],
        start_date=end_date - dt.timedelta(hours=6),
        end_date=end_date,
        settings=default_settings,
    )
    station_id = request.all().df.get_column("station_id")[0]

    df = request.filter_by_station_id(station_id).values.all().df

    steps = df.get_column("date").diff().drop_nulls().dt.total_minutes().to_list()
    assert steps, f"{station_id} returned no values to measure"
    assert max(set(steps), key=steps.count) == 15
