import numpy as np
import pandas as pd
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
        [['US1NYKN0003', 'daily', 'precipitation_height',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['US1NYKN0003', 'daily', 'snow_depth_new',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['US1NYKN0003', 'daily', 'snow_depth',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['US1NYKN0003', 'daily', 'count_days_multiday_precipitation',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['US1NYKN0003', 'daily', 'precipitation_height_multiday',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['US1NYKN0003', 'daily', 'water_equivalent_snow_depth',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['US1NYKN0003', 'daily', 'water_equivalent_snow_depth_new',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['USC00305798', 'daily', 'precipitation_height',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['USC00305798', 'daily', 'snow_depth_new',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['USC00305798', 'daily', 'snow_depth',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['USC00305798', 'daily', 'temperature_air_max_200',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['USC00305798', 'daily', 'temperature_air_min_200',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['USC00305798', 'daily', 'temperature_air_200',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['USC00305798', 'daily', 'weather_type_fog',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['USC00305798', 'daily', 'weather_type_thunder',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['USC00305798', 'daily', 'weather_type_ice_sleet_snow_hail',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['USC00305798', 'daily', 'weather_type_glaze_rime',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan],
         ['USC00305798', 'daily', 'weather_type_high_damaging_winds',
          pd.Timestamp('2020-01-01 05:00:00+0000', tz='UTC'),
          np.nan, np.nan]],
        columns=['station_id', 'dataset', 'parameter', 'date', 'value', 'quality']
    )
    df_expected_values['dataset'] = df_expected_values.dataset.astype('category')

    assert_frame_equal(
        pd.concat(values_result).reset_index(drop=True),
        df_expected_values,
        check_categorical=False
    )
