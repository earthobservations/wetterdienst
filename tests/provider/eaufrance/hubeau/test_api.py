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
from aiohttp import ServerDisconnectedError
from fsspec.exceptions import FSTimeoutError

from tests.provider.station_catalogue_stubs import _hubeau
from wetterdienst import Options, Settings
from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.eaufrance.hubeau import HubeauRequest, api
from wetterdienst.provider.eaufrance.hubeau.api import (
    _RESOLUTION_TO_STEP,
    _SNIFF_MIN_INTERVALS,
    _STEP_TO_RESOLUTION,
    _modal_steps,
)
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

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
        {"station_id": [row[0] for row in rows], "timestamp": [row[1] for row in rows]},
        schema={"station_id": pl.String, "timestamp": pl.Datetime(time_unit="us")},
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

    ``fast`` transmits through the first window; ``1011000101`` is an overseas gauge, whose station
    code begins with a digit rather than a basin letter; ``unmapped`` transmits at an interval no
    resolution covers; ``quiet`` and ``discharge_only`` are silent there and answer the second
    pass, the latter only for discharge; ``dead`` never transmits at all.
    """
    stations = [_station(name) for name in ("fast", "1011000101", "unmapped", "quiet", "discharge_only", "dead")]

    def _paged_rows(url: str, settings: Settings, *, ttl: object, timeout: int) -> list[dict]:  # noqa: ARG001
        if "referentiel" in url:
            return stations
        if "code_entite" not in url:
            return _observations([*_dates("fast", 5, 8), *_dates("1011000101", 15, 8), *_dates("unmapped", 30, 8)])
        if "grandeur_hydro=H" in url:
            return _observations(_dates("quiet", 60, 8))
        return _observations(_dates("discharge_only", 10, 8))

    monkeypatch.setattr(api, "_paged_rows", _paged_rows)


@pytest.mark.usefixtures("hubeau_network")
def test_hubeau_values_carry_the_qualification_code_as_a_whole_number(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that `code_qualification_obs` comes back as the code Hubeau writes in `quality_flags` (GH-2018, GH-2758).

    The hydrometry API documents it as "7 valeurs possibles : 0, 4, 8, 12, 16, 20, 30 (Neutre, Faible, Forte,
    Douteuse, Non qualifiée, Bonne, Estimée)" (hubeau.eaufrance.fr/api/v2/hydrometrie/api-docs, checked 2026-10-12).
    The live realtime observations of 2026-10-12 hold 16 (1761 of 2000 rows) and 12 (239), both with the status
    "Brute". The JSON number is a float in a frame, and is written without a decimal point.
    """
    stub = api._paged_rows  # noqa: SLF001

    def _paged_rows(url: str, settings: Settings, *, ttl: object, timeout: int) -> list[dict]:
        if "code_entite=1011000101" not in url:
            return stub(url, settings, ttl=ttl, timeout=timeout)
        return [
            {
                "code_station": "1011000101",
                "date_obs": "2026-08-21T04:00:00Z",
                "resultat_obs": 1.5,
                "code_qualification_obs": 16,
            },
            {
                "code_station": "1011000101",
                "date_obs": "2026-08-21T04:15:00Z",
                "resultat_obs": 1.6,
                "code_qualification_obs": 12,
            },
            {
                "code_station": "1011000101",
                "date_obs": "2026-08-21T04:30:00Z",
                "resultat_obs": 1.7,
                "code_qualification_obs": None,
            },
        ]

    monkeypatch.setattr(api, "_paged_rows", _paged_rows)
    end = dt.datetime(2026, 8, 21, 5, tzinfo=ZoneInfo("UTC"))
    request = HubeauRequest(
        parameters=[("15_minutes", "data", "stage")],
        start=end - dt.timedelta(days=1),
        end=end,
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    )
    df = request.filter_by_station_id("1011000101").values().all().df.sort("timestamp")
    assert df.schema["quality_flags"] == pl.String
    assert df.get_column("quality_flags").to_list() == ["16", "12", None]
    assert "quality" not in df.columns


