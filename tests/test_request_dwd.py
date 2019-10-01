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
