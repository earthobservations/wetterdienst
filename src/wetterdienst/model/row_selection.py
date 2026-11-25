# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Choose the rows of a `values` answer: `filter`, `sort`, `first` and `by` (GH-4411).

A model that is asked for the lowest temperature ever measured in a city cannot find it when a station's daily
minimum is megabytes and an answer holds 40,000 characters. These four options pick the rows the answer is about,
on the server, from what was read.

======  ==============================================================================================================
filter  conditions joined with `,` (and): `column op value`; the columns `value`, `year`, `month`, `day`, `hour` or
        the name of a parameter of the request (GH-4419); the operators `=  !=  <  <=  >  >=`; a list `a|b` of numbers
        with `=` and `!=`. `value<=-20,month=12|1|2`, `temperature_air_min_2m<0,wind_gust_max>=17.2`
sort    one or more columns, `-` before one for descending: `-value`, `month,day`, `temperature_air_min_2m`; the
        columns of `filter` and `timestamp` and `station_id`
first   how many rows of each group, the first of the `sort` order; the rows that tie with the last one are kept
by      the groups `first` counts in, default the station: `station_id,year`; `none` is over all the stations
max_rows  the most rows of the whole answer, the last step, after the others: the first rows of the answer's order
======  ==============================================================================================================

The text is read by the small parser below, which is all there is: no regular expression, no `eval`, no SQL of
polars or DuckDB, and nothing in the text is a function or a nesting. A name is the one thing it reads that is not a
fixed word: letters, digits and underscores, looked up among the parameters of the request and nowhere else. It
is linear in the length of the text, which is bounded (`MAX_FILTER_LENGTH` and the constants beside it), and the one
error it raises names the option, the position, what was found there and what is allowed. The text is checked in full
before a station is read.

A parameter's name stands for its value at the timestamp of the row, so that two parameters of one station meet at
one time: `temperature_air_min_2m<0,wind_gust_max>=17.2` keeps the timestamps of a station at which every condition
holds, a missing value meeting none, and the answer is the rows of every requested parameter at those timestamps.
With a name, a row of `filter`, `sort`, `first` and `by` is a timestamp of a station (and a resolution), not a reading
of one parameter; `ParameterNames` says which names the request has and `RowSelection._timestamp_rows` makes the
frame of timestamps of a station that the conditions are judged on.

Where the options act, what a group is and what an empty answer means are written in `docs/usage/restapi.md` ("Choose
the rows"); this module is the one place that implements them: the reader of the values (`TimeseriesValues.all` and
`query`), the result (`ValuesResult.selected_rows`) and every surface call `RowSelection`.

The module imports no polars until a frame is selected from, so that the command line can parse a text for `--help`
and a usage error without its cost.
"""

from __future__ import annotations

import datetime as dt
import difflib
import math
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Final, Literal, TypedDict

from wetterdienst.exceptions import RequestError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

    import polars as pl

    from wetterdienst.metadata.resolution import Resolution
    from wetterdienst.model.metadata import ParameterModel

#: the longest `filter` text, in characters: far more than any condition list a person or a model writes (8 conditions
#: of 30 characters), and little enough that the parse is of no cost
MAX_FILTER_LENGTH: Final = 400
#: the most conditions a `filter` joins
MAX_CONDITIONS: Final = 8
#: the most numbers one list `a|b|c` holds
MAX_LIST_ITEMS: Final = 32
#: the longest number, in characters
MAX_NUMBER_LENGTH: Final = 24
#: the longest `sort` and `by` text, in characters
MAX_ORDER_LENGTH: Final = 100
#: the largest `first`: the rows of a group are the readings of a station, and more than this are no answer to read
MAX_FIRST: Final = 10_000
#: the largest `max_rows`: an answer to read is not larger, and what is held for it in memory is bounded by it
MAX_MAX_ROWS: Final = 10_000
#: the series a report names one by one (`Searched.to_dict`); the totals count all of them
MAX_REPORTED_SERIES: Final = 100
#: the same in the answer of an MCP tool, whose answer is held to a budget the report would otherwise take (100 stations
#: are 28,000 characters of 40,000)
MAX_TOOL_SERIES: Final = 20

#: the columns a condition of `filter` may name; the calendar parts are those of the `timestamp` in UTC
FILTER_COLUMNS: Final = ("value", "year", "month", "day", "hour")
#: the columns `sort` may name
SORT_COLUMNS: Final = ("value", "timestamp", "year", "month", "day", "hour", "station_id")
#: the columns `by` may name, besides `none`: the group is always one series (resolution, dataset, parameter) as well.
#: Not `timestamp`: a group of one instant over many stations has no bound but the rows read, and the calendar parts
#: do the same for the groups that mean something (a year, a month, a day)
BY_COLUMNS: Final = ("station_id", "year", "month", "day", "hour")
#: the group `first` counts in when `by` is not given
DEFAULT_BY: Final = ("station_id",)

#: the whole numbers a calendar column may be compared with: a number outside is a mistake (`month=0`, `hour=24`)
_CALENDAR_RANGE: Final = {"year": (1, 9999), "month": (1, 12), "day": (1, 31), "hour": (0, 23)}
#: the largest magnitude of a `value` number: more is no reading
_MAX_VALUE: Final = 1e15

#: the columns that make a timestamp of a station and a resolution one row of a long frame
_STAMP_KEYS: Final = ("station_id", "resolution", "timestamp")

_OPERATORS: Final = ("<=", ">=", "!=", "<", ">", "=")
_WORD = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
_DIGITS = frozenset("0123456789")

Operator = Literal["=", "!=", "<", "<=", ">", ">="]


class RowOptions(TypedDict, total=False):
    """The keywords of `TimeseriesValues.all` and `query` that choose the rows, as the text of each option."""

    filter: str | None
    sort: str | None
    first: int | str | None
    by: str | None
    max_rows: int | str | None


_FILTER_EXAMPLE = "Example: filter=value<=-20,month=12|1|2"
_SORT_EXAMPLE = "Example: sort=-value (the highest first), sort=value (the lowest), sort=month,day"
_BY_EXAMPLE = "Example: by=station_id,year (per station and year), by=none (over all stations)"

#: what to say to a column that a model or a person tries and that is none of the allowed ones, by name
_COLUMN_HINTS: Final = {
    "parameter": (
        "a parameter is a column by its own name, which must be one of the request's `parameters`: "
        "temperature_air_min_2m<0"
    ),
    "parameters": "name the parameters in `parameters`, and use a parameter's own name as the column",
    "resolution": "resolutions and datasets are never mixed in a group; name the one you want in `parameters`",
    "dataset": "resolutions and datasets are never mixed in a group; name the one you want in `parameters`",
    "station": "the column is `station_id`; choose stations with `stations`, `name` or the other selections",
    "stations": "the column is `station_id`; choose stations with `stations`, `name` or the other selections",
    "station_id": "choose stations with `stations`, `name` or the other selections; `station_id` is for `sort`, `by`",
    "date": "use `timestamp` for the window of the request, or `year`, `month` and `day` for a part of the date",
    "time": "use `hour` for the hour of the day, or `timestamp` for the window of the request",
    "timestamp": "the window is the `timestamp` option of the request; use `year`, `month`, `day` or `hour` here",
    "top": "`top` is the northern edge of a bounding box; the first rows of a group are `first`",
    "by:timestamp": (
        "a group of one instant is a row: use `year`, `month`, `day` or `hour`, or `none` for all stations together"
    ),
    "quality": "quality flags are not available in the row options yet",
    "quality_flags": "quality flags are not available in the row options yet",
    "flags": "quality flags are not available in the row options yet",
    "min": "name the lowest rows with sort=value and first=1; the highest with sort=-value and first=1",
    "max": "name the highest rows with sort=-value and first=1; the lowest with sort=value and first=1",
    "count": "counting and aggregating are not in the row options; `first` and `filter` choose rows",
    "mean": "counting and aggregating are not in the row options; `first` and `filter` choose rows",
    "sum": "counting and aggregating are not in the row options; `first` and `filter` choose rows",
    "asc": "write `-` before a column for descending, nothing for ascending: sort=-value",
    "desc": "write `-` before a column for descending, nothing for ascending: sort=-value",
}

_OPERATOR_HINTS: Final = {
    "==": "write a single `=`",
    "=<": "write `<=`",
    "=>": "write `>=`",
    "<>": "write `!=`",
    "~": "regular expressions and pattern matching are not available",
}


#: the words reserved for the options of step 2 (`docs/usage/compatibility.md`): no column, no parameter's name
STEP_TWO_WORDS: Final = frozenset({"window", "year_start", "timezone", "aggregate", "having", "per", "max_missing"})
#: the words that are never a parameter's name, so that a model that tries them is told what to do without a request
#: (the REST model refuses them before any station is looked up): the columns of the options, and the words
#: `_COLUMN_HINTS` answers. `tests/model/test_row_selection_names.py` holds every parameter of every provider to it
RESERVED_WORDS: Final = frozenset(
    {*FILTER_COLUMNS, *SORT_COLUMNS, "none", *STEP_TWO_WORDS, *(w for w in _COLUMN_HINTS if ":" not in w)}
)
#: the most closest names an unknown one is told, and the most names listed when none is close
_CLOSEST: Final = 3
_LISTED_NAMES: Final = 12


def _name_like(word: str) -> bool:
    """Tell whether a word can be a parameter's name: letters, digits and underscores, with a letter among them."""
    return bool(word) and all(char in _WORD for char in word) and any(char.isalpha() for char in word)