@pytest.mark.usefixtures("hubeau_network")
def test_all_lists_each_station_under_the_interval_it_transmits_at() -> None:
    """Test that a station is listed under its own measured interval and under no other."""
    df = HubeauRequest(parameters=ALL_PARAMETERS, settings=Settings()).all().df

    assert dict(df.select("station_id", "resolution").iter_rows()) == {
        "fast": "5_minutes",
        "1011000101": "15_minutes",
        "quiet": "hourly",
        "discharge_only": "10_minutes",
    }


@pytest.mark.usefixtures("hubeau_network")
def test_all_leaves_out_a_station_whose_interval_no_resolution_covers() -> None:
    """Test that an unmapped interval is served under no resolution rather than a neighbouring one.

    Filing a half-hourly gauge under ``15_minutes`` or ``hourly`` would describe it wrongly for
    every reader downstream, and would have it judged against twice or half the readings it
    actually transmits wherever its coverage is measured.
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
def test_all_lists_the_stations_outside_metropolitan_france() -> None:
    """Test that the overseas departments are listed rather than filtered out by their code.

    Metropolitan station codes begin with the letter of their hydrographic basin, and the codes of
    Guadeloupe, Martinique, Guyane, La Réunion and Mayotte begin with a digit instead. The station
    list kept only the codes beginning with a letter, which excluded all 176 overseas gauges --
    86 of them transmitting -- for no reason the filter recorded.
    """
    df = HubeauRequest(parameters=ALL_PARAMETERS, settings=Settings()).all().df

    assert "1011000101" in df.get_column("station_id").to_list()


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
    """Test that a station listed at fifteen minutes actually returns a fifteen-minute series.

    Measured over the whole served window rather than a few hours of it: a gauge that misses a
    transmission leaves a double-length interval behind, and over a short window those gaps can
    outnumber the intervals they interrupt without the station being anything but fifteen-minutely.
    Gaps are multiples of the interval, so the grid shows through them.
    """
    end_date = dt.datetime.now(ZoneInfo("UTC"))
    request = HubeauRequest(
        parameters=[("15_minutes", "data", "stage")],
        start=end_date - dt.timedelta(days=30),
        end=end_date,
        settings=default_settings,
    )
    station_id = request.all().df.get_column("station_id")[0]

    df = request.filter_by_station_id(station_id).values().all().df

    steps = df.get_column("timestamp").diff().drop_nulls().dt.total_minutes().to_list()
    assert steps, f"{station_id} returned no values to measure"
    assert max(set(steps), key=steps.count) == 15
    on_grid = sum(step % 15 == 0 for step in steps) / len(steps)
    assert on_grid > 0.9, f"{station_id}: only {on_grid:.0%} of its intervals fall on a 15-minute grid"


def test_all_reports_the_gauge_datum_as_gauge_zero_not_as_elevation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the altitude of a gauge's zero is listed as ``gauge_zero`` and not as ``elevation``.

    ``altitude_ref_alti_station`` is the datum a stage is read from -- -1.809 m on the tidal Garonne
    at Bordeaux -- and not the ground the station stands on, which is what ``elevation`` means for
    every other provider. Pegelonline lists its gauge datum the same way.
    """
    bordeaux = {**_station("O972001001"), "altitude_ref_alti_station": -1.809}
    no_datum = {**_station("K447001001"), "altitude_ref_alti_station": None}

    def _paged_rows(url: str, settings: Settings, *, ttl: object, timeout: int) -> list[dict]:  # noqa: ARG001
        if "referentiel" in url:
            return [bordeaux, no_datum]
        return _observations([*_dates("O972001001", 5, 8), *_dates("K447001001", 5, 8)])

    monkeypatch.setattr(api, "_paged_rows", _paged_rows)

    df = HubeauRequest(parameters=ALL_PARAMETERS, settings=Settings()).all().df

    assert dict(df.select("station_id", "gauge_zero").iter_rows()) == {"O972001001": -1.809, "K447001001": None}
    assert df.get_column("elevation").null_count() == df.height == 2


