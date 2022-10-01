# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pandas as pd
from pandas._testing import assert_frame_equal

from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest


def test_noaa_ghcn_stations():
    df = NoaaGhcnRequest("daily").all().df.iloc[:5, :]

    df_expected = pd.DataFrame(
        {
            "station_id": pd.Series(
                [
                    "ACW00011604",
                    "ACW00011647",
                    "AE000041196",
                    "AEM00041194",
                    "AEM00041217",
                ],
                dtype=str,
            ),
            "from_date": pd.to_datetime(
                [
                    "1949-01-01 00:00:00+00:00",
                    "1957-01-01 00:00:00+00:00",
                    "1944-01-01 00:00:00+00:00",
                    "1983-01-01 00:00:00+00:00",
                    "1983-01-01 00:00:00+00:00",
                ]
            ),
            "to_date": pd.to_datetime(
                [
                    "1949-12-31 00:00:00+00:00",
                    "1970-12-31 00:00:00+00:00",
                    "2022-12-31 00:00:00+00:00",
                    "2022-12-31 00:00:00+00:00",
                    "2022-12-31 00:00:00+00:00",
                ]
            ),
            "height": pd.Series([10.1, 19.2, 34.0, 10.4, 26.8], dtype=float),
            "latitude": pd.Series([17.1167, 17.1333, 25.333, 25.255, 24.433], dtype=float),
            "longitude": pd.Series([-61.7833, -61.7833, 55.517, 55.364, 54.651], dtype=float),
            "name": pd.Series(
                [
                    "ST JOHNS COOLIDGE FLD",
                    "ST JOHNS",
                    "SHARJAH INTER. AIRP",
                    "DUBAI INTL",
                    "ABU DHABI INTL",
                ],
                dtype=str,
            ),
            "state": pd.Series([pd.NA] * 5, dtype=str),
        }
    )
    assert_frame_equal(df, df_expected)
