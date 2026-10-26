# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for Météo-France SYNOP API."""

import gzip
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.provider.value_stubs import serve, stations_result
from wetterdienst import Options, Settings
from wetterdienst.exceptions import DownloadError, InvalidParameterError
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.meteofrance.synop import MeteoFranceSynopRequest
from wetterdienst.provider.meteofrance.synop import api as synop_api
from wetterdienst.util import archive

_PRECIPITATION = [
    "precipitation_amount_last_1h",
    "precipitation_amount_last_3h",
    "precipitation_amount_last_6h",
    "precipitation_amount_last_12h",
    "precipitation_amount_last_24h",
]


def _values(
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict[str, str]],
    parameters: list[str],
    *,
    drop_nulls: bool = True,
    year: int = 2024,
    end: datetime | None = None,
) -> pl.DataFrame:
    """Read rows through the reader as the columns of the source's file, empty where a row has none."""
    schema = list(synop_api._SYNOP_CSV_SCHEMA)  # noqa: SLF001
    lines = [";".join(schema)] + [";".join(row.get(column, "") for column in schema) for row in rows]
    serve(
        monkeypatch, synop_api, {f"/data/OBS/SYNOP/synop_{year}.csv.gz": gzip.compress("\n".join(lines).encode("utf8"))}
    )
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", parameter) for parameter in parameters],
        start=datetime(year, 1, 1, tzinfo=UTC),
        end=end or datetime(year, 1, 2, tzinfo=UTC),
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=drop_nulls),
    )
    return stations_result(request, "subdaily", "data", "07005").values().all().df.sort("timestamp")


def test_meteofrance_synop_api_a_file_that_unpacks_past_the_ceiling_is_a_download_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a gzip that unpacks to more than the ceiling is refused, not inflated by the table reader (GH-3340)."""
    monkeypatch.setattr(archive, "MAX_UNPACKED_BYTES", 100)
    rows = [{"geo_id_wmo": "07005", "validity_time": "2024-01-01T18:00:00Z", "rr1": "0.2"}] * 20
    with pytest.raises(DownloadError, match="unpacks to more than"):
        _values(monkeypatch, rows, ["precipitation_amount_last_1h"])


def test_meteofrance_synop_api_trace_of_precipitation_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the -0.1 of a trace is 0.0 in all five precipitation columns, and a reading is left as it is (GH-2674).

    The raw row is that of ABBEVILLE at 2024-01-01T18:00Z in synop_2024.csv.gz, widened to the five columns.
    The second row holds readings of 0.1 mm and above, which stay.
    """
    rows = [
        {
            "geo_id_wmo": "07005",
            "validity_time": "2024-01-01T18:00:00Z",
            "rr1": "-0.1",
            "rr3": "-0.1",
            "rr6": "-0.1",
            "rr12": "-0.1",
            "rr24": "-0.1",
        },
        {
            "geo_id_wmo": "07005",
            "validity_time": "2024-01-01T21:00:00Z",
            "rr1": "0.1",
            "rr3": "0.4",
            "rr6": "1.2",
            "rr12": "0.0",
            "rr24": "5.5",
        },
    ]
    df = _values(monkeypatch, rows, _PRECIPITATION)
    by_parameter = {
        str(parameter): group.get_column("value").to_list()
        for (parameter,), group in df.partition_by("parameter", as_dict=True).items()
    }
    assert by_parameter == {
        "precipitation_amount_last_1h": [0.0, 0.1],
        "precipitation_amount_last_3h": [0.0, 0.4],
        "precipitation_amount_last_6h": [0.0, 1.2],
        "precipitation_amount_last_12h": [0.0, 0.0],
        "precipitation_amount_last_24h": [0.0, 5.5],
    }


