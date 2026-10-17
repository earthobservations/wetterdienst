# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Build the ``quality_flags`` string of a reading from the flags its source publishes.

The column is one nullable string. The source's ordinary quality flag is written as the plain code the
source writes (``T``, ``Good``, ``3``) and comes first; every further kind of flag a source publishes
is a ``kind:code`` token after it, comma-separated, in the fixed order the provider lists them in
(GHCN: ``G,measurement:T,source:7``; CHMI: ``3,element:E``). The prefix ``quality:`` is never written,
so a plain token is always the quality flag. A blank flag is left out and a reading without any flag is
null.

Building every provider's column here keeps that format in one place: a further kind is one more
keyword at the end of the call, and the format a caller splits on (``str.split(",")``) does not change.

The last kind is ``raw``: a value a reader maps from a missing-value sentinel to null (or to the value the
source documents it to mean) carries the text the source wrote in its place, ``raw:-999`` (GH-2759).
``null_sentinels`` is the one place that maps a sentinel and returns that text with the cleaned value, so a
reader cannot do the one and forget the other.

A value no sensor can have produced, a number outside the physical range of its parameter that is no code
(4021 °C beside a daily mean of 110 °C), is mapped the same way: ``OutOfRange`` is a rule of ``null_sentinels``
beside ``Sentinel``, and the value is read as ``raw:4021`` (GH-2797). The bounds are the reader's, per resolution where
the quantity grows with the span, in the unit of the source, and generous: a value that is only odd stays.

A stuck or dead sensor over a period of time gives values inside every range. ``NoReading`` maps what a
station, a parameter and a period select to null the same way, keeping the value as ``raw`` (GH-3031).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

import polars as pl

if TYPE_CHECKING:
    from collections.abc import Iterable

QUALITY_FLAGS = "quality_flags"
# the kind of the token that records the sentinel a value was mapped from, always the last one
RAW = "raw"
# a regular expression for the token, in a `quality_flags` string
RAW_TOKEN = rf"(^|,){RAW}:"
# the suffix of the column that carries `raw` beside a value column of a wide frame, until the frame is made long
RAW_SUFFIX = "__raw"

Frame = TypeVar("Frame", pl.DataFrame, pl.LazyFrame)


def join_quality_flags(quality: pl.Expr | None = None, /, **kinds: pl.Expr) -> pl.Expr:
    """Join the flags of a reading into the value of the ``quality_flags`` column.

    Args:
        quality: the expression of the source's ordinary quality flag, written as a plain code; ``None``
            for a source that publishes only the other kinds.
        **kinds: every further kind of flag as ``kind=expression``, written ``kind:code``. They come out in
            the order they are given, after the quality flag.

    Returns:
        The expression of the column. A flag that is null or blank (after stripping) is left out, and a
        reading none of whose flags is set is null. A code is passed as the string or the integer the source
        writes: a float would be written ``3.0``.

    """
    tokens = []
    if quality is not None:
        tokens.append(_as_code(quality))
    tokens.extend(
        pl.when(code.is_not_null()).then(pl.lit(f"{kind}:") + code)
        for kind, code in ((kind, _as_code(expr)) for kind, expr in kinds.items())
    )
    if not tokens:
        msg = "at least one flag is needed"
        raise ValueError(msg)
    joined = pl.concat_str(tokens, separator=",", ignore_nulls=True)
    return pl.when(joined.str.len_chars() > 0).then(joined).alias(QUALITY_FLAGS)


def _as_code(expr: pl.Expr) -> pl.Expr:
    """Read a flag as the text of its code: stripped, and null where it is blank."""
    return expr.cast(pl.String).str.strip_chars().replace("", None)


class Sentinel:
    """One way a source writes "no value", and what a reader makes of it.

    Args:
        *texts: the sentinel as the source writes it (``"-999"``, ``"99.9"``, ``"NaN"``, or in a column of text
            one that is no number, ``"-None"``), at least one. The text is what ends up in the ``raw`` token of a
            value read from a number, so it is written as the source documents it and never as a float
            (``"-999"``, not ``"-999.0"``). A value read from text carries the text of its own cell instead.
        where: restricts the sentinel to the values this expression selects (a parameter, a dataset), for a
            code that is a sentinel in one column and a reading in the next.
        to: the value the source documents the sentinel to mean (``0.0`` for "no precipitation"); ``None``,
            the default, makes the value null.

    """

    def __init__(self, *texts: str, where: pl.Expr | None = None, to: float | None = None) -> None:
        """Declare a sentinel, refusing a text that could not be a token of ``quality_flags``."""
        if not texts:
            msg = "a sentinel needs the text the source writes"
            raise ValueError(msg)
        for text in texts:
            # the token is one element of a comma-separated string
            if not text.strip() or "," in text:
                msg = f"{text!r} cannot be the text of a sentinel: it is blank or holds a comma"
                raise ValueError(msg)
        self.texts = tuple(text.strip() for text in texts)
        self.where = where
        self.to = to


