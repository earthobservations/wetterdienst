# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.observation.metadata import DwdObservationDataset
from wetterdienst.provider.dwd.observation.metadata.dataset import (
    RESOLUTION_DATASET_MAPPING,
)


def check_dwd_observations_dataset(
    dataset: DwdObservationDataset,
    resolution: Resolution,
    period: Period,
) -> bool:
    """
    Function to check for element (alternative name) and if existing return it
    Differs from folder name e.g. air_temperature -> tu
    """
    check = RESOLUTION_DATASET_MAPPING.get(resolution, {}).get(dataset, [])

    if period not in check:
        return False

    return True
