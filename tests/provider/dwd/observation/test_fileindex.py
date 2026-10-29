# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation file index creation."""

import datetime as dt
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import polars as pl
import portion
import pytest

from tests.provider.value_stubs import stations_result
from wetterdienst import Settings
from wetterdienst.metadata.period import Period
from wetterdienst.model.metadata import DatasetModel
from wetterdienst.provider.dwd.observation import (
    DwdObservationMetadata,
    DwdObservationRequest,
    download,
    fileindex,
)
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.provider.dwd.observation.fileindex import (
    create_file_index_for_climate_observations,
    create_file_list_for_climate_observations,
    is_mez_file,
)


@pytest.mark.remote
def test_file_index_creation_success(default_settings: Settings) -> None:
    """Test the creation of a file index for historical climate data."""
    # Existing combination of parameters
    file_index = create_file_index_for_climate_observations(
        dataset=DwdObservationMetadata.daily.climate_summary,
        period=Period.RECENT,
        settings=default_settings,
    ).collect()
    assert not file_index.is_empty()
    assert file_index.filter(pl.col("station_id").eq("01048")).get_column("url").to_list() == [
        (
            "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
            "climate/daily/kl/recent/tageswerte_KL_01048_akt.zip"
        ),
    ]


@pytest.mark.remote
def test_file_index_creation_precipitation_minute_1(default_settings: Settings) -> None:
    """Test the creation of a file index for 1-minute precipitation historical data."""
    # Existing combination of parameters
    file_index = create_file_index_for_climate_observations(
        dataset=DwdObservationMetadata.minute_1.precipitation,
        period=Period.HISTORICAL,
        settings=default_settings,
    ).collect()
    assert not file_index.is_empty()
    assert "00000" not in file_index.get_column("station_id")


@pytest.mark.remote
def test_create_file_list_for_dwd_server(default_settings: Settings) -> None:
    """Test the creation of a file list for DWD server."""
    remote_file_path = create_file_list_for_climate_observations(
        station_id="01048",
        dataset=DwdObservationMetadata.daily.climate_summary,
        period=Period.RECENT,
        settings=default_settings,
    ).to_list()
    assert remote_file_path == [
        (
            "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
            "daily/kl/recent/tageswerte_KL_01048_akt.zip"
        ),
    ]
    # with date range
    remote_file_path = create_file_list_for_climate_observations(
        station_id="00003",
        dataset=DwdObservationMetadata.minute_10.temperature_air,
        period=Period.HISTORICAL,
        date_ranges=["19930428_19991231"],
        settings=default_settings,
    ).to_list()
    assert remote_file_path == [
        (
            "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
            "10_minutes/air_temperature/historical/"
            "10minutenwerte_TU_00003_19930428_19991231_hist.zip"
        ),
    ]


_TEN_MINUTE_FILES = [
    "10minutenwerte_TU_01048_19900101_19910630_hist.zip",
    "10minutenwerte_TU_01048_19911119_19991231_hist.zip",
    "10minutenwerte_TU_01048_20000101_20091231_hist.zip",
    "10minutenwerte_TU_01048_20100101_20191231_hist.zip",
    "10minutenwerte_TU_01048_20200101_20241231_hist.zip",
    "10minutenwerte_TU_01048_20250101_20250731_hist.zip",
]


def _serve_ten_minute_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the listing of the historical 10 minute air temperature directory from the test."""
    urls = [
        f"https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/historical/{name}"
        for name in _TEN_MINUTE_FILES
    ]
    listing = (
        pl.DataFrame({"url": urls}).with_columns(pl.col("url").str.split("/").list.last().alias("filename")).lazy()
    )
    monkeypatch.setattr(fileindex, "_create_file_index_for_dwd_server", lambda *_, **__: listing)


def test_historical_file_bounds_are_utc_instants_of_the_stamps(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that a file spans the UTC (or, before 2000, MEZ) days its name gives, not Berlin days.

    The stamps of the 10 minute files are UTC from 2000 and MEZ, the fixed UTC+1, before, so the file
    of 2010 to 2019 ends at 00:00 UTC on 2020-01-01 and one that ends in summer 1991 at 23:00 UTC on 30 June,
    whatever Europe/Berlin does with summer time (GH-2811). The files at the turn of 1999 to 2000 reach into
    each other's hour (GH-2815).
    """
    _serve_ten_minute_files(monkeypatch)
    index = create_file_index_for_climate_observations(
        DwdObservationMetadata.minute_10.temperature_air, Period.HISTORICAL, default_settings
    ).collect()
    bounds = {row["date_range"]: (row["start_timestamp"], row["end_timestamp"]) for row in index.iter_rows(named=True)}
    utc = dt.UTC
    assert bounds["19911119_19991231"] == (
        dt.datetime(1991, 11, 18, 23, tzinfo=utc),
        dt.datetime(2000, 1, 1, tzinfo=utc),
    )
    # the first file of 2000 begins with the six stamps 23:00 to 23:50 UTC of 1999-12-31 (GH-2815), and is chosen
    # from 22:00 UTC, as the file of 1999 lists the stamps of that hour twice and it tells the copy (GH-2829)
    assert bounds["20000101_20091231"] == (
        dt.datetime(1999, 12, 31, 22, tzinfo=utc),
        dt.datetime(2010, 1, 1, tzinfo=utc),
    )
    assert bounds["19900101_19910630"] == (
        dt.datetime(1989, 12, 31, 23, tzinfo=utc),
        dt.datetime(1991, 6, 30, 23, tzinfo=utc),
    )
    assert bounds["20100101_20191231"] == (
        dt.datetime(2010, 1, 1, tzinfo=utc),
        dt.datetime(2020, 1, 1, tzinfo=utc),
    )
    assert index.schema["start_timestamp"] == pl.Datetime("us", "UTC")
    assert index.schema["end_timestamp"] == pl.Datetime("us", "UTC")


