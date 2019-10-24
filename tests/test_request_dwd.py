import pytest
from python_dwd.request_dwd import DWDRequest, extract_numbers_from_string
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


def test_extract_numbers_from_string():
    with pytest.raises(TypeError):
        extract_numbers_from_string(string=1, number_type="float", decimal=".")

    with pytest.raises(TypeError):
        extract_numbers_from_string(string="abc", number_type="str", decimal=".")

    with pytest.raises(ValueError):
        extract_numbers_from_string(string="1234", number_type="int", decimal=";")

    with pytest.raises(ValueError):
        extract_numbers_from_string(string="1234.5", number_type="int", decimal=".")

    assert extract_numbers_from_string(string="abc", number_type="float", decimal=".") is []

    assert extract_numbers_from_string(string=" B 123 CDE 45", number_type="int", decimal="") == [123, 45]

    assert extract_numbers_from_string(string=".123.", number_type="int", decimal=".") == [123]

    assert extract_numbers_from_string(string=".123.", number_type="float", decimal=".") == [123.0]


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
