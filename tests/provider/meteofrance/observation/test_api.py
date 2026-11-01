# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for Météo-France observation API ("Données climatologiques de base")."""

from __future__ import annotations

import gzip
import json
import logging
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from typing import TYPE_CHECKING
from urllib.request import urlopen
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.provider.value_stubs import stations_result
from wetterdienst import Options, Settings
from wetterdienst.exceptions import DownloadError, InvalidParameterError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.meteofrance.observation import MeteoFranceObservationRequest, api
from wetterdienst.util.network import File, RedirectRefusedError, UpstreamMaintenanceError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.remote
def test_meteofrance_observation_api_interleaved_datasets_no_duplicate_stations() -> None:
    """Test that requesting datasets in interleaved order doesn't duplicate station rows.

    itertools.groupby() only groups consecutive items; since parameter order is preserved from
    user input, interleaving datasets (here: core, others, core) used to produce a separate group
    -- and a duplicated station row -- for the second "core" occurrence.
    """
    request = MeteoFranceObservationRequest(
        parameters=[
            ("daily", "core", "precipitation_amount"),
            ("daily", "others", "humidity_relative_mean"),
            ("daily", "core", "wind_speed_mean"),
        ],
    ).filter_by_station_id("31069001")
    df = request.df
    assert len(df) == 2
    assert sorted(df.get_column("dataset").to_list()) == ["core", "others"]


@pytest.mark.remote
def test_meteofrance_observation_api_daily_stations() -> None:
    """Test that the daily resolution's much larger climatological station network resolves.

    Station discovery for daily/monthly is built from Météo-France's canonical station metadata
    registry rather than scanning every French department's climatological archive.
    """
    request = MeteoFranceObservationRequest(
        parameters=[("daily", "core", "temperature_air_mean_2m")],
    ).filter_by_station_id("31069001")
    df = request.df
    assert not df.is_empty()
    assert df.get_column("name").to_list() == ["TOULOUSE-BLAGNAC"]
    # regression check: start_timestamp must be populated, since the app seeds its date-range
    # picker from it; end_timestamp is legitimately null here since the station is still open (the
    # app already falls back to "today" for a null end_timestamp)
    assert df.get_column("start_timestamp").is_not_null().all()


