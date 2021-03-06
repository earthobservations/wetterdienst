# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====
Acquire measurement information from DWD and filter using SQL.


=====
Setup
=====
::

    pip install wetterdienst[sql]

"""
import logging

from wetterdienst.dwd.observations import (
    DwdObservationParameterSet,
    DwdObservationRequest,
    DwdObservationResolution,
)

log = logging.getLogger()


def sql_example():

    request = DwdObservationRequest(
        parameter=[DwdObservationParameterSet.TEMPERATURE_AIR],
        resolution=DwdObservationResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_parameters=True,
    )

    stations = request.filter(station_id=(1048,))

    sql = "SELECT * FROM data WHERE parameter='temperature_air_200' AND value < -7.0;"
    log.info(f"Invoking SQL query '{sql}'")

    df = stations.values.all().df
    df = df.dwd.lower().io.sql(sql)

    print(df)


def main():
    logging.basicConfig(level=logging.INFO)
    sql_example()


if __name__ == "__main__":
    main()
