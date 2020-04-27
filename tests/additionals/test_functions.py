from python_dwd.additionals.functions import check_parameters, retrieve_time_resolution_from_filename,\
    retrieve_parameter_from_filename, retrieve_period_type_from_filename, determine_parameters
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.enumerations.parameter_enumeration import Parameter


def test_check_parameters():
    assert check_parameters(Parameter.PRECIPITATION, TimeResolution.MINUTE_10, PeriodType.HISTORICAL)


def test_retrieve_time_resolution_from_filename():
    assert retrieve_time_resolution_from_filename('10minutenwerte_2019.csv') == TimeResolution.MINUTE_10
    assert retrieve_time_resolution_from_filename('1minutenwerte_2019.csv') == TimeResolution.MINUTE_1
    assert retrieve_time_resolution_from_filename('tageswerte__2019.csv') == TimeResolution.DAILY
    assert retrieve_time_resolution_from_filename('tageswerte2019.csv') == None
    


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
