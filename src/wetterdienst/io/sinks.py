# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Write a result to a target: the file writers by extension and the database sinks by scheme.

`ExportMixin.to_target` reads the connection string and hands the result to the sink `find_sink` names for it. A file
target is then written by the function `FILE_WRITERS` holds for its extension. Each writer imports its dependency when
it is used (`import_optional`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from copy import copy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import polars as pl
import polars.selectors as cs

from wetterdienst.exceptions import ExportRefusedError, MissingDependencyError
from wetterdienst.util.extras import as_missing_dependency, import_optional, missing_dependency_message
from wetterdienst.util.json_util import dumps_json
from wetterdienst.util.url import ConnectionString, redact_password

if TYPE_CHECKING:
    import sqlalchemy

    from wetterdienst.io.export import ExportMixin

log = logging.getLogger(__name__)

#: what `to_target` does with a target that already exists
IfExists = Literal["replace", "append", "fail", "skip"]

#: writes the result to the file at the path
FileWriter = Callable[["ExportMixin", str], None]

#: writes the result to the target: the result, the target as written, its reading and `if_exists`
Sink = Callable[["ExportMixin", str, ConnectionString, IfExists], None]


def _array_group(df: pl.DataFrame) -> str:
    """Name the group the array formats write into.

    For what the whole frame holds, not for whatever its first row happens to say: a wide frame
    merging the datasets of one resolution carries no dataset name at all, and an empty group
    would write the arrays into the store root, where a write clobbers every other group in it.
    """
    for column in ("dataset", "resolution"):
        if column in df.columns:
            names = df.get_column(column).cast(pl.String).drop_nulls().unique().sort().to_list()
            if names:
                return "_".join(names)
    return "data"


def _write_array_store(result: ExportMixin, filepath: str, *, netcdf: bool) -> None:
    """Write the frame to a Zarr group or a NetCDF file, through xarray.

    The two share everything but their notion of time. NetCDF has a convention for it, so the
    timestamps stay timestamps and xarray writes them as CF units; Zarr keeps the ISO strings
    and the `datetime64` encoding that turns them back into the epoch nanoseconds a reader of
    an existing store expects, which is a contract this must not break.
    """
    xarray = import_optional("xarray", "Writing Zarr and NetCDF", extra="export")

    engine = _netcdf_engine() if netcdf else None
    if netcdf and not engine:
        # no engine is a package that is not installed, and `h5netcdf` the one `export` carries
        raise MissingDependencyError(missing_dependency_message("Writing NetCDF", "h5netcdf", extra="export"))
    if not netcdf:
        # xarray imports it only when it writes the store
        import_optional("zarr", "Writing Zarr", extra="export")

    group = _array_group(result.df)
    df = result.df
    # a gap stays a gap: NaN in a number, and in a time `NaT`, which numpy reads out of the string below. A text column
    # has no NaN and holds an empty string, as it did. Zarr wrote -999 here (`fill_null(-999)` against
    # `TypeError: float() argument must be a string or a number, not 'NAType'`), which a reader took for a measurement:
    # an air temperature of -999 degrees, or a station 999 m below the sea. NetCDF kept its NaN all along
    # xarray encoding cannot handle a pandas Categorical (produced from Enum columns, which a caller
    # may have made of the frame's own), so cast them to String, and a list column is no more an array than it
    # is a CSV field. A `pl.Categorical` fails on its own: `Cannot interpret 'CategoricalDtype(...)' as a data type`
    df = join_list_columns(df).with_columns(pl.col(pl.Enum, pl.Categorical).cast(pl.String))
    # every timestamp the frame carries, in UTC without the zone: a stations frame has
    # `start_timestamp` and `end_timestamp` and no `timestamp`, and naming the values column alone (then
    # `date`) took it down with a missing column before it could be written at all
    df = df.with_columns(cs.datetime().dt.convert_time_zone("UTC").dt.replace_time_zone(None))

    if netcdf:
        log.info(f"Writing to NetCDF file '{filepath}'")
        dataset = xarray.Dataset.from_dataframe(df.to_pandas())
        dataset.to_netcdf(filepath, group=group, engine=engine)
        log.info(f"Wrote NetCDF file with variables={list(dataset.data_vars)}")
        return

    # the columns to read back as timestamps, taken before they are written as strings rather
    # than from a list of the names this library happens to use
    datetime_columns = df.select(cs.datetime()).columns
    pandas_df = df.with_columns(cs.datetime().dt.to_string("iso:strict").fill_null("NaT")).to_pandas()
    dataset = xarray.Dataset.from_dataframe(pandas_df)
    log.info(f"Converted to xarray Dataset. Size={dataset.sizes}")
    log.info(f"Writing to Zarr group '{filepath}'")
    # TODO: Also use attributes: `store.set_attribute()`
    store = dataset.to_zarr(
        filepath,
        mode="w",
        group=group,  # use dataset name as group name
        encoding={name: {"dtype": "datetime64[ns]"} for name in datetime_columns},
    )

    # Reporting.
    dimensions = store.get_dimensions()
    variables = list(store.get_variables().keys())
    log.info(f"Wrote Zarr file with dimensions={dimensions} and variables={variables}")
    log.info(f"Zarr Dataset Group info:\n{store.ds.info}")


def _driver_missing(e: ModuleNotFoundError, url: sqlalchemy.engine.URL) -> MissingDependencyError | None:
    """Say which driver a SQLAlchemy URL needs, when SQLAlchemy found it not installed.

    SQLAlchemy imports the DBAPI when it makes the engine, so the absence of a driver arrives as
    that module's `ModuleNotFoundError`. A bare `mysql://` is `mysqlclient`. A bare `postgresql://`
    is psycopg 3 where it imports, and psycopg2 where it does not on SQLAlchemy 2.0 (2.1 takes
    psycopg 3 itself), so where psycopg is not installed at all the absence of psycopg2 names
    psycopg, which is the driver the `postgresql` extra installs. A driver no extra installs
    (`pg8000`, `pyodbc`, a psycopg2 the target names, a psycopg that is installed but does not
    load) is named without an install line.

    Returns:
        The error to raise from `e`, or `None` where `e` is no absence of a package.

    """
    import importlib.util  # noqa: PLC0415

    what = "Writing to a SQL database"
    missing = as_missing_dependency(e, what)
    if (
        missing is not None
        and e.name == "psycopg2"
        and url.drivername == "postgresql"
        and importlib.util.find_spec("psycopg") is None
    ):
        return MissingDependencyError(missing_dependency_message(what, "psycopg"))
    return missing


def _psycopg_imports() -> bool:
    """Tell whether psycopg 3 imports: installed without a libpq to call, it does not."""
    import importlib  # noqa: PLC0415

    try:
        importlib.import_module("psycopg")
    except ImportError:
        return False
    return True


def _netcdf_engine() -> Literal["h5netcdf", "netcdf4"] | None:
    """Name an installed engine xarray can write NetCDF with, if there is one.

    Not scipy, which writes NetCDF3: that format has no groups, and every write here is grouped by
    the datasets the frame holds, so scipy answers with a bare `NotImplementedError` -- the very
    thing the engine check exists to replace.
    """
    import importlib.util  # noqa: PLC0415

    # the module to look for, and what xarray calls the engine that needs it: `netCDF4` is the
    # module, `netcdf4` the engine
    for module, engine in (("h5netcdf", "h5netcdf"), ("netCDF4", "netcdf4")):
        if importlib.util.find_spec(module):
            return engine
    return None


def join_list_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Join a list column into one comma-separated field.

    The formats without a notion of a list -- CSV, spreadsheets, the array stores -- take
    `taken_station_ids` as text or not at all. Zarr and NetCDF failed on it with `can only convert
    an array of size 1 to a Python scalar`, so an interpolation could not be written to either.
    """
    list_columns = [name for name, dtype in df.schema.items() if isinstance(dtype, pl.List)]
    if not list_columns:
        return df
    return df.with_columns(pl.col(name).cast(pl.List(pl.String)).list.join(",") for name in list_columns)


def _write_csv(result: ExportMixin, filepath: str) -> None:
    """Write the frame as CSV."""
    log.info(f"Writing to CSV file '{filepath}'")
    # the same rendering `to_csv` gives, so a file and a response hold the same thing
    result._flatten().write_csv(filepath)  # noqa: SLF001


def _write_xlsx(result: ExportMixin, filepath: str) -> None:
    """Write the frame as a spreadsheet."""
    log.info(f"Writing to spreadsheet file '{filepath}'")
    # polars writes through XlsxWriter and names it in its own error
    import_optional("xlsxwriter", "Writing a spreadsheet", extra="excel")
    result._flatten().write_excel(filepath)  # noqa: SLF001


def _write_json(result: ExportMixin, filepath: str) -> None:
    """Write the frame as JSON."""
    # JSON has arrays of its own, so a list of station ids stays a list. The records
    # are the frame's, not the `{"metadata": ..., "values": [...]}` envelope `to_json`
    # returns -- a file holds the data, and the envelope describes a response
    log.info(f"Writing to JSON file '{filepath}'")
    result._iso_datetimes().write_json(filepath)  # noqa: SLF001


def _write_jsonl(result: ExportMixin, filepath: str) -> None:
    """Write the frame as JSON Lines, which is NDJSON under either extension."""
    # one JSON object per line, which is what a stream of records is read as: what `to_ndjson` returns
    log.info(f"Writing to JSON Lines file '{filepath}'")
    result._iso_datetimes().write_ndjson(filepath)  # noqa: SLF001


def _write_geojson(result: ExportMixin, filepath: str) -> None:
    """Write the frame as GeoJSON: the feature collection, written as `to_geojson` writes it."""
    # the collection itself and not the `{"data": ...}` that `to_geojson` wraps it in: a `.geojson` file is read by
    # tools that expect a `FeatureCollection` at the top, as a `.json` file holds the records and not the envelope
    log.info(f"Writing to GeoJSON file '{filepath}'")
    collection = result.to_ogc_feature_collection()["data"]
    # bytes, as `ensure_ascii=False` writes UTF-8 and a text file would translate the newlines on Windows
    Path(filepath).write_bytes(dumps_json(collection, indent=4, ensure_ascii=False).encode("utf-8"))


def _write_feather(result: ExportMixin, filepath: str) -> None:
    """Write the frame as Feather."""
    # https://arrow.apache.org/docs/python/feather.html
    log.info(f"Writing to Feather file '{filepath}'")
    result.df.write_ipc(filepath, compression="lz4")


def _write_parquet(result: ExportMixin, filepath: str) -> None:
    """Write the frame as Parquet."""
    """
    # Acquire data and store to Parquet file.
    alias fetch="wetterdienst values --provider=dwd --network=observation --stations=1048,4411 --parameters=daily/kl --periods=recent"
    fetch --target="file://observations.parquet"

    # Check Parquet file.
    parquet-tools schema observations.parquet
    parquet-tools head observations.parquet

    # References
    - https://arrow.apache.org/docs/python/parquet.html
    """  # noqa:E501

    log.info(f"Writing to Parquet file '{filepath}'")

    result.df.write_parquet(filepath)


def _write_zarr(result: ExportMixin, filepath: str) -> None:
    """Write the frame to a Zarr group."""
    _write_array_store(result, filepath, netcdf=False)


def _write_netcdf(result: ExportMixin, filepath: str) -> None:
    """Write the frame to a NetCDF file."""
    """
    # Acquire data and store to Zarr group or NetCDF file.
    alias fetch="wetterdienst dwd observation values --stations=1048,4411 --parameters=daily/kl --periods=recent"
    fetch --target="file://observation.zarr"
    fetch --target="file://observation.nc"

    # References
    - https://xarray.pydata.org/en/stable/generated/xarray.Dataset.from_dataframe.html
    - https://xarray.pydata.org/en/stable/generated/xarray.Dataset.to_zarr.html
    - https://xarray.pydata.org/en/stable/generated/xarray.Dataset.to_netcdf.html
    """

    _write_array_store(result, filepath, netcdf=True)


#: the file writers, by the extension a `file://` target ends in, which is read in any case (`.CSV` is `.csv`)
FILE_WRITERS: dict[str, FileWriter] = {
    ".csv": _write_csv,
    ".xlsx": _write_xlsx,
    ".json": _write_json,
    ".jsonl": _write_jsonl,
    ".ndjson": _write_jsonl,
    ".geojson": _write_geojson,
    ".feather": _write_feather,
    ".parquet": _write_parquet,
    ".zarr": _write_zarr,
    ".nc": _write_netcdf,
}


def _write_file(result: ExportMixin, target: str, connspec: ConnectionString, if_exists: IfExists) -> None:
    """Write the frame to the file a `file://` target names, by its extension."""
    if if_exists == "append":
        msg = "Append mode is not supported for file exports."
        raise ExportRefusedError(msg)

    filepath = connspec.path

    if Path(filepath).exists():
        if if_exists == "fail":
            msg = f"File '{filepath}' already exists, aborting write due to if_exists='fail'."
            raise ExportRefusedError(msg)
        if if_exists == "skip":
            log.info(f"File '{filepath}' exists, skipping write due to if_exists='skip'.")
            return

    for extension, writer in FILE_WRITERS.items():
        if filepath.lower().endswith(extension):
            writer(result, filepath)
            return
    msg = f"Unknown export file type for target '{target}'"
    if "?" in target.rpartition("/")[2]:
        # everything after `file://` is the path, so a `?a=1` ending it belongs to the file name, which then has no
        # extension; a `?` in a directory is not what the refusal is about
        msg += ". A file target has no query string: write a '?' of the file name as %3F, and leave a query out"
    raise ExportRefusedError(msg)


def _write_duckdb(result: ExportMixin, target: str, connspec: ConnectionString, if_exists: IfExists) -> None:  # noqa: ARG001
    """Write the frame to a DuckDB database."""
    database = connspec.database
    tablename = connspec.table
    """
    ====================
    DuckDB database sink
    ====================

    Install Python driver::

        pip install duckdb

    Acquire data::

        wetterdienst dwd observation values --stations=1048,4411 --parameters=daily/kl --periods=recent --target="duckdb:///dwd.duckdb?table=weather"

    Example queries::

        python -c 'import duckdb; c = duckdb.connect(database="dwd.duckdb"); print(c.table("weather"))'
        python -c 'import duckdb; c = duckdb.connect(database="dwd.duckdb"); print(c.execute("SELECT * FROM weather").df())'

    """  # noqa:E501
    log.info(f"Writing to DuckDB. database={database}, table={tablename}")
    duckdb = import_optional("duckdb", "Writing to DuckDB", extra="duckdb")

    df = copy(result.df)

    df = df.with_columns(cs.datetime().dt.replace_time_zone(None))

    connection = duckdb.connect(database=database, read_only=False)
    try:
        connection.register("origin", df)
        if if_exists == "replace":
            connection.execute(f"DROP TABLE IF EXISTS {tablename};")
            connection.execute(f"CREATE TABLE {tablename} AS SELECT * FROM origin;")  # noqa: S608
        elif if_exists == "append":
            result = connection.execute(
                f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name='{tablename}';",  # noqa: S608
            )
            row = result.fetchone()
            exists = row is not None and row[0] > 0
            if not exists:
                connection.execute(f"CREATE TABLE {tablename} AS SELECT * FROM origin;")  # noqa: S608
            else:
                # `BY NAME`, because a plain `INSERT ... SELECT *` matches by position: two runs
                # whose frames carry the same number of columns under different names were
                # accepted, and the second one's values landed under the first one's headings.
                # A `--shape=wide` schedule does that by changing one parameter -- a day's
                # precipitation was filed as its temperature, exit 0 and nothing said. Matching
                # by name refuses that with `Binder Error: Table "weather" does not have a
                # column with name "precipitation_amount"`, and still accepts a frame whose
                # columns are a subset, filling the rest with nulls
                connection.execute(f"INSERT INTO {tablename} BY NAME SELECT * FROM origin;")  # noqa: S608
        elif if_exists == "fail":
            # Will fail if table exists
            try:
                connection.execute(f"CREATE TABLE {tablename} AS SELECT * FROM origin;")  # noqa: S608
            except duckdb.CatalogException as e:
                msg = f"Table '{tablename}' already exists in the database, aborting write due to if_exists='fail'."
                raise ExportRefusedError(msg) from e
        elif if_exists == "skip":
            # Only create if not exists, skip if exists
            result = connection.execute(
                f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name='{tablename}';"  # noqa: S608
            )
            row = result.fetchone()
            exists = row is not None and row[0] > 0
            if not exists:
                connection.execute(f"CREATE TABLE {tablename} AS SELECT * FROM origin;")  # noqa: S608
            else:
                log.info(f"Table {tablename} exists, skipping write due to if_exists='skip'.")
    finally:
        connection.close()
    log.info("Writing to DuckDB finished")


def _write_influxdb(result: ExportMixin, target: str, connspec: ConnectionString, if_exists: IfExists) -> None:  # noqa: ARG001, C901
    """Write the frame to InfluxDB, of the version the protocol names."""
    protocol = connspec.protocol
    database = connspec.database
    tablename = connspec.table
    """
    ==========================
    InfluxDB 1.x database sink
    ==========================

    Install Python driver::

        pip install influxdb

    Run database::

        docker run -it --rm --publish=8086:8086 influxdb:1.8

    Acquire data::

        alias fetch="wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent --stations=1048,4411"
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
        # percent-encode a `%` or `@` in the token, and a `%`, `@`, `:` or `/` in the
        # organization (`%25`, `%40`, `%3A`, `%2F`)

        alias fetch="wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent --stations=1048,4411"
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
        # percent-encode a `%` or `@` in the token, and a `%`, `@`, `:` or `/` in the
        # organization (`%25`, `%40`, `%3A`, `%2F`)
        INFLUXDB_HOST="eu-central-1-1.aws.cloud2.influxdata.com"

        alias fetch="wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent --stations=1048,4411"
        fetch --target="influxdb3s://${INFLUXDB_ORGANIZATION}:${INFLUXDB_TOKEN}@${INFLUXDB_HOST}/?database=dwd&table=weather"

    Example queries::

        influx query 'from(bucket:"dwd") |> range(start:-2d) |> limit(n: 10)'
    """  # noqa:E501
    # every write here is points, and a point carrying the timestamp and tags another
    # already has replaces that one, so what this sink does is exactly `append`. Refusing
    # that spelling made the batch export impossible: `TimeseriesValues.to_target` writes
    # its first station with the `if_exists` it was given and every station after it with
    # `append`, so no argument let a multi-station request reach InfluxDB at all.
    #
    # `replace` is accepted for the same reason it always was -- it is the default, and a
    # caller who has not thought about the question should not be stopped -- but it does
    # not delete what is already in the measurement, because nothing here issues a delete.
    # `fail` and `skip` are refused rather than quietly meaning `append`: both turn on
    # whether the measurement already exists, and this sink never asks
    if if_exists in ("fail", "skip"):
        msg = (
            f"if_exists='{if_exists}' is not supported for InfluxDB exports, which would "
            f"have to ask whether the measurement exists; use 'append' or 'replace'."
        )
        raise ExportRefusedError(msg)

    if protocol in ["influxdb", "influxdbs", "influxdb1", "influxdb1s"]:
        version = 1
    elif protocol in ["influxdb2", "influxdb2s"]:
        version = 2
    elif protocol in ["influxdb3", "influxdb3s"]:
        version = 3
    else:
        msg = f"Unknown protocol variant '{protocol}' for InfluxDB"
        raise ExportRefusedError(msg)

    # a point is a reading at a time of a station, resolution and dataset: a frame without these, such as the stations
    # (`start_timestamp` and `end_timestamp`, no `timestamp`), has nothing to write, and failed with a bare `KeyError`
    # on the first row after the client had connected
    missing = [name for name in ("timestamp", "station_id", "resolution", "dataset") if name not in result.df.columns]
    if missing:
        msg = (
            f"InfluxDB stores readings at a time, and this frame has no {', '.join(f'`{name}`' for name in missing)} "
            f"column to make a point of; write it to a file or another database instead (duckdb://, sqlite://, ...)."
        )
        raise ExportRefusedError(msg)

    log.info(f"Writing to InfluxDB version {version}. database={database}, table={tablename}")

    # the InfluxDB 2 and 3 clients take the server as one URL: https for the `s` variants,
    # the target's port, and an IPv6 host in the brackets `ConnectionString` reads it out of.
    # The InfluxDB 1 client formats its host into its base URL as given, so it gets them too;
    # it reads the host nowhere else but for UDP, which this sink does not use
    scheme = "https" if protocol.endswith("s") else "http"
    netloc = f"[{connspec.host}]" if ":" in (connspec.host or "") else connspec.host

    # Set up the connection.
    if version == 1:
        influxdb = import_optional("influxdb", "Writing to InfluxDB 1", extra="influxdb")

        client_v1 = influxdb.InfluxDBClient(
            host=netloc,
            port=connspec.port or 8086,
            username=connspec.username,
            password=connspec.password,
            database=database,
            ssl=protocol.endswith("s"),
            # the client's own default is not to check the server's certificate, which left the
            # `s` of the scheme promising a TLS that anyone on the path could stand in for. True
            # is what `requests` reads `REQUESTS_CA_BUNDLE` for, so a certificate of one's own
            # is trusted by naming its CA there, not by switching the check off (GH-3342)
            verify_ssl=True,
        )
        client_v1.create_database(database)
    elif version == 2:
        influxdb_client = import_optional("influxdb_client", "Writing to InfluxDB 2", extra="influxdb")
        write_api_module = import_optional(
            "influxdb_client.client.write_api", "Writing to InfluxDB 2", extra="influxdb"
        )
        PointV2 = influxdb_client.Point  # noqa: N806

        url = f"{scheme}://{netloc}:{connspec.port or 8086}"
        client_v2 = influxdb_client.InfluxDBClient(url=url, org=connspec.username or "", token=connspec.password or "")
        write_api = client_v2.write_api(write_options=write_api_module.SYNCHRONOUS)
    elif version == 3:
        influxdb_client_3 = import_optional("influxdb_client_3", "Writing to InfluxDB 3", extra="influxdb")
        write_api_module = import_optional(
            "influxdb_client_3.write_client.client.write_api", "Writing to InfluxDB 3", extra="influxdb"
        )
        PointV3 = influxdb_client_3.Point  # noqa: N806

        write_options = influxdb_client_3.WriteOptions(write_type=write_api_module.WriteType.synchronous)
        wco = influxdb_client_3.write_client_options(WriteOptions=write_options)
        # with no port, 443 for https, as the client defaults to whatever the scheme, and
        # for http the 8181 an InfluxDB 3 Core listens on. No host is left to the client,
        # which refuses it by name
        port = connspec.port or (443 if scheme == "https" else 8181)
        client_v3 = influxdb_client_3.InfluxDBClient3(
            host=connspec.host and f"{scheme}://{netloc}:{port}",
            org=connspec.username,
            token=connspec.password,
            write_client_options=wco,
            database=database,
        )

    points = []
    for record in result.df.iter_rows(named=True):
        # for record in items.iter_rows(named=True):
        time = record.pop("timestamp").isoformat()
        tags = {
            "station_id": record.pop("station_id"),
            "resolution": record.pop("resolution"),
            "dataset": record.pop("dataset"),
        }
        parameter = record.pop("parameter", None)
        # the flags of a long row go beside its value and never alone; a wide row names each flags column
        # after its parameter, and those are fields like the values
        quality_flags = record.pop("quality_flags", None)
        # fields is a dict of either a single value (long format) or multiple values (wide format).
        fields = {k: v for k, v in record.items() if v is not None}
        # the same for a wide row, for the flags `raw:` gives a value mapped from a sentinel: they are not
        # written without the value (GH-2759). Any other flag of a missing value is written as before
        fields = {
            k: v
            for k, v in fields.items()
            if not (
                k.endswith("_quality_flags")
                and "raw:" in str(v)
                and record.get(k.removesuffix("_quality_flags")) is None
            )
        }
        if not fields:
            continue
        if version == 1:
            if parameter:
                tags["parameter"] = parameter
                if quality_flags:
                    fields["quality_flags"] = quality_flags
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
                if quality_flags:
                    point = point.field("quality_flags", quality_flags)
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
                if quality_flags:
                    point = point.field("quality_flags", quality_flags)
            for field, value in fields.items():
                point = point.field(field, value)

        points.append(point)

    # Write to InfluxDB.
    if version == 1:
        client_v1.write_points(
            points=points,
            batch_size=50000,
        )
    elif version == 2:
        write_api.write(bucket=database, record=points)
        write_api.close()
    elif version == 3:
        client_v3.write(record=points)

    log.info("Writing to InfluxDB finished")


def _write_cratedb(result: ExportMixin, target: str, connspec: ConnectionString, if_exists: IfExists) -> None:
    """Write the frame to CrateDB."""
    database = connspec.database
    tablename = connspec.table
    """
    =====================
    CrateDB database sink
    =====================

    Install Python driver::

        pip install wetterdienst[cratedb] crash

    Run database::

        docker run -it --rm --publish=4200:4200 --env CRATE_HEAP_SIZE=2048M crate/crate:nightly

    Acquire data::

        wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent --stations=1048,4411 --target="crate://crate@localhost/dwd?table=weather"

    Example queries::

        psql postgres://crate@localhost --command 'SELECT * FROM dwd.weather;'

        crash -c 'select * from dwd.weather;'
        crash -c 'select count(*) from dwd.weather;'
        crash -c "select *, date_format('%Y-%m-%dT%H:%i:%s.%fZ', timestamp) as datetime from dwd.weather order by datetime limit 10;"

    """  # noqa:E501
    log.info(f"Writing to CrateDB. target={redact_password(target)}, table={tablename}")

    # the dialect first: it is what `to_sql` loads by the name `crate`, and SQLAlchemy alone
    # does not carry it, so without it the `export` extra is no help
    import_optional("sqlalchemy_cratedb", "Writing to CrateDB", extra="cratedb")
    sqlalchemy = import_optional("sqlalchemy", "Writing to CrateDB", extra="export")

    # CrateDB's SQLAlchemy driver doesn't accept `database` or `table` query parameters.
    # Rebuilt from the reading above, with the password encoded again, so SQLAlchemy reads
    # it back as the same password whatever it holds
    cratedb_target = sqlalchemy.engine.URL.create(
        "crate",
        username=connspec.username,
        password=connspec.password,
        host=connspec.host,
        port=connspec.port,
    ).render_as_string(hide_password=False)

    # Convert timezone-aware datetime fields to naive ones.
    # FIXME: Omit this as soon as the CrateDB driver is capable of supporting timezone-qualified timestamps.
    # Cast an Enum column, which a caller may have made of the frame's own, to String so the
    # pandas/SQLAlchemy write gets plain text.
    df = result.df.with_columns(
        cs.datetime().dt.replace_time_zone(time_zone=None),
        pl.col(pl.Enum).cast(pl.String),
    )
    if if_exists in ("skip", "fail"):
        engine = sqlalchemy.create_engine(cratedb_target)
        insp = sqlalchemy.inspect(engine)
        if insp.has_table(tablename, schema=database):
            if if_exists == "skip":
                log.info(f"Table {tablename} exists, skipping write due to if_exists='skip'.")
                return
            # asked ourselves rather than letting pandas raise its own `ValueError`, so that
            # a refusal is one class wherever it comes from
            msg = f"Table '{tablename}' already exists in the database, aborting write due to if_exists='fail'."
            raise ExportRefusedError(msg)
    df.to_pandas().to_sql(
        name=tablename,
        con=cratedb_target,
        schema=database,
        if_exists=if_exists if if_exists != "skip" else "fail",
        index=False,
        chunksize=5000,
    )
    log.info("Writing to CrateDB finished")


def _write_sqlalchemy(result: ExportMixin, target: str, connspec: ConnectionString, if_exists: IfExists) -> None:  # noqa: C901
    """Write the frame to any database SQLAlchemy has a dialect for."""
    tablename = connspec.table
    """
    ================================
    Generic SQLAlchemy database sink
    ================================

    Install Python driver::

        pip install sqlalchemy

    Examples::

        # Prepare
        alias fetch='wetterdienst values --provider=dwd --network=observation --parameters=daily/kl
            --periods=recent --stations=1048,4411'

        # Acquire data.
        fetch --target="sqlite:///dwd.sqlite?table=weather"

        # Query data.
        sqlite3 dwd.sqlite "SELECT * FROM weather;"

    """
    chunk_size = 5000

    log.info("Writing to SQL database")
    sqlalchemy = import_optional("sqlalchemy", "Writing to a SQL database", extra="export")
    from sqlalchemy.dialects.mssql.base import DATETIME2, NVARCHAR, MSDialect  # noqa: PLC0415
    from sqlalchemy.dialects.mysql.base import MySQLDialect  # noqa: PLC0415

    # `table` is ours, read above to name the table; SQLAlchemy hands every query argument
    # to the driver as a connection option, and psycopg, psycopg2, mysqlclient and pymysql
    # refuse one they do not know, so a `postgresql://` or `mysql://` target could not
    # connect at all. Only `table` goes: the rest of the query (`sslmode`, `charset`, ...)
    # is the driver's
    # SQLAlchemy's own reading, which `ConnectionString` copies; read here by SQLAlchemy
    # itself because 2.0 leaves the database as written and 2.1 decodes it
    url = sqlalchemy.make_url(target).difference_update_query(["table"])
    # the protocols this sink writes are the dialects SQLAlchemy has, so it is asked, and
    # before an engine is made: an unknown one would come out of `create_engine` as
    # SQLAlchemy's `NoSuchModuleError`, a failure of ours to the CLI and a traceback to a caller
    try:
        url.get_dialect()
    except sqlalchemy.exc.NoSuchModuleError as e:
        msg = (
            f"Unknown export protocol '{url.drivername}': nothing here writes it. Supported are "
            f"file://, duckdb://, influxdb://, crate:// and the SQLAlchemy dialects that are installed, "
            f"such as sqlite://, postgresql:// and mysql://."
        )
        raise ExportRefusedError(msg) from e
    if url.get_backend_name() == "sqlite":
        # Honour SQLite's SQLITE_MAX_VARIABLE_NUMBER, which defaults to 999 for SQLite
        # versions prior to 3.32.0 (2020-05-22) and to 32766 from then on, see
        # https://www.sqlite.org/limits.html#max_variable_number. A multi-row insert
        # carries one variable per cell, so the rows per insert follow from the columns.
        # Decided on the parsed URL, not the string: `sqlite+pysqlite://` and
        # `sqlite+pysqlcipher://` name their driver and are SQLite all the same
        import sqlite3  # noqa: PLC0415

        max_variables = 999 if sqlite3.sqlite_version_info < (3, 32, 0) else 32766
        chunk_size = min(chunk_size, max_variables // len(result.df.columns))
    if url.get_backend_name() == "postgresql":
        # a bare `postgresql://` means psycopg2 to SQLAlchemy 2.0 and psycopg 3 to 2.1,
        # which needs Python 3.11, so both are allowed. The `postgresql` extra installs
        # psycopg 3: named here, the same URL finds it on either. A target naming its
        # driver keeps it, and without psycopg 3 SQLAlchemy picks as it always did
        if url.drivername == "postgresql" and _psycopg_imports():
            url = url.set(drivername="postgresql+psycopg")
        # psycopg 3 and pg8000 bind on the server, which takes at most 65535 parameters a
        # statement, and a multi-row insert carries one per cell. psycopg2 binds on the
        # client and needs no cap, but smaller inserts cost it nothing but round trips
        chunk_size = min(chunk_size, 65535 // len(result.df.columns))
    try:
        engine = sqlalchemy.create_engine(url)
    except ModuleNotFoundError as e:
        # the driver behind the URL (`MySQLdb`, `psycopg2`) is imported here, by SQLAlchemy
        missing = _driver_missing(e, url)
        if missing is None:
            raise
        raise missing from e
    try:
        if if_exists in ("skip", "fail") and sqlalchemy.inspect(engine).has_table(tablename):
            if if_exists == "skip":
                log.info(f"Table {tablename} exists, skipping write due to if_exists='skip'.")
                return
            # asked ourselves rather than letting pandas raise its own `ValueError`, so that
            # a refusal is one class wherever it comes from
            msg = f"Table '{tablename}' already exists in the database, aborting write due to if_exists='fail'."
            raise ExportRefusedError(msg)
        columns = [pl.col(pl.Enum).cast(pl.String)]
        # `to_sql` takes SQLAlchemy types here, which pandas' annotation leaves out
        dtype: dict[Any, Any] | None = None
        if isinstance(engine.dialect, (MySQLDialect, MSDialect)):
            # pandas writes a zoned datetime as `TIMESTAMP(timezone=True)`, which MySQL,
            # MariaDB and the dialects built on theirs compile to a plain `TIMESTAMP`:
            # nothing before 1970, and converted from the session's time zone, so a
            # pre-1970 row is refused or stored as zeros. A naive one becomes `DATETIME`
            # (years 1000 to 9999), so every datetime column goes in as naive UTC.
            # SQL Server compiles it to `TIMESTAMP` too, which there is `rowversion`, a
            # row counter that takes no value at all
            columns.append(cs.datetime().dt.convert_time_zone("UTC").dt.replace_time_zone(None))
        frame = result.df.with_columns(columns)
        if isinstance(engine.dialect, MSDialect):
            # SQL Server takes at most 2100 parameters a request, 2099 here to leave room
            # for a driver that counts one more, and 1000 rows in a table value constructor
            chunk_size = min(chunk_size, 1000, 2099 // len(result.df.columns))
            # a naive datetime would be SQL Server's `DATETIME`, which starts in 1753 and
            # rounds to 1/300 s; `DATETIME2` holds every year a Python datetime can
            dtype = {name: DATETIME2() for name in frame.select(cs.datetime()).columns}
            # pandas declares text as `Text`, which is `VARCHAR(max)` here (`TEXT` before
            # SQL Server 2012): stored in the column's code page, so under a collation
            # such as `SQL_Latin1_General_CP1_CI_AS` (Windows-1252, the default of an
            # English install) a name like `Łódź` or `Třeboň` loses every character
            # outside it to a `?`.
            # `NVARCHAR(max)` holds Unicode. Read off the frame after the Enum cast, and
            # with a column of nothing but nulls, which pandas also declares as `Text`
            dtype |= {
                name: NVARCHAR()
                for name in frame.select(cs.string(include_categorical=True), cs.by_dtype(pl.Null)).columns
            }
        frame.to_pandas().to_sql(
            name=tablename,
            con=engine,
            if_exists=if_exists if if_exists != "skip" else "fail",
            index=False,
            method="multi",
            chunksize=chunk_size,
            dtype=dtype,
        )
    finally:
        engine.dispose()
    log.info("Writing to SQL database finished")


#: the sinks, by the scheme of the target: `file://`, `duckdb://` and `crate://` as written, and every variant of
#: `influxdb` (`influxdb2s://`) by the protocol, which is lower-cased. Any other target goes to `_write_sqlalchemy`
SINKS: dict[str, Sink] = {
    "file": _write_file,
    "duckdb": _write_duckdb,
    "influxdb": _write_influxdb,
    "crate": _write_cratedb,
}


def find_sink(target: str, protocol: str) -> Sink:
    """Name the sink that writes the target: the scheme it starts with, else the protocol it names, else SQLAlchemy."""
    if protocol.startswith("influxdb"):
        return SINKS["influxdb"]
    for scheme, sink in SINKS.items():
        if scheme != "influxdb" and target.startswith(f"{scheme}://"):
            return sink
    return _write_sqlalchemy
