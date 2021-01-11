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
    DWDObservationData,
    DWDObservationParameterSet,
    DWDObservationResolution,
)

log = logging.getLogger()


def sql_example():

    observations = DWDObservationData(
        station_ids=[1048],
        parameters=[DWDObservationParameterSet.TEMPERATURE_AIR],
        resolution=DWDObservationResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_parameters=True,
    )

    sql = "SELECT * FROM data WHERE parameter='temperature_air_200' AND value < -7.0;"
    log.info(f"Invoking SQL query '{sql}'")

    df = observations.all()
    df = df.dwd.lower().io.sql(sql)

    print(df)


def main():
    logging.basicConfig(level=logging.INFO)
    sql_example()


if __name__ == "__main__":
    main()
