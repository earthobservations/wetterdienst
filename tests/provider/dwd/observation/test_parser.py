# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD historical climate data parsing."""

import datetime as dt
import logging
import re
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from fsspec.implementations.http import HTTPFileSystem
from fsspec.implementations.zip import ZipFileSystem
from polars.testing import assert_frame_equal

from wetterdienst import Period
from wetterdienst.model.metadata import DatasetModel
from wetterdienst.model.quality_flags import join_quality_flags, raw_column
from wetterdienst.provider.dwd.observation import DwdObservationMetadata
from wetterdienst.provider.dwd.observation.parser import (
    parse_climate_observations_data,
)
from wetterdienst.util.network import File


@pytest.mark.remote
def test_parse_dwd_data() -> None:
    """Test parsing of DWD historical climate data."""
    url = (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
        "climate/daily/kl/historical/tageswerte_KL_00001_19370101_19860630_hist.zip"
    )
    httpfs = HTTPFileSystem()
    payload = BytesIO(httpfs.cat(url))
    filename = "produkt_klima_tag_19370101_19860630_00001.txt"
    zfs = ZipFileSystem(payload)
    product_payload = zfs.cat(filename)
    file = File(
        url=url,
        content=BytesIO(product_payload),
        status=200,
    )
    given_df = parse_climate_observations_data(
        files=[file],
        dataset=DwdObservationMetadata.daily.climate_summary,
        period=Period.HISTORICAL,
    ).collect()
    expected_df = pl.DataFrame(
        {
            "station_id": ["1", "1"],
            "timestamp": [
                dt.datetime(1937, 1, 1, tzinfo=ZoneInfo("UTC")),
                dt.datetime(1986, 6, 30, tzinfo=ZoneInfo("UTC")),
            ],
            "qn_3": [None, None],
            "fx": [None, None],
            "fm": [None, None],
            "qn_4": ["5", "10"],
            "rsk": ["0.0", "0.0"],
            "rskf": ["0", "0"],
            "sdk": [None, None],
            "shk_tag": ["0", "0"],
            "nm": ["6.3", "0.3"],
            "vpm": [None, "13.9"],
            "pm": [None, None],
            "tmk": ["-0.5", "19.8"],
            "upm": [None, "60.00"],
            "txk": ["2.5", "24.8"],
            "tnk": ["-1.6", "14.4"],
            "tgk": [None, None],
            # the text of a mapped sentinel, `-999`, is kept beside the null it became (GH-2759)
            "fm__raw": ["-999", "-999"],
            "fx__raw": ["-999", "-999"],
            "nm__raw": [None, None],
            "pm__raw": ["-999", "-999"],
            "rsk__raw": [None, None],
            "rskf__raw": [None, None],
            "sdk__raw": ["-999", "-999"],
            "shk_tag__raw": [None, None],
            "tgk__raw": ["-999", "-999"],
            "tmk__raw": [None, None],
            "tnk__raw": [None, None],
            "txk__raw": [None, None],
            "upm__raw": ["-999", None],
            "vpm__raw": ["-999", None],
        },
        schema={
            "station_id": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "qn_3": pl.String,
            "fx": pl.String,
            "fm": pl.String,
            "qn_4": pl.String,
            "rsk": pl.String,
            "rskf": pl.String,
            "sdk": pl.String,
            "shk_tag": pl.String,
            "nm": pl.String,
            "vpm": pl.String,
            "pm": pl.String,
            "tmk": pl.String,
            "upm": pl.String,
            "txk": pl.String,
            "tnk": pl.String,
            "tgk": pl.String,
            "fm__raw": pl.String,
            "fx__raw": pl.String,
            "nm__raw": pl.String,
            "pm__raw": pl.String,
            "rsk__raw": pl.String,
            "rskf__raw": pl.String,
            "sdk__raw": pl.String,
            "shk_tag__raw": pl.String,
            "tgk__raw": pl.String,
            "tmk__raw": pl.String,
            "tnk__raw": pl.String,
            "txk__raw": pl.String,
            "upm__raw": pl.String,
            "vpm__raw": pl.String,
        },
        orient="col",
    )
    assert_frame_equal(
        given_df[[0, -1], :],
        expected_df,
    )


@pytest.mark.parametrize(
    ("dataset", "column", "payload"),
    [
        (
            DwdObservationMetadata.hourly.visibility,
            "v_vv_i",
            (
                "STATIONS_ID;MESS_DATUM;QN_8;V_VV_I;V_VV;eor\n"
                "  96;2025020800;    3;   P;  18770;eor\n"
                "  96;2025020801;    3;   I;  23000;eor\n"
                "  96;2025020802;    3;    ;   -999;eor\n"
            ),
        ),
        (
            DwdObservationMetadata.hourly.cloudiness,
            "v_n_i",
            (
                "STATIONS_ID;MESS_DATUM;QN_8;V_N_I;V_N;eor\n"
                "  96;2025020800;    3;   P;      7;eor\n"
                "  96;2025020801;    3;   I;      8;eor\n"
                "  96;2025020802;    3;    ;   -999;eor\n"
            ),
        ),
    ],
)
def test_parse_dwd_data_decodes_measurement_method(dataset: DatasetModel, column: str, payload: str) -> None:
    """Test that the letter-coded measurement method indicators are decoded rather than dropped.

    DWD writes these as `P` (human person) and `I` (instrument) in files that are otherwise
    numeric. The value column is Float64, so a letter has nowhere to go: both parameters were
    declared but silently dropped, and a request for them returned nothing at all.

    They stay text here because DWD pads its fields with spaces, so every data column is read as
    text and cast to Float64 only at the very end -- a numeric column would not stack with its
    neighbours in `_tidy_up_df`.
    """
    file = File(url="", content=BytesIO(payload.encode("utf8")), status=200)
    df = parse_climate_observations_data(files=[file], dataset=dataset, period=Period.RECENT).collect()
    assert df.get_column(column).to_list() == ["1", "2", None]
    assert df.schema[column] == pl.String


def test_daily_soil_temperature_declares_the_columns_the_file_has() -> None:
    """Test that every parameter of daily soil temperature is a column of DWD's product file.

    The files (recent and historical) carry the depths 2, 5, 10, 20 and 50 cm and nothing deeper;
    the dataset sheet lists `V_TE002M` to `V_TE050M`. A 100 cm column was declared once, and a
    request for it succeeded and returned no rows (GH-2700).
    """
    payload = (
        "STATIONS_ID;MESS_DATUM;QN_2;V_TE002M;V_TE005M;V_TE010M;V_TE020M;V_TE050M;eor\n"
        "      44;20250101;    3;   2.0;   2.1;   2.5;   3.0;   4.0;eor\n"
    )
    dataset = DwdObservationMetadata.daily.temperature_soil
    file = File(url="", content=BytesIO(payload.encode("utf8")), status=200)
    df = parse_climate_observations_data(files=[file], dataset=dataset, period=Period.RECENT).collect()
    # `<column>__raw` keeps the text of a mapped sentinel beside its null (GH-2759)
    in_file = {c for c in df.columns if c not in {"station_id", "timestamp"} and not c.endswith("__raw")}
    assert {parameter.name_original for parameter in dataset.parameters} == in_file


