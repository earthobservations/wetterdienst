import pytest
from python_dwd.dwd_station_request import DWDStationRequest, parse_parameter_from_value, \
    find_any_one_word_from_wordlist, parse_station_id_to_list_of_integers, PARAMETER_WORDLIST_MAPPING,\
    PERIODTYPE_WORDLIST_MAPPING, TIMERESOLUTION_WORDLIST_MAPPING, StartDateEndDateError
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


def test_parse_parameter_from_value():
    assert parse_parameter_from_value("cl", PARAMETER_WORDLIST_MAPPING) == Parameter.CLIMATE_SUMMARY
    assert parse_parameter_from_value("sonne_dauer", PARAMETER_WORDLIST_MAPPING) == Parameter.SUNSHINE_DURATION

    assert parse_parameter_from_value("rec", PERIODTYPE_WORDLIST_MAPPING) == PeriodType.RECENT
    assert parse_parameter_from_value("jetzt", PERIODTYPE_WORDLIST_MAPPING) == PeriodType.NOW

    assert parse_parameter_from_value("daily", TIMERESOLUTION_WORDLIST_MAPPING) == TimeResolution.DAILY
    assert parse_parameter_from_value("monat", TIMERESOLUTION_WORDLIST_MAPPING) == TimeResolution.MONTHLY


def test_find_any_one_word_from_wordlist():
    assert not find_any_one_word_from_wordlist(["letters"], [["letters"], ["else"]])
    assert find_any_one_word_from_wordlist(["letters"], [["letters"], ["letters"]])

    assert find_any_one_word_from_wordlist(["a_unique", "b_unique"], [["some", "thing", "a"], ["some", "thing", "b"]])


def test_parse_station_id_to_list_of_integers():
    # @todo
    assert True


def test_dwd_station_request():
    assert DWDStationRequest(station_id=[1], time_resolution="daily", parameter="cl", period_type="hist") \
           == [[1], Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, [PeriodType.HISTORICAL], None, None]

    assert DWDStationRequest(station_id=[1],
                             parameter=Parameter.CLIMATE_SUMMARY,
                             period_type=PeriodType.HISTORICAL,
                             time_resolution=TimeResolution.DAILY) == \
           [[1], Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, [PeriodType.HISTORICAL], None, None]


def test_station_id():
    with pytest.raises(ValueError):
        DWDStationRequest(station_id="test",
                          parameter=Parameter.CLIMATE_SUMMARY,
                          period_type=PeriodType.HISTORICAL,
                          time_resolution=TimeResolution.DAILY)


def test_parameter_enumerations():
    with pytest.raises(ValueError):
        DWDStationRequest(station_id=[1],
                          parameter="cl",
                          period_type="now",
                          time_resolution="daily")


def test_time_input():
    with pytest.raises(ValueError):
        DWDStationRequest(station_id=[1],
                          parameter=Parameter.CLIMATE_SUMMARY,
                          time_resolution=TimeResolution.DAILY,
                          start_date="1971-01-01")

        with pytest.raises(ValueError):
            DWDStationRequest(station_id=[1],
                              parameter=Parameter.CLIMATE_SUMMARY,
                              time_resolution=TimeResolution.DAILY,
                              period_type=PeriodType.HISTORICAL,
                              start_date="1971-01-01")

    with pytest.raises(StartDateEndDateError):
        DWDStationRequest(station_id=[1],
                          parameter=Parameter.CLIMATE_SUMMARY,
                          time_resolution=TimeResolution.DAILY,
                          start_date="1971-01-01",
                          end_date="1951-01-01")