def test_all_gives_the_referential_the_budget_of_the_other_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that reading the station referential may take as long as reading the observations.

    The referential is a single page, but a slow one: on 2026-10-01 it took 25 to 78 seconds to
    arrive, and four of six reads ran past the 30 seconds it was given, so the station list failed
    with ``FSTimeoutError`` more often than not.
    """
    timeouts: dict[str, int] = {}

    def _paged_rows(url: str, settings: Settings, *, ttl: object, timeout: int) -> list[dict]:  # noqa: ARG001
        timeouts[url] = timeout
        if "referentiel" in url:
            return [_station("O972001001")]
        return _observations(_dates("O972001001", 5, 8))

    monkeypatch.setattr(api, "_paged_rows", _paged_rows)

    HubeauRequest(parameters=ALL_PARAMETERS, settings=Settings()).all()

    referential = {url: timeout for url, timeout in timeouts.items() if "referentiel" in url}
    assert {url.split("?")[0].rsplit("/", 1)[-1] for url in referential} == {"stations", "sites"}
    assert set(referential.values()) == {api._SNIFF_TIMEOUT} == {api._VALUES_TIMEOUT}  # noqa: SLF001


def test_all_takes_the_elevation_from_the_station_site(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a station's elevation is the altitude of the site it names, where that is one.

    The station referential publishes only the altitude of the gauge's zero, which is not the
    ground's. The sites referential publishes ``altitude_site``, but not always a usable one: on
    2026-10-01, 48 stations in service were on a site at 0 m, inland ones among them whose gauge
    zero lies hundreds of metres up, 3 on a site at -999 m and 4 on one at 12000 m or more.
    """
    altitudes = {
        "O9720010": 4.0,  # La Garonne à Bordeaux
        "M6220010": -3.0,  # La Loire à Mauves-sur-Loire, on the tidal Loire
        "O7161510": 0.0,  # Le Lot à Espalion, whose gauge zero is at 331.5 m
        "I3103010": -999.0,
        "30530001": 130000.0,
        "K4470010": None,
    }
    # H2270003 names a site the sites referential does not list
    stations = [{**_station(f"{site}01"), "code_site": site} for site in [*altitudes, "H2270003"]]

    def _paged_rows(url: str, settings: Settings, *, ttl: object, timeout: int) -> list[dict]:  # noqa: ARG001
        if "referentiel/sites" in url:
            return [{"code_site": site, "altitude_site": altitude} for site, altitude in altitudes.items()]
        if "referentiel/stations" in url:
            return stations
        return _observations([date for station in stations for date in _dates(station["code_station"], 5, 8)])

    monkeypatch.setattr(api, "_paged_rows", _paged_rows)

    df = HubeauRequest(parameters=ALL_PARAMETERS, settings=Settings()).all().df

    assert dict(df.select("station_id", "elevation").iter_rows()) == {
        "O972001001": 4.0,
        "M622001001": -3.0,
        "O716151001": None,
        "I310301001": None,
        "3053000101": None,
        "K447001001": None,
        "H227000301": None,
    }


@pytest.mark.parametrize(
    "error",
    [
        FSTimeoutError(),
        ServerDisconnectedError(),
        FileNotFoundError("referentiel/sites"),
        json.JSONDecodeError("Expecting value", "<html>", 0),
        None,
    ],
    ids=["timeout", "disconnected", "not_found", "not_json", "no_connection"],
)
def test_all_lists_the_stations_when_the_sites_cannot_be_read(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    error: Exception | None,
) -> None:
    """Test that a sites referential that cannot be read leaves the elevation null, not the list empty.

    The sites referential supplies the elevation and nothing else. It answered 503 on 2026-10-01
    while the station referential answered, and failing the station list over it would bring back
    the very failure a slow referential caused. A connection that cannot be made is no error at
    all: ``_paged_rows`` reads it as an empty answer (``no_connection``), and is warned about too.
    """

    def _paged_rows(url: str, settings: Settings, *, ttl: object, timeout: int) -> list[dict]:  # noqa: ARG001
        if "referentiel/sites" in url:
            if error is None:
                return []
            raise error
        if "referentiel/stations" in url:
            return [{**_station("O972001001"), "code_site": "O9720010"}]
        return _observations(_dates("O972001001", 5, 8))

    monkeypatch.setattr(api, "_paged_rows", _paged_rows)

    df = HubeauRequest(parameters=ALL_PARAMETERS, settings=Settings()).all().df

    assert dict(df.select("station_id", "elevation").iter_rows()) == {"O972001001": None}
    assert "sites referential could not be read" in caplog.text


