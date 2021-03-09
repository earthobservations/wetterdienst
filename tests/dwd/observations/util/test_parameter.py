# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.dwd.observations.metadata import (
    DwdObservationDataset,
    DwdObservationParameter,
)
from wetterdienst.dwd.observations.metadata.parameter import (
    DwdObservationDatasetStructure,
)
from wetterdienst.dwd.observations.util.parameter import (
    check_dwd_observations_dataset,
    create_parameter_to_dataset_combination,
)
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution


def test_create_parameter_to_parameter_set_combination():
    par_to_par_set_combination = create_parameter_to_dataset_combination(
        parameter=DwdObservationParameter.MINUTE_10.PRECIPITATION_HEIGHT,
        resolution=Resolution.MINUTE_10,
    )

    assert par_to_par_set_combination == (
        DwdObservationDatasetStructure.MINUTE_10.PRECIPITATION.PRECIPITATION_HEIGHT,
        DwdObservationDataset.PRECIPITATION,
    )

    par_to_par_set_combination = create_parameter_to_dataset_combination(
        parameter=DwdObservationDatasetStructure.MINUTE_10.PRECIPITATION.PRECIPITATION_HEIGHT,
        resolution=Resolution.MINUTE_10,
    )

    assert par_to_par_set_combination == (
        DwdObservationDatasetStructure.MINUTE_10.PRECIPITATION.PRECIPITATION_HEIGHT,
        DwdObservationDataset.PRECIPITATION,
    )

    par_to_par_set_combination = create_parameter_to_dataset_combination(
        parameter=DwdObservationDataset.PRECIPITATION,
        resolution=Resolution.MINUTE_10,
    )

    assert par_to_par_set_combination == (
        DwdObservationDataset.PRECIPITATION,
        DwdObservationDataset.PRECIPITATION,
    )


def test_check_parameters():
    assert check_dwd_observations_dataset(
        DwdObservationDataset.PRECIPITATION,
        Resolution.MINUTE_10,
        Period.HISTORICAL,
    )
    assert not check_dwd_observations_dataset(
        DwdObservationDataset.CLIMATE_SUMMARY,
        Resolution.MINUTE_1,
        Period.HISTORICAL,
    )
