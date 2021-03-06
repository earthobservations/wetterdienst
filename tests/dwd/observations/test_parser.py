# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
""" Tests for parser function """
from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import pytest
import requests
from pandas._testing import assert_frame_equal

from wetterdienst import Period, Resolution
from wetterdienst.dwd.observations import DwdObservationParameterSet
from wetterdienst.dwd.observations.parser import parse_climate_observations_data


@pytest.mark.remote
def test_parse_dwd_data():
    url = (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
        "climate/daily/kl/historical/tageswerte_KL_00001_19370101_19860630_hist.zip"
    )
    r = requests.get(url)
    r.raise_for_status()

    payload = BytesIO(r.content)

    filename = "produkt_klima_tag_19370101_19860630_00001.txt"

    file = ZipFile(payload).read(filename)

    df = parse_climate_observations_data(
        filenames_and_files=[(filename, BytesIO(file))],
        parameter=DwdObservationParameterSet.CLIMATE_SUMMARY,
        resolution=Resolution.DAILY,
        period=Period.HISTORICAL,
    )

    assert_frame_equal(
        df.iloc[[0, -1], :].reset_index(drop=True),
        pd.DataFrame(
            {
                "STATION_ID": ["1", "1"],
                "DATE": ["19370101", "19860630"],
                "QN_3": [pd.NA, pd.NA],
                "FX": [pd.NA, pd.NA],
                "FM": [pd.NA, pd.NA],
                "QN_4": ["5", "10"],
                "RSK": ["0.0", "0.0"],
                "RSKF": ["0", "0"],
                "SDK": [pd.NA, pd.NA],
                "SHK_TAG": ["0", "0"],
                "NM": ["6.3", "0.3"],
                "VPM": [pd.NA, "13.9"],
                "PM": [pd.NA, pd.NA],
                "TMK": ["-0.5", "19.8"],
                "UPM": [pd.NA, "60.00"],
                "TXK": ["2.5", "24.8"],
                "TNK": ["-1.6", "14.4"],
                "TGK": [pd.NA, pd.NA],
            }
        ),
    )