@dataclass(frozen=True)
class ParameterColumn:
    """A parameter of the request as a column of the selection: where its readings are in a frame.

    `resolution`, `dataset` and `parameter` identify its rows in the long shape, as the frame has them (the dataset
    in lower case, the parameter humanised if the request is); `wide` is the column that holds it in the wide shape;
    the numbers of a condition are in the unit the answer has for it, after the conversion of units.
    """

    resolution: str
    dataset: str
    parameter: str
    wide: str


@dataclass(frozen=True)
class ParameterNames:
    """The parameters of a request by the names a `filter` or a `sort` may write.

    A parameter's own name, or its name after its dataset (`climate_summary_wind_gust_max`), which is how the wide
    shape names a column when the request spans several datasets.

    `lookup` maps a name in lower case to the parameters it can mean, each with the name as it is written in the
    answer: one for a name that is unambiguous, several where the same name is in two datasets (then only the name
    with its dataset says which). In a request of one dataset a parameter's own name is the one the answer writes, so
    it wins over the name after the dataset of another parameter that spells the same
    (`water_equivalent_snow_depth` is a parameter of `water_equivalent`, and `snow_depth` after its dataset).
    `resolutions` are those of all the parameters of the request, since a timestamp is
    only the same instant within one of them. Names with a sign other than a letter, digit or underscore (some of a
    provider's own, with `humanize=false`) cannot be written in the text and are `unwritable`.
    """

    lookup: Mapping[str, tuple[tuple[str, ParameterColumn], ...]] = field(default_factory=dict, compare=False)
    resolutions: tuple[str, ...] = ()
    unwritable: tuple[str, ...] = ()
    #: the bare names, in the order of the request, for the text of a refusal
    listed: tuple[str, ...] = ()

    @classmethod
    def of(
        cls,
        parameters: Iterable[ParameterModel],
        *,
        humanize: bool,
    ) -> ParameterNames:
        """Build the names of a request from its parameters, named as the answer names them (`humanize`)."""
        parameters = list(parameters)
        spans_datasets = len({parameter.dataset.name.lower() for parameter in parameters}) > 1
        columns: dict[tuple[str, str, str], tuple[str, ParameterColumn]] = {}
        for parameter in parameters:
            name = parameter.name if humanize else parameter.name_original
            dataset = parameter.dataset.name.lower()
            resolution = parameter.dataset.resolution.name
            wide = f"{dataset}_{name}" if spans_datasets else name
            columns.setdefault(
                (resolution, dataset, name),
                (name, ParameterColumn(resolution, dataset, name, wide)),
            )
        found: dict[str, dict[ParameterColumn, tuple[str, bool]]] = {}
        unwritable: list[str] = []
        for (_, dataset, _), (name, column) in columns.items():
            if not _name_like(name):
                unwritable.append(name)
                continue
            for written, bare in ((name, True), (f"{dataset}_{name}", False)):
                found.setdefault(written.lower(), {}).setdefault(column, (written, bare))
        lookup: dict[str, tuple[tuple[str, ParameterColumn], ...]] = {}
        for key, each in found.items():
            entries = list(each.items())
            if not spans_datasets and any(bare for _, (_, bare) in entries):
                entries = [(column, spelled) for column, spelled in entries if spelled[1]]
            lookup[key] = tuple((spelled[0], column) for column, spelled in entries)
        resolutions = tuple(dict.fromkeys(resolution for resolution, _, _ in columns))
        listed = tuple(dict.fromkeys(name for name, _ in columns.values() if _name_like(name)))
        return cls(lookup, resolutions, tuple(dict.fromkeys(unwritable)), listed)

    def column(self, written: str) -> ParameterColumn:
        """Give the parameter a name as `find` returned it stands for."""
        return next(column for name, column in self.lookup[written.lower()] if name == written)

    def close_to(self, word: str) -> list[str]:
        """Give the names of the request that look like a word that is none, the closest first, a parameter once."""
        close = difflib.get_close_matches(word.lower()[:60], list(self.lookup), n=_CLOSEST * 2, cutoff=0.5)
        seen: dict[ParameterColumn, str] = {}
        for key in close:
            for written, column in self.lookup[key]:
                seen.setdefault(column, written)
        return list(seen.values())[:_CLOSEST]

    def distinct_spellings(self, hits: Sequence[tuple[str, ParameterColumn]]) -> list[str]:
        """Give for each parameter a name may mean a spelling that means that one only: with its dataset, else bare."""
        spellings = []
        for _, column in hits:
            for spelling in (f"{column.dataset}_{column.parameter}", column.parameter):
                if len(self.lookup.get(spelling.lower(), ())) == 1:
                    spellings.append(spelling)
                    break
        return spellings

    def describe(self) -> str:
        """Write some of the request's names for a refusal: all of them where they are few."""
        shown = self.listed[:_LISTED_NAMES]
        more = len(self.listed) - len(shown)
        return ", ".join(shown) + (f" and {more} more" if more > 0 else "")


class RowSelectionError(RequestError):
    """A `filter`, `sort`, `first` or `by` that cannot be read, as the one error of the parser.

    A `RequestError` (a `ValueError`), so a Python caller catches it as the other refusals of a request, the REST API
    and the MCP tools answer it as a 422 located at the option and the command line as a usage error. `option` names
    the option, `position` is the 1-based character of its text where the text goes wrong (None for a refusal that is
    not about one character), `found` what is there and `expected` what is allowed there. It is raised for the text
    alone, and for a name that is none of the request's parameters or is the name of several of them, once the request
    is known: the REST API answers that one as a 422 too, located at the option.
    """

    def __init__(
        self,
        option: str,
        problem: str,
        *,
        position: int | None = None,
        found: str | None = None,
        expected: str | None = None,
        hint: str | None = None,
    ) -> None:
        """Build the message from the parts, which stay on the exception as attributes."""
        self.option = option
        self.position = position
        self.found = found
        self.expected = expected
        self.hint = hint
        where = f" at position {position}" if position is not None else ""
        parts = [f"Invalid `{option}`{where}: {problem}"]
        if found is not None:
            parts[0] += f"; found {found}"
        if expected is not None:
            parts[0] += f", expected {expected}"
        parts[0] += "."
        if hint:
            hint = hint[0].upper() + hint[1:]
            parts.append(hint if hint.endswith((".", ")")) else f"{hint}.")
        super().__init__(" ".join(parts))


class RowsOverLimitError(RequestError):
    """The rows chosen so far are more than the reader may hold, and the groups say none of them will go.

    Raised by `TimeseriesValues.all` when its caller set a limit on the rows it holds (the REST API does, to the limit
    of an answer), as soon as a selection whose groups stay in a station has chosen more than that: nothing a later
    station reads can take them back. `rows` is how many were chosen so far, `maximum` the limit.
    """

    def __init__(self, rows: int, maximum: int) -> None:
        """Name the rows chosen so far and the limit."""
        self.rows = rows
        self.maximum = maximum
        super().__init__(f"The options chose {rows:,} rows so far, more than the {maximum:,} that may be held.")


def _refusal(
    option: str,
    problem: str,
    *,
    position: int | None = None,
    found: str | None = None,
    expected: str | None = None,
    hint: str | None = None,
) -> RowSelectionError:
    """Build the error of an option, to be raised: the text of each is written where it is raised."""
    return RowSelectionError(option, problem, position=position, found=found, expected=expected, hint=hint)


class RowSelectionRefusedError(RequestError):
    """A selection that is well written and cannot be applied to this request: say what to change.

    The text is not at fault but the request it goes with: `value` over parameters in different units, `value` in the
    wide shape, a grouping `query` cannot give. A `RequestError`, answered as a 400 (the options are fine, the request
    as a whole is not).
    """


def _show(text: str, position: int) -> str:
    """Quote what is at a 1-based position of a text for a message: the character, or the end of the text."""
    return repr(text[position - 1]) if position <= len(text) else "the end of the text"


def _check_text(option: str, text: str, maximum: int) -> None:
    """Refuse a text that is empty, too long or has a character outside printable ASCII, before it is scanned."""
    if not text.strip():
        raise _refusal(option, "the text is empty", hint="leave the option out for none")
    if len(text) > maximum:
        raise _refusal(
            option,
            f"the text has {len(text):,} characters, more than the {maximum} allowed",
            hint="shorten it; a list `a|b|c` of numbers or fewer conditions does the same",
        )
    for index, char in enumerate(text, start=1):
        if not (" " <= char <= "~" or char == "\t"):
            raise _refusal(
                option,
                "a character that is not plain ASCII",
                position=index,
                found=repr(char),
                expected="letters, digits and the signs `, | < > = ! - .`",
                hint="write numbers with a point and no unit or thousands separator",
            )


