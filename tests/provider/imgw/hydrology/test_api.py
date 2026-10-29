# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the IMGW hydrology API."""

import datetime as dt
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.exceptions import DownloadError
from wetterdienst.provider.imgw.hydrology.api import ImgwHydrologyRequest
from wetterdienst.util.network import File


def _expected_station(resolution: str) -> pl.DataFrame:
    """Provide expected DataFrame for station."""
    return pl.DataFrame(
        [
            {
                "resolution": resolution,
                "dataset": "hydrology",
                "station_id": "150190130",
                "start_timestamp": None,
                "end_timestamp": None,
                "latitude": 50.350278,
                "longitude": 19.185556,
                "elevation": None,
                "name": "ŁAGISZA",
                "region": None,
                "river": "Przemsza (212)",
                "river_kilometer": 41.66,
                "gauge_zero": 260.124,
                "gauge_zero_datum": None,
            },
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
            "region": pl.String,
            "river": pl.String,
            "river_kilometer": pl.Float64,
            "gauge_zero": pl.Float64,
            "gauge_zero_datum": pl.String,
        },
        orient="row",
    )


@pytest.mark.remote
def test_imgw_hydrology_api_daily() -> None:
    """Test fetching of daily hydrology data."""
    request = ImgwHydrologyRequest(
        parameters=[("daily", "hydrology")],
        start="2010-08-01",
    ).filter_by_station_id("150190130")
    assert_frame_equal(request.df, _expected_station("daily"))
    values = request.values().all()
    df_expected = pl.DataFrame(
        [
            {
                "station_id": "150190130",
                "resolution": "daily",
                "dataset": "hydrology",
                "parameter": "discharge",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 3.62,
                "quality_flags": None,
            },
            {
                "station_id": "150190130",
                "resolution": "daily",
                "dataset": "hydrology",
                "parameter": "stage",
                "timestamp": dt.datetime(2010, 8, 1, tzinfo=ZoneInfo("UTC")),
                "value": 164.0,
                "quality_flags": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected)


@pytest.mark.remote
def test_imgw_hydrology_api_monthly() -> None:
    """Test fetching of monthly hydrology data."""
    request = ImgwHydrologyRequest(
        parameters=[("monthly", "hydrology")],
        start="2010-06-01",
    ).filter_by_station_id("150190130")
    assert_frame_equal(request.df, _expected_station("monthly"))
    values = request.values().all()
    df_expected_values = pl.DataFrame(
        [
            {
                "station_id": "150190130",
                "resolution": "monthly",
                "dataset": "hydrology",
                "parameter": "discharge_max",
                "timestamp": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 18.3,
                "quality_flags": None,
            },
            {
                "station_id": "150190130",
                "resolution": "monthly",
                "dataset": "hydrology",
                "parameter": "discharge_mean",
                "timestamp": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 8.36,
                "quality_flags": None,
            },
            {
                "station_id": "150190130",
                "resolution": "monthly",
                "dataset": "hydrology",
                "parameter": "discharge_min",
                "timestamp": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 2.75,
                "quality_flags": None,
            },
            {
                "station_id": "150190130",
                "resolution": "monthly",
                "dataset": "hydrology",
                "parameter": "stage_max",
                "timestamp": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 264.0,
                "quality_flags": None,
            },
            {
                "station_id": "150190130",
                "resolution": "monthly",
                "dataset": "hydrology",
                "parameter": "stage_mean",
                "timestamp": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 199.0,
                "quality_flags": None,
            },
            {
                "station_id": "150190130",
                "resolution": "monthly",
                "dataset": "hydrology",
                "parameter": "stage_min",
                "timestamp": dt.datetime(2010, 6, 1, tzinfo=ZoneInfo("UTC")),
                "value": 149.0,
                "quality_flags": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected_values)


@pytest.mark.remote
def test_imgw_hydrology_api_daily_consolidated_yearly_file() -> None:
    """IMGW consolidated daily hydrology into one zip per year from 2023 onwards.

    2023's zip uses a semicolon-separated, unquoted CSV export; 2024's zip wraps each
    row in a broken extra pair of quotes. This exercises both, via the hydrological-year
    shift that maps calendar 2023-11-01 into the "2024" file.
    """
    request = ImgwHydrologyRequest(
        parameters=[("daily", "hydrology")],
        start="2023-11-01",
        end="2023-11-01",
    ).filter_by_station_id("149180020")
    values = request.values().all()
    df_expected = pl.DataFrame(
        [
            {
                "station_id": "149180020",
                "resolution": "daily",
                "dataset": "hydrology",
                "parameter": "discharge",
                "timestamp": dt.datetime(2023, 11, 1, tzinfo=ZoneInfo("UTC")),
                "value": 25.4,
                "quality_flags": None,
            },
            {
                "station_id": "149180020",
                "resolution": "daily",
                "dataset": "hydrology",
                "parameter": "stage",
                "timestamp": dt.datetime(2023, 11, 1, tzinfo=ZoneInfo("UTC")),
                "value": 113.0,
                "quality_flags": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(values.df, df_expected)


@pytest.mark.remote
def test_imgw_hydrology_api_monthly_recent_export_formats() -> None:
    """2023 and 2024 monthly hydrology exports each use a different CSV quirk (see api.py)."""
    for start_date, expected_max, expected_mean, expected_min in [
        ("2023-06-01", 50.6, 17.7, 9.76),
        ("2024-06-01", 216.0, 36.7, 16.7),
    ]:
        request = ImgwHydrologyRequest(
            parameters=[("monthly", "hydrology")],
            start=start_date,
        ).filter_by_station_id("149180020")
        values = request.values().all()
        discharge = values.df.filter(pl.col("parameter").str.starts_with("discharge")).sort("parameter")
        assert discharge.get_column("value").to_list() == [expected_max, expected_mean, expected_min]


def test_imgw_hydrology_raises_a_failed_download_and_drops_a_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A download that failed for any reason but a 404 is raised, not dropped as a missing file (GH-2430)."""
    from types import SimpleNamespace  # noqa: PLC0415

    from wetterdienst import Settings  # noqa: PLC0415
    from wetterdienst.provider.imgw.hydrology import api as imgw_hydrology_api  # noqa: PLC0415
    from wetterdienst.provider.imgw.hydrology.api import ImgwHydrologyMetadata, ImgwHydrologyValues  # noqa: PLC0415

    missing = File(url="https://example.invalid/missing.zip", content=FileNotFoundError("missing.zip"), status=404)
    failed = File(url="https://example.invalid/a.zip", content=ConnectionError("503"), status=503)
    values = ImgwHydrologyValues.__new__(ImgwHydrologyValues)
    values.sr = SimpleNamespace(request=SimpleNamespace(settings=Settings()))  # ty: ignore[invalid-assignment]
    monkeypatch.setattr(values, "_get_urls", lambda _dataset: ["unused"])
    dataset = ImgwHydrologyMetadata.daily.hydrology
    monkeypatch.setattr(imgw_hydrology_api, "download_files", lambda **_kwargs: [missing, failed])
    with pytest.raises(DownloadError):
        values._collect_station_parameter_or_dataset("149180020", dataset)  # noqa: SLF001
    monkeypatch.setattr(imgw_hydrology_api, "download_files", lambda **_kwargs: [missing])
    assert values._collect_station_parameter_or_dataset("149180020", dataset).is_empty()  # noqa: SLF001


def test_imgw_hydrology_reads_a_headerless_daily_file_by_column_position(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the headerless daily file is read by the position of its columns, whichever polars reads it.

    The schema of the reader names the columns ``column_1`` and on, which polars 2 no longer does by itself.
    """
    from types import SimpleNamespace  # noqa: PLC0415
    from zipfile import ZipFile  # noqa: PLC0415

    from wetterdienst import Settings  # noqa: PLC0415
    from wetterdienst.provider.imgw.hydrology import api as imgw_hydrology_api  # noqa: PLC0415
    from wetterdienst.provider.imgw.hydrology.api import ImgwHydrologyMetadata, ImgwHydrologyValues  # noqa: PLC0415

    # station, name, river, hydrological year, month, day, stage, discharge, water temperature
    csv = "149180020,CHALUPKI,Odra,2023,03,15,141,12.5,9.9\n149180020,CHALUPKI,Odra,2023,03,16,150,13.5,9999\n"
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("codz_2023_03.csv", csv)
    buffer.seek(0)
    values = ImgwHydrologyValues.__new__(ImgwHydrologyValues)
    values.sr = SimpleNamespace(  # ty: ignore[invalid-assignment]
        request=SimpleNamespace(settings=Settings()),
        start=None,
        parameters=[],
        options=SimpleNamespace(drop_nulls_effective=False),
    )
    monkeypatch.setattr(values, "_get_urls", lambda _dataset: ["unused"])
    monkeypatch.setattr(
        imgw_hydrology_api,
        "download_files",
        lambda **_kwargs: [File(url="https://example.invalid/codz_2023.zip", content=buffer, status=200)],
    )
    df = values._collect_station_parameter_or_dataset("149180020", ImgwHydrologyMetadata.daily.hydrology)  # noqa: SLF001
    # 9999 is the missing temperature of the second day
    # the reader hands over the text of the cell, the core makes the number of it
    df = df.with_columns(pl.col("value").cast(pl.Float64, strict=False))
    assert df.sort("parameter", "timestamp").select("parameter", "value").rows() == [
        ("przepływ", 12.5),
        ("przepływ", 13.5),
        ("stan wody", 141.0),
        ("stan wody", 150.0),
        ("temperatura wody", 9.9),
        ("temperatura wody", None),
    ]


def _hydrology_urls(
    monkeypatch: pytest.MonkeyPatch, dataset_resolution: str, files: list[str], start: dt.datetime, end: dt.datetime
) -> list[str]:
    """Run the file selection of ``_get_urls`` on a listing, for a window of UTC instants."""
    from types import SimpleNamespace  # noqa: PLC0415

    from wetterdienst import Settings  # noqa: PLC0415
    from wetterdienst.provider.imgw.hydrology import api as imgw_hydrology_api  # noqa: PLC0415
    from wetterdienst.provider.imgw.hydrology.api import ImgwHydrologyMetadata, ImgwHydrologyValues  # noqa: PLC0415

    values = ImgwHydrologyValues.__new__(ImgwHydrologyValues)
    values.sr = SimpleNamespace(start=start, end=end, settings=Settings())  # ty: ignore[invalid-assignment]
    monkeypatch.setattr(imgw_hydrology_api, "list_files_for_interval", lambda *_args, **_kwargs: files)
    dataset = getattr(ImgwHydrologyMetadata, dataset_resolution).hydrology
    return values._get_urls(dataset)  # noqa: SLF001


def _utc(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=ZoneInfo("UTC"))


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        # codz_2023_03 is the third month of the hydrological year 2023, which starts in November: January 2023.
        # The file of the whole year starts on 2022-11-01
        (_utc(2023, 1, 15), _utc(2023, 1, 16), ["codz_2023.zip", "codz_2023_03.zip"]),
        # codz_2022_12 is October 2022, which ends at 2022-10-31 00:00: a window that touches it keeps it, one
        # that starts the next day does not (both ends of a period are in it)
        (_utc(2022, 10, 31), _utc(2022, 10, 31), ["codz_2022_12.zip"]),
        (_utc(2022, 11, 1), _utc(2022, 11, 1), ["codz_2023.zip", "codz_2023_01.zip"]),
        # the first two months of a hydrological year belong to the calendar year before it
        (_utc(2022, 12, 31), _utc(2023, 1, 1), ["codz_2023.zip", "codz_2023_02.zip", "codz_2023_03.zip"]),
        (_utc(2024, 1, 1), _utc(2024, 1, 2), []),
    ],
)
def test_imgw_hydrology_daily_files_are_selected_by_the_period_their_name_gives(
    monkeypatch: pytest.MonkeyPatch, start: dt.datetime, end: dt.datetime, expected: list[str]
) -> None:
    """Test that a daily file is kept when the hydrological months of its name overlap the window."""
    files = [
        f"https://example.invalid/{name}"
        for name in (
            "codz_2022_12.zip",
            "codz_2023.zip",
            "codz_2023_01.zip",
            "codz_2023_02.zip",
            "codz_2023_03.zip",
            "codz_2023_04.zip",
            "zjaw_2023.zip",
            "UWAGA.txt",
        )
    ]
    urls = _hydrology_urls(monkeypatch, "daily", files, start, end)
    assert [url.rsplit("/", 1)[-1] for url in urls] == expected


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        # mies_2023 is the hydrological year 2023, which starts on 2022-11-01
        (_utc(2022, 10, 31), _utc(2022, 10, 31), ["mies_2022.zip"]),
        (_utc(2023, 10, 31), _utc(2023, 10, 31), ["mies_2023.zip"]),
        (_utc(2023, 12, 1), _utc(2023, 12, 1), ["mies_2024.zip"]),
        (_utc(2022, 6, 1), _utc(2023, 2, 1), ["mies_2022.zip", "mies_2023.zip"]),
    ],
)
def test_imgw_hydrology_monthly_files_are_selected_by_the_hydrological_year(
    monkeypatch: pytest.MonkeyPatch, start: dt.datetime, end: dt.datetime, expected: list[str]
) -> None:
    """Test that a monthly file is kept when its hydrological year overlaps the window."""
    files = [f"https://example.invalid/mies_{year}.zip" for year in (2022, 2023, 2024)]
    urls = _hydrology_urls(monkeypatch, "monthly", files, start, end)
    assert [url.rsplit("/", 1)[-1] for url in urls] == expected


def test_imgw_hydrology_a_file_name_without_a_period_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a name the period cannot be read from is reported, not left out with its data."""
    files = ["https://example.invalid/mies_2023.zip", "https://example.invalid/mies_xx.zip"]
    with pytest.raises(ValueError, match=r"mies_xx\.zip"):
        _hydrology_urls(monkeypatch, "monthly", files, _utc(2023, 1, 1), _utc(2023, 2, 1))


_STATION_LIST_HEADER = (
    "LP.;Kod 9-znakowy;Nazwa stacji;Rzeka;Rok założenia;Szerokość geograficzna;Długość geograficzna;"
    "Rzędna zera wodowskazu;Kilometr biegu rzeki\r\n"
)


def _serve_station_list(monkeypatch: pytest.MonkeyPatch, rows: str) -> None:
    catalogue = _STATION_LIST_HEADER + rows
    monkeypatch.setattr(
        "wetterdienst.provider.imgw.hydrology.api.download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(catalogue.encode("utf8")), status=200),
    )


def test_imgw_hydrology_station_list_gives_the_river_its_kilometre_and_the_gauge_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the river, its kilometre and the gauge zero of the list are the columns wsv/pegel names (GH-3599).

    The kilometre is measured from the river's mouth and the gauge zero is in metres above sea level, negative on
    the Baltic coast; the founding year ("Rok założenia") is left out. Where the list leaves a field empty, the
    column is null, and it states no datum, so `gauge_zero_datum` is null.
    """
    _serve_station_list(
        monkeypatch,
        "1;149180010;Krzyżanowice;Odra (1);1927;49 59 37;18 17 14;184.806;713.04\r\n"
        "269;154160150;Darłowo;Morze Bałtyckie (0);1819;54 26 25;16 22 40;-4.904;\r\n"
        "270;154150060;Rościęcino;Parsęta (44);2024;54 06 55;15 36 26;;12.47\r\n"
        "271;153140010;Świnoujście;Morze Bałtyckie (0);1850;53 54 36;14 14 50;-5.1;0\r\n",
    )

    df = ImgwHydrologyRequest(parameters=[("daily", "hydrology")]).all().df

    assert df.select("station_id", "river", "river_kilometer", "gauge_zero", "gauge_zero_datum").rows() == [
        ("149180010", "Odra (1)", 713.04, 184.806, None),
        ("154160150", "Morze Bałtyckie (0)", None, -4.904, None),
        ("154150060", "Parsęta (44)", 12.47, None, None),
        ("153140010", "Morze Bałtyckie (0)", 0.0, -5.1, None),
    ]
    assert df.schema["river"] == pl.String
    assert df.schema["river_kilometer"] == pl.Float64
    assert df.schema["gauge_zero"] == pl.Float64
    assert df.schema["gauge_zero_datum"] == pl.String
    assert "founding_year" not in df.columns


def test_imgw_hydrology_station_list_reads_what_is_no_number_as_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a gauge zero or kilometre that is no number is null and does not fail the station list."""
    _serve_station_list(monkeypatch, "1;149180010;Krzyżanowice;Odra (1);1927;49 59 37;18 17 14;brak;713.04\r\n")

    df = ImgwHydrologyRequest(parameters=[("daily", "hydrology")]).all().df

    assert df.select("gauge_zero", "river_kilometer").rows() == [(None, 713.04)]
