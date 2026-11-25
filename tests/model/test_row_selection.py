# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The text of the row options is read by a hand-written parser that raises one error and is bounded (GH-4411).

What is held here: the grammar (what is read and what is refused, with the position and the hint), the caps, that
nothing but `RowSelectionError` ever comes out of a text, that the time and the memory of a parse do not grow with
what is typed, and that what the parser read is written back by `echo` as the same selection.
"""

from __future__ import annotations

import contextlib
import os
import random
import string
import time
import tracemalloc

import pytest

from wetterdienst.exceptions import RequestError
from wetterdienst.model import row_selection as rs
from wetterdienst.model.row_selection import (
    MAX_CONDITIONS,
    MAX_FILTER_LENGTH,
    MAX_FIRST,
    MAX_LIST_ITEMS,
    MAX_NUMBER_LENGTH,
    Condition,
    RowSelectionError,
    SortKey,
    parse_by,
    parse_filter,
    parse_row_selection,
    parse_sort,
    read_first,
    read_max_rows,
)


def _sel(text: str) -> list[tuple[str, str, tuple[float | int, ...]]]:
    return [(c.column, c.operator, c.values) for c in parse_filter(text)]


def test_reads_a_condition_of_every_column_and_operator() -> None:
    """Reads a condition of every column and operator."""
    assert _sel("value<=-20") == [("value", "<=", (-20.0,))]
    assert _sel("value>=0.5,year>1900,month<12,day!=24,hour=0") == [
        ("value", ">=", (0.5,)),
        ("year", ">", (1900,)),
        ("month", "<", (12,)),
        ("day", "!=", (24,)),
        ("hour", "=", (0,)),
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("value<=-20", -20.0),
        ("value< -20", -20.0),
        ("  value  <=  -20  ", -20.0),
        ("VALUE<=-20", -20.0),
        ("value<=1e3", 1000.0),
        ("value<=1E3", 1000.0),
        ("value<=2e-3", 0.002),
        ("value<=-0.5", -0.5),
        ("value<=007", 7.0),
        ("value\t<=\t5", 5.0),
    ],
)
def test_whitespace_case_and_number_formats(text: str, expected: float) -> None:
    """Whitespace case and number formats."""
    assert _sel(text)[0][2] == (expected,)


def test_a_list_goes_with_equal_and_not_equal() -> None:
    """A list goes with equal and not equal."""
    assert _sel("month=12|1|2") == [("month", "=", (12, 1, 2))]
    assert _sel("year != 1940 | 1941") == [("year", "!=", (1940, 1941))]
    assert _sel("value=1.5|-2") == [("value", "=", (1.5, -2.0))]


def test_a_column_may_be_named_twice() -> None:
    """A range, or an answer that is empty: neither is an error."""
    assert len(parse_filter("value>=-20,value<=-10")) == 2
    assert len(parse_filter("month=12,month=1")) == 2


@pytest.mark.parametrize(
    ("text", "position", "fragment"),
    [
        ("value<=", 8, "no number"),
        ("value==5", 6, "single `=`"),
        ("value=<5", 6, "`<=`"),
        ("value<>5", 6, "`!=`"),
        ("value<=nan", 8, "nan, inf"),
        ("value<=inf", 8, "nan, inf"),
        ("value<=+5", 8, "plus sign"),
        ("value<=5,", 10, "comma with no condition"),
        ("value<=5,,month=1", 10, "no column"),
        (",value<=5", 1, "no column"),
        ("value<=5x", 9, "something after the number"),
        ("value<=5 degC", 10, "something after the number"),
        ("value<=1e", 10, "exponent with no digits"),
        ("value<=1.", 10, "no digits after it"),
        ("value<=.5", 8, "no number"),
        ("value<=--5", 9, "no number"),
        ("value", 6, "condition ends after the column"),
        ("value 5", 7, "no operator"),
        ("value<5|6", 8, "list `|`"),
        ("value>=5|6", 9, "list `|`"),
        ("month=13", 7, "outside the range"),
        ("month=0", 7, "outside the range"),
        ("hour=24", 6, "outside the range"),
        ("day=32", 5, "outside the range"),
        ("year=0", 6, "outside the range"),
        ("month=1.5", 7, "whole number"),
        ("month=1e1", 7, "whole number"),
        ("value<=1e999", 8, "too large"),
        ("value<=1e30", 8, "too large"),
    ],
)
def test_refusals_name_the_position_and_what_is_wrong(text: str, position: int, fragment: str) -> None:
    """Refusals name the position and what is wrong."""
    with pytest.raises(RowSelectionError) as raised:
        parse_filter(text)
    error = raised.value
    assert error.option == "filter"
    assert error.position == position, str(error)
    assert fragment in str(error), str(error)
    assert f"position {position}" in str(error)


@pytest.mark.parametrize(
    ("column", "hint"),
    [
        ("parameter", "`parameters`"),
        ("timestamp", "`timestamp` option"),
        ("station_id", "`stations`"),
        ("quality", "not available"),
        ("top", "`first`"),
        ("temperature", "Example"),
    ],
)
def test_an_unknown_column_is_refused_with_what_to_do_instead(column: str, hint: str) -> None:
    """An unknown column is refused with what to do instead."""
    with pytest.raises(RowSelectionError) as raised:
        parse_filter(f"{column}<5")
    assert "value, year, month, day, hour" in str(raised.value)
    assert hint in str(raised.value)


def test_text_that_is_empty_too_long_or_not_ascii_is_refused_before_it_is_read() -> None:
    """Text that is empty too long or not ascii is refused before it is read."""
    with pytest.raises(RowSelectionError, match="empty"):
        parse_filter("   ")
    with pytest.raises(RowSelectionError, match="more than the 400"):
        parse_filter("v" * (MAX_FILTER_LENGTH + 1))
    with pytest.raises(RowSelectionError) as raised:
        parse_filter("value<=5°")
    assert raised.value.position == 9
    assert "not plain ASCII" in str(raised.value)
    with pytest.raises(RowSelectionError, match="not plain ASCII"):
        parse_filter("value<=5\n")


def test_the_caps_hold_at_their_edge() -> None:
    """The caps hold at their edge."""
    assert len(parse_filter(",".join(["value>=1"] * MAX_CONDITIONS))) == MAX_CONDITIONS
    with pytest.raises(RowSelectionError, match="more than 8 conditions"):
        parse_filter(",".join(["value>=1"] * (MAX_CONDITIONS + 1)))
    assert len(parse_filter("month=" + "|".join(["1"] * MAX_LIST_ITEMS))[0].values) == MAX_LIST_ITEMS
    with pytest.raises(RowSelectionError, match="more than 32 numbers"):
        parse_filter("month=" + "|".join(["1"] * (MAX_LIST_ITEMS + 1)))
    long_number = "0." + "1" * (MAX_NUMBER_LENGTH - 2)
    assert len(long_number) == MAX_NUMBER_LENGTH
    assert parse_filter(f"value<={long_number}")
    with pytest.raises(RowSelectionError, match="more than the 24"):
        parse_filter(f"value<={long_number}1")


def test_the_one_error_is_a_request_error_and_a_value_error() -> None:
    """The one error is a request error and a value error."""
    with pytest.raises(RequestError):
        parse_filter("nonsense")
    with pytest.raises(ValueError, match="Invalid `filter`"):
        parse_filter("nonsense")


def test_sort_reads_keys_and_directions() -> None:
    """Sort reads keys and directions."""
    assert parse_sort("-value") == (SortKey("value", descending=True),)
    assert parse_sort("month, -day ,timestamp") == (
        SortKey("month", descending=False),
        SortKey("day", descending=True),
        SortKey("timestamp", descending=False),
    )
    assert parse_sort("VALUE") == (SortKey("value", descending=False),)


@pytest.mark.parametrize(
    ("text", "position", "fragment"),
    [
        ("", None, "empty"),
        ("value,", 7, "no column"),
        (",value", 1, "no column"),
        ("value,value", 7, "named twice"),
        ("value,-value", 7, "named twice"),
        ("parameter", 1, "`parameters`"),
        ("-parameter", 2, "`parameters`"),
        ("desc", 1, "Write `-` before a column"),
        ("value desc", 1, "not a column"),
        ("--value", 2, "not a column"),
    ],
)
def test_sort_refusals(text: str, position: int | None, fragment: str) -> None:
    """Sort refusals."""
    with pytest.raises(RowSelectionError) as raised:
        parse_sort(text)
    assert raised.value.option == "sort"
    assert raised.value.position == position, str(raised.value)
    assert fragment in str(raised.value), str(raised.value)


def test_by_reads_columns_or_none() -> None:
    """By reads columns or none."""
    assert parse_by("station_id,year") == ("station_id", "year")
    assert parse_by("none") == ()
    assert parse_by(" None ") == ()


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("none,year", "together with other columns"),
        ("year,none", "together with other columns"),
        ("year,year", "named twice"),
        ("parameter", "`parameters`"),
        ("value", "not a column"),
        ("station", "station_id"),
    ],
)
def test_by_refusals(text: str, fragment: str) -> None:
    """By refusals."""
    with pytest.raises(RowSelectionError) as raised:
        parse_by(text)
    assert raised.value.option == "by"
    assert fragment in str(raised.value), str(raised.value)


@pytest.mark.parametrize("value", [1, "1", " 12 ", MAX_FIRST])
def test_first_reads_a_whole_number(value: object) -> None:
    """First reads a whole number."""
    assert read_first(value) == int(str(value).strip())


@pytest.mark.parametrize("value", [0, -1, MAX_FIRST + 1, "0", "1.5", "one", "", "1e3", True, 1.0, None, "9" * 30])
def test_first_refuses_anything_else(value: object) -> None:
    """First refuses anything else."""
    with pytest.raises(RowSelectionError) as raised:
        read_first(value)
    assert raised.value.option == "first"


def test_first_needs_sort_and_by_needs_first_each_with_a_hint() -> None:
    """First needs sort and by needs first each with a hint."""
    with pytest.raises(RowSelectionError, match=r"no `sort` is given.*sort=-value") as raised:
        parse_row_selection(first=1)
    assert raised.value.option == "first"
    with pytest.raises(RowSelectionError, match=r"no `first` is given.*first=N") as raised:
        parse_row_selection(sort="value", by="year")
    assert raised.value.option == "by"


def test_no_option_is_no_selection_and_an_empty_text_is_no_option() -> None:
    """No option is no selection and an empty text is no option."""
    assert parse_row_selection() is None
    assert parse_row_selection(filter="", sort="", first="", by="") is None
    assert parse_row_selection(sort="-value") is not None


def test_the_reserved_names_of_step_2_are_not_columns() -> None:
    """The reserved names of step 2 are not columns."""
    for name in ("window", "year_start", "timezone", "aggregate", "having", "per", "max_missing"):
        for parse in (parse_filter, parse_sort, parse_by):
            with pytest.raises(RowSelectionError):
                parse(name)


def _random_text(rng: random.Random, kind: str) -> str:
    """Make a text of the shape the options have, or a mutilation of one."""
    columns = {
        "filter": ("value", "year", "month", "day", "hour", "VALUE", "parameter", "x"),
        "sort": ("value", "timestamp", "year", "month", "day", "hour", "station_id", "-value", "-year", "none", "x"),
        "by": ("station_id", "year", "month", "day", "hour", "timestamp", "none", "x"),
    }[kind]
    pieces = []
    for _ in range(rng.randint(0, 6)):
        column = rng.choice(columns)
        if kind == "filter":
            number = rng.choice(
                ["-20", "0.5", "1e3", "2E-3", "12", "1", "007", "nan", "+5", "9" * rng.randint(1, 40), ""]
            )
            listed = "|".join(rng.choice(["1", "-2.5", "12", "x", ""]) for _ in range(rng.randint(0, 4)))
            pieces.append(
                column
                + rng.choice(["", " ", "<=", ">=", "!=", "=", "<", ">", "==", "<>", "=<", "~", " <= "])
                + number
                + ("|" + listed if listed and rng.random() < 0.5 else "")
            )
        else:
            pieces.append(column)
    text = rng.choice([",", ", ", " , ", ",,", ""]).join(pieces)
    roll = rng.random()
    if roll < 0.3 and text:
        i = rng.randrange(len(text))
        text = (
            text[:i] + rng.choice(string.printable + "\u00e4\u2603\x00" + chr(0x202E)) + text[i + rng.randint(0, 2) :]
        )
    elif roll < 0.4:
        text = "".join(rng.choice(string.printable + "\u00e4\u2603\x00") for _ in range(rng.randint(0, 80)))
    return text


def _fuzz_count() -> int:
    return int(os.environ.get("WD_FUZZ_ROWS", "120000"))


@pytest.mark.parametrize("kind", ["filter", "sort", "by"])
def test_nothing_but_the_one_error_comes_out_of_any_text(kind: str) -> None:
    """A few 100,000 texts, valid and mutilated: they parse, or raise `RowSelectionError`; what parsed round-trips."""
    rng = random.Random(f"row-selection-{kind}")  # noqa: S311
    parse = {"filter": parse_filter, "sort": parse_sort, "by": parse_by}[kind]
    parsed = refused = 0
    for _ in range(_fuzz_count() // 3):
        text = _random_text(rng, kind)
        try:
            result = parse(text)
        except RowSelectionError as error:
            refused += 1
            checked = (error.option, error.position, len(str(error)))
            assert checked[0] == kind
            assert checked[1] is None or 1 <= checked[1] <= max(len(text), 1) + 1
            assert checked[2] < 1200
            continue
        parsed += 1
        # what was read is written back as the same selection
        match kind:
            case "filter":
                written = ",".join(c.text() for c in result)
            case "sort":
                written = ",".join(k.text() for k in result)
            case _:
                written = ",".join(result) or "none"
        assert parse(written) == result, (text, written)
    assert parsed > 50
    assert refused > 50


def test_time_and_memory_do_not_grow_with_what_is_typed() -> None:
    """The parse of the longest text allowed costs microseconds; a longer one is refused without being read."""
    worst = "month=" + "|".join(["12"] * MAX_LIST_ITEMS) + ("," + "value>=-1.5e-3") * (MAX_CONDITIONS - 1)
    assert len(worst) <= MAX_FILTER_LENGTH
    parse_filter(worst)
    start = time.perf_counter()
    for _ in range(2000):
        parse_filter(worst)
    per_parse = (time.perf_counter() - start) / 2000
    assert per_parse < 0.002, per_parse

    # a text of any length over the cap is refused at once: the same time for 1 KB and for 10 MB
    timings = []
    for size in (10**3, 10**5, 10**7):
        text = "value<=1," * (size // 9)
        start = time.perf_counter()
        for _ in range(20):
            with pytest.raises(RowSelectionError):
                parse_filter(text)
        timings.append(time.perf_counter() - start)
    assert max(timings) < 0.05, timings

    # memory stays flat over many parses of texts of every size
    tracemalloc.start()
    baseline = tracemalloc.get_traced_memory()[0]
    rng = random.Random(7)  # noqa: S311
    for _ in range(20000):
        with contextlib.suppress(RowSelectionError):
            parse_filter(_random_text(rng, "filter") * rng.randint(1, 30))
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert peak - baseline < 2_000_000, peak - baseline


def test_the_parser_is_linear_up_to_its_cap() -> None:
    """Time grows in proportion to the length of the text, not faster, over the lengths that are read."""

    def cost(conditions: int) -> float:
        text = ",".join(["value>=-12.5"] * conditions)
        best = min(_timed(lambda: parse_filter(text)) for _ in range(5))
        return best / len(text)

    per_character = [cost(n) for n in (1, 2, 4, 8)]
    # the cost per character is flat to within a small factor, which a quadratic parse would not be
    assert max(per_character) < 6 * min(per_character), per_character


def _timed(call: object) -> float:
    start = time.perf_counter()
    for _ in range(300):
        call()  # ty: ignore[call-non-callable]
    return time.perf_counter() - start


def test_condition_and_key_write_themselves_as_they_are_read() -> None:
    """Condition and key write themselves as they are read."""
    assert Condition("value", "<=", (-20.0,)).text() == "value<=-20"
    assert Condition("value", ">", (0.5,)).text() == "value>0.5"
    assert Condition("value", "<", (1e-05,)).text() == "value<1e-05"
    assert Condition("month", "=", (12, 1)).text() == "month=12|1"
    assert SortKey("value", descending=True).text() == "-value"
    assert rs.RowSelection().echo() == {"filter": None, "sort": None, "first": None, "by": None, "max_rows": None}


@pytest.mark.parametrize("value", [1, "1", " 20 ", 10_000])
def test_max_rows_reads_a_whole_number(value: object) -> None:
    """A whole number from 1 to 10,000, as a number or the text of one."""
    assert read_max_rows(value) == int(str(value).strip())


@pytest.mark.parametrize("value", [0, -1, 10_001, "0", "1.5", "twenty", "1e3", True, 1.0, "9" * 30])
def test_max_rows_refuses_anything_else(value: object) -> None:
    """Anything else is refused with the option's name, and a hint."""
    with pytest.raises(RowSelectionError) as raised:
        read_max_rows(value)
    assert raised.value.option == "max_rows"
    assert "max_rows" in str(raised.value)


def test_max_rows_needs_no_other_option_and_is_echoed() -> None:
    """It works alone, and the report names it."""
    selection = parse_row_selection(max_rows=5)
    assert selection is not None
    assert selection.max_rows == 5
    assert selection.per_station
    assert selection.echo() == {"filter": None, "sort": None, "first": None, "by": None, "max_rows": 5}
    assert parse_row_selection(max_rows="") is None
