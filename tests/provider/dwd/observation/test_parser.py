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
            "date": [
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
            "date": pl.Datetime(time_zone="UTC"),
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
