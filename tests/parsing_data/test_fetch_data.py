import pytest

from python_dwd import collect_dwd_data
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


@pytest.mark.remote
def test_fetch_and_parse_dwd_data():
    data = collect_dwd_data(
        station_ids=[1048],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.RECENT,
    )

    assert list(data.columns.values) == [
        'STATION_ID',
        'DATE',
        'QN_3',
        'WIND_GUST_MAX',
        'WIND_VELOCITY',
        'QN_4',
        'PRECIPITATION_HEIGHT',
        'PRECIPITATION_FORM',
        'SUNSHINE_DURATION',
        'SNOW_DEPTH',
        'CLOUD_COVER',
        'VAPOR_PRESSURE',
        'PRESSURE',
        'TEMPERATURE',
        'HUMIDITY',
        'TEMPERATURE_MAX_200',
        'TEMPERATURE_MIN_200',
        'TEMPERATURE_MIN_005',
    ]