def test_meteofrance_synop_api_reads_the_maintained_yearly_file_not_the_stale_mirror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the yearly file is the one data.gouv.fr lists, which runs on past the mirror's end.

    `data/synchro_ftp/OBS/SYNOP/synop_2026.csv.gz` ended at 2026-09-08T21:00Z (last modified 2026-09-09) while
    `data/OBS/SYNOP/synop_2026.csv.gz`, the resource of the dataset, ended at 2026-10-25T21:00Z (both read on
    2026-10-26). The rows are those of PARIS-MONTSOURIS (07156) in the latter at 2026-09-09T00:00Z (t=288.25 K) and
    2026-10-25T21:00Z (t=283.65 K), the first and the last hours the mirror does not hold, moved to 07005. The stub
    answers for the maintained path only, so a read of the mirror fails.
    """
    rows = [
        {"geo_id_wmo": "07005", "validity_time": "2026-09-09T00:00:00Z", "t": "288.25"},
        {"geo_id_wmo": "07005", "validity_time": "2026-10-25T21:00:00Z", "t": "283.65"},
    ]
    df = _values(
        monkeypatch,
        rows,
        ["temperature_air_2m"],
        year=2026,
        end=datetime(2026, 10, 26, tzinfo=UTC),
    )
    assert df.get_column("timestamp").to_list() == [
        datetime(2026, 9, 9, 0, tzinfo=UTC),
        datetime(2026, 10, 25, 21, tzinfo=UTC),
    ]
    assert df.get_column("value").round(2).to_list() == [15.1, 10.5]


def test_meteofrance_synop_api_a_station_absent_from_the_file_is_the_empty_long_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a file that holds rows of other stations only is no rows for the station asked for (GH-2627)."""
    rows = [{"geo_id_wmo": "07015", "validity_time": "2024-01-01T18:00:00Z", "rr1": "0.2"}]
    df = _values(monkeypatch, rows, ["precipitation_amount_last_1h"])
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()


def test_meteofrance_synop_api_wind_is_named_for_its_ten_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that dd and ff come back as the 10-minute mean they are (GH-2733).

    The rows are the first two of Toulouse-Blagnac (07630) in synop_2024.csv.gz, 2024-01-01 00:00Z (dd=190, ff=2)
    and 03:00Z (dd=170, ff=1), moved to 07005. The hourly FF of 31069001 at those stamps is 2.4 and 1.4, which
    the source's ff cuts to the integer. The old names are not found in the dataset.
    """
    rows = [
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T00:00:00Z", "dd": "190", "ff": "2"},
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T03:00:00Z", "dd": "170", "ff": "1"},
    ]
    df = _values(monkeypatch, rows, ["wind_direction_mean_last_10min", "wind_speed_mean_last_10min"])
    by_parameter = {
        str(parameter): group.get_column("value").to_list()
        for (parameter,), group in df.partition_by("parameter", as_dict=True).items()
    }
    assert by_parameter == {"wind_direction_mean_last_10min": [190.0, 170.0], "wind_speed_mean_last_10min": [2.0, 1.0]}
    for old in ("wind_speed", "wind_direction"):
        with pytest.raises(InvalidParameterError):
            MeteoFranceSynopRequest(parameters=[("subdaily", "data", old)])


def test_meteofrance_synop_api_gust_is_named_for_its_ten_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that raf10 comes back as the gust of the last 10 minutes it is, no gust of the interval (GH-2836).

    The sheet says "raf10 rafales sur les 10 dernières minutes" beside "rafper rafales sur une période", and raf10
    is below rafper in 77 % of the 141873 pairs of synop_2024.csv.gz in which both are given. The rows are
    made after those of Toulouse-Blagnac (07630). The old name is not found in the dataset.
    """
    rows = [
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T00:00:00Z", "raf10": "4.1", "rafper": "6.2"},
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T03:00:00Z", "raf10": "3.0", "rafper": "3.0"},
    ]
    df = _values(monkeypatch, rows, ["wind_gust_max_last_10min"])
    assert df.get_column("parameter").unique().to_list() == ["wind_gust_max_last_10min"]
    assert df.get_column("value").to_list() == [4.1, 3.0]
    with pytest.raises(InvalidParameterError):
        MeteoFranceSynopRequest(parameters=[("subdaily", "data", "wind_gust_max")])


