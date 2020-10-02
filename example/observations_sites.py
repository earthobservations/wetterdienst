"""
=====
About
=====
Acquire station information from DWD.

"""
import logging

from datetime import datetime
from wetterdienst import DWDObservationSites
from wetterdienst import Parameter, PeriodType, TimeResolution

log = logging.getLogger()


def station_example():

    sites = DWDObservationSites(
        Parameter.TEMPERATURE_AIR,
        TimeResolution.HOURLY,
        PeriodType.RECENT,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20)
    )

    df = sites.nearby_radius(
        latitude=50.0,
        longitude=8.9,
        max_distance_in_km=30
    )

    print(df)


def main():
    logging.basicConfig(level=logging.INFO)
    station_example()


if __name__ == "__main__":
    main()
