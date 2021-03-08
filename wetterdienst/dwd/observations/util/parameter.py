# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from typing import Tuple, Union

from wetterdienst.dwd.observations.metadata import (
    DwdObservationParameter,
    DwdObservationParameterSet,
)
from wetterdienst.dwd.observations.metadata.parameter import (
    PARAMETER_TO_PARAMETER_MAPPING,
)
from wetterdienst.dwd.observations.metadata.parameter_set import (
    RESOLUTION_PARAMETER_MAPPING,
)
from wetterdienst.exceptions import InvalidEnumeration, InvalidParameter
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.util.enumeration import parse_enumeration_from_template


def create_parameter_to_parameter_set_combination(
    parameter: Union[DwdObservationParameter, DwdObservationParameterSet],
    resolution: Resolution,
) -> Tuple[
    Union[DwdObservationParameter, DwdObservationParameterSet],
    DwdObservationParameterSet,
]:
    """Function to create a mapping from a requested parameter to a provided parameter
    set which has to be downloaded first to extract the parameter from it"""
    try:
        parameter_ = parse_enumeration_from_template(
            parameter, DwdObservationParameter[resolution.name]
        )

        parameter = PARAMETER_TO_PARAMETER_MAPPING[resolution][parameter_]

        return parameter, parse_enumeration_from_template(
            parameter.__class__.__name__, DwdObservationParameterSet
        )
    except (KeyError, InvalidEnumeration):
        try:
            parameter_set = parse_enumeration_from_template(
                parameter, DwdObservationParameterSet
            )

            return parameter_set, parameter_set
        except InvalidEnumeration:
            raise InvalidParameter(
                f"parameter {parameter} could not be parsed for "
                f"time resolution {resolution}"
            )


def check_dwd_observations_parameter_set(
    parameter_set: DwdObservationParameterSet,
    resolution: Resolution,
    period: Period,
) -> bool:
    """
    Function to check for element (alternative name) and if existing return it
    Differs from foldername e.g. air_temperature -> tu
    """
    check = RESOLUTION_PARAMETER_MAPPING.get(resolution, {}).get(parameter_set, [])

    if period not in check:
        return False

    return True
