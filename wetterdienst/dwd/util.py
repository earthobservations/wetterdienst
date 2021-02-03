# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from typing import Optional

from wetterdienst.dwd.observations.metadata import DWDObservationParameterSet
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution


def build_parameter_set_identifier(
    parameter_set: DWDObservationParameterSet,
    resolution: Resolution,
    period: Period,
    station_id: str,
    date_range_string: Optional[str] = None,
) -> str:
    """ Create parameter set identifier that is used for storage interactions """
    identifier = (
        f"{parameter_set.value}/{resolution.value}/" f"{period.value}/{station_id}"
    )

    if date_range_string:
        identifier = f"{identifier}/{date_range_string}"

    return identifier
