from wetterdienst.dwd.observations.metadata import (
    DWDObsTimeResolution,
    DWDObsParameterSet,
    DWDObsParameter,
    DWDObsPeriodType,
)
from wetterdienst.dwd.observations.util.parameter import (
    create_parameter_to_parameter_set_combination,
    check_dwd_observations_parameter_set,
)


def test_create_parameter_to_parameter_set_combination():
    par_to_par_set_combination = create_parameter_to_parameter_set_combination(
        parameter=DWDObsParameter.MINUTE_10.PRECIPITATION.PRECIPITATION_HEIGHT,
        time_resolution=DWDObsTimeResolution.MINUTE_10,
    )

    assert par_to_par_set_combination == (
        DWDObsParameter.MINUTE_10.PRECIPITATION.PRECIPITATION_HEIGHT,
        DWDObsParameterSet.PRECIPITATION,
    )


def test_check_parameters():
    assert check_dwd_observations_parameter_set(
        DWDObsParameterSet.PRECIPITATION,
        DWDObsTimeResolution.MINUTE_10,
        DWDObsPeriodType.HISTORICAL,
    )
    assert not check_dwd_observations_parameter_set(
        DWDObsParameterSet.CLIMATE_SUMMARY,
        DWDObsTimeResolution.MINUTE_1,
        DWDObsPeriodType.HISTORICAL,
    )
