# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The regions a selection by `region` compares and refuses (GH-4418)."""

from __future__ import annotations

import pickle

import pytest

from wetterdienst.exceptions import NoRegionsError, RequestError, UnknownRegionError
from wetterdienst.model.regions import MAX_REGIONS_NAMED, region_keys, search_regions, select_regions

STATES = [
    "Baden-Württemberg",
    "Bayern",
    "Bremen",
    "Hamburg",
    "Hessen",
    "Niedersachsen",
    "Nordrhein-Westfalen",
    "Sachsen",
    "Sachsen-Anhalt",
]


@pytest.mark.parametrize(
    ("asked", "expected"),
    [
        # case, and the spelling of the umlaut in either of the two ways it is typed without one
        ("hamburg", ["Hamburg"]),
        ("HAMBURG", ["Hamburg"]),
        ("baden-württemberg", ["Baden-Württemberg"]),
        ("Baden-Wurttemberg", ["Baden-Württemberg"]),
        ("Baden-Wuerttemberg", ["Baden-Württemberg"]),
        # a hyphen and a space are one break between words
        ("Baden Wuerttemberg", ["Baden-Württemberg"]),
        ("  Sachsen Anhalt ", ["Sachsen-Anhalt"]),
        # whole, not fuzzy: Sachsen is Sachsen, not Sachsen-Anhalt, and not Niedersachsen
        ("Sachsen", ["Sachsen"]),
        # several, each as the list writes it, in the order they were asked
        (["Hamburg", "bremen"], ["Hamburg", "Bremen"]),
        # one region named twice is one
        (["Hamburg", "HAMBURG"], ["Hamburg"]),
    ],
)
def test_a_region_is_compared_whole_without_regard_to_case_accents_or_the_break_between_words(
    asked: str | list[str], expected: list[str]
) -> None:
    """The regions the list writes, whatever the way they were typed."""
    assert select_regions(STATES, search_regions(asked), network="N") == expected


@pytest.mark.parametrize(
    ("known", "asked", "expected"),
    [
        # Hub'Eau writes its départements in capitals without accents and with an apostrophe
        (["COTES-D'ARMOR", "FINISTERE"], "Côtes d'Armor", ["COTES-D'ARMOR"]),
        (["COTES-D'ARMOR", "FINISTERE"], "finistère", ["FINISTERE"]),
        # the two letters of a province or a canton are the region as the source writes it
        (["BC", "ON", "AB"], "bc", ["BC"]),
        # a département number is text: the zero is part of it
        (["09", "20", "972"], "09", ["09"]),
        # the list writes a space where the name has one
        (["Maarianhamina", "Helsinki"], "helsinki", ["Helsinki"]),
        # the accent the list writes and the one that is typed
        (["Thüringen", "Wien"], "Thueringen", ["Thüringen"]),
        (["Thüringen", "Wien"], "Thuringen", ["Thüringen"]),
        # the list writes the umlaut out, and the umlaut is typed
        (["Thueringen", "Wien"], "Thüringen", ["Thueringen"]),
        (["Thuringen", "Wien"], "Thüringen", ["Thuringen"]),
    ],
)
def test_the_source_of_the_region_writes_it_and_the_search_reads_it_that_way(
    known: list[str], asked: str, expected: list[str]
) -> None:
    """Compared the way station names are, so the spelling of a provider does not matter."""
    assert select_regions(known, [asked], network="N") == expected


def test_nulls_blanks_and_repeats_in_the_list_are_no_regions() -> None:
    """The list holds a null for a station without a region, and a row for every dataset of a station."""
    known = ["Hamburg", None, "Hamburg", "  ", "Bremen "]

    assert select_regions(known, ["Bremen"], network="N") == ["Bremen"]
    with pytest.raises(UnknownRegionError) as error:
        select_regions(known, ["Berlin"], network="N")
    assert error.value.known == ["Bremen", "Hamburg"]


def test_two_spellings_of_a_region_in_the_list_are_both_selected() -> None:
    """A list that writes one region two ways has both, which is what the source says."""
    assert select_regions(["Hamburg", "HAMBURG", "Bremen"], ["hamburg"], network="N") == ["HAMBURG", "Hamburg"]


def test_hesse_is_no_hessen_and_the_refusal_says_which_region_is_close() -> None:
    """No table of names in other languages is behind it: only what the source writes, and a hint."""
    with pytest.raises(UnknownRegionError) as error:
        select_regions(STATES, ["Hesse"], network="DwdObservationRequest")

    message = str(error.value)
    assert message.startswith("DwdObservationRequest has no station in the region 'Hesse'.")
    assert "Closest: 'Hesse': 'Hessen'." in message
    assert message.endswith(f"The regions there are: {', '.join(STATES)}.")
    assert error.value.unknown == ["Hesse"]
    assert error.value.known == STATES
    assert error.value.hints == {"Hesse": ["Hessen"]}
    # a request the caller rephrases, a `ValueError` among them
    assert isinstance(error.value, RequestError)
    assert isinstance(error.value, ValueError)


