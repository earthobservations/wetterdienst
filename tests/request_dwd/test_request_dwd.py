import pytest
from python_dwd.request_dwd import DWDRequest, extract_numbers_from_string, FuzzyExtractor
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

    assert extract_numbers_from_string(string="abc", number_type="float", decimal=".") == []

    assert extract_numbers_from_string(string=" B 123 CDE 45", number_type="int", decimal="") == [123, 45]

    assert extract_numbers_from_string(string=".123.", number_type="int", decimal=".") == [123]

    assert extract_numbers_from_string(string=".123.", number_type="float", decimal=".") == [123.0]


def test_fuzzy_extractor():
    with pytest.raises(TypeError):
        FuzzyExtractor("station_id", int)

    with pytest.raises(AssertionError):
        FuzzyExtractor("unknownparameter", "1_minute")

    with pytest.raises(ValueError):
        FuzzyExtractor("station_id", ["AB1CD2"]).extract_parameter_from_value()

    assert FuzzyExtractor("station_id", ["S1", "S2", "S3"]).extract_parameter_from_value() == [1, 2, 3]

    assert FuzzyExtractor("time_resolution", "1_minute").extract_parameter_from_value() == TimeResolution.MINUTE_1

    assert FuzzyExtractor("time_resolution", "10_minute").extract_parameter_from_value() == TimeResolution.MINUTE_10

    assert str(FuzzyExtractor("start_date", "19710101").extract_parameter_from_value().date()) == "1971-01-01"


def test_dwd_request():
    assert DWDRequest(station_id="1", parameter="cl", period_type="hist", time_resolution="daily") \
           == [[1], Parameter.CLIMATE_SUMMARY, PeriodType.HISTORICAL, [TimeResolution.DAILY], None, None]


def test_station_id():
    with pytest.raises(ValueError):
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
                   parameter="cl",
                   period_type="now",
                   time_resolution="daily")


def test_time_input():
    with pytest.raises(ValueError):
        DWDRequest(station_id=[1048],
                   parameter="cl",
                   period_type="hist",
                   start_date="1971-01-01")

    with pytest.raises(ValueError):
        DWDRequest(station_id=[1048],
                   parameter="kl",
                   period_type="hist",
                   start_date="1971-01-01",
                   end_date="1951-01-01")
