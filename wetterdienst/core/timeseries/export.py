# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import List
from urllib.parse import urlunparse

import polars as pl

from wetterdienst.metadata.columns import Columns
from wetterdienst.util.polars_util import chunker
from wetterdienst.util.url import ConnectionString

log = logging.getLogger(__name__)


@dataclass
class ExportMixin:
    """
    Postprocessing data.

    This aids in collecting, filtering, formatting and emitting data
    acquired through the core machinery.
    """

    df: pl.DataFrame

    def fill_gaps(self):
        self.df = self.df.fillna(-999)
        return self.df

    def filter_by_sql(self, sql: str) -> pl.DataFrame:
        self.df = self._filter_by_sql(self.df, sql)
        return self.df

    def to_dict(self) -> List[dict]:

        # Convert all datetime columns to ISO format.
        df = convert_datetimes(self.df)

        # Return dictionary with timeseries types.
        return df.to_dicts()

    def to_json(self, pretty: bool = True):
        df = self.df.select(pl.all())
        for column in ("from_date", "to_date", "date"):
            if column in df:
                df = df.with_columns(
                    pl.col(column).apply(lambda date: date and date.isoformat() or None, return_dtype=pl.Utf8)
                )
        return df.write_json(row_oriented=True, pretty=pretty)

    def to_csv(self):
        return self.df.write_csv(datetime_format="%Y-%m-%dT%H-%M-%S")

    def to_geojson(self, indent: int = 4) -> str:
        """
        Convert station information into GeoJSON format.

        Return:
             JSON string in GeoJSON FeatureCollection format.
        """
        return json.dumps(self.to_ogc_feature_collection(), indent=indent, ensure_ascii=False)

    def to_format(self, fmt: str, **kwargs) -> str:
        """
        Wrapper to create output based on a format string

        :param fmt: string defining the output format
        :return: string of formatted data
        """
        fmt = fmt.lower()

        if fmt == "json":
            return self.to_json(pretty=kwargs.get("pretty"))
        elif fmt == "csv":
            return self.to_csv()
        elif fmt == "geojson":
            return self.to_geojson(indent=kwargs.get("indent"))
        else:
            raise KeyError("Unknown output format")

    @staticmethod
    def _filter_by_sql(df: pl.DataFrame, sql: str) -> pl.DataFrame:
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

        df = df.with_columns(pl.col(Columns.DATE.value).dt.replace_time_zone(None)).to_pandas()
        df = duckdb.query_df(df, "data", sql).pl()
        return df.with_columns(pl.col(Columns.DATE.value).dt.replace_time_zone("UTC"))

    @abstractmethod
    def to_ogc_feature_collection(self):
        pass

    def to_target(self, target: str):
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

        log.info(f"Exporting records to {target}\n{self.df.select(pl.count())}")

        connspec = ConnectionString(target)
        protocol = connspec.url.scheme
        database = connspec.get_database()
        tablename = connspec.get_table()

        if target.startswith("file://"):
            filepath = connspec.get_path()

            if target.endswith(".xlsx"):
                log.info(f"Writing to spreadsheet file '{filepath}'")
                # Convert all datetime columns to ISO format.
                df = convert_datetimes(self.df)
                df.write_excel(filepath)

            elif target.endswith(".feather"):
                # https://arrow.apache.org/docs/python/feather.html
                log.info(f"Writing to Feather file '{filepath}'")
                self.df.write_ipc(filepath, compression="lz4")

            elif target.endswith(".parquet"):
                """
                # Acquire data and store to Parquet file.
                alias fetch="wetterdienst values --provider=dwd --network=observation --station=1048,4411 --parameter=kl --resolution=daily --period=recent"
                fetch --target="file://observations.parquet"

                # Check Parquet file.
                parquet-tools schema observations.parquet
                parquet-tools head observations.parquet

                # References
                - https://arrow.apache.org/docs/python/parquet.html
                """  # noqa:E501

                log.info(f"Writing to Parquet file '{filepath}'")

                self.df.write_parquet(filepath)

            elif target.endswith(".zarr"):
                """
                # Acquire data and store to Zarr group.
                alias fetch="wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily --period=recent"
                fetch --target="file://observation.zarr"

                # References
                - https://xarray.pydata.org/en/stable/generated/xarray.Dataset.from_dataframe.html
                - https://xarray.pydata.org/en/stable/generated/xarray.Dataset.to_zarr.html
                """  # noqa:E501

                log.info(f"Writing to Zarr group '{filepath}'")
                import xarray

                # Problem: `TypeError: float() argument must be a string or a number, not 'NAType'`.
                # Solution: Fill gaps in the data.
                df = self.df.fill_null(-999).to_pandas()

                # Convert pandas DataFrame to xarray Dataset.
                dataset = xarray.Dataset.from_dataframe(df)
                log.info(f"Converted to xarray Dataset. Size={dataset.sizes}")

                # Export to Zarr format.
                # TODO: Add "group" parameter.
                #       Group path. (a.k.a. `path` in zarr terminology.)
                # TODO: Also use attributes: `store.set_attribute()`
                store = dataset.to_zarr(
                    filepath,
                    mode="w",
                    group=None,
                    encoding={"date": {"dtype": "datetime64"}},
                )

                # Reporting.
                dimensions = store.get_dimensions()
                variables = list(store.get_variables().keys())

                log.info(f"Wrote Zarr file with dimensions={dimensions} and variables={variables}")
                log.info(f"Zarr Dataset Group info:\n{store.ds.info}")

            else:
                raise KeyError("Unknown export file type")

            return

        if target.startswith("duckdb://"):
            """
            ====================
            DuckDB database sink
            ====================

            Install Python driver::

                pip install duckdb

            Acquire data::

                wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily --period=recent --target="duckdb:///dwd.duckdb?table=weather"

            Example queries::

                python -c 'import duckdb; c = duckdb.connect(database="dwd.duckdb"); print(c.table("weather"))'
                python -c 'import duckdb; c = duckdb.connect(database="dwd.duckdb"); print(c.execute("SELECT * FROM weather").df())'

            """  # noqa:E501
            log.info(f"Writing to DuckDB. database={database}, table={tablename}")
            import duckdb

            df = self.df.with_columns(pl.col(Columns.DATE.value).dt.replace_time_zone(None)).to_pandas()

            connection = duckdb.connect(database=database, read_only=False)
            connection.register("origin", df)
            connection.execute(f"DROP TABLE IF EXISTS {tablename};")
            connection.execute(f"CREATE TABLE {tablename} AS SELECT * FROM origin;")  # noqa:S608

            weather_table = connection.table(tablename)
            print(weather_table)  # noqa: T201
            print("Cardinalities:")  # noqa: T201
            print(weather_table.to_df().count())  # noqa: T201
            connection.close()
            log.info("Writing to DuckDB finished")

        elif protocol.startswith("influxdb"):
            """
            ==========================
            InfluxDB 1.x database sink
            ==========================

            Install Python driver::

                pip install influxdb

            Run database::

                docker run -it --rm --publish=8086:8086 influxdb:1.8

            Acquire data::

                alias fetch="wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411"
                fetch --target="influxdb://localhost/?database=dwd&table=weather"

            Example queries::

                http 'localhost:8086/query?db=dwd&q=SELECT * FROM weather;'
                http 'localhost:8086/query?db=dwd&q=SELECT COUNT(*) FROM weather;'


            ==========================
            InfluxDB 2.x database sink
            ==========================

            Install Python driver::

                pip install influxdb_client

            Run database::

                docker run -it --rm --publish=8086:8086 influxdb:2.0
                influx setup --name=default --username=root --password=12345678 --org=acme --bucket=dwd --retention=0 --force

            Acquire data::

                INFLUXDB_ORGANIZATION=acme
                INFLUXDB_TOKEN=t5PJry6TyepGsG7IY_n0K4VHp5uPvt9iap60qNHIXL4E6mW9dLmowGdNz0BDi6aK_bAbtD76Z7ddfho6luL2LA==

                alias fetch="wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411"
                fetch --target="influxdb2://${INFLUXDB_ORGANIZATION}:${INFLUXDB_TOKEN}@localhost/?database=dwd&table=weather"

            Example queries::

                influx query 'from(bucket:"dwd") |> range(start:-2d) |> limit(n: 10)'
            """  # noqa:E501

            if protocol in ["influxdb", "influxdbs", "influxdb1", "influxdb1s"]:
                version = 1
            elif protocol in ["influxdb2", "influxdb2s"]:
                version = 2
            else:
                raise KeyError(f"Unknown protocol variant '{protocol}' for InfluxDB")

            log.info(f"Writing to InfluxDB version {version}. database={database}, table={tablename}")

            # Setup the connection.
            if version == 1:
                from influxdb import InfluxDBClient

                client = InfluxDBClient(
                    host=connspec.url.hostname,
                    port=connspec.url.port or 8086,
                    username=connspec.url.username,
                    password=connspec.url.password,
                    database=database,
                    ssl=protocol.endswith("s"),
                )
                client.create_database(database)
            elif version == 2:
                from influxdb_client import InfluxDBClient, Point
                from influxdb_client.client.write_api import SYNCHRONOUS

                ssl = protocol.endswith("s")
                url = f"http{ssl and 's' or ''}://{connspec.url.hostname}:{connspec.url.port or 8086}"
                client = InfluxDBClient(url=url, org=connspec.url.username, token=connspec.url.password)
                write_api = client.write_api(write_options=SYNCHRONOUS)

            points = []
            for items in chunker(self.df, chunksize=50000):
                for record in items.iter_rows(named=True):
                    time = record.pop("date").isoformat()
                    fields = {k: v for k, v in record.items() if v is not None}
                    if not fields:
                        continue
                    if version == 1:
                        point = {
                            "measurement": tablename,
                            "time": time,
                            "fields": fields,
                        }
                    elif version == 2:
                        point = Point(tablename).time(time)
                        for field, value in fields.items():
                            point = point.field(field, value)

                    points.append(point)

            # Write to InfluxDB.
            if version == 1:
                client.write_points(
                    points=points,
                    batch_size=50000,
                )
            elif version == 2:
                write_api.write(bucket=database, record=points)
                write_api.close()

            log.info("Writing to InfluxDB finished")

        elif target.startswith("crate://"):
            """
            =====================
            CrateDB database sink
            =====================

            Install Python driver::

                pip install crate[sqlalchemy] crash

            Run database::

                docker run -it --rm --publish=4200:4200 --env CRATE_HEAP_SIZE=2048M crate/crate:nightly

            Acquire data::

                wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily --period=recent --target="crate://crate@localhost/dwd?table=weather"

            Example queries::

                psql postgres://crate@localhost --command 'SELECT * FROM dwd.weather;'

                crash -c 'select * from dwd.weather;'
                crash -c 'select count(*) from dwd.weather;'
                crash -c "select *, date_format('%Y-%m-%dT%H:%i:%s.%fZ', date) as datetime from dwd.weather order by datetime limit 10;"

            """  # noqa:E501
            log.info(f"Writing to CrateDB. target={target}, table={tablename}")

            # CrateDB's SQLAlchemy driver doesn't accept `database` or `table` query parameters.
            cratedb_url = connspec.url._replace(path="", query=None)
            cratedb_target = urlunparse(cratedb_url)

            # Convert timezone-aware datetime fields to naive ones.
            # FIXME: Omit this as soon as the CrateDB driver is capable of supporting timezone-qualified timestamps.
            df = self.df.with_columns(pl.col("date").dt.replace_time_zone(time_zone=None))

            df.to_pandas().to_sql(
                name=tablename,
                con=cratedb_target,
                schema=database,
                if_exists="replace",
                index=False,
                chunksize=5000,
            )
            log.info("Writing to CrateDB finished")

        else:
            """
            ================================
            Generic SQLAlchemy database sink
            ================================

            Install Python driver::

                pip install sqlalchemy

            Examples::

                # Prepare
                alias fetch='wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily
                --period=recent'

                # Acquire data.
                fetch --target="sqlite:///dwd.sqlite?table=weather"

                # Query data.
                sqlite3 dwd.sqlite "SELECT * FROM weather;"

            """
            # Honour SQLite's SQLITE_MAX_VARIABLE_NUMBER, which defaults to 999
            # for SQLite versions prior to 3.32.0 (2020-05-22),
            # see https://www.sqlite.org/limits.html#max_variable_number.
            chunk_size = 5000
            if target.startswith("sqlite://"):
                import sqlite3

                if sqlite3.sqlite_version_info < (3, 32, 0):
                    chunk_size = int(999 / len(self.df.columns))

            log.info("Writing to SQL database")
            self.df.to_pandas().to_sql(
                name=tablename,
                con=target,
                if_exists="replace",
                index=False,
                method="multi",
                chunksize=chunk_size,
            )
            log.info("Writing to SQL database finished")


def convert_datetimes(df: pl.DataFrame) -> pl.DataFrame:
    """
    Convert all datetime columns to ISO format.

    :param df:        df[Columns.FROM_DATE] = df[Columns.FROM_DATE].dt.tz_localize(self.tz)
    :return:
    """
    date_columns = list(df.select(pl.col(pl.Datetime)).columns)
    date_columns.extend([Columns.FROM_DATE.value, Columns.TO_DATE.value, Columns.DATE.value])
    date_columns = set(date_columns)
    for date_column in date_columns:
        if date_column in df:
            df = df.with_columns(
                pl.col(date_column).apply(lambda v: v.isoformat() if v else None, return_dtype=pl.Utf8)
            )
    return df
