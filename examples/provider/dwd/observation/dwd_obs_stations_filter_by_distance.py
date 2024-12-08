# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====
Acquire station information from DWD.

"""  # Noqa:D205,D400

import logging
from datetime import datetime

from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)

log = logging.getLogger()


def stations_filter_by_distance_example():
    """Retrieve stations_result of DWD that measure temperature."""
    stations = DwdObservationRequest(
        parameters=("hourly", "temperature_air"),
        period="recent",
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 20),
    )

    result = stations.filter_by_distance(latlon=(50.0, 8.9), distance=30)

    print(result.df)


def main():
    """Run example."""
    logging.basicConfig(level=logging.INFO)
    stations_filter_by_distance_example()


if __name__ == "__main__":
    main()
