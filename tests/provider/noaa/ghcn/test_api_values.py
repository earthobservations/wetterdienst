import pandas as pd
import numpy as np
from datetime import datetime
from pandas._testing import assert_frame_equal

from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest


def test_noaa_ghcn_values():
    stations = NoaaGhcnRequest("daily", start_date=datetime(2020, 1, 1), end_date=datetime(2020, 1, 2))
    stations = stations.filter_by_rank(40.63539851538455, -73.98955218831027, 2)

    df_expected = pd.DataFrame([['US1NYKN0003', pd.Timestamp('2008-01-01 00:00:00+0000', tz='UTC'),
                                 pd.Timestamp('2009-12-31 00:00:00+0000', tz='UTC'), 7.9, 40.6194, -73.9859,
                                 'BROOKLYN 2.4 SW', 'NY', 1.8054568219792044],
                                ['USC00305798', pd.Timestamp('1951-01-01 00:00:00+0000', tz='UTC'),
                                 pd.Timestamp('1953-12-31 00:00:00+0000', tz='UTC'), 6.1, 40.6, -73.9667,
                                 'NEW YORK BENSONHURST', 'NY', 4.3833274341551505]],
                               columns=['station_id', 'from_date', 'to_date', 'height', 'latitude', 'longitude',
                                        'name', 'state', 'distance'])
    assert_frame_equal(stations.df, df_expected)

    values_result = []
    for result in stations.values.query():
        values_result.append(result.df)

    df_expected_values = pd.DataFrame(
        [['US1NYKN0003', "daily", 'prcp', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['US1NYKN0003', "daily", 'snow', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['US1NYKN0003', "daily", 'snwd', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['US1NYKN0003', "daily", 'dapr', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['US1NYKN0003', "daily", 'mdpr', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['US1NYKN0003', "daily", 'wesd', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['US1NYKN0003', "daily", 'wesf', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['USC00305798', "daily", 'prcp', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['USC00305798', "daily", 'snow', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['USC00305798', "daily", 'snwd', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['USC00305798', "daily", 'tmax', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['USC00305798', "daily", 'tmin', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['USC00305798', "daily", 'tobs', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['USC00305798', "daily", 'wt01', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['USC00305798', "daily", 'wt03', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['USC00305798', "daily", 'wt04', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['USC00305798', "daily", 'wt06', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan],
         ['USC00305798', "daily", 'wt11', pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'), np.nan, np.nan]],
        columns=['station_id', 'dataset', 'parameter', 'date', 'value', 'quality']
    )
    df_expected_values['dataset'] = df_expected_values.dataset.astype('category')

    assert_frame_equal(
        pd.concat(values_result).reset_index(drop=True),
        df_expected_values,
        check_categorical=False
    )