class OutOfRange:
    """A reading outside the physical range of its parameter, which no sensor can have produced.

    The rule of a value that is no sentinel (it repeats no number) but a row of the source that cannot be a
    measurement: 4021 °C for a daily maximum, 17,802 mm for a month of rain. It maps such a value to null and
    keeps it as the ``raw`` token, as a ``Sentinel`` does.

    Args:
        low: the lowest value that is a reading, included, in the unit of the source (the unit ``null_sentinels``
            reads the value in, before any conversion).
        high: the highest value that is a reading, included.
        where: restricts the rule to the values this expression selects (a parameter), the range being the one of it.

    The bounds are to be generous, such that no record lies outside them: they find a value that is a defect of the
    source, not an extreme. A NaN or an infinity lies outside every range, and is mapped as any other value. The
    ``raw`` text of a value read from a number is the number as short as it can be written, an integral one without
    ``.0`` (``4021``, ``110.26``); a value read from text keeps the text of its cell.

    """

    def __init__(self, low: float, high: float, *, where: pl.Expr | None = None) -> None:
        """Declare a range, refusing one that holds no value."""
        if not low <= high:
            msg = f"the range {low}..{high} holds no value"
            raise ValueError(msg)
        self.low = low
        self.high = high
        self.where = where


class NoReading:
    """Every value that ``where`` selects is no reading: a sensor that was stuck or dead over a period.

    The rule of a value that is no sentinel and lies inside every range, because the whole series of a station for a
    span of time is a defect of the sensor (a sunshine that follows the length of the day whatever the weather, a
    zero every day of a summer), and no single number gives it away (GH-3031). It maps such a value to null and keeps
    it as the ``raw`` token, as ``OutOfRange`` does. A value that is blank or no number is not touched.

    Args:
        where: the values this expression selects, the station, the parameter and the period of the defect.

    """

    def __init__(self, where: pl.Expr) -> None:
        """Declare the rule."""
        self.where = where


def null_sentinels(
    value: pl.Expr,
    *sentinels: Sentinel | OutOfRange | NoReading,
    text: bool = True,
    non_numeric: bool = False,
) -> tuple[pl.Expr, pl.Expr]:
    """Map the sentinels of a source to null and return the text the source wrote for each, with the value.

    The two expressions are made from the same ``value`` and belong together: the first is the cleaned value,
    the second the ``raw`` text for ``join_quality_flags(..., raw=...)`` (null where nothing was mapped), so a
    reader cannot map a sentinel without keeping what it was. Use them in one ``select`` or ``with_columns``.

    A sentinel matches by number (``"-999"`` matches ``-999``, ``-999.0`` and ``" -999.00"``), after the text is
    stripped, and ``"NaN"`` matches a NaN.

    Args:
        value: the expression of the reading. With ``text=True`` the text the source wrote, a String column,
            which is what a reader that sets ``infer_schema_length=0`` has; with ``text=False`` a number.
        *sentinels: the sentinels, ranges and periods (``Sentinel``, ``OutOfRange``, ``NoReading``), the first that
            matches decides.
        text: whether ``value`` is the text of the source. Then the ``raw`` text is the stripped cell as it was
            written (``-999.0`` stays ``-999.0``); from a number it is the text the matching sentinel was
            declared with, or for an ``OutOfRange`` the number as ``OutOfRange`` writes it.
        non_numeric: also map every non-blank text that is no number (``mq``, ``---``, ``Ip``, ``nan``, ``inf``) to
            null, with the text as its ``raw`` token (a comma in it is written as a semicolon, as the tokens are
            separated by commas). Needs ``text=True``.

    Returns:
        ``(cleaned, raw)``. With ``text=True`` the cleaned value is the stripped text, String, unless
        ``non_numeric`` or a sentinel's ``to`` is set, which make it Float64; with ``text=False`` it is the
        number as it was, an integer staying one unless a sentinel's ``to`` is set, which makes it Float64.

    """
    if non_numeric and not text:
        msg = "`non_numeric` reads the text of the source, so it needs `text=True`"
        raise ValueError(msg)
    cell = value.str.strip_chars() if text else value
    number = cell.cast(pl.Float64, strict=False)
    reads_number = text and (
        non_numeric or any(isinstance(sentinel, Sentinel) and sentinel.to is not None for sentinel in sentinels)
    )
    # a number keeps its dtype (an integer column stays one), a text its String unless it is read as a number
    base = number if reads_number else (cell if text else value)
    null = pl.lit(None, dtype=pl.Float64 if reads_number else (pl.String if text else None))

    branches: list[tuple[pl.Expr, pl.Expr, pl.Expr]] = []
    for sentinel in sentinels:
        if isinstance(sentinel, NoReading):
            # a blank cell or a text that is no number is nothing to take back
            chosen = sentinel.where & number.is_not_null()
            branches.append((chosen.fill_null(value=False), null, cell if text else _written(number)))
            continue
        if isinstance(sentinel, OutOfRange):
            outside = (number < sentinel.low) | (number > sentinel.high)
            if sentinel.where is not None:
                outside = outside & sentinel.where
            # a number is written as short as it goes, `4021.0` as `4021`; a text as it was written
            written = cell if text else _written(number)
            branches.append((outside.fill_null(value=False), null, written))
            continue
        mapped = null if sentinel.to is None else pl.lit(sentinel.to, dtype=pl.Float64)
        for sentinel_text in sentinel.texts:
            hit = _is(cell, number, sentinel_text, text=text)
            if sentinel.where is not None:
                hit = hit & sentinel.where
            branches.append((hit.fill_null(value=False), mapped, cell if text else pl.lit(sentinel_text)))
    if non_numeric:
        # a free text may hold the separator of the tokens
        # (a NaN or an infinity is no reading either; `cast` takes `nan` and `inf` for numbers)
        no_number = number.is_null() | number.is_nan() | number.is_infinite()
        branches.append(((cell.str.len_chars() > 0) & no_number, null, cell.str.replace_all(",", ";")))
    return _first_hit(branches, 1, base), _first_hit(branches, 2, pl.lit(None, dtype=pl.String))


