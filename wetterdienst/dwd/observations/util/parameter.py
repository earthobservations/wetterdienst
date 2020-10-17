from typing import Tuple, Union, Type

from wetterdienst import TimeResolution
from wetterdienst.dwd.observations.metadata.parameter import DWDObservationParameter
from wetterdienst.dwd.observations.metadata.parameter_set import DWDParameterSet
from wetterdienst.dwd.util import parse_enumeration_from_template
from wetterdienst.exceptions import InvalidEnumeration, InvalidParameter


def create_parameter_to_parameter_set_combination(
    parameter: Union[Type[DWDObservationParameter], DWDParameterSet],
    time_resolution: TimeResolution,
) -> Tuple[Union[DWDObservationParameter, DWDParameterSet], DWDParameterSet]:
    """Function to create a mapping from a requested parameter to a provided parameter
    set which has to be downloaded first to extract the parameter from it"""
    parameter_set_enums = [
        value
        for key, value in DWDObservationParameter[time_resolution.name].__dict__.items()
        if not key.startswith("_")
    ]

    for parameter_set_enum in parameter_set_enums:
        try:
            parameter_ = parse_enumeration_from_template(parameter, parameter_set_enum)
            parameter_set = parse_enumeration_from_template(
                parameter_set_enum.__name__, DWDParameterSet
            )
            return parameter_, parameter_set
        except InvalidEnumeration:
            pass

    try:
        parameter_set = parse_enumeration_from_template(parameter, DWDParameterSet)
        return parameter_set, parameter_set
    except InvalidEnumeration:
        pass

    raise InvalidParameter(
        f"parameter {parameter} could not be parsed for "
        f"time resolution {time_resolution}"
    )
