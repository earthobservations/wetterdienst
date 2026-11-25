# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Count, average, add up and take the extremes of a station's values per year, month, day or hour (GH-4412).

A model that is asked how many frost days a year Potsdam has, or which winter was the coldest, cannot read 130 years of
daily values and count them: an answer holds 40,000 characters. `statistics` does it on the server, from what the
reader of the values reads, one station at a time, and says per group how many values were searched and how many were
expected, so that an answer says where it rests on a gap.

Options (the grammar is that of `values`, `model/option_grammar.py`):

- `aggregate`: one to five of `count mean sum min max earliest latest`, joined by `,`
- `by`: the groups besides the series, any of `year month day hour`, each once; none is one group per series
- `filter`: `year month day hour` say which values are looked at, `value` which of them count
- `year_start`: the month a `year` begins (1 to 12); the year is named by the year it ends in (winter 2023/24 is 2024)
- `max_missing`: how many missing values a group may have and still be complete (and get a `mean` and a `sum`)
- `having`: conditions on the results (the aggregates asked for, `searched`, `expected`, `complete`)
- `sort`: the order of the groups (the aggregates, the columns of `by`, `station_id`, `searched`, `expected`)
- `first`: the first N groups of the `sort` order, exactly N: how many more tie is a warning
- `per`: over what `first` counts: `station` (each series) or `none` (all stations of one parameter)
- `max_rows`: the most groups of the whole answer, the last step

The order is fixed: `filter` (the time conditions, then the value conditions), the groups, the aggregates,
completeness, `having`, `sort`, `first`, `max_rows`. A group that is not over yet is incomplete: its `mean` and `sum`
are null unless `max_missing` allows the gap, and its `count`, `min`, `max`, `earliest` and `latest` are of the values
there are, with `complete` false and a warning. Time conditions say which values are looked at, value conditions
which of them count: a group with values and no match has a `count` of 0 and a `sum` of 0, a group with no value at all
has nothing (null). Series are never merged.

`parse_statistics` reads and checks the options before a station is read; `StatisticsRun` is what the walk of
`TimeseriesValues` feeds one station at a time (the frames of a station are let go as its groups are made), and
`StatisticsResult` is what comes out. The rules of completeness are written in `docs/usage/restapi.md` ("Statistics");
this module is the one place that implements them.

The module imports no polars until a frame is reduced, so that the command line can parse a text for `--help` and a
usage error without its cost.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Final

