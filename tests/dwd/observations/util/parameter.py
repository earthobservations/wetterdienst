from wetterdienst.dwd.observations.metadata import (
    DWDObservationParameter,
    DWDObservationParameterSet,
    DWDObsPeriodType,
    DWDObsTimeResolution,
)
from wetterdienst.dwd.observations.util.parameter import (
    check_dwd_observations_parameter_set,
    create_parameter_to_parameter_set_combination,
)


def test_create_parameter_to_parameter_set_combination():
    par_to_par_set_combination = create_parameter_to_parameter_set_combination(
        parameter=DWDObservationParameter.MINUTE_10.PRECIPITATION.PRECIPITATION_HEIGHT,
        resolution=DWDObsTimeResolution.MINUTE_10,
    )

    assert par_to_par_set_combination == (
        DWDObservationParameter.MINUTE_10.PRECIPITATION.PRECIPITATION_HEIGHT,
        DWDObservationParameterSet.PRECIPITATION,
    )


def test_check_parameters():
    assert check_dwd_observations_parameter_set(
        DWDObservationParameterSet.PRECIPITATION,
        DWDObsTimeResolution.MINUTE_10,
        DWDObsPeriodType.HISTORICAL,
    )
    assert not check_dwd_observations_parameter_set(
        DWDObservationParameterSet.CLIMATE_SUMMARY,
        DWDObsTimeResolution.MINUTE_1,
        DWDObsPeriodType.HISTORICAL,
    )
