import pytest
from python_dwd.request_dwd import DWDRequest
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


def test_station_id():
    with pytest.raises(TypeError):
        DWDRequest(station_id="test",
                   parameter=Parameter.CLIMATE_SUMMARY,
                   period_type=PeriodType.HISTORICAL,
                   time_resolution=TimeResolution.DAILY)

    with pytest.raises(ValueError):
        DWDRequest(station_id=["test"],
                   parameter=Parameter.CLIMATE_SUMMARY,
                   period_type=PeriodType.HISTORICAL,
                   time_resolution=TimeResolution.DAILY)


def test_parameter_enumerations():
    with pytest.raises(ValueError):
        DWDRequest(station_id=[1048],
                   parameter=Parameter.CLIMATE_SUMMARY,
                   period_type=PeriodType.NOW,
                   time_resolution=TimeResolution.DAILY)


def test_time_input():
    with pytest.raises(ValueError):
        DWDRequest(station_id=[1048],
                   parameter=Parameter.CLIMATE_SUMMARY,
                   period_type=PeriodType.HISTORICAL,
                   time_resolution=TimeResolution.DAILY,
                   start_date="1971-01-01")

    with pytest.raises(ValueError):
        DWDRequest(station_id=[1048],
                   parameter=Parameter.CLIMATE_SUMMARY,
                   period_type=PeriodType.HISTORICAL,
                   start_date="1971-01-01",
                   end_date="1951-01-01")
