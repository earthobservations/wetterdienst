from typing import Tuple, Union

from wetterdienst.dwd.observations.metadata import (
    DWDObservationParameter,
    DWDObservationParameterSet,
    DWDObservationPeriod,
    DWDObservationResolution,
)
from wetterdienst.dwd.observations.metadata.parameter import (
    DWDObservationParameterSetStructure,
)
from wetterdienst.dwd.observations.metadata.parameter_set import (
    RESOLUTION_PARAMETER_MAPPING,
)
from wetterdienst.exceptions import InvalidEnumeration, InvalidParameter
from wetterdienst.util.enumeration import parse_enumeration_from_template


def create_parameter_to_parameter_set_combination(
    parameter: Union[DWDObservationParameter, DWDObservationParameterSet],
    resolution: DWDObservationResolution,
) -> Tuple[
    Union[DWDObservationParameter, DWDObservationParameterSet],
    DWDObservationParameterSet,
]:
    """Function to create a mapping from a requested parameter to a provided parameter
    set which has to be downloaded first to extract the parameter from it"""
    parameter_set_enums = [
        value
        for key, value in DWDObservationParameterSetStructure[
            resolution.name
        ].__dict__.items()
        if not key.startswith("_")
    ]

    for parameter_set_enum in parameter_set_enums:
        try:
            parameter_ = parse_enumeration_from_template(
                parameter,
                DWDObservationParameterSetStructure[resolution.name][
                    parameter_set_enum.__name__
                ],
            )

            parameter_set = parse_enumeration_from_template(
                parameter_set_enum.__name__, DWDObservationParameterSet
            )

            return parameter_, parameter_set
        except InvalidEnumeration:
            pass

    try:
        parameter_set = parse_enumeration_from_template(
            parameter, DWDObservationParameterSet
        )
        return parameter_set, parameter_set
    except InvalidEnumeration:
        pass

    raise InvalidParameter(
        f"parameter {parameter} could not be parsed for "
        f"time resolution {resolution}"
    )


def check_dwd_observations_parameter_set(
    parameter_set: DWDObservationParameterSet,
    resolution: DWDObservationResolution,
    period: DWDObservationPeriod,
) -> bool:
    """
    Function to check for element (alternative name) and if existing return it
    Differs from foldername e.g. air_temperature -> tu
    """
    check = RESOLUTION_PARAMETER_MAPPING.get(resolution, {}).get(parameter_set, [])

    if period not in check:
        return False

    return True
