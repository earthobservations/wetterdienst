# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from typing import Optional

from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.observation.metadata.dataset import (
    RESOLUTION_DATASET_MAPPING,
    DwdObservationDataset,
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


def build_parameter_set_identifier(
    dataset: DwdObservationDataset,
    resolution: Resolution,
    period: Period,
    station_id: str,
    date_range_string: Optional[str] = None,
) -> str:
    """Create parameter set identifier that is used for storage interactions"""
    identifier = f"{dataset.value}/{resolution.value}/{period.value}/{station_id}"

    if date_range_string:
        return f"{identifier}/{date_range_string}"

    return identifier
