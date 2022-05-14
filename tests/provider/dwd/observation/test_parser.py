# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
""" Tests for parser function """
from io import BytesIO
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest
import requests
from pandas._testing import assert_frame_equal

from wetterdienst import Period, Resolution
from wetterdienst.provider.dwd.observation import DwdObservationDataset
from wetterdienst.provider.dwd.observation.parser import parse_climate_observations_data


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
        dataset=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=Resolution.DAILY,
        period=Period.HISTORICAL,
    )

    assert_frame_equal(
        df.iloc[[0, -1], :].reset_index(drop=True),
        pd.DataFrame(
            {
                "station_id": ["1", "1"],
                "date": ["19370101", "19860630"],
                "qn_3": pd.Series([np.NaN, np.NaN], dtype=object),
                "fx": pd.Series([np.NaN, np.NaN], dtype=object),
                "fm": pd.Series([np.NaN, np.NaN], dtype=object),
                "qn_4": ["5", "10"],
                "rsk": ["0.0", "0.0"],
                "rskf": ["0", "0"],
                "sdk": pd.Series([np.NaN, np.NaN], dtype=object),
                "shk_tag": ["0", "0"],
                "nm": ["6.3", "0.3"],
                "vpm": [np.NaN, "13.9"],
                "pm": pd.Series([np.NaN, np.NaN], dtype=object),
                "tmk": ["-0.5", "19.8"],
                "upm": [np.NaN, "60.00"],
                "txk": ["2.5", "24.8"],
                "tnk": ["-1.6", "14.4"],
                "tgk": pd.Series([np.NaN, np.NaN], dtype=object),
            }
        ),
    )