def test_meteofrance_synop_api_calm_wind_direction_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that dd=0 beside ff=0 has no direction, where 360 is north and the other directions stay (GH-2856).

    The rows are made after Toulouse-Blagnac (07630) in synop_2024.csv.gz: a calm (dd=0 beside ff=0, 3495 rows in
    the file, none with another ff), a light wind the integer ff cuts to 0 (dd=170, ff=0, 10925 rows) and north
    (dd=360). The row at 09:00 is a dd=0 beside ff=1, as Pamandzi writes it in 2012, which stays, as a 0 beside a
    wind that blows does in every provider (GH-3222). The zero of the calm keeps its text as the `raw` token (rows
    without a value are kept to see it), and ff=0 is a reading.
    """
    rows = [
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T00:00:00Z", "dd": "0", "ff": "0"},
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T03:00:00Z", "dd": "170", "ff": "0"},
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T06:00:00Z", "dd": "360", "ff": "3"},
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T09:00:00Z", "dd": "0", "ff": "1"},
    ]
    df = _values(monkeypatch, rows, ["wind_direction_mean_last_10min", "wind_speed_mean_last_10min"], drop_nulls=False)
    direction = df.filter(pl.col("parameter").eq("wind_direction_mean_last_10min"))
    assert direction.get_column("value").to_list() == [None, 170.0, 360.0, 0.0]
    assert direction.get_column("quality_flags").to_list() == ["raw:0", None, None, None]
    speed = df.filter(pl.col("parameter").eq("wind_speed_mean_last_10min"))
    assert speed.get_column("value").to_list() == [0.0, 0.0, 3.0, 1.0]
    assert speed.get_column("quality_flags").to_list() == [None, None, None, None]


def test_meteofrance_synop_api_dd_of_400_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the dd=400 of the 1996 file has no direction, where the directions around it stay (GH-2873).

    The rows are those of DUMONT D'URVILLE (89642) at 1996-04-03 06, 09, 12 and 15 h in synop_1996.csv.gz (dd=130, 130,
    400, 0 beside ff=3, 2, 1, 0), moved to 07005 and to 1996-01-01. The 400 keeps its text as the `raw` token, as the
    calm 0 beside it does (rows without a value are kept to see it).
    """
    rows = [
        {"geo_id_wmo": "07005", "validity_time": "1996-01-01T06:00:00Z", "dd": "130", "ff": "3"},
        {"geo_id_wmo": "07005", "validity_time": "1996-01-01T09:00:00Z", "dd": "130", "ff": "2"},
        {"geo_id_wmo": "07005", "validity_time": "1996-01-01T12:00:00Z", "dd": "400", "ff": "1"},
        {"geo_id_wmo": "07005", "validity_time": "1996-01-01T15:00:00Z", "dd": "0", "ff": "0"},
    ]
    df = _values(
        monkeypatch, rows, ["wind_direction_mean_last_10min", "wind_speed_mean_last_10min"], drop_nulls=False, year=1996
    )
    direction = df.filter(pl.col("parameter").eq("wind_direction_mean_last_10min")).sort("timestamp")
    assert direction.get_column("value").to_list() == [130.0, 130.0, None, None]
    assert direction.get_column("quality_flags").to_list() == [None, None, "raw:400", "raw:0"]
    speed = df.filter(pl.col("parameter").eq("wind_speed_mean_last_10min")).sort("timestamp")
    assert speed.get_column("value").to_list() == [3.0, 2.0, 1.0, 0.0]


def test_meteofrance_synop_api_obscured_sky_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that n=101 has no cloud cover, where a class of 0 to 100 percent keeps its value (GH-2674).

    The last row is that of CHASSIRON at 2024-01-03T06:00Z in synop_2024.csv.gz (n=101, nbas=9, vv=900), moved
    to 07005 at 09:00; the others are classes of the clear to the overcast sky.
    """
    rows = [
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T00:00:00Z", "n": "0"},
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T03:00:00Z", "n": "90"},
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T06:00:00Z", "n": "100"},
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T09:00:00Z", "n": "101", "nbas": "9", "vv": "900"},
    ]
    df = _values(monkeypatch, rows, ["cloud_cover_total"])
    assert df.get_column("timestamp").to_list() == [
        datetime(2024, 1, 1, 0, tzinfo=UTC),
        datetime(2024, 1, 1, 3, tzinfo=UTC),
        datetime(2024, 1, 1, 6, tzinfo=UTC),
    ]
    assert df.get_column("value").to_list() == [0.0, 0.9, 1.0]


@pytest.mark.remote
def test_meteofrance_synop_api_stations() -> None:
    """Test that station metadata can be retrieved and is complete."""
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", "temperature_air_2m")],
    ).filter_by_station_id("07005")
    df = request.df
    assert not df.is_empty()
    assert df.get_column("name").to_list() == ["ABBEVILLE"]


@pytest.mark.remote
def test_meteofrance_synop_api_values() -> None:
    """Test subdaily (3-hourly synop) values, including unit conversion from source Kelvin."""
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", "temperature_air_2m")],
        start=datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=datetime(2024, 1, 2, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("07005")
    df = next(request.values().query()).df
    values = df.get_column("value")
    assert values.is_not_null().sum() > 0
    # temperature is converted from Kelvin to Celsius, so should be within a plausible range
    assert values.drop_nulls().is_between(-50, 50).all()


@pytest.mark.remote
@pytest.mark.parametrize(
    "parameter",
    [
        "wind_speed_mean_last_10min",
        "wind_direction_mean_last_10min",
        "humidity_relative",
        "pressure_air_sea_level",
        "precipitation_amount_last_3h",
        "cloud_cover_total",
    ],
)
def test_meteofrance_synop_api_parameters(parameter: str) -> None:
    """Test that core parameters can be requested and yield data for a well-covered station."""
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", parameter)],
        start=datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=datetime(2024, 1, 3, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("07690")
    df = next(request.values().query()).df
    assert df.get_column("value").is_not_null().sum() > 0
