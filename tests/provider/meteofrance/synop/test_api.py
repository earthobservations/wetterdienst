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
    station_id: str = "07005",
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
    return stations_result(request, "subdaily", "data", station_id).values().all().df.sort("timestamp")


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


def test_meteofrance_synop_api_the_twelve_hour_extremes_are_celsius_at_06_and_18_utc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that tx12 and tn12 are offered, in degree Celsius, and that an empty field is no value (GH-3540).

    The rows are those of PARIS-MONTSOURIS (07156) in synop_2026.csv.gz (read 2026-10-28) at 2026-10-26T18:00Z,
    2026-10-27T06:00Z and 2026-10-27T18:00Z, moved to 07005 (`tx24` and `tn24` are empty for it in every row of
    2025 and 2026), with the 3-hourly step of 2026-10-27T12:00Z between them, which has none of the four.
    """
    rows = [
        {"geo_id_wmo": "07005", "validity_time": "2026-10-26T18:00:00Z", "tn12": "281.35", "tx12": "286.15"},
        {"geo_id_wmo": "07005", "validity_time": "2026-10-27T06:00:00Z", "tn12": "285.75", "tx12": "287.85"},
        {"geo_id_wmo": "07005", "validity_time": "2026-10-27T12:00:00Z", "t": "288.55"},
        {"geo_id_wmo": "07005", "validity_time": "2026-10-27T18:00:00Z", "tn12": "285.75", "tx12": "289.35"},
    ]
    df = _values(
        monkeypatch,
        rows,
        ["temperature_air_max_2m_last_12h", "temperature_air_min_2m_last_12h"],
        year=2026,
        end=datetime(2026, 10, 28, tzinfo=UTC),
    )
    by_parameter = {
        str(parameter): (group.get_column("timestamp").to_list(), group.get_column("value").round(2).to_list())
        for (parameter,), group in df.partition_by("parameter", as_dict=True).items()
    }
    assert by_parameter == {
        "temperature_air_max_2m_last_12h": (
            [
                datetime(2026, 10, 26, 18, tzinfo=UTC),
                datetime(2026, 10, 27, 6, tzinfo=UTC),
                datetime(2026, 10, 27, 18, tzinfo=UTC),
            ],
            [13.0, 14.7, 16.2],
        ),
        "temperature_air_min_2m_last_12h": (
            [
                datetime(2026, 10, 26, 18, tzinfo=UTC),
                datetime(2026, 10, 27, 6, tzinfo=UTC),
                datetime(2026, 10, 27, 18, tzinfo=UTC),
            ],
            [8.2, 12.6, 12.6],
        ),
    }


_COPIED_TN12 = [
    # CAYENNE-MATOURY (81405) at 2026-07-01T00:00Z: tx12 and tn12 are the same 303.75 K (30.6 C) beside t 298.55 K
    {"geo_id_wmo": "07005", "validity_time": "2024-01-01T00:00:00Z", "t": "298.55", "tn12": "303.75", "tx12": "303.75"},
    # PARIS-MONTSOURIS (07156) at 2026-10-27T06:00Z: the two differ, both stay
    {"geo_id_wmo": "07005", "validity_time": "2024-01-01T06:00:00Z", "t": "286.65", "tn12": "285.75", "tx12": "287.85"},
    # a tx12 with no tn12 beside it has nothing to be compared with
    {"geo_id_wmo": "07005", "validity_time": "2024-01-01T12:00:00Z", "tx12": "290.15"},
]


@pytest.mark.parametrize(
    "parameters",
    [["temperature_air_min_2m_last_12h"], ["temperature_air_min_2m_last_12h", "temperature_air_max_2m_last_12h"]],
)
def test_meteofrance_synop_api_a_tn12_that_copies_the_tx12_of_its_row_is_null_with_its_text(
    monkeypatch: pytest.MonkeyPatch, parameters: list[str]
) -> None:
    """Test that tn12 is null, with `raw:303.75`, where it is the text of the tx12 beside it, and tx12 stays (GH-3540).

    Cayenne-Matoury, Le Raizet and Lamentin write the maximum of the daytime into tn12 at some hours (1290 rows of the
    2026 file, 1116 of 2025). The copy is read from the tx12 column of the row whether tx12 is asked for or not.
    """
    df = _values(monkeypatch, _COPIED_TN12, parameters, drop_nulls=False)
    minimum = df.filter(pl.col("parameter") == "temperature_air_min_2m_last_12h")
    assert minimum.get_column("value").round(2).to_list() == [None, 12.6, None]
    assert minimum.get_column("quality_flags").to_list() == ["raw:303.75", None, None]
    if len(parameters) == 2:
        maximum = df.filter(pl.col("parameter") == "temperature_air_max_2m_last_12h")
        assert maximum.get_column("value").round(2).to_list() == [30.6, 14.7, 17.0]
        assert maximum.get_column("quality_flags").to_list() == [None, None, None]


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


def test_meteofrance_synop_api_a_reading_no_sensor_produced_is_null_with_its_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that pressure, temperature and rain beyond the records are null with the number the file wrote (GH-3135).

    The rows are those of the files of 1996 to 2005 (`pres` 11170 Pa at LA DESIRADE, `t` 369.15 K at 07117, `td` 358.95
    K at 61997, `rr1` 800 mm at 61976), moved to 07005 and to 2024. The first row is the edge of every bound, which
    stays: 50,000 and 85,000 Pa, 183.15 K, 600 mm; the second the other edge: 110,000 Pa, 333.15 K, 2,000 mm. The trace
    of -0.1 is still 0.0, and a rr6 of 805 mm and a rr24 of 999.4 mm are inside the records.
    """
    rows = [
        {
            "geo_id_wmo": "07005",
            "validity_time": "2024-01-01T00:00:00Z",
            "pres": "50000",
            "pmer": "85000",
            "t": "183.15",
            "td": "183.15",
            "rr1": "600.0",
            "rr3": "1200.0",
            "rr6": "805.0",
            "rr24": "999.4",
        },
        {
            "geo_id_wmo": "07005",
            "validity_time": "2024-01-01T03:00:00Z",
            "pres": "110000",
            "pmer": "110000",
            "t": "333.15",
            "td": "333.15",
            "rr1": "-0.1",
            "rr24": "2000.0",
        },
        {
            "geo_id_wmo": "07005",
            "validity_time": "2024-01-01T06:00:00Z",
            "pres": "11170",
            "pmer": "84990",
            "t": "369.15",
            "td": "358.95",
            "rr1": "800.0",
            "rr3": "1200.1",
            "rr6": "1200.1",
            "rr24": "2000.1",
        },
        {
            "geo_id_wmo": "07005",
            "validity_time": "2024-01-01T09:00:00Z",
            "pres": "110000.5",
            "pmer": "110000.5",
            "t": "183.1",
            "td": "333.2",
            "rr1": "-0.2",
        },
    ]
    parameters = [
        "pressure_air_site",
        "pressure_air_sea_level",
        "temperature_air_2m",
        "temperature_dew_point_2m",
        "precipitation_amount_last_1h",
        "precipitation_amount_last_3h",
        "precipitation_amount_last_6h",
        "precipitation_amount_last_24h",
    ]
    df = _values(monkeypatch, rows, parameters, drop_nulls=False)
    by_parameter = {
        str(parameter): group.sort("timestamp")
        for (parameter,), group in df.partition_by("parameter", as_dict=True).items()
    }

    def values(parameter: str) -> list[float | None]:
        return by_parameter[parameter].get_column("value").to_list()

    def raw(parameter: str) -> list[str | None]:
        return by_parameter[parameter].get_column("quality_flags").to_list()

    assert values("pressure_air_site") == [500.0, 1100.0, None, None]
    assert raw("pressure_air_site") == [None, None, "raw:11170", "raw:110000.5"]
    assert values("pressure_air_sea_level") == [850.0, 1100.0, None, None]
    assert raw("pressure_air_sea_level") == [None, None, "raw:84990", "raw:110000.5"]
    assert values("temperature_air_2m") == [-90.0, 60.0, None, None]
    assert raw("temperature_air_2m") == [None, None, "raw:369.15", "raw:183.1"]
    assert values("temperature_dew_point_2m") == [-90.0, 60.0, None, None]
    assert raw("temperature_dew_point_2m") == [None, None, "raw:358.95", "raw:333.2"]
    assert values("precipitation_amount_last_1h") == [600.0, 0.0, None, None]
    assert raw("precipitation_amount_last_1h") == [None, "raw:-0.1", "raw:800.0", "raw:-0.2"]
    assert values("precipitation_amount_last_3h") == [1200.0, None, None, None]
    assert raw("precipitation_amount_last_3h") == [None, None, "raw:1200.1", None]
    assert values("precipitation_amount_last_6h") == [805.0, None, None, None]
    assert raw("precipitation_amount_last_6h") == [None, None, "raw:1200.1", None]
    assert values("precipitation_amount_last_24h") == [999.4, 2000.0, None, None]
    assert raw("precipitation_amount_last_24h") == [None, None, "raw:2000.1", None]