@pytest.mark.remote
@pytest.mark.parametrize(
    ("dataset", "parameter"),
    [
        ("core", "temperature_air_mean_2m"),
        ("core", "wind_gust_max"),
        ("core", "wind_direction_gust_max"),
        ("others", "radiation_global"),
        ("others", "humidity_relative_mean"),
    ],
)
def test_meteofrance_observation_api_daily(dataset: str, parameter: str) -> None:
    """Test daily climatological values ("Données climatologiques de base - quotidiennes").

    Also guards against the parameter-name case mismatch bug: the source columns are uppercase
    (e.g. "RR", "TN"), and the base class matches requested parameters against name_original
    using an exact, case-sensitive comparison.
    """
    request = MeteoFranceObservationRequest(
        parameters=[("daily", dataset, parameter)],
        start=datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=datetime(2023, 1, 31, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("31069001")
    df = next(request.values().query()).df
    assert df.get_column("value").is_not_null().sum() > 0


@pytest.mark.remote
@pytest.mark.parametrize(
    "parameter",
    [
        "precipitation_amount",
        "temperature_air_max_2m_mean",
        "wind_gust_max",
        "sunshine_duration",
    ],
)
def test_meteofrance_observation_api_monthly(parameter: str) -> None:
    """Test monthly climatological values ("Données climatologiques de base - mensuelles")."""
    request = MeteoFranceObservationRequest(
        parameters=[("monthly", "data", parameter)],
        start=datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=datetime(2023, 6, 1, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("31069001")
    df = next(request.values().query()).df
    assert df.get_column("value").is_not_null().sum() > 0


@pytest.mark.remote
@pytest.mark.parametrize(
    ("dataset", "parameter"),
    [
        ("core", "temperature_air_2m"),
        ("core", "precipitation_amount"),
        ("core", "wind_direction_mean_last_10min"),
        ("others", "cloud_cover_total"),
        ("others", "visibility"),
    ],
)
def test_meteofrance_observation_api_hourly(dataset: str, parameter: str) -> None:
    """Test hourly climatological values ("Données climatologiques de base - horaires").

    Also guards against the AAAAMMJJHH date format regression: polars' strptime requires a
    minute whenever an hour is present in the format string, but this date column has none.
    """
    request = MeteoFranceObservationRequest(
        parameters=[("hourly", dataset, parameter)],
        start=datetime(2025, 6, 1, tzinfo=ZoneInfo("UTC")),
        end=datetime(2025, 6, 7, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("31069001")
    df = next(request.values().query()).df
    assert df.get_column("value").is_not_null().sum() > 0


@pytest.mark.remote
def test_meteofrance_observation_api_6_minutes() -> None:
    """Test 6-minute climatological values ("Données climatologiques de base -  6 minutes").

    Only precipitation is published at this resolution.
    """
    request = MeteoFranceObservationRequest(
        parameters=[("6_minutes", "data", "precipitation_amount")],
        start=datetime(2025, 6, 1, tzinfo=ZoneInfo("UTC")),
        end=datetime(2025, 6, 2, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("31069001")
    df = next(request.values().query()).df
    assert not df.is_empty()
    # 6-minute intervals within a day: exercise that the date column parses to real, distinct
    # timestamps rather than e.g. all collapsing to midnight
    assert df.get_column("timestamp").n_unique() > 1


def _climate_gz(resolution: str, dataset: str, rows: list[dict[str, str]]) -> bytes:
    """Write rows into a gzipped file with the columns of the source's file, empty where a row has none."""
    schema = list(api._CLIMATE_SCHEMAS[resolution, dataset])  # noqa: SLF001
    lines = [";".join(schema)] + [";".join(row.get(column, "") for column in schema) for row in rows]
    return gzip.compress("\n".join(lines).encode("utf8"))


def _serve_climate(
    monkeypatch: pytest.MonkeyPatch, files: dict[str, bytes], last_modified: dict[str, str] | None = None
) -> list[str]:
    """Serve the period files of a dataset, by the title of their resource, and return the titles asked for.

    A file the test does not serve fails with a KeyError, and the titles asked for show whether the
    request read the files it needs and no others. `last_modified` is the date data.gouv.fr gives a resource in the
    listing, by its title, as it writes it; a resource not in it has none.
    """
    resources = [
        {
            "title": title,
            "url": f"https://static.data.gouv.fr/{title}.csv.gz",
            **({"last_modified": last_modified[title]} if title in (last_modified or {}) else {}),
        }
        for title in files
    ]
    asked: list[str] = []

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        url = url or args[0]
        assert "/api/1/datasets/" in url, url
        return File(url=url, content=BytesIO(json.dumps({"resources": resources}).encode("utf8")), status=200)

    def download_files(urls: list[str], **_: object) -> list[File]:
        found = []
        for url in urls:
            title = url.rsplit("/", 1)[1].removesuffix(".csv.gz")
            asked.append(title)
            found.append(File(url=url, content=BytesIO(files[title]), status=200))
        return found

    monkeypatch.setattr(api, "download_file", download_file)
    monkeypatch.setattr(api, "download_files", download_files)
    return asked


def _values(
    resolution: str,
    dataset: str,
    parameter: str,
    station_id: str,
    start: datetime,
    end: datetime,
    *,
    drop_nulls: bool = True,
) -> pl.DataFrame:
    request = MeteoFranceObservationRequest(
        parameters=[(resolution, dataset, parameter)],
        start=start,
        end=end,
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=drop_nulls),
    )
    return stations_result(request, resolution, dataset, station_id).values().all().df.sort("timestamp")


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def _hourly_files(department: str, previous: list[dict[str, str]], latest: list[dict[str, str]]) -> dict[str, bytes]:
    return {
        f"HOR_departement_{department}_periode_2020-2024": _climate_gz("hourly", "core", previous),
        f"HOR_departement_{department}_periode_2025-2026": _climate_gz("hourly", "core", latest),
    }


def test_meteofrance_observation_api_hourly_reunion_is_converted_from_fu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that Réunion's hourly stamps, which are FU (UTC+4), come back as UTC (GH-2677).

    The rows are the file's own for station 97418110 around the New Year. The temperatures are those of
    SYNOP 61980 (Gillot-Aéroport, UTC) at 2024-12-31 15, 18 and 21 h and 2025-01-01 00 h:
    300.05, 298.05, 297.85 and 297.45 K = 26.9, 24.9, 24.7 and 24.3 °C, which the file stamps four hours
    later. The last two sit in the file of 2025-2026 although their UTC time is in 2024, so both files are read.
    """
    files = _hourly_files(
        "974",
        previous=[
            {"NUM_POSTE": "97418110", "AAAAMMJJHH": "2024123119", "T": "26.9"},
            {"NUM_POSTE": "97418110", "AAAAMMJJHH": "2024123122", "T": "24.9"},
        ],
        latest=[
            {"NUM_POSTE": "97418110", "AAAAMMJJHH": "2025010101", "T": "24.7"},
            {"NUM_POSTE": "97418110", "AAAAMMJJHH": "2025010104", "T": "24.3"},
        ],
    )
    asked = _serve_climate(monkeypatch, files)
    df = _values("hourly", "core", "temperature_air_2m", "97418110", _utc(2024, 12, 31, 15), _utc(2025, 1, 1))
    assert df.get_column("timestamp").to_list() == [
        _utc(2024, 12, 31, 15),
        _utc(2024, 12, 31, 18),
        _utc(2024, 12, 31, 21),
        _utc(2025, 1, 1, 0),
    ]
    assert df.get_column("value").to_list() == [26.9, 24.9, 24.7, 24.3]
    assert sorted(asked) == sorted(files)


def test_meteofrance_observation_api_hourly_reunion_reads_the_file_of_the_fu_year(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a request in the last UTC hours of a year reads the file of the next year, which FU is in.

    2024-12-31 21:00 UTC is 2025-01-01 01:00 FU in Réunion, so the file of 2025-2026 holds it and the
    file of 2020-2024 does not (GH-2677).
    """
    files = _hourly_files(
        "974",
        previous=[{"NUM_POSTE": "97418110", "AAAAMMJJHH": "2024123122", "T": "24.9"}],
        latest=[{"NUM_POSTE": "97418110", "AAAAMMJJHH": "2025010101", "T": "24.7"}],
    )
    asked = _serve_climate(monkeypatch, files)
    stamp = _utc(2024, 12, 31, 21)
    df = _values("hourly", "core", "temperature_air_2m", "97418110", stamp, stamp)
    assert df.get_column("timestamp").to_list() == [stamp]
    assert df.get_column("value").to_list() == [24.7]
    assert asked == ["HOR_departement_974_periode_2025-2026"]


def test_meteofrance_observation_api_hourly_saint_pierre_is_converted_from_fu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that Saint-Pierre-et-Miquelon's hourly stamps, FU = UTC-4, come back as UTC (GH-2677).

    The rows are the file's own for station 97502001 at the New Year. SYNOP 71805 (UTC) reads
    277.55, 277.95 and 277.95 K = 4.4, 4.8 and 4.8 °C at 2025-01-01 00, 03 and 06 h, which the file
    stamps four hours earlier. The first two sit in the file of 2020-2024 although their UTC time is
    in 2025, so a request that lies in 2025 reads both files.
    """
    files = _hourly_files(
        "975",
        previous=[
            {"NUM_POSTE": "97502001", "AAAAMMJJHH": "2024123120", "T": "4.4"},
            {"NUM_POSTE": "97502001", "AAAAMMJJHH": "2024123123", "T": "4.8"},
        ],
        latest=[{"NUM_POSTE": "97502001", "AAAAMMJJHH": "2025010102", "T": "4.8"}],
    )
    asked = _serve_climate(monkeypatch, files)
    df = _values("hourly", "core", "temperature_air_2m", "97502001", _utc(2025, 1, 1), _utc(2025, 1, 1, 6))
    assert df.get_column("timestamp").to_list() == [_utc(2025, 1, 1, 0), _utc(2025, 1, 1, 3), _utc(2025, 1, 1, 6)]
    assert df.get_column("value").to_list() == [4.4, 4.8, 4.8]
    assert sorted(asked) == sorted(files)
    # and a request of the first hour alone needs the earlier file only
    asked.clear()
    df = _values("hourly", "core", "temperature_air_2m", "97502001", _utc(2025, 1, 1), _utc(2025, 1, 1))
    assert df.get_column("value").to_list() == [4.4]
    assert asked == ["HOR_departement_975_periode_2020-2024"]


def test_meteofrance_observation_api_6_minutes_saint_pierre_is_converted_from_fu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the 6-minute stamps of an overseas station are converted like the hourly ones (GH-2677).

    The 6-minute file is on the clock of the hourly file in every overseas department: for the stations
    compared, the hourly RR1 of an hour is the sum of the 6-minute RR stamped in the hour before it, in
    the file's own stamps.
    """
    rows = [
        {"NUM_POSTE": "97502001", "AAAAMMJJHHMN": "202501020400", "RR": "0.2"},
        {"NUM_POSTE": "97502001", "AAAAMMJJHHMN": "202501020406", "RR": "0.4"},
        {"NUM_POSTE": "97502001", "AAAAMMJJHHMN": "202501020412", "RR": "0.4"},
    ]
    _serve_climate(monkeypatch, {"MIN_departement_975_periode_2025-2026": _climate_gz("6_minutes", "data", rows)})
    df = _values("6_minutes", "data", "precipitation_amount", "97502001", _utc(2025, 1, 2, 8), _utc(2025, 1, 2, 8, 12))
    assert df.get_column("timestamp").to_list() == [
        _utc(2025, 1, 2, 8, 0),
        _utc(2025, 1, 2, 8, 6),
        _utc(2025, 1, 2, 8, 12),
    ]
    assert df.get_column("value").to_list() == [0.2, 0.4, 0.4]


def test_meteofrance_observation_api_daily_and_monthly_overseas_keep_their_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the date of a daily or monthly value of an overseas station is not shifted (GH-2677).

    It names the FU day or month like every daily stamp names its day, at 00:00; moving it by the
    offset would put Réunion's 1 January on 31 December and out of a request that starts on the 1st.
    """
    daily = [{"NUM_POSTE": "97418110", "AAAAMMJJ": "20250101", "RR": "14.7"}]
    daily_files = {"QUOT_departement_974_periode_2025-2026_RR-T-Vent": _climate_gz("daily", "core", daily)}
    _serve_climate(monkeypatch, daily_files)
    df = _values("daily", "core", "precipitation_amount", "97418110", _utc(2025, 1, 1), _utc(2025, 1, 3))
    assert df.get_column("timestamp").to_list() == [_utc(2025, 1, 1)]
    assert df.get_column("value").to_list() == [14.7]
    monthly = [{"NUM_POSTE": "97418110", "AAAAMM": "202501", "RR": "85.2"}]
    _serve_climate(monkeypatch, {"MENS_departement_974_periode_2025-2026": _climate_gz("monthly", "data", monthly)})
    df = _values("monthly", "data", "precipitation_amount", "97418110", _utc(2025, 1, 1), _utc(2025, 2, 1))
    assert df.get_column("timestamp").to_list() == [_utc(2025, 1, 1)]
    assert df.get_column("value").to_list() == [85.2]


def test_meteofrance_observation_api_hourly_invisible_sky_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that N=9, the sky invisible, has no cloud cover and not 9/8, where the octas 0 to 8 keep theirs (GH-2687).

    The field descriptions of the dataset define N as "9=ciel invisible par brouillard et/ou autre phénomène
    météorologique". The rows are those of station 31069001 at 2025-06-03 04:00 to 07:00 UTC (N=7, 9, 9, 8),
    and a clear hour before.
    """
    latest = [
        {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025060300", "N": "0"},
        {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025060304", "N": "7"},
        {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025060305", "N": "9"},
        {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025060306", "N": "9"},
        {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025060307", "N": "8"},
    ]
    files = {"HOR_departement_31_periode_2025-2026": _climate_gz("hourly", "others", latest)}
    _serve_climate(monkeypatch, files)
    df = _values("hourly", "others", "cloud_cover_total", "31069001", _utc(2025, 6, 3), _utc(2025, 6, 4))
    assert df.get_column("timestamp").to_list() == [_utc(2025, 6, 3, 0), _utc(2025, 6, 3, 4), _utc(2025, 6, 3, 7)]
    assert df.get_column("value").to_list() == [0.0, 0.875, 1.0]


def test_meteofrance_observation_api_hourly_ten_minute_wind_is_named_for_its_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that FF and DD come back as the 10-minute mean they are (GH-2707).

    The row is that of station 31069001 at 2025-01-01 02 h (FF = 2.2, DD = 10). The old names are not found in
    the hourly dataset.
    """
    hourly = [{"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025010102", "FF": "2.2", "DD": "10"}]
    _serve_climate(monkeypatch, {"HOR_departement_31_periode_2025-2026": _climate_gz("hourly", "core", hourly)})
    start, end = _utc(2025, 1, 1), _utc(2025, 1, 2)
    df = _values("hourly", "core", "wind_speed_mean_last_10min", "31069001", start, end)
    assert df.get_column("value").to_list() == [2.2]
    df = _values("hourly", "core", "wind_direction_mean_last_10min", "31069001", start, end)
    assert df.get_column("value").to_list() == [10.0]
    for old in ("wind_speed", "wind_direction"):
        with pytest.raises(InvalidParameterError):
            MeteoFranceObservationRequest(parameters=[("hourly", "core", old)])


def test_meteofrance_observation_api_hourly_fxy_is_the_highest_ten_minute_mean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that FXY comes back as the highest 10-minute mean wind of the hour, not as a gust (GH-2834).

    The field descriptions define FXY as "valeur maximale de FF dans l'heure" and FF as "force du vent moyenné sur
    10 mn". The rows are those of station 31069001 (Toulouse-Blagnac) at 2025-01-01 02 h and 2025-01-03 07 h (FF =
    2.2 and 0.9, FXY = 2.5 and 2.3), as in the calm-wind test below. The hourly `wind_gust_max` is not found.
    """
    hourly = [
        {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025010102", "FF": "2.2", "FXY": "2.5"},
        {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025010307", "FF": "0.9", "FXY": "2.3"},
    ]
    _serve_climate(monkeypatch, {"HOR_departement_31_periode_2025-2026": _climate_gz("hourly", "core", hourly)})
    df = _values("hourly", "core", "wind_speed_rolling_mean_max", "31069001", _utc(2025, 1, 1), _utc(2025, 2, 1))
    assert df.get_column("timestamp").to_list() == [_utc(2025, 1, 1, 2), _utc(2025, 1, 3, 7)]
    assert df.get_column("value").to_list() == [2.5, 2.3]
    with pytest.raises(InvalidParameterError):
        MeteoFranceObservationRequest(parameters=[("hourly", "core", "wind_gust_max")])


def test_meteofrance_observation_api_hourly_calm_wind_has_no_direction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a direction of 0, the calm wind, is null and 360, the north, stays (GH-2720).

    The rows are the file's own for station 31069001 (Toulouse-Blagnac) at 2025-01-01 02 h, 2025-01-01 09 h
    (FF = 0.0, DD = 0, with a gust from 320) and 2025-01-03 07 h (DD = 360), and for 31042012 (Luchon) at
    2025-01-31 05 h, where FF, DD, FXY and DXY all read zero. The field descriptions give the directions
    "en rose de 360" and no code for a calm wind. DXY, the direction of FXY, is in the file and is not read
    (GH-2836): the hourly `wind_direction_gust_max` is not found.
    """
    latest = [
        {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025010102", "FF": "2.2", "DD": "10", "FXY": "2.5", "DXY": "140"},
        {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025010109", "FF": "0.0", "DD": "0", "FXY": "1.4", "DXY": "320"},
        {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025010307", "FF": "0.9", "DD": "360", "FXY": "2.3", "DXY": "340"},
        {"NUM_POSTE": "31042012", "AAAAMMJJHH": "2025013105", "FF": "0.0", "DD": "0", "FXY": "0.0", "DXY": "0"},
    ]
    _serve_climate(monkeypatch, {"HOR_departement_31_periode_2025-2026": _climate_gz("hourly", "core", latest)})
    start, end = _utc(2025, 1, 1), _utc(2025, 2, 1)
    df = _values("hourly", "core", "wind_direction_mean_last_10min", "31069001", start, end)
    assert df.get_column("timestamp").to_list() == [_utc(2025, 1, 1, 2), _utc(2025, 1, 3, 7)]
    assert df.get_column("value").to_list() == [10.0, 360.0]
    assert _values("hourly", "core", "wind_direction_mean_last_10min", "31042012", start, end).is_empty()
    with pytest.raises(InvalidParameterError):
        MeteoFranceObservationRequest(parameters=[("hourly", "core", "wind_direction_gust_max")])


def test_meteofrance_observation_api_hourly_variable_wind_direction_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a direction of 999 is null, where the directions around it stay (GH-2720).

    The rows are the file's own for station 98404001 (Kerguelen) at 1965-04-17 20 h, 23 h and 18th 02 h FU (FF = 23.0
    to 26.0, DD = 240, 999, 240), which the +5 h of Kerguelen makes 15 h, 18 h and 21 h UTC.
    """
    rows = [
        {"NUM_POSTE": "98404001", "AAAAMMJJHH": "1965041720", "FF": "23.0", "DD": "240"},
        {"NUM_POSTE": "98404001", "AAAAMMJJHH": "1965041723", "FF": "23.0", "DD": "999"},
        {"NUM_POSTE": "98404001", "AAAAMMJJHH": "1965041802", "FF": "26.0", "DD": "240"},
    ]
    _serve_climate(monkeypatch, {"HOR_departement_984_periode_1960-1969": _climate_gz("hourly", "core", rows)})
    df = _values("hourly", "core", "wind_direction_mean_last_10min", "98404001", _utc(1965, 4, 17), _utc(1965, 4, 18))
    assert df.get_column("timestamp").to_list() == [_utc(1965, 4, 17, 15), _utc(1965, 4, 17, 21)]
    assert df.get_column("value").to_list() == [240.0, 240.0]


def test_meteofrance_observation_api_daily_calm_wind_has_no_direction_of_the_gust(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a daily DXI of 0 is null, with FXI = 0.0, where 360 and 180 stay (GH-2720).

    The rows are the file's own for station 31042012 (Luchon), 1996-02-19 to 23: 360, 360, 0, 360, 180 with
    gusts of 9.0, 12.0, 0.0, 8.0 and 3.0 m/s.
    """
    rows = [
        {"NUM_POSTE": "31042012", "AAAAMMJJ": "19960219", "FXI": "9.0", "DXI": "360"},
        {"NUM_POSTE": "31042012", "AAAAMMJJ": "19960220", "FXI": "12.0", "DXI": "360"},
        {"NUM_POSTE": "31042012", "AAAAMMJJ": "19960221", "FXI": "0.0", "DXI": "0"},
        {"NUM_POSTE": "31042012", "AAAAMMJJ": "19960222", "FXI": "8.0", "DXI": "360"},
        {"NUM_POSTE": "31042012", "AAAAMMJJ": "19960223", "FXI": "3.0", "DXI": "180"},
    ]
    files = {"QUOT_departement_31_periode_1950-2024_RR-T-Vent": _climate_gz("daily", "core", rows)}
    _serve_climate(monkeypatch, files)
    df = _values("daily", "core", "wind_direction_gust_max", "31042012", _utc(1996, 2, 19), _utc(1996, 2, 23))
    assert df.get_column("timestamp").to_list() == [
        _utc(1996, 2, 19),
        _utc(1996, 2, 20),
        _utc(1996, 2, 22),
        _utc(1996, 2, 23),
    ]
    assert df.get_column("value").to_list() == [360.0, 360.0, 360.0, 180.0]


def test_meteofrance_observation_api_daily_dxi_of_400_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a daily DXI of 400 is null with its text as `raw` token, where the days around it stay (GH-2728).

    The rows are the file's own for station 31299001 (MURET-LHERM), 2007-09-04 to 06: DXI = 300, 400, 340 with gusts
    of 11.0, 8.0 and 8.0 m/s, all with QDXI = 1.
    """
    rows = [
        {"NUM_POSTE": "31299001", "AAAAMMJJ": "20070904", "FXI": "11.0", "DXI": "300", "QDXI": "1"},
        {"NUM_POSTE": "31299001", "AAAAMMJJ": "20070905", "FXI": "8.0", "DXI": "400", "QDXI": "1"},
        {"NUM_POSTE": "31299001", "AAAAMMJJ": "20070906", "FXI": "8.0", "DXI": "340", "QDXI": "1"},
    ]
    files = {"QUOT_departement_31_periode_1950-2024_RR-T-Vent": _climate_gz("daily", "core", rows)}
    _serve_climate(monkeypatch, files)
    df = _values(
        "daily", "core", "wind_direction_gust_max", "31299001", _utc(2007, 9, 4), _utc(2007, 9, 6), drop_nulls=False
    )
    assert df.get_column("value").to_list() == [300.0, None, 340.0]
    assert df.get_column("quality_flags").to_list() == ["1", "1,raw:400", "1"]


def test_meteofrance_observation_api_hourly_metropole_is_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a metropolitan station, whose stamps are UTC as published, is not converted."""
    latest = [{"NUM_POSTE": "31011001", "AAAAMMJJHH": "2025010100", "T": "-1.8"}]
    files = {"HOR_departement_31_periode_2025-2026": _climate_gz("hourly", "core", latest)}
    _serve_climate(monkeypatch, files)
    df = _values("hourly", "core", "temperature_air_2m", "31011001", _utc(2025, 1, 1), _utc(2025, 1, 1))
    assert df.get_column("timestamp").to_list() == [_utc(2025, 1, 1)]
    assert df.get_column("value").to_list() == [-1.8]


def test_meteofrance_observation_api_hourly_crozet_changes_its_fu_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that Crozet's stamps are converted with +5 h in 2003 before October and with +4 h from November on.

    The rows are the file's own for station 98404004. SYNOP 61997 (UTC) reads 274.95, 276.75 and 274.45 K
    = 1.8, 3.6 and 1.3 °C at 2003-09-13 12 h, 2003-09-15 09 h and 2003-11-07 15 h, which the file stamps
    at 17 h, 14 h and 19 h.
    """
    rows = [
        {"NUM_POSTE": "98404004", "AAAAMMJJHH": "2003091317", "T": "1.8"},
        {"NUM_POSTE": "98404004", "AAAAMMJJHH": "2003091514", "T": "3.6"},
        {"NUM_POSTE": "98404004", "AAAAMMJJHH": "2003110719", "T": "1.3"},
    ]
    files = {"HOR_departement_984_periode_2000-2009": _climate_gz("hourly", "core", rows)}
    _serve_climate(monkeypatch, files)
    df = _values("hourly", "core", "temperature_air_2m", "98404004", _utc(2003, 9, 13), _utc(2003, 11, 8))
    assert df.get_column("timestamp").to_list() == [_utc(2003, 9, 13, 12), _utc(2003, 9, 15, 9), _utc(2003, 11, 7, 15)]
    assert df.get_column("value").to_list() == [1.8, 3.6, 1.3]


def test_meteofrance_observation_api_hourly_without_known_fu_offset_is_not_converted(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a station whose offset is unknown is returned as published, and says so.

    Port Martin (98404006, Adélie Land, open 1950 to 1952) predates the SYNOP archive, so there is no
    reading to compare its stamps with.
    """
    rows = [{"NUM_POSTE": "98404006", "AAAAMMJJHH": "1950021409", "T": "-0.2"}]
    _serve_climate(monkeypatch, {"HOR_departement_984_periode_1950-1959": _climate_gz("hourly", "core", rows)})
    with caplog.at_level(logging.WARNING, logger=api.__name__):
        df = _values("hourly", "core", "temperature_air_2m", "98404006", _utc(1950, 2, 14), _utc(1950, 2, 15))
    assert df.get_column("timestamp").to_list() == [_utc(1950, 2, 14, 9)]
    assert df.get_column("value").to_list() == [-0.2]
    assert "98404006" in caplog.text


@pytest.mark.parametrize(
    ("station_id", "hours"),
    [
        ("97101015", -4),  # Le Raizet, Guadeloupe; SYNOP 78897
        ("97213004", -4),  # Lamentin, Martinique; SYNOP 78925
        ("97307001", -3),  # Cayenne-Matoury, Guyane; SYNOP 81405
        ("97418110", 4),  # Gillot, Réunion; SYNOP 61980
        ("97502001", -4),  # Saint-Pierre; SYNOP 71805
        ("98403001", 3),  # Glorieuses; SYNOP 61968
        ("98403002", 3),  # Juan de Nova; SYNOP 61970
        ("98403003", 3),  # Europa; SYNOP 61972
        ("98403004", 4),  # Tromelin; SYNOP 61976
        ("98404001", 5),  # Kerguelen; SYNOP 61998
        ("98404002", 5),  # Nouvelle-Amsterdam; SYNOP 61996
        ("98404003", 9),  # Dumont d'Urville; SYNOP 89642
        ("98404004", 4),  # Crozet since 2003; SYNOP 61997
        ("98508001", 3),  # Pamandzi, Mayotte; SYNOP 67005
        ("98613001", 12),  # Hihifo, Wallis-et-Futuna; SYNOP 91753
        ("98715002", -10),  # Faa'a, Polynésie; SYNOP 91938
        ("98723001", -10),  # Hiva-Oa, Marquesas; SYNOP 91925
        ("98719005", -10),  # Mangareva, Gambier; SYNOP 91948
        ("98818001", 11),  # Nouméa, Nouvelle-Calédonie; SYNOP 91592
        ("31069001", None),  # metropolitan France
    ],
)
def test_meteofrance_observation_api_fu_offset(station_id: str, hours: int | None) -> None:
    """Test the offset of FU from UTC of each department, as measured against SYNOP (GH-2677)."""
    offsets = api._fu_hours(station_id)  # noqa: SLF001
    assert (offsets[-1][1] if offsets else None) == hours


@pytest.mark.parametrize(
    ("label", "utc"),
    [
        # Crozet is +5 h before 2003-10-01 00:00 (as stamped) and +4 h from then on
        ("200309302359", datetime(2003, 9, 30, 18, 59)),  # noqa: DTZ001
        ("200310010000", datetime(2003, 9, 30, 20, 0)),  # noqa: DTZ001
        ("200310010100", datetime(2003, 9, 30, 21, 0)),  # noqa: DTZ001
    ],
)
def test_meteofrance_observation_api_crozet_switch_is_pinned(label: str, utc: datetime) -> None:
    """Test that Crozet's FU offset changes at the stamp 2003-10-01 00:00 and not an hour before or after.

    The day of the switch is not known (the SYNOP archive has no reading of Crozet between 2003-09-15 and
    2003-11-07), so the date is a choice, and the numbers here are labels, not readings.
    """
    df = pl.DataFrame({"d": [label]}).select(
        api._parse_climate_date(pl.col("d"), "6_minutes", api._fu_hours("98404004")).alias("t")  # noqa: SLF001
    )
    assert df.get_column("t").to_list() == [utc.replace(tzinfo=UTC)]


def test_meteofrance_observation_api_unknown_fu_offset_warns_only_when_rows_come_back(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a request that returns nothing for a station without a known offset does not warn.

    Department 984 has period files for every decade, so the file of 2020-2024 is read for Port Martin
    (98404006, open 1950 to 1952) although it holds no row of it.
    """
    rows = [{"NUM_POSTE": "98404004", "AAAAMMJJHH": "2021010100", "T": "3.0"}]
    _serve_climate(monkeypatch, {"HOR_departement_984_periode_2020-2024": _climate_gz("hourly", "core", rows)})
    with caplog.at_level(logging.WARNING, logger=api.__name__):
        df = _values("hourly", "core", "temperature_air_2m", "98404006", _utc(2021, 1, 1), _utc(2021, 1, 2))
    assert df.is_empty()
    # the offset warning of the provider; the core says elsewhere that the source has no values of the station
    assert "98404006" not in "".join(record.getMessage() for record in caplog.records if record.name == api.__name__)


def test_meteofrance_observation_api_a_request_outside_every_period_file_is_the_empty_long_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a range no period file of the department covers reads no file and is no rows (GH-2627)."""
    rows = [{"NUM_POSTE": "31069001", "AAAAMMJJHH": "2021010100", "T": "3.0"}]
    asked = _serve_climate(monkeypatch, {"HOR_departement_031_periode_2020-2024": _climate_gz("hourly", "core", rows)})
    df = _values("hourly", "core", "temperature_air_2m", "31069001", _utc(1990, 1, 1), _utc(1990, 1, 2))
    assert asked == []
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()


def test_meteofrance_observation_api_a_period_file_that_is_a_404_is_the_empty_long_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a listed period file the portal does not have is left out, and a station with no other is no rows."""
    title = "HOR_departement_031_periode_2020-2024"
    resources = [{"title": title, "url": f"https://static.data.gouv.fr/{title}.csv.gz"}]

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        url = url or args[0]
        return File(url=url, content=BytesIO(json.dumps({"resources": resources}).encode("utf8")), status=200)

    def download_files(urls: list[str], **_: object) -> list[File]:
        return [File(url=url, content=FileNotFoundError(url), status=404) for url in urls]

    monkeypatch.setattr(api, "download_file", download_file)
    monkeypatch.setattr(api, "download_files", download_files)
    df = _values("hourly", "core", "temperature_air_2m", "31069001", _utc(2021, 1, 1), _utc(2021, 1, 2))
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()


def test_meteofrance_observation_api_daily_returns_the_validation_code_of_each_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the Q column of a parameter is returned verbatim in `quality_flags`, blank as null (GH-2018, GH-2758).

    The Q columns were in the file's schema and left out of the columns read. The daily description (the
    climatologie-donnees-quotidiennes-descriptif PDF, checked 2026-10-11): "un code qualité est associé à la
    mesure (noté Qparamètre). Il qualifie l'état de validation de la donnée : 9 : donnée filtrée, 0 : donnée
    protégée, 1 : donnée validée, 2 : donnée douteuse en cours de vérification". The codes are those the live
    Q_75_latest-2025-2026_RR-T-Vent file holds for QDXI and QRR: 1, 9 and blank.
    """
    rows = [
        {"NUM_POSTE": "75114001", "AAAAMMJJ": "20250101", "RR": "0.2", "QRR": "1", "TN": "3.0", "QTN": "9"},
        {"NUM_POSTE": "75114001", "AAAAMMJJ": "20250102", "RR": "0.0", "QRR": "", "TN": "2.5", "QTN": "2"},
        {"NUM_POSTE": "75114001", "AAAAMMJJ": "20250103", "RR": "1.0", "QRR": "0", "TN": "1.5", "QTN": "1"},
    ]
    files = {"QUOT_departement_75_periode_2025-2026_RR-T-Vent": _climate_gz("daily", "core", rows)}
    _serve_climate(monkeypatch, files)
    request = MeteoFranceObservationRequest(
        parameters=[("daily", "core", "precipitation_amount"), ("daily", "core", "temperature_air_min_2m")],
        start=_utc(2025, 1, 1),
        end=_utc(2025, 1, 3),
        settings=Settings(cache_disable=True),
    )
    df = stations_result(request, "daily", "core", "75114001").values().all().df
    assert df.sort("parameter", "timestamp").select("parameter", "value", "quality_flags").rows() == [
        ("precipitation_amount", 0.2, "1"),
        ("precipitation_amount", 0.0, None),
        ("precipitation_amount", 1.0, "0"),
        ("temperature_air_min_2m", 3.0, "9"),
        ("temperature_air_min_2m", 2.5, "2"),
        ("temperature_air_min_2m", 1.5, "1"),
    ]
    assert "quality" not in df.columns
    assert "quality_flag" not in df.columns


@pytest.mark.parametrize(
    ("resolution", "dataset"),
    [
        ("daily", "core"),
        ("daily", "others"),
        ("monthly", "data"),
        ("hourly", "core"),
        ("hourly", "others"),
        ("6_minutes", "data"),
    ],
)
def test_meteofrance_observation_api_every_parameter_has_a_validation_code_column(
    resolution: str, dataset: str
) -> None:
    """Test that the file of every dataset has the Q column of each parameter it declares, which is read with it."""
    schema = api._CLIMATE_SCHEMAS[resolution, dataset]  # noqa: SLF001
    declared = MeteoFranceObservationRequest.metadata[resolution][dataset]
    assert [parameter.name_original for parameter in declared if f"Q{parameter.name_original}" not in schema] == []


@pytest.mark.parametrize(
    ("url", "kept"),
    [
        pytest.param(
            "https://static.data.gouv.fr/resources/x/HOR_departement_31_periode_2020-2024.csv.gz",
            True,
            id="data.gouv.fr",
        ),
        pytest.param(
            "https://meteofrance.s3.sbg.io.cloud.ovh.net/data/x/HOR_departement_31_periode_2020-2024.csv.gz",
            True,
            id="the store of Météo-France",
        ),
        pytest.param("https://example.net/HOR_departement_31_periode_2020-2024.csv.gz", False, id="another host"),
        pytest.param("http://169.254.169.254/latest/meta-data/iam", False, id="an internal address"),
    ],
)
def test_meteofrance_observation_api_a_resource_is_fetched_only_at_data_gouv_or_the_store_of_meteofrance(
    url: str,
    kept: bool,  # noqa: FBT001
) -> None:
    """The address of a resource is the dataset's to name (GH-3339); a resource of no department is not read."""
    resources = [
        {"title": "HOR_departement_31_periode_2020-2024", "url": url},
        {"title": "documentation", "url": "https://example.net/documentation.pdf"},
    ]
    match = api._match_department_resources  # noqa: SLF001
    if kept:
        assert [resource["url"] for resource in match(resources, "HOR_departement_31_periode_", "")] == [url]
    else:
        with pytest.raises(DownloadError, match="the link was not fetched"):
            match(resources, "HOR_departement_31_periode_", "")


@pytest.mark.parametrize(
    ("content", "status", "asked_again"),
    [
        pytest.param(TimeoutError(), 500, True, id="timeout"),
        pytest.param(RedirectRefusedError("a redirect was not followed"), 500, False, id="refused redirect"),
        pytest.param(UpstreamMaintenanceError("data.gouv.fr is in maintenance"), 500, False, id="maintenance"),
        pytest.param(FileNotFoundError("gone"), 404, False, id="404"),
    ],
)
def test_the_climate_downloads_ask_again_only_for_a_failure_that_may_pass(
    monkeypatch: pytest.MonkeyPatch,
    content: Exception,
    status: int,
    asked_again: bool,  # noqa: FBT001
) -> None:
    """A refused redirect, like a 404, fails again at once, so the second, less concurrent attempt is not made."""
    url = "https://static.data.gouv.fr/resources/x.csv"
    second_attempts: list[str] = []

    def second_attempt(url: str, **_kwargs: object) -> File:
        second_attempts.append(url)
        return File(url=url, content=content, status=status)

    monkeypatch.setattr(api, "_resource_cache_ttl", lambda _resource: CacheExpiry.FIVE_MINUTES)
    monkeypatch.setattr(
        api, "download_files", lambda urls, **_kwargs: [File(url=u, content=content, status=status) for u in urls]
    )
    monkeypatch.setattr(api, "download_file", second_attempt)
    files = api._download_climate_resources([{"url": url}], Settings())  # noqa: SLF001
    assert isinstance(files[url].content, Exception)
    assert second_attempts == ([url] if asked_again else [])


def _hourly_rows(station_id: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    return (
        [{"NUM_POSTE": station_id, "AAAAMMJJHH": "2024061512", "T": "21.5"}],
        [{"NUM_POSTE": station_id, "AAAAMMJJHH": "2025061512", "T": "23.5"}],
    )


def _hourly_updated(
    monkeypatch: pytest.MonkeyPatch,
    last_modified: dict[str, str],
    start: datetime,
    end: datetime,
    rows: tuple[list[dict[str, str]], list[dict[str, str]]] | None = None,
    options: Options | None = None,
) -> datetime | None:
    """Read hourly values of Toulouse in a window, with the listing dating its two period files, and give the date.

    `rows` are the rows of the two files, which hold a reading of the station in each by default.
    """
    previous, latest = rows or _hourly_rows("31069001")
    _serve_climate(monkeypatch, _hourly_files("31", previous, latest), last_modified)
    request = MeteoFranceObservationRequest(
        parameters=[("hourly", "core", "temperature_air_2m")],
        start=start,
        end=end,
        settings=Settings(cache_disable=True),
        options=options,
    )
    result = stations_result(request, "hourly", "core", "31069001").values().all()
    assert not result.df.is_empty()
    return result.data_updated_at


_PERIODS = ("HOR_departement_31_periode_2020-2024", "HOR_departement_31_periode_2025-2026")


def test_meteofrance_observation_api_the_date_of_an_answer_is_the_newest_of_the_files_it_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The date is the newest `last_modified` of the files read: Étalab asks for the most recent update (GH-2567).

    Both period files are read and the older-dated of them is the one read last, so the newest is not the last.
    """
    old, new = _PERIODS
    dates = {old: "2026-10-26T06:54:51.123000+00:00", new: "2026-10-25T06:54:19+00:00"}

    updated = _hourly_updated(monkeypatch, dates, _utc(2024, 6, 15), _utc(2025, 6, 16))

    assert updated == datetime(2026, 10, 26, 6, 54, 51, 123000, tzinfo=UTC)


def test_meteofrance_observation_api_a_window_in_one_file_has_the_date_of_that_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A request that reads the old file only says when the old file was updated, not the date of the newest one."""
    old, new = _PERIODS
    dates = {old: "2026-03-01T10:00:00+00:00", new: "2026-10-26T06:54:51+00:00"}

    updated = _hourly_updated(monkeypatch, dates, _utc(2024, 6, 15), _utc(2024, 6, 16))

    assert updated == datetime(2026, 3, 1, 10, tzinfo=UTC)


def test_meteofrance_observation_api_a_date_without_a_zone_is_read_as_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    """data.gouv.fr writes its dates with an offset; one without is UTC, as every timestamp of the library is."""
    old, new = _PERIODS

    updated = _hourly_updated(
        monkeypatch,
        {old: "2026-03-01T10:00:00", new: "2026-03-01T11:00:00+01:00"},
        _utc(2024, 6, 15),
        _utc(2025, 6, 16),
    )

    assert updated == datetime(2026, 3, 1, 10, tzinfo=UTC)


@pytest.mark.parametrize(
    "dates",
    [
        pytest.param({}, id="no date in the listing"),
        pytest.param({_PERIODS[0]: "", _PERIODS[1]: "yesterday"}, id="no date that reads"),
    ],
)
def test_meteofrance_observation_api_no_date_in_the_listing_is_no_date_rather_than_the_time_of_the_request(
    monkeypatch: pytest.MonkeyPatch, dates: dict[str, str]
) -> None:
    """A resource the listing does not date leaves the answer undated: the date is the source's, never made up."""
    assert _hourly_updated(monkeypatch, dates, _utc(2024, 6, 15), _utc(2025, 6, 16)) is None


def test_meteofrance_observation_api_a_file_with_a_date_is_not_made_undated_by_one_without(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The newest of the dates the source states: a resource without one adds none and takes none away."""
    old, _ = _PERIODS

    updated = _hourly_updated(monkeypatch, {old: "2026-03-01T10:00:00+00:00"}, _utc(2024, 6, 15), _utc(2025, 6, 16))

    assert updated == datetime(2026, 3, 1, 10, tzinfo=UTC)


def test_meteofrance_observation_api_the_date_is_of_the_station_and_a_file_that_was_not_downloaded_is_not_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A period file that is a 404 was not read, so its date says nothing of the data in the answer."""
    old, new = _PERIODS
    dates = {old: "2026-03-01T10:00:00+00:00", new: "2026-10-26T06:54:51+00:00"}
    previous, _ = _hourly_rows("31069001")
    resources = [
        {"title": title, "url": f"https://static.data.gouv.fr/{title}.csv.gz", "last_modified": dates[title]}
        for title in (old, new)
    ]
    files = {old: _climate_gz("hourly", "core", previous)}

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        url = url or args[0]
        return File(url=url, content=BytesIO(json.dumps({"resources": resources}).encode("utf8")), status=200)

    def download_files(urls: list[str], **_: object) -> list[File]:
        found = []
        for url in urls:
            title = url.rsplit("/", 1)[1].removesuffix(".csv.gz")
            found.append(
                File(url=url, content=BytesIO(files[title]), status=200)
                if title in files
                else File(url=url, content=FileNotFoundError(url), status=404)
            )
        return found

    monkeypatch.setattr(api, "download_file", download_file)
    monkeypatch.setattr(api, "download_files", download_files)
    request = MeteoFranceObservationRequest(
        parameters=[("hourly", "core", "temperature_air_2m")],
        start=_utc(2024, 6, 15),
        end=_utc(2025, 6, 16),
        settings=Settings(cache_disable=True),
    )

    result = stations_result(request, "hourly", "core", "31069001").values().all()

    assert result.data_updated_at == datetime(2026, 3, 1, 10, tzinfo=UTC)


def test_meteofrance_observation_api_a_cached_listing_gives_the_date_of_the_copy_it_is(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The listing is read through the cache, and the date is in its body: an answer carries the date of its copy.

    The portal is stood in for by a server of this machine whose listing changes after the first request. Within the
    time the listing is kept (`CacheExpiry.METAINDEX`) the second answer is made of the first listing, asks the
    portal for nothing and has the date of the first copy, not of the portal's current one and not of the time it was
    made. Once the cache is off it is the current one.
    """
    old, new = _PERIODS
    previous, latest = _hourly_rows("31069001")
    files = _hourly_files("31", previous, latest)
    served: list[str] = []

    class Portal(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            served.append(self.path)
            updated = "2026-10-26T06:54:51+00:00" if len(served) == 1 else "2026-10-27T06:54:51+00:00"
            resources = [
                {"title": title, "url": f"{base}/{title}.csv.gz", "last_modified": updated} for title in (old, new)
            ]
            body = json.dumps({"resources": resources}).encode("utf8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            """Keep the output of the test clean."""

    server = HTTPServer(("127.0.0.1", 0), Portal)
    base = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(api, "_CLIMATE_BASE_URL", f"{base}/api/1/datasets/")
    monkeypatch.setattr(
        api,
        "download_files",
        lambda urls, **_: [
            File(url=url, content=BytesIO(files[url.rsplit("/", 1)[1].removesuffix(".csv.gz")]), status=200)
            for url in urls
        ],
    )

    def updated(settings: Settings) -> datetime | None:
        request = MeteoFranceObservationRequest(
            parameters=[("hourly", "core", "temperature_air_2m")],
            start=_utc(2024, 6, 15),
            end=_utc(2025, 6, 16),
            settings=settings,
        )
        return stations_result(request, "hourly", "core", "31069001").values().all().data_updated_at

    try:
        cached = Settings(cache_dir=tmp_path, cache_disable=False)
        first = updated(cached)
        second = updated(cached)
        uncached = updated(Settings(cache_dir=tmp_path, cache_disable=True))
    finally:
        server.shutdown()
        server.server_close()

    assert first == second == datetime(2026, 10, 26, 6, 54, 51, tzinfo=UTC)
    assert len(served) == 2
    assert uncached == datetime(2026, 10, 27, 6, 54, 51, tzinfo=UTC)


def test_meteofrance_observation_api_a_file_without_a_row_of_the_station_does_not_date_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A station that closed in 2024 is only in the older file, and the date of the newer one is not its date.

    Both files are read, as the request covers both years. The newer one was updated on the 26th of October 2026 and
    holds another station; the data of this one has not changed since the older file was written.
    """
    old, new = _PERIODS
    dates = {old: "2025-01-10T06:00:00+00:00", new: "2026-10-26T06:54:51+00:00"}
    other = [{"NUM_POSTE": "31070001", "AAAAMMJJHH": "2025061512", "T": "23.5"}]
    rows = ([{"NUM_POSTE": "31069001", "AAAAMMJJHH": "2024061512", "T": "21.5"}], other)

    updated = _hourly_updated(monkeypatch, dates, _utc(2024, 6, 15), _utc(2025, 6, 16), rows)

    assert updated == datetime(2025, 1, 10, 6, tzinfo=UTC)


def test_meteofrance_observation_api_a_file_whose_rows_are_outside_the_window_does_not_date_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A window that ends at the turn of the year reads the file of 2025-2026 by its years, and drops its only row.

    The row is of the station, in June 2025, and the window ends on 2025-01-01: the answer holds the older file's
    row alone and has the date of the older file.
    """
    old, new = _PERIODS
    dates = {old: "2025-01-10T06:00:00+00:00", new: "2026-10-26T06:54:51+00:00"}
    rows = (
        [{"NUM_POSTE": "31069001", "AAAAMMJJHH": "2024123112", "T": "3.5"}],
        [{"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025061512", "T": "23.5"}],
    )
    asked = _serve_climate(monkeypatch, _hourly_files("31", *rows), dates)
    request = MeteoFranceObservationRequest(
        parameters=[("hourly", "core", "temperature_air_2m")],
        start=_utc(2024, 12, 31),
        end=_utc(2025, 1, 1),
        settings=Settings(cache_disable=True),
    )

    result = stations_result(request, "hourly", "core", "31069001").values().all()

    assert sorted(asked) == sorted(_PERIODS)
    assert result.df.height == 1
    assert result.data_updated_at == datetime(2025, 1, 10, 6, tzinfo=UTC)


def _rows_with_a_reading_of_another_parameter_in_the_newer_file() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Give rows of the station: the older file has its temperature, the newer one only its precipitation."""
    return (
        [{"NUM_POSTE": "31069001", "AAAAMMJJHH": "2024061512", "T": "21.5"}],
        [{"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025061512", "T": "", "RR1": "0.2"}],
    )


def test_meteofrance_observation_api_a_file_with_no_reading_of_a_requested_parameter_does_not_date_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The newer file has rows of the station in the window, but none of them has the temperature that was asked for.

    The long shape drops the rows without a value, so the answer holds the older file's row alone.
    """
    old, new = _PERIODS
    dates = {old: "2025-01-10T06:00:00+00:00", new: "2026-10-26T06:54:51+00:00"}

    updated = _hourly_updated(
        monkeypatch,
        dates,
        _utc(2024, 6, 15),
        _utc(2025, 6, 16),
        _rows_with_a_reading_of_another_parameter_in_the_newer_file(),
    )

    assert updated == datetime(2025, 1, 10, 6, tzinfo=UTC)


def test_meteofrance_observation_api_a_row_without_a_value_is_a_row_of_the_wide_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wide shape keeps the rows without a value, so the newer file has a row in the answer and dates it."""
    old, new = _PERIODS
    dates = {old: "2025-01-10T06:00:00+00:00", new: "2026-10-26T06:54:51+00:00"}

    updated = _hourly_updated(
        monkeypatch,
        dates,
        _utc(2024, 6, 15),
        _utc(2025, 6, 16),
        _rows_with_a_reading_of_another_parameter_in_the_newer_file(),
        Options(shape="wide"),
    )

    assert updated == datetime(2026, 10, 26, 6, 54, 51, tzinfo=UTC)


def test_meteofrance_observation_api_a_file_changed_upstream_is_fetched_again_and_dates_the_answer_it_is(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The date of a file is of the copy the values are read from, also where the copy is kept for ever (GH-2567).

    A period file of 2020-2024 is cached with no end. The portal here, a server of this machine, changes the file and
    the date its listing gives it: the answer after that has the new reading and the new date, not the old copy under
    the new date. An answer after nothing changed reads the copy again and asks the portal for no file.
    """
    old, _ = _PERIODS
    reading = {"value": "21.5"}
    listed: dict[str, str] = {}
    asked_files: list[str] = []
    now = datetime.now(UTC)

    class Portal(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.endswith(".csv.gz"):
                asked_files.append(self.path)
                body = _climate_gz(
                    "hourly", "core", [{"NUM_POSTE": "31069001", "AAAAMMJJHH": "2024061512", "T": reading["value"]}]
                )
            else:
                resource = {"title": old, "url": f"{base}/{old}.csv.gz", "last_modified": listed["date"]}
                body = json.dumps({"resources": [resource]}).encode("utf8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            """Keep the output of the test clean."""

    server = HTTPServer(("127.0.0.1", 0), Portal)
    base = f"http://127.0.0.1:{server.server_port}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(api, "_CLIMATE_BASE_URL", f"{base}/api/1/datasets/")
    # the listing is read at the portal each time, as it is once its own cache has run out
    monkeypatch.setattr(
        api,
        "_get_climate_resources",
        lambda *_: json.loads(urlopen(f"{base}/api/1/datasets/x/", timeout=10).read())["resources"],  # noqa: S310
    )

    def answer() -> tuple[list[float], datetime | None]:
        request = MeteoFranceObservationRequest(
            parameters=[("hourly", "core", "temperature_air_2m")],
            start=_utc(2024, 6, 15),
            end=_utc(2024, 6, 16),
            settings=Settings(cache_dir=tmp_path, cache_disable=False),
        )
        result = stations_result(request, "hourly", "core", "31069001").values().all()
        return result.df.get_column("value").to_list(), result.data_updated_at

    first_date = now - timedelta(hours=2)
    # after the copy was made, which the clock of the test has to be told: the listing of a real portal says a date
    # that is past, and a copy made after it is the file
    second_date = now + timedelta(hours=1)
    try:
        listed["date"] = first_date.isoformat()
        first = answer()
        again = answer()
        files_before_the_change = len(asked_files)
        reading["value"] = "22.5"
        listed["date"] = second_date.isoformat()
        before_the_change = datetime.now(UTC)
        changed = answer()
    finally:
        server.shutdown()
        server.server_close()

    assert first == again == ([21.5], first_date)
    assert files_before_the_change == 1
    assert changed[0] == [22.5]
    # the date is no later than the new copy: this listing dates the file an hour ahead of the clock
    assert changed[1] is not None
    assert before_the_change <= changed[1] <= second_date
    assert len(asked_files) == 2


def test_meteofrance_observation_api_the_first_of_the_rows_of_one_reading_dates_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both files hold the reading of 2024-06-15 12 h, and the core keeps the first, that of the older file.

    The newer file was updated later and its row is the one the core drops, so it does not date the answer.
    """
    old, new = _PERIODS
    dates = {old: "2025-01-10T06:00:00+00:00", new: "2026-10-26T06:54:51+00:00"}
    rows = (
        [{"NUM_POSTE": "31069001", "AAAAMMJJHH": "2024061512", "T": "21.5"}],
        [{"NUM_POSTE": "31069001", "AAAAMMJJHH": "2024061512", "T": "22.5"}],
    )
    _serve_climate(monkeypatch, _hourly_files("31", *rows), dates)
    request = MeteoFranceObservationRequest(
        parameters=[("hourly", "core", "temperature_air_2m")],
        start=_utc(2024, 6, 15),
        end=_utc(2025, 6, 16),
        settings=Settings(cache_disable=True),
    )

    result = stations_result(request, "hourly", "core", "31069001").values().all()

    assert result.df.get_column("value").to_list() == [21.5]
    assert result.data_updated_at == datetime(2025, 1, 10, 6, tzinfo=UTC)


def test_meteofrance_observation_api_a_row_without_a_value_gives_its_reading_to_the_row_that_has_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The older file has no temperature at 12 h and the newer one has: the core keeps the one with a value (GH-3450).

    So the answer holds the newer file's reading beside the older file's other one, and the newer file, whose row is
    kept, dates it.
    """
    old, new = _PERIODS
    dates = {old: "2025-01-10T06:00:00+00:00", new: "2026-10-26T06:54:51+00:00"}
    rows = (
        [
            {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2024061512", "T": ""},
            {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2024061513", "T": "21.5"},
        ],
        [{"NUM_POSTE": "31069001", "AAAAMMJJHH": "2024061512", "T": "22.5"}],
    )
    _serve_climate(monkeypatch, _hourly_files("31", *rows), dates)
    request = MeteoFranceObservationRequest(
        parameters=[("hourly", "core", "temperature_air_2m")],
        start=_utc(2024, 6, 15),
        end=_utc(2025, 6, 16),
        settings=Settings(cache_disable=True),
    )

    result = stations_result(request, "hourly", "core", "31069001").values().all()

    assert result.df.get_column("value").to_list() == [22.5, 21.5]
    assert result.data_updated_at == datetime(2026, 10, 26, 6, 54, 51, tzinfo=UTC)


class _Portal:
    """A portal of data.gouv.fr on this machine: the listing of a period file and the file, which may change or fail."""

    def __init__(self) -> None:
        self.reading = "21.5"
        self.date = ""
        self.files_fail = False
        self.asked_files: list[str] = []
        portal = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path.endswith(".csv.gz"):
                    portal.asked_files.append(self.path)
                    if portal.files_fail:
                        self.send_response(503)
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    body = _climate_gz(
                        "hourly",
                        "core",
                        [{"NUM_POSTE": "31069001", "AAAAMMJJHH": "2024061512", "T": portal.reading}],
                    )
                else:
                    resource = {
                        "title": _PERIODS[0],
                        "url": f"{portal.base}/{_PERIODS[0]}.csv.gz",
                        "last_modified": portal.date,
                    }
                    body = json.dumps({"resources": [resource]}).encode("utf8")
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args: object) -> None:
                """Keep the output of the test clean."""

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def _answer_from(tmp_path: Path) -> tuple[list[float], datetime | None]:
    """Read the hourly temperature of Toulouse in June 2024 with the cache on, as an answer of the library."""
    request = MeteoFranceObservationRequest(
        parameters=[("hourly", "core", "temperature_air_2m")],
        start=_utc(2024, 6, 15),
        end=_utc(2024, 6, 16),
        settings=Settings(cache_dir=tmp_path, cache_disable=False),
    )
    result = stations_result(request, "hourly", "core", "31069001").values().all()
    return result.df.get_column("value").to_list(), result.data_updated_at


@pytest.mark.parametrize(
    ("ahead", "dated"),
    [
        pytest.param(timedelta(hours=1), True, id="an hour ahead"),
        pytest.param(timedelta(days=3650), False, id="ten years ahead"),
    ],
)
def test_meteofrance_observation_api_a_listing_that_dates_a_file_in_the_future_does_not_refetch_it_every_time(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ahead: timedelta, *, dated: bool
) -> None:
    """A date beyond now is not a reason to download a 100 MB file for each answer (GH-2567).

    The listing is read once and kept, and a copy made after it was read is not older than it. A date ten years ahead
    is no date of an update: no refetch for it, and the answer is undated. One an hour ahead is one that a source whose
    clock is ahead may give: the copy is fetched once, and the answer is dated by the copy.
    """
    portal = _Portal()
    monkeypatch.setattr(api, "_CLIMATE_BASE_URL", f"{portal.base}/api/1/datasets/")
    portal.date = (datetime.now(UTC) + ahead).isoformat()
    try:
        answers = [_answer_from(tmp_path) for _ in range(4)]
    finally:
        portal.close()

    assert [values for values, _ in answers] == [[21.5]] * 4
    assert len(portal.asked_files) == 1
    assert len({date for _, date in answers}) == 1
    date = answers[0][1]
    assert (date is not None) is dated
    if date is not None:
        # the date of the copy, which is made before the date the listing gives
        assert datetime.now(UTC) - timedelta(minutes=5) < date < datetime.now(UTC) + ahead


def test_meteofrance_observation_api_an_outage_of_the_file_host_serves_the_copy_and_its_own_date(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The file changed, the listing says so, and the host of the files does not answer: the copy from before is read.

    The date is that of the copy and not the listing's later one, which the values do not hold (GH-2567).
    """
    portal = _Portal()
    monkeypatch.setattr(api, "_CLIMATE_BASE_URL", f"{portal.base}/api/1/datasets/")
    # the listing is read at the portal each time, as it is once its own cache has run out
    monkeypatch.setattr(
        api,
        "_get_climate_resources",
        lambda *_: json.loads(urlopen(f"{portal.base}/api/1/datasets/x/", timeout=10).read())["resources"],  # noqa: S310
    )
    first_date = datetime.now(UTC) - timedelta(hours=2)
    try:
        portal.date = first_date.isoformat()
        first = _answer_from(tmp_path)
        made = datetime.now(UTC)
        portal.reading = "22.5"
        portal.date = (made + timedelta(hours=1)).isoformat()
        portal.files_fail = True
        outage = _answer_from(tmp_path)
        portal.files_fail = False
        recovered = _answer_from(tmp_path)
    finally:
        portal.close()

    assert first == ([21.5], first_date)
    # the copy from before, dated as of the time it was made, which is before the date of the listing
    assert outage[0] == [21.5]
    assert outage[1] is not None
    assert first_date < outage[1] <= made
    assert recovered[0] == [22.5]
    assert recovered[1] is not None
    assert recovered[1] > made


# the departments without frost (GH-3135): a temperature below 0 C is no reading there. Each case is a row of the
# source's file as it writes it (the fields the case reads and those beside them; Wallis-et-Futuna holds no reading
# below 0 C in any period, so its case is made up), with the period file it is in, the parameter that reads it, the
# window that holds it, and the text it keeps
_FROSTLESS = [
    pytest.param(
        "hourly",
        "core",
        "temperature_air_2m",
        "972",
        "HOR_departement_972_periode_2020-2024",
        "97212007",
        {"AAAAMMJJHH": "2021051012", "T": "-20.0", "QT": "9"},
        (_utc(2021, 5, 10), _utc(2021, 5, 11)),
        "-20.0",
        id="972 hourly T -20.0 (GROS-MORNE BOISLEZ, 441 m)",
    ),
    pytest.param(
        "hourly",
        "others",
        "temperature_dew_point_2m",
        "973",
        "HOR_departement_973_periode_2020-2024",
        "97353001",
        {"AAAAMMJJHH": "2022122914", "TD": "-23.8", "QTD": "9"},
        (_utc(2022, 12, 29), _utc(2022, 12, 30)),
        "-23.8",
        id="973 hourly TD -23.8 (MARIPASOULA, 106 m)",
    ),
    pytest.param(
        "daily",
        "core",
        "temperature_air_mean_2m",
        "971",
        "QUOT_departement_971_periode_1950-2024_RR-T-Vent",
        "97127004",
        {"AAAAMMJJ": "20081129", "TM": "-10.9", "QTM": "9"},
        (_utc(2008, 11, 29), _utc(2008, 11, 30)),
        "-10.9",
        id="971 daily TM -10.9 (ST-MARTIN GRAND-CASE, 5 m)",
    ),
    pytest.param(
        "monthly",
        "data",
        "temperature_air_mean_2m",
        "972",
        "MENS_departement_972_periode_1950-2024",
        "97218013",
        {"AAAAMM": "200106", "TMM": "-11.5", "QTMM": "1"},
        (_utc(2001, 6, 1), _utc(2001, 7, 1)),
        "-11.5",
        id="972 monthly TMM -11.5 (MORNE-ROUGE CHAMDST, 474 m)",
    ),
    pytest.param(
        "hourly",
        "others",
        "temperature_dew_point_2m",
        "985",
        "HOR_departement_985_periode_2025-2026",
        "98511003",
        # between TD 20.0 at 06 h and 20.6 at 08 h
        {"AAAAMMJJHH": "2025061007", "T": "23.8", "QT": "1", "TD": "-4.5", "QTD": "9", "U": "15", "QU": "9"},
        (_utc(2025, 6, 10), _utc(2025, 6, 11)),
        "-4.5",
        id="985 (Mayotte) hourly TD -4.5 (VAHIBE_SAPC, 222 m)",
    ),
    pytest.param(
        "hourly",
        "others",
        "temperature_dew_point_2m",
        "984",
        "HOR_departement_984_periode_2010-2019",
        "98403004",
        {"AAAAMMJJHH": "2014040100", "T": "27.3", "QT": "1", "TD": "-21.6", "QTD": "9", "U": "3", "QU": "9"},
        (_utc(2014, 3, 31), _utc(2014, 4, 1, 12)),
        "-21.6",
        id="984 (Iles Eparses) hourly TD -21.6 (TROMELIN, 7 m)",
    ),
    pytest.param(
        "hourly",
        "others",
        "temperature_dew_point_2m",
        "987",
        "HOR_departement_987_periode_2020-2024",
        "98720002",
        {"AAAAMMJJHH": "2023031401", "T": "28.3", "QT": "1", "TD": "-32.6", "QTD": "1", "U": "1", "QU": "1"},
        (_utc(2023, 3, 14), _utc(2023, 3, 15)),
        "-32.6",
        id="987 (French Polynesia) hourly TD -32.6 (HAO AERO, 5 m)",
    ),
    pytest.param(
        "hourly",
        "core",
        "temperature_air_2m",
        "986",
        "HOR_departement_986_periode_2020-2024",
        "98611001",
        {"AAAAMMJJHH": "2023031401", "T": "-1.0", "QT": "1"},
        (_utc(2023, 3, 13), _utc(2023, 3, 15)),
        "-1.0",
        id="986 (Wallis-et-Futuna) hourly T -1.0, made up (MAOPOOPO, 35 m)",
    ),
]


@pytest.mark.parametrize(
    ("resolution", "dataset", "parameter", "department", "title", "station", "row", "window", "text"), _FROSTLESS
)
def test_meteofrance_observation_api_a_temperature_below_zero_is_null_where_there_is_no_frost(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    dataset: str,
    parameter: str,
    department: str,
    title: str,
    station: str,
    row: dict[str, str],
    window: tuple[datetime, datetime],
    text: str,
) -> None:
    """Test that a temperature below 0 C in Guadeloupe, Martinique, Guyane and Mayotte is null with its text."""
    assert station.startswith(department)
    files = {title: _climate_gz(resolution, dataset, [{"NUM_POSTE": station, **row}])}
    _serve_climate(monkeypatch, files)
    df = _values(resolution, dataset, parameter, station, *window, drop_nulls=False)
    assert df.get_column("value").to_list() == [None]
    assert df.get_column("quality_flags").to_list()[0].endswith(f"rejected:range,raw:{text}")


@pytest.mark.parametrize(
    ("department", "station", "value", "kept"),
    [
        # La Reunion has frost at altitude: PLAINE DES CHICOTS (97411170, 1,834 m) read -2.3 C in 2020-08-11 02 h FU
        ("974", "97411170", "-2.3", True),
        # Saint-Pierre-et-Miquelon, at 47 degrees north, and a station of the mainland
        ("975", "97502001", "-5.0", True),
        ("07", "07005001", "-5.0", True),
        # the southern territories (984, KERGUELEN) and New Caledonia (988, OUANAHAM) are not in the rule
        ("984", "98404001", "-5.0", True),
        ("988", "98814001", "-5.0", True),
        # 0 C is no reading below it, and a warm one is none either
        ("971", "97127004", "0.0", True),
        ("971", "97127004", "25.4", True),
        ("972", "97212007", "-0.1", False),
        # the lowest-lying edge of each department of the rule: the Iles Eparses (EUROPA), Mayotte, Wallis-et-Futuna and
        # French Polynesia (RAPA, 27.6 S)
        ("984", "98403003", "-0.1", False),
        ("985", "98508001", "-0.1", False),
        ("986", "98613001", "-0.1", False),
        ("987", "98741001", "-0.1", False),
    ],
)
def test_meteofrance_observation_api_a_temperature_below_zero_is_null_only_where_there_is_no_frost(
    monkeypatch: pytest.MonkeyPatch,
    department: str,
    station: str,
    value: str,
    kept: bool,  # noqa: FBT001
) -> None:
    """Test that the rule leaves La Reunion, Saint-Pierre and the mainland alone, and 0 C and warmer stay (GH-3135).

    The reading of La Reunion is that of PLAINE DES CHICOTS; -0.1 C in Martinique is the nearest below the edge.
    """
    title = f"HOR_departement_{department}_periode_2020-2024"
    row = {"NUM_POSTE": station, "AAAAMMJJHH": "2020081102", "T": value, "QT": "1"}
    _serve_climate(monkeypatch, {title: _climate_gz("hourly", "core", [row])})
    df = _values(
        "hourly", "core", "temperature_air_2m", station, _utc(2020, 8, 10), _utc(2020, 8, 12), drop_nulls=False
    )
    assert df.get_column("value").to_list() == [float(value) if kept else None]


@pytest.mark.parametrize(
    ("department", "station", "kept"),
    [
        # the departments of the rule: Mayotte (VAHIBE_SAPC), Iles Eparses (TROMELIN), Guadeloupe (ST-CLAUDE CITERNE)
        ("985", "98511003", False),
        ("984", "98403004", False),
        ("971", "97124009", False),
        # La Reunion has frost at altitude, the southern territories and the mainland have it too
        ("974", "97411170", True),
        ("984", "98404001", True),
        ("07", "07005001", True),
    ],
)
def test_meteofrance_observation_api_the_humidity_beside_a_dew_point_below_zero_is_null_where_there_is_no_frost(
    monkeypatch: pytest.MonkeyPatch,
    department: str,
    station: str,
    kept: bool,  # noqa: FBT001
) -> None:
    """Test that the U of an hour whose TD the frost rule nulls is null too, with its text, and U alone is asked for.

    The first row is that of VAHIBE_SAPC (98511003) at 2025-06-10 07 h (TD -4.5 C beside U 15 %), the second an hour of
    a TD of 20.6 C beside U 78 %, the third a TD of 0.0 C, which is no reading below 0 C; a U of 15 % beside a dew point
    that is a reading is none to null (no floor on the humidity). The dew point is read for the humidity and is not in
    the answer (GH-3629).
    """
    rows = [
        {"NUM_POSTE": station, "AAAAMMJJHH": "2025061007", "TD": "-4.5", "QTD": "9", "U": "15", "QU": "9"},
        {"NUM_POSTE": station, "AAAAMMJJHH": "2025061008", "TD": "20.6", "QTD": "1", "U": "78", "QU": "1"},
        {"NUM_POSTE": station, "AAAAMMJJHH": "2025061009", "TD": "0.0", "QTD": "1", "U": "15", "QU": "1"},
    ]
    title = f"HOR_departement_{department}_periode_2025-2026"
    _serve_climate(monkeypatch, {title: _climate_gz("hourly", "others", rows)})
    df = _values(
        "hourly", "others", "humidity_relative", station, _utc(2025, 6, 10), _utc(2025, 6, 11), drop_nulls=False
    )
    assert df.get_column("parameter").unique().to_list() == ["humidity_relative"]
    assert df.get_column("value").to_list() == ([None, 0.78, 0.15] if not kept else [0.15, 0.78, 0.15])
    flags = df.get_column("quality_flags").to_list()
    assert flags[0] == ("9" if kept else "9,rejected:consistency,raw:15")
    assert flags[1] == "1"
    assert flags[2] == "1"


def test_meteofrance_observation_api_the_humidity_and_the_dew_point_are_nulled_together_in_one_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that asking for the dataset gives both nulled, each with its own text (GH-3629)."""
    station = "98403004"
    rows = [{"NUM_POSTE": station, "AAAAMMJJHH": "2014040100", "TD": "-21.6", "QTD": "9", "U": "3", "QU": "9"}]
    _serve_climate(monkeypatch, {"HOR_departement_984_periode_2010-2019": _climate_gz("hourly", "others", rows)})
    request = MeteoFranceObservationRequest(
        parameters=[("hourly", "others", "humidity_relative"), ("hourly", "others", "temperature_dew_point_2m")],
        start=_utc(2014, 3, 31),
        end=_utc(2014, 4, 2),
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    )
    df = stations_result(request, "hourly", "others", station).values().all().df
    by_parameter = {str(p): g for (p,), g in df.partition_by("parameter", as_dict=True).items()}
    assert by_parameter["humidity_relative"].get_column("value").to_list() == [None]
    assert by_parameter["humidity_relative"].get_column("quality_flags").to_list() == ["9,rejected:consistency,raw:3"]
    assert by_parameter["temperature_dew_point_2m"].get_column("value").to_list() == [None]
    assert by_parameter["temperature_dew_point_2m"].get_column("quality_flags").to_list() == [
        "9,rejected:range,raw:-21.6"
    ]
