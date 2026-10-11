# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD historical climate data parsing."""

import datetime as dt
import logging
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from fsspec.implementations.http import HTTPFileSystem
from fsspec.implementations.zip import ZipFileSystem
from polars.testing import assert_frame_equal

from wetterdienst import Period
from wetterdienst.model.metadata import DatasetModel
from wetterdienst.provider.dwd.observation import DwdObservationMetadata
from wetterdienst.provider.dwd.observation.parser import parse_climate_observations_data
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
    `WW_Text` beside it (stundenwerte_WW_01869_akt.zip, 2025-04-08 00:00). It is no weather, so
    it must not be counted, maxed or averaged as one. In `v_s1_cs` of the hourly cloud type, -1 is
    DWD's own value for an automated observation.
    """
    payload = (
        "STATIONS_ID;MESS_DATUM;QN_8;  WW;WW_Text;eor\n"
        "       1869;2025040800;    3;  -1;Wetter wurde nicht gemeldet;eor\n"
        "       1869;2025040801;    3;  -1;Wetter wurde nicht gemeldet;eor\n"
        "       1869;2025040802;    3;  61;Regen;eor\n"
        "       1869;2025040803;    3;   0;;eor\n"
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


def _parse_moisture(rows: str, period: Period = Period.RECENT) -> pl.DataFrame:
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
    df = _parse_moisture("14006;2025010501;    3;   3.2;   4.8;  -1.6;  -99.9;  -99.9;  95.0;  -1.2;eor\n")
    assert df.get_column("p_std").to_list() == ["-99.9"]
    assert df.get_column("tt_std").to_list() == ["-99.9"]
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
    speed of 1.3 m/s; the description documents only -999. A direction of 0 is a
    direction and has to survive.
    """
    file = File(url="", content=BytesIO(payload.encode("utf8")), status=200)
    df = parse_climate_observations_data(
        files=[file],
        dataset=DwdObservationMetadata.hourly.wind,
        period=Period.HISTORICAL,
    ).collect()
    assert df.get_column("d").cast(pl.Float64).to_list() == [250.0, None, 0.0, None]
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