def test_all_names_the_vertical_datum_of_the_gauge_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that ``gauge_zero_datum`` names the system ``gauge_zero`` is given in, by its Sandre label.

    Hub'Eau gives ``altitude_ref_alti_station`` in the system ``code_systeme_alti_site`` names, from
    Sandre nomenclature 76, and stations differ: of those in service on 2026-10-01, 1765 were on
    IGN 1969 and 493 on NGF 1884, and many overseas gauges on a system of their own territory's. A
    code the labels do not cover is given as the code itself, and no code as null.
    """
    systems = {
        "O972001001": 3,  # La Garonne à Bordeaux
        "2115000201": 9,  # La rivière Capot au Lorrain, on Martinique
        "5143000101": 31,  # La Tapanahoni à Grand-Santi, in Guyane, on a local relative system
        "ngf_1884": 2,
        "unknown": 0,
        "unmapped": 99,
        "no_code": None,
    }
    stations = [{**_station(station_id), "code_systeme_alti_site": code} for station_id, code in systems.items()]
    urls: list[str] = []

    def _paged_rows(url: str, settings: Settings, *, ttl: object, timeout: int) -> list[dict]:  # noqa: ARG001
        urls.append(url)
        if "referentiel/sites" in url:
            return []
        if "referentiel/stations" in url:
            return stations
        return _observations([date for station_id in systems for date in _dates(station_id, 5, 8)])

    monkeypatch.setattr(api, "_paged_rows", _paged_rows)

    df = HubeauRequest(parameters=ALL_PARAMETERS, settings=Settings()).all().df

    assert dict(df.select("station_id", "gauge_zero_datum").iter_rows()) == {
        "O972001001": "IGN 1969",
        "2115000201": "IGN 1987 (Martinique)",
        "5143000101": "Système local - hauteur relative",
        "ngf_1884": "Nivellement Général de la France 1884",
        "unknown": "Système altimétrique inconnu",
        "unmapped": "99",
        "no_code": None,
    }
    assert df.schema["gauge_zero_datum"] == pl.String
    # the station referential has to be asked for the code, or its live answer carries none
    (stations_url,) = [url for url in urls if "referentiel/stations" in url]
    assert "code_systeme_alti_site" in stations_url.split("fields=")[1].split("&")[0].split(",")


def test_all_lists_the_stations_when_the_sites_download_times_out(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A timed-out sites referential is still caught as one, now that its error names the file (GH-2460).

    `raise_if_exception` raises an error naming the URL rather than the stored one, and the sites
    referential tells a failure to read apart from a defect by the error's type.
    """

    def _download_file(url: str, **_kwargs: object) -> File:
        if "referentiel/sites" in url:
            return File(url=url, content=FSTimeoutError(), status=408)
        if "referentiel/stations" in url:
            rows = [{**_station("O972001001"), "code_site": "O9720010"}]
        else:
            rows = _observations(_dates("O972001001", 5, 8))
        return File(url=url, content=BytesIO(json.dumps({"data": rows}).encode()), status=200)

    monkeypatch.setattr(api, "download_file", _download_file)

    df = HubeauRequest(parameters=ALL_PARAMETERS, settings=Settings()).all().df

    assert dict(df.select("station_id", "elevation").iter_rows()) == {"O972001001": None}
    assert "sites referential could not be read" in caplog.text
    assert "DownloadError('https://hubeau.eaufrance.fr/api/v2/hydrometrie/referentiel/sites'" in caplog.text


