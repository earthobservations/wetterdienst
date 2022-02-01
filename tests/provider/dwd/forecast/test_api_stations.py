# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
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

    # TODO: fix empty state value to be pd.NA

    assert_frame_equal(
        df.loc[df[Columns.STATION_ID.value] == "01001", :].reset_index(drop=True),
        pd.DataFrame(
            {
                "station_id": ["01001"],
                "icao_id": ["ENJA"],
                "from_date": pd.to_datetime([pd.NA], utc=True),
                "to_date": pd.to_datetime([pd.NaT], utc=True),
                "height": [10.0],
                "latitude": [70.93],
                "longitude": [-8.0],
                "name": ["JAN MAYEN"],
                "state": ["nan"],
            }
        ),
    )