@pytest.mark.parametrize(
    ("station", "kept"),
    [
        # Guadeloupe (LA DESIRADE, ST-BARTHELEMY, LE RAIZET), Martinique, Guyane and Mayotte (PAMANDZI)
        ("78890", False),
        ("78894", False),
        ("78897", False),
        ("78922", False),
        ("78925", False),
        ("81401", False),
        ("81405", False),
        ("81408", False),
        ("81415", False),
        ("67005", False),
        # the Iles Eparses (984): GLORIEUSES, JUAN DE NOVA, EUROPA, TROMELIN
        ("61968", False),
        ("61970", False),
        ("61972", False),
        ("61976", False),
        # Wallis-et-Futuna (986): HIHIFO, MAOPOOPO
        ("91753", False),
        ("91754", False),
        # French Polynesia (987): HIVA-OA, BORA-BORA, TAIARAPU-EST, FAAA, TAKAROA, HAO, MANGAREVA, RAPA (27.6 S)
        ("91925", False),
        ("91929", False),
        ("91936", False),
        ("91938", False),
        ("91943", False),
        ("91944", False),
        ("91948", False),
        ("91958", False),
        # La Reunion has frost at altitude, Saint-Pierre is at 47 degrees north, the mainland has frost, and the
        # southern territories (KERGUELEN, CROZET, DUMONT D'URVILLE) and New Caledonia (NOUMEA) are not in the rule
        ("61980", True),
        ("71805", True),
        ("07005", True),
        ("61998", True),
        ("61997", True),
        ("89642", True),
        ("91592", True),
    ],
)
def test_meteofrance_synop_api_a_temperature_below_zero_is_null_where_there_is_no_frost(
    monkeypatch: pytest.MonkeyPatch,
    station: str,
    kept: bool,  # noqa: FBT001
) -> None:
    """Test that a temperature below 0 C where there is no frost is null, at the stations named for it (GH-3135).

    The first row is that of MARIPASOULA (81415) at 2025-02-12T00:00Z in synop_2025.csv.gz (`td` 255.65 K beside `t`
    297.95 K) moved to the station of the case (the files hold no reading below 0 C at Wallis-et-Futuna and French
    Polynesia, where the case is the same row), the second the 0 C of the edge, which stays, as does any reading of
    another station.
    """
    rows = [
        {
            "geo_id_wmo": station,
            "validity_time": "2025-02-12T00:00:00Z",
            "t": "297.95",
            "td": "255.65",
            "tn24": "270.15",
            "tx24": "304.55",
        },
        {"geo_id_wmo": station, "validity_time": "2025-02-12T03:00:00Z", "t": "273.15", "td": "273.15"},
    ]
    parameters = [
        "temperature_air_2m",
        "temperature_dew_point_2m",
        "temperature_air_min_2m_last_24h",
        "temperature_air_max_2m_last_24h",
    ]
    df = _values(
        monkeypatch,
        rows,
        parameters,
        drop_nulls=False,
        year=2025,
        end=datetime(2025, 2, 13, tzinfo=UTC),
        station_id=station,
    )
    by_parameter = {
        str(parameter): group.sort("timestamp")
        for (parameter,), group in df.partition_by("parameter", as_dict=True).items()
    }
    assert by_parameter["temperature_air_2m"].get_column("value").to_list() == pytest.approx([24.8, 0.0])
    assert by_parameter["temperature_air_max_2m_last_24h"].get_column("value").to_list() == pytest.approx([31.4, None])
    dew_point = by_parameter["temperature_dew_point_2m"]
    minimum = by_parameter["temperature_air_min_2m_last_24h"]
    if kept:
        assert dew_point.get_column("value").to_list() == pytest.approx([-17.5, 0.0])
        assert minimum.get_column("value").to_list() == pytest.approx([-3.0, None])
    else:
        assert dew_point.get_column("value").to_list() == [None, 0.0]
        assert dew_point.get_column("quality_flags").to_list() == ["raw:255.65", None]
        assert minimum.get_column("value").to_list() == [None, None]
        assert minimum.get_column("quality_flags").to_list() == ["raw:270.15", None]


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
def test_meteofrance_synop_api_the_twelve_hour_extremes_of_paris() -> None:
    """Test that Paris-Montsouris, which reports no tx24 and tn24, has tx12 and tn12 at 06 and 18 UTC (GH-3540)."""
    request = MeteoFranceSynopRequest(
        parameters=[
            ("subdaily", "data", "temperature_air_max_2m_last_12h"),
            ("subdaily", "data", "temperature_air_min_2m_last_12h"),
        ],
        start=datetime(2026, 10, 19, tzinfo=ZoneInfo("UTC")),
        end=datetime(2026, 10, 26, 23, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("07156")
    df = next(request.values().query()).df.drop_nulls("value")
    # a station and stamp may be in the file more than once, so the stamps are counted, not the rows
    wide = (
        df.group_by("timestamp", "parameter")
        .agg(pl.col("value").first())
        .pivot(on="parameter", index="timestamp", values="value")
        .sort("timestamp")
    )
    # 8 days of two reports a day
    assert wide.height == 16
    assert set(wide.get_column("timestamp").dt.hour().to_list()) == {6, 18}
    assert wide.get_column("temperature_air_max_2m_last_12h").is_between(-5, 35).all()
    assert wide.get_column("temperature_air_min_2m_last_12h").is_between(-5, 35).all()
    assert (wide["temperature_air_max_2m_last_12h"] >= wide["temperature_air_min_2m_last_12h"]).all()
    # the values of the file at 2026-10-26T18:00Z: tx12 286.15 K, tn12 281.35 K
    last = wide.filter(pl.col("timestamp") == datetime(2026, 10, 26, 18, tzinfo=UTC)).to_dicts()[0]
    assert round(last["temperature_air_max_2m_last_12h"], 2) == 13.0


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
