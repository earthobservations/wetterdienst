# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pandas as pd
import pytest
from pandas._testing import assert_frame_equal

from wetterdienst.metadata.columns import Columns
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType


@pytest.mark.remote
def test_dwd_mosmix_stations_success():
    # Existing combination of parameters
    request = DwdMosmixRequest(parameter="small", mosmix_type=DwdMosmixType.LARGE)

    df = request.all().df

    assert not df.empty

    df_given = (
        df.loc[df[Columns.STATION_ID.value].isin(["01001", "72306", "83891", "94767"]), :]
        .sort_values("station_id")
        .reset_index(drop=True)
    )

    df_expected = pd.DataFrame(
        [
            {
                "station_id": "01001",
                "icao_id": "ENJA",
                "from_date": pd.NaT,
                "to_date": pd.NaT,
                "height": 10.0,
                "latitude": 70.93,
                "longitude": -8.0,
                "name": "JAN MAYEN",
                "state": pd.NA,
            },
            {
                "station_id": "72306",
                "icao_id": "KRDU",
                "from_date": pd.NaT,
                "to_date": pd.NaT,
                "height": 132.0,
                "latitude": 35.87,
                "longitude": -78.12,
                "name": "RALEIGH/DURHAM NC.",
                "state": pd.NA,
            },
            {
                "station_id": "83891",
                "icao_id": "SBLJ",
                "from_date": pd.NaT,
                "to_date": pd.NaT,
                "height": 937.0,
                "latitude": -27.13,
                "longitude": -49.67,
                "name": "LAGES",
                "state": pd.NA,
            },
            {
                "station_id": "94767",
                "icao_id": "YSSY",
                "from_date": pd.NaT,
                "to_date": pd.NaT,
                "height": 6.0,
                "latitude": -33.28,
                "longitude": 151.18,
                "name": "SYDNEY AIRPORT",
                "state": pd.NA,
            },
        ]
    )

    df_expected.from_date = pd.to_datetime(df_expected.from_date, utc=True)
    df_expected.to_date = pd.to_datetime(df_expected.to_date, utc=True)

    assert_frame_equal(df_given, df_expected)
