# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Station names are matched without regard to case, diacritics or the way an umlaut is typed."""

import pytest

from wetterdienst.util.names import fold_name, match_names


@pytest.mark.parametrize(
    ("name", "plain", "spelled"),
    [
        ("Köln", "koln", "koeln"),
        ("KÖLN", "koln", "koeln"),
        ("Düsseldorf", "dusseldorf", "duesseldorf"),
        ("Bärenstein", "barenstein", "baerenstein"),
        ("Straße", "strasse", "strasse"),
        ("STRASSE", "strasse", "strasse"),
        ("Tromsø", "tromso", "tromsoe"),
        ("Århus", "arhus", "aarhus"),
        ("Łódź", "lodz", "lodz"),
        ("Gdańsk", "gdansk", "gdansk"),
        ("Zürich", "zurich", "zuerich"),
        ("São Paulo", "sao paulo", "sao paulo"),
        ("Málaga", "malaga", "malaga"),
        ("Brno-Tuřany", "brno-turany", "brno-turany"),
        ("Plzeň-Mikulka", "plzen-mikulka", "plzen-mikulka"),
        ("Çanakkale", "canakkale", "canakkale"),
        ("Šumava", "sumava", "sumava"),
        ("Reykjavík", "reykjavik", "reykjavik"),
        ("Þingvellir", "thingvellir", "thingvellir"),
        ("Hamburg-Fuhlsbüttel", "hamburg-fuhlsbuttel", "hamburg-fuhlsbuettel"),
        ("Dresden", "dresden", "dresden"),
        # a name typed with a combining mark (macOS file names, some JSON) is the same name
        ("Köln", "koln", "koeln"),
    ],
)
def test_a_name_folds_to_its_plain_and_its_spelled_out_form(name: str, plain: str, spelled: str) -> None:
    """The accent is dropped in the plain form; the umlaut and the Nordic letters are spelled out in the other."""
    assert fold_name(name) == (plain, spelled)


NAMES = ["Köln", "Koln-Bonn", "Düsseldorf", "Dusseldorf-Flughafen", None, "Kiel", "Koeln-Stammheim", "Dresden"]


def _hits(query: str, threshold: float = 0.8) -> list[str | None]:
    return [NAMES[index] for index, _ in match_names(query, NAMES, threshold)]


@pytest.mark.parametrize("query", ["Köln", "Koln", "koeln", "KOELN", "köln", "Köln"])
def test_every_way_of_writing_koeln_finds_koeln(query: str) -> None:
    """An umlaut written out, dropped or typed as it is: the same station is found."""
    assert "Köln" in _hits(query)


@pytest.mark.parametrize("query", ["Dusseldorf", "Düsseldorf", "duesseldorf", "DUSSELDORF", "düsseldorf"])
def test_every_way_of_writing_duesseldorf_finds_it(query: str) -> None:
    """Düsseldorf is found by its plain, its spelled and its accented form, in both directions."""
    hits = _hits(query)
    assert "Düsseldorf" in hits
    assert "Dusseldorf-Flughafen" in hits


def test_the_exact_spelling_is_the_best_match() -> None:
    """The name scores 100 in its own folded form, so that it is ahead of the stations that merely hold it."""
    assert match_names("koeln", NAMES, 0.8)[0][1] == 100.0
    assert [NAMES[index] for index, _ in match_names("Düsseldorf", NAMES, 1.0)] == ["Düsseldorf"]


def test_a_null_name_never_matches() -> None:
    """A station without a name is no candidate, whatever the threshold."""
    assert NAMES.index(None) not in {index for index, _ in match_names("", NAMES, 0.0)}
    assert NAMES.index(None) not in {index for index, _ in match_names("anything", NAMES, 0.0)}


def test_the_threshold_is_the_least_score_and_equal_scores_keep_the_order_of_the_names() -> None:
    """A name below the threshold is out; the ones that tie come in the order they were given."""
    assert _hits("Kiel", 1.0) == ["Kiel"]
    ties = match_names("Kiel", ["Kiel-B", "Kiel-A", "Kiel"], 0.8)
    assert [index for index, _ in ties] == [2, 0, 1]


def test_an_unrelated_name_does_not_match() -> None:
    """Folding is no loosening: a different name stays below the threshold."""
    assert _hits("Berlin") == []
    assert _hits("") == []