@dataclass(frozen=True)
class Condition:
    """One condition of a `filter`: a column, an operator and the number or the list of numbers it is compared with."""

    column: str
    operator: Operator
    values: tuple[int | float, ...]

    def text(self) -> str:
        """Write the condition as the parser reads it."""
        return f"{self.column}{self.operator}{'|'.join(_number_text(number) for number in self.values)}"


def _number_text(number: float) -> str:
    """Write a number as the parser reads it: a whole one without a point (`-20`), another as its shortest text."""
    if isinstance(number, float) and number.is_integer() and abs(number) < 1e15:
        return str(int(number))
    return str(number) if isinstance(number, int) else repr(number)


@dataclass(frozen=True)
class SortKey:
    """One key of a `sort`: a column and the direction."""

    column: str
    descending: bool

    def text(self) -> str:
        """Write the key as the parser reads it."""
        return f"-{self.column}" if self.descending else self.column


class _Scanner:
    """Read a text by hand, one character at a time: no regular expression, no backtracking, linear."""

    def __init__(self, option: str, text: str) -> None:
        self.option = option
        self.text = text
        self.index = 0

    @property
    def position(self) -> int:
        """The 1-based position of the next character."""
        return self.index + 1

    def peek(self) -> str:
        """Give the next character, an empty string at the end."""
        return self.text[self.index] if self.index < len(self.text) else ""

    def skip_blanks(self) -> None:
        """Pass spaces and tabs."""
        while self.index < len(self.text) and self.text[self.index] in " \t":
            self.index += 1

    def digits(self) -> int:
        """Pass ASCII digits and give how many there were."""
        start = self.index
        while self.index < len(self.text) and self.text[self.index] in _DIGITS:
            self.index += 1
        return self.index - start

    def word(self) -> str:
        """Read letters, digits and underscores."""
        start = self.index
        while self.index < len(self.text) and self.text[self.index] in _WORD:
            self.index += 1
        return self.text[start : self.index]

    def fail(
        self,
        problem: str,
        *,
        expected: str,
        hint: str | None = None,
        at: int | None = None,
        found: str | None = None,
    ) -> RowSelectionError:
        """Build the error for the text at `at` (the next character by default), `found` where that is a token."""
        position = at if at is not None else self.position
        return RowSelectionError(
            self.option,
            problem,
            position=position,
            found=found if found is not None else _show(self.text, position),
            expected=expected,
            hint=hint,
        )


def _unknown_column(
    scanner: _Scanner,
    word: str,
    allowed: Sequence[str],
    start: int,
    example: str,
    names: ParameterNames | None = None,
) -> RowSelectionError:
    """Build the refusal of a column that is none of the option's and, where the request is known, no parameter."""
    hints = [_COLUMN_HINTS.get(f"{scanner.option}:{word.lower()}") or _COLUMN_HINTS.get(word.lower())]
    expected = f"one of {', '.join(allowed)}"
    if names is not None and names.listed and scanner.option in ("filter", "sort"):
        expected += f", or a parameter of this request ({names.describe()})"
        close = names.close_to(word) if _name_like(word) and word.lower() not in RESERVED_WORDS else []
        if close:
            hints.insert(0, f"did you mean {' or '.join(close)}?")
        if names.unwritable:
            hints.append(
                f"{len(names.unwritable)} parameter(s) of this request have a name with a sign that cannot be written "
                "here (`humanize=false`); ask for the humanised names"
            )
    hints.append(example)
    text = " ".join(h if h.endswith((".", "?", ")")) else f"{h}." for h in hints if h)
    return scanner.fail(
        f"`{word}` is not a column of this option" if word else "no column",
        expected=expected,
        hint=text,
        at=start,
        found=repr(word[:40]) if word else None,
    )


def _name_column(
    scanner: _Scanner,
    word: str,
    allowed: Sequence[str],
    start: int,
    example: str,
    names: ParameterNames | None,
) -> str:
    """Read a word that is no column of the option as the name of a parameter, and give the name it is written as.

    Without the request's names (`names` is None: the model of a REST request, the check of the command line) any
    word that can be a name is accepted and left as written in lower case, to be looked up when the request is
    known. With them the word must be one of them, in either case: its name as the answer writes it comes back, and
    a name the request has twice, in two datasets, is refused with the name that says which.
    """
    lower = word.lower()
    if lower in RESERVED_WORDS or not _name_like(word):
        raise _unknown_column(scanner, word, allowed, start, example, names)
    if names is None:
        return lower
    hits = names.lookup.get(lower, ())
    if len(hits) == 1:
        return hits[0][0]
    if not hits:
        raise _unknown_column(scanner, word, allowed, start, example, names)
    if len(names.resolutions) > 1:
        # the same name at two resolutions is the lesser fault: a request of two resolutions has no names at all
        raise _resolutions_refusal(names)
    spellings = names.distinct_spellings(hits)
    shown = ", ".join(spellings[:_LISTED_NAMES]) + (
        f" and {len(spellings) - _LISTED_NAMES} more" if len(spellings) > _LISTED_NAMES else ""
    )
    datasets = dict.fromkeys(column.dataset for _, column in hits)
    where = ", ".join(list(datasets)[:_LISTED_NAMES]) + (
        f" and {len(datasets) - _LISTED_NAMES} more" if len(datasets) > _LISTED_NAMES else ""
    )
    raise scanner.fail(
        f"`{word}` is the name of {len(hits)} parameters of this request",
        expected="a name that says which, as the wide shape writes it after the dataset: "
        + (shown or "none is unique"),
        hint=f"the datasets are {where}",
        at=start,
        found=repr(word),
    )


def _read_number(scanner: _Scanner, column: str) -> int | float:  # noqa: C901
    """Read one number of a condition: `-20`, `0.5`, `1e3`, `2e-3`; a whole number for a calendar column."""
    start = scanner.position
    begin = scanner.index
    if scanner.peek() == "+":
        raise scanner.fail(
            "a plus sign",
            expected="a number without a sign or with a minus",
            hint="write 5, not +5 (a `+` in a URL is read as a space)",
        )
    if scanner.peek() == "-":
        scanner.index += 1
    if not scanner.digits():
        raise scanner.fail(
            "no number",
            expected="a number such as -20, 0.5 or 1e3",
            hint="Not numbers: nan, inf, names and units. Write the number alone, in the unit of the values",
        )
    fraction = False
    if scanner.peek() == ".":
        scanner.index += 1
        if not scanner.digits():
            raise scanner.fail("a point with no digits after it", expected="digits, as in 0.5")
        fraction = True
    if scanner.peek() in ("e", "E"):
        scanner.index += 1
        fraction = True
        if scanner.peek() == "-":
            scanner.index += 1
        if not scanner.digits():
            raise scanner.fail("an exponent with no digits", expected="digits, as in 1e3 or 2e-3")
    token = scanner.text[begin : scanner.index]
    if len(token) > MAX_NUMBER_LENGTH:
        raise scanner.fail(
            f"the number has {len(token)} characters, more than the {MAX_NUMBER_LENGTH} allowed",
            expected="a shorter number",
            at=start,
        )
    if column in _CALENDAR_RANGE:
        if fraction:
            raise scanner.fail(
                f"`{column}` is a whole number",
                expected="a whole number",
                hint=f"write {column}=7, not {token}",
                at=start,
                found=repr(token),
            )
        number = int(token)
        low, high = _CALENDAR_RANGE[column]
        if not low <= number <= high:
            raise scanner.fail(
                f"{token} is outside the range of `{column}`",
                expected=f"a number from {low} to {high}",
                at=start,
                found=repr(token),
            )
        return number
    value = float(token)
    if not math.isfinite(value) or abs(value) > _MAX_VALUE:
        raise scanner.fail(
            f"{token} is too large", expected=f"a magnitude of at most {_MAX_VALUE:g}", at=start, found=repr(token)
        )
    return value


