from typing import Tuple, Union

from wetterdienst.dwd.observations.metadata import (
    DWDObsTimeResolution,
    DWDObsParameter,
    DWDObsParameterSet,
    DWDObsPeriodType,
)
from wetterdienst.dwd.observations.metadata.parameter import DWDObsParameterSetStructure
from wetterdienst.dwd.observations.metadata.parameter_set import (
    TIME_RESOLUTION_PARAMETER_MAPPING,
)
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.exceptions import InvalidEnumeration, InvalidParameter


def create_parameter_to_parameter_set_combination(
    parameter: Union[DWDObsParameter, DWDObsParameterSet],
    time_resolution: DWDObsTimeResolution,
) -> Tuple[Union[DWDObsParameter, DWDObsParameterSet], DWDObsParameterSet]:
    """Function to create a mapping from a requested parameter to a provided parameter
    set which has to be downloaded first to extract the parameter from it"""
    parameter_set_enums = [
        value
        for key, value in DWDObsParameterSetStructure[
            time_resolution.name
        ].__dict__.items()
        if not key.startswith("_")
    ]

    for parameter_set_enum in parameter_set_enums:
        try:
            parameter_ = parse_enumeration_from_template(
                parameter,
                DWDObsParameterSetStructure[time_resolution.name][
                    parameter_set_enum.__name__
                ],
            )

            parameter_set = parse_enumeration_from_template(
                parameter_set_enum.__name__, DWDObsParameterSet
            )

            return parameter_, parameter_set
        except InvalidEnumeration:
            pass

    try:
        parameter_set = parse_enumeration_from_template(parameter, DWDObsParameterSet)
        return parameter_set, parameter_set
    except InvalidEnumeration:
        pass

    raise InvalidParameter(
        f"parameter {parameter} could not be parsed for "
        f"time resolution {time_resolution}"
    )


def check_dwd_observations_parameter_set(
    parameter_set: DWDObsParameterSet,
    time_resolution: DWDObsTimeResolution,
    period_type: DWDObsPeriodType,
) -> bool:
    """
    Function to check for element (alternative name) and if existing return it
    Differs from foldername e.g. air_temperature -> tu
    """
    check = TIME_RESOLUTION_PARAMETER_MAPPING.get(time_resolution, {}).get(
        parameter_set, []
    )

    if period_type not in check:
        return False

    return True


if __name__ == "__main__":
    print(
        create_parameter_to_parameter_set_combination(
            time_resolution=DWDObsTimeResolution.DAILY,
            parameter=DWDObsParameter.DAILY.PRECIPITATION_HEIGHT,
        )
    )
