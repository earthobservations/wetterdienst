# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====
Summarize values from nearby stations.

"""  # Noqa:D205,D400

import logging

from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)

log = logging.getLogger()


def summarize_example():
    """Retrieve temperature data by DWD and filter by sql statement."""
    request = DwdObservationRequest(
        parameters=("hourly", "temperature_air", "temperature_air_mean_2m"),
        start_date="2019-01-01",
        end_date="2020-01-01",
    )

    frankfurt = (50.11, 8.68)
    values = request.summarize(frankfurt)

    print(values.df)


def main():
    """Run example."""
    logging.basicConfig(level=logging.INFO)
    summarize_example()


if __name__ == "__main__":
    main()
