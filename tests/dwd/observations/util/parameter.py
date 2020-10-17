from wetterdienst import TimeResolution, DWDParameterSet
from wetterdienst.dwd.observations.metadata.parameter import DWDObservationParameter
from wetterdienst.dwd.observations.util.parameter import (
    create_parameter_to_parameter_set_combination,
)


def test_create_parameter_to_parameter_set_combination():
    par_to_par_set_combination = create_parameter_to_parameter_set_combination(
        parameter=DWDObservationParameter.MINUTE_10.PRECIPITATION.PRECIPITATION_HEIGHT,
        time_resolution=TimeResolution.MINUTE_10,
    )

    assert par_to_par_set_combination == (
        DWDObservationParameter.MINUTE_10.PRECIPITATION.PRECIPITATION_HEIGHT,
        DWDParameterSet.PRECIPITATION,
    )