def test_all_leaves_a_station_in_service_without_an_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a station Hub'Eau gives no closing date has a null ``end_timestamp``.

    The station list read a null ``date_fermeture_station`` as the time of the call, so no station
    had a null end and the same station's end differed from one call to the next. A closing date
    the referential does give is kept.
    """
    stations = [_station("open"), {**_station("closing"), "date_fermeture_station": "2030-01-01T00:00:00Z"}]

    def _paged_rows(url: str, settings: Settings, *, ttl: object, timeout: int) -> list[dict]:  # noqa: ARG001
        if "referentiel/sites" in url:
            return []
        if "referentiel/stations" in url:
            return stations
        return _observations([*_dates("open", 5, 8), *_dates("closing", 5, 8)])

    monkeypatch.setattr(api, "_paged_rows", _paged_rows)

    df = HubeauRequest(parameters=ALL_PARAMETERS, settings=Settings()).all().df

    assert dict(df.select("station_id", "end_timestamp").iter_rows()) == {
        "open": None,
        "closing": dt.datetime(2030, 1, 1, tzinfo=ZoneInfo("UTC")),
    }
    assert df.schema["end_timestamp"] == pl.Datetime(time_zone="UTC")


@pytest.mark.usefixtures("hubeau_network")
def test_all_types_the_end_as_a_timestamp_when_no_station_has_one() -> None:
    """Test that ``end_timestamp`` stays a UTC datetime when every station's end is null.

    This is the shape Hub'Eau answers in: the list asks for stations in service only, and none of
    them carries a closing date.
    """
    df = HubeauRequest(parameters=ALL_PARAMETERS, settings=Settings()).all().df

    assert not df.is_empty()
    assert df.get_column("end_timestamp").null_count() == len(df)
    assert df.schema["end_timestamp"] == pl.Datetime(time_zone="UTC")


@pytest.mark.parametrize("resolution", sorted(set(_STEP_TO_RESOLUTION.values())))
def test_descriptions_say_what_the_swagger_says_of_the_stamp_and_the_height(resolution: str) -> None:
    """The descriptions say a value is dated by its instant and the height is relative to the gauge zero (GH-3264).

    The swagger of the hydrometry API (read 2026-10-22) gives ``date_obs`` as the "date, exprimée en TU, d'occurence de
    la donnée" and no interval, and the station referential gives ``altitude_ref_alti_station`` as the altitude of the
    zero of the gauge, which "permet de convertir des hauteurs relatives en hauteurs absolues". A description that
    left the reference out, as the page of the API does, would let stations of different gauge zeros be compared.
    """
    descriptions = {p.name_original: p.description for p in HubeauRequest.metadata[resolution]["data"]}
    assert set(descriptions) == {"H", "Q"}
    for notation, description in descriptions.items():
        assert "dated by the instant it occurred" in description, notation
    assert "relative to the zero of the station's gauge" in descriptions["H"]
    assert "`gauge_zero`" in descriptions["H"]
    assert "states no mean or interval" in descriptions["H"]
    assert "gauge" not in descriptions["Q"]


@pytest.mark.parametrize(
    "foreign",
    [
        "http://192.0.2.1/latest/meta-data/iam",
        "https://api.sandre.eaufrance.fr/x",
        "https://hubeau.eaufrance.fr.example.org/x",
    ],
)
def test_paged_rows_does_not_follow_a_cursor_to_another_host(monkeypatch: pytest.MonkeyPatch, foreign: str) -> None:
    """Test that the `next` of a page is followed at the host that was asked, and no other (GH-3339)."""
    asked: list[str] = []

    def _download_file(url: str, **_kwargs: object) -> File:
        asked.append(url)
        page = {"data": [{"n": 1}], "next": foreign}
        return File(url=url, content=BytesIO(json.dumps(page).encode()), status=200)

    monkeypatch.setattr(api, "download_file", _download_file)

    with pytest.raises(DownloadError, match="the link was not fetched"):
        api._paged_rows(  # noqa: SLF001
            "https://hubeau.eaufrance.fr/api/v2/first",
            Settings(),
            ttl=CacheExpiry.METAINDEX,
            timeout=30,
        )

    assert asked == ["https://hubeau.eaufrance.fr/api/v2/first"]


def _positions(*positions: tuple[float | None, float | None]) -> pl.DataFrame:
    """Build stations ``S0``, ``S1``, ... from ``(latitude, longitude)`` pairs, as the reader holds them."""
    return pl.DataFrame(
        {
            "station_id": [f"S{index}" for index in range(len(positions))],
            "latitude": [latitude for latitude, _ in positions],
            "longitude": [longitude for _, longitude in positions],
        },
        schema={"station_id": pl.String, "latitude": pl.Float64, "longitude": pl.Float64},
    )


@pytest.mark.parametrize(
    ("latitude", "longitude", "swapped"),
    [
        # swapped in the source, rows of 2026-10-26: Anor in Nord, Planioles in Lot, Le Tech in Pyrenees-Orientales
        (4.099322, 49.989435, True),
        (2.028415, 44.633866, True),
        (2.557169, 42.4174, True),
        # right in metropolitan France: Paris, the Garonne at La Reole, Corsica
        (48.84468962, 2.365510635, False),
        (44.579311754, -0.034612117, False),
        (42.2557, 9.3704, False),
        # right overseas: Guadeloupe, Martinique, Guyane, Reunion and the corners of Mayotte from the referential. The
        # swapped position of Mayotte (latitude 45, longitude -12.8) is in the box of the extent of the network
        (16.189402471, -61.658989597, False),
        (14.484987307, -60.852992932, False),
        (5.493567718, -51.884756948, False),
        (2.25838631, -54.544087482, False),
        (-21.381009615, 55.229631108, False),
        (-20.883458667, 55.721976963, False),
        (-12.800646373, 45.205680635, False),
        (-12.97068984, 45.129723012, False),
        (-12.715276989, 45.106868127, False),
        (-12.761317582, 45.098430035, False),
        # Bray-Dunes, the northernmost point of France (51.09 north, 2.54 east): inside, so not touched, and swapped
        # (latitude 2.54, longitude 51.09) is told; a station at 51.2 north is in no area either way, so it is left
        (51.09, 2.54, False),
        (2.54, 51.09, True),
        (51.2, 2.54, False),
        (2.54, 51.2, False),
        # in no area either way: the Blavet as the referential lists it, the middle of the Atlantic
        (35.108562837, 0.840483401, False),
        (30.0, -40.0, False),
        # on the edge of metropolitan France (south 41.0, west -5.5, north 51.1, east 10.0): inside, so not touched ...
        (41.0, -5.5, False),
        (51.1, 10.0, False),
        # ... a pair whose swapped one is on the edge is swapped, and one whose swapped one is just outside is not
        (-5.5, 41.0, True),
        (10.0, 51.1, True),
        (10.0, 51.11, False),
        (51.11, 10.0, False),
        (-5.5, 40.99, False),
        (-5.51, 41.0, False),
        (40.99, -5.5, False),
    ],
)
def test_a_position_is_swapped_by_where_it_lies(latitude: float, longitude: float, swapped: bool) -> None:  # noqa: FBT001
    """Test that a position in no area changes places if its swapped pair is in one (GH-3468)."""
    result = api._swap_misplaced_positions(_positions((latitude, longitude)))  # noqa: SLF001

    expected = (longitude, latitude) if swapped else (latitude, longitude)
    assert (result["latitude"][0], result["longitude"][0]) == expected


def test_swapping_leaves_the_other_stations_and_columns_as_they_are() -> None:
    """Test that only the pair of a swapped station changes, whatever its place in the frame, and a null does not."""
    df = _positions((48.0, 2.0), (4.099322, 49.989435), (None, 2.0), (2.0, None), (35.108562837, 0.840483401))

    result = api._swap_misplaced_positions(df)  # noqa: SLF001

    assert result["station_id"].to_list() == ["S0", "S1", "S2", "S3", "S4"]
    assert result["latitude"].to_list() == [48.0, 49.989435, None, 2.0, 35.108562837]
    assert result["longitude"].to_list() == [2.0, 4.099322, 2.0, None, 0.840483401]
    assert result.schema == df.schema


def test_swapping_reports_the_stations_it_swapped_as_the_source_wrote_them(caplog: pytest.LogCaptureFixture) -> None:
    """Test that the stations swapped are logged at debug with the pair the source wrote, and nothing when none was."""
    with caplog.at_level("DEBUG", logger=api.log.name):
        api._swap_misplaced_positions(_positions((4.1, 50.0), (2.0, 44.6), (48.0, 2.0)))  # noqa: SLF001
    assert [record.getMessage() for record in caplog.records if "swapped" in record.getMessage()] == [
        (
            "Hubeau: swapped latitude and longitude of 2 stations whose position is in no area of France, as the "
            "referential wrote them: S0 raw:4.1,50.0, S1 raw:2.0,44.6"
        )
    ]

    caplog.clear()
    with caplog.at_level("DEBUG", logger=api.log.name):
        api._swap_misplaced_positions(_positions((48.0, 2.0), (-12.8, 45.2)))  # noqa: SLF001
    assert not [record for record in caplog.records if "swapped" in record.getMessage()]


def test_a_position_that_no_swap_puts_right_is_null_with_a_warning() -> None:
    """Test that a station in no area either way, the Blavet, has no position, and the answer says so (GH-3468)."""
    begin_response()
    df = _positions((48.0, 2.0), (35.108562837, 0.840483401), (-12.8, 45.2), (None, 2.0), (None, None), (30.0, -40.0))

    result = api._null_unplaced_positions(df)  # noqa: SLF001

    assert result["station_id"].to_list() == [f"S{index}" for index in range(6)]
    assert result["latitude"].to_list() == [48.0, None, -12.8, None, None, None]
    assert result["longitude"].to_list() == [2.0, None, 45.2, 2.0, None, None]
    assert result.schema == df.schema
    assert recorded_warnings() == [
        {
            "code": "position-unplaced",
            "message": "Hub'Eau lists 2 stations at a position in none of metropolitan France, Guadeloupe, "
            "Martinique, Guyane, Reunion and Mayotte, also with latitude and longitude swapped: their latitude and "
            "longitude are null, so no search by place finds them. The referential wrote "
            "S1 raw:35.108562837,0.840483401, S5 raw:30.0,-40.0.",
        }
    ]


def test_the_warning_of_one_unplaced_station_is_in_the_singular() -> None:
    """Test that the warning names the one station the source wrote, and what it wrote, as a `raw:` token."""
    begin_response()

    api._null_unplaced_positions(_positions((48.0, 2.0), (35.108562837, 0.840483401)))  # noqa: SLF001

    [warning] = recorded_warnings()
    assert warning["code"] == api.POSITION_UNPLACED
    assert warning["message"].startswith("Hub'Eau lists a station at a position in none of")
    assert "their" not in warning["message"]
    assert "its latitude and longitude are null, so no search by place finds it." in warning["message"]
    assert warning["message"].endswith("The referential wrote S1 raw:35.108562837,0.840483401.")


def test_the_warning_of_many_unplaced_stations_names_the_first_and_counts_the_rest() -> None:
    """Test that a referential that goes wrong for many stations gets one warning of a readable length."""
    begin_response()

    api._null_unplaced_positions(_positions(*[(30.0, -40.0 + index) for index in range(13)]))  # noqa: SLF001

    [warning] = recorded_warnings()
    assert warning["message"].startswith("Hub'Eau lists 13 stations at a position")
    assert "S9 raw:30.0,-31.0 and 3 more." in warning["message"]
    assert "S10 raw" not in warning["message"]


def test_nothing_unplaced_is_no_warning_and_no_change() -> None:
    """Test that a frame whose positions are all in an area, or missing, is returned as it is, with no warning."""
    begin_response()
    df = _positions((48.0, 2.0), (-12.8, 45.2), (None, None))

    assert api._null_unplaced_positions(df).equals(df)  # noqa: SLF001
    assert recorded_warnings() == []


def test_an_unplaced_station_is_a_log_line_outside_a_request(caplog: pytest.LogCaptureFixture) -> None:
    """Test that the library, used as one, logs the warning at warning level, as every `warn_response` does."""
    with caplog.at_level("WARNING", logger=api.log.name):
        api._null_unplaced_positions(_positions((35.108562837, 0.840483401)))  # noqa: SLF001

    assert [record.levelname for record in caplog.records] == ["WARNING"]


def test_the_referential_stations_are_swapped_before_the_rest_are_nulled() -> None:
    """Test that Anor is swapped, Mayotte kept and the Blavet nulled, as one step reads the referential's rows."""
    begin_response()

    def row(station_id: str, longitude: float, latitude: float) -> dict[str, object]:
        return {"code_station": station_id, "longitude_station": longitude, "latitude_station": latitude}

    df = api._referential_stations(  # noqa: SLF001
        [
            row("H000000201", 49.989435, 4.099322),
            row("3013000101", 45.205680635, -12.800646373),
            row("J543211003", 0.840483401, 35.108562837),
            row("F700000102", 2.365510635, 48.84468962),
        ]
    )

    assert df.select("station_id", "latitude", "longitude").rows() == [
        ("H000000201", 49.989435, 4.099322),
        ("3013000101", -12.800646373, 45.205680635),
        ("J543211003", None, None),
        ("F700000102", 48.84468962, 2.365510635),
    ]
    assert [warning["code"] for warning in recorded_warnings()] == ["position-unplaced"]