def test_parse_dwd_data_encodes_true_local_time_offset() -> None:
    """Test that true local time becomes its distance from the record's own timestamp.

    Solar records are stamped with the UTC instant of a whole true-solar-time hour, so the two
    timestamps sit apart by the solar correction. Taking that here is the whole point: `mess_datum`
    is rounded to the hour later on, and the rounding is what would discard it.
    """
    payload = (
        "STATIONS_ID;MESS_DATUM;QN_592;FG_LBERG;MESS_DATUM_WOZ;eor\n"
        # February, near the equation of time's minimum
        "  183;2023021005:20;    1;      0;2023021006:00;eor\n"
        # November, near its maximum -- same station, half an hour further ahead
        "  183;2023111004:50;    1;      0;2023111006:00;eor\n"
    )
    file = File(url="", content=BytesIO(payload.encode("utf8")), status=200)
    df = parse_climate_observations_data(
        files=[file],
        dataset=DwdObservationMetadata.hourly.solar,
        period=Period.HISTORICAL,
    ).collect()
    assert df.get_column("mess_datum_woz").to_list() == ["40", "70"]


SOLAR_HEADER = "STATIONS_ID;MESS_DATUM;QN_592;ATMO_LBERG;FD_LBERG;FG_LBERG;SD_LBERG;ZENIT;MESS_DATUM_WOZ;eor\n"

# Frankfurt/Main (01420), 2022-08-17, as DWD wrote it: the rows 1091 to 1107 of
# produkt_st_stunde_20220508_20260930_01420.txt. The minute that ends the hour falls from :30 to :29 at 13:29, so that
# 12:30 and 13:29 are both nearest to 13:00 (GH-3938)
FRANKFURT_2022_08_17 = """\
       1420;2022081709:30;    1;  144.0;   42.0;   43.0;   0;    47.70;2022081710:00;eor
       1420;2022081710:30;    1;  142.0;  109.0;  111.0;   0;    41.02;2022081711:00;eor
       1420;2022081711:30;    1;  144.0;   80.0;   87.0;   2;    37.19;2022081712:00;eor
       1420;2022081712:30;    1;  139.0;  136.0;  218.0;  39;    37.21;2022081713:00;eor
       1420;2022081713:29;    1;  142.0;  112.0;  182.0;  48;    41.06;2022081714:00;eor
       1420;2022081714:29;    1;  141.0;  110.0;  209.0;  54;    47.75;2022081715:00;eor
       1420;2022081715:29;    1;  136.0;   61.0;  180.0;  60;    56.17;2022081716:00;eor
       1420;2022081716:29;    1;  136.0;   41.0;  140.0;  60;    65.47;2022081717:00;eor
       1420;2022081717:29;    1;  142.0;   47.0;   72.0;  60;    75.09;2022081718:00;eor
       1420;2022081718:29;    1;  140.0;   18.0;   24.0;  52;    84.61;2022081719:00;eor
       1420;2022081719:29;    1;  139.0;    1.0;    1.0;   0;    93.66;2022081720:00;eor
       1420;2022081720:29;    1;  138.0;    0.0;    0.0;   0;   101.86;2022081721:00;eor
       1420;2022081721:29;    1;  133.0;    0.0;    0.0;   0;   108.73;2022081722:00;eor
       1420;2022081722:29;    1;  136.0;    0.0;    0.0;   0;   113.76;2022081723:00;eor
       1420;2022081723:29;    1;  137.0;    0.0;    0.0;   0;   116.45;2022081800:00;eor
       1420;2022081801:29;    1;  140.0;    0.0;    0.0;   0;   113.80;2022081802:00;eor
       1420;2022081802:29;    1;  140.0;    0.0;    0.0;   0;   108.79;2022081803:00;eor
"""

# Hamburg-Fuhlsbuettel (01975), 2005-03-11: the rows 1662 to 1682 of produkt_st_stunde_20050101_20260930_01975.txt. The
# minute is :30 until 13:30 and :29 from 14:29, so that 13:30 and 14:29 are both nearest to 14:00. The minute crosses
# :30 in the same way in January or March of every year of this file, 22 times, and DWD's Frankfurt file does it 7 times
HAMBURG_2005_03_11 = """\
       1975;2005031104:30;    1;  116.0;    0.0;    0.0;   0;   106.16;2005031105:00;eor
       1975;2005031105:30;    1;  116.0;    0.0;    0.0;   0;    97.40;2005031106:00;eor
       1975;2005031106:30;    1;  117.0;    0.0;    0.0;   0;    88.52;2005031107:00;eor
       1975;2005031107:30;    1;  117.0;    2.0;    3.0;   0;    79.91;2005031108:00;eor
       1975;2005031108:30;    1;  117.0;    8.0;    8.0;   0;    71.98;2005031109:00;eor
       1975;2005031109:30;    1;  116.0;   14.0;   14.0;   0;    65.24;2005031110:00;eor
       1975;2005031110:30;    1;  117.0;   17.0;   17.0;   0;    60.25;2005031111:00;eor
       1975;2005031111:30;    1;  118.0;   14.0;   14.0;   0;    57.56;2005031112:00;eor
       1975;2005031112:30;    1;  119.0;   16.0;   16.0;   0;    57.54;2005031113:00;eor
       1975;2005031113:30;    1;  119.0;   21.0;   21.0;   0;    60.20;2005031114:00;eor
       1975;2005031114:29;    1;  114.0;   45.0;   46.0;   4;    65.17;2005031115:00;eor
       1975;2005031115:29;    1;   99.0;   50.0;   69.0;  28;    71.88;2005031116:00;eor
       1975;2005031116:29;    1;  102.0;   34.0;   45.0;  23;    79.78;2005031117:00;eor
       1975;2005031117:29;    1;  111.0;    8.0;    8.0;   0;    88.37;2005031118:00;eor
       1975;2005031118:29;    1;  109.0;    0.0;    0.0;   0;    97.23;2005031119:00;eor
       1975;2005031119:29;    1;  109.0;    0.0;    0.0;   0;   105.96;2005031120:00;eor
       1975;2005031120:29;    1;  111.0;    0.0;    0.0;   0;   114.11;2005031121:00;eor
       1975;2005031121:29;    1;  110.0;    0.0;    0.0;   0;   121.17;2005031122:00;eor
       1975;2005031122:29;    1;  103.0;    0.0;    0.0;   0;   126.48;2005031123:00;eor
       1975;2005031123:29;    1;   98.0;    0.0;    0.0;   0;   129.37;2005031200:00;eor
       1975;2005031200:29;    1;  109.0;    0.0;    0.0;   0;   129.35;2005031201:00;eor
"""


def _parse_solar(rows: str) -> pl.DataFrame:
    """Parse the rows of a station's hourly solar file, as the library does."""
    file = File(
        url="https://example.invalid/solar.zip", content=BytesIO((SOLAR_HEADER + rows).encode("utf8")), status=200
    )
    return parse_climate_observations_data(
        files=[file], dataset=DwdObservationMetadata.hourly.solar, period=Period.HISTORICAL
    ).collect()


def _solar_rows(stamps: list[str], station: str = "1420") -> str:
    """Write rows of the file for the raw stamps (`YYYYMMDDHH:MM`), the global radiation of each being its number.

    MESS_DATUM_WOZ is the whole hour after the raw stamp, as in DWD's files.
    """
    lines = []
    for number, stamp in enumerate(stamps, 1):
        woz = dt.datetime.strptime(stamp, "%Y%m%d%H:%M").replace(minute=0) + dt.timedelta(hours=1)  # noqa: DTZ007
        lines.append(
            f"{station:>11};{stamp};    1;  100.0;    0.0;{number:>7}.0;   0;    50.00;{woz:%Y%m%d%H:%M};eor\n"
        )
    return "".join(lines)


