import json
import logging
from typing import Union
from urllib.parse import urlparse, parse_qs

import pandas as pd

from wetterdienst import DWDStationRequest, TimeResolution
from wetterdienst.additionals.geo_location import stations_to_geojson
from wetterdienst.additionals.time_handling import parse_datetime, mktimerange
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns

log = logging.getLogger(__name__)


class DataPackage:
    """
    Postprocessing DWD data.

    This aids in collecting, filtering, formatting and emitting data
    acquired through the core machinery.
    """

    def __init__(
        self, df: pd.DataFrame = None, request: Union[DWDStationRequest] = None
    ):
        self.df = df
        self.request = request

        if self.request is not None:
            self.collect(self.request)

    def collect(self, request: Union[DWDStationRequest]):
        """
        Collect all data from ``DWDStationRequest`` and assign to ``self.df``.

        :param request: The DWDStationRequest instance.
        :return: self
        """

        data = list(request.collect_data())

        if not data:
            raise ValueError("No data available for given constraints")

        self.df = pd.concat(data)

        return self

    def filter_by_date(
        self, date: str, time_resolution: TimeResolution
    ) -> pd.DataFrame:
        """
        Filter Pandas DataFrame by date or date interval.

        Accepts different kinds of date formats, like:

        - 2020-05-01
        - 2020-06-15T12
        - 2020-05
        - 2019
        - 2020-05-01/2020-05-05
        - 2017-01/2019-12
        - 2010/2020

        :param date:
        :param time_resolution:
        :return: Filtered DataFrame
        """

        # Filter by date interval.
        if "/" in date:
            date_from, date_to = date.split("/")
            date_from = parse_datetime(date_from)
            date_to = parse_datetime(date_to)
            if time_resolution in (
                TimeResolution.ANNUAL,
                TimeResolution.MONTHLY,
            ):
                date_from, date_to = mktimerange(time_resolution, date_from, date_to)
                expression = (date_from <= self.df[DWDMetaColumns.FROM_DATE.value]) & (
                    self.df[DWDMetaColumns.TO_DATE.value] <= date_to
                )
            else:
                expression = (date_from <= self.df[DWDMetaColumns.DATE.value]) & (
                    self.df[DWDMetaColumns.DATE.value] <= date_to
                )
            df = self.df[expression]

        # Filter by specific date.
        else:
            date = parse_datetime(date)
            if time_resolution in (
                TimeResolution.ANNUAL,
                TimeResolution.MONTHLY,
            ):
                date_from, date_to = mktimerange(time_resolution, date)
                expression = (date_from <= self.df[DWDMetaColumns.FROM_DATE.value]) & (
                    self.df[DWDMetaColumns.TO_DATE.value] <= date_to
                )
            else:
                expression = date == self.df[DWDMetaColumns.DATE.value]
            df = self.df[expression]

        return df

    def lowercase_fieldnames(self):
        """
        Make Pandas DataFrame column names lowercase.

        :return: Mungled DataFrame
        """
        self.df = self.df.rename(columns=str.lower)
        for attribute in DWDMetaColumns.PARAMETER, DWDMetaColumns.ELEMENT:
            attribute_name = attribute.value.lower()
            if attribute_name in self.df:
                self.df[attribute_name] = self.df[attribute_name].str.lower()
        return self

    def filter_by_sql(self, sql: str) -> pd.DataFrame:
        """
        Filter Pandas DataFrame using an SQL query.
        The virtual table name is "data", so queries
        should look like ``SELECT * FROM data;``.

        This implementation is based on DuckDB, so please
        have a look at its SQL documentation.

        - https://duckdb.org/docs/sql/introduction

        :param sql: A SQL expression.
        :return: Filtered DataFrame
        """
        import duckdb

        return duckdb.query(self.df, "data", sql).df()

    def format(self, format: str) -> str:
        """
        Format/render Pandas DataFrame to given output format.

        :param format: One of json, geojson, csv, excel.
        :return: Rendered payload.
        """

        # Output as JSON.
        if format == "json":
            output = self.df.to_json(orient="records", date_format="iso", indent=4)

        # Output as GeoJSON.
        elif format == "geojson":
            output = json.dumps(stations_to_geojson(self.df), indent=4)

        # Output as CSV.
        elif format == "csv":
            output = self.df.to_csv(index=False, date_format="%Y-%m-%dT%H-%M-%S")

        # Output as XLSX.
        # FIXME: Make --format=excel write to a designated file.
        elif format == "excel":
            # TODO: Obtain output file name from command line.
            output_filename = "output.xlsx"
            log.info(f"Writing {output_filename}")
            self.df.to_excel(output_filename, index=False)
            output = None

        else:
            raise KeyError("Unknown output format")

        return output

    def export(self, target: str):
        """
        Emit Pandas DataFrame to target. A target
        is identified by a connection string.

        Examples:

        - duckdb://dwd.duckdb?table=weather
        - influxdb://localhost/?database=dwd&table=weather
        - crate://localhost/?database=dwd&table=weather

        Dispatch data to different data sinks. Currently, SQLite, DuckDB,
        InfluxDB and CrateDB are implemented. However, through the SQLAlchemy
        layer, it should actually work with any supported SQL database.

        - https://docs.sqlalchemy.org/en/13/dialects/

        :param target: Target connection string.
        :return: self
        """

        database, tablename = ConnectionString(target).get()

        if target.startswith("duckdb://"):
            """
            ====================
            DuckDB database sink
            ====================

            Install Python driver::

                pip install duckdb

            Acquire data::

                wetterdienst readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent --target="duckdb:///dwd.duckdb?table=weather"

            Example queries::

                python -c 'import duckdb; c = duckdb.connect(database="dwd.duckdb"); print(c.table("weather"))'  # noqa
                python -c 'import duckdb; c = duckdb.connect(database="dwd.duckdb"); print(c.execute("SELECT * FROM weather").df())'  # noqa

            """
            log.info(f"Writing to DuckDB {database, tablename}")
            import duckdb

            connection = duckdb.connect(database=database, read_only=False)
            connection.register("origin", self.df)
            connection.execute(f"DROP TABLE IF EXISTS {tablename};")
            connection.execute(
                f"CREATE TABLE {tablename} AS SELECT * FROM origin;"  # noqa:S608
            )

            weather_table = connection.table(tablename)
            print(weather_table)
            print("Cardinalities:")
            print(weather_table.to_df().count())
            connection.close()
            log.info("Writing to DuckDB finished")

        elif target.startswith("influxdb://"):
            """
            ======================
            InfluxDB database sink
            ======================

            Install Python driver::

                pip install influxdb

            Run database::

                docker run --publish "8086:8086" influxdb/influxdb:1.8.2

            Acquire data::

                wetterdienst readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent --target="influxdb://localhost/?database=dwd&table=weather"

            Example queries::

                http 'localhost:8086/query?db=dwd&q=SELECT * FROM weather;'
                http 'localhost:8086/query?db=dwd&q=SELECT COUNT(*) FROM weather;'
            """
            log.info(f"Writing to InfluxDB {database, tablename}")
            from influxdb.dataframe_client import DataFrameClient

            # Setup the connection.
            c = DataFrameClient(database=database)
            c.create_database(database)

            # Mungle the data frame.
            df = self.df.set_index(pd.DatetimeIndex(self.df["date"]))
            df = df.drop(["date"], axis=1)
            df = df.dropna()

            # Write to InfluxDB.
            c.write_points(
                dataframe=df,
                measurement=tablename,
                tag_columns=["station_id", "parameter", "element"],
            )
            log.info("Writing to InfluxDB finished")

        elif target.startswith("crate://"):
            """
            =====================
            CrateDB database sink
            =====================

            Install Python driver::

                pip install crate[sqlalchemy] crash

            Run database::

                docker run --publish "4200:4200" --env CRATE_HEAP_SIZE=512M crate/crate:4.2.4

            Acquire data::

                wetterdienst readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent --target="crate://localhost/?database=dwd&table=weather"

            Example queries::

                crash -c 'select * from weather;'
                crash -c 'select count(*) from weather;'
                crash -c "select *, date_format('%Y-%m-%dT%H:%i:%s.%fZ', date) as datetime from weather order by datetime limit 10;"  # noqa

            """
            log.info("Writing to CrateDB")
            self.df.to_sql(
                name=tablename,
                con=target,
                if_exists="replace",
                index=False,
                method="multi",
                chunksize=5000,
            )
            log.info("Writing to CrateDB finished")

        else:
            """
            ========================
            SQLAlchemy database sink
            ========================

            Install Python driver::

                pip install sqlalchemy

            Examples::

                # Prepare
                alias fetch='wetterdienst readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent'

                # Acquire data.
                fetch --target="sqlite:///dwd.sqlite?table=weather"

                # Query data.
                sqlite3 dwd.sqlite "SELECT * FROM weather;"

            """
            log.info("Writing to SQL database")
            self.df.to_sql(
                name=tablename,
                con=target,
                if_exists="replace",
                index=False,
                method="multi",
                chunksize=5000,
            )
            log.info("Writing to SQL database finished")

        return self


class ConnectionString:
    def __init__(self, url):
        self.url_raw = url
        self.url = urlparse(url)

    def get_query_param(self, name):
        query = parse_qs(self.url.query)
        try:
            return query[name][0]
        except (KeyError, IndexError):
            return None

    def get_table(self):
        return self.get_query_param("table") or "weather"

    def get_database(self):
        database = None
        if self.url.netloc:
            database = self.get_query_param("database")
        else:
            if self.url.path.startswith("/"):
                database = self.url.path[1:]

        return database or "dwd"

    def get(self):
        database = self.get_database()
        tablename = self.get_table()
        return database, tablename
