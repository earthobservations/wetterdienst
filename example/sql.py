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

from wetterdienst import DWDStationRequest, DataPackage
from wetterdienst import Parameter, PeriodType, TimeResolution

log = logging.getLogger()


def sql_example():

    request = DWDStationRequest(
        station_ids=[1048],
        parameter=[Parameter.TEMPERATURE_AIR],
        time_resolution=TimeResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_column_names=True,
        prefer_local=True,
        write_file=True,
    )

    sql = "SELECT * FROM data WHERE element='temperature_air_200' AND value < -7.0;"
    log.info(f"Invoking SQL query '{sql}'")

    data = DataPackage(request=request)
    data.lowercase_fieldnames()
    df = data.filter_by_sql(sql)

    print(df)


def main():
    logging.basicConfig(level=logging.INFO)
    sql_example()


if __name__ == "__main__":
    main()
