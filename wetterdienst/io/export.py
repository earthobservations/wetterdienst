# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Export data to various formats."""

from __future__ import annotations

import json
import logging
from abc import abstractmethod
from copy import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlunparse

import polars as pl
import polars.selectors as cs

from wetterdienst.util.url import ConnectionString

if TYPE_CHECKING:
    import plotly.graph_objs as go

log = logging.getLogger(__name__)


@dataclass
class ExportMixin:
    """Postprocessing data.

    This aids in collecting, filtering, formatting and emitting data acquired through the core machinery.
    """

    df: pl.DataFrame

    def filter_by_sql(self, sql: str) -> pl.DataFrame:
        """Filter df using an SQL query WHERE clause."""
        self.df = self._filter_by_sql(self.df, sql)
        return self.df

    @abstractmethod
    def to_dict(self, *args: tuple, **kwargs: dict) -> dict:
        """Convert station information into dictionary format."""

    @abstractmethod
    def to_json(self, *args: tuple, **kwargs: dict) -> str:
        """Convert station information into JSON format."""

    @abstractmethod
    def to_ogc_feature_collection(self, *args: tuple, with_metadata: bool, **kwargs: dict) -> dict:
        """Convert station information into OGC Feature Collection format.

        Abstract method implementation.
        """

    def to_geojson(self, *, with_metadata: bool = False, indent: int | bool | None = 4, **_kwargs: dict) -> str:
        """Convert station information into GeoJSON format.

        Args:
            with_metadata: Include metadata in GeoJSON
            indent: Indentation level for JSON output

        Returns:
            GeoJSON string

        """
        if indent is True:
            indent = 4
        elif indent is False:
            indent = None
        json_kwargs = {"indent": indent, "ensure_ascii": False}
        return json.dumps(self.to_ogc_feature_collection(with_metadata=with_metadata), **json_kwargs)

    def to_csv(self, **kwargs: dict) -> str:
        """Convert DataFrame to CSV format.

        Args:
            **kwargs: Additional arguments passed to the CSV writer

        Returns:
            CSV string

        """
        df = self.df
        df = df.with_columns(
            pl.col(cs.Datetime(time_zone="*")).map_elements(
                lambda date: date.isoformat() if date else None,
                return_dtype=pl.String,
            ),
        )
        if "taken_station_ids" in df.columns:
            # Convert list of station IDs to a comma-separated string.
            df = df.with_columns(
                pl.col("taken_station_ids").list.join(",").alias("taken_station_ids"),
            )
        return df.write_csv(**kwargs)

    @abstractmethod
    def to_plot(self, **kwargs: dict) -> go.Figure:
        """Create a plotly figure from the DataFrame."""

    @abstractmethod
    def _to_image(self, **kwargs: dict) -> bytes | str:
        """Create an image from the plotly figure."""

    def to_image(self, **kwargs: dict) -> bytes | str:
        """Create an image from the plotly figure.

        Args:
            **kwargs: Additional arguments passed to the image creation method

        Returns:
            Image data as bytes or string

        """
        return self._to_image(**kwargs)

    def to_format(self, fmt: str, **kwargs: Any) -> str | bytes:  # noqa: ANN401
        """Format data according to the specified format.

        The formatting is done by one of the following methods:
        - `to_json`
        - `to_csv`
        - `to_geojson`
        - `to_image`

        Args:
            fmt: Output format
            **kwargs: Additional arguments passed to the formatting method

        Returns:
            Formatted data

        """
        fmt = fmt.lower()

        if fmt == "json":
            return self.to_json(**kwargs)
        if fmt == "csv":
            return self.to_csv()
        if fmt == "geojson":
            return self.to_geojson(**kwargs)
        if fmt in ("html", "png", "jpg", "webp", "svg", "pdf"):
            return self.to_image(fmt=fmt, **kwargs)
        msg = "Unknown output format"
        raise KeyError(msg)

    @staticmethod
    def _filter_by_sql(df: pl.DataFrame, sql: str) -> pl.DataFrame:
        """Filter df using an SQL query WHERE clause.

        This implementation is based on DuckDB, so please
        have a look at its SQL documentation.

        - https://duckdb.org/docs/sql/introduction

        Args:
            df: DataFrame to filter
            sql: SQL WHERE clause

        Returns:
            Filtered DataFrame

        """
        import duckdb  # noqa: PLC0415

        df = df.with_columns(pl.col("date").dt.replace_time_zone(None))  # uses df from local scope
        sql = f"FROM df WHERE {sql}"
        df = duckdb.sql(sql).pl()
        return df.with_columns(pl.col("date").dt.replace_time_zone("UTC"))

    def to_target(self, target: str) -> None:  # noqa: C901
        """Emit data to a target.

        The target is identified by a connection string.

        Examples:
        - duckdb://dwd.duckdb?table=weather
        - influxdb://localhost/?database=dwd&table=weather
        - crate://localhost/?database=dwd&table=weather

        Dispatch data to different data sinks. Currently, SQLite, DuckDB,
        InfluxDB and CrateDB are implemented. However, through the SQLAlchemy
        layer, it should actually work with any supported SQL database.

        - https://docs.sqlalchemy.org/en/13/dialects/

        Args:
            target: Connection string

        Raises:
            KeyError: Unknown export

        Returns:
            None (data is emitted to the target)

        """
        log.info(f"Exporting records to {target}\n{self.df.select(pl.len())}")

        connspec = ConnectionString(target)
        protocol = connspec.protocol
        database = connspec.database
        tablename = connspec.table

        if target.startswith("file://"):
            filepath = connspec.path

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
                alias fetch="wetterdienst values --provider=dwd --network=observation --station=1048,4411 --parameters=daily/kl --periods=recent"
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
                alias fetch="wetterdienst dwd observation values --station=1048,4411 --parameters=daily/kl --periods=recent"
                fetch --target="file://observation.zarr"

                # References
                - https://xarray.pydata.org/en/stable/generated/xarray.Dataset.from_dataframe.html
                - https://xarray.pydata.org/en/stable/generated/xarray.Dataset.to_zarr.html
                """  # noqa:E501

                log.info(f"Writing to Zarr group '{filepath}'")
                import xarray  # noqa: PLC0415

                # Problem: `TypeError: float() argument must be a string or a number, not 'NAType'`.
                # Solution: Fill gaps in the data.
                df = self.df.fill_null(-999)
                df = df.with_columns(
                    pl.col("date")
                    .dt.convert_time_zone("UTC")
                    .dt.replace_time_zone(None)
                    .map_elements(lambda date: date.isoformat(), return_dtype=pl.String),
                )
                group = df.get_column("dataset").gather(0).item()
                df = df.to_pandas()

                # Convert pandas DataFrame to xarray Dataset.
                dataset = xarray.Dataset.from_dataframe(df)
                log.info(f"Converted to xarray Dataset. Size={dataset.sizes}")

                # Export to Zarr format.
                # TODO: Also use attributes: `store.set_attribute()`
                store = dataset.to_zarr(
                    filepath,
                    mode="w",
                    group=group,  # use dataset name as group name
                    encoding={"date": {"dtype": "datetime64[ns]"}},
                )

                # Reporting.
                dimensions = store.get_dimensions()
                variables = list(store.get_variables().keys())

                log.info(f"Wrote Zarr file with dimensions={dimensions} and variables={variables}")
                log.info(f"Zarr Dataset Group info:\n{store.ds.info}")

            else:
                msg = "Unknown export file type"
                raise KeyError(msg)

            return

        if target.startswith("duckdb://"):
            """
            ====================
            DuckDB database sink
            ====================

            Install Python driver::

                pip install duckdb

            Acquire data::

                wetterdienst dwd observation values --station=1048,4411 --parameters=daily/kl --periods=recent --target="duckdb:///dwd.duckdb?table=weather"

            Example queries::

                python -c 'import duckdb; c = duckdb.connect(database="dwd.duckdb"); print(c.table("weather"))'
                python -c 'import duckdb; c = duckdb.connect(database="dwd.duckdb"); print(c.execute("SELECT * FROM weather").df())'

            """  # noqa:E501
            log.info(f"Writing to DuckDB. database={database}, table={tablename}")
            import duckdb  # noqa: PLC0415

            df = copy(self.df)

            for column in ("start_date", "end_date", "date"):
                if column in df.columns:
                    df = df.with_columns(pl.col(column).dt.replace_time_zone(None))

            connection = duckdb.connect(database=database, read_only=False)
            connection.register("origin", df)
            connection.execute(f"DROP TABLE IF EXISTS {tablename};")
            connection.execute(f"CREATE TABLE {tablename} AS SELECT * FROM origin;")  # noqa:S608
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

                alias fetch="wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent --station=1048,4411"
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

                alias fetch="wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent --station=1048,4411"
                fetch --target="influxdb2://${INFLUXDB_ORGANIZATION}:${INFLUXDB_TOKEN}@localhost/?database=dwd&table=weather"

            Example queries::

                influx query 'from(bucket:"dwd") |> range(start:-2d) |> limit(n: 10)'


            ==========================
            InfluxDB 3.x database sink
            ==========================

            Install Python driver::

                pip install influxdb3_python

            Acquire data::

                INFLUXDB_ORGANIZATION=acme
                INFLUXDB_TOKEN=t5PJry6TyepGsG7IY_n0K4VHp5uPvt9iap60qNHIXL4E6mW9dLmowGdNz0BDi6aK_bAbtD76Z7ddfho6luL2LA==
                INFLUXDB_HOST="eu-central-1-1.aws.cloud2.influxdata.com"

                alias fetch="wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent --station=1048,4411"
                fetch --target="influxdb3://${INFLUXDB_ORGANIZATION}:${INFLUXDB_TOKEN}@${INFLUXDB_HOST}/?database=dwd&table=weather"

            Example queries::

                influx query 'from(bucket:"dwd") |> range(start:-2d) |> limit(n: 10)'
            """  # noqa:E501

            if protocol in ["influxdb", "influxdbs", "influxdb1", "influxdb1s"]:
                version = 1
            elif protocol in ["influxdb2", "influxdb2s"]:
                version = 2
            elif protocol in ["influxdb3", "influxdb3s"]:
                version = 3
            else:
                msg = f"Unknown protocol variant '{protocol}' for InfluxDB"
                raise KeyError(msg)

            log.info(f"Writing to InfluxDB version {version}. database={database}, table={tablename}")

            # Set up the connection.
            if version == 1:
                from influxdb import InfluxDBClient  # noqa: PLC0415

                client = InfluxDBClient(
                    host=connspec.host,
                    port=connspec.port or 8086,
                    username=connspec.username,
                    password=connspec.password,
                    database=database,
                    ssl=protocol.endswith("s"),
                )
                client.create_database(database)
            elif version == 2:
                from influxdb_client import InfluxDBClient as InfluxDBClientV2  # noqa: PLC0415
                from influxdb_client import Point as PointV2  # noqa: PLC0415
                from influxdb_client.client.write_api import SYNCHRONOUS  # noqa: PLC0415

                ssl = protocol.endswith("s")
                url = f"http{(ssl and 's') or ''}://{connspec.url.hostname}:{connspec.url.port or 8086}"
                client = InfluxDBClientV2(url=url, org=connspec.username, token=connspec.password)
                write_api = client.write_api(write_options=SYNCHRONOUS)
            elif version == 3:
                from influxdb_client_3 import (  # noqa: PLC0415
                    InfluxDBClient3 as InfluxDBClientV3,
                )
                from influxdb_client_3 import (  # noqa: PLC0415
                    Point as PointV3,
                )
                from influxdb_client_3 import (  # noqa: PLC0415
                    WriteOptions,
                    write_client_options,
                )
                from influxdb_client_3.write_client.client.write_api import WriteType  # noqa: PLC0415

                write_options = WriteOptions(write_type=WriteType.synchronous)
                wco = write_client_options(WriteOptions=write_options)
                client_v3 = InfluxDBClientV3(
                    host=connspec.host,
                    org=connspec.username,
                    token=connspec.password,
                    write_client_options=wco,
                    database=database,
                )

            points = []
            for record in self.df.iter_rows(named=True):
                # for record in items.iter_rows(named=True):
                time = record.pop("date").isoformat()
                tags = {
                    "station_id": record.pop("station_id"),
                    "resolution": record.pop("resolution"),
                    "dataset": record.pop("dataset"),
                }
                parameter = record.pop("parameter", None)
                quality = record.pop("quality", None)
                # fields is a dict of either a single value (long format) or multiple values (wide format).
                fields = {k: v for k, v in record.items() if v is not None}
                if not fields:
                    continue
                if version == 1:
                    if parameter:
                        tags["parameter"] = parameter
                        if quality:
                            fields["quality"] = quality
                    point = {
                        "measurement": tablename,
                        "time": time,
                        "tags": tags,
                        "fields": fields,
                    }
                elif version == 2:
                    point = (
                        PointV2(tablename)
                        .time(time)
                        .tag("station_id", tags["station_id"])
                        .tag("resolution", tags["resolution"])
                        .tag("dataset", tags["dataset"])
                    )
                    # long format
                    if parameter:
                        point = point.tag("parameter", parameter)
                        if quality:
                            point = point.field("quality", quality)
                    for field, value in fields.items():
                        point = point.field(field, value)
                elif version == 3:
                    point = (
                        PointV3(tablename)
                        .time(time)
                        .tag("station_id", tags["station_id"])
                        .tag("resolution", tags["resolution"])
                        .tag("dataset", tags["dataset"])
                    )
                    if parameter:
                        point = point.tag("parameter", parameter)
                        if quality:
                            point = point.field("quality", quality)
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
            elif version == 3:
                client_v3.write(record=points)

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

                wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent --station=1048,4411 --target="crate://crate@localhost/dwd?table=weather"

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
                alias fetch='wetterdienst values --provider=dwd --network=observation --parameters=daily/kl
                    --periods=recent --station=1048,4411'

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
                import sqlite3  # noqa: PLC0415

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
    """Convert all datetime columns to ISO format."""
    date_columns = list(df.select(pl.col(pl.Datetime)).columns)
    date_columns.extend(["start_date", "end_date", "date"])
    date_columns = set(date_columns)
    for date_column in date_columns:
        if date_column in df:
            df = df.with_columns(
                pl.col(date_column).map_elements(lambda v: v.isoformat() if v else None, return_dtype=pl.String),
            )
    return df