def test_every_region_that_is_unknown_is_named_even_when_another_is_known() -> None:
    """A request with one known and two unknown regions is refused, naming the two and not the known one."""
    with pytest.raises(UnknownRegionError) as error:
        select_regions(STATES, ["Hamburg", "Atlantis", "Hesse"], network="N")

    assert error.value.unknown == ["Atlantis", "Hesse"]
    assert "regions 'Atlantis', 'Hesse'" in str(error.value)
    # nothing is close to Atlantis, so it has no hint
    assert set(error.value.hints) == {"Hesse"}


def test_a_region_with_no_close_one_is_refused_with_the_list_alone() -> None:
    """No hint where nothing is close."""
    with pytest.raises(
        UnknownRegionError, match=r"^N has no station in the region 'Atlantis'\. The regions there are"
    ) as e:
        select_regions(STATES, ["Atlantis"], network="N")

    assert e.value.hints == {}
    assert "Closest" not in str(e.value)


def test_a_long_list_of_regions_is_capped_in_the_message_and_whole_on_the_error() -> None:
    """164 municipalities are no help in a sentence; the error carries all of them for a program to read."""
    known = [f"Municipality {number:03d}" for number in range(164)]

    with pytest.raises(UnknownRegionError) as error:
        select_regions(known, ["Atlantis"], network="N")

    message = str(error.value)
    assert message.endswith(f"Municipality {MAX_REGIONS_NAMED - 1:03d} and {164 - MAX_REGIONS_NAMED} more.")
    assert f"Municipality {MAX_REGIONS_NAMED:03d}" not in message
    assert len(error.value.known) == 164
    assert len(message) < 700


def test_a_close_region_among_many_is_offered_and_at_most_three() -> None:
    """The hint is the closest regions, so the one meant is found among a long list without reading it."""
    known = [f"Municipality {number:03d}" for number in range(164)] + ["Rovaniemi", "Rovala"]

    with pytest.raises(UnknownRegionError) as error:
        select_regions(known, ["Rovaniem"], network="N")

    assert error.value.hints["Rovaniem"][0] == "Rovaniemi"
    assert len(error.value.hints["Rovaniem"]) <= 3


def test_a_very_long_region_is_cut_in_the_message_and_whole_on_the_error() -> None:
    """A name the source writes at length does not fill the message."""
    known = ["Alpha", "x" * 200]

    with pytest.raises(UnknownRegionError) as error:
        select_regions(known, ["Atlantis"], network="N")

    assert "x" * 200 not in str(error.value)
    assert "x" * 200 in error.value.known


@pytest.mark.parametrize("known", [[], [None, None], ["", "   "]])
def test_a_network_with_no_region_is_refused_for_that_reason(known: list[str | None]) -> None:
    """A list whose regions are all null names none: not a misspelling, so not the 'unknown region' sentence."""
    with pytest.raises(NoRegionsError, match=r"^N lists no region: .* Select the stations by `name`, a point") as error:
        select_regions(known, ["Hamburg"], network="N")

    assert error.value.known == []
    # an unknown region as well, for a caller that asks for one
    assert isinstance(error.value, UnknownRegionError)
    assert "no station in the region" not in str(error.value)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("Hamburg", ["Hamburg"]),
        # a text is one region, a comma in it is no separator: the surfaces split before they come here
        ("Hamburg, Bremen", ["Hamburg, Bremen"]),
        ([" Hamburg ", "Bremen", "Hamburg"], ["Hamburg", "Bremen"]),
        (("Hamburg",), ["Hamburg"]),
    ],
)
def test_the_regions_of_a_search_are_stripped_and_each_named_once(given: str | tuple, expected: list[str]) -> None:
    """What `search_regions` hands on."""
    assert search_regions(given) == expected


@pytest.mark.parametrize("given", ["", "  ", [], [" "], ["Hamburg", ""]])
def test_no_region_and_a_blank_one_are_refused(given: str | list[str]) -> None:
    """A selection by region that names none is no selection."""
    with pytest.raises(ValueError, match="region"):
        search_regions(given)


@pytest.mark.parametrize("given", [1, ["Hamburg", 2], [None]])
def test_a_region_that_is_no_text_is_a_type_error(given: object) -> None:
    """A number is no region, as a number is no ICAO code."""
    with pytest.raises(TypeError, match="region has to be a text"):
        search_regions(given)  # ty: ignore[invalid-argument-type]


def test_the_keys_of_a_region_are_the_plain_and_the_spelled_form_in_words() -> None:
    """Folded as station names are, with the break between words one space."""
    assert region_keys("Baden-Württemberg") == ("baden wurttemberg", "baden wuerttemberg")
    assert region_keys("COTES-D'ARMOR") == ("cotes d armor", "cotes d armor")


def test_the_refusals_pickle_with_what_they_keep() -> None:
    """An error crosses a process boundary (the parallel test runs) with its regions and its hints."""
    with pytest.raises(UnknownRegionError) as error:
        select_regions(STATES, ["Hesse"], network="N")

    copy = pickle.loads(pickle.dumps(error.value))  # noqa: S301

    assert type(copy) is UnknownRegionError
    assert (str(copy), copy.unknown, copy.known, copy.hints) == (
        str(error.value),
        ["Hesse"],
        STATES,
        {"Hesse": ["Hessen"]},
    )
    none = pickle.loads(pickle.dumps(NoRegionsError("N lists no region")))  # noqa: S301
    assert type(none) is NoRegionsError
    assert none.known == []