def parse_filter(text: str, names: ParameterNames | None = None) -> tuple[Condition, ...]:
    """Read a `filter` text into its conditions, joined by `,`, or raise `RowSelectionError`.

    Spaces and tabs between tokens are ignored; column names and `e` of an exponent are read in either case. A column
    may be named twice (`value>=-20,value<=-10` is a range, `month=12,month=1` is an empty answer, not an error).
    A word that is no column of the option is a parameter's name: `names` are the request's, which it must be one of;
    without them it is accepted if it can be a name (see `_name_column`).
    """
    _check_text("filter", text, MAX_FILTER_LENGTH)
    scanner = _Scanner("filter", text)
    conditions: list[Condition] = []
    while True:
        if len(conditions) >= MAX_CONDITIONS:
            raise scanner.fail(
                f"more than {MAX_CONDITIONS} conditions",
                expected="at most 8 conditions; a list `a|b` joins values of one column",
                at=min(scanner.position, len(text) + 1),
            )
        scanner.skip_blanks()
        start = scanner.position
        word = scanner.word()
        column = word.lower()
        if column not in FILTER_COLUMNS:
            column = _name_column(scanner, word, FILTER_COLUMNS, start, _FILTER_EXAMPLE, names)
        scanner.skip_blanks()
        operator = _read_operator(scanner)
        scanner.skip_blanks()
        values = [_read_number(scanner, column)]
        scanner.skip_blanks()
        while scanner.peek() == "|":
            if operator not in ("=", "!="):
                raise scanner.fail(
                    f"a list `|` after `{operator}`",
                    expected="`,` or the end of the text",
                    hint="a list goes with `=` and `!=` only; for a range write two conditions: value>=-20,value<=-10",
                )
            scanner.index += 1
            scanner.skip_blanks()
            if len(values) >= MAX_LIST_ITEMS:
                raise scanner.fail(
                    f"a list of more than {MAX_LIST_ITEMS} numbers",
                    expected="at most 32 numbers in a list",
                )
            values.append(_read_number(scanner, column))
            scanner.skip_blanks()
        conditions.append(Condition(column, operator, tuple(values)))
        if scanner.peek() == ",":
            scanner.index += 1
            scanner.skip_blanks()
            if not scanner.peek():
                raise scanner.fail("a comma with no condition after it", expected="a condition", hint=_FILTER_EXAMPLE)
            continue
        if scanner.peek():
            raise scanner.fail(
                "something after the number",
                expected="`,` for the next condition, `|` for another number, or the end of the text",
                hint=("a unit or a word after the number is not read; " if scanner.peek().isalpha() else "")
                + _FILTER_EXAMPLE,
            )
        return tuple(conditions)


def _read_operator(scanner: _Scanner) -> Operator:
    """Read the operator of a condition: the longest of `<= >= != < > =`, or refuse what is written instead."""
    for operator in _OPERATORS:
        if scanner.text.startswith(operator, scanner.index):
            scanner.index += len(operator)
            following = scanner.text[scanner.index : scanner.index + 1]
            if following in ("=", "<", ">"):
                pair = operator + following
                raise scanner.fail(
                    f"`{pair}` is not an operator",
                    expected="one of = != < <= > >=",
                    hint=_OPERATOR_HINTS.get(pair, "write one operator"),
                    at=scanner.position - len(operator),
                )
            return operator
    char = scanner.peek()
    raise scanner.fail(
        "no operator after the column" if char else "the condition ends after the column",
        expected="one of = != < <= > >=",
        hint=_OPERATOR_HINTS.get(char, "a condition is a column, an operator and a number: value<=-20"),
    )


def _split(option: str, text: str, maximum: int) -> list[tuple[str, int]]:
    """Cut a `sort` or `by` text at its commas, each part with the 1-based position of its first character."""
    _check_text(option, text, maximum)
    parts: list[tuple[str, int]] = []
    start = 0
    for index, char in enumerate([*text, ","]):
        if char == ",":
            parts.append((text[start:index], start + 1))
            start = index + 1
    return parts


def parse_sort(text: str, names: ParameterNames | None = None) -> tuple[SortKey, ...]:
    """Read a `sort` text into its keys, or raise `RowSelectionError`: columns joined by `,`, `-` for descending.

    A word that is no column of the option is a parameter's name, read as `parse_filter` reads it.
    """
    scanner = _Scanner("sort", text)
    keys: list[SortKey] = []
    for part, position in _split("sort", text, MAX_ORDER_LENGTH):
        stripped = part.strip(" \t")
        offset = position + (len(part) - len(part.lstrip(" \t")))
        descending = stripped.startswith("-")
        word = stripped[1:].strip(" \t") if descending else stripped
        column = word.lower()
        if column not in SORT_COLUMNS:
            column = _name_column(scanner, word, SORT_COLUMNS, offset + (1 if descending else 0), _SORT_EXAMPLE, names)
        if any(key.column == column for key in keys):
            raise scanner.fail(
                f"`{column}` is named twice",
                expected="each column once",
                hint=_SORT_EXAMPLE,
                at=offset,
            )
        keys.append(SortKey(column, descending))
    return tuple(keys)


def parse_by(text: str) -> tuple[str, ...]:
    """Read a `by` text into its columns, or raise `RowSelectionError`; `none` is the empty tuple (all stations)."""
    scanner = _Scanner("by", text)
    columns: list[str] = []
    for part, position in _split("by", text, MAX_ORDER_LENGTH):
        word = part.strip(" \t")
        offset = position + (len(part) - len(part.lstrip(" \t")))
        column = word.lower()
        if column == "none":
            if len(columns) > 0 or len(text.split(",")) > 1:
                raise scanner.fail(
                    "`none` together with other columns",
                    expected="`none` alone, or columns without it",
                    hint=_BY_EXAMPLE,
                    at=offset,
                )
            return ()
        if column not in BY_COLUMNS:
            raise _unknown_column(scanner, word, (*BY_COLUMNS, "none"), offset, _BY_EXAMPLE)
        if column in columns:
            raise scanner.fail(f"`{column}` is named twice", expected="each column once", hint=_BY_EXAMPLE, at=offset)
        columns.append(column)
    return tuple(columns)