def _stamps(day: str, start: int, minute: int, count: int) -> list[str]:
    """Give `count` raw stamps an hour apart from `start` o'clock of `day` (`YYYYMMDD`), all at the same minute."""
    return [f"{day}{start + hour:02d}:{minute:02d}" for hour in range(count)]


def test_solar_hourly_gives_each_frankfurt_hour_its_own_stamp() -> None:
    """Test that 12:30 and 13:29 of Frankfurt, which round to the same hour, each keep a row (GH-3938).

    The two rows (218 and 182 J/cm2) were both stamped 13:00 and only 218 was served, which left 14:00 with
    nothing beside it. The rows lead in with the hours that end at :30, which, being as near to the hour before as to
    the hour after, are the ones that move: back by one hour, up to 12:30 at 12:00, so that 13:29 keeps 13:00.
    """
    df = _parse_solar(FRANKFURT_2022_08_17)
    assert df.height == 17
    assert df.get_column("timestamp").is_unique().all()
    served = dict(
        zip(df.get_column("fg_lberg").cast(pl.Float64).to_list(), df.get_column("timestamp").to_list(), strict=True)
    )
    assert served[218.0] == dt.datetime(2022, 8, 17, 12, tzinfo=ZoneInfo("UTC"))
    assert served[182.0] == dt.datetime(2022, 8, 17, 13, tzinfo=ZoneInfo("UTC"))
    # 23:29 and 01:29 keep the 23:00 and 01:00 that they are nearest to, with 00:00 free between them
    assert df.get_column("timestamp").dt.hour().to_list() == [9, 10, 11, 12, *range(13, 24), 1, 2]


def test_solar_hourly_gives_each_hamburg_hour_its_own_stamp() -> None:
    """Test that the rows of Hamburg, whose minute falls from :30 to :29, are each stamped once (GH-3938).

    13:30 and 14:29 are both nearest to 14:00. The ten rows that end at :30 lead to the collision, and the eleven that
    end at :29 follow it up to 00:29 (00:00, the day after), so the ten move back by one hour, which is fewer than the
    eleven that would move on, and each lies 30 min from its raw end, as near as before.
    """
    df = _parse_solar(HAMBURG_2005_03_11)
    assert df.height == 21
    assert df.get_column("timestamp").is_unique().all()
    assert df.get_column("timestamp").dt.hour().to_list() == [*range(4, 24), 0]
    # the global radiation of 13:30 (21) is at 13:00 and that of 14:29 (46) at 14:00: neither is lost or doubled
    served = dict(
        zip(
            df.get_column("fg_lberg").cast(pl.Float64).to_list(),
            df.get_column("timestamp").dt.hour().to_list(),
            strict=True,
        )
    )
    assert served[21.0] == 13
    assert served[46.0] == 14


@pytest.mark.parametrize(
    ("stamps", "hours"),
    [
        pytest.param(
            [*_stamps("20220817", 0, 22, 5), *_stamps("20220817", 5, 41, 3)],
            [0, 1, 2, 3, 4, 6, 7, 8],
            id="no collision: each at the hour it ends nearest to",
        ),
        pytest.param(
            # 12:30 and 13:29 are both nearest to 13:00; 10:20 leaves 12:00 free, and 14:29 and 15:29 follow 13:29
            ["2022081710:20", "2022081712:30", "2022081713:29", "2022081714:29", "2022081715:29"],
            [10, 12, 13, 14, 15],
            id="the free hour is before: the earlier row moves back, one row",
        ),
        pytest.param(
            # 15:20 leaves 14:00 free, and 10:30 to 12:30 lead up to 13:29
            ["2022081710:30", "2022081711:30", "2022081712:30", "2022081713:29", "2022081715:20"],
            [11, 12, 13, 14, 15],
            id="the free hour is after: the later row moves on, one row",
        ),
        pytest.param(
            # as near as it gets either way (40 + 20 min against 20 + 40 min), and one row moves either way: the later
            ["2022081712:40", "2022081713:20"],
            [13, 14],
            id="a tie goes to the later stamps",
        ),
    ],
)
def test_solar_hours_move_the_fewest_rows_to_the_nearest_free_hour(stamps: list[str], hours: list[int]) -> None:
    """Test the rule that gives two source hours that end in one clock hour a stamp each (GH-3938)."""
    df = _parse_solar(_solar_rows(stamps))
    assert df.height == len(stamps)
    assert df.get_column("timestamp").is_unique().all()
    assert df.get_column("timestamp").dt.hour().to_list() == hours


