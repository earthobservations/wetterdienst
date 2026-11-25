# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The small grammar the options of a request that choose rows or groups are written in (GH-4411, GH-4412).

`filter` and `sort` of `values` (`model/row_selection.py`), and `filter`, `having`, `sort`, `by` and `aggregate` of
`statistics` (`model/group_statistics.py`) are all texts of this one grammar: conditions joined with `,`, each a
column, an operator and a number or a list of numbers; columns joined with `,`, with `-` before one for descending.
It is read by the hand-written scanner below, which is all there is: no regular expression, no `eval`, no SQL, and
nothing in the text is a function or a nesting. It is linear in the length of the text, which is bounded
(`MAX_FILTER_LENGTH` and the constants beside it), and the one error it raises, `RowSelectionError`, names the option,
the position, what was found there and what is allowed.

What differs between the options is the columns each allows and what a word that is no column of the option is
taken for (a parameter's name in `values`, a refusal that says where the word belongs in `statistics`): both are
arguments of `parse_conditions` and `parse_columns`. The text is checked in full before a station is read.

The module imports no polars, so that the command line can parse a text for `--help` and a usage error without its
cost.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from wetterdienst.exceptions import RequestError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

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


#: the whole numbers a calendar column may be compared with: a number outside is a mistake (`month=0`, `hour=24`)
_CALENDAR_RANGE: Final = {"year": (1, 9999), "month": (1, 12), "day": (1, 31), "hour": (0, 23)}
#: the largest magnitude of a `value` number: more is no reading
_MAX_VALUE: Final = 1e15


_OPERATORS: Final = ("<=", ">=", "!=", "<", ">", "=")
_WORD = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
_DIGITS = frozenset("0123456789")

Operator = Literal["=", "!=", "<", "<=", ">", ">="]


_OPERATOR_HINTS: Final = {
    "==": "write a single `=`",
    "=<": "write `<=`",
    "=>": "write `>=`",
    "<>": "write `!=`",
    "~": "regular expressions and pattern matching are not available",
}


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
        hint=_OPERATOR_HINTS.get(
            char,
            "a condition is a column, an operator and a number: temperature_air_min_2m<0 or value<=-20. "
            "No arithmetic: a difference of two parameters cannot be filtered",
        ),
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


def parse_conditions(
    option: str,
    text: str,
    columns: Sequence[str],
    example: str,
    resolve: Callable[[_Scanner, str, int], str],
) -> tuple[Condition, ...]:
    """Read a text of conditions joined by `,` into `Condition`s, or raise `RowSelectionError`.

    Spaces and tabs between tokens are ignored; column names and `e` of an exponent are read in either case. A column
    may be named twice (`value>=-20,value<=-10` is a range, `month=12,month=1` is an empty answer, not an error).
    A word that is none of `columns` is given to `resolve`, which returns the column it stands for or raises.
    """
    _check_text(option, text, MAX_FILTER_LENGTH)
    scanner = _Scanner(option, text)
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
        if column not in columns:
            column = resolve(scanner, word, start)
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
                raise scanner.fail("a comma with no condition after it", expected="a condition", hint=example)
            continue
        if scanner.peek():
            raise scanner.fail(
                "something after the number",
                expected="`,` for the next condition, `|` for another number, or the end of the text",
                hint=("a unit or a word after the number is not read; " if scanner.peek().isalpha() else "") + example,
            )
        return tuple(conditions)


def parse_columns(
    option: str,
    text: str,
    columns: Sequence[str],
    example: str,
    resolve: Callable[[_Scanner, str, int], str],
    *,
    signed: bool,
    maximum: int = MAX_ORDER_LENGTH,
) -> tuple[SortKey, ...]:
    """Read a text of columns joined by `,` into keys, or raise `RowSelectionError`: `-` before one is descending.

    `signed` is for `sort`; `by` and `aggregate` are the same text without a sign (the keys are all ascending). A word
    that is none of `columns` is given to `resolve`, which returns the column it stands for or raises. Each column
    may be named once.
    """
    scanner = _Scanner(option, text)
    keys: list[SortKey] = []
    for part, position in _split(option, text, maximum):
        stripped = part.strip(" \t")
        offset = position + (len(part) - len(part.lstrip(" \t")))
        descending = signed and stripped.startswith("-")
        word = stripped[1:].strip(" \t") if descending else stripped
        column = word.lower()
        if column not in columns:
            column = resolve(scanner, word, offset + (1 if descending else 0))
        if any(key.column == column for key in keys):
            raise scanner.fail(f"`{column}` is named twice", expected="each column once", hint=example, at=offset)
        keys.append(SortKey(column, descending))
    return tuple(keys)
