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


def stations_filter_by_examples():
    """Retrieve stations_result of DWD that measure temperature."""
    request = DwdObservationRequest(
        parameters=("hourly", "temperature_air"),
        periods="recent",
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 20),
    )

    print("All stations")
    print(request.all().df)

    print("Filter by station_id (1048)")
    station_id = 1048
    print(request.filter_by_station_id(station_id).df)

    print("Filter by name (Dresden)")
    name = "Dresden Klotzsche"
    print(request.filter_by_name(name).df)

    frankfurt = (50.11, 8.68)
    print("Filter by distance (30 km)")
    print(request.filter_by_distance(latlon=frankfurt, distance=30).df)
    print("Filter by rank (3 closest stations)")
    print(request.filter_by_rank(latlon=frankfurt, rank=3).df)

    print("Filter by bbox (Frankfurt)")
    bbox = (8.52, 50.03, 8.80, 50.22)
    print(request.filter_by_bbox(*bbox).df)

    print("Filter by sql (starting with Dre)")
    sql = "name LIKE 'Dre%'"
    print(request.filter_by_sql(sql).df)


def main():
    """Run example."""
    logging.basicConfig(level=logging.INFO)
    stations_filter_by_examples()


if __name__ == "__main__":
    main()
