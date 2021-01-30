# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE.rst for more info.
"""
=====
About
=====
Acquire station information from DWD.

"""
import logging
from datetime import datetime

from wetterdienst.dwd.observations import (
    DWDObservationParameterSet,
    DWDObservationPeriod,
    DWDObservationResolution,
    DWDObservationStations,
)

log = logging.getLogger()


def station_example():
    stations = DWDObservationStations(
        parameter_set=DWDObservationParameterSet.TEMPERATURE_AIR,
        resolution=DWDObservationResolution.HOURLY,
        period=DWDObservationPeriod.RECENT,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 20),
    )

    df = stations.nearby_radius(latitude=50.0, longitude=8.9, max_distance_in_km=30)

    print(df)


def main():
    logging.basicConfig(level=logging.INFO)
    station_example()


if __name__ == "__main__":
    main()