# the spellings a person types for one station name, the name as it is written first: an umlaut or a Nordic letter
# kept, dropped (``Koln``) or spelled out (``Koeln``), and the case it comes in
SPELLINGS = [
    ["Köln", "Koln", "Koeln", "KOELN"],
    ["Århus", "Arhus", "Aarhus"],
    ["Düsseldorf", "Dusseldorf", "Duesseldorf"],
    ["Straße", "Strasse"],
    ["Tromsø", "Tromso", "Tromsoe"],
    ["Göteborg", "Goteborg", "Goeteborg"],
    ["Zürich", "Zurich", "Zuerich"],
    ["Bäumchen", "Baumchen", "Baeumchen"],
    ["Malmö", "Malmo", "Malmoe"],
    ["Sønderborg", "Sonderborg", "Soenderborg"],
]

# a list that holds the umlaut forms, as DWD's, SMHI's and DMI's do, the same names with a suffix as stations are
# named (``Köln-Flughafen``), and names that are none of these
UMLAUT_STATIONS = [
    None,
    *[group[0] for group in SPELLINGS],
    *[f"{group[0]}-Flughafen" for group in SPELLINGS],
    "Kiel",
    "Dresden",
    "Bremen",
    "Hamburg-Fuhlsbüttel",
]


def _found(query: str, names: list[str | None], threshold: float) -> list[tuple[int, float]]:
    """Return the stations a query finds as `(index, score)`, in the order they are returned."""
    return match_names(query, names, threshold)


@pytest.mark.parametrize("threshold", [0.8, 0.9, 1.0])
@pytest.mark.parametrize("group", SPELLINGS, ids=[group[0] for group in SPELLINGS])
def test_every_spelling_of_a_name_finds_the_same_stations_in_the_same_order(group: list[str], threshold: float) -> None:
    """The name typed with its umlaut, without it, spelled out or in capitals answers with one list of stations.

    The list holds the umlaut forms; a spelling that found fewer stations than another, or the same ones in
    another order, would make what a caller gets depend on a keyboard. The scores may differ, as ``Koeln`` is an
    exact match of ``Köln`` through its spelled-out form and ``Koln`` through its plain one, 100 each. From the
    default threshold of 0.8 up: a name that merely looks like another (``Königsberg`` for ``Köln`` at 0.8) is
    scored in the form the query was typed in, and so can come back for one spelling and not for another.
    """
    found = {spelling: [index for index, _ in _found(spelling, UMLAUT_STATIONS, threshold)] for spelling in group}
    assert found[group[0]], f"{group[0]} finds nothing"
    assert {spelling: hits for spelling, hits in found.items() if hits != found[group[0]]} == {}


@pytest.mark.parametrize("group", SPELLINGS, ids=[group[0] for group in SPELLINGS])
def test_every_spelling_of_a_name_finds_the_station_in_the_first_place(group: list[str]) -> None:
    """The station written with the umlaut is the best match of every spelling, with the full score."""
    for spelling in group:
        best_index, best_score = _found(spelling, UMLAUT_STATIONS, 0.8)[0]
        assert UMLAUT_STATIONS[best_index] == group[0], spelling
        assert best_score == 100.0, spelling


@pytest.mark.parametrize("group", SPELLINGS, ids=[group[0] for group in SPELLINGS])
def test_the_umlaut_spelling_finds_the_station_written_without_it(group: list[str]) -> None:
    """A station an ASCII-only source writes as ``Koeln``, ``Dusseldorf`` or ``Strasse`` is found by the umlaut query.

    Each other spelling is a station of its own here, and the name with the umlaut finds every one of them at the
    full score, in the order the stations are listed.
    """
    ascii_stations = [spelling for spelling in group[1:] if spelling.isascii() and spelling != spelling.upper()]
    assert ascii_stations
    stations = ["Kiel", *ascii_stations, "Dresden"]
    assert _found(group[0], stations, 0.8) == [(index, 100.0) for index in range(1, 1 + len(ascii_stations))]


def test_koeln_and_dusseldorf_written_without_an_umlaut_are_found_by_the_umlaut_query() -> None:
    """The two named ones: ``Koeln`` (the umlaut spelled out) and ``Dusseldorf`` (the umlaut dropped)."""
    stations = ["Koeln", "Dusseldorf", "Kiel"]
    assert [stations[index] for index, _ in _found("Köln", stations, 0.8)] == ["Koeln"]
    assert [stations[index] for index, _ in _found("Düsseldorf", stations, 0.8)] == ["Dusseldorf"]
