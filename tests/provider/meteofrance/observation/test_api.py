# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for Météo-France observation API ("Données climatologiques de base")."""

from __future__ import annotations

import gzip
import json
import logging
from datetime import UTC, datetime
from io import BytesIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

from tests.provider.value_stubs import stations_result
from wetterdienst import Settings
from wetterdienst.provider.meteofrance.observation import MeteoFranceObservationRequest, api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    import polars as pl


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

    The listing also names a period that is not served, so that a file the request does not need but is
    downloaded anyway fails with an unknown title.
    """
    titles = [*files, "unserved"]
    resources = [{"title": title, "url": f"https://example.invalid/{title}.csv.gz"} for title in titles]
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
