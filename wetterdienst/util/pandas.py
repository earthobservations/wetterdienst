# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
Postprocessing data.

This aids in collecting, filtering, formatting and emitting data
acquired through the core machinery.

Extending pandas
================
- https://pandas.pydata.org/pandas-docs/stable/development/extending.html
"""
import logging
from urllib.parse import urlunparse

import pandas as pd

from wetterdienst.metadata.columns import Columns
from wetterdienst.util.url import ConnectionString

log = logging.getLogger(__name__)


@pd.api.extensions.register_dataframe_accessor("io")
class IoAccessor:
    def __init__(self, pandas_obj):
        self.df: pd.DataFrame = pandas_obj

    @staticmethod
    def convert_datetimes(df: pd.DataFrame) -> pd.DataFrame:
        df: pd.DataFrame = df.copy(deep=True)

        # Convert all datetime columns to ISO format.
        date_columns = list(df.select_dtypes(include=[pd.DatetimeTZDtype]).columns)
        for date_column in date_columns:
            df[date_column] = df[date_column].apply(lambda d: d.isoformat())

        return df

    def to_dict(self) -> dict:

        # Convert all datetime columns to ISO format.
        df = self.convert_datetimes(self.df)

        # Return dictionary with scalar types.
        return df.to_dict(orient="records")

    def sql(self, sql: str) -> pd.DataFrame:
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

    def format(self, fmt: str) -> str:
        """
        Format/render Pandas DataFrame to given output format.

        :param fmt: One of json, geojson, csv, excel.
        :return: Rendered payload.
        """

        # Format as JSON.
        if fmt == "json":
            output = self.df.to_json(orient="records", date_format="iso", indent=4)

        # Format as CSV.
        elif fmt == "csv":
            output = self.df.to_csv(index=False, date_format="%Y-%m-%dT%H-%M-%S")

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

        log.info(f"Exporting records to {target}\n{self.df.count()}")

        t = ConnectionString(target)
        database = t.get_database()
        tablename = t.get_table()

        if target.startswith("file://"):
            filepath = t.get_path()

            if target.endswith(".xlsx"):
                log.info(f"Writing to spreadsheet file '{filepath}'")

                # Convert all datetime columns to ISO format.
                df = self.convert_datetimes(self.df)
                df.to_excel(filepath, index=False)

            elif target.endswith(".feather"):
                # https://arrow.apache.org/docs/python/feather.html
                log.info(f"Writing to Feather file '{filepath}'")
                import pyarrow.feather as feather

                feather.write_feather(self.df, filepath, compression="lz4")

            elif target.endswith(".parquet"):
                # https://arrow.apache.org/docs/python/parquet.html
                log.info(f"Writing to Parquet file '{filepath}'")
                import pyarrow as pa
                import pyarrow.parquet as pq

                table = pa.Table.from_pandas(self.df)
                pq.write_table(table, filepath)

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

                wetterdienst dwd observations values --station=1048,4411 --parameter=kl --resolution=daily --period=recent --target="duckdb:///dwd.duckdb?table=weather"

            Example queries::

                python -c 'import duckdb; c = duckdb.connect(database="dwd.duckdb"); print(c.table("weather"))'  # noqa
                python -c 'import duckdb; c = duckdb.connect(database="dwd.duckdb"); print(c.execute("SELECT * FROM weather").df())'  # noqa

            """
            log.info(f"Writing to DuckDB. database={database}, table={tablename}")
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

                docker run -it --rm --publish=8086:8086 influxdb:1.8

            Acquire data::

                wetterdienst dwd observations values --station=1048,4411 --parameter=kl --resolution=daily --period=recent --target="influxdb://localhost/?database=dwd&table=weather"

            Example queries::

                http 'localhost:8086/query?db=dwd&q=SELECT * FROM weather;'
                http 'localhost:8086/query?db=dwd&q=SELECT COUNT(*) FROM weather;'
            """
            log.info(f"Writing to InfluxDB. database={database}, table={tablename}")
            from influxdb.dataframe_client import DataFrameClient

            # 1. Mungle the data frame.
            # Use the "date" column as appropriate timestamp index.
            df = self.df.set_index(pd.DatetimeIndex(self.df["date"]))
            df = df.drop(["date"], axis=1)

            # Work around `ValueError: fill value must be in categories`.
            # The reason is that the InfluxDB Pandas adapter tries to apply
            # `tag_df.fillna('')  # replace NA with empty string`.
            # However, it is not possible to apply `.fillna` to categorical
            # columns. See:
            # - https://github.com/pandas-dev/pandas/issues/24079
            # - https://stackoverflow.com/questions/65316023/filling-np-nan-entries-of-float-column-gives-valueerror-fill-value-must-be-in-c/65316190
            # - https://stackoverflow.com/questions/53664948/pandas-fillna-throws-valueerror-fill-value-must-be-in-categories
            # - https://stackoverflow.com/questions/32718639/pandas-filling-nans-in-categorical-data/44633307
            #
            # So, let's convert all categorical columns back to their designated type representations.
            # https://stackoverflow.com/questions/32011359/convert-categorical-data-in-pandas-dataframe/32011969#32011969
            if "quality" in df:
                df.quality = df.quality.astype("Int64")
            categorical_columns = df.select_dtypes(["category"]).columns
            df[categorical_columns] = df[categorical_columns].astype("str")

            # When using the tidy format, don't export empty records.
            # Otherwise, the InfluxDB dataframe driver adapter will croak.
            if df.attrs.get("tidy"):
                df = df.dropna()

            # Compute designated tag fields from some candidates.
            tag_columns = []
            tag_candidates = [
                Columns.STATION_ID.value,
                Columns.QUALITY.value,
                Columns.QUALITY_PREFIX.value,
                Columns.DATASET.value,
                Columns.PARAMETER.value,
            ]
            for tag_candidate in tag_candidates:
                tag_candidate = tag_candidate.lower()
                for column in df.columns:
                    if column.startswith(tag_candidate):
                        tag_columns.append(column)

            # Setup the connection.
            c = DataFrameClient(database=database)
            c.create_database(database)

            # Need pandas>=1.2, otherwise InfluxDB's `field_df = dataframe[field_columns].replace([np.inf, -np.inf], np.nan)`
            # will erroneously cast `Int64` to `object`, so `int_columns = df.select_dtypes(include=['integer']).columns`
            # will fail.
            # https://github.com/pandas-dev/pandas/issues/32988

            # Write to InfluxDB.
            c.write_points(
                dataframe=df,
                measurement=tablename,
                tag_columns=tag_columns,
                batch_size=50000,
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

                docker run -it --rm --publish=4200:4200 --env CRATE_HEAP_SIZE=2048M crate/crate:nightly

            Acquire data::

                wetterdienst dwd observations values --station=1048,4411 --parameter=kl --resolution=daily --period=recent --target="crate://crate@localhost/dwd?table=weather"

            Example queries::

                psql postgres://crate@localhost --command 'SELECT * FROM dwd.weather;'

                crash -c 'select * from dwd.weather;'
                crash -c 'select count(*) from dwd.weather;'
                crash -c "select *, date_format('%Y-%m-%dT%H:%i:%s.%fZ', date) as datetime from dwd.weather order by datetime limit 10;"  # noqa

            """
            log.info(f"Writing to CrateDB. target={target}, table={tablename}")

            # CrateDB's SQLAlchemy driver doesn't accept `database` or `table` query parameters.
            cratedb_url = t.url._replace(path="", query=None)
            cratedb_target = urlunparse(cratedb_url)

            # Convert timezone-aware datetime fields to naive ones.
            # FIXME: Omit this as soon as the CrateDB driver is capable of supporting timezone-qualified timestamps.
            self.df.date = self.df.date.dt.tz_localize(None)
            # self.df.date = self.df.date.dt.tz_convert(None)

            self.df.to_sql(
                name=tablename,
                con=cratedb_target,
                schema=database,
                if_exists="replace",
                index=False,
                # method="multi",
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
                alias fetch='wetterdienst dwd observations values --station=1048,4411 --parameter=kl --resolution=daily --period=recent'

                # Acquire data.
                fetch --target="sqlite:///dwd.sqlite?table=weather"

                # Query data.
                sqlite3 dwd.sqlite "SELECT * FROM weather;"

            """

            # Honour SQLite's SQLITE_MAX_VARIABLE_NUMBER, which defaults to 999
            # for SQLite versions prior to 3.32.0 (2020-05-22),
            # see https://www.sqlite.org/limits.html#max_variable_number.
            chunksize = 5000
            if target.startswith("sqlite://"):
                import sqlite3

                if sqlite3.sqlite_version_info < (3, 32, 0):
                    chunksize = int(999 / len(self.df.columns))

            log.info("Writing to SQL database")
            self.df.to_sql(
                name=tablename,
                con=target,
                if_exists="replace",
                index=False,
                method="multi",
                chunksize=chunksize,
            )
            log.info("Writing to SQL database finished")