@pytest.mark.parametrize(
    ("start", "end", "date_ranges"),
    [
        # the last hour of a file's last day: the file that holds it is chosen (it was dropped, as the
        # file's end was taken as 23:00 UTC)
        ("2019-12-31T23:00+00:00", "2019-12-31T23:50+00:00", ["20100101_20191231"]),
        # in summer the last two hours (the end was taken as 22:00 UTC, Berlin midnight in CEST)
        ("2025-07-31T22:00+00:00", "2025-07-31T22:30+00:00", ["20250101_20250731"]),
        ("2025-07-31T23:00+00:00", "2025-07-31T23:50+00:00", ["20250101_20250731"]),
        # not affected before: the hour before the cut-off of a winter file
        ("2019-12-31T22:00+00:00", "2019-12-31T22:30+00:00", ["20100101_20191231"]),
        # across the seam both files are chosen
        ("2019-12-31T23:00+00:00", "2020-01-01T01:00+00:00", ["20100101_20191231", "20200101_20241231"]),
        # a request that ends on the first stamp of a file needs that file
        ("2019-12-31T23:50+00:00", "2020-01-01T00:00+00:00", ["20100101_20191231", "20200101_20241231"]),
        # a Berlin-aware window is the same instants: 23:00 to 00:30 UTC
        ("2020-01-01T00:00+01:00", "2020-01-01T01:30+01:00", ["20100101_20191231", "20200101_20241231"]),
        # a window that starts after a file's last stamp does not need it
        ("2020-01-01T00:00+00:00", "2020-01-01T01:00+00:00", ["20200101_20241231"]),
        # MEZ before 2000 is a fixed UTC+1: the first hour of a file is 23:00 UTC of the day before, and a file
        # that ends in summer ends at 23:00 UTC, where Berlin's CEST midnight is 22:00 UTC
        ("1991-11-18T23:00+00:00", "1991-11-18T23:30+00:00", ["19911119_19991231"]),
        ("1991-06-30T22:30+00:00", "1991-06-30T22:50+00:00", ["19900101_19910630"]),
        # the file of 1999 lists these stamps twice, one row a copy of a row of the file of 2000 (GH-2829)
        ("1999-12-31T22:00+00:00", "1999-12-31T22:50+00:00", ["19911119_19991231", "20000101_20091231"]),
        ("1999-12-31T21:00+00:00", "1999-12-31T21:50+00:00", ["19911119_19991231"]),
        # the stamps 23:00 to 23:50 UTC of 1999-12-31 are in the file of 2000, whose name says 20000101, and the
        # wind file of 1999 holds them as MEZ 00:00 to 00:50 (GH-2815)
        ("1999-12-31T23:00+00:00", "1999-12-31T23:50+00:00", ["19911119_19991231", "20000101_20091231"]),
        ("1999-12-31T22:00+00:00", "2000-01-01T00:30+00:00", ["19911119_19991231", "20000101_20091231"]),
    ],
)
def test_historical_files_are_chosen_by_the_instants_they_cover(
    monkeypatch: pytest.MonkeyPatch,
    default_settings: Settings,
    start: str,
    end: str,
    date_ranges: list[str],
) -> None:
    """Test that the historical files chosen for a request are those whose stamps fall in the window."""
    _serve_ten_minute_files(monkeypatch)
    berlin = ZoneInfo("Europe/Berlin")
    interval = portion.closed(
        dt.datetime.fromisoformat(start).astimezone(berlin), dt.datetime.fromisoformat(end).astimezone(berlin)
    )
    values = SimpleNamespace(sr=SimpleNamespace(request=SimpleNamespace(interval=interval)))
    chosen = DwdObservationValues._get_historical_date_ranges(  # noqa: SLF001
        values, "01048", DwdObservationMetadata.minute_10.temperature_air, default_settings
    )
    assert chosen == date_ranges


