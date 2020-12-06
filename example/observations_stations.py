"""
=====
About
=====
Acquire station information from DWD.

"""
import logging

from datetime import datetime
from wetterdienst.dwd.observations import (
    DWDObservationStations,
    DWDObservationParameterSet,
    DWDObservationPeriod,
    DWDObservationResolution,
)

log = logging.getLogger()


def station_example():

    sites = DWDObservationStations(
        parameter_set=DWDObservationParameterSet.TEMPERATURE_AIR,
        resolution=DWDObservationResolution.HOURLY,
        period=DWDObservationPeriod.RECENT,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 20),
    )

    df = sites.nearby_radius(latitude=50.0, longitude=8.9, max_distance_in_km=30)

    print(df)


def main():
    logging.basicConfig(level=logging.INFO)
    station_example()


if __name__ == "__main__":
    main()