def _read_count(option: str, value: object, maximum: int, hint: str, large: str) -> int:
    """Read a count option: a whole number from 1 to `maximum`; a text of digits is read as the number it writes."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise _refusal(option, "not a whole number", found=repr(value), expected="a whole number from 1")
    if isinstance(value, str):
        text = value.strip(" \t")
        if not text.isascii() or not text.isdigit():
            raise _refusal(
                option,
                "not a whole number",
                found=repr(value)[:40],
                expected=f"a whole number from 1 to {maximum}",
                hint=f"Example: {option}=1",
            )
        if len(text) > 12:
            raise _refusal(option, "too large", expected=f"a whole number from 1 to {maximum}")
        value = int(text)
    if not 1 <= value <= maximum:
        raise _refusal(
            option,
            f"{value} is outside the range allowed",
            expected=f"a whole number from 1 to {maximum}",
            hint=hint if value > maximum else large,
        )
    return value


def read_first(first: object) -> int:
    """Read `first`: a whole number from 1 to `MAX_FIRST`; a text of digits is read as the number it writes."""
    return _read_count(
        "first",
        first,
        MAX_FIRST,
        "for more rows ask for all of them and read them from a stream (format=ndjson), or use `filter`",
        "`first` is at least 1",
    )


def read_max_rows(max_rows: object) -> int:
    """Read `max_rows`: a whole number from 1 to `MAX_MAX_ROWS`; a text of digits is read as the number it writes."""
    return _read_count(
        "max_rows",
        max_rows,
        MAX_MAX_ROWS,
        "for more rows leave `max_rows` out and read the answer from a stream (format=ndjson), or use `filter`",
        "`max_rows` is at least 1",
    )


@dataclass(frozen=True)
class RowSelection:
    """The rows an answer is about: what `filter`, `sort`, `first` and `by` say, read and checked.

    Build one with `parse_row_selection`; it is immutable and holds no frame. `reduce_station` applies it to the frame
    of one station as the values are read, and `finish` joins the reduced frames and puts the rows in the order
    the answer has. `apply` is the same for a frame that is held whole.
    """

    conditions: tuple[Condition, ...] = ()
    sort: tuple[SortKey, ...] = ()
    first: int | None = None
    #: None: the default group, the station; the empty tuple: all stations
    by: tuple[str, ...] | None = None
    #: the most rows of the whole answer, the last step: after `filter`, `sort` and `first`; None for no cap
    max_rows: int | None = None
    #: the parameters the conditions and the keys name, each by the name it is written as in them (the name as the
    #: answer writes it) and the parameter it stands for, in the order they are first written: empty where none is
    names: tuple[tuple[str, ParameterColumn], ...] = ()

    @property
    def by_names(self) -> bool:
        """Whether a parameter is named: a row of the choice is then a timestamp of a station, not one reading."""
        return bool(self.names)

    @property
    def groups(self) -> tuple[str, ...]:
        """The columns a group of `first` is made of besides the series: the station unless `by` says otherwise."""
        return DEFAULT_BY if self.by is None else self.by

    @property
    def per_station(self) -> bool:
        """Whether a station's rows are all that decide which of them are kept: `first` groups never span stations."""
        return self.first is None or "station_id" in self.groups

    @property
    def uses_value(self) -> bool:
        """Whether the selection looks at the value of a row, which a wide frame has in a column per parameter."""
        return any(c.column == "value" for c in self.conditions) or any(k.column == "value" for k in self.sort)

    @property
    def orders(self) -> bool:
        """Whether the answer is put in an order of its own: it is when `sort` is given, else it is as it was read."""
        return bool(self.sort)

    def echo(self) -> dict[str, str | int | None]:
        """Give the options as the parser read them, the way a report names them."""
        return {
            "filter": ",".join(c.text() for c in self.conditions) or None,
            "sort": ",".join(k.text() for k in self.sort) or None,
            "first": self.first,
            "by": None if self.by is None else (",".join(self.by) or "none"),
            "max_rows": self.max_rows,
        }

    def refuse_for(self, parameters: Sequence[ParameterModel], symbols: Callable[[ParameterModel], str]) -> None:
        """Refuse a `value` condition over parameters whose values are not in one unit, naming how to ask.

        `symbols` gives the unit a parameter's values come back in. `value<=-20` over a temperature and a wind speed
        compares degrees with metres per second; the groups of `first` are one parameter each, so `sort=value` is
        fine, but a condition has one number for all of them.
        """
        if not any(c.column == "value" for c in self.conditions):
            return
        units: dict[str, str] = {}
        for parameter in parameters:
            units.setdefault(symbols(parameter), parameter.name)
        if len(units) > 1:
            listed = "; ".join(f"{name} in {unit}" for unit, name in units.items())
            raise RowSelectionRefusedError(
                "A `filter` on `value` has one number for every parameter of the request, which are not in one unit "
                f"({listed}). Name one parameter in `parameters`, e.g. daily/climate_summary/temperature_air_min_2m, "
                "or filter on `year`, `month`, `day` or `hour` only."
            )

    def refuse_wide(self) -> None:
        """Refuse a selection of `value` in the wide shape, where a row holds one column per parameter."""
        if self.uses_value:
            raise RowSelectionRefusedError(
                "`value` is not available in the wide shape, where a row has one column per parameter and no `value`. "
                "Name the parameter instead (temperature_air_min_2m<0), ask with shape=long, or use `year`, `month`, "
                "`day` and `hour` only."
            )

    def _derived(self, frame: pl.DataFrame, columns: Sequence[str]) -> tuple[pl.DataFrame, dict[str, str]]:
        """Add the calendar parts the selection reads to a frame as columns of their own, by the column's name."""
        import polars as pl  # noqa: PLC0415

        names = {name: f"_row_{name}" for name in dict.fromkeys(columns) if name in _CALENDAR_RANGE}
        if not names:
            return frame, {}
        stamp = pl.col("timestamp")
        parts = {"year": stamp.dt.year(), "month": stamp.dt.month(), "day": stamp.dt.day(), "hour": stamp.dt.hour()}
        return frame.with_columns(parts[name].alias(alias) for name, alias in names.items()), names

    def _condition(self, condition: Condition, names: dict[str, str]) -> pl.Expr:
        import polars as pl  # noqa: PLC0415

        column = pl.col(names.get(condition.column, condition.column))
        values = list(condition.values)
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
        # a missing value never matches: not `!=` either, which the comparison with a null does not answer
        return expr.fill_null(value=False) & column.is_not_null()

    def _names_of(self, columns: Iterable[str]) -> list[str]:
        """Give those of some columns that name a parameter, once each, in the order given."""
        bound = dict(self.names)
        return [column for column in dict.fromkeys(columns) if column in bound]

    def _timestamp_rows(
        self, frame: pl.DataFrame, needed: Sequence[str]
    ) -> tuple[pl.DataFrame, dict[str, str], list[str]]:
        """Give the timestamps of a frame as rows, with the value of each parameter named in `needed` in a column.

        A timestamp of a station and a resolution is one row, however many parameters the long frame has a reading of
        there: the columns are made from the rows of the named parameters only (a left join of each on the stamps
        of all of them), so what is held is as wide as the names are, not as the request is. A wide frame has its
        timestamps as rows already and the parameters as columns, which a station that delivers fewer than the request
        asks for lacks: those are added as missing, and the columns added are returned to be dropped. Without a name
        the stamps of the frame are the rows. Gives the rows, the column of each name and the columns added.
        """
        import polars as pl  # noqa: PLC0415

        bound = dict(self.names)
        wanted = list(dict.fromkeys(needed))
        if "parameter" not in frame.columns:
            lacking = list(dict.fromkeys(bound[n].wide for n in wanted if bound[n].wide not in frame.columns))
            keyed = (
                frame.with_columns(pl.lit(None, pl.Float64).alias(column) for column in lacking) if lacking else frame
            )
            return keyed, {name: bound[name].wide for name in wanted}, lacking
        keys = list(_STAMP_KEYS)
        if not wanted:
            return frame.select(keys).unique(maintain_order=True), {}, []
        columns = list(dict.fromkeys(bound[name] for name in wanted))

        def of(column: ParameterColumn) -> pl.Expr:
            return (
                (pl.col("resolution") == column.resolution)
                & (pl.col("dataset") == column.dataset)
                & (pl.col("parameter") == column.parameter)
            )

        rows = frame.filter(pl.any_horizontal(of(column) for column in columns))
        keyed = rows.select(keys).unique(maintain_order=True)
        labels: dict[ParameterColumn, str] = {}
        for index, column in enumerate(columns):
            labels[column] = f"_row_name_{index}"
            part = (
                rows.filter(of(column))
                .select(*keys, pl.col("value").alias(labels[column]))
                .unique(subset=keys, keep="first", maintain_order=True)
            )
            keyed = keyed.join(part, on=keys, how="left", maintain_order="left")
        return keyed, {name: labels[bound[name]] for name in wanted}, []

    @staticmethod
    def _rows_of(frame: pl.DataFrame, chosen: pl.DataFrame, drop: Sequence[str]) -> pl.DataFrame:
        """Give the rows of a frame at the timestamps `chosen` holds, in the order the frame has them.

        A wide frame is its own timestamps: the chosen rows, without the columns that were added to judge them. A long
        frame has the rows of every parameter at a chosen timestamp, which are all of them the answer's.
        """
        if "parameter" not in frame.columns:
            return chosen.drop(drop)
        return frame.join(chosen.select(*_STAMP_KEYS), on=list(_STAMP_KEYS), how="semi", maintain_order="left")

    def filtered(self, frame: pl.DataFrame) -> pl.DataFrame:
        """Keep the rows that meet every condition of `filter`; the order of the rows is kept.

        A condition on a parameter's name is judged on a timestamp of a station, and meets it where that parameter
        has a value there; all the conditions must hold at one timestamp, and the rows kept are those of every
        parameter at it (a long frame) or the timestamp's row (a wide one).
        """
        import polars as pl  # noqa: PLC0415

        if not self.conditions:
            return frame
        named = self._names_of(c.column for c in self.conditions)
        if not named:
            work, names = self._derived(frame, [c.column for c in self.conditions])
            kept = work.filter(pl.all_horizontal(self._condition(c, names) for c in self.conditions))
            return kept.drop(names.values()) if names else kept
        keyed, labels, added = self._timestamp_rows(frame, named)
        work, derived = self._derived(keyed, [c.column for c in self.conditions])
        lookup = {**derived, **labels}
        kept = work.filter(pl.all_horizontal(self._condition(c, lookup) for c in self.conditions))
        return self._by_timestamp(self._rows_of(frame, kept, [*derived.values(), *added]))

    def _by_timestamp(self, frame: pl.DataFrame) -> pl.DataFrame:
        """Order the rows of a long frame chosen by names, where no `sort` orders them: station, then time.

        The plain answer is in series order (a parameter, then its time), so a cut of it (`max_rows`, the budget of a
        tool) keeps the first parameter's rows and none of the others', which with names would leave the answer
        without the values the conditions were about. Within a station the rows are ordered by resolution, timestamp,
        dataset and parameter, the stations stay in the order they came in. A wide frame is in the order of its
        timestamps already, and a `sort` orders it as it says (`ordered`).
        """
        import polars as pl  # noqa: PLC0415

        if self.orders or "parameter" not in frame.columns or frame.is_empty():
            return frame
        # the rows of a station are together, as every frame the reader or a result holds has them
        block = pl.col("station_id").rle_id().alias("_row_station")
        by = ["_row_station", "resolution", "timestamp", "dataset", "parameter"]
        return frame.with_columns(block).sort(by, maintain_order=True).drop("_row_station")

    def _series(self, frame: pl.DataFrame) -> list[str]:
        """Give the columns that name the series of a frame: a wide one has no parameter."""
        return [name for name in ("resolution", "dataset", "parameter") if name in frame.columns]

    def _first(self, frame: pl.DataFrame) -> pl.DataFrame:
        """Keep the first `first` rows of every group in the `sort` order, with the rows that tie with the last one.

        With a parameter named, a row is a timestamp of a station (its readings are the long frame's rows at it) and
        the group is a resolution and the columns of `by`: the timestamps are ranked and the rows of those kept are
        given back. See `_first_of`.
        """
        if frame.is_empty() or not self.by_names:
            return self._first_of(frame, {})
        keyed, labels, added = self._timestamp_rows(frame, self._names_of(k.column for k in self.sort))
        return self._rows_of(frame, self._first_of(keyed, labels), added)

    def _first_of(self, frame: pl.DataFrame, labels: dict[str, str]) -> pl.DataFrame:
        """Keep the first `first` rows of every group in the `sort` order, with the rows that tie with the last one.

        A group is one series and the columns of `by`. A row is kept when fewer than `first` rows of its group sort
        strictly before it, so the ties of the last row kept are all kept. A row whose sort column is null has no
        place in the order and is not kept. `labels` are the columns of the parameters the keys name, where a key does.

        Done in one sort and a few passes over the rows, none of them a window over the groups (which costs more than
        linear when the groups are many): sorted by the group and then by the keys, a row starts a group where a group
        column differs from the row before it, and starts a run of ties where a sort column does; the number of rows
        of its group before the first row of its run is what is compared with `first`.
        """
        import polars as pl  # noqa: PLC0415

        assert self.first is not None  # noqa: S101
        if frame.is_empty():
            return frame
        columns = [key.column for key in self.sort] + list(self.groups)
        work, derived = self._derived(frame, columns)
        names = {**derived, **labels}
        sort_columns = [names.get(key.column, key.column) for key in self.sort]
        groups = self._series(work) + [names.get(column, column) for column in self.groups]
        ranked = work.drop_nulls(subset=sort_columns).sort(
            [*groups, *sort_columns],
            descending=[False] * len(groups) + [key.descending for key in self.sort],
            maintain_order=True,
            nulls_last=True,
        )
        row = pl.int_range(pl.len())
        first_row = row == 0
        starts_group = pl.any_horizontal([pl.col(c).ne_missing(pl.col(c).shift(1)) for c in groups]) | first_row
        starts_run = starts_group | pl.any_horizontal([pl.col(c).ne_missing(pl.col(c).shift(1)) for c in sort_columns])
        group_start = pl.when(starts_group).then(row).otherwise(None).forward_fill()
        run_start = pl.when(starts_run).then(row).otherwise(None).forward_fill()
        kept = ranked.filter(run_start - group_start < self.first)
        return kept.drop(derived.values()) if derived else kept

    def reduce_station(self, frame: pl.DataFrame) -> pl.DataFrame:
        """Apply the selection to the rows of one station (or to any frame): `filter`, then `first` within the groups.

        The rows come back in the order they had, but those of `first`, which come back in the `sort` order. What
        remains to do for a frame of several stations is `finish`: the groups of `by` that span stations, and the
        order of the answer.
        """
        frame = self.filtered(frame)
        if self.first is not None:
            frame = self._first(frame)
        return frame

    def finish(self, frames: Sequence[pl.DataFrame], schema: pl.Schema | None = None) -> pl.DataFrame:
        """Join the reduced frames of the stations and settle the groups that span stations and the order.

        Where a group of `first` spans stations, the first rows of the whole group are among the first rows of its
        parts, ties included (a row with fewer than `first` rows of the group before it has fewer of its station's),
        so `first` is applied again to the joined frames. Then, if `sort` is given, the rows are ordered by series, the
        sort keys, the station and the timestamp, which fully determines the order.
        """
        import polars as pl  # noqa: PLC0415

        frame = pl.concat(list(frames), how="diagonal") if frames else pl.DataFrame(schema=schema)
        if self.first is not None and not self.per_station:
            frame = self._first(frame)
        return self.ordered(frame) if self.orders else frame

    def ordered(self, frame: pl.DataFrame) -> pl.DataFrame:
        """Put the rows in the order of `sort`: by series, then the keys, and the station and timestamp after them.

        The sort is stable, the keys are the columns the user named in the direction they named, a null comes last,
        and the series, the station and the timestamp make the order the same for every run, whatever the order the
        stations came in. With a parameter named a long frame has no series of its own to go by: a row is a timestamp,
        so the order is the resolution, the keys, the station, the timestamp, and then the rows at one timestamp by
        dataset and parameter; a parameter used as a key is the value it has at the row's timestamp (null where it has
        none, which comes last).
        """
        if frame.is_empty():
            return frame
        columns = [key.column for key in self.sort]
        by_stamp = self.by_names and "parameter" in frame.columns
        work, helpers, added = frame, {}, []
        if named := self._names_of(columns):
            keyed, helpers, added = self._timestamp_rows(frame, named)
            if "parameter" in frame.columns:
                labels = list(dict.fromkeys(helpers.values()))
                work = frame.join(
                    keyed.select(*_STAMP_KEYS, *labels), on=list(_STAMP_KEYS), how="left", maintain_order="left"
                )
                added = labels
            else:
                work = keyed
                added = [*added]
        work, derived = self._derived(work, columns)
        lookup = {**derived, **helpers}
        series = ["resolution"] if by_stamp else self._series(work)
        tail = [name for name in ("station_id", "timestamp") if name in work.columns and name not in columns]
        if by_stamp:
            tail += [name for name in ("dataset", "parameter") if name in work.columns]
        by = series + [lookup.get(column, column) for column in columns] + tail
        descending = [False] * len(series) + [key.descending for key in self.sort] + [False] * len(tail)
        ordered = work.sort(by, descending=descending, nulls_last=True, maintain_order=True)
        drop = [*derived.values(), *added]
        return ordered.drop(drop) if drop else ordered

    def cap_station(self, frame: pl.DataFrame, *, held: bool = False) -> pl.DataFrame:
        """Cut the rows of one station to the `max_rows` that could be in the answer: its first, in the answer's order.

        Only for a selection whose groups stay in a station (`per_station`): then no row a later step could take back
        precedes the `max_rows` kept, and a station can hold no more than the answer. The count of what matched is the
        caller's, taken before. `held` is for rows that a later step goes on with (`TimeseriesValues.all`): with a
        parameter named the cut then leaves a timestamp whole (see `cap_held`); the rows of a station that `query`
        yields are cut exactly.
        """
        if self.max_rows is None:
            return frame
        frame = self.ordered(frame) if self.orders else frame
        return self.cap_held(frame) if held else self.cap(frame)

    def cap_held(self, frame: pl.DataFrame) -> pl.DataFrame:
        """Cut rows that are held for later steps to `max_rows`, as `cap` does, but never in the middle of a timestamp.

        With a parameter named a timestamp is ordered by the value that parameter has there, and a later step (the
        choice again over the stations held, the order of the whole) finds it in the rows of the timestamp: a timestamp
        cut between its rows would lose the row of that value and be put last. So the rows of every timestamp that has
        one among the first `max_rows` are kept, which are at most as many more as the request has parameters, less one.
        The answer itself is cut exactly, by `cap`, as its last step.
        """
        if self.max_rows is None:
            return frame
        head = frame.head(self.max_rows)
        if not (self.by_names and self.orders and "parameter" in frame.columns) or head.height == frame.height:
            return head
        return frame.join(head.select(*_STAMP_KEYS).unique(), on=list(_STAMP_KEYS), how="semi", maintain_order="left")

    def cap(self, frame: pl.DataFrame) -> pl.DataFrame:
        """Cut the answer to its first `max_rows` rows, in the order it has: the last step, over all stations."""
        return frame if self.max_rows is None else frame.head(self.max_rows)

    def apply(self, frame: pl.DataFrame) -> pl.DataFrame:
        """Apply the selection to a frame that holds all the rows: `reduce_station`, `finish` and `cap` in one call.

        Without the cap the rows are those that matched, which is what a report counts.
        """
        return self.cap(self.matching(frame))

    def matching(self, frame: pl.DataFrame) -> pl.DataFrame:
        """Give the rows the options choose before the cap: `reduce_station` and `finish` in one call."""
        return self.finish([self.reduce_station(frame)], schema=frame.schema)


