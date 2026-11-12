# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Filter a frame with the WHERE clause of an SQL query, run on DuckDB."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import polars as pl
import polars.selectors as cs

from wetterdienst.metadata.aliases import use_alias
from wetterdienst.metadata.renamed import aliased_column, renamed_column
from wetterdienst.util.extras import import_optional

if TYPE_CHECKING:
    from wetterdienst.metadata.aliases import ParameterAlias

#: DuckDB's own message for a column the clause names and the frame lacks, anchored at its start: a clause can make
#: DuckDB write text of its own choosing into another binder error (a struct key spelled as this message), which
#: must not be read as a missing column
_MISSING_COLUMN = re.compile(
    r'Binder Error: (?:Referenced column|[A-Za-z ]+ "[^"]+" does not have a column named) "([^"]+)"',
)


class _AliasedColumnError(Exception):
    """A column of a SQL clause that the frame lacks, but holds under the name its parameter was renamed to.

    Never leaves `filter_by_sql`, which adds the column under the old name and runs the clause again.
    """

    def __init__(self, name: str, column: str, parameter: str, alias: ParameterAlias) -> None:
        super().__init__(name)
        self.name = name
        self.column = column
        self.parameter = parameter
        self.alias = alias


def filter_by_sql(df: pl.DataFrame, sql: str) -> pl.DataFrame:
    """Filter df using an SQL query WHERE clause, a column named by an alias of its parameter taken as the new one.

    A column that the frame lacks and that is the old name of a renamed parameter (`wetterdienst.metadata.aliases`)
    is read from the column it was renamed to, with the warning of every alias; the answer holds the frame's own
    columns only.
    """
    frame = df
    aliased: list[str] = []
    while True:
        try:
            filtered = _filter_by_sql_clause(frame, sql)
        except _AliasedColumnError as e:
            # the same name again: the retry did not help, and the caller's own error is the answer
            if e.name in aliased and e.__cause__ is not None:
                raise e.__cause__ from None
            use_alias(e.parameter, e.alias)
            aliased.append(e.name)
            frame = frame.with_columns(pl.col(e.column).alias(e.name))
            continue
        return filtered.drop(aliased)


def _filter_by_sql_clause(df: pl.DataFrame, sql: str) -> pl.DataFrame:
    """Filter df using an SQL query WHERE clause.

    This implementation is based on DuckDB, so please
    have a look at its SQL documentation.

    - https://duckdb.org/docs/sql/introduction

    The clause runs on a DuckDB connection of its own, which holds the frame as `df` and nothing
    else: it cannot read or list files, reach the network or install or load extensions, and
    raises a `duckdb.Error` when it tries (`PermissionException` for a file or a URL). It is
    parsed as a single condition in parentheses, so anything after it -- a second statement,
    `ORDER BY`, `LIMIT`, `WHERE`, `FROM` -- raises `duckdb.ParserException`, unless it closes
    those parentheses itself, when DuckDB ignores a trailing `FROM`; trailing semicolons and
    whitespace are dropped. It runs on one thread with DuckDB's memory limit at 1 GiB plus the
    frame's size and nowhere to spill to, and raises `duckdb.OutOfMemoryException` when DuckDB's
    buffers would grow past that.

    Args:
        df: DataFrame to filter
        sql: SQL WHERE clause

    Returns:
        Filtered DataFrame

    """
    duckdb = import_optional("duckdb", "Filtering with SQL", extra="sql")

    # every timestamp the frame carries, not the values column alone (then `date`): a stations
    # frame has `start_timestamp` and `end_timestamp` and no `timestamp` at all, so the CLI's own
    # `--sql "state=\'Sachsen\'"` (as it then was) -- documented as a filter on station metadata
    # -- died on a missing column
    zones = {name: dtype.time_zone for name, dtype in df.schema.items() if isinstance(dtype, pl.Datetime)}
    df = df.with_columns(cs.datetime().dt.replace_time_zone(None))
    # the clause is the caller's, and the REST API and MCP server pass it on from anyone who can
    # reach them: DuckDB's default connection would let it read and list files on this host
    # (`read_csv`, `read_text`, `glob`) or load an extension, so it runs on a connection of its
    # own that refuses every file system access and extension, and cannot be told otherwise.
    # No temp directory either: DuckDB lets its own (`.tmp` under the working directory) through
    # with external access off, and the clause could read and list files there.
    # It also gets one core, and DuckDB's buffers at 1 GiB plus the frame's size without spilling
    # to disk, so a clause building something huge there (`(SELECT list(i) FROM range(1e9)
    # t(i))`) fails fast rather than taking every core and most of the memory. The frame is
    # scanned in place, but a subquery over it builds in proportion to it: a 40-million-row,
    # 1.3 GiB values frame needs more than 1 GiB for `station_id IN (SELECT station_id FROM df
    # WHERE value > 10)`, and filters with it in under five seconds within 1 GiB plus its size.
    # Not bounded: how long a clause runs on its core, and what it allocates outside the
    # buffers, such as one very long string from `repeat()` or a list from scalar `range()`
    memory_limit = 2**30 + df.estimated_size()
    con = duckdb.connect(
        config={
            "temp_directory": "",
            "threads": 1,
            "memory_limit": f"{memory_limit}B",
            "max_temp_directory_size": "0B",
        },
    )
    try:
        # in this order, after the rest: DuckDB applies a config dict in an order of its own, and
        # refuses an empty `temp_directory` set after external access is off
        con.execute("SET enable_external_access = false")
        con.execute("SET lock_configuration = true")
        con.register("df", df)
        # parsed as one expression, not pasted into a statement: `true; SELECT ...` would run
        # the statements after it and return their result in place of the filtered frame. In
        # parentheses, as DuckDB drops a trailing `FROM` or `AS` from a filter expression without
        # a word, and before 1.5 a trailing `ORDER BY`, `LIMIT` or `WHERE` too; the newline keeps
        # a trailing `--` comment from swallowing the closing one
        # trailing semicolons and whitespace, Unicode's included, in one pass from the end: the
        # regex `[\s;]+$` backtracks quadratically over a long run of either followed by anything
        # else, and the clause is the caller's to make as long as they like
        end = len(sql)
        while end and (sql[end - 1].isspace() or sql[end - 1] == ";"):
            end -= 1
        clause = sql[:end]
        df = con.table("df").filter(f"({clause}\n)").pl()
    except duckdb.BinderException as e:
        # unqualified (`height`) or qualified by the table (`df.height`), which DuckDB words apart
        missing = _MISSING_COLUMN.match(str(e))
        # only a name the frame lacks is a candidate; the column is added by name through polars, so no text of
        # an error ever reaches the SQL that is run again
        lacking = missing and missing.group(1).lower() not in {column.lower() for column in df.columns}
        aliased = aliased_column(missing.group(1), df.columns) if missing and lacking else None
        if missing and aliased:
            raise _AliasedColumnError(missing.group(1), *aliased) from e
        new = renamed_column(missing.group(1), df.columns) if missing else None
        if missing and new:
            msg = f'column "{missing.group(1)}" was renamed to "{new}"'
            raise duckdb.BinderException(msg) from e
        raise
    finally:
        con.close()
    return df.with_columns(
        pl.col(name).dt.replace_time_zone(zone) for name, zone in zones.items() if zone and name in df.columns
    )
