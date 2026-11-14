# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The notation of `wmo_id`, `wigos_id` and `icao_id`: what the core reads, and what a search is given (GH-4070)."""

import polars as pl
import pytest

from wetterdienst.model.station_ids import (
    STATION_ID_COLUMNS,
    icao_id_or_none,
    search_icao_id,
    search_wigos_id,
    search_wmo_id,
    wigos_id_or_none,
    wmo_id_or_none,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("01001", "01001"),
        ("10381", "10381"),
        (" 10381 ", "10381"),
        (None, None),
        # a text of another length is no WMO number, and is not padded into one: GHCN hourly has `400` on 445 Spanish
        # stations, and Geosphere a 7-digit `8989106` that is no WMO number either
        ("400", None),
        ("8989106", None),
        ("1001", None),
        ("of", None),
        ("unkno", None),
        ("A191", None),
        ("", None),
        ("0100a", None),
        # a digit that is none of 0-9
        ("١٠٣٨١", None),
    ],
)
def test_a_wmo_id_is_exactly_five_digits(value: str | None, expected: str | None) -> None:
    """Five digits are a WMO number; anything else is none, and is not padded into one."""
    assert wmo_id_or_none(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("EDDH", "EDDH"),
        ("eddh", "EDDH"),
        (" Eddh ", "EDDH"),
        # DWD writes no code as four dashes
        ("----", None),
        ("EDD", None),
        ("EDDHX", None),
        ("ED1H", None),
        ("", None),
        (None, None),
    ],
)
def test_an_icao_id_is_four_upper_case_letters(value: str | None, expected: str | None) -> None:
    """Four letters in any case are an ICAO code, written upper case; `----` is none."""
    assert icao_id_or_none(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0-20000-0-10381", "0-20000-0-10381"),
        # Belgium: OSCAR writes the issuer 56, RMI wrote 056
        ("0-056-101-01002", "0-56-101-01002"),
        ("0-56-101-01002", "0-56-101-01002"),
        ("00-0020000-000-06260", "0-20000-0-06260"),
        # the local id is as the provider publishes it: its zeros and its case stay
        ("0-756-0-BIA", "0-756-0-BIA"),
        ("0-203-0-20303032003", "0-203-0-20303032003"),
        (" 0-20000-0-06260 ", "0-20000-0-06260"),
        ("0-20000-0-", None),
        ("0-20000-06260", None),
        ("a-20000-0-06260", None),
        ("06260", None),
        ("", None),
        (None, None),
    ],
)
def test_a_wigos_id_has_its_three_numbers_without_leading_zeros(value: str | None, expected: str | None) -> None:
    """The issuer and the other numbers lose their zeros; the local id stays."""
    assert wigos_id_or_none(value) == expected


def test_the_core_reads_a_column_in_its_notation_whichever_way_the_source_wrote_it() -> None:
    """`STATION_ID_COLUMNS` is what `shape_stations_frame` applies: the same rules, over a frame."""
    df = pl.DataFrame(
        {
            "wmo": ["01001", "400", None, " 10381"],
            "wigos": ["0-056-101-01002", "junk", None, "0-20000-0-10381"],
            "icao": ["eddh", "----", None, "EDDB"],
        }
    )

    read = df.select(
        STATION_ID_COLUMNS["wmo_id"]("wmo").alias("wmo"),
        STATION_ID_COLUMNS["wigos_id"]("wigos").alias("wigos"),
        STATION_ID_COLUMNS["icao_id"]("icao").alias("icao"),
    )

    assert read.to_dict(as_series=False) == {
        "wmo": ["01001", None, None, "10381"],
        "wigos": ["0-56-101-01002", None, None, "0-20000-0-10381"],
        "icao": ["EDDH", None, None, "EDDB"],
    }
    assert read.schema == pl.Schema({"wmo": pl.String, "wigos": pl.String, "icao": pl.String})


def test_the_expressions_and_the_functions_read_alike() -> None:
    """The expression the core applies to a frame and the function for one value agree."""
    values = ["0-056-101-01002", "0-20000-0-06260", "0-20000-0-", "x", "00-1-2-3"]
    frame = pl.DataFrame({"v": values}).select(STATION_ID_COLUMNS["wigos_id"]("v").alias("v"))

    assert frame.get_column("v").to_list() == [wigos_id_or_none(value) for value in values]


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (10381, ["10381"]),
        # the leading zero a number loses is given back: Jan Mayen
        (1001, ["01001"]),
        ("1001", ["01001"]),
        ("01001", ["01001"]),
        (" 10381 ", ["10381"]),
        (["10381", 10147, "1001"], ["10381", "10147", "01001"]),
        # the same number twice is asked once
        (["10381", 10381], ["10381"]),
        (("10381",), ["10381"]),
    ],
)
def test_a_wmo_search_pads_what_it_is_given(given: object, expected: list[str]) -> None:
    """One to five digits, as a text or a number, are the WMO number with its zeros."""
    assert search_wmo_id(given) == expected  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize("given", ["abc", "123456", "", "1.5", "-1", "10381,10147", "0-20000-0-10381", []])
def test_a_wmo_search_refuses_what_is_no_wmo_number(given: object) -> None:
    """What is not one to five digits is refused with the column named."""
    with pytest.raises(ValueError, match="wmo_id"):
        search_wmo_id(given)  # ty: ignore[invalid-argument-type]


def test_a_wmo_search_refuses_what_is_neither_a_text_nor_a_number() -> None:
    """A float or a bool is no WMO number, and a TypeError."""
    with pytest.raises(TypeError, match="wmo_id has to be a text or a number"):
        search_wmo_id([1.5])  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="wmo_id has to be a text or a number"):
        search_wmo_id(True)  # noqa: FBT003


def test_an_icao_search_ignores_the_case() -> None:
    """A code typed in lower or mixed case is searched as upper case, each once."""
    assert search_icao_id("eddh") == ["EDDH"]
    assert search_icao_id(["eddh", "EdDb", "EDDH"]) == ["EDDH", "EDDB"]


@pytest.mark.parametrize("given", ["ED", "EDDHX", "ED1H", "----", ""])
def test_an_icao_search_refuses_what_is_not_four_letters(given: str) -> None:
    """A code of another length or with a digit is refused."""
    with pytest.raises(ValueError, match=r"icao_id.*four letters"):
        search_icao_id(given)


def test_a_wigos_search_reads_the_issuer_as_the_column_writes_it() -> None:
    """An issuer written with a leading zero is searched without it."""
    assert search_wigos_id("0-056-101-01002") == ["0-56-101-01002"]
    assert search_wigos_id(["0-20000-0-10381", "0-020000-0-10381"]) == ["0-20000-0-10381"]


@pytest.mark.parametrize("given", ["06260", "0-20000-0-", "EDDH", ""])
def test_a_wigos_search_refuses_what_is_no_identifier(given: str) -> None:
    """What is not four dash-separated parts, the first three numbers, is refused."""
    with pytest.raises(ValueError, match="wigos_id"):
        search_wigos_id(given)