def parse_row_selection(
    filter: str | None = None,  # noqa: A002
    sort: str | None = None,
    first: int | str | None = None,
    by: str | None = None,
    max_rows: int | str | None = None,
    parameters: ParameterNames | None = None,
) -> RowSelection | None:
    """Read the four options of a request into a `RowSelection`, None where none is given.

    An empty string is no option, as a query parameter left empty is. Besides the errors of the four texts, which
    `RowSelectionError` carries, two rules cross them: `first` needs `sort` (the first rows of what order?) and `by`
    needs `first` (a group of what?), both told with the option to add or leave out.

    `parameters` are the names of the request's parameters (`ParameterNames.of`). Given, a word of `filter` and `sort`
    that is no column must be one of them, and the selection that comes back is bound to them: it can be applied to the
    rows of that request. Not given, a word that can be a name is accepted as written, which is all a check of the text
    alone needs (the command line, the model of a REST request), and the selection is not to be applied.

    Raises:
        RowSelectionError: a text that cannot be read, or a combination that has no meaning.
        RowSelectionRefusedError: a name together with `value`, or names with a request of several resolutions.

    """
    texts = {name: value for name, value in (("filter", filter), ("sort", sort), ("by", by)) if value not in (None, "")}
    if not texts and first in (None, "") and max_rows in (None, ""):
        return None
    conditions = parse_filter(texts["filter"], parameters) if "filter" in texts else ()
    keys = parse_sort(texts["sort"], parameters) if "sort" in texts else ()
    count = read_first(first) if first not in (None, "") else None
    columns = parse_by(texts["by"]) if "by" in texts else None
    cap = read_max_rows(max_rows) if max_rows not in (None, "") else None
    if count is not None and not keys:
        raise _refusal(
            "first",
            "`first` takes the first rows of an order, and no `sort` is given",
            hint="add sort=value for the lowest, sort=-value for the highest, sort=timestamp for the earliest "
            "or sort=-timestamp for the latest (a parameter's name in place of `value` orders the timestamps by it). "
            "Example: sort=-value&first=1",
        )
    if columns is not None and count is None:
        raise _refusal(
            "by",
            "`by` names the groups `first` counts in, and no `first` is given",
            hint="add first=N, or leave `by` out. Example: sort=value&first=1&by=station_id,year",
        )
    used = _used_names(conditions, keys, parameters)
    if used:
        _check_names(conditions, keys, parameters)
    return RowSelection(conditions=conditions, sort=keys, first=count, by=columns, max_rows=cap, names=used)


