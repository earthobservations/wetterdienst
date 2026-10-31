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

A wind direction of 0 is a calm, and null with ``raw:0``, only beside a speed of 0 of the same reading: ``calm`` is that
rule for every provider, and ``with_speed_beside`` lays the speed beside the direction of a long frame (GH-3222).

A stuck or dead sensor over a period of time gives values inside every range. ``NoReading`` maps what a
station, a parameter and a period select to null the same way, keeping the value as ``raw`` (GH-3031).

A station pressure that the barometric formula does not expect at the station's elevation (a typo still inside every
world-wide bound: 909 hPa at a station at sea level) is mapped by ``OutOfRange`` too, with the range
``station_pressure_range`` gives (GH-3627).

A model that writes a little below the floor of its quantity (an amount of precipitation of -0.02 mm) rounds to
nothing: ``Floor`` maps what is below the floor to the floor and keeps the number as ``raw``, as a trace is (GH-3263).

``OutOfRange``, ``NoReading`` and ``Floor`` are judgements, and each belongs to one plausibility check (``range``,
``elevation``, ``stuck``, ``consistency``, ``floor``: ``model/plausibility.py``) whose mode the request chooses
(GH-3676). A ``hard`` check does what is described above and writes ``rejected:<check>`` before ``raw:``; a ``soft``
one keeps the value and writes ``suspect:<check>``, with no ``raw:``. A ``Sentinel`` is the source's own code and has no
mode. The readers do not pass the mode: ``null_sentinels`` takes it from the plausibility in effect, and the
``raw`` text it returns carries the verdict to ``join_quality_flags``, which writes the tokens.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

import polars as pl

from wetterdienst.model.plausibility import CHECKS, REJECTED, SUSPECT, Plausibility, active

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

# the `raw` text a reader carries beside a value is the text of a sentinel, or, where a plausibility check judged the
# value, the tokens of the verdict behind a start mark: `rejected:range+stuck,raw:4021` for a value that was rejected,
# `suspect:range` for one that was kept. `join_quality_flags` writes them as they are, without the mark, and the text of
# a sentinel as `raw:<text>`. The mark is a control character no source writes.
_MARK = "\x1e"
# what `_merge_raw` reads the tokens with: the kind, the checks, and the text of a rejected value
_KIND = rf"^{_MARK}([a-z]+):"
_CHECKS = rf"^{_MARK}[a-z]+:([a-z+]+)"
_TEXT = r"(?s),raw:(.*)$"
# the order the names of several checks are written in, which is the order of a merge as well
_WRITE_ORDER = tuple(sorted(CHECKS))


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
    for kind, expr in kinds.items():
        if kind == RAW:
            # the verdict of a plausibility check comes before the text, which stays the last token
            tokens.append(_raw_tail(expr))
            continue
        code = _as_code(expr)
        tokens.append(pl.when(code.is_not_null()).then(pl.lit(f"{kind}:") + code))
    if not tokens:
        msg = "at least one flag is needed"
        raise ValueError(msg)
    # one occurrence of the tokens, which hold the `raw` expression of a reader: a `when` would repeat them
    return pl.concat_str(tokens, separator=",", ignore_nulls=True).replace("", None).alias(QUALITY_FLAGS)


def _raw_tail(raw: pl.Expr) -> pl.Expr:
    """Write the ``raw`` text of a reading as the tokens it stands for: the verdict of a check, then ``raw:<text>``.

    The text is a sentinel's as the source wrote it (``raw:-999``), or the tokens of a verdict behind the mark (see
    ``_MARK``): ``suspect:range`` with no text, ``rejected:range,raw:4021`` with the number. Null where the reading was
    not mapped.
    """
    raw = raw.cast(pl.String)
    return _as_code(pl.when(raw.str.starts_with(_MARK)).then(raw.str.slice(1)).otherwise(pl.lit("raw:") + raw))


def _as_code(expr: pl.Expr) -> pl.Expr:
    """Read a flag as the text of its code: stripped, and null where it is blank."""
    return expr.cast(pl.String).str.strip_chars().replace("", None)


