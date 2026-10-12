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
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

import polars as pl

if TYPE_CHECKING:
    from collections.abc import Iterable

QUALITY_FLAGS = "quality_flags"
# the kind of the token that records the sentinel a value was mapped from, always the last one
RAW = "raw"
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


def null_sentinels(
    value: pl.Expr,
    *sentinels: Sentinel,
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
        *sentinels: the sentinels, the first that matches decides.
        text: whether ``value`` is the text of the source. Then the ``raw`` text is the stripped cell as it was
            written (``-999.0`` stays ``-999.0``); from a number it is the text the matching sentinel was
            declared with.
        non_numeric: also map every non-blank text that is no number (``mq``, ``---``, ``Ip``) to null, with the
            text as its ``raw`` token. Needs ``text=True``.

    Returns:
        ``(cleaned, raw)``. With ``text=True`` the cleaned value is the stripped text, String, unless
        ``non_numeric`` or a sentinel's ``to`` is set, which make it Float64; with ``text=False`` it is the
        number as it was, an integer staying one.

    """
    if non_numeric and not text:
        msg = "`non_numeric` reads the text of the source, so it needs `text=True`"
        raise ValueError(msg)
    cell = value.str.strip_chars() if text else value
    number = cell.cast(pl.Float64, strict=False)
    reads_number = text and (non_numeric or any(sentinel.to is not None for sentinel in sentinels))
    # a number keeps its dtype (an integer column stays one), a text its String unless it is read as a number
    base = number if reads_number else (cell if text else value)
    null = pl.lit(None, dtype=pl.Float64 if reads_number else (pl.String if text else None))

    branches: list[tuple[pl.Expr, pl.Expr, pl.Expr]] = []
    for sentinel in sentinels:
        mapped = null if sentinel.to is None else pl.lit(sentinel.to, dtype=pl.Float64)
        for sentinel_text in sentinel.texts:
            hit = _is(cell, number, sentinel_text, text=text)
            if sentinel.where is not None:
                hit = hit & sentinel.where
            branches.append((hit.fill_null(value=False), mapped, cell if text else pl.lit(sentinel_text)))
    if non_numeric:
        branches.append(((cell.str.len_chars() > 0) & number.is_null(), null, cell))
    return _first_hit(branches, 1, base), _first_hit(branches, 2, pl.lit(None, dtype=pl.String))


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
    *sentinels: Sentinel,
    non_numeric: bool = False,
) -> Frame:
    """Map the sentinels of the given columns of a wide frame, keeping the ``raw`` text beside each.

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

    The value columns are ``on``, or every column that is not in ``index`` and not a ``raw_column``. The value
    columns need one dtype, as for ``DataFrame.unpivot``; a column without a ``raw_column`` has a null ``raw``.
    """
    names = df.columns
    raw_columns = {name for name in names if name.endswith(RAW_SUFFIX)}
    on = on if on is not None else [name for name in names if name not in index and name not in raw_columns]
    packed = df.select(
        *index,
        *(
            pl.struct(
                pl.col(column).alias(value_name),
                (pl.col(raw_column(column)) if raw_column(column) in raw_columns else pl.lit(None, dtype=pl.String))
                .cast(pl.String)
                .alias(RAW),
            ).alias(column)
            for column in on
        ),
    )
    long = packed.unpivot(on=on, index=index, variable_name=variable_name, value_name=value_name)
    return long.with_columns(
        pl.col(value_name).struct.field(RAW),
        pl.col(value_name).struct.field(value_name),
    )