def _written(number: pl.Expr) -> pl.Expr:
    """Write a number as the shortest text that reads back as it, an integral one without its ``.0``."""
    return number.cast(pl.String).str.replace(r"\.0$", "")


def _is(cell: pl.Expr, number: pl.Expr, sentinel: str, *, text: bool) -> pl.Expr:
    """Tell whether a reading is the sentinel: by its number, a NaN by being one, a text that is none by its text."""
    try:
        wanted = float(sentinel)
    except ValueError:
        if not text:
            msg = f"{sentinel!r} is no number, so it can only be the sentinel of a column of text"
            raise ValueError(msg) from None
        return cell.eq(sentinel)
    return number.is_nan() if wanted != wanted else number.eq(wanted)  # noqa: PLR0124


def _first_hit(branches: list[tuple[pl.Expr, pl.Expr, pl.Expr]], index: int, otherwise: pl.Expr) -> pl.Expr:
    """Give the third item of the first branch whose condition holds, ``otherwise`` if none does."""
    expr = None
    for branch in branches:
        expr = (pl.when(branch[0]) if expr is None else expr.when(branch[0])).then(branch[index])
    return otherwise if expr is None else expr.otherwise(otherwise)


def raw_column(column: str) -> str:
    """Name the column that carries the ``raw`` text beside a value column of a wide frame."""
    return f"{column}{RAW_SUFFIX}"


def clear_sentinels(
    df: Frame,
    columns: Iterable[str],
    *sentinels: Sentinel | OutOfRange | NoReading,
    non_numeric: bool = False,
) -> Frame:
    """Map the sentinels and out-of-range values of the given columns of a wide frame, keeping their ``raw`` text.

    A String column is read as the text of the source and any other as a number (``null_sentinels`` with
    ``text`` set so). The text goes into ``<column>__raw`` (``raw_column``), which a later call for the same
    column keeps and only fills where it is still null, so a column cleaned by several rules records the first
    that matched. ``unpivot_with_raw`` carries it into the long frame, where ``join_quality_flags(...,
    raw=...)`` writes it. A column the frame does not have is skipped.
    """
    schema = df.collect_schema()
    expressions = []
    for column in columns:
        if column not in schema:
            continue
        cleaned, raw = null_sentinels(
            pl.col(column), *sentinels, text=schema[column] == pl.String, non_numeric=non_numeric
        )
        if raw_column(column) in schema:
            raw = pl.coalesce(pl.col(raw_column(column)), raw)
        expressions += [cleaned.alias(column), raw.alias(raw_column(column))]
    # polars types `with_columns` on the union `DataFrame | LazyFrame`, not on the constrained `Frame` TypeVar,
    # so the checker cannot see that a DataFrame in gives a DataFrame out and a LazyFrame a LazyFrame
    return df.with_columns(expressions)  # ty: ignore[invalid-return-type]


def unpivot_with_raw(
    df: pl.DataFrame,
    *,
    index: list[str],
    on: list[str] | None = None,
    variable_name: str = "parameter",
    value_name: str = "value",
) -> pl.DataFrame:
    """Unpivot a wide frame to long, the ``raw`` text of each column going with its value as column ``raw``.

    The value columns are ``on``, or every column that is not in ``index`` and not a ``raw_column``; they are
    unpivoted as ``DataFrame.unpivot`` does. A column without a ``raw_column`` has a null ``raw``.
    """
    names = df.columns
    raw_columns = {name for name in names if name.endswith(RAW_SUFFIX)}
    on = on if on is not None else [name for name in names if name not in index and name not in raw_columns]
    long = df.unpivot(on=on, index=index, variable_name=variable_name, value_name=value_name)
    # the text goes through the same unpivot, so its rows are the rows of the values, one for one, and it is
    # laid beside them without a join. The value columns may differ in dtype (a column of nulls beside one of
    # numbers), which a struct of value and text could not hold
    raw = df.select(
        *index,
        *(
            (pl.col(raw_column(column)) if raw_column(column) in raw_columns else pl.lit(None, dtype=pl.String))
            .cast(pl.String)
            .alias(column)
            for column in on
        ),
    ).unpivot(on=on, index=index, variable_name=variable_name, value_name=RAW)
    return long.with_columns(raw.get_column(RAW))
