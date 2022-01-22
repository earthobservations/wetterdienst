# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.unit import OriginUnit, SIUnit
from wetterdienst.provider.dwd.forecast.metadata.parameter import DwdMosmixParameter
from wetterdienst.provider.dwd.forecast.metadata.unit import DwdMosmixUnit
from wetterdienst.provider.dwd.observation.metadata.parameter import (
    DwdObservationDatasetTree,
    DwdObservationParameter,
)
from wetterdienst.provider.dwd.observation.metadata.unit import DwdObservationUnit
from wetterdienst.provider.eccc.observation.metadata.dataset import (
    EcccObservationParameter,
)
from wetterdienst.provider.eccc.observation.metadata.unit import EcccObservationUnit
from wetterdienst.provider.noaa.ghcn import NoaaGhcnParameter
from wetterdienst.provider.noaa.ghcn.unit import NoaaGhcnUnit

ORIGIN_UNITS = [unit.value for unit in OriginUnit]
SI_UNITS = [unit.value for unit in SIUnit]


@pytest.mark.parametrize(
    "parameter_enum,is_ds_tree",
    (
        (DwdObservationParameter, False),
        (DwdObservationDatasetTree, True),
        (DwdObservationUnit, True),
        (DwdMosmixParameter, False),
        (DwdMosmixUnit, False),
        (EcccObservationParameter, False),
        (EcccObservationUnit, False),
        (NoaaGhcnParameter, False),
        (NoaaGhcnUnit, False),
    ),
)
def test_parameter_names(parameter_enum, is_ds_tree):
    """Test parameter and dataset tree enums for consistent parameter naming following the
    core Parameter enum. Due to equal structure units are also tested here"""

    def _check_quality_flags(param):
        return param.startswith("QUALITY") or param.startswith("QN")

    parameters = []

    for res in parameter_enum:
        if is_ds_tree:
            for dataset in parameter_enum[res]:
                for parameter in parameter_enum[res][dataset]:
                    parameter_name = parameter.name
                    if not _check_quality_flags(parameter_name):
                        if parameter_name not in Parameter._member_names_:
                            parameters.append(parameter_name)
        else:
            for parameter in parameter_enum[res]:
                parameter_name = parameter.name
                if not _check_quality_flags(parameter_name):
                    if parameter_name not in Parameter._member_names_:
                        parameters.append(parameter_name)

    assert not parameters
