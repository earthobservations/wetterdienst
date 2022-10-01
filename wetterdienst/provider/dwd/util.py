# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from typing import Optional

from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.observation.metadata.dataset import DwdObservationDataset


def build_parameter_set_identifier(
    dataset: DwdObservationDataset,
    resolution: Resolution,
    period: Period,
    station_id: str,
    date_range_string: Optional[str] = None,
) -> str:
    """Create parameter set identifier that is used for storage interactions"""
    identifier = f"{dataset.value}/{resolution.value}/" f"{period.value}/{station_id}"

    if date_range_string:
        return f"{identifier}/{date_range_string}"

    return identifier
