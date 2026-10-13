# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for Météo-France observation API ("Données climatologiques de base")."""

from __future__ import annotations

import gzip
import json
import logging
from datetime import UTC, datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.provider.value_stubs import stations_result
from wetterdienst import Settings
from wetterdienst.exceptions import NoParametersFoundError
from wetterdienst.provider.meteofrance.observation import MeteoFranceObservationRequest, api
from wetterdienst.util.network import File


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
            ("daily", "others", "humidity_relative"),
            ("daily", "core", "wind_speed"),
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
        ("others", "humidity_relative"),
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
    df = next(request.values.query()).df
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
    df = next(request.values.query()).df
    assert df.get_column("value").is_not_null().sum() > 0


@pytest.mark.remote
@pytest.mark.parametrize(
    ("dataset", "parameter"),
    [
        ("core", "temperature_air_2m"),
        ("core", "precipitation_amount"),
        ("core", "wind_direction_gust_max"),
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
    df = next(request.values.query()).df
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
    df = next(request.values.query()).df
    assert not df.is_empty()
    # 6-minute intervals within a day: exercise that the date column parses to real, distinct
    # timestamps rather than e.g. all collapsing to midnight
    assert df.get_column("timestamp").n_unique() > 1


def _climate_gz(resolution: str, dataset: str, rows: list[dict[str, str]]) -> bytes:
    """Write rows into a gzipped file with the columns of the source's file, empty where a row has none."""
    schema = list(api._CLIMATE_SCHEMAS[resolution, dataset])  # noqa: SLF001
    lines = [";".join(schema)] + [";".join(row.get(column, "") for column in schema) for row in rows]
    return gzip.compress("\n".join(lines).encode("utf8"))


def _serve_climate(monkeypatch: pytest.MonkeyPatch, files: dict[str, bytes]) -> list[str]:
    """Serve the period files of a dataset, by the title of their resource, and return the titles asked for.

    A file the test does not serve fails with a KeyError, and the titles asked for show whether the
    request read the files it needs and no others.
    """
    resources = [{"title": title, "url": f"https://example.invalid/{title}.csv.gz"} for title in files]
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
) -> pl.DataFrame:
    request = MeteoFranceObservationRequest(
        parameters=[(resolution, dataset, parameter)],
        start=start,
        end=end,
        settings=Settings(cache_disable=True),
    )
    return stations_result(request, resolution, dataset, station_id).values.all().df.sort("timestamp")


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
    df = _values("hourly", "core", "wind_speed_last_10min", "31069001", start, end)
    assert df.get_column("value").to_list() == [2.2]
    df = _values("hourly", "core", "wind_direction_last_10min", "31069001", start, end)
    assert df.get_column("value").to_list() == [10.0]
    for old in ("wind_speed", "wind_direction"):
        with pytest.raises(NoParametersFoundError):
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
    with pytest.raises(NoParametersFoundError):
        MeteoFranceObservationRequest(parameters=[("hourly", "core", "wind_gust_max")])


def test_meteofrance_observation_api_hourly_calm_wind_has_no_direction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a direction of 0, the calm wind, is null and 360, the north, stays (GH-2720).

    The rows are the file's own for station 31069001 (Toulouse-Blagnac) at 2025-01-01 02 h, 2025-01-01 09 h
    (FF = 0.0, DD = 0, with a gust from 320) and 2025-01-03 07 h (DD = 360), and for 31042012 (Luchon) at
    2025-01-31 05 h, where FF, DD, FXY and DXY all read zero. The field descriptions give the directions
    "en rose de 360" and no code for a calm wind.
    """
    latest = [
        {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025010102", "FF": "2.2", "DD": "10", "FXY": "2.5", "DXY": "140"},
        {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025010109", "FF": "0.0", "DD": "0", "FXY": "1.4", "DXY": "320"},
        {"NUM_POSTE": "31069001", "AAAAMMJJHH": "2025010307", "FF": "0.9", "DD": "360", "FXY": "2.3", "DXY": "340"},
        {"NUM_POSTE": "31042012", "AAAAMMJJHH": "2025013105", "FF": "0.0", "DD": "0", "FXY": "0.0", "DXY": "0"},
    ]
    _serve_climate(monkeypatch, {"HOR_departement_31_periode_2025-2026": _climate_gz("hourly", "core", latest)})
    start, end = _utc(2025, 1, 1), _utc(2025, 2, 1)
    df = _values("hourly", "core", "wind_direction_last_10min", "31069001", start, end)
    assert df.get_column("timestamp").to_list() == [_utc(2025, 1, 1, 2), _utc(2025, 1, 3, 7)]
    assert df.get_column("value").to_list() == [10.0, 360.0]
    df = _values("hourly", "core", "wind_direction_gust_max", "31069001", start, end)
    assert df.get_column("value").to_list() == [140.0, 320.0, 340.0]
    for parameter in ("wind_direction_last_10min", "wind_direction_gust_max"):
        assert _values("hourly", "core", parameter, "31042012", start, end).is_empty()


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
    df = _values("hourly", "core", "wind_direction_last_10min", "98404001", _utc(1965, 4, 17), _utc(1965, 4, 18))
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
    assert "98404006" not in caplog.text


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
    df = (
        stations_result(request, "daily", "core", "75114001")
        .values.all()
        .df.with_columns(pl.col("parameter").cast(pl.String))
    )
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