def _used_names(
    conditions: Sequence[Condition], keys: Sequence[SortKey], parameters: ParameterNames | None
) -> tuple[tuple[str, ParameterColumn], ...]:
    """Give the parameters the conditions and keys name, each name once in the order it is first written."""
    if parameters is None:
        return ()
    columns = dict.fromkeys(
        column
        for column in [*(c.column for c in conditions), *(k.column for k in keys)]
        if column not in FILTER_COLUMNS and column not in SORT_COLUMNS
    )
    return tuple((column, parameters.column(column)) for column in columns)


def _check_names(conditions: Sequence[Condition], keys: Sequence[SortKey], parameters: ParameterNames | None) -> None:
    """Refuse a selection of names that cannot be applied to the request: `value` beside a name, several resolutions.

    A name stands for a parameter's value at a timestamp, so a row is a timestamp; `value` is the value of one row of
    one parameter, which has no place in the same selection. And the timestamps of two resolutions are not the same
    instants, so a request that names a parameter holds one resolution.
    """
    if any(c.column == "value" for c in conditions) or any(k.column == "value" for k in keys):
        msg = (
            "`value` and a parameter's name are in one selection. A name stands for that parameter's value at the "
            "timestamp of the row, and `value` is the value of each row of one parameter: use the names, "
            "e.g. temperature_air_min_2m<0,wind_gust_max>=17.2, and no `value`."
        )
        raise RowSelectionRefusedError(msg)
    if parameters is not None and len(parameters.resolutions) > 1:
        raise _resolutions_refusal(parameters)


def _resolutions_refusal(names: ParameterNames) -> RowSelectionRefusedError:
    """Build the refusal of a name in a request of several resolutions, whose timestamps are not the same instants."""
    shown = ", ".join(names.resolutions[:_LISTED_NAMES])
    msg = (
        "A parameter's name is a column of the timestamps of one resolution, and this request has "
        f"{len(names.resolutions)} ({shown}), whose timestamps are not the same instants. "
        "Request the parameters of one resolution."
    )
    return RowSelectionRefusedError(msg)


@dataclass(frozen=True)
class Searched:
    """What a selection looked at: per station and series the values searched, those expected and the span searched.

    One row per station and series (a station, resolution, dataset and parameter) in `series`, a frame with the columns
    `station_id`, `resolution`, `dataset`, `parameter`, `searched` (the values the selection saw: readings with a value,
    after the plausibility rules and the conversion of units), `expected` (what the request covers, see `searched_of`),
    `gaps` (what the series lacks between its first and its last value), `first` and `last` (the stamps of its first
    and last value, UTC), `matched` (the rows the options chose from it) and `returned` (the rows of the answer from it,
    fewer than `matched` where `max_rows` cut the answer). `window` is the window of the request, `selection` what was
    asked.

    The rows of the answer are counted as the frame has them: `matched_rows` and `returned_rows` are heights, which in
    the long shape are the sums of the series, and in the wide shape are not (a wide row holds every parameter of its
    resolution, so the sum over the series counts it once for each). `stations_read` is how many stations the walk read,
    those that had no value included, which the series of a station without one cannot say.
    """

    series: pl.DataFrame
    selection: RowSelection
    window: tuple[dt.datetime | None, dt.datetime | None] = (None, None)
    #: the rows of the answer
    rows: int = field(default=0)
    #: the rows the options chose, and the rows returned, as frames hold them; None where a count was not made
    matched_rows: int | None = None
    returned_rows: int | None = None
    #: the stations the walk read; None where the report was made from a result that did not walk
    stations_read: int | None = None
    #: how many series `to_dict` lists: a tool lists fewer, so that the report does not take its budget
    listed: int = MAX_REPORTED_SERIES

    @property
    def matched_total(self) -> int:
        """Give the rows that matched, as the frame counts them, else as the series add up."""
        if self.matched_rows is not None:
            return self.matched_rows
        return int(self.series.get_column("matched").sum())

    @property
    def returned_total(self) -> int:
        """Give the rows returned, as the frame counts them, else as the series add up."""
        if self.returned_rows is not None:
            return self.returned_rows
        return int(self.series.get_column("returned").sum())

    @classmethod
    def nothing(
        cls,
        selection: RowSelection,
        window: tuple[dt.datetime | None, dt.datetime | None],
        stations_read: int | None = None,
    ) -> Searched:
        """Give the report of a search that found no station with values: no series, the options and the window."""
        import polars as pl  # noqa: PLC0415

        series = pl.DataFrame(
            schema={
                "station_id": pl.String,
                "name": pl.String,
                "resolution": pl.String,
                "dataset": pl.String,
                "parameter": pl.String,
                "searched": pl.UInt32,
                "expected": pl.UInt32,
                "gaps": pl.UInt32,
                "first": pl.Datetime("us", "UTC"),
                "last": pl.Datetime("us", "UTC"),
                "matched": pl.UInt32,
                "returned": pl.UInt32,
            }
        )
        return cls(
            series=series,
            selection=selection,
            window=window,
            matched_rows=0,
            returned_rows=0,
            stations_read=stations_read,
        )

    def with_matched(self, frame: pl.DataFrame) -> Searched:
        """Count the rows of `frame`, the answer, per station and series, and give the report with them."""
        import polars as pl  # noqa: PLC0415

        keys = ["station_id", "resolution", "dataset", "parameter"]
        series = self.series.drop("matched", "returned", strict=False)
        if frame.is_empty() or "station_id" not in frame.columns:
            matched = series.with_columns(pl.lit(0, pl.UInt32).alias("matched"))
        elif "parameter" in frame.columns:
            counts = frame.group_by(keys).agg(pl.len().alias("matched"))
            matched = series.join(counts, on=keys, how="left", nulls_equal=True, maintain_order="left").with_columns(
                pl.col("matched").fill_null(0)
            )
        else:
            # a wide row holds the parameters of its resolution (and its dataset, null where it merged several)
            counts = frame.group_by("station_id", "resolution", "dataset").agg(pl.len().alias("matched"))
            exact = series.join(
                counts, on=["station_id", "resolution", "dataset"], how="left", nulls_equal=True, maintain_order="left"
            )
            merged = counts.filter(pl.col("dataset").is_null()).drop("dataset").rename({"matched": "merged"})
            matched = (
                exact.join(merged, on=["station_id", "resolution"], how="left", maintain_order="left")
                .with_columns(pl.coalesce("matched", "merged").fill_null(0).alias("matched"))
                .drop("merged")
            )
        matched = matched.with_columns(pl.col("matched").alias("returned"))
        return replace(self, series=matched, rows=frame.height, matched_rows=frame.height, returned_rows=frame.height)

    def with_returned(self, frame: pl.DataFrame) -> Searched:
        """Count the rows of `frame`, the answer as it is returned, per station and series, beside those that matched.

        They are the matched rows unless `max_rows` cut the answer: what matched stays what the options chose.
        """
        counted = self.with_matched(frame).series
        series = self.series.with_columns(counted.get_column("matched").alias("returned"))
        return replace(self, series=series, rows=frame.height, returned_rows=frame.height)

    def warn_if_capped(self) -> None:
        """Tell, as a warning of the answer being served, that `max_rows` cut it: how many of how many matched rows.

        Logged at the level of info and recorded under `rows-capped` for the `metadata` block of the answer; nothing
        where every row that matched is returned.
        """
        import logging  # noqa: PLC0415

        from wetterdienst.util.response_warnings import ROWS_CAPPED, warn_response  # noqa: PLC0415

        matched, returned = self.matched_total, self.returned_total
        if returned < matched:
            warn_response(
                logging.getLogger(__name__),
                ROWS_CAPPED,
                f"{returned:,} of {matched:,} matched rows are returned: `max_rows` is {self.selection.max_rows}. "
                "The rows are the first of the answer's order, and `metadata.search` counts all that matched.",
                level=logging.INFO,
            )

    def to_dict(self) -> dict[str, object]:
        """Write the report for a `metadata` block: the options, the window, the series and their totals.

        The series come before the totals, and in each the span of the values (`first`, `last`) before the counts, so
        that a reader sees from when to when a series was searched before it reads how many values that is.
        """
        import polars as pl  # noqa: PLC0415

        from wetterdienst.util.datetime import format_timestamp  # noqa: PLC0415

        series = self.series
        shown = series.head(self.listed)

        def stamp(value: dt.datetime | None) -> str | None:
            return format_timestamp(value) if value is not None else None

        def total(name: str) -> int | None:
            # null where one series has no fixed step: a total that is partly unknown is no total
            column = series.get_column(name)
            return int(column.sum()) if column.null_count() == 0 else None

        return {
            "options": self.selection.echo(),
            "window": {"start": stamp(self.window[0]), "end": stamp(self.window[1])},
            "series": [
                {
                    "station_id": row["station_id"],
                    "name": row["name"],
                    "resolution": row["resolution"],
                    "dataset": row["dataset"],
                    "parameter": row["parameter"],
                    "first": stamp(row["first"]),
                    "last": stamp(row["last"]),
                    "searched": row["searched"],
                    "expected": row["expected"],
                    "gaps": row["gaps"],
                    "matched": row["matched"],
                    "returned": row["returned"],
                }
                for row in shown.iter_rows(named=True)
            ],
            "series_omitted": max(0, series.height - self.listed),
            "totals": {
                "stations_read": self.stations_read,
                "stations_with_values": series.filter(pl.col("searched") > 0).get_column("station_id").n_unique(),
                "series": series.height,
                "searched": int(series.get_column("searched").sum()),
                "expected": total("expected"),
                "gaps": total("gaps"),
                "matched": self.matched_total,
                "returned": self.returned_total,
            },
        }