def _checked(check: str) -> str:
    """Refuse a name that is no plausibility check."""
    if check not in CHECKS:
        msg = f"{check!r} is no plausibility check: {', '.join(CHECKS)}"
        raise ValueError(msg)
    return check


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
        check: the plausibility check the rule belongs to, which decides what happens to a value outside: ``range`` for
            a bound of the parameter, ``elevation`` for a station pressure the elevation does not allow.

    The bounds are to be generous, such that no record lies outside them: they find a value that is a defect of the
    source, not an extreme. A NaN or an infinity lies outside every range, and is mapped as any other value. The
    ``raw`` text of a value read from a number is the number as short as it can be written, an integral one without
    ``.0`` (``4021``, ``110.26``); a value read from text keeps the text of its cell.

    """

    def __init__(self, low: float, high: float, *, where: pl.Expr | None = None, check: str = "range") -> None:
        """Declare a range, refusing one that holds no value."""
        if not low <= high:
            msg = f"the range {low}..{high} holds no value"
            raise ValueError(msg)
        self.low = low
        self.high = high
        self.where = where
        self.check = _checked(check)


class NoReading:
    """Every value that ``where`` selects is no reading: a sensor that was stuck or dead over a period.

    The rule of a value that is no sentinel and lies inside every range, because the whole series of a station for a
    span of time is a defect of the sensor (a sunshine that follows the length of the day whatever the weather, a
    zero every day of a summer), and no single number gives it away (GH-3031). It maps such a value to null and keeps
    it as the ``raw`` token, as ``OutOfRange`` does. A value that is blank or no number is not touched. It is also the
    rule of a reading that is no reading because the one beside it, of the same sensor, was nulled as impossible: the
    relative humidity of the hour whose dew point a station without frost cannot have (GH-3629).

    Args:
        where: the values this expression selects, the station, the parameter and the period of the defect.
        check: the plausibility check the rule belongs to: ``stuck`` for a sensor that held still or was dead over a
            period, which is what the rule is for; ``consistency`` for a reading that the one beside it, of another
            parameter of the same file, contradicts; ``range`` for a bound on the value alone.

    """

    def __init__(self, where: pl.Expr, *, check: str = "stuck") -> None:
        """Declare the rule."""
        self.where = where
        self.check = _checked(check)


class Floor:
    """A value below the floor of its quantity, which a model writes as the noise around nothing: it is the floor.

    The rule of an amount that cannot be negative and of which a model's output is a little: DWD's ICON writes
    -0.02 mm for the precipitation of an hour (GH-3263). It maps such a value to ``floor``, as the trace of FMI or KNMI
    is 0.0, and keeps the number as the ``raw`` token: from a number as short as it goes (``-0.10`` as ``-0.1``),
    from a text the cell as written. A NaN or a null is not touched, and neither is a value of -0.0, which is not
    below the floor. Of a column of text, a floor makes numbers: a text that is no number becomes null, with no token
    unless ``non_numeric`` is set. Declare a code of the source (``-999``) as a ``Sentinel`` before it: the first rule
    that matches decides.

    Args:
        floor: the lowest value the quantity has, included, in the unit of the source, and the value a lower one is
            mapped to.
        where: restricts the rule to the values this expression selects (a parameter).

    """

    #: the plausibility check of every floor
    check = "floor"

    def __init__(self, floor: float, *, where: pl.Expr | None = None) -> None:
        """Declare the floor."""
        self.floor = floor
        self.where = where


# the pressure of the standard atmosphere at sea level, in hPa, and what the barometric formula of it (the international
# standard atmosphere, valid in the troposphere) expects at a height: a station pressure that lies further than
# `STATION_PRESSURE_TOLERANCE` from it is no reading (GH-3627)
STANDARD_SEA_LEVEL_PRESSURE = 1013.25
STATION_PRESSURE_TOLERANCE = 75.0
# the elevations the check is made for, in metres: a catalogue that gives another (a missing-value code, a typo) tells
# nothing, and the formula is the standard atmosphere's to 11 km
_STATION_ELEVATIONS = (-500.0, 9000.0)


def standard_station_pressure(elevation: float) -> float:
    """Give the pressure in hPa that the barometric formula of the standard atmosphere expects at an elevation in m."""
    return STANDARD_SEA_LEVEL_PRESSURE * (1.0 - 2.25577e-5 * elevation) ** 5.25588


def station_pressure_range(
    elevation: float | None, *, per_hectopascal: float = 1.0, where: pl.Expr | None = None
) -> OutOfRange | None:
    """Give the rule of a station pressure: the barometric formula at the station's elevation, 75 hPa either way.

    The world-wide bounds of a pressure at the station (500 to 1090 hPa) are too wide to find a reading mistyped by a
    digit at a station near sea level (a P0 of 909.5 hPa at 48 m) or one that is a pressure of another height (968.6
    hPa at the Zugspitze, 2,956 m, where 705 hPa are expected): 75 hPa are about 650 m of height, which the weather at
    the station stays within: the deep lows of Dumont d'Urville (938 hPa at 43 m, where 1008 are expected) are inside.
    A reading outside is null and keeps the number as ``raw`` (``OutOfRange``), under the check ``elevation``.

    Args:
        elevation: the elevation of the station in m, as its catalogue gives it.
        per_hectopascal: how many units of the source make a hPa (100 for Pa); the range is in the unit of the source.
        where: restricts the rule to the parameter(s) this expression selects.

    Returns:
        The rule, or ``None`` where the station has no elevation or one outside -500 to 9000 m.

    """
    if elevation is None or not _STATION_ELEVATIONS[0] <= elevation <= _STATION_ELEVATIONS[1]:
        return None
    expected = standard_station_pressure(elevation)
    return OutOfRange(
        (expected - STATION_PRESSURE_TOLERANCE) * per_hectopascal,
        (expected + STATION_PRESSURE_TOLERANCE) * per_hectopascal,
        where=where,
        check="elevation",
    )


# the text of the direction of a calm wind, as every source that writes one writes it
CALM = "0"
# the column a long frame carries the speed of a wind direction's own reading in, beside the direction
# (`with_speed_beside`), until the reader drops it
SPEED_BESIDE = "__speed_beside"


def calm(speed: pl.Expr, *, where: pl.Expr | None = None) -> Sentinel:
    """Give the rule of a calm: a wind direction of 0 beside a speed of exactly 0 of the same reading (GH-3222).

    A calm has no direction, so its 0 is null and keeps ``raw:0``. A 0 beside a speed above 0 stays, as most sources
    write north as 360 and some as 0 too, and so does a 0 beside a speed the source does not give, which tells nothing.
    The rule is the same for every provider and every direction, of the mean wind as of the gust (beside the gust's
    speed); a code the source documents as no direction (990, 999, a variable wind) is ``no_direction_code``.

    Args:
        speed: the speed of the same reading, as a number or the text of one, in any unit.
        where: restricts the rule to the direction(s) this expression selects.

    """
    beside = speed.cast(pl.Float64, strict=False).eq(0).fill_null(value=False)
    return Sentinel(CALM, where=beside if where is None else where & beside)


def no_direction_code(*texts: str, where: pl.Expr | None = None) -> Sentinel:
    """Give the rule of a no-direction code: a wind direction the source writes as no bearing (GH-3222).

    A direction that is a code of the source (990 or 999 for a variable wind, DWD's "uml.,windstill DD=00", IPMA's
    point 0, "no direction"), or a value that is neither a calm nor north on the source's own scale, is null and keeps
    its text, whatever the speed beside it. It is the one rule beside ``calm`` that maps a 0 away, and only where the
    source names the 0 so or its data rules out a bearing: a 0 that may be north is the business of ``calm``.

    Args:
        *texts: the codes as the source writes them.
        where: restricts the rule to the direction(s) this expression selects.

    """
    return Sentinel(*texts, where=where)


def with_speed_beside(
    df: Frame,
    pairs: dict[str, str],
    *,
    on: list[str],
    value: pl.Expr | None = None,
    into: str = SPEED_BESIDE,
) -> Frame:
    """Lay the speed of the same reading beside every wind direction of a long frame, as column ``SPEED_BESIDE``.

    Any parameter can be laid beside another the same way, under the column name ``into`` (``SPEED_BESIDE`` by
    default): DWD's road weather lays the air temperature beside the road surface temperature (GH-3624).

    Args:
        df: the long frame, with a ``parameter`` column and the value.
        pairs: the direction and the speed of its reading, as the frame names them (``{"dd": "ff"}``).
        on: the columns that make one reading besides ``parameter`` (the timestamp).
        value: the expression of the value, ``pl.col("value")`` by default.
        into: the name of the column that carries the value beside, ``SPEED_BESIDE`` by default.

    Returns:
        The frame with the column ``into`` (``SPEED_BESIDE`` by default), null on every row that is no direction and
        where the speed is missing, for ``calm(pl.col(SPEED_BESIDE))``. The rows and their order are those of ``df``.

    """
    value = pl.col("value") if value is None else value
    if not pairs:
        # polars types `with_columns` on the union `DataFrame | LazyFrame`, not on the constrained `Frame` TypeVar
        return df.with_columns(pl.lit(None, dtype=pl.Float64).alias(into))  # ty: ignore[invalid-return-type]
    parts = [
        df.filter(pl.col("parameter") == speed).select(
            *on, pl.lit(direction, dtype=pl.String).alias("parameter"), value.alias(into)
        )
        for direction, speed in pairs.items()
    ]
    # the parts are all DataFrames or all LazyFrames, which `concat` takes, but the checker sees a list of `Frame`
    speeds = pl.concat(parts).unique(subset=[*on, "parameter"], keep="first", maintain_order=True)  # ty: ignore[invalid-argument-type]
    # polars types `join` on the union `DataFrame | LazyFrame`, not on the constrained `Frame` TypeVar
    return df.join(speeds, on=[*on, "parameter"], how="left", maintain_order="left")  # ty: ignore[invalid-return-type]


def null_sentinels(  # noqa: C901
    value: pl.Expr,
    *sentinels: Sentinel | OutOfRange | NoReading | Floor,
    text: bool = True,
    non_numeric: bool = False,
    plausibility: Plausibility | None = None,
) -> tuple[pl.Expr, pl.Expr]:
    """Map the sentinels of a source to null and return the text the source wrote for each, with the value.

    The two expressions are made from the same ``value`` and belong together: the first is the cleaned value,
    the second the ``raw`` text for ``join_quality_flags(..., raw=...)`` (null where nothing was mapped), so a
    reader cannot map a sentinel without keeping what it was. Use them in one ``select`` or ``with_columns``.

    A sentinel matches by number (``"-999"`` matches ``-999``, ``-999.0`` and ``" -999.00"``), after the text is
    stripped, and ``"NaN"`` matches a NaN.

    A ``Sentinel`` is the source's own code and always maps its value. An ``OutOfRange``, a ``NoReading`` and a
    ``Floor`` are judgements, whose mode the plausibility check each belongs to has in ``plausibility`` (GH-3676): a
    ``hard`` one maps the value (to null, a ``Floor`` to its floor) and the ``raw`` text carries ``rejected:<check>``
    with the number; a ``soft`` one leaves the value as it is and the ``raw`` text carries ``suspect:<check>``. A
    sentinel decides before any judgement; a value that several checks reject is rejected by all of them, and one that
    several checks only find suspect is suspect for all of them, their names joined with ``+``. A rejected value
    carries the verdict of the hard checks alone. A NaN or an infinity outside a range is no judgement: it is mapped as
    a code is, null with its text.

    Args:
        value: the expression of the reading. With ``text=True`` the text the source wrote, a String column,
            which is what a reader that sets ``infer_schema_length=0`` has; with ``text=False`` a number.
        *sentinels: the sentinels, ranges and periods (``Sentinel``, ``OutOfRange``, ``NoReading``,
            ``Floor``), the first sentinel that matches decides, then the first hard rule.
        text: whether ``value`` is the text of the source. Then the ``raw`` text is the stripped cell as it was
            written (``-999.0`` stays ``-999.0``); from a number it is the text the matching sentinel was
            declared with, or for an ``OutOfRange`` or a ``Floor`` the number as short as it goes.
        non_numeric: also map every non-blank text that is no number (``mq``, ``---``, ``Ip``, ``nan``, ``inf``) to
            null, with the text as its ``raw`` token (a comma in it is written as a semicolon, as the tokens are
            separated by commas). Needs ``text=True``.
        plausibility: the mode of every check; the plausibility in effect (``model.plausibility.active``) by default,
            which is the request's while a ``TimeseriesValues`` runs the reader.

    Returns:
        ``(cleaned, raw)``. With ``text=True`` the cleaned value is the stripped text, String, unless
        ``non_numeric``, a sentinel's ``to`` or a ``Floor`` is set, which make it Float64; with ``text=False`` it is the
        number as it was, an integer staying one unless a sentinel's ``to`` is set or a ``Floor`` is given, which make
        it Float64.

    """
    if non_numeric and not text:
        msg = "`non_numeric` reads the text of the source, so it needs `text=True`"
        raise ValueError(msg)
    modes = plausibility if plausibility is not None else active()
    cell = value.str.strip_chars() if text else value
    number = cell.cast(pl.Float64, strict=False)
    reads_number = text and (non_numeric or _maps_to_a_value(sentinels))
    # a number keeps its dtype (an integer column stays one), a text its String unless it is read as a number
    base = number if reads_number else (cell if text else value)
    null = pl.lit(None, dtype=pl.Float64 if reads_number else (pl.String if text else None))
    # a number is written as short as it goes, `4021.0` as `4021`; a text as it was written
    written = cell if text else _written(number)

    # what decides first: the codes of the source, then the numbers that are no number
    coded: list[tuple[pl.Expr, pl.Expr, pl.Expr]] = []
    # then the judgements of a hard check, which null the value (a floor sets it to the floor), and those of a soft one,
    # which only flag it, each by the check they belong to
    rejects: list[pl.Expr] = []
    floors: list[tuple[pl.Expr, pl.Expr, pl.Expr]] = []
    hard_hits: dict[str, list[pl.Expr]] = {}
    soft_hits: dict[str, list[pl.Expr]] = {}
    unreadable: list[pl.Expr] = []
    for sentinel in sentinels:
        if isinstance(sentinel, Sentinel):
            mapped = null if sentinel.to is None else pl.lit(sentinel.to, dtype=pl.Float64)
            for sentinel_text in sentinel.texts:
                hit = _is(cell, number, sentinel_text, text=text)
                if sentinel.where is not None:
                    hit = hit & sentinel.where
                coded.append((hit.fill_null(value=False), mapped, cell if text else pl.lit(sentinel_text)))
            continue
        if isinstance(sentinel, NoReading):
            # a blank cell or a text that is no number is nothing to take back
            chosen = (sentinel.where & number.is_not_null()).fill_null(value=False)
        else:
            outside = _outside(number, sentinel)
            if isinstance(sentinel, OutOfRange):
                # a NaN or an infinity lies outside every range, and is no judgement of the number but a text that is
                # none, mapped as a code is
                outside = outside & number.is_finite()
                bad = ~number.is_finite() & number.is_not_null()
                unreadable.append(bad if sentinel.where is None else bad & sentinel.where)
            if sentinel.where is not None:
                outside = outside & sentinel.where
            chosen = outside.fill_null(value=False)
        if modes.mode(sentinel.check) == "hard":
            if isinstance(sentinel, Floor):
                floors.append((chosen, pl.lit(sentinel.floor, dtype=pl.Float64), written))
            else:
                rejects.append(chosen)
            hard_hits.setdefault(sentinel.check, []).append(chosen)
        else:
            soft_hits.setdefault(sentinel.check, []).append(chosen)
    if unreadable:
        coded.append((pl.any_horizontal(*unreadable).fill_null(value=False), null, written))
    if non_numeric:
        # a free text may hold the separator of the tokens
        # (a NaN or an infinity is no reading either; `cast` takes `nan` and `inf` for numbers)
        no_number = number.is_null() | number.is_nan() | number.is_infinite()
        coded.append(((cell.str.len_chars() > 0) & no_number, null, cell.str.replace_all(",", ";")))
    # the rules that null a value are one branch: they map it alike, and a long list of them (a range for each
    # parameter) would otherwise be as many branches of the plan
    nulled = [(pl.any_horizontal(*rejects), null, written)] if rejects else []
    cleaned = _first_hit([*coded, *nulled, *floors], 1, base)
    raw = _first_hit(coded, 2, _verdict(hard_hits, soft_hits, written))
    return cleaned, raw


def _verdict(hard: dict[str, list[pl.Expr]], soft: dict[str, list[pl.Expr]], written: pl.Expr) -> pl.Expr:
    """Give the ``raw`` text of a value that no code mapped: the tokens of the checks' verdict, null if none hit.

    A value one hard check rejects carries the hard checks that did, and the number; one that only soft checks find
    suspect carries those checks, and no number, the value being kept. Each rule is in the expression once.
    """
    if not hard and not soft:
        return pl.lit(None, dtype=pl.String)
    parts = []
    if hard:
        parts.append(_annotate(REJECTED, _names(hard), pl.lit(",raw:") + written))
    if soft:
        parts.append(_annotate(SUSPECT, _names(soft), pl.lit("")))
    return pl.coalesce(*parts)


def _names(hits: dict[str, list[pl.Expr]]) -> pl.Expr:
    """Write the names of the checks that hit, joined with ``+`` in the order of ``_WRITE_ORDER``; null if none did."""
    names = pl.concat_str(
        [pl.when(pl.any_horizontal(*hits[name])).then(pl.lit(name)) for name in _WRITE_ORDER if name in hits],
        separator="+",
        ignore_nulls=True,
    )
    return names.replace("", None)


def _annotate(kind: str | pl.Expr, names: pl.Expr, suffix: pl.Expr) -> pl.Expr:
    """Write the tokens of a verdict behind the mark; null where there are no names."""
    kind = pl.lit(kind) if isinstance(kind, str) else kind
    return pl.concat_str(pl.lit(_MARK), kind, pl.lit(":"), names, suffix)


def _merge_raw(previous: pl.Expr, new: pl.Expr) -> pl.Expr:
    """Lay the ``raw`` text of a later rule on the one a column already carries.

    The first text stays where there is one, as it always did, with two exceptions that keep the verdicts of the
    checks together (GH-3676). Two soft verdicts become one with both checks (``suspect:range+stuck``). A value that a
    later hard check rejected, or that a later sentinel mapped, carries that and not the suspicion before it, which a
    rejected value does not keep. A rejected value keeps its own text, and a code before a judgement stays.
    """
    previous_annotated = previous.str.starts_with(_MARK)
    new_annotated = new.str.starts_with(_MARK)
    previous_kind, new_kind = previous.str.extract(_KIND, 1), new.str.extract(_KIND, 1)
    previous_checks, new_checks = previous.str.extract(_CHECKS, 1), new.str.extract(_CHECKS, 1)
    previous_rejected, new_rejected = previous_kind.eq(REJECTED), new_kind.eq(REJECTED)
    both = (
        pl.concat_str(previous_checks, new_checks, separator="+")
        .str.split("+")
        .list.unique()
        .list.sort()
        .list.join("+")
    )
    previous_text, new_text = previous.str.extract(_TEXT, 1), new.str.extract(_TEXT, 1)
    text = pl.when(previous_rejected).then(previous_text).otherwise(new_text)
    together = _annotate(
        pl.when(previous_rejected | new_rejected).then(pl.lit(REJECTED)).otherwise(pl.lit(SUSPECT)),
        pl.when(previous_rejected.eq(new_rejected))
        .then(both)
        .when(new_rejected)
        .then(new_checks)
        .otherwise(previous_checks),
        pl.when(text.is_not_null()).then(pl.lit(",raw:") + text).otherwise(pl.lit("")),
    )
    return (
        pl.when(previous.is_null())
        .then(new)
        .when(new.is_null())
        .then(previous)
        .when(previous_annotated & new_annotated)
        .then(together)
        # a code that follows a suspicion is the verdict on the value it nulled
        .when(previous_annotated & previous_kind.eq(SUSPECT))
        .then(new)
        .otherwise(previous)
    )


def _maps_to_a_value(sentinels: tuple[Sentinel | OutOfRange | NoReading | Floor, ...]) -> bool:
    """Tell whether a rule maps to a number (a ``Sentinel`` with ``to``, a ``Floor``), which makes a text column one."""
    return any(isinstance(rule, Floor) or (isinstance(rule, Sentinel) and rule.to is not None) for rule in sentinels)


def _outside(number: pl.Expr, rule: OutOfRange | Floor) -> pl.Expr:
    """Select the numbers a range or a floor takes: those outside the range, those below the floor."""
    if isinstance(rule, Floor):
        return number < rule.floor
    return (number < rule.low) | (number > rule.high)


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
    *sentinels: Sentinel | OutOfRange | NoReading | Floor,
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
            raw = _merge_raw(pl.col(raw_column(column)), raw)
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
