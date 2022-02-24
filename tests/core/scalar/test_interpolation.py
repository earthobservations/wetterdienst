from datetime import datetime

import pandas as pd
from pandas import Timestamp
from pandas._testing import assert_frame_equal

from wetterdienst import Parameter
from wetterdienst.provider.dwd.observation import (
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)


def test_interpolation():
    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200.name,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2022, 1, 20),
    )

    result = stations.interpolate(latitude=50.0, longitude=8.9)
    interpolated_df = result.df
    assert interpolated_df.shape[0] == 18001
    assert interpolated_df.dropna().shape[0] == 12385

    test_df = result.filter_by_date("2022-01-02 00:00:00+0000").reset_index(drop=True)

    assert_frame_equal(
        test_df,
        pd.DataFrame(
            {
                "date": {0: Timestamp("2022-01-02 00:00:00+0000", tz="UTC")},
                "parameter": {0: Parameter.TEMPERATURE_AIR_MEAN_200.name.lower()},
                "value": {0: 276.94455095211555},
                "distance_mean": {0: 13.37185625092419},
                "station_ids": {0: ["02480", "04411", "07341", "00917"]},
            }
        ),
    )