from wetterdienst.exceptions import RequestError
from wetterdienst.model.option_grammar import (
    MAX_FILTER_LENGTH,
    MAX_FIRST,
    MAX_MAX_ROWS,
    Condition,
    RowSelectionError,
    RowSelectionRefusedError,
    SortKey,
    _refusal,
    _Scanner,
    parse_columns,
    parse_conditions,
)
from wetterdienst.model.option_grammar import (
    _read_count as read_count,
)
from wetterdienst.model.row_selection import RESERVED_WORDS, ParameterNames, _name_like
from wetterdienst.model.series_report import latest_complete
from wetterdienst.util.response_warnings import (
    ANSWER_TRUNCATED,  # noqa: F401
    ROWS_CAPPED,
    count_response_warning,
    warn_response,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

    import polars as pl

    from wetterdienst.model.metadata import ParameterModel
    from wetterdienst.model.result import StationsResult

log = logging.getLogger(__name__)

#: what a group can be asked for, in the order an answer writes it
AGGREGATES: Final = ("count", "mean", "sum", "min", "max", "earliest", "latest")
#: the aggregates that name the date of the value they hold, `min_at` and so on
DATED: Final = ("min", "max", "earliest", "latest")
#: the calendar columns a group is made of, from the coarsest to the finest
CALENDAR: Final = ("year", "month", "day", "hour")
#: how fine a calendar column is
_FINENESS: Final = {"year": 0, "month": 1, "day": 2, "hour": 3}
#: the finest calendar column a resolution has; a resolution not listed has all
_FINEST: Final = {"annual": "year", "monthly": "month", "daily": "day"}
#: at most this many aggregates in a request
MAX_AGGREGATES: Final = 5
#: the largest `max_missing`: more than a year of 10-minute readings is no gap to allow
MAX_MISSING: Final = 10_000
#: the most steps of a resolution one series is counted over to say how many values a group should have: a window of
#: more than 170 years of hours is no window of values (an answer of 50,000 groups needs none of them)
MAX_CELLS: Final = 1_500_000
#: the groups a `per=none` choice lets pile up before it drops the candidates that cannot be among the first N
COMPACT_GROUPS: Final = 50_000
#: the words of the options that are kept for a later version, so that no column or aggregate takes their names
RESERVED_BY: Final = ("decade", "season", "week", "quarter", "timezone")
RESERVED_AGGREGATES: Final = ("longest_run", "window", "median", "percentile", "std", "var")

_AGGREGATE_EXAMPLE = "Example: aggregate=count or aggregate=mean,max"
_BY_EXAMPLE = "Example: by=year (a group a year), by=year,month, by=month (every January together)"
_FILTER_EXAMPLE = "Example: filter=value<0 or filter=month=12|1|2,value>=25"
_HAVING_EXAMPLE = "Example: having=count>=100 or having=searched<360"
_SORT_EXAMPLE = "Example: sort=-count (the highest first), sort=mean, sort=year"

#: the groups one `max_rows`-less answer may hold, for a caller of the library (REST and the tools hold their own)
_STEP: Final = {
    "1_minute": 1,
    "5_minutes": 5,
    "6_minutes": 6,
    "10_minutes": 10,
    "15_minutes": 15,
}
_INTERVAL: Final = {"hourly": "1h", "6_hours": "6h", "daily": "1d", "monthly": "1mo", "annual": "1y"}

#: a total over a window of its own (`precipitation_amount_last_3h`): its rows overlap, so a sum counts the same rain
#: several times
_WINDOW_NAME = re.compile(r"(_last_(\d+)h|_multiday|_since_last)")
#: unit types that have no magnitude to take the mean or an extreme of: a direction, a weather code
_NO_STATISTIC_TYPES: Final = frozenset({"angle", "significant_weather"})
#: the hours one reading of a resolution stands for, to tell a window of its own that overlaps its neighbours
_RESOLUTION_HOURS: Final = {
    "1_minute": 1 / 60,
    "5_minutes": 5 / 60,
    "6_minutes": 6 / 60,
    "10_minutes": 10 / 60,
    "15_minutes": 15 / 60,
    "hourly": 1,
    "6_hours": 6,
    "daily": 24,
    "monthly": 24 * 28,
    "annual": 24 * 365,
}
#: what a sum is for: amounts, durations, energies and counts
_SUMMABLE: Final = frozenset({"sum", "count", "occurrence"})

#: the codes of the warnings of an answer of `statistics`
INCOMPLETE_GROUPS = "incomplete-groups"
GAPS_ALLOWED = "gaps-allowed"


def incomplete_groups_message(total: int, shown: int, maximum: int) -> str:
    """Write the warning about groups with fewer values than expected, for `total` of them, `shown` in the answer.

    `{count}` and `{where}` are left for the sum over the series and the stations that have one.
    """
    if total == 1:
        return (
            "{count} group has fewer values than expected{where} ("
            + ("it is in this answer" if shown else "it is not in this answer")
            + f"): its `mean` and `sum` are null (`max_missing` is {maximum}); its `count`, `min`, `max`, "
            "`earliest` and `latest` are of the values there are, `complete` is false, and `searched` and `expected` "
            "beside it say how many."
        )
    return (
        "{count} groups have fewer values than expected{where} "
        f"({shown:,} of them in this answer): their `mean` and `sum` are null (`max_missing` is {maximum}); their "
        "`count`, `min`, `max`, `earliest` and `latest` are of the values there are, `complete` is false, and "
        "`searched` and `expected` beside them say how many."
    )


def _values_text(count: int) -> str:
    """Write a number of values, with the noun in its number: `1 value`, `37 values`."""
    return f"{count:,} value{'' if count == 1 else 's'}"


def gaps_allowed_message(groups: int, most: int, lacking: int, plan: StatisticsPlan) -> str:
    """Write the warning about groups that lack values and are in the answer because `max_missing` allows it.

    `groups` of them, `most` the values the worst lacks, `lacking` what all lack. Never called for none. What the
    caller can do depends on what was asked: a `mean` or a `sum` is of the values there are and is kept by raising
    `max_missing` no further than a gap accepted, while `count`, `min`, `max`, `earliest` and `latest` do not depend on
    `max_missing` at all: only `complete` does, and `having=complete` with `max_missing` 0 ranks the full groups alone.
    """
    verb = "ranked" if plan.sort else "in the answer"
    one = groups == 1
    means = any(name in ("mean", "sum") for name in plan.aggregate)
    if one:
        head = f"1 group lacks {_values_text(most)}"
        owner, says = "its", "beside it"
    else:
        head = f"{groups:,} groups lack up to {_values_text(most)} ({lacking:,} in all)"
        owner, says = "their", "beside them"
    leading = f"{owner} `mean` and `sum` are of the values there are, and " if means else ""
    advice = (
        "Keep `max_missing` at 0 to rank only groups that have every value."
        if means
        else "To rank only groups that have every value, use `having=complete` with `max_missing` 0."
    )
    return (
        f"{head} and {'is' if one else 'are'} {verb} because `max_missing` is {plan.max_missing}: {leading}"
        f"`complete` is true, which says no more than `max_missing` lack (`searched` and `expected` {says} say how "
        f"many). {advice}"
    )


_IN_ANSWER = re.compile(r"\((?:[\d,]+ of them in this answer|it is in this answer|it is not in this answer)\)")


def restate_incomplete(message: str, shown: int) -> str:
    """Say in the warning about incomplete groups how many of them an answer that was cut afterwards still holds."""
    if message.startswith("1 group has"):
        text = "it is in this answer" if shown else "it is not in this answer"
    else:
        text = f"{shown:,} of them in this answer"
    return _IN_ANSWER.sub(f"({text})", message)


NO_VALUES_IN_GROUPS = "no-values-in-groups"
NO_VALUES_IN_GROUPS_MESSAGE = (
    "{count} groups lie before the first or after the last value of their series and are not listed{where}; "
    "`metadata.search.totals.groups` counts them."
)
COMPLETENESS_UNKNOWN = "completeness-unknown"
COMPLETENESS_UNKNOWN_MESSAGE = (
    "How many values a group should have is not known for {count} series{where} (a forecast, a resolution without a "
    "fixed step, or a series whose step is coarser than its resolution): their groups count as complete."
)
TIES_NOT_SHOWN = "ties-not-shown"


class GroupsOverLimitError(RequestError):
    """The groups held so far are more than the reader may hold, and nothing a later station reads can take them back.

    Raised by the walk of `statistics` when its caller set a limit (the REST API does, to the limit of an answer) and
    the groups kept from the stations read are more than that. `groups` is how many were held so far, `maximum` the
    limit.
    """

    def __init__(self, groups: int, maximum: int) -> None:
        """Name the groups held so far and the limit."""
        self.groups = groups
        self.maximum = maximum
        super().__init__(
            f"{groups:,} groups so far, more than the {maximum:,} that may be held. "
            "Drop a column of `by`, or add `having` or `first`."
        )

    def __reduce__(self) -> tuple[type[GroupsOverLimitError], tuple[int, int]]:
        """Rebuild the error from its two numbers, as it is built (an error is pickled across processes)."""
        return type(self), (self.groups, self.maximum)


# ----------------------------------------------------------------------------------------------------------------
# the options
# ----------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class StatisticsPlan:
    """What the options of a request say, read and checked: immutable, holds no frame and knows no series."""

    aggregate: tuple[str, ...]
    by: tuple[str, ...] = ()
    #: the conditions of `filter` in the order they were written
    conditions: tuple[Condition, ...] = ()
    having: tuple[Condition, ...] = ()
    sort: tuple[SortKey, ...] = ()
    first: int | None = None
    per: str = "station"
    year_start: int = 1
    max_missing: int = 0
    max_rows: int | None = None

    @property
    def time_conditions(self) -> tuple[Condition, ...]:
        """The conditions on `year`, `month`, `day` and `hour`: which values are looked at."""
        return tuple(c for c in self.conditions if c.column != "value")

    @property
    def value_conditions(self) -> tuple[Condition, ...]:
        """The conditions on `value`: which of the values looked at count."""
        return tuple(c for c in self.conditions if c.column == "value")

    @property
    def per_station(self) -> bool:
        """Whether `first` counts in each series: it does unless `per=none`."""
        return self.per == "station"

    def bound(self, names: ParameterNames) -> StatisticsPlan:
        """Settle the names of parameters a `filter` was written with, now that the request's parameters are known.

        The name of the one parameter of the request is `value`; any other name is refused with what to write.
        """
        named = [c for c in self.conditions if c.column not in ("value", *CALENDAR)]
        if not named:
            return self
        from wetterdienst.metadata.parameter_table import PARAMETERS  # noqa: PLC0415

        columns = {column for hits in names.lookup.values() for _, column in hits}
        conditions = []
        for condition in self.conditions:
            if condition.column in ("value", *CALENDAR):
                conditions.append(condition)
                continue
            if len(columns) == 1 and condition.column in names.lookup:
                conditions.append(replace(condition, column="value"))
                continue
            if condition.column in names.lookup:
                # a name of the request is no typo: it is only that two parameters cannot both be `value`
                hint = (
                    f"`{condition.column}` is a parameter of this request, but a parameter's name is a column of "
                    "`statistics` only where the request has that one parameter: ask for it alone and write `value`."
                )
            elif condition.column in PARAMETERS:
                # another quantity of the library, not a misspelling: no name is suggested for it
                hint = (
                    f"`{condition.column}` is not a parameter of this request, and a parameter's name is a column of "
                    "`statistics` only where the request has that one parameter: write `value`, with one parameter in "
                    "`parameters`."
                )
            else:
                close = names.close_to(condition.column)
                hint = (f"did you mean {' or '.join(close)}? " if close else "") + (
                    "A parameter's name is no column of `statistics` unless the request has that one parameter: "
                    "write `value`, with one parameter in `parameters`."
                )
            raise _refusal(
                "filter",
                f"`{condition.column}` is no column of this option",
                found=repr(condition.column),
                expected="one of value, year, month, day, hour",
                hint=hint,
            )
        return replace(self, conditions=tuple(conditions))

    def echo(self) -> dict[str, Any]:
        """Give the options as the parser read them, the way a report names them."""
        return {
            "aggregate": list(self.aggregate),
            "filter": ",".join(c.text() for c in self.conditions) or None,
            "by": list(self.by),
            "per": self.per,
            "having": ",".join(c.text() for c in self.having) or None,
            "sort": ",".join(k.text() for k in self.sort) or None,
            "first": self.first,
            "year_start": self.year_start,
            "max_missing": self.max_missing,
            "max_rows": self.max_rows,
        }


def _unknown(
    scanner: _Scanner,
    word: str,
    allowed: Sequence[str],
    start: int,
    example: str,
    hints: Mapping[str, str] | None = None,
) -> RowSelectionError:
    """Build the refusal of a word that is none of the columns of the option, with what to write instead."""
    hint = (hints or {}).get(word.lower())
    text = f"{hint}. {example}" if hint else example
    return scanner.fail(
        (f"`{word}` is not {'an aggregate' if scanner.option == 'aggregate' else 'a column'} of this option")
        if word
        else "no column",
        expected=f"one of {', '.join(allowed)}",
        hint=text,
        at=start,
        found=repr(word[:40]) if word else None,
    )


def _resolver(
    allowed: Sequence[str], example: str, hints: Mapping[str, str] | None = None
) -> Callable[[_Scanner, str, int], str]:
    """Give the function that refuses a word that is none of `allowed`, for the grammar to call."""

    def resolve(scanner: _Scanner, word: str, start: int) -> str:
        raise _unknown(scanner, word, allowed, start, example, hints)

    return resolve


_TRUTH: Final = {"true": "1", "yes": "1", "false": "0", "no": "0"}


def _bare_complete(text: str) -> str:
    """Read `complete` as a condition of `having`: alone it is `complete=1`; `true`, `yes`, `false`, `no` are 1, 0.

    A word that is neither a number nor one of them is refused here, saying what the flag takes: it is no quantity, so
    the grammar's "write the number alone, in the unit of the values" would send the caller the wrong way. A text over
    the length the grammar allows is left to it to refuse, and nothing here scans it: plain string operations only.
    """
    if len(text) > MAX_FILTER_LENGTH:
        return text
    parts = []
    offset = 0
    for part in text.split(","):
        parts.append(_complete_condition(part, offset))
        offset += len(part) + 1
    return ",".join(parts)


def _complete_condition(part: str, offset: int) -> str:
    """Read one comma-separated part of `having` as the condition on `complete` it may be, else leave it as it is."""
    stripped = part.strip()
    if stripped.lower() == "complete":
        return "complete=1"
    name, equals, rest = part.partition("=")
    operator = "!=" if name.rstrip().endswith("!") else "="
    if not equals or name.strip().lower().removesuffix("!").strip() != "complete" or not rest.strip():
        return part
    values = []
    inside = 0
    start = len(name) + 1 + (len(rest) - len(rest.lstrip()))
    for value in rest.strip().split("|"):
        token = value.strip().lower()
        if token not in _TRUTH and not _is_number(token):
            raise RowSelectionError(
                "having",
                "`complete` is a flag, not a quantity",
                position=offset + start + inside + len(value) - len(value.lstrip()) + 1,
                found=repr(value.strip()),
                expected="1, 0, true, yes, false or no",
                hint="`complete` alone keeps the complete groups: having=complete, or having=complete=false",
            )
        values.append(_TRUTH.get(token, value))
        inside += len(value) + 1
    return f"complete{operator}{'|'.join(values)}"


def _is_number(token: str) -> bool:
    """Say whether a token is a number the grammar reads: digits, a point, a sign, an exponent (a long one is none)."""
    if not token or len(token) > 40 or not set(token) <= set("0123456789.-+eE"):
        return False
    try:
        float(token)
    except ValueError:
        return False
    return not token.startswith(("+", "."))


def _filter_resolver() -> Callable[[_Scanner, str, int], str]:
    """Give what reads a word of `filter` that is no column: the name of a parameter, held until the request is known.

    A name is accepted as written (in lower case) where it can be one, as `values` accepts it, and
    `StatisticsPlan.bound` turns it into `value` where the request has that one parameter only, and refuses it where
    it has not.
    """
    columns = ("value", *CALENDAR)

    def resolve(scanner: _Scanner, word: str, start: int) -> str:
        lower = word.lower()
        if lower in RESERVED_WORDS or not _name_like(word):
            raise _unknown(scanner, word, columns, start, _FILTER_EXAMPLE, _filter_hints())
        return lower

    return resolve


def _later(words: Iterable[str], what: str) -> dict[str, str]:
    """Say of words that are kept for a later version that they are not available yet."""
    return {word: f"`{word}` is {what} that is not available in this version" for word in words}


def parse_statistics(  # noqa: C901
    aggregate: str | Sequence[str] | None,
    *,
    by: str | Sequence[str] | None = None,
    filter: str | None = None,  # noqa: A002
    year_start: int | str | None = None,
    max_missing: int | str | None = None,
    having: str | None = None,
    sort: str | None = None,
    first: int | str | None = None,
    per: str | None = None,
    max_rows: int | str | None = None,
) -> StatisticsPlan:
    """Read the options of a request for statistics into a `StatisticsPlan`, or raise `RowSelectionError`.

    The texts are checked in full, and the options against each other (`first` needs `sort`, `year_start` needs a
    `year` in `by`, `per` needs `first`), before any station is read: the series
    of the request are checked against the aggregates asked as the first one is read (`refuse_for`).

    Raises:
        RowSelectionError: a text that cannot be read, or a combination that has no meaning.

    """
    names = _read_names("aggregate", aggregate)
    if not names:
        raise _refusal(
            "aggregate", "no aggregate is given", hint=f"{_AGGREGATE_EXAMPLE}. One to five of {_or(AGGREGATES)}"
        )
    aggregates = tuple(
        key.column
        for key in parse_columns(
            "aggregate",
            ",".join(names),
            AGGREGATES,
            _AGGREGATE_EXAMPLE,
            _resolver(AGGREGATES, _AGGREGATE_EXAMPLE, _aggregate_hints()),
            signed=False,
        )
    )
    if len(aggregates) > MAX_AGGREGATES:
        raise _refusal(
            "aggregate",
            f"{len(aggregates)} aggregates, more than the {MAX_AGGREGATES} allowed",
            hint="ask for the others in a second request",
        )
    by_names = _read_names("by", by)
    columns = (
        tuple(
            key.column
            for key in parse_columns(
                "by",
                ",".join(by_names),
                CALENDAR,
                _BY_EXAMPLE,
                _resolver(CALENDAR, _BY_EXAMPLE, _by_hints()),
                signed=False,
            )
        )
        if by_names
        else ()
    )
    # the order of a series' columns is the calendar's, whatever order they were written in
    columns = tuple(column for column in CALENDAR if column in columns)

    conditions: tuple[Condition, ...] = ()
    if filter not in (None, ""):
        conditions = parse_conditions(
            "filter",
            str(filter),
            ("value", *CALENDAR),
            _FILTER_EXAMPLE,
            _filter_resolver(),
        )

    having_columns = (*aggregates, "searched", "expected", "complete")
    having_conditions: tuple[Condition, ...] = ()
    if having not in (None, ""):
        having_conditions = parse_conditions(
            "having",
            _bare_complete(str(having)),
            having_columns,
            _HAVING_EXAMPLE,
            _resolver(having_columns, _HAVING_EXAMPLE, _having_hints(aggregates)),
        )
    sort_columns = (*aggregates, *CALENDAR, "station_id", "searched", "expected", "complete")
    keys: tuple[SortKey, ...] = ()
    if sort not in (None, ""):
        keys = parse_columns(
            "sort",
            str(sort),
            sort_columns,
            _SORT_EXAMPLE,
            _resolver(sort_columns, _SORT_EXAMPLE, _sort_hints(aggregates)),
            signed=True,
        )
        for key in keys:
            if key.column in CALENDAR and key.column not in columns:
                raise _refusal(
                    "sort",
                    f"`{key.column}` is not a group of this request",
                    hint=f"add it to `by`, or sort by {_or(columns or aggregates)}",
                )

    count = read_count("first", first, MAX_FIRST, _FIRST_LARGE, _FIRST_SMALL) if first not in (None, "") else None
    cap = (
        read_count("max_rows", max_rows, MAX_MAX_ROWS, _MAX_ROWS_LARGE, _MAX_ROWS_SMALL)
        if max_rows not in (None, "")
        else None
    )
    if count is not None and not keys:
        raise _refusal(
            "first",
            "`first` takes the first groups of the `sort` order, and no `sort` is given",
            hint=f"add sort=-{aggregates[0]} (the highest first) or sort={aggregates[0]} (the lowest). "
            f"Example: sort=-{aggregates[0]}&first=3",
        )
    per_name = (per or "station").strip().lower()
    if per_name not in ("station", "none"):
        raise _refusal("per", f"`{per}` is not allowed", expected="station or none", hint="Example: per=none")
    if per_name != "station" and count is None:
        raise _refusal(
            "per",
            "`per` says over what `first` counts, and no `first` is given",
            hint=f"add first=N and sort=-{aggregates[0]}, or leave `per` out",
        )
    start = _read_whole("year_start", year_start, 1, 12, default=1)
    if start != 1 and "year" not in columns:
        raise _refusal(
            "year_start",
            "`year_start` says where the `year` of a group begins, and `by` has no `year`",
            hint="add by=year",
        )
    missing = _read_whole("max_missing", max_missing, 0, MAX_MISSING, default=0)
    return StatisticsPlan(
        aggregate=aggregates,
        by=columns,
        conditions=conditions,
        having=having_conditions,
        sort=keys,
        first=count,
        per=per_name,
        year_start=start,
        max_missing=missing,
        max_rows=cap,
    )


_FIRST_LARGE = "ask for fewer groups, or narrow the request with `having` or `filter`"
_FIRST_SMALL = "`first` is at least 1"
_MAX_ROWS_LARGE = "ask for fewer groups, or narrow the request with `having`, `first` or `filter`"
_MAX_ROWS_SMALL = "`max_rows` is at least 1"


def _or(names: Iterable[str]) -> str:
    """Write names as a list ending in "or"."""
    names = list(names)
    if len(names) < 2:
        return "".join(names)
    return f"{', '.join(names[:-1])} or {names[-1]}"


def _read_names(option: str, value: str | Sequence[str] | None) -> list[str]:
    """Read an option given as a text or as a list of names into the names, an empty text as none given."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not all(isinstance(item, str) for item in value):
        raise _refusal(option, "not a text", found=repr(value)[:40])
    return [item for item in value if item.strip()]


def _read_whole(option: str, value: object, low: int, high: int, *, default: int) -> int:
    """Read a whole number from `low` to `high`; a text of digits is read as the number it writes."""
    if value in (None, ""):
        return default
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise _refusal(option, "not a whole number", found=repr(value)[:40], expected=f"a whole number from {low}")
    if isinstance(value, str):
        text = value.strip(" \t")
        if not text.isascii() or not text.isdigit() or len(text) > 12:
            raise _refusal(
                option,
                "not a whole number",
                found=repr(value)[:40],
                expected=f"a whole number from {low} to {high}",
                hint=f"Example: {option}={high if option == 'max_missing' else 12}",
            )
        value = int(text)
    if not low <= value <= high:
        raise _refusal(
            option,
            f"{value} is outside the range allowed",
            expected=f"a whole number from {low} to {high}",
            hint="the month a year begins: 1 is January, 12 is December" if option == "year_start" else None,
        )
    return value


def _aggregate_hints() -> dict[str, str]:
    """Say what to write for the aggregates a caller tries that are not in this version, or are spelled otherwise."""
    return {
        **_later(RESERVED_AGGREGATES, "an aggregate"),
        "average": "the average is `mean`",
        "avg": "the average is `mean`",
        "total": "the total is `sum`",
        "number": "the number of values is `count`",
        "first": "the first value in time is `earliest`",
        "last": "the last value in time is `latest`",
        "minimum": "the lowest value is `min`",
        "maximum": "the highest value is `max`",
    }


def _by_hints() -> dict[str, str]:
    """Say what a `by` column that is not one means: the station is never a group, a later column is reserved."""
    return {
        **_later(RESERVED_BY, "a group"),
        "station_id": "a series is a station and a parameter and is never merged; `per=none` ranks across stations",
        "station": "a series is a station and a parameter and is never merged; `per=none` ranks across stations",
        "none": "leave `by` out for one group a series",
        "date": "use `year`, `month`, `day` and `hour`",
        "timestamp": "use `year`, `month`, `day` and `hour`",
        "parameter": "a series is a station and a parameter and is never merged",
    }


def _filter_hints() -> dict[str, str]:
    """Say what a `filter` column that is not one means."""
    return {
        "quality": "quality flags are not available in the row options yet",
        "quality_flags": "quality flags are not available in the row options yet",
        "timestamp": "the window is the `timestamp` option of the request; use `year`, `month`, `day` or `hour` here",
        "station_id": "choose stations with `stations`, `name` or the other selections",
        "parameter": "conditions on a parameter's name are not in `statistics`: one condition is on `value`",
        "temperature_air_min_2m": "a parameter's name is no column of `statistics`: use `value`, with one parameter",
    }


def _having_hints(aggregates: Sequence[str]) -> dict[str, str]:
    """Say what a `having` column that is not one means: an aggregate not asked for, a time column."""
    hints = {
        name: f"`{name}` is not among the `aggregate` of this request: add it there first"
        for name in AGGREGATES
        if name not in aggregates
    }
    hints.update(
        {
            name: f"`{name}` is a time condition, which says which values are looked at: put it in `filter`"
            for name in CALENDAR
        }
    )
    hints["value"] = "`value` is a condition on the values looked at: put it in `filter`"
    hints["rank"] = "`rank` is the place of a group under `per=none`, and is no column to choose by"
    return hints


def _sort_hints(aggregates: Sequence[str]) -> dict[str, str]:
    """Say what a `sort` column that is not one means."""
    hints = {
        name: f"`{name}` is not among the `aggregate` of this request: add it there first"
        for name in AGGREGATES
        if name not in aggregates
    }
    hints["value"] = "a group has no `value`: sort by an aggregate, such as -mean or -max"
    return hints


# ----------------------------------------------------------------------------------------------------------------
# what a parameter allows
# ----------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SeriesMeta:
    """What a statistic needs to know of a parameter: the unit it comes back in, its quantity and its statistic."""

    name: str
    unit: str
    unit_type: str
    aggregation: str | None

    @classmethod
    def of(cls, parameter: ParameterModel, unit: str) -> SeriesMeta:
        """Read the quantity and the aggregation of a parameter from its own metadata."""
        return cls(parameter.name, unit, parameter.unit_type, parameter.effective_aggregation)

    @classmethod
    def of_canonical(cls, name: str, unit: str) -> SeriesMeta:
        """Read the quantity and the aggregation of a canonical parameter by its name."""
        from wetterdienst.metadata.parameter_table import PARAMETERS  # noqa: PLC0415

        canonical = PARAMETERS[name]
        return cls(name, unit, canonical.unit_type, canonical.aggregation)


def _refusal_of(aggregate: str, meta: SeriesMeta, resolution: str) -> tuple[str | None, str | None]:
    """Judge an aggregate of a parameter: the reason it is refused (None where allowed) and the unit of the result."""
    if aggregate in ("count", "earliest", "latest"):
        return None, None if aggregate == "count" else meta.unit
    # a direction has no mean, and a zenith angle has: the angles of a direction are named so
    direction = meta.unit_type == "angle" and "direction" in meta.name
    if direction or meta.unit_type == "significant_weather" or meta.aggregation == "code":
        kind = "a direction" if direction else "a code"
        return f"`{meta.name}` is {kind}: it has no {aggregate}; use count, earliest or latest", None
    if aggregate in ("min", "max"):
        return None, meta.unit
    if aggregate == "mean":
        if meta.aggregation == "uncertainty":
            return f"`{meta.name}` is an estimate of an error, no quantity: it has no mean", None
        return None, meta.unit
    # a sum
    if meta.aggregation in _SUMMABLE:
        if _overlaps(meta.name, resolution):
            reason = (
                f"`{meta.name}` is a total over a window of its own: summing its rows counts the same rain "
                "several times"
            )
            return reason, None
        return None, meta.unit
    if meta.unit_type == "temperature" and resolution in ("daily", "hourly"):
        # degree days (the Hellmann number, heating degree days) and degree hours
        return None, _degree_unit(meta.unit, resolution)
    kind = meta.aggregation or "a reading"
    reason = (
        f"a sum of `{meta.name}` ({kind} of {meta.unit_type}) is no quantity: sums are for amounts (precipitation, "
        "sunshine, counts) and, daily or hourly, for temperatures (degree days)"
    )
    return reason, None


def _overlaps(name: str, resolution: str) -> bool:
    """Tell whether the rows of a parameter that is a total over a window of its own overlap at this resolution.

    `_multiday` and `_since_last` windows always do; a `_last_Nh` window does where it is longer than the step of the
    resolution (`precipitation_amount_last_1h` of hourly values is each hour once, of 10-minute values six times).
    """
    found = _WINDOW_NAME.search(name)
    if found is None:
        return False
    if found.group(2) is None:
        return True
    step = _RESOLUTION_HOURS.get(resolution)
    return step is None or int(found.group(2)) > step


def _degree_unit(unit: str, resolution: str) -> str:
    """Write the unit of a sum of temperatures: `°Cd` for daily and `°Ch` for hourly values."""
    suffix = "d" if resolution == "daily" else "h"
    return f"{unit}{suffix}" if unit == "°C" else f"{unit} {suffix}"


def refuse_for(plan: StatisticsPlan, meta: SeriesMeta, resolution: str) -> dict[str, str | None]:
    """Refuse what a series cannot do with the options, and give the unit of each aggregate where it differs.

    A sum of a pressure, a mean of a direction, `by=hour` of daily values, a `month` condition of annual ones: each is
    well written and cannot be applied to this series, so it is a `RowSelectionRefusedError`, the request's to change.
    """
    units: dict[str, str | None] = {}
    for name in plan.aggregate:
        reason, unit = _refusal_of(name, meta, resolution)
        if reason is not None:
            allowed = [other for other in AGGREGATES if _refusal_of(other, meta, resolution)[0] is None]
            raise RowSelectionRefusedError(
                f"Invalid `aggregate`: {reason}; found {name}. Allowed here: {', '.join(allowed)}."
            )
        units[name] = unit
    finest = _FINEST.get(resolution)
    limit = _FINENESS[finest] if finest else _FINENESS["hour"]
    for column in CALENDAR:
        if _FINENESS[column] <= limit:
            continue
        where = (
            "by" if column in plan.by else "filter" if any(c.column == column for c in plan.time_conditions) else None
        )
        if where:
            raise RowSelectionRefusedError(
                f"Invalid `{where}`: `{column}` is finer than the {resolution} values of `{meta.name}`. "
                f"The finest column of {resolution} data is `{finest}`."
            )
    if plan.year_start != 1 and resolution == "annual":
        raise RowSelectionRefusedError(
            f"Invalid `year_start`: the annual values of `{meta.name}` have no seasons; leave `year_start` out."
        )
    return units


# ----------------------------------------------------------------------------------------------------------------
# the calendar
# ----------------------------------------------------------------------------------------------------------------


def _season_year(year: int, month: int, year_start: int) -> int:
    """Give the year a stamp is named by: the year its season ends in (`year_start` is the month a season begins)."""
    return year + (1 if year_start > 1 and month >= year_start else 0)


def _season_bounds(year: int, year_start: int) -> tuple[dt.datetime, dt.datetime]:
    """Give the first and the last instant of the year a season is named by, within the years 1 to 9999."""
    year = min(max(year, 1), 9999)
    if year_start == 1:
        return dt.datetime(year, 1, 1, tzinfo=dt.UTC), dt.datetime(year, 12, 31, 23, 59, 59, 999999, tzinfo=dt.UTC)
    end = dt.datetime(year, year_start, 1, tzinfo=dt.UTC) - dt.timedelta(microseconds=1)
    return dt.datetime(max(year - 1, 1), year_start, 1, tzinfo=dt.UTC), end


def _floor(resolution: str, stamp: dt.datetime) -> dt.datetime:
    """Give the start of the step of a resolution a stamp lies in, as the cells of a group are counted from."""
    if resolution == "annual":
        return stamp.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    if resolution == "monthly":
        return stamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if resolution == "daily":
        return stamp.replace(hour=0, minute=0, second=0, microsecond=0)
    if resolution == "6_hours":
        return stamp.replace(hour=stamp.hour - stamp.hour % 6, minute=0, second=0, microsecond=0)
    return stamp.replace(minute=0, second=0, microsecond=0)


def _anchor(resolution: str, stamp: dt.datetime, *, own_stamp: bool = False) -> dt.datetime:
    """Give where the cells of a period that begins at `stamp` begin.

    A month or a year is counted when the period begins at a value's own stamp on its first day, at whatever time of it
    (`own_stamp`: a monthly value dated 06:00 of the 1st is that month's). A window that begins at 12:00 of the 1st has
    passed that month, as `count_readings` counts it, and so does a period that begins later in it; the steps of the
    finer resolutions begin at the step they lie in.
    """
    if resolution == "monthly":
        return _floor(resolution, stamp) if own_stamp and stamp.day == 1 else _ceil(resolution, stamp)
    if resolution == "annual":
        return (
            _floor(resolution, stamp) if own_stamp and (stamp.month, stamp.day) == (1, 1) else _ceil(resolution, stamp)
        )
    return _floor(resolution, stamp)


def _ceil(resolution: str, stamp: dt.datetime) -> dt.datetime:
    """Give the first anchor of a calendar resolution at or after a stamp: a month it began in is not counted."""
    floor = _floor(resolution, stamp)
    if floor == stamp:
        return floor
    if resolution == "annual":
        return floor.replace(year=floor.year + 1)
    return floor.replace(year=floor.year + floor.month // 12, month=floor.month % 12 + 1)


#: how many hours one cell of a resolution spans, at the least: the steps of a calendar resolution are longer
_CELL_HOURS: Final = {"hourly": 1, "6_hours": 6, "daily": 24, "monthly": 24 * 28, "annual": 24 * 365}


def _cells(resolution: str, low: dt.datetime, high: dt.datetime, *, own_stamp: bool = False) -> pl.DataFrame:
    """Make the cells a period holds, the steps of a resolution, with how many readings each stands for (`_w`).

    A step finer than an hour is counted by the hour, so that a station of one-minute readings costs no more than one of
    hourly ones: a cell is an hour and stands for the steps of it that lie in the period, which is all of `60 //
    minutes` of them but in the first hour and the last, where the period begins and ends. The steps are those of the
    clock (a 10-minute value is dated 00:10, 00:20, so a period from 00:05 begins at 00:10), and the first and the last
    cell are stamped at the first and the last step, so that what lies before the first step and after the last is
    neither expected nor an edge. The cells of a calendar resolution are its anchors.
    """
    import polars as pl  # noqa: PLC0415

    if resolution in _STEP:
        return _sub_hourly_cells(_STEP[resolution], low, high)
    if resolution not in _INTERVAL:
        message = f"`{resolution}` has no fixed step to count the values of a group by"
        raise RowSelectionRefusedError(message)
    start = _anchor(resolution, low, own_stamp=own_stamp)
    empty = pl.DataFrame(schema={"timestamp": pl.Datetime("us", "UTC"), "_w": pl.Int64})
    if high < start:
        return empty
    _refuse_wide_window(resolution, (high - start) / dt.timedelta(hours=1) / _CELL_HOURS[resolution])
    cells = pl.datetime_range(start, high, _INTERVAL[resolution], time_zone="UTC", eager=True)
    return pl.DataFrame({"timestamp": cells}).with_columns(pl.lit(1, pl.Int64).alias("_w"))


def _refuse_wide_window(resolution: str, cells: float) -> None:
    """Refuse a window with more cells than a group is counted over: it would cost more than the answer can say."""
    if cells > MAX_CELLS:
        message = (
            f"The window spans {cells:,.0f} steps of {resolution} values, more than the {MAX_CELLS:,} the statistics "
            "count the values of a group over. Give a narrower `timestamp`."
        )
        raise RowSelectionRefusedError(message)


def _on_the_clock(stamp: dt.datetime, minutes: int, *, up: bool) -> dt.datetime:
    """Give the step of the clock (every `minutes` minutes of the hour) at or after a stamp, or at or before it."""
    floor = stamp.replace(minute=stamp.minute - stamp.minute % minutes, second=0, microsecond=0)
    return floor + dt.timedelta(minutes=minutes) if up and floor != stamp else floor


def _sub_hourly_cells(minutes: int, low: dt.datetime, high: dt.datetime) -> pl.DataFrame:
    """Make the hourly cells of a period of steps finer than an hour, each with the steps of it in the period."""
    import polars as pl  # noqa: PLC0415

    step = dt.timedelta(minutes=minutes)
    # the steps are those of the clock (a 10-minute value is dated 00:10, 00:20), not counted from where the period
    # begins: a window from 00:05 has its first step at 00:10 and a window to 03:00 its last at 03:00
    low = _on_the_clock(low, minutes, up=True)
    last = _on_the_clock(high, minutes, up=False)
    high = last
    hour = dt.timedelta(hours=1)
    first_hour = low.replace(minute=0, second=0, microsecond=0)
    last_hour = last.replace(minute=0, second=0, microsecond=0)
    if high < low:
        return pl.DataFrame(schema={"timestamp": pl.Datetime("us", "UTC"), "_w": pl.Int64})
    _refuse_wide_window("hourly", (last_hour - first_hour) / hour + 1)
    full = 60 // minutes
    stamp = pl.Datetime("us", "UTC")
    cells = pl.datetime_range(first_hour, last_hour, "1h", time_zone="UTC", eager=True)
    frame = pl.DataFrame({"timestamp": cells}).with_columns(pl.lit(full, pl.Int64).alias("_w"))
    if first_hour == last_hour:
        return frame.with_columns(
            pl.lit(low, stamp).alias("timestamp"), pl.lit(1 + (last - low) // step, pl.Int64).alias("_w")
        )
    # the steps of the first hour that begin at or after `low`, and those of the last that begin at or before `last`
    in_first = -((low - (first_hour + hour)) // step)
    in_last = 1 + (last - last_hour) // step
    row, end = pl.int_range(pl.len()), pl.len() - 1
    return frame.with_columns(
        pl.when(row == 0)
        .then(pl.lit(low, stamp))
        .when(row == end)
        .then(pl.lit(last, stamp))
        .otherwise(pl.col("timestamp"))
        .alias("timestamp"),
        pl.when(row == 0).then(in_first).when(row == end).then(in_last).otherwise(full).cast(pl.Int64).alias("_w"),
    )


def _keyed(frame: pl.DataFrame, year_start: int, columns: Iterable[str]) -> pl.DataFrame:
    """Add the calendar parts a group or a condition reads as columns: UTC, the year a season ends in."""
    import polars as pl  # noqa: PLC0415

    stamp = pl.col("timestamp")
    parts = {
        "year": stamp.dt.year()
        if year_start == 1
        else stamp.dt.year() + (stamp.dt.month() >= year_start).cast(pl.Int32),
        "month": stamp.dt.month(),
        "day": stamp.dt.day(),
        "hour": stamp.dt.hour(),
    }
    wanted = [name for name in CALENDAR if name in set(columns)]
    return frame.with_columns(parts[name].alias(name) for name in wanted)


def keep(frame: pl.DataFrame, conditions: Sequence[Condition]) -> pl.DataFrame:
    """Keep the rows that meet every condition, a missing value never meeting one."""
    import polars as pl  # noqa: PLC0415

    if not conditions:
        return frame
    return frame.filter(pl.all_horizontal(condition_expr(c) for c in conditions))


def condition_expr(condition: Condition) -> pl.Expr:
    """Write a condition as an expression over the column it names: a missing value never matches, `!=` included."""
    import polars as pl  # noqa: PLC0415

    column = pl.col(condition.column)
    values = list(condition.values)
    if isinstance(values[0], (int, float)) and not isinstance(values[0], bool):
        # a list of whole numbers meets a column of integers of any width and a float as well (`count=90|365`)
        column = column.cast(pl.Float64)
        values = [float(v) for v in values]
    match condition.operator:
        case "=":
            expr = column.is_in(values) if len(values) > 1 else column == values[0]
        case "!=":
            expr = ~column.is_in(values) if len(values) > 1 else column != values[0]
        case "<":
            expr = column < values[0]
        case "<=":
            expr = column <= values[0]
        case ">":
            expr = column > values[0]
        case _:
            expr = column >= values[0]
    return expr.fill_null(value=False) & column.is_not_null()


# ----------------------------------------------------------------------------------------------------------------
# one series
# ----------------------------------------------------------------------------------------------------------------


@dataclass
class SeriesStatistics:
    """The statistics of one station's series: who it is, how much of it was searched, its groups and their statistics.

    `frame` holds the groups that are rows: the columns of `by`, each aggregate (with `<aggregate>_at` for `min`,
    `max`, `first` and `last`), `searched` and `expected`. The statistics over the groups (`over_groups`) are of all
    the series' groups before `having`, `sort` and `first` chose among them.
    """

    station_id: str
    name: str | None
    resolution: str
    dataset: str
    parameter: str
    unit: str
    units: dict[str, str]
    first: dt.datetime | None
    last: dt.datetime | None
    searched: int
    expected: int | None
    gaps: int | None
    over_groups: dict[str, dict[str, Any]]
    frame: pl.DataFrame
    #: all the groups of the series, those that are not rows included
    groups: int = 0
    not_listed: int = 0
    incomplete: int = 0
    #: the groups left after `having`, before `sort` and `first` chose among them
    matched: int = 0
    #: how many groups tie with the last one shown, and are not shown (`first` is exactly N)
    tied: int = 0
    unknown_completeness: bool = False


def _report_of(report: Mapping[str, Any] | None, series: _SeriesIn) -> dict[str, Any]:
    """Give the row of the report of a series, an empty one for a series the report has no row for."""
    if report is not None:
        return dict(report)
    return {
        "name": None,
        "searched": 0,
        "expected": None,
        "gaps": None,
        "first": None,
        "last": None,
        "station_id": series.station_id,
    }


@dataclass(frozen=True)
class _SeriesIn:
    """A series as the walk hands it over: who it is, what its parameter allows, and its readings with a value."""

    station_id: str
    resolution: str
    dataset: str
    parameter: str
    meta: SeriesMeta
    frame: pl.DataFrame
    forecast: bool = False


def reduce_series(  # noqa: C901
    plan: StatisticsPlan,
    series: _SeriesIn,
    report: Mapping[str, Any] | None,
    window: tuple[dt.datetime | None, dt.datetime | None],
    now: dt.datetime,
) -> SeriesStatistics:
    """Make the groups of a series and their aggregates, with the completeness of each, as the rules say.

    `report` is the row `searched_of` gave for the series: how many values it has, from when to when, and how many are
    expected. The groups are those of the window (without one, from the first value to the last, the running year
    whole): a group has a cell for each step of the resolution in its period that passes the time conditions, and
    `expected` is the number of cells. `searched` is the values present in them, `count` and the others are of those
    that also meet the value conditions.
    """
    import polars as pl  # noqa: PLC0415

    units = refuse_for(plan, series.meta, series.resolution)
    row = _report_of(report, series)
    w0, w1 = window
    first_ts, last_ts = row["first"], row["last"]
    keys = list(plan.by) or ["_all"]
    calendar = {*plan.by, *(c.column for c in plan.time_conditions)}
    frame = series.frame.drop_nulls("value").sort("timestamp")

    looked = keep(_keyed(frame, plan.year_start, calendar), plan.time_conditions)
    matched = keep(looked, plan.value_conditions)
    if not plan.by:
        looked = looked.with_columns(pl.lit(0).alias("_all"))
        matched = matched.with_columns(pl.lit(0).alias("_all"))

    # ---- expected, per group: the steps of the resolution in the group's period -------------------------------------
    known = row["expected"] is not None
    expected = None
    if known and (first_ts is not None or w0 is not None):
        period = _period(plan, series.resolution, (w0, w1), first_ts, last_ts, now)
        if period is not None:
            cells = _cells(series.resolution, period[0], period[1], own_stamp=period[2])
            cells = keep(_keyed(cells, plan.year_start, calendar), plan.time_conditions)
            if not plan.by:
                cells = cells.with_columns(pl.lit(0).alias("_all"))
            # a group is a period with a step inside the window (without one, inside the values): the months of a year
            # the window cuts that lie outside it are no groups, not groups without a value
            low = w0 if w0 is not None else first_ts
            high = w1 if w1 is not None else (last_ts if w0 is None else None)
            inside = pl.lit(value=True)
            if low is not None:
                # a cell begins where its step does: the day of a value dated 06:00 begins at 00:00, before the value.
                # A month or a year the window begins inside has passed, as a window counts them: its cell is not
                # inside, unless the period begins at a value's own stamp, which that month or year holds
                calendar_step = series.resolution in ("monthly", "annual")
                from_window = w0 is not None
                lower = (
                    _ceil(series.resolution, low) if calendar_step and from_window else _floor(series.resolution, low)
                )
                inside &= pl.col("timestamp") >= lower
            if high is not None:
                inside &= pl.col("timestamp") <= high
            expected = (
                cells.group_by(keys)
                .agg(
                    pl.col("_w").sum().alias("expected"),
                    pl.col("timestamp").min().alias("_cmin"),
                    pl.col("timestamp").max().alias("_cmax"),
                    inside.any().alias("_inside"),
                )
                # a period that has not begun (December of the running year) is no group
                .filter((pl.col("_cmin") <= now) & pl.col("_inside"))
                .drop("_inside")
            )
    searched_by = looked.group_by(keys).agg(pl.len().cast(pl.Int64).alias("searched"))
    if expected is not None:
        base = expected.join(searched_by, on=keys, how="full", coalesce=True)
    else:
        base = searched_by.with_columns(pl.lit(None, pl.Int64).alias("expected"))
    base = base.with_columns(pl.col("searched").fill_null(0).cast(pl.Int64), pl.col("expected").cast(pl.Int64))
    # a group with more values than steps (a source finer than its resolution): how many it should have is not known
    base = base.with_columns(
        pl.when(pl.col("searched") > pl.col("expected")).then(None).otherwise(pl.col("expected")).alias("expected")
    )

    # ---- the aggregates, of the values that count ------------------------------------------------------------------
    if matched.height:
        base = base.join(matched.group_by(keys).agg(_aggregates(plan)), on=keys, how="left")
    for column in ("_matched", *plan.aggregate, *(f"{a}_at" for a in plan.aggregate if a in DATED)):
        if column not in base.columns:
            dtype = pl.Datetime("us", "UTC") if column.endswith("_at") else pl.Float64
            base = base.with_columns(pl.lit(None, pl.UInt32 if column == "_matched" else dtype).alias(column))
    base = base.with_columns(pl.col("_matched").fill_null(0))

    # ---- completeness: an incomplete group has no mean and no sum --------------------------------------------------
    incomplete = ((pl.col("expected") - pl.col("searched")) > plan.max_missing).fill_null(value=False)
    no_value = pl.col("searched") == 0
    exprs = []
    for name in plan.aggregate:
        if name == "count":
            exprs.append(pl.when(no_value).then(None).otherwise(pl.col("_matched")).cast(pl.Int64).alias("count"))
        elif name in ("mean", "sum"):
            none_matched = pl.when(pl.col("_matched") == 0).then(0.0 if name == "sum" else None).otherwise(pl.col(name))
            # rounded where it is made, so that two sums that differ in the last bit of a float tie
            exprs.append(pl.when(no_value | incomplete).then(None).otherwise(none_matched).round(6).alias(name))
    base = base.with_columns([*exprs, incomplete.alias("_incomplete"), (~incomplete).cast(pl.Int8).alias("complete")])

    # ---- which groups are rows: not the periods before the first value or after the last -----------------------------
    total = base.height
    not_listed = 0
    if first_ts is None:
        not_listed, base = base.height, base.head(0)
    elif "_cmin" in base.columns:
        outside = no_value & ((pl.col("_cmax") < first_ts) | (pl.col("_cmin") > last_ts))
        not_listed = int(base.select(outside.sum()).item())
        base = base.filter(~outside)
    base = base.sort(keys, maintain_order=True)

    # ---- the statistics over the groups, before having, sort and first ----------------------------------------------
    over: dict[str, dict[str, Any]] = {}
    for name in plan.aggregate:
        if name in ("earliest", "latest"):
            continue
        # only complete groups with a value: a running year's count is a lower bound, no year's count
        usable = base.filter(~pl.col("_incomplete")).get_column(name).drop_nulls()
        over[name] = {
            "groups": total,
            "usable": usable.len(),
            "min": _number(usable.min()),
            "max": _number(usable.max()),
            "mean": _number(usable.mean()),
        }
    base = base.drop("_matched", "_all", "_cmin", "_cmax", strict=False)
    selected = [*plan.by, *_aggregate_columns(plan), "searched", "expected", "complete", "_incomplete"]
    base = base.select(selected)
    return SeriesStatistics(
        station_id=series.station_id,
        name=row["name"],
        resolution=series.resolution,
        dataset=series.dataset,
        parameter=series.parameter,
        unit=series.meta.unit,
        units={a: u for a, u in units.items() if u is not None and u != series.meta.unit},
        first=first_ts,
        last=last_ts,
        searched=int(row["searched"]),
        expected=row["expected"],
        gaps=row["gaps"],
        over_groups=over,
        frame=base,
        groups=total,
        not_listed=not_listed,
        incomplete=int(base.get_column("_incomplete").sum()),
        matched=base.height,
        unknown_completeness=bool(base.filter(pl.col("expected").is_null() & (pl.col("searched") > 0)).height),
    )


def _aggregate_columns(plan: StatisticsPlan) -> list[str]:
    """Give the columns the aggregates make, in the order they are asked for, a dated one followed by its date."""
    columns: list[str] = []
    for name in plan.aggregate:
        columns.append(name)
        if name in DATED:
            columns.append(f"{name}_at")
    return columns


def _aggregates(plan: StatisticsPlan) -> list[pl.Expr]:
    """Write the aggregates of a group of the values that count, which are in the order of their time."""
    import polars as pl  # noqa: PLC0415

    value, stamp = pl.col("value"), pl.col("timestamp")
    out: list[pl.Expr] = [pl.len().alias("_matched")]
    for name in plan.aggregate:
        if name == "mean":
            out.append(value.mean().alias("mean"))
        elif name == "sum":
            out.append(value.sum().alias("sum"))
        elif name in ("min", "max"):
            extreme = value.min() if name == "min" else value.max()
            out.append(extreme.alias(name))
            # a tie gives the earliest date
            out.append(stamp.filter(value == extreme).first().alias(f"{name}_at"))
        elif name in ("earliest", "latest"):
            out.append((value.first() if name == "earliest" else value.last()).alias(name))
            out.append((stamp.first() if name == "earliest" else stamp.last()).alias(f"{name}_at"))
    return out


def _number(value: Any) -> float | None:  # noqa: ANN401
    """Round a statistic over the groups to the six decimals an answer keeps; None stays none."""
    return None if value is None else round(float(value), 6)


def _period(
    plan: StatisticsPlan,
    resolution: str,
    window: tuple[dt.datetime | None, dt.datetime | None],
    first_ts: dt.datetime | None,
    last_ts: dt.datetime | None,
    now: dt.datetime,
) -> tuple[dt.datetime, dt.datetime, bool] | None:
    """Give the period the cells of a series are counted over, None where it has none (rule 3 of the completeness).

    The third member says whether the period begins at a value's own stamp (and not at the start of a window).

    With a `year` in `by`: the years (or seasons) of the window, whole, and cut neither by the window nor by the record
    nor by today, so that a year that the window cuts, or that is not over, is incomplete. Without a `year`: from the
    start of the window (without one: the first value) to its end (without one: the last value) and not past the last
    complete step
    of the resolution, but never narrower than the values found: as `searched_of` counts, so that one group over the
    whole series has the `expected` of the series.
    """
    w0, w1 = window
    if "year" in plan.by:
        start_at, end_at = (w0, w1 or now) if w0 is not None else (first_ts, last_ts)
        if start_at is None or end_at is None:
            return None
        low = _season_bounds(_season_year(start_at.year, start_at.month, plan.year_start), plan.year_start)[0]
        high = _season_bounds(_season_year(end_at.year, end_at.month, plan.year_start), plan.year_start)[1]
        return (low, high, False) if low <= high else None
    from wetterdienst.metadata.resolution import Resolution  # noqa: PLC0415

    latest = latest_complete(Resolution(resolution), now)
    has_window = w0 is not None and latest is not None and w0 <= latest
    if first_ts is None or last_ts is None:
        if not has_window or w0 is None or latest is None:
            return None
        return w0, min(w1 or latest, latest), False
    low, high = first_ts, last_ts
    if has_window and w0 is not None and latest is not None:
        low = min(w0, first_ts)
        high = max(min(w1 or latest, latest), last_ts)
    return low, high, low == first_ts


# ----------------------------------------------------------------------------------------------------------------
# having, sort and first
# ----------------------------------------------------------------------------------------------------------------


def _with_station(frame: pl.DataFrame, station_id: str) -> pl.DataFrame:
    """Give the groups of a series a `station_id` column, which `sort` may name."""
    import polars as pl  # noqa: PLC0415

    return frame.with_columns(pl.lit(station_id).alias("station_id"))


def _ordered(plan: StatisticsPlan, frame: pl.DataFrame) -> pl.DataFrame:
    """Put the groups in the order of `sort`: a null last, then the columns of `by` and the station tell ties apart."""
    columns = [key.column for key in plan.sort]
    tail = [c for c in (*plan.by, "station_id") if c in frame.columns and c not in columns]
    return frame.sort(
        [*columns, *tail],
        descending=[*(key.descending for key in plan.sort), *([False] * len(tail))],
        nulls_last=True,
        maintain_order=True,
    )


def _first_of(plan: StatisticsPlan, frame: pl.DataFrame, *, exact: bool) -> tuple[pl.DataFrame, int]:
    """Keep the first `first` groups of the `sort` order, and say how many more tie with the last one kept.

    `exact` keeps exactly N (the ties are ordered by the columns of `by` and the station); without it every group that
    ties with the N-th is kept, which is what a pool of candidates must keep until the stations are all read (a
    group worse than the N-th of some stations cannot be the N-th of all of them, one that ties with it can).
    A group whose sort column is null has no place in the order and is not kept.
    """
    import polars as pl  # noqa: PLC0415

    assert plan.first is not None  # noqa: S101
    columns = [key.column for key in plan.sort]
    ranked = _ordered(plan, frame.drop_nulls(subset=columns))
    if ranked.is_empty():
        return ranked, 0
    row = pl.int_range(pl.len())
    starts_run = pl.any_horizontal([pl.col(c).ne_missing(pl.col(c).shift(1)) for c in columns]) | (row == 0)
    run_start = pl.when(starts_run).then(row).otherwise(None).forward_fill()
    tied = int(ranked.select(((run_start < plan.first) & (row >= plan.first)).sum()).item())
    if exact:
        return ranked.head(plan.first), tied
    return ranked.filter(run_start < plan.first), tied


def _having(plan: StatisticsPlan, frame: pl.DataFrame) -> pl.DataFrame:
    """Keep the groups that meet every condition of `having`."""
    return keep(frame, plan.having)


# ----------------------------------------------------------------------------------------------------------------
# the walk's side: a run feeds on stations, a result comes out
# ----------------------------------------------------------------------------------------------------------------


def _now() -> dt.datetime:
    """Give the moment a group is judged over: the one place a test sets the clock."""
    return dt.datetime.now(dt.UTC)


class StatisticsRun:
    """The statistics of a walk of stations: one station at a time goes in, only its groups stay.

    Built by `for_stations` from a stations result (the parameters of the request, the options, the window), and fed
    by the walk of `TimeseriesValues` (`add_station`), which hands over each station's frame and lets it go. Each
    series is reduced at once to its groups; with `per=station` `having`, `sort` and `first` are applied then, so that
    what stays is what the answer holds; with `per=none` the candidates of each parameter stay, cut to those that can
    still be among the first N as the stations arrive (`_compact`). `finish` makes the result.
    """

    def __init__(
        self,
        plan: StatisticsPlan,
        parameters: Mapping[tuple[str, str, str], SeriesMeta],
        window: tuple[dt.datetime | None, dt.datetime | None],
        *,
        forecast: bool = False,
        held_groups_limit: int | None = None,
        names: Mapping[str, str | None] | None = None,
    ) -> None:
        """Hold the plan, the parameters by (resolution, dataset, parameter), the window and the held-groups limit."""
        self.plan = plan
        self.parameters = parameters
        self.window = window
        self.forecast = forecast
        self.limit = held_groups_limit
        self.names = names
        self.series: list[SeriesStatistics] = []
        self.now = _now()
        self._held = 0
        self._since_compaction = 0
        #: per parameter under `per=none`: the key of the N-th group at the last compaction, and how many groups that
        #: dropped have it too (they tie with the N-th, whatever comes later)
        self._carried: dict[tuple[str, str, str], tuple[tuple[Any, ...], int]] = {}

    @classmethod
    def for_stations(
        cls,
        stations: StationsResult,
        plan: StatisticsPlan,
        *,
        unit_symbol: Callable[[ParameterModel], str],
        held_groups_limit: int | None = None,
    ) -> StatisticsRun:
        """Build the run of a request from its stations result: the parameters by name as the answer writes it."""
        from wetterdienst.model.series_report import station_names  # noqa: PLC0415

        options = stations.options
        if not options.tidy:
            raise RowSelectionRefusedError(
                "`statistics` needs the long shape, where a row is one value of one parameter; the request is wide. "
                "Ask with shape=long."
            )
        plan = plan.bound(ParameterNames.of(stations.parameters, humanize=options.humanize))
        parameters: dict[tuple[str, str, str], SeriesMeta] = {}
        units: dict[str, str] = {}
        for parameter in stations.parameters:
            name = parameter.name if options.humanize else parameter.name_original
            key = (parameter.dataset.resolution.name, parameter.dataset.name.lower(), name)
            meta = SeriesMeta.of(parameter, unit_symbol(parameter))
            parameters.setdefault(key, meta)
            units.setdefault(meta.unit, parameter.name)
            # what a parameter cannot do with the options is told before any download, not at a station with rows
            refuse_for(plan, meta, parameter.dataset.resolution.name)
        if plan.value_conditions and len(units) > 1:
            listed = "; ".join(f"{name} in {unit}" for unit, name in units.items())
            raise RowSelectionRefusedError(
                "A `filter` on `value` has one number for every parameter of the request, which are not in one unit "
                f"({listed}). Name one parameter in `parameters`, e.g. daily/climate_summary/temperature_air_min_2m, "
                "or filter on `year`, `month`, `day` and `hour` only."
            )
        return cls(
            plan,
            parameters,
            (stations.start, stations.end),
            forecast=stations.request.metadata.kind == "forecast",
            held_groups_limit=held_groups_limit,
            names=station_names(stations.df),
        )

    def meta_of(self, resolution: str, dataset: str, parameter: str) -> SeriesMeta:
        """Give what the request knows of a series' parameter, as the answer names it."""
        found = self.parameters.get((resolution, dataset, parameter))
        if found is None:
            found = next(
                (m for (r, _, p), m in self.parameters.items() if r == resolution and p == parameter),
                None,
            )
        if found is None:
            message = f"`{parameter}` of {resolution}/{dataset} is not a parameter of this request"
            raise RowSelectionRefusedError(message)
        return found

    def add_station(self, df: pl.DataFrame, searched: pl.DataFrame) -> None:
        """Reduce the series of one station's long frame to their groups, and let the frame go.

        `searched` is the report of the station's series (`searched_of`). Raises `GroupsOverLimitError` where the
        groups held are more than the limit.
        """
        reports = {(r["resolution"], r["dataset"], r["parameter"]): r for r in searched.iter_rows(named=True)}
        for key, frame in df.partition_by(
            ["resolution", "dataset", "parameter"], as_dict=True, maintain_order=True
        ).items():
            resolution, dataset, parameter = (str(part) for part in key)
            station_id = str(frame.get_column("station_id")[0])
            series = _SeriesIn(
                station_id,
                resolution,
                dataset,
                parameter,
                self.meta_of(resolution, dataset, parameter),
                frame.select("timestamp", "value"),
                forecast=self.forecast,
            )
            stats = reduce_series(self.plan, series, reports.get(key), self.window, self.now)
            self._keep(stats)
        if self.limit and self._held > self.limit and not self.plan.per_station and self.plan.first:
            # the candidates are cut to the first N before the limit says they are too many: only what cannot be among
            # the first N is let go
            self._compact()
        if self.limit and self._held > self.limit:
            raise GroupsOverLimitError(self._held, self.limit)

    def _keep(self, stats: SeriesStatistics) -> None:
        """Choose among a series' groups as far as its own series decides, and hold what is left."""
        frame = _having(self.plan, stats.frame)
        stats.matched = frame.height
        if self.plan.per_station:
            frame, tied = self._choose(stats, frame)
            stats.tied = tied
        stats.frame = frame
        self._held += frame.height
        self._since_compaction += frame.height
        self.series.append(stats)
        if (
            not self.plan.per_station
            and self.plan.first
            and self._since_compaction > max(4 * self.plan.first, COMPACT_GROUPS)
        ):
            self._compact()

    def _choose(self, stats: SeriesStatistics, frame: pl.DataFrame) -> tuple[pl.DataFrame, int]:
        """Put one series' groups in the order of `sort` and keep its first N, exactly, with how many more tie."""
        if not self.plan.sort:
            return frame, 0
        frame = _with_station(frame, stats.station_id)
        if self.plan.first is not None:
            frame, tied = _first_of(self.plan, frame, exact=True)
        else:
            frame, tied = _ordered(self.plan, frame), 0
        return frame.drop("station_id"), tied

    def _by_parameter(self) -> dict[tuple[str, str, str], list[SeriesStatistics]]:
        """Group the series that compete under `per=none`: the stations of one parameter."""
        groups: dict[tuple[str, str, str], list[SeriesStatistics]] = {}
        for stats in self.series:
            groups.setdefault((stats.resolution, stats.dataset, stats.parameter), []).append(stats)
        return groups

    def _across(self, *, final: bool) -> int:
        """Keep the first N over the stations of each parameter (`per=none`), and give how many more tie.

        Exactly N, in the order of `sort`: what is dropped cannot come back, so the number of dropped groups that have
        the key of the N-th is carried (`_carried`) and counted as tying with it as long as the N-th key is the same.
        `final` also ranks the groups.
        """
        import polars as pl  # noqa: PLC0415

        tied_total = 0
        columns = [key.column for key in self.plan.sort]
        for parameter, members in self._by_parameter().items():
            pool = pl.concat(
                [
                    _with_station(m.frame, m.station_id).with_columns(pl.lit(index).alias("_s"))
                    for index, m in enumerate(members)
                ],
                how="diagonal_relaxed",
            )
            chosen, tied = _first_of(self.plan, pool, exact=True)
            carried = self._carried.get(parameter)
            if chosen.height:
                key = tuple(chosen.row(-1, named=True)[column] for column in columns)
                before = carried[1] if carried is not None and carried[0] == key else 0
                if tied + before:
                    self._carried[parameter] = (key, tied + before)
                else:
                    self._carried.pop(parameter, None)
                tied_total += tied + before
            if final:
                # the place of each group over the stations of the parameter
                chosen = chosen.with_row_index("rank", offset=1).with_columns(pl.col("rank").cast(pl.Int64))
            for index, member in enumerate(members):
                member.frame = chosen.filter(pl.col("_s") == index).drop("_s", "station_id", strict=False)
                member.tied = 0
        self._held = sum(m.frame.height for m in self.series)
        return tied_total

    def _compact(self) -> None:
        """Drop the candidates that cannot be among the first N of their parameter, keeping the count of the ties."""
        self._across(final=False)
        self._since_compaction = 0

    def finish(
        self,
        stations: StationsResult,
        *,
        stations_read: int | None,
        data_updated_at: dt.datetime | None = None,
    ) -> StatisticsResult:
        """Settle what is left (`first` over the stations of `per=none`, `max_rows`) and make the result."""
        tied = 0
        series, left_out = self.series, []
        if not self.plan.per_station and self.plan.first:
            tied = self._across(final=True)
            series, left_out = self._in_rank_order()
        tied += sum(s.tied for s in series)
        result = StatisticsResult(
            stations=stations,
            plan=self.plan,
            series=series,
            left_out=left_out,
            window=self.window,
            stations_read=stations_read,
            tied=tied,
            data_updated_at=data_updated_at,
        )
        cap = self.plan.max_rows
        total = sum(s.frame.height for s in series)
        if cap is not None and total > cap:
            result = result.head(cap, drop_empty=not self.plan.per_station)
            result.capped = (cap, total)
        result.warn()
        return result

    def _in_rank_order(self) -> tuple[list[SeriesStatistics], list[SeriesStatistics]]:
        """Put the series of `per=none` in the order of their best group, and leave out those that kept none.

        One parameter at a time, in the order the parameters were read: the series whose best group ranks first comes
        first. A series that kept no group is not listed (the totals still count it).
        """
        listed: list[SeriesStatistics] = []
        left_out: list[SeriesStatistics] = []
        for members in self._by_parameter().values():
            kept = [m for m in members if not m.frame.is_empty()]
            left_out.extend(m for m in members if m.frame.is_empty())
            kept.sort(key=_best_rank)
            listed.extend(kept)
        return listed, left_out


def gaps_allowed_of(series: Sequence[SeriesStatistics]) -> tuple[int, int, int]:
    """Count the groups of an answer that lack values and are complete only because `max_missing` allows it.

    Gives how many, the most values one lacks, and how many all lack: a running year is among them as it lacks the
    days to come. A group with no `expected` is not (nothing is known to lack), nor is one with every value.
    """
    import polars as pl  # noqa: PLC0415

    groups = most = lacking = 0
    for s in series:
        if s.frame.is_empty():
            continue
        lacks = (
            s.frame.filter(
                pl.col("expected").is_not_null()
                & ~pl.col("_incomplete")
                & (pl.col("searched") > 0)
                & (pl.col("expected") > pl.col("searched"))
            )
            .select((pl.col("expected") - pl.col("searched")).alias("lacks"))
            .get_column("lacks")
            .to_list()
        )
        if not lacks:
            continue
        groups += len(lacks)
        most = max(most, *lacks)
        lacking += sum(lacks)
    return groups, most, lacking


def _best_rank(series: SeriesStatistics) -> int:
    """Give the rank of the best group a series kept, which a series of `per=none` that is listed has."""
    best = series.frame.get_column("rank").min()
    return int(best) if isinstance(best, int) else 0


@dataclass
class StatisticsResult:
    """What `statistics` answers: the series with their groups, the options, the window and the totals.

    `series` is in the order the stations were read, and with `per=none` in the order of the rank of their best group
    (`rank` is the place of each group over the stations of a parameter), those that kept no group left out
    (`left_out`, which the totals count). The groups of a series are in the order of `sort`, or by the columns of `by`.
    `df` is one row per group with the identity of its series in front of it. `to_dict`, `to_json`, `to_csv` and
    `to_ndjson` write the answer, `search` the report of what was searched that the `metadata` block of a REST answer
    carries.
    """

    stations: StationsResult
    plan: StatisticsPlan
    series: list[SeriesStatistics]
    left_out: list[SeriesStatistics] = field(default_factory=list)
    window: tuple[dt.datetime | None, dt.datetime | None] = (None, None)
    stations_read: int | None = None
    tied: int = 0
    capped: tuple[int, int] | None = None
    data_updated_at: dt.datetime | None = None
    warnings_made: bool = field(default=False, repr=False)

    def head(self, groups: int, *, drop_empty: bool = False) -> StatisticsResult:
        """Keep the first `groups` groups of the answer: by rank under `per=none`, else in the order of the answer.

        A series left with no group is dropped with `drop_empty` (and counted in the totals as every series is).
        """
        import polars as pl  # noqa: PLC0415

        if self.plan.per_station:
            left = groups
            frames = []
            for s in self.series:
                frame = s.frame.head(left)
                left -= frame.height
                frames.append(frame)
        else:
            order = {
                key: n
                for n, key in enumerate(dict.fromkeys((s.resolution, s.dataset, s.parameter) for s in self.series))
            }
            ranks = [
                s.frame.select("rank").with_columns(
                    pl.lit(n).alias("_s"), pl.lit(order[(s.resolution, s.dataset, s.parameter)]).alias("_p")
                )
                for n, s in enumerate(self.series)
            ]
            kept = pl.concat(ranks).sort("rank", "_p", "_s").head(groups) if ranks else None
            frames = (
                [
                    s.frame.filter(pl.col("rank").is_in(kept.filter(pl.col("_s") == n).get_column("rank")))
                    for n, s in enumerate(self.series)
                ]
                if kept is not None
                else []
            )
        listed, dropped = [], []
        for s, frame in zip(self.series, frames, strict=True):
            (dropped if drop_empty and frame.is_empty() else listed).append(replace(s, frame=frame))
        return replace(self, series=listed, left_out=[*self.left_out, *dropped])

    @property
    def df(self) -> pl.DataFrame:
        """Give one row per group: the series, `rank` (`per=none`), the columns of `by`, the aggregates, the counts."""
        import polars as pl  # noqa: PLC0415

        frames = [self._identified(s, s.frame.drop("_incomplete")) for s in self.series]
        if not frames:
            return pl.DataFrame(schema=_schema(self.plan))
        return pl.concat(frames, how="diagonal_relaxed").with_columns(pl.col("complete").cast(pl.Boolean))

    @staticmethod
    def _identified(s: SeriesStatistics, frame: pl.DataFrame) -> pl.DataFrame:
        """Put the identity of a series in front of its groups."""
        import polars as pl  # noqa: PLC0415

        identity = {
            "station_id": s.station_id,
            "resolution": s.resolution,
            "dataset": s.dataset,
            "parameter": s.parameter,
        }
        return frame.select(*(pl.lit(value).alias(key) for key, value in identity.items()), pl.all())

    def _written(self, s: SeriesStatistics) -> pl.DataFrame:
        """Give the groups of a series as the answer writes them: dates as text, `complete` as a boolean."""
        import polars as pl  # noqa: PLC0415

        pattern = "%Y-%m-%d" if s.resolution in ("daily", "monthly", "annual") else "%Y-%m-%dT%H:%MZ"
        dated = {f"{name}_at" for name in DATED}
        columns = [
            pl.col(c).dt.strftime(pattern).alias(c)
            if c in dated
            else pl.col(c).cast(pl.Boolean).alias(c)
            if c == "complete"
            else pl.col(c)
            for c in _group_fields(self.plan)
        ]
        return s.frame.select(columns)

    def warn(self) -> None:
        """Tell what the answer leaves open as the warnings of the request being served (once per answer)."""
        if self.warnings_made:
            return
        self.warnings_made = True
        plan = self.plan
        groups, most, lacking = gaps_allowed_of(self.series)
        if groups:
            count_response_warning(
                GAPS_ALLOWED,
                groups,
                gaps_allowed_message(groups, most, lacking, plan),
            )
        every = [*self.series, *self.left_out]
        in_answer = sum(int(s.frame.get_column("_incomplete").sum()) for s in self.series)
        message = incomplete_groups_message(sum(s.incomplete for s in every), in_answer, plan.max_missing)
        for s in every:
            name = s.name
            if s.incomplete:
                count_response_warning(
                    INCOMPLETE_GROUPS,
                    s.incomplete,
                    message,
                    station=s.station_id,
                    station_name=name,
                )
            if s.not_listed:
                count_response_warning(
                    NO_VALUES_IN_GROUPS,
                    s.not_listed,
                    NO_VALUES_IN_GROUPS_MESSAGE,
                    station=s.station_id,
                    station_name=name,
                )
            if s.unknown_completeness:
                count_response_warning(
                    COMPLETENESS_UNKNOWN, 1, COMPLETENESS_UNKNOWN_MESSAGE, station=s.station_id, station_name=name
                )
        if self.tied:
            warn_response(
                log,
                TIES_NOT_SHOWN,
                f"{self.tied:,} more {'groups tie' if self.tied != 1 else 'group ties'} with the last one shown (the "
                "same value of every `sort` column) and "
                f"{'are' if self.tied != 1 else 'is'} not shown: `first` keeps exactly N, in the order of `by` and "
                "then of the station. Add a second `sort` column, or raise `first`.",
                level=logging.INFO,
            )
        if self.capped is not None:
            returned, matched = self.capped
            warn_response(
                log,
                ROWS_CAPPED,
                f"{returned:,} of {matched:,} groups are returned: `max_rows` is {plan.max_rows}. The groups are the "
                f"{'best by rank' if not plan.per_station else 'first in the order of the answer'}, and "
                "`metadata.search.totals` counts all that matched.",
                level=logging.INFO,
            )

    # -- the answer ------------------------------------------------------------------------------------------------

    def totals(self) -> dict[str, Any]:
        """Count what the answer searched and holds, summed over all its series, those left out of the list too."""
        series = [*self.series, *self.left_out]
        unknown = any(s.expected is None for s in series)
        unknown_gaps = any(s.gaps is None for s in series)
        return {
            "stations_read": self.stations_read,
            "stations_with_values": len({s.station_id for s in series if s.searched}),
            "series": len(series),
            "searched": sum(s.searched for s in series),
            "expected": None if unknown else sum(s.expected or 0 for s in series),
            "gaps": None if unknown_gaps else sum(s.gaps or 0 for s in series),
            "groups": sum(s.groups for s in series),
            "groups_not_listed": sum(s.not_listed for s in series),
            "groups_incomplete": sum(s.incomplete for s in series),
            "groups_matched": sum(s.matched for s in series),
            "groups_returned": sum(s.frame.height for s in self.series),
        }

    def search(self) -> dict[str, Any]:
        """Write what was searched for the `metadata` block: the options as read, the window and the totals."""
        from wetterdienst.util.datetime import format_timestamp  # noqa: PLC0415

        def stamp(value: dt.datetime | None) -> str | None:
            return format_timestamp(value) if value is not None else None

        return {
            "options": self.plan.echo(),
            "window": {"start": stamp(self.window[0]), "end": stamp(self.window[1])},
            "totals": self.totals(),
        }

    def rows_of(self, series: SeriesStatistics) -> list[dict[str, Any]]:
        """Write the groups of a series as the answer has them: `by`, the aggregates, the counts, `complete`."""
        return self._written(series).to_dicts()

    def series_dicts(self, *, groups: bool = True) -> list[dict[str, Any]]:
        """Write the series: who each is, how much of it was searched, the statistics over its groups, its groups."""
        out = []
        for s in self.series:
            entry: dict[str, Any] = {
                "station_id": s.station_id,
                "name": s.name,
                "resolution": s.resolution,
                "dataset": s.dataset,
                "parameter": s.parameter,
                "unit": s.unit,
            }
            if s.units:
                entry["units"] = s.units
            entry.update(
                {
                    "first_timestamp": _short_stamp(s.first, s.resolution) if s.first else None,
                    "last_timestamp": _short_stamp(s.last, s.resolution) if s.last else None,
                    "searched": s.searched,
                    "expected": s.expected,
                    "gaps": s.gaps,
                    "over_groups": s.over_groups,
                }
            )
            if groups:
                entry["groups"] = self.rows_of(s)
            out.append(entry)
        return out

    def to_dict(self) -> dict[str, Any]:
        """Write the series of the answer, each with its groups: `{"series": [...]}`, without the `metadata` block."""
        return {"series": self.series_dicts()}

    def to_json(self, *, pretty: bool = False) -> str:
        """Write the answer as JSON: `to_dict` and what was searched (`search`: in `metadata` of a REST answer)."""
        answer = {"search": self.search(), **self.to_dict()}
        return json.dumps(
            answer, indent=2 if pretty else None, separators=None if pretty else (",", ":"), ensure_ascii=False
        )

    def to_csv(self, *, include_header: bool = True) -> str:
        """Write the groups as CSV, one row per group, the identity of its series first; no names, no statistics."""
        import polars as pl  # noqa: PLC0415

        frames = [self._identified(s, self._written(s)) for s in self.series]
        frame = pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame(schema=_schema(self.plan))
        return frame.write_csv(include_header=include_header)

    def groups_ndjson(self) -> str:
        """Write the groups as NDJSON lines, each with the identity of its series in front."""
        return "".join(self._identified(s, self._written(s)).write_ndjson() for s in self.series)

    def to_ndjson(self) -> str:
        """Write the groups as NDJSON, a line each with its series' identity, then an `end` line with the rest."""
        end = {
            "search": self.search(),
            "series": [{k: v for k, v in e.items() if k != "groups"} for e in self.series_dicts()],
        }
        return self.groups_ndjson() + json.dumps({"end": end}, ensure_ascii=False, separators=(",", ":")) + "\n"


def _group_fields(plan: StatisticsPlan) -> list[str]:
    """Name the columns of a group as the answer writes them: `rank` (`per=none`), `by`, the aggregates, the counts."""
    return [
        *(["rank"] if not plan.per_station else []),
        *plan.by,
        *_aggregate_columns(plan),
        "searched",
        "expected",
        "complete",
    ]


def _schema(plan: StatisticsPlan) -> dict[str, Any]:
    """Give the columns of the groups of a plan with their types, for a result that has none."""
    import polars as pl  # noqa: PLC0415

    schema: dict[str, Any] = dict.fromkeys(("station_id", "resolution", "dataset", "parameter"), pl.String)
    for name in _group_fields(plan):
        if name.endswith("_at"):
            schema[name] = pl.Datetime("us", "UTC")
        elif name in ("rank", "count", "searched", "expected"):
            schema[name] = pl.Int64
        elif name == "complete":
            schema[name] = pl.Boolean
        elif name in CALENDAR:
            schema[name] = pl.Int32 if name == "year" else pl.Int8
        else:
            schema[name] = pl.Float64
    return schema


def _short_stamp(value: dt.datetime, resolution: str) -> str:
    """Write a date in the shortest ISO form of the series: the day for daily and coarser, the minute for finer."""
    if resolution in ("daily", "monthly", "annual"):
        return value.strftime("%Y-%m-%d")
    return value.strftime("%Y-%m-%dT%H:%MZ")


def statistics_of_frame(
    stations: StationsResult,
    df: pl.DataFrame,
    plan: StatisticsPlan,
    *,
    unit_symbol: Callable[[ParameterModel], str],
    held_groups_limit: int | None = None,
) -> StatisticsResult:
    """Make the statistics of a frame of values that is held whole, station by station, as the walk makes them."""
    from wetterdienst.model.series_report import searched_of, station_names  # noqa: PLC0415

    run = StatisticsRun.for_stations(stations, plan, unit_symbol=unit_symbol, held_groups_limit=held_groups_limit)
    names = station_names(stations.df)
    read = 0
    if not df.is_empty():
        for station in df.partition_by("station_id", maintain_order=True):
            read += 1
            report = searched_of(
                station, run.window, run.now, names=names, forecast=run.forecast, stamped_on_the_day=True
            )
            run.add_station(station, report)
    return run.finish(stations, stations_read=read)


__all__ = [
    "AGGREGATES",
    "CALENDAR",
    "GroupsOverLimitError",
    "SeriesStatistics",
    "StatisticsPlan",
    "StatisticsResult",
    "StatisticsRun",
    "parse_statistics",
]
