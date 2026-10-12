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
"""

from __future__ import annotations

import polars as pl

QUALITY_FLAGS = "quality_flags"


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