def test_a_station_request_warns_of_the_station_without_a_position(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the stations of the referential of 2026-10-26 come with the one warning, for the Blavet alone."""
    begin_response()

    stations = _hubeau(monkeypatch)

    assert stations.filter(pl.col("latitude").is_null())["station_id"].to_list() == ["J543211003"]
    [warning] = recorded_warnings()
    assert warning["code"] == "position-unplaced"
    assert warning["message"].endswith("The referential wrote J543211003 raw:35.108562837,0.840483401.")


def test_the_extent_of_the_network_reaches_the_north_of_france() -> None:
    """Test that the declared extent holds Bray-Dunes (51.09 north), the northernmost point of France (GH-3481)."""
    west, south, east, north = HubeauRequest.metadata.extent.bbox

    assert south <= 51.09 <= north
    assert west <= 2.54 <= east
    assert north == api._AREAS["metropolitan France"][1]  # noqa: SLF001


@pytest.mark.parametrize("area", api._AREAS)  # noqa: SLF001
def test_the_swapped_position_of_an_area_is_in_none(area: str) -> None:
    """Test that a station in an area cannot be taken for a swapped one: its swapped position is in no area.

    The rule leaves a position in an area alone whatever its swapped one is; this holds the boxes to being apart enough
    that a swapped station is not in one of them either, which would make it a correct one. The box of the swapped
    positions of an area (its latitudes as longitudes and the other way round) shares no point with any area: the
    intervals of each axis are tested, closed as the rule is, so the whole box is held and not some points of it.
    """
    south, north, west, east = api._AREAS[area]  # noqa: SLF001
    swapped_south, swapped_north, swapped_west, swapped_east = west, east, south, north

    overlapping = [
        other
        for other, (other_south, other_north, other_west, other_east) in api._AREAS.items()  # noqa: SLF001
        if swapped_south <= other_north
        and other_south <= swapped_north
        and swapped_west <= other_east
        and other_west <= swapped_east
    ]

    assert not overlapping, f"the swapped positions of {area} overlap {overlapping}"
