import datetime as dt

import numpy as np
import pandas as pd
import pytest
from pandas._testing import assert_frame_equal

from wetterdienst.provider.noaa.ghcn import NoaaGhcnParameter, NoaaGhcnRequest


@pytest.mark.parametrize(
    "start_date,end_date",
    [
        (dt.datetime(2015, 1, 1), dt.datetime(2022, 1, 1)),
        (dt.datetime(2015, 1, 1, 1), dt.datetime(2022, 1, 1, 1)),
        (dt.datetime(2015, 1, 1, 1, 1), dt.datetime(2022, 1, 1, 1, 1)),
        (dt.datetime(2015, 1, 1, 1, 1, 1), dt.datetime(2022, 1, 1, 1, 1, 1)),
    ],
)
def test_api_amsterdam(start_date, end_date, default_settings):
    request = NoaaGhcnRequest(
        parameter=[NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_MEAN_200],
        start_date=start_date,
        end_date=end_date,
        settings=default_settings,
    ).filter_by_name("DE BILT")
    values = request.values.all().df
    assert not values.value.dropna().empty
    assert_frame_equal(
        values[values["date"] == pd.Timestamp("2015-04-15 22:00:00+00:00")].reset_index(drop=True),
        pd.DataFrame(
            {
                "station_id": pd.Categorical(["NLM00006260"]),
                "dataset": pd.Categorical(["daily"]),
                "parameter": pd.Categorical(["temperature_air_mean_200"]),
                "date": [pd.Timestamp("2015-04-15 22:00:00+0000", tz="UTC")],
                "value": [282.75],
                "quality": [np.nan],
            }
        ),
        check_categorical=False,
    )
