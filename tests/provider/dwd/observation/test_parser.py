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
from wetterdienst.model.plausibility import Plausibility, applying
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
    """Test that -1 in the hourly cloud cover fields becomes null, while cloud type keeps its -1.

    DWD writes -1 where the sky could not be seen at all, SYNOP's N = 9. It is a statement that no
    amount could be given, not an amount: left alone it is read as -1 eighths and converts to
    -0.125 of the sky. `v_sN_cs` beside it is a cloud *type* code where -1 is DWD's own value for
    an automated observation, so that one has to survive.
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
    # the cloud type code keeps it: -1 is what DWD writes for an automated observation
    assert df.get_column("v_s1_cs").to_list() == ["-1", "6"]


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
    """Test that -1 in `WW` becomes null, while the same -1 in the cloud type code `v_s1_cs` stays.

    Station 01869 writes -1 for every hour whose present weather was not reported and says so in
    `WW_Text` beside it (stundenwerte_WW_01869_akt.zip, 2025-04-09 00:00). It is no weather, so
    it must not be counted, maxed or averaged as one. In `v_s1_cs` of the hourly cloud type, -1 is
    DWD's own value for an automated observation.
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
    assert df.get_column("v_s1_cs").to_list() == ["-1"]
    # the rule is the dataset's: the same column name elsewhere is not its business
    assert df.get_column("ww").to_list() == ["-1"]


MOISTURE_COLUMNS = ("absf_std", "vp_std", "tf_std", "rf_std", "td_std")
MOISTURE_HEADER = "STATIONS_ID;MESS_DATUM;QN_8;ABSF_STD;VP_STD;TF_STD;P_STD;TT_STD;RF_STD;TD_STD;eor\n"


def _written(df: pl.DataFrame, column: str) -> list[str | None]:
    """Write the text the parser kept beside a column as `join_quality_flags` writes it into `quality_flags`."""
    return df.select(join_quality_flags(raw=pl.col(raw_column(column)))).get_column("quality_flags").to_list()


def _parse_moisture(
    rows: str, period: Period = Period.RECENT, plausibility: Plausibility | None = None
) -> pl.DataFrame:
    """Parse a hourly moisture file, with every check as it is by default but `stuck`, which is hard here."""
    file = File(url="", content=BytesIO((MOISTURE_HEADER + rows).encode("utf8")), status=200)
    with applying(plausibility or Plausibility(stuck="hard")):
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
