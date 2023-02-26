# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.unit import OriginUnit, SIUnit
from wetterdienst.provider.dwd.mosmix.api import DwdMosmixDataset
from wetterdienst.provider.dwd.mosmix.metadata.parameter import DwdMosmixParameter
from wetterdienst.provider.dwd.mosmix.metadata.unit import DwdMosmixUnit
from wetterdienst.provider.dwd.observation import DwdObservationDataset
from wetterdienst.provider.dwd.observation.metadata.parameter import (
    DwdObservationParameter,
)
from wetterdienst.provider.dwd.observation.metadata.unit import DwdObservationUnit
from wetterdienst.provider.eccc.observation.metadata.parameter import (
    EcccObservationDataset,
    EcccObservationParameter,
)
from wetterdienst.provider.eccc.observation.metadata.unit import EcccObservationUnit
from wetterdienst.provider.environment_agency.hydrology.api import (
    EaHydrologyParameter,
    EaHydrologyUnit,
)
from wetterdienst.provider.geosphere.observation import GeosphereObservationParameter
from wetterdienst.provider.geosphere.observation.api import GeosphereObservationUnit
from wetterdienst.provider.noaa.ghcn import NoaaGhcnParameter
from wetterdienst.provider.noaa.ghcn.api import NoaaGhcnDataset
from wetterdienst.provider.noaa.ghcn.unit import NoaaGhcnUnit
from wetterdienst.provider.nws.observation import NwsObservationParameter
from wetterdienst.provider.nws.observation.api import NwsObservationUnit
from wetterdienst.provider.wsv.pegel.api import WsvPegelParameter, WsvPegelUnit

ORIGIN_UNITS = [unit.value for unit in OriginUnit]
SI_UNITS = [unit.value for unit in SIUnit]


@pytest.mark.parametrize(
    "parameter_enum",
    (
        DwdObservationParameter,
        DwdObservationUnit,
        DwdMosmixParameter,
        DwdMosmixUnit,
        EcccObservationParameter,
        EcccObservationUnit,
        NoaaGhcnParameter,
        NoaaGhcnUnit,
        WsvPegelParameter,
        WsvPegelUnit,
        EaHydrologyParameter,
        EaHydrologyUnit,
        NwsObservationParameter,
        NwsObservationUnit,
        GeosphereObservationParameter,
        GeosphereObservationUnit,
    ),
)
def test_parameter_names(parameter_enum):
    """Test parameter and dataset tree enums for consistent parameter naming following the
    core Parameter enum. Due to equal structure units are also tested here"""

    def _check_quality_flags(param):
        return param.startswith("QUALITY") or param.startswith("QN")

    parameters = []

    for res in parameter_enum:
        for dataset in res:

            if hasattr(dataset, "name"):
                continue

            for parameter in dataset:
                parameter_name = parameter.name
                if not _check_quality_flags(parameter_name):
                    if parameter_name not in Parameter._member_names_:
                        parameters.append(parameter_name)

        for parameter in res:
            try:
                parameter_name = parameter.name
            except AttributeError:
                continue
            if not _check_quality_flags(parameter_name):
                if parameter_name not in Parameter._member_names_:
                    parameters.append(parameter_name)

    assert not parameters


@pytest.mark.parametrize(
    "parameter_enum,unit_enum",
    (
        (DwdObservationParameter, DwdObservationUnit),
        (DwdMosmixParameter, DwdMosmixUnit),
        (EcccObservationParameter, EcccObservationUnit),
        (NoaaGhcnParameter, NoaaGhcnUnit),
        (WsvPegelParameter, WsvPegelUnit),
        (EaHydrologyParameter, EaHydrologyUnit),
        (NwsObservationParameter, NwsObservationUnit),
        (GeosphereObservationParameter, GeosphereObservationUnit),
    ),
)
def test_parameter_unit_alignment(parameter_enum, unit_enum):
    """Test parameter and unit enums for alignment"""
    for res in parameter_enum:
        # check existence of res in unit enum
        assert unit_enum[res.__name__]

        for dataset in res:
            if hasattr(dataset, "name"):
                continue

            assert unit_enum[res.__name__][dataset.__name__]

            for parameter in dataset:
                parameter_name = parameter.name

                # check existence of parameter in unit enum
                assert unit_enum[res.__name__][dataset.__name__][parameter_name]


@pytest.mark.parametrize(
    "parameter_enum,dataset_enum",
    (
        (DwdObservationParameter, DwdObservationDataset),
        (DwdMosmixParameter, DwdMosmixDataset),
        (EcccObservationParameter, EcccObservationDataset),
        (NoaaGhcnParameter, NoaaGhcnDataset),
    ),
)
def test_parameter_dataset_alignment(parameter_enum, dataset_enum):
    """Test parameter and dataset enums for alignment. Specifically the datasets that are used in the parameter enum
    should match the actual dataset enumeration names. Also, no parameter should have a name similar to a dataset.
    """
    dataset_names = [ds.name for ds in dataset_enum]

    for res in parameter_enum:
        for dataset in res:
            if hasattr(dataset, "name"):
                continue

            assert dataset.__name__ in dataset_names

            for parameter in dataset:
                parameter_name = parameter.name
                assert parameter_name not in dataset_names

        for parameter in res:
            try:
                parameter_name = parameter.name
            except AttributeError:
                continue

            assert parameter_name not in dataset_names