def latest_complete(resolution: Resolution, now: dt.datetime) -> dt.datetime | None:
    """Give the stamp of the last reading of a resolution that is complete at `now`, None where it has no fixed step.

    The reading of the day, the hour or the month that is still running does not exist yet: for daily data the stamp of
    yesterday, for hourly data that of the hour before this one, for monthly data the first of last month and for annual
    data the first of January of last year. What lies after it is the future, which a window may reach into and no
    series can be missing.
    """
    from wetterdienst.metadata.resolution import Resolution, reading_step  # noqa: PLC0415

    now = now.astimezone(dt.UTC)
    if resolution == Resolution.MONTHLY:
        year, month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
        return dt.datetime(year, month, 1, tzinfo=dt.UTC)
    if resolution == Resolution.ANNUAL:
        return dt.datetime(now.year - 1, 1, 1, tzinfo=dt.UTC)
    step = reading_step(resolution)
    if step is None:
        return None
    epoch = dt.datetime(1970, 1, 1, tzinfo=dt.UTC)
    return now - (now - epoch) % step - step


def station_names(stations: pl.DataFrame) -> dict[str, str | None]:
    """Give the name of each station of a stations frame by its id, for the report; none where the frame has none."""
    if "name" not in stations.columns or "station_id" not in stations.columns:
        return {}
    rows = stations.select("station_id", "name").unique(subset="station_id", keep="first", maintain_order=True)
    return dict(rows.iter_rows())


def wide_value_columns(frame: pl.DataFrame) -> list[str]:
    """Name the columns of a wide frame that hold a parameter's values: not the keys, not the columns of the flags."""
    keys = {"station_id", "resolution", "dataset", "timestamp"}
    return [c for c in frame.columns if c not in keys and not c.endswith("_quality_flags")]


def _usual_step(resolution: Resolution) -> dt.timedelta | None:
    """Give how far apart the readings of a resolution usually are, for the comparison with a series' own step."""
    from wetterdienst.metadata.resolution import Resolution, reading_step  # noqa: PLC0415

    if resolution == Resolution.MONTHLY:
        return dt.timedelta(days=30)
    if resolution == Resolution.ANNUAL:
        return dt.timedelta(days=365)
    return reading_step(resolution)


def searched_of(
    frame: pl.DataFrame,
    window: tuple[dt.datetime | None, dt.datetime | None] = (None, None),
    now: dt.datetime | None = None,
    *,
    names: Mapping[str, str | None] | None = None,
    forecast: bool = False,
) -> pl.DataFrame:
    """Count what a frame of values holds per station and series, before any selection: the report's raw rows.

    The frame is long (a row a value) or wide (a column a parameter, whose `parameter` is then the name of the column).
    `searched` counts the readings with a value; `first` and `last` are the stamps of the first and the last of them;
    `name` is the station's, from `names`. `expected` is what the request covers, counted in the steps of the
    resolution (calendar months and years for the monthly and annual data), null where the resolution has none or more
    readings were found than the step allows (a source with a finer step than its resolution says):

    - with a window, from its start to its end or to the last complete reading at `now`, whichever is earlier, so that
      a window that begins before the data, a series that ended before the window does, and a year that is not over
      are incomplete, as they are; never narrower than the values found. A window that begins after the last complete
      reading (a forecast's) has no past to be missing: the span of the values is counted. A series with no value is
      counted over the window too, so that it reads as all missing;
    - without one, from the first value to the last.

    `gaps` is what the series lacks inside its own span, from its first value to its last, whatever the window says.

    Both are null for a `forecast` and where the series is coarser than its resolution: almost none of its steps is as
    short as the resolution's (the 5 % quantile of the steps is above one and a half times it). A maximum of the last
    12 hours in an hourly dataset has a value every 12 hours, so 11 of 12 hours are no gap; a series that misses half
    its hours, or that was read at 7, 14 and 21 h for twenty years and then every hour, is not coarser: its gaps
    count. A series with no value has no gaps to count, and its `expected` is the window.
    """
    import polars as pl  # noqa: PLC0415

    from wetterdienst.metadata.resolution import Resolution, count_readings  # noqa: PLC0415

    now = now or dt.datetime.now(dt.UTC)
    keys = ["station_id", "resolution", "dataset", "parameter"]
    if "parameter" in frame.columns:
        valued = pl.col("value").is_not_null()
        grouped = frame.group_by(keys, maintain_order=True).agg(
            valued.sum().alias("searched"),
            pl.col("timestamp").filter(valued).min().alias("first"),
            pl.col("timestamp").filter(valued).max().alias("last"),
            pl.col("timestamp").filter(valued).sort().diff().quantile(0.05, interpolation="lower").alias("usual"),
        )
    else:
        parts = [
            frame.group_by(keys[:3], maintain_order=True)
            .agg(
                pl.col(column).is_not_null().sum().alias("searched"),
                pl.col("timestamp").filter(pl.col(column).is_not_null()).min().alias("first"),
                pl.col("timestamp").filter(pl.col(column).is_not_null()).max().alias("last"),
                pl.col("timestamp")
                .filter(pl.col(column).is_not_null())
                .sort()
                .diff()
                .quantile(0.05, interpolation="lower")
                .alias("usual"),
            )
            .with_columns(pl.lit(column).alias("parameter"))
            for column in wide_value_columns(frame)
        ]
        grouped = (
            pl.concat(parts).select([*keys, "searched", "first", "last", "usual"])
            if parts
            else pl.DataFrame(
                schema={
                    **dict.fromkeys(keys, pl.String),
                    "searched": pl.UInt32,
                    "first": pl.Datetime("us", "UTC"),
                    "last": pl.Datetime("us", "UTC"),
                    "usual": pl.Duration("us"),
                }
            )
        )
    known = {resolution.value for resolution in Resolution}
    start, end = window
    expected: list[int | None] = []
    gaps: list[int | None] = []
    for row in grouped.iter_rows(named=True):
        span = covered = None
        if row["resolution"] in known and not forecast:
            resolution = Resolution(row["resolution"])
            nominal = _usual_step(resolution)
            coarser = row["usual"] is not None and nominal is not None and row["usual"] > nominal * 1.5
            latest = latest_complete(resolution, now)
            has_window = start is not None and latest is not None and start <= latest
            if coarser:
                pass
            elif row["first"] is not None:
                span = count_readings(resolution, row["first"], row["last"])
                covered = span
                if has_window:
                    until = min(end or latest, latest)
                    covered = count_readings(resolution, min(start, row["first"]), max(until, row["last"]))
            elif has_window:
                covered = count_readings(resolution, start, min(end or latest, latest))
            if span is not None and row["searched"] > span:
                span = covered = None
            if covered is not None and row["searched"] > covered:
                covered = None
        expected.append(covered)
        gaps.append(None if span is None else span - row["searched"])
    name = (
        pl.col("station_id").replace_strict(dict(names), default=None, return_dtype=pl.String)
        if names
        else pl.lit(None, pl.String)
    )
    return grouped.with_columns(
        name.alias("name"),
        pl.Series("expected", expected, dtype=pl.UInt32),
        pl.Series("gaps", gaps, dtype=pl.UInt32),
        pl.col("searched").cast(pl.UInt32),
    ).select(["station_id", "name", *keys[1:], "searched", "expected", "gaps", "first", "last"])
