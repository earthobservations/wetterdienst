"""
=====
About
=====
Acquire station information from DWD.

"""
import logging

from datetime import datetime
from wetterdienst import DWDObservationSites
from wetterdienst import DWDParameterSet, PeriodType, TimeResolution

log = logging.getLogger()


def station_example():

    sites = DWDObservationSites(
        parameter=DWDParameterSet.TEMPERATURE_AIR,
        time_resolution=TimeResolution.HOURLY,
        period_type=PeriodType.RECENT,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 20)
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
