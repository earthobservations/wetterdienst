import pytest

from wetterdienst.additionals.functions import check_parameters, retrieve_time_resolution_from_filename, \
    retrieve_parameter_from_filename, retrieve_period_type_from_filename, determine_parameters, \
    cast_to_list, parse_enumeration_from_template
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.exceptions.invalid_parameter_exception import InvalidParameter


def test_check_parameters():
    assert check_parameters(Parameter.PRECIPITATION, TimeResolution.MINUTE_10, PeriodType.HISTORICAL)
    assert not check_parameters(Parameter.CLIMATE_SUMMARY, TimeResolution.MINUTE_1, PeriodType.HISTORICAL)


def test_retrieve_time_resolution_from_filename():
    assert retrieve_time_resolution_from_filename('10minutenwerte_2019.csv') == TimeResolution.MINUTE_10
    assert retrieve_time_resolution_from_filename('1minutenwerte_2019.csv') == TimeResolution.MINUTE_1
    assert retrieve_time_resolution_from_filename('tageswerte__2019.csv') == TimeResolution.DAILY
    assert retrieve_time_resolution_from_filename('tageswerte2019.csv') is None


def test_retrieve_parameter_from_filename():
    assert retrieve_parameter_from_filename('bidb_!!_st_.xml', TimeResolution.HOURLY) == Parameter.SOLAR
    assert retrieve_parameter_from_filename('10000_historical_nieder_.txt', TimeResolution.MINUTE_1) \
        == Parameter.PRECIPITATION
    assert retrieve_parameter_from_filename('klima_climate_kl_.csv', TimeResolution.DAILY) == Parameter.CLIMATE_SUMMARY
    assert retrieve_parameter_from_filename('klima_climate_kl_.csv', TimeResolution.MINUTE_1) is None


def test_retrieve_period_type_from_filename():
    assert retrieve_period_type_from_filename('_hist.xml') == PeriodType.HISTORICAL
    assert retrieve_period_type_from_filename('no_period_type') is None


def test_determine_parameters():
    assert determine_parameters('10minutenwerte_hist_nieder_') == (Parameter.PRECIPITATION,
                                                                   TimeResolution.MINUTE_10,
                                                                   PeriodType.HISTORICAL)


def test_cast_to_list():
    assert cast_to_list("abc") == ["abc"]
    assert cast_to_list(1) == [1]
    assert cast_to_list(PeriodType.HISTORICAL) == [PeriodType.HISTORICAL]


def test_parse_enumeration_from_template():
    assert parse_enumeration_from_template("climate_summary", Parameter) == Parameter.CLIMATE_SUMMARY
    assert parse_enumeration_from_template("kl", Parameter) == Parameter.CLIMATE_SUMMARY

    with pytest.raises(InvalidParameter):
        parse_enumeration_from_template("climate", Parameter)
