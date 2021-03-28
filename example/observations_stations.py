# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====
Acquire station information from DWD.

"""
import logging
from datetime import datetime

from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)

log = logging.getLogger()


def station_example():
    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 20),
        tidy=True,
        humanize=True,
    )

    df = stations.nearby_radius(latitude=50.0, longitude=8.9, max_distance_in_km=30).df

    print(df)


def main():
    logging.basicConfig(level=logging.INFO)
    station_example()


if __name__ == "__main__":
    main()
