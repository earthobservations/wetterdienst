# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The schemas of the frames a result holds, as objects a caller and a test can assert against.

A frame is what a result hands over in ``.df``, so its column names, order and dtypes are part of
what the library promises. They are declared here, once, and the code that builds a frame is built
from them rather than the other way round::

    from wetterdienst.model.schema import LONG_SCHEMA

    assert request.filter_by_station_id("01048").values().all().df.schema == LONG_SCHEMA

``station_id``, ``resolution``, ``dataset`` and ``parameter`` are ``String`` in every one of them,
populated or empty, from one request or from another, so that two results concatenate and a result
joins against a stations frame without a cast. ``timestamp`` is UTC to the microsecond.

A schema is a :class:`polars.Schema`, which is ordered and compares equal to another with the same
names, order and dtypes (and to a ``dict`` of them). The library builds its frames from these very
objects, so treat them as read-only: copy one with ``pl.Schema(LONG_SCHEMA)`` to change it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from collections.abc import Iterable

#: the one type every timestamp column has, whichever provider it comes from and whether the frame
#: holds values, interpolated values or a summary: UTC, to the microsecond. A source that stamps in
#: local time or in nanoseconds is converted by its provider, not passed on.
TIMESTAMP_DTYPE = pl.Datetime(time_unit="us", time_zone="UTC")

#: the columns that say which series a row belongs to; ``String`` on every frame that carries them
IDENTITY_COLUMNS = ("station_id", "resolution", "dataset", "parameter")

#: what a request's stations are described by (``StationsResult.df``). A provider may add columns of
#: its own, such as WSV's ``gauge_zero`` or the ``icao_id`` of the DWD forecast networks, among or after
#: these; these columns keep their dtypes and their order relative to each other.
STATIONS_SCHEMA = pl.Schema(
    {
        "resolution": pl.String,
        "dataset": pl.String,
        "station_id": pl.String,
        "start_timestamp": TIMESTAMP_DTYPE,
        "end_timestamp": TIMESTAMP_DTYPE,
        "latitude": pl.Float64,
        "longitude": pl.Float64,
        "elevation": pl.Float64,
        "name": pl.String,
        "region": pl.String,
    },
)

#: the long shape (``Options(shape="long")``), one row per reading. ``quality_flags`` is every flag
#: the source publishes for the reading, as one string: the plain code of a source with one flag,
#: ``kind:code`` tokens of a source with several, comma-separated in a fixed order per provider, and a
#: last ``raw:<text>`` token for a value mapped from a missing-value sentinel; null where the source
#: published none.
LONG_SCHEMA = pl.Schema(
    {
        "station_id": pl.String,
        "resolution": pl.String,
        "dataset": pl.String,
        "parameter": pl.String,
        "timestamp": TIMESTAMP_DTYPE,
        "value": pl.Float64,
        "quality_flags": pl.String,
    },
)

#: the columns of the wide shape (``Options(shape="wide")``) that do not depend on the request, one
#: row per timestamp. ``dataset`` is null on a row of a resolution that holds several requested
#: datasets. When the request spans several datasets, the columns of the parameters are prefixed with
#: their dataset's name. They follow these, in the order the request names the parameters, see
#: :func:`wide_schema`.
WIDE_SCHEMA = pl.Schema(
    {
        "station_id": pl.String,
        "resolution": pl.String,
        "dataset": pl.String,
        "timestamp": TIMESTAMP_DTYPE,
    },
)

#: the dtype of the column of a parameter in the wide shape, and of the column of its flags
WIDE_VALUE_DTYPE = pl.Float64()
WIDE_FLAGS_DTYPE = pl.String()

#: the suffix of the column of a parameter's flags in the wide shape
WIDE_FLAGS_SUFFIX = "_quality_flags"

#: ``InterpolatedValuesResult.df``: one row per timestamp and parameter, with the mean distance of the
#: stations the value was made of and their ids
INTERPOLATED_SCHEMA = pl.Schema(
    {
        "station_id": pl.String,
        "resolution": pl.String,
        "dataset": pl.String,
        "parameter": pl.String,
        "timestamp": TIMESTAMP_DTYPE,
        "value": pl.Float64,
        "distance_mean": pl.Float64,
        "taken_station_ids": pl.List(pl.String),
    },
)

#: ``SummarizedValuesResult.df``: one row per timestamp and parameter, with the distance of the station
#: the value was taken from and its id
SUMMARIZED_SCHEMA = pl.Schema(
    {
        "station_id": pl.String,
        "resolution": pl.String,
        "dataset": pl.String,
        "parameter": pl.String,
        "timestamp": TIMESTAMP_DTYPE,
        "value": pl.Float64,
        "distance": pl.Float64,
        "taken_station_id": pl.String,
    },
)


def wide_schema(parameters: Iterable[str]) -> pl.Schema:
    """Give the schema of a wide frame for the named parameters, in the order a result holds them.

    A populated frame has the columns of the parameters that were delivered, so it is this schema when
    every named parameter was.

    Args:
        parameters: the names of the columns of the parameters, which carry their dataset's name as
            a prefix when the request spans several datasets.

    Returns:
        The columns of ``WIDE_SCHEMA``, then for each parameter its value and its flags.

    """
    columns = dict(WIDE_SCHEMA)
    for parameter in parameters:
        columns[parameter] = WIDE_VALUE_DTYPE
        columns[f"{parameter}{WIDE_FLAGS_SUFFIX}"] = WIDE_FLAGS_DTYPE
    return pl.Schema(columns)


def select_schema(schema: pl.Schema, columns: Iterable[str]) -> pl.Schema:
    """Give the part of a schema that names the columns, in the order they are named in."""
    return pl.Schema({column: schema[column] for column in columns})


def coerce(df: pl.DataFrame, schema: pl.Schema) -> pl.DataFrame:
    """Cast the columns of a frame that the schema names to its dtypes, leaving the others as they are.

    A column of the schema that the frame does not have is left out rather than added: what a frame
    is missing is for the code that builds it to say.
    """
    return df.with_columns(
        pl.col(column).cast(dtype)
        for column, dtype in schema.items()
        if column in df.columns and df.schema[column] != dtype
    )
