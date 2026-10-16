# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Acquire measurement information from DWD and filter using SQL.

Setup
-----

    pip install wetterdienst[sql]
"""

import logging

from wetterdienst import Options
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)

log = logging.getLogger()


def values_sql_example() -> None:
    """Retrieve temperature data by DWD and filter by sql statement."""
    options = Options(shape="long", humanize=True, convert_units=False)

    request = DwdObservationRequest(
        parameters=("hourly", "temperature_air"),
        start="2019-01-01",
        end="2020-01-01",
        options=options,
    )

    stations = request.filter_by_station_id(station_id=(1048,))

    print(stations.df)

    sql = "parameter='temperature_air_2m' AND value < -7.0;"
    log.info(f"Invoking SQL query '{sql}'")

    # Acquire observation values and filter with SQL.
    results = stations.values().all()
    results.filter_by_sql(sql)

    print(results.df)


def main() -> None:
    """Run example."""
    logging.basicConfig(level=logging.INFO)
    values_sql_example()


if __name__ == "__main__":
    main()
