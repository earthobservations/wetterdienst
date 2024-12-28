# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from fsspec.implementations.http import HTTPFileSystem
from fsspec.implementations.zip import ZipFileSystem
from polars.testing import assert_frame_equal

from wetterdienst import Period
from wetterdienst.provider.dwd.observation import DwdObservationMetadata
from wetterdienst.provider.dwd.observation.parser import parse_climate_observations_data


@pytest.mark.remote
def test_parse_dwd_data():
    url = (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
        "climate/daily/kl/historical/tageswerte_KL_00001_19370101_19860630_hist.zip"
    )
    httpfs = HTTPFileSystem()
    payload = BytesIO(httpfs.cat(url))
    filename = "produkt_klima_tag_19370101_19860630_00001.txt"
    zfs = ZipFileSystem(payload)
    file = zfs.cat(filename)
    given_df = parse_climate_observations_data(
        filenames_and_files=[(filename, BytesIO(file))],
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