def test_solar_hours_move_the_shorter_run_of_a_collision() -> None:
    """Test that a collision at the end of a long run of :30 stamps moves the rows after it, not the run (GH-3938).

    As in the Frankfurt file for 2022: the minute is :30 for 40 hours (nearest to the hour after, as near as to the
    hour before) and then :29 for 8 hours. The 40 rows keep the hours that rounding gave them, and the 8 follow them
    an hour on, each 31 min from the raw end instead of 29, so that 8 stamps change and not 40.
    """
    stamps = [*_stamps("20220815", 0, 30, 24), *_stamps("20220816", 0, 30, 16), *_stamps("20220816", 16, 29, 8)]
    df = _parse_solar(_solar_rows(stamps))
    assert df.height == 48
    assert df.get_column("timestamp").is_unique().all()
    origin = dt.datetime(2022, 8, 15, tzinfo=ZoneInfo("UTC"))
    served = [int((timestamp - origin).total_seconds() // 3600) for timestamp in df.get_column("timestamp")]
    assert served == [*range(1, 41), *range(41, 49)]


def test_solar_hourly_says_when_a_row_has_no_free_hour_near_it(caplog: pytest.LogCaptureFixture) -> None:
    """Test that rows that cannot get an hour within one of their own are kept, apart, and a warning says so (GH-3938).

    Four hours that all end between 12:30 and 12:45 are nearest to 13:00, and within an hour of it are 12:00, 13:00
    and 14:00, which are three. They are stamped the hour after the one before them, as far as it needs to be, and
    none is dropped.
    """
    stamps = ["2022081712:30", "2022081712:35", "2022081712:40", "2022081712:45"]
    with caplog.at_level(logging.WARNING):
        df = _parse_solar(_solar_rows(stamps))
    assert df.get_column("fg_lberg").cast(pl.Float64).to_list() == [1.0, 2.0, 3.0, 4.0]
    assert df.get_column("timestamp").dt.hour().to_list() == [13, 14, 15, 16]
    assert "3 source hour(s) of solar.zip" in caplog.text
    assert "no row is lost" in caplog.text


def test_solar_hourly_keeps_the_true_local_time_of_a_moved_row() -> None:
    """Test that `true_local_time_offset` stays the minutes from the raw stamp to MESS_DATUM_WOZ for a moved row.

    The offset is taken from the raw stamps before the hour is assigned: 12:30 to 13:00 WOZ is 30 min, as 60 minus
    the raw minute, whatever hour the row is served at (12:00 after it was moved) (GH-3938).
    """
    df = _parse_solar(FRANKFURT_2022_08_17)
    offsets = dict(
        zip(
            df.get_column("fg_lberg").cast(pl.Float64).to_list(), df.get_column("mess_datum_woz").to_list(), strict=True
        )
    )
    assert offsets[218.0] == "30"
    assert offsets[182.0] == "31"
    assert df.get_column("mess_datum_woz").cast(pl.Int64).to_list() == [30] * 4 + [31] * 13


def test_solar_hourly_assigns_the_hours_of_each_station_apart() -> None:
    """Test that two stations in one file do not take each other's hours (GH-3938).

    12:30 and 13:29 are 59 min apart: 12:00 and 13:00 keep them nearer to their ends than 13:00 and 14:00 do.
    """
    stamps = ["2022081712:30", "2022081713:29"]
    df = _parse_solar(_solar_rows(stamps, "1420") + _solar_rows(stamps, "1975"))
    assert df.height == 4
    for station in ("1420", "1975"):
        assert df.filter(pl.col("station_id") == station).get_column("timestamp").dt.hour().to_list() == [12, 13]


def test_parse_dwd_data_reports_unknown_true_local_time(caplog: pytest.LogCaptureFixture) -> None:
    """Test that a true local time that no longer parses is reported rather than quietly nulled.

    A format change would otherwise turn every value null without a word, leaving a parameter that
    is declared and answers with nothing -- the failure this area exists to prevent.
    """
    payload = (
        "STATIONS_ID;MESS_DATUM;QN_592;FG_LBERG;MESS_DATUM_WOZ;eor\n"
        "  183;2023021005:20;    1;      0;2023-02-10T06:00:00;eor\n"
    )
    file = File(url="", content=BytesIO(payload.encode("utf8")), status=200)
    with caplog.at_level(logging.WARNING):
        df = parse_climate_observations_data(
            files=[file],
            dataset=DwdObservationMetadata.hourly.solar,
            period=Period.HISTORICAL,
        ).collect()
    assert df.get_column("mess_datum_woz").to_list() == [None]
    assert "mess_datum_woz" in caplog.text
    assert "2023-02-10T06:00:00" in caplog.text


def test_parse_dwd_data_drops_obscured_sky_cloud_cover() -> None:
    """Test that -1 in the hourly cloud cover and cloud type fields becomes null.

    DWD writes -1 where the sky could not be seen at all, SYNOP's N = 9. It is a statement that no
    amount could be given, not an amount: left alone it is read as -1 eighths and converts to
    -0.125 of the sky. `v_sN_cs` beside it writes the same -1 for a cloud *type*, which no DWD
    description names and which sits beside an obscured cover in 2,633 of 2,641 hours (GH-3772), so
    that one is null too, with the text DWD wrote kept in `v_s1_cs__raw`.
    """
    payload = (
        "STATIONS_ID;MESS_DATUM;QN_8;V_N_I;V_N;V_S1_CS;V_S1_CSA;V_S1_HHS;V_S1_NS;eor\n"
        "    3;1994010100;    5;   I;  -1;      -1;      -1;    -999;      -1;eor\n"
        "    3;1994010101;    5;   I;   7;       6;      SC;     600;       4;eor\n"
    )
    file = File(url="", content=BytesIO(payload.encode("utf8")), status=200)
    df = parse_climate_observations_data(
        files=[file],
        dataset=DwdObservationMetadata.hourly.cloud_type,
        period=Period.HISTORICAL,
    ).collect()
    assert df.get_column("v_n").to_list() == [None, "7"]
    assert df.get_column("v_s1_ns").to_list() == [None, "4"]
    assert df.get_column("v_s1_cs").to_list() == [None, "6"]
    assert df.get_column("v_s1_cs__raw").to_list() == ["-1", None]


def test_parse_dwd_data_nulls_the_cloud_type_minus_one_beside_a_layer_that_was_seen() -> None:
    """Test that the cloud type -1 is null in every layer, also where the cover beside it is an amount (GH-3772).

    The rows are 2003-03-23 09:00 of station 02014 (stundenwerte_CS_02014_19490101_20251231_hist.zip, read
    2026-11-03), one of the 8 of 2,641 hours with a type of -1 beside a first layer that was seen, and the hour
    before it. The -1 in the second layer of the later row is made up (the file has none there). The text DWD wrote
    stays in `<column>__raw`; the letters `V_S1_CSA` beside the type are dropped.
    """
    payload = (
        "STATIONS_ID;MESS_DATUM;QN_8; V_N;V_N_I;V_S1_CS;V_S1_CSA;V_S1_HHS;V_S1_NS;V_S2_CS;V_S2_CSA;V_S2_HHS;V_S2_NS;"
        "V_S3_CS;V_S3_CSA;V_S3_HHS;V_S3_NS;V_S4_CS;V_S4_CSA;V_S4_HHS;V_S4_NS;eor\n"
        "       2014;2003032308;    1;   1;   P;   0;  CI;  7500;   1;-999;-999;  -999;-999;"
        "-999;-999;  -999;-999;-999;-999;  -999;-999;eor\n"
        "       2014;2003032309;    1;   1;   P;  -1;  -1;  7500;   1;  -1;  -1;  -999;-999;"
        "-999;-999;  -999;-999;-999;-999;  -999;-999;eor\n"
    )
    file = File(url="", content=BytesIO(payload.encode("utf8")), status=200)
    df = parse_climate_observations_data(
        files=[file],
        dataset=DwdObservationMetadata.hourly.cloud_type,
        period=Period.HISTORICAL,
    ).collect()
    assert df.get_column("v_s1_cs").to_list() == ["0", None]
    assert df.get_column("v_s1_cs__raw").to_list() == [None, "-1"]
    # the second layer is held to it too
    assert df.get_column("v_s2_cs").to_list() == [None, None]
    assert df.get_column("v_s2_cs__raw").to_list() == ["-999", "-1"]
    # the cover beside a seen layer is an amount and stays
    assert df.get_column("v_s1_ns").to_list() == ["1", "1"]
    assert "v_s1_csa" not in df.columns


def test_parse_dwd_data_reports_unknown_measurement_method(caplog: pytest.LogCaptureFixture) -> None:
    """Test that an indicator outside the code table is reported rather than quietly nulled.

    Only P and I have ever been observed. A letter outside the table has to become null, as there
    is no digit to give it, but that leaves it indistinguishable from "not measured" -- which is
    what the reserved 0 exists to keep apart -- so it must not pass silently.
    """
    payload = (
        "STATIONS_ID;MESS_DATUM;QN_8;V_VV_I;V_VV;eor\n"
        "  96;2025020800;    3;   P;  18770;eor\n"
        "  96;2025020801;    3;   X;  23000;eor\n"
    )
    file = File(url="", content=BytesIO(payload.encode("utf8")), status=200)
    with caplog.at_level(logging.WARNING):
        df = parse_climate_observations_data(
            files=[file],
            dataset=DwdObservationMetadata.hourly.visibility,
            period=Period.RECENT,
        ).collect()
    assert df.get_column("v_vv_i").to_list() == ["1", None]
    assert "['X']" in caplog.text
    assert "v_vv_i" in caplog.text


def test_parse_dwd_hourly_weather_phenomena_nulls_weather_not_reported() -> None:
    """Test that -1 in `WW` becomes null, for the dataset's own column only.

    Station 01869 writes -1 for every hour whose present weather was not reported and says so in
    `WW_Text` beside it (stundenwerte_WW_01869_akt.zip, 2025-04-09 00:00). It is no weather, so
    it must not be counted, maxed or averaged as one. The rule is the dataset's: the `WW` of the
    hourly cloud type file is not touched by it.
    """
    payload = (
        "STATIONS_ID;MESS_DATUM;QN_8;  WW;WW_Text;eor\n"
        "       1869;2025040900;    3;  -1;Wetter wurde nicht gemeldet;eor\n"
        "       1869;2025040901;    3;  -1;Wetter wurde nicht gemeldet;eor\n"
        "       1869;2025040902;    3;  61;Regen;eor\n"
        "       1869;2025040903;    3;   0;;eor\n"
    )
    file = File(url="", content=BytesIO(payload.encode("utf8")), status=200)
    df = parse_climate_observations_data(
        files=[file],
        dataset=DwdObservationMetadata.hourly.weather_phenomena,
        period=Period.RECENT,
    ).collect()
    # a weather code of 0 is a reading and has to survive
    assert df.get_column("ww").to_list() == [None, None, "61", "0"]
    assert df.get_column("qn_8").to_list() == ["3", "3", "3", "3"]

    cloud_type = File(
        url="",
        content=BytesIO(b"STATIONS_ID;MESS_DATUM;QN_8;V_S1_CS;WW;eor\n    3;1994010100;    5;      -1;  -1;eor\n"),
        status=200,
    )
    df = parse_climate_observations_data(
        files=[cloud_type],
        dataset=DwdObservationMetadata.hourly.cloud_type,
        period=Period.HISTORICAL,
    ).collect()
    assert df.get_column("v_s1_cs").to_list() == [None]
    # the rule is the dataset's: the same column name elsewhere is not its business
    assert df.get_column("ww").to_list() == ["-1"]


MOISTURE_COLUMNS = ("absf_std", "vp_std", "tf_std", "rf_std", "td_std")
MOISTURE_HEADER = "STATIONS_ID;MESS_DATUM;QN_8;ABSF_STD;VP_STD;TF_STD;P_STD;TT_STD;RF_STD;TD_STD;eor\n"


def _written(df: pl.DataFrame, column: str) -> list[str | None]:
    """Write the text the parser kept beside a column as `join_quality_flags` writes it into `quality_flags`."""
    return df.select(join_quality_flags(raw=pl.col(raw_column(column)))).get_column("quality_flags").to_list()


def _parse_moisture(rows: str, period: Period = Period.RECENT) -> pl.DataFrame:
    """Parse a hourly moisture file: the parser decodes its codes and judges nothing."""
    file = File(url="", content=BytesIO((MOISTURE_HEADER + rows).encode("utf8")), status=200)
    return parse_climate_observations_data(
        files=[file],
        dataset=DwdObservationMetadata.hourly.moisture,
        period=period,
    ).collect()


def test_parse_dwd_hourly_moisture_nulls_minus_99_9() -> None:
    """Test that -99.9 in the five moisture columns is a missing value, and the columns beside them stay.

    The description documents `missing value = -999`, but the files write -99.9 (station 14006,
    2025-01-05 01:00, in stundenwerte_TF_14006_20201104_20251231_hist.zip). `TT_STD` in the same row
    is a reading, and `P_STD` is left as it is.
    """
    df = _parse_moisture(
        "14006;2025010500;    3;   4.6;   5.8;  -0.3;  995.9;  -0.1;  95.7;  -0.7;eor\n"
        "14006;2025010501;    3; -99.9; -99.9; -99.9;  995.9;  -0.7; -99.9; -99.9;eor\n"
    )
    assert df.get_column("absf_std").to_list() == ["4.6", None]
    assert df.get_column("vp_std").to_list() == ["5.8", None]
    assert df.get_column("tf_std").to_list() == ["-0.3", None]
    assert df.get_column("rf_std").to_list() == ["95.7", None]
    assert df.get_column("td_std").to_list() == ["-0.7", None]
    assert df.get_column("p_std").to_list() == ["995.9", "995.9"]
    assert df.get_column("tt_std").to_list() == ["-0.1", "-0.7"]


def test_parse_dwd_hourly_moisture_historical_row_and_documented_sentinel() -> None:
    """Test the historical row of station 03735 (1949-01-28 06:00), and that the documented -999 still maps.

    `P_STD` is not part of the rule: the file writes 959.5 in it for every row, the six missing ones included.
    """
    df = _parse_moisture(
        "3735;1949012806;    3; -99.9; -99.9; -99.9;  959.5; -11.0; -99.9; -99.9;eor\n"
        "3735;1949012807;    3;  -999;  -999;  -999;  -999;  -999;  -999;  -999;eor\n",
        period=Period.HISTORICAL,
    )
    for column in MOISTURE_COLUMNS:
        assert df.get_column(column).to_list() == [None, None]
    assert df.get_column("p_std").to_list() == ["959.5", None]
    assert df.get_column("tt_std").to_list() == ["-11.0", None]


def test_parse_dwd_hourly_moisture_rule_is_per_dataset_and_per_column() -> None:
    """Test that -99.9 is only a missing value in the five columns of this dataset, not a blanket rule."""
    df = _parse_moisture("14006;2025010501;    3;   3.2;   4.8;  -1.6;  995.9;  -99.9;  95.0;  -1.2;eor\n")
    assert df.get_column("p_std").to_list() == ["995.9"]
    assert df.get_column("tt_std").to_list() == ["-99.9"]
    # a -99.9 in `P_STD` is no missing value of this rule: the reader leaves it to the core, which judges it by range
    df = _parse_moisture("14006;2025010501;    3;   3.2;   4.8;  -1.6;  -99.9;  -0.1;  95.0;  -1.2;eor\n")
    assert df.get_column("p_std").to_list() == ["-99.9"]
    # the same column names under another dataset are not this dataset's rule
    other = File(
        url="",
        content=BytesIO(
            b"STATIONS_ID;MESS_DATUM;QN_9;TT_TU;RF_TU;ABSF_STD;eor\n     3;2025010501;    3;   3.1;  50.0; -99.9;eor\n"
        ),
        status=200,
    )
    df = parse_climate_observations_data(
        files=[other],
        dataset=DwdObservationMetadata.hourly.temperature_air,
        period=Period.RECENT,
    ).collect()
    assert df.get_column("absf_std").to_list() == ["-99.9"]
    assert df.get_column("tt_tu").to_list() == ["3.1"]


def _moisture_rows(pressures: list[str], station: str = "14072") -> str:
    """Give hourly moisture rows, one per pressure, as the file writes them."""
    start = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
    return "".join(
        f"{station};{start + dt.timedelta(hours=hour):%Y%m%d%H};    3;   4.0;   5.0;  -0.5;{pressure:>8};"
        "  -0.2;  90.0;  -0.9;eor\n"
        for hour, pressure in enumerate(pressures)
    )


def _moisture_file(rows: str) -> File:
    return File(url="", content=BytesIO((MOISTURE_HEADER + rows).encode("utf8")), status=200)


def _raw_pressure(df: pl.DataFrame) -> list[str | None]:
    """Give the text of the pressure the parser kept, without the `rejected:stuck` the stuck rule writes before it."""
    return [
        flags.removeprefix("rejected:stuck,").removeprefix("raw:") if flags is not None else None
        for flags in _written(df, "p_std")
    ]


def test_parse_dwd_hourly_moisture_keeps_a_pressure_that_moves_or_is_short() -> None:
    """Test that a P_STD with more than three values, or a constant of 499 readings, is left as it is."""
    # a barometer: a hundred values, none of them held
    moving = [f"{990 + hour % 100 / 10:.1f}" for hour in range(500)]
    df = _parse_moisture(_moisture_rows(moving))
    assert df.get_column("p_std").to_list() == moving
    assert _raw_pressure(df) == [None] * 500
    # four values are a pressure that moves
    four = ["977.1"] * 125 + ["977.6"] * 125 + ["977.9"] * 125 + ["978.2"] * 125
    assert _parse_moisture(_moisture_rows(four)).get_column("p_std").to_list() == four
    # one reading short: no evidence yet, however few the values
    for short in (["997.3"] * 499, ["953.1"] * 250 + ["954.8"] * 249):
        df = _parse_moisture(_moisture_rows(short))
        assert df.get_column("p_std").to_list() == short
        assert _raw_pressure(df) == [None] * 499


def test_parse_dwd_hourly_moisture_pressure_constant_rule_is_per_dataset() -> None:
    """Test that the pressure of the hourly pressure dataset, one value or not, is left as it is."""
    start = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
    rows = "".join(
        f"    3;{start + dt.timedelta(hours=hour):%Y%m%d%H};    3;  1013.2;   997.3;eor\n" for hour in range(500)
    )
    file = File(
        url="",
        content=BytesIO(f"STATIONS_ID;MESS_DATUM;QN_8;P;P0;eor\n{rows}".encode()),
        status=200,
    )
    df = parse_climate_observations_data(
        files=[file],
        dataset=DwdObservationMetadata.hourly.pressure,
        period=Period.RECENT,
    ).collect()
    assert df.get_column("p0").to_list() == ["997.3"] * 500


@pytest.mark.parametrize(
    "payload",
    [
        # as DWD writes it, padded, so that the column is read as text
        (
            "STATIONS_ID;MESS_DATUM;QN_3;   F;   D;eor\n"
            "          3;1975101607;    5;   2.1;  250;eor\n"
            "          3;1975101608;    5;   1.3;  990;eor\n"
            "          3;1975101609;    5;   0.0;    0;eor\n"
            "          3;1975101610;    5;   4.0; -999;eor\n"
        ),
        # unpadded, so that the column is read as numbers
        (
            "STATIONS_ID;MESS_DATUM;QN_3;F;D;eor\n"
            "3;1975101607;5;2.1;250;eor\n"
            "3;1975101608;5;1.3;990;eor\n"
            "3;1975101609;5;0.0;0;eor\n"
            "3;1975101610;5;4.0;-999;eor\n"
        ),
    ],
    ids=["padded", "unpadded"],
)
def test_parse_dwd_data_drops_variable_wind_direction(payload: str) -> None:
    """Test that 990 in the hourly wind direction becomes null, with the wind speed beside it kept.

    The files write 990 where there is no direction (station 00003, 1975-10-16 08:00) next to a real
    speed of 1.3 m/s; the description documents only -999. The 0 beside a speed of 0 is a calm, null as
    well (GH-2805).
    """
    file = File(url="", content=BytesIO(payload.encode("utf8")), status=200)
    df = parse_climate_observations_data(
        files=[file],
        dataset=DwdObservationMetadata.hourly.wind,
        period=Period.HISTORICAL,
    ).collect()
    assert df.get_column("d").cast(pl.Float64).to_list() == [250.0, None, None, None]
    assert df.get_column("f").cast(pl.Float64).to_list() == [2.1, 1.3, 0.0, 4.0]


def test_parse_dwd_data_drops_variable_wind_direction_10_minutes() -> None:
    """Test that 990 in the 10 minute wind direction becomes null, with the wind speed beside it kept.

    Station 00198 writes 990 at 1994-05-02 13:50 next to a speed of 1.1 m/s, station 00298 at
    1993-09-14 11:50 next to the missing speed.
    """
    payload = (
        "STATIONS_ID;MESS_DATUM;  QN;FF_10;DD_10;eor\n"
        "        198;199405021340;    1;   1.1;  120;eor\n"
        "        198;199405021350;    1;   1.1;  990;eor\n"
        "        298;199309141150;    1;  -999;  990;eor\n"
    )
    file = File(url="", content=BytesIO(payload.encode("utf8")), status=200)
    df = parse_climate_observations_data(
        files=[file],
        dataset=DwdObservationMetadata.minute_10.wind,
        period=Period.HISTORICAL,
    ).collect()
    assert df.get_column("dd_10").cast(pl.Float64).to_list() == [120.0, None, None]
    assert df.get_column("ff_10").cast(pl.Float64).to_list() == [1.1, 1.1, None]


# Lines of the historical files, read 2026-10-12, as DWD writes them (GH-2805): the dataset, the header, the lines, the
# direction column and, per line, the direction and the `raw` text that arrive.
_CALM_WIND_FILES = {
    # hourly wind D is on a rose without a 0, and the sheet names no code: the 0 beside a speed of 0 is null, the 0
    # beside 0.4 m/s stays, as in every provider (GH-3222)
    "hourly/wind": (
        DwdObservationMetadata.hourly.wind,
        "STATIONS_ID;MESS_DATUM;QN_3;   F;   D;eor",
        [
            "          3;1975010115;    5;   4.3; 250;eor",
            "          3;1975010215;    5;   1.2; 360;eor",
            "          3;1975020807;    5;   0.0;   0;eor",
            "          3;1997081708;    3;   0.4;   0;eor",
        ],
        "d",
        [("250", None), ("360", None), (None, "0"), ("0", None)],
    ),
    # DWD names the column "Windrichtung uml.,windstill DD=00": every 0 is null, with the speed of 0 or of 1.0 m/s
    # or of the 7.7 m/s of Büsum (00785) on 1986-02-14
    "hourly/wind_synop": (
        DwdObservationMetadata.hourly.wind_synoptic,
        "STATIONS_ID;MESS_DATUM;QN_8;  FF;  DD;eor",
        [
            "          3;1950041503;    1;   0.5; 360;eor",
            "          3;1950050406;    1;   0.0;   0;eor",
            "          3;1954021915;    1;   1.0;   0;eor",
            "        785;1986021410;    1;   7.7;   0;eor",
        ],
        "dd",
        [("360", None), (None, "0"), (None, "0"), (None, "0")],
    ),
    # the "32-teilige Windrose" has no point 0; 32 is north. The 0 beside Beaufort 0 is null, the 0 beside Beaufort 1
    # stays, 0 degrees (GH-3222)
    "subdaily/wind": (
        DwdObservationMetadata.subdaily.wind,
        "STATIONS_ID;MESS_DATUM;QN_4;DK_TER;FK_TER;eor",
        [
            "          1;1937010114;    5;  24;   3;eor",
            "          1;1937011007;    5;  32;   3;eor",
            "          1;1937010107;    5;   0;   0;eor",
            "       1001;2001070506;   10;   0;   1;eor",
        ],
        "dk_ter",
        [("270.0", None), ("360.0", None), (None, "0"), ("0.0", None)],
    ),
    # 0 is also north at some stations (01691 on 1994-05-01 reads 360 at 15:40 and 0 at 15:50 at 6 m/s), so only the
    # 0 of a speed of 0 is null; a speed of 0.1 or a missing one is not known to be a calm
    "10_minutes/wind": (
        DwdObservationMetadata.minute_10.wind,
        "STATIONS_ID;MESS_DATUM;  QN;FF_10;DD_10;eor",
        [
            "       1691;199405011540;    1;   6.0; 360;eor",
            "       1691;199405011550;    1;   6.1;   0;eor",
            "          3;199304281230;    1;   0.0;   0;eor",
            "        298;199811210010;    1;   0.1;   0;eor",
            "          3;199908122130;    1;  -999;   0;eor",
        ],
        "dd_10",
        [("360", None), ("0", None), (None, "0"), ("0", None), ("0", None)],
    ),
    # the speed of the direction is the gust: 00003 on 1993-06-15 15:30 has a 0 beside a gust of 4.1 m/s
    "10_minutes/extreme_wind": (
        DwdObservationMetadata.minute_10.wind_extreme,
        "STATIONS_ID;MESS_DATUM;  QN;FX_10;FNX_10;FMX_10;DX_10",
        [
            "          3;199306150700;    1;   4.5;  -999;  -999; 360",
            "          3;199306151530;    1;   4.1;  -999;  -999;   0",
            "          3;199304281230;    1;   0.0;  -999;  -999;   0",
        ],
        "dx_10",
        [("360", None), ("0", None), (None, "0")],
    ),
    # the urban 10 minute file (15818 on 2025-04-28, 19844 on 2025-04-12), written with two decimals: the same rule as
    # 10 minute wind, with the sheet missing (GH-2809). No file has a 0 beside a speed above 0 or a missing one, so
    # those two lines are made up to pin the gate
    "10_minutes/urban_wind": (
        DwdObservationMetadata.minute_10.urban_wind,
        "STATIONS_ID;MESS_DATUM;  QN;FF_ST_10;DD_ST_10;eor",
        [
            "      15818;202504281820;    3;   0.10; 220;eor",
            "      15818;202504281830;    3;   0.00;   0;eor",
            "      19844;202504121320;    3;   0.70; 360;eor",
            "      19844;202504121330;    3;   0.40;   0;eor",
            "      19844;202504121340;    3;  -999;   0;eor",
        ],
        "dd_st_10",
        [("220", None), (None, "0"), ("360", None), ("0", None), ("0", None)],
    ),
    # the urban hourly file (13667, stundenwerte_wind_13667_akt.zip, read 2026-10-15): a 0 comes beside 0.1 to 0.8 m/s
    # and never beside 0, in hours whose six 10 minute directions are spread over the compass (13667 on 2025-04-12
    # 04:00: 50, 110, 250, 260, 100, 80 degrees), so it is no calm and no north, which the file writes as 360 (GH-2809).
    # Every 0 is null whatever the speed, and a speed of 0 (made up, no file has one) does not change that
    "hourly/urban_wind": (
        DwdObservationMetadata.hourly.urban_wind,
        "STATIONS_ID; MESS_DATUM; QUALITAETS_NIVEAU; STRUKTUR_VERSION; WINDGESCHWINDIGKEIT; WINDRICHTUNG; eor",
        [
            "     13667;   2018061722;    2;0;  0.50;  0;eor",
            "     13667;   2018062421;    2;0;  0.20;  0;eor",
            "     13667;   2018092301;    2;0;  0.40;360;eor",
            "     13667;   2018092302;    2;0;  0.00;  0;eor",
        ],
        "windrichtung",
        [(None, "0"), (None, "0"), ("360", None), (None, "0")],
    ),
}


@pytest.mark.parametrize("name", list(_CALM_WIND_FILES))
def test_parse_dwd_data_nulls_the_wind_direction_0_of_a_calm_and_keeps_the_text(name: str) -> None:
    """Test that a direction of 0 DWD writes for a calm is null with `0` as its raw text, and 360 stays (GH-2805).

    Only a 0 beside a speed of exactly 0 is null, as in every provider (GH-3222), but where the sheet names the 0 the
    code of a variable wind as well (hourly wind_synop), where every 0 is null, and in the hourly urban wind, whose
    0 is neither a calm nor north (GH-2809).
    """
    dataset, header, rows, column, expected = _CALM_WIND_FILES[name]
    file = File(url="", content=BytesIO(("\n".join([header, *rows]) + "\n").encode("utf8")), status=200)
    df = parse_climate_observations_data(files=[file], dataset=dataset, period=Period.HISTORICAL).collect()
    assert list(zip(df.get_column(column).to_list(), df.get_column(f"{column}__raw").to_list(), strict=True)) == [
        (value, raw) for value, raw in expected
    ]


def test_parse_dwd_data_turns_the_subdaily_wind_rose_point_into_degrees() -> None:
    """Test that the 32-point wind rose of `DK_TER` is returned in degrees, 32 as 360, after the sentinels (GH-2808).

    The rows are those of terminwerte_FK_00096_akt.zip (read 2026-10-13), beside the hourly wind_synop `DD` of
    stundenwerte_F_00096_akt.zip at the same hour: 24 beside 290 and 270, 32 beside 350, 16 beside 170, 8 beside 100,
    4 beside 40. The 0 of 2025-08-11 06:00 (Beaufort 0, DD 220 at 0.2 m/s) is a calm and stays null with its text, and
    so does the -999 DWD documents for a missing value (written by hand, the file has none).
    """
    rows = [
        "STATIONS_ID;MESS_DATUM;QN_4;DK_TER;FK_TER;eor",
        "         96;2025041006;    9;  24;   2;eor",
        "         96;2025041012;    9;  24;   3;eor",
        "         96;2025041118;    9;  32;   1;eor",
        "         96;2025041218;    9;  16;   1;eor",
        "         96;2025041306;    9;   8;   2;eor",
        "         96;2025041418;    9;   4;   1;eor",
        "         96;2025081106;    9;   0;   0;eor",
        "         96;2025081112;    9;-999;   0;eor",
    ]
    file = File(url="", content=BytesIO(("\n".join(rows) + "\n").encode("utf8")), status=200)
    df = parse_climate_observations_data(
        files=[file], dataset=DwdObservationMetadata.subdaily.wind, period=Period.RECENT
    ).collect()
    assert list(zip(df.get_column("dk_ter").to_list(), df.get_column("dk_ter__raw").to_list(), strict=True)) == [
        ("270.0", None),
        ("270.0", None),
        ("360.0", None),
        ("180.0", None),
        ("90.0", None),
        ("45.0", None),
        (None, "0"),
        (None, "-999"),
    ]


def _documented_codes(page: str, column: str) -> set[int]:
    """Read the `∈ [...]` constraint of the row of `column` on a dwd/observation docs page."""
    docs = Path(__file__).parents[4] / "docs" / "data" / "provider" / "dwd" / "observation" / page
    row = next(
        (line for line in docs.read_text().splitlines() if line.startswith("| {term}`") and f"| {column} |" in line),
        None,
    )
    assert row is not None, f"no row for {column} in {page}"
    constraint = row.rstrip(" |").rsplit("|", 1)[1]
    return {int(code) for code in re.findall(r"\d+", constraint)}


def test_parse_dwd_hourly_precipitation_form_keeps_every_code_the_files_hold() -> None:
    """Test that the codes of `WRTR` in the files come back as written, 9 and -999 as null, and the docs list them.

    Rows of station 01048 (stundenwerte_RR_01048_19950901_20251231_hist.zip). The sheet defines 0, 1, 4, 6, 7, 8
    and 9, the file also holds 2 and 3 (2001-05-09 02:00 and 2002-01-14 04:00). 9, written 2021-07-09 17:00, is in the
    sheet's words "Missing value, Type of precipitation unascertainable" (GH-2703): null, with the 9 as its `raw`
    text, as -999 is.
    """
    rows = "".join(
        f"1048;20010412{hour:02d};    1;   0.0;   1;{code:>4};eor\n"
        for hour, code in enumerate(["0", "1", "2", "3", "4", "6", "7", "8", "9", "-999"])
    )
    file = File(
        url="",
        content=BytesIO(("STATIONS_ID;MESS_DATUM;QN_8;  R1;RS_IND;WRTR;eor\n" + rows).encode("utf8")),
        status=200,
    )
    df = parse_climate_observations_data(
        files=[file], dataset=DwdObservationMetadata.hourly.precipitation, period=Period.HISTORICAL
    ).collect()
    codes = df.get_column("wrtr").to_list()
    assert codes == ["0", "1", "2", "3", "4", "6", "7", "8", None, None]
    assert df.get_column("wrtr__raw").to_list() == [None] * 8 + ["9", "-999"]
    assert {int(code) for code in codes if code is not None} == _documented_codes("hourly.md", "wrtr")
    # only the precipitation form: a 9 in the height or the indicator beside it is a value
    assert df.get_column("r1").to_list() == ["0.0"] * 10
    assert df.get_column("rs_ind").to_list() == ["1"] * 10


def test_parse_dwd_hourly_precipitation_leaves_a_9_of_another_column_alone() -> None:
    """Test that the 9 of `WRTR` is no sentinel of the columns beside it: 9.0 mm of rain is a reading."""
    file = File(
        url="",
        content=BytesIO(
            b"STATIONS_ID;MESS_DATUM;QN_8;  R1;RS_IND;WRTR;eor\n1048;2001041200;    1;   9.0;   9;   6;eor\n"
        ),
        status=200,
    )
    df = parse_climate_observations_data(
        files=[file], dataset=DwdObservationMetadata.hourly.precipitation, period=Period.HISTORICAL
    ).collect()
    assert df.select("r1", "rs_ind", "wrtr", "wrtr__raw").row(0) == ("9.0", "9", "6", None)


@pytest.mark.parametrize(
    ("page", "dataset", "header", "row", "column"),
    [
        (
            "1_minute.md",
            DwdObservationMetadata.minute_1.precipitation,
            "STATIONS_ID;MESS_DATUM_BEGINN;MESS_DATUM_ENDE;QN;RS_01;RTH_01;RWH_01;RS_IND_01;eor\n",
            "1048;199501010{m}00;199501010{m}59;    1;  0.00;  -999;  -999;{c:>4};eor\n",
            "rs_ind_01",
        ),
        (
            "5_minutes.md",
            DwdObservationMetadata.minute_5.precipitation,
            "STATIONS_ID;MESS_DATUM;QN_5min;RS_COUNT_05;RS_IND_05;RS_05;eor\n",
            "1048;199501010{m}00;    1;   5;{c:>4};   0.00;eor\n",
            "rs_ind_05",
        ),
        (
            "10_minutes.md",
            DwdObservationMetadata.minute_10.precipitation,
            "STATIONS_ID;MESS_DATUM;  QN;RWS_DAU_10;RWS_10;RWS_IND_10;eor\n",
            "1048;199501010{m}00;    1;   0;   0.00;{c:>4};eor\n",
            "rws_ind_10",
        ),
    ],
)
def test_parse_dwd_precipitation_indicator_keeps_the_heating_codes(
    page: str, dataset: DatasetModel, header: str, row: str, column: str
) -> None:
    """Test that the codes 2 and 3 of a QN = 1 row come back with 0 and 1, and the docs list 0 to 3.

    The shape of the rows is that of station 01048; the 10-minute files of 1991 to 1999 hold both heating codes
    under QN = 1 (67 and 40883 rows), the 1- and 5-minute sheets define them the same way.
    """
    rows = "".join(row.format(m=minute, c=code) for minute, code in enumerate(["0", "1", "2", "3", "-999"]))
    file = File(url="", content=BytesIO((header + rows).encode("utf8")), status=200)
    df = parse_climate_observations_data(files=[file], dataset=dataset, period=Period.HISTORICAL).collect()
    # a 1-minute row is read as the 60 minutes between its begin and its end
    codes = list(dict.fromkeys(df.get_column(column).to_list()))
    assert codes == ["0", "1", "2", "3", None]
    assert {int(code) for code in codes if code is not None} == _documented_codes(page, column)


@pytest.mark.parametrize(
    ("dataset", "header", "row", "column"),
    [
        (
            DwdObservationMetadata.daily.climate_summary,
            (
                "STATIONS_ID;MESS_DATUM;QN_3;  FX;  FM;QN_4; RSK;RSKF; SDK;SHK_TAG;  NM; VPM;  PM; TMK; UPM; TXK; TNK; "
                "TGK;eor\n"
            ),
            (
                "1048;196703{d:02d};-999;-999;-999;    5;   4.3;{c:>4};   1.800;   0;   6.0;   6.5; 983.10;    4.8;"
                "   76.00;   7.4;    2.3;   -0.2;eor\n"
            ),
            "rskf",
        ),
        (
            DwdObservationMetadata.daily.precipitation_more,
            "STATIONS_ID;MESS_DATUM;QN_6;  RS; RSF;SH_TAG;NSH_TAG;eor\n",
            "1048;197902{d:02d};    5;   7.1;{c:>4};  13;   1;eor\n",
            "rsf",
        ),
    ],
    ids=["rskf", "rsf"],
)
def test_parse_dwd_daily_precipitation_form_keeps_every_code_the_files_hold(
    dataset: DatasetModel, header: str, row: str, column: str
) -> None:
    """Test that the codes of `RSKF` and `RSF` come back as written, and the docs list them.

    The shape of the rows is that of station 01048 (1967-03-02 and 1979-02-13, QN 5). DWD's sheet of 2021 defined
    0, 1, 4, 6, 7, 8 and 9 and the current one only says "numerical code"; the historical files of all stations
    (2026-10-14) hold 2, 3 and 5 besides, and no 9. -999 is the missing value and maps to null.
    """
    rows = "".join(
        row.format(d=day, c=code)
        for day, code in enumerate(["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "-999"], 1)
    )
    file = File(url="", content=BytesIO((header + rows).encode("utf8")), status=200)
    df = parse_climate_observations_data(files=[file], dataset=dataset, period=Period.HISTORICAL).collect()
    codes = df.get_column(column).to_list()
    assert codes == ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", None]
    assert {int(code) for code in codes if code is not None} == _documented_codes("daily.md", column)


def _parse(dataset: DatasetModel, payload: str, period: Period = Period.RECENT) -> pl.DataFrame:
    file = File(url="", content=BytesIO(payload.encode("utf8")), status=200)
    return parse_climate_observations_data(files=[file], dataset=dataset, period=period).collect()
