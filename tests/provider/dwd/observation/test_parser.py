# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
from io import BytesIO
from zipfile import ZipFile

import polars as pl
import pytest
import requests
from polars.testing import assert_frame_equal

from wetterdienst import Period, Resolution
from wetterdienst.provider.dwd.observation import DwdObservationDataset
from wetterdienst.provider.dwd.observation.parser import parse_climate_observations_data


@pytest.mark.remote
def test_parse_dwd_data():
    url = (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
        "climate/daily/kl/historical/tageswerte_KL_00001_19370101_19860630_hist.zip"
    )
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    payload = BytesIO(r.content)
    filename = "produkt_klima_tag_19370101_19860630_00001.txt"
    file = ZipFile(payload).read(filename)
    given_df = parse_climate_observations_data(
        filenames_and_files=[(filename, BytesIO(file))],
        dataset=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=Resolution.DAILY,
        period=Period.HISTORICAL,
    ).collect()
    expected_df = pl.DataFrame(
        {
            "station_id": ["1", "1"],
            "date": [
                dt.datetime(1937, 1, 1, tzinfo=dt.timezone.utc),
                dt.datetime(1986, 6, 30, tzinfo=dt.timezone.utc),
            ],
            "qn_3": pl.Series(values=[None, None], dtype=pl.Utf8),
            "fx": pl.Series(values=[None, None], dtype=pl.Utf8),
            "fm": pl.Series(values=[None, None], dtype=pl.Utf8),
            "qn_4": ["5", "10"],
            "rsk": ["0.0", "0.0"],
            "rskf": ["0", "0"],
            "sdk": pl.Series(values=[None, None], dtype=pl.Utf8),
            "shk_tag": ["0", "0"],
            "nm": ["6.3", "0.3"],
            "vpm": [None, "13.9"],
            "pm": pl.Series(values=[None, None], dtype=pl.Utf8),
            "tmk": ["-0.5", "19.8"],
            "upm": [None, "60.00"],
            "txk": ["2.5", "24.8"],
            "tnk": ["-1.6", "14.4"],
            "tgk": pl.Series(values=[None, None], dtype=pl.Utf8),
        }
    )
    assert_frame_equal(
        given_df[[0, -1], :],
        expected_df,
    )