def test_no_date_range_selects_every_file_and_an_empty_list_none(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that ``None`` is no filter, and that ``[]`` -- a window no file covers -- selects no file (GH-3505)."""
    _serve_ten_minute_files(monkeypatch)
    dataset = DwdObservationMetadata.minute_10.temperature_air

    def chosen(date_ranges: list[str] | None) -> list[str]:
        urls = create_file_list_for_climate_observations(
            "01048", dataset, Period.HISTORICAL, default_settings, date_ranges
        )
        return [url.rsplit("/", 1)[-1] for url in urls]

    assert chosen(None) == _TEN_MINUTE_FILES
    assert chosen(["20100101_20191231"]) == ["10minutenwerte_TU_01048_20100101_20191231_hist.zip"]
    assert chosen([]) == []


def test_a_window_between_two_historical_files_downloads_no_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a request for the gap between two files of a station reads none of the station's files (GH-3505).

    The station's files end in 1991-06 and begin again in 1991-11: a window in between has no date range, which
    was read as no filter and downloaded and parsed all six files for rows the window then dropped.
    """
    _serve_ten_minute_files(monkeypatch)
    downloaded: list[str] = []
    monkeypatch.setattr(download, "download_files", lambda urls, *_, **__: downloaded.extend(urls) or [])
    request = DwdObservationRequest(
        parameters=[("10_minutes", "temperature_air", "temperature_air_2m")],
        periods=["historical"],
        start=dt.datetime(1991, 7, 15, tzinfo=dt.UTC),
        end=dt.datetime(1991, 9, 15, tzinfo=dt.UTC),
        settings=Settings(cache_disable=True),
    )
    values = stations_result(request, "10_minutes", "temperature_air", "01048").values()
    model = request.metadata["10_minutes"]["temperature_air"]

    assert values._periods_and_date_ranges("01048", model, request.settings) == [(Period.HISTORICAL, [])]  # noqa: SLF001
    assert values._collect_station_parameter_or_dataset("01048", model).is_empty()  # noqa: SLF001
    assert values._files_ahead("01048", [model]).urls == []  # noqa: SLF001
    assert downloaded == []


@pytest.mark.parametrize(
    ("filename", "mez"),
    [
        ("10minutenwerte_TU_01048_19911119_19991231_hist.zip", True),
        ("5minutenwerte_nieder_01048_19991201_19991231_hist.zip", True),
        ("10minutenwerte_TU_01048_20000101_20091231_hist.zip", False),
        ("1minutenwerte_nieder_00003_20000101_20000131_hist.zip", False),
        # recent and now carry no dates and are UTC
        ("10minutenwerte_TU_01048_akt.zip", False),
    ],
)
def test_is_mez_file(filename: str, *, mez: bool) -> None:
    """Test that a file is MEZ as a whole by the first day its name gives (GH-2815)."""
    assert is_mez_file(filename) is mez


@pytest.mark.parametrize(
    ("dataset", "directory", "december", "january"),
    [
        (
            DwdObservationMetadata.minute_5.precipitation,
            "5_minutes/precipitation/historical",
            "5minutenwerte_nieder_01048_19991201_19991231_hist.zip",
            "5minutenwerte_nieder_01048_20000101_20000131_hist.zip",
        ),
        (
            DwdObservationMetadata.minute_1.precipitation,
            "1_minute/precipitation/historical",
            "1minutenwerte_nieder_00003_19991201_19991231_hist.zip",
            "1minutenwerte_nieder_00003_20000101_20000131_hist.zip",
        ),
    ],
)
def test_the_one_and_five_minute_files_meet_at_midnight_utc_and_reach_into_it(
    monkeypatch: pytest.MonkeyPatch,
    default_settings: Settings,
    dataset: DatasetModel,
    directory: str,
    december: str,
    january: str,
) -> None:
    """Test the bounds of the 1- and 5-minute files at the turn of 1999 to 2000 (GH-2815).

    The file of January 2000 begins at 00:00 UTC, unlike the 10 minute one. The file of December 1999 is MEZ and
    holds stamps past its MEZ midnight (1-minute: to 00:59, 5-minute: 00:00, which the parser drops, GH-2827;
    station 00003 and 01048, read 2026-10-13), which are 23:00 to 23:59 UTC, so it ends at 00:00 UTC of 2000-01-01
    and a request for that hour gets the December file.
    """
    base = f"https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/{directory}/"
    listing = pl.DataFrame({"url": [base + december, base + january], "filename": [december, january]}).lazy()
    monkeypatch.setattr(fileindex, "_create_file_index_for_dwd_server", lambda *_, **__: listing)
    index = create_file_index_for_climate_observations(dataset, Period.HISTORICAL, default_settings).collect()
    bounds = {row["filename"]: (row["start_timestamp"], row["end_timestamp"]) for row in index.iter_rows(named=True)}
    utc = dt.UTC
    assert bounds[december][1] == dt.datetime(2000, 1, 1, tzinfo=utc)
    assert bounds[january][0] == dt.datetime(2000, 1, 1, tzinfo=utc)
