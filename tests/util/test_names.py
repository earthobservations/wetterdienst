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


def _order(query: str, names: list[str | None], threshold: float = 0.8) -> list[str | None]:
    return [names[index] for index, _ in match_names(query, names, threshold)]


def test_a_tie_goes_to_the_closer_name_not_to_the_first_row() -> None:
    """GH-4207: every name that holds a short query scores the same, so the closer whole name has to win."""
    pollen = [
        "Rheinland-Pfalz und Saarland: Rhein, Pfalz, Nahe und Mosel",
        "Rheinland-Pfalz und Saarland: Mittelgebirgsbereich Rheinland-Pfalz",
        "Rheinland-Pfalz und Saarland: Saarland",
    ]
    assert _order("Saarland", pollen)[0] == "Rheinland-Pfalz und Saarland: Saarland"
    # the scores of the two that reached the threshold are untouched, and tie on the first key; the third was
    # under it, and holds the query: it is in (GH-4215), last, and reported with the threshold
    assert [score for _, score in match_names("Saarland", pollen, 0.8)] == [90.0, 90.0, 80.0]

    franken = [
        "Bayern: Bayern nördl. der Donau, o. Bayr. Wald, o. Mainfranken",
        "Bayern: Mainfranken",
    ]
    assert _order("Mainfranken", franken)[0] == "Bayern: Mainfranken"

    saxony = ["Niedersachsen und Bremen: Östl. Niedersachsen", "Sachsen: Tiefland Sachsen"]
    assert _order("Sachsen", saxony)[0] == "Sachsen: Tiefland Sachsen"


def test_the_closer_name_wins_in_the_transliterated_form_too() -> None:
    """The tie-break reads the transliterated form as well: the umlaut is spelled out in the closer name.

    Both names score 90 and hold ``muenchen`` in the transliterated form. In the plain form the umlaut name is
    ``munchen``, a worse match (60.9) than the name that spells it out (61.5), so only the transliterated forms
    (66.7 against 61.5) put it first.
    """
    names = ["Bayern: Muenchen 1", "Bayern: München"]

    assert len({score for _, score in match_names("Muenchen", names, 0.8)}) == 1
    assert _order("Muenchen", names) == ["Bayern: München", "Bayern: Muenchen 1"]


def test_a_tie_on_both_keys_keeps_the_order_of_the_names() -> None:
    """Same score and the same closeness: the order the names were given in decides."""
    names = ["Kiel-B", "Kiel-A", "Kiel-C"]
    assert _order("Kiel", names) == names
    assert _order("Kiel", names[::-1]) == names[::-1]


def test_a_name_that_holds_the_whole_query_as_words_comes_before_one_that_scores_higher() -> None:
    """GH-4215: "Sachsen: Tiefland Sachsen" scores 95 for the query, above the 90 of the name that holds all of it."""
    names = ["Sachsen: Tiefland Sachsen", "Sachsen-Anhalt: Tiefland Sachsen-Anhalt"]
    scores = dict(match_names("Tiefland Sachsen-Anhalt", names, 0.8))
    assert scores[0] > scores[1], "the premise: WRatio alone ranks the part of another region first"
    assert _order("Tiefland Sachsen-Anhalt", names) == [names[1], names[0]]


def test_a_name_that_holds_the_query_always_reaches_the_threshold() -> None:
    """GH-4215: the length of a name keeps its WRatio under the threshold, and does not keep it from the result."""
    long_name = "Bayern: Bayern nördl. der Donau, o. Bayr. Wald, o. Mainfranken"
    assert dict(match_names("Bayern", [long_name], 0.8)) == {0: 80.0}, "the threshold is its score"
    assert [index for index, _ in match_names("Bayern", [long_name, "Hessen: Nord"], 0.8)] == [0]
    # the threshold stays a limit of the names that do not hold the query
    assert match_names("Bayern", ["Bayr. Wald", "Hessen"], 0.95) == []


def test_the_words_of_the_query_are_whole_and_consecutive() -> None:
    """A run of whole words: not a part of a word (Niedersachsen), not words with another word between them."""
    assert _order("Sachsen", ["Niedersachsen: Ost", "Sachsen-Anhalt: Harz"])[0] == "Sachsen-Anhalt: Harz"
    names = ["Anhalt Harz Sachsen", "Sachsen Harz Anhalt", "Sachsen-Anhalt"]
    assert _order("Sachsen Anhalt", names)[0] == "Sachsen-Anhalt"
    # the punctuation and the case of the query and of the names are the same to it
    assert _order("sachsen-anhalt", ["Hessen", "SACHSEN, Anhalt (Harz)"]) == ["SACHSEN, Anhalt (Harz)"]


def test_a_name_that_holds_the_query_in_the_transliterated_form_ranks_first() -> None:
    """The words are compared in the plain and in the transliterated form: "Köln" is `koeln` as well as `koln`."""
    names = ["Muenchen Land Koeln", "Koelner Strasse"]
    assert _order("Köln", names)[0] == "Muenchen Land Koeln"
    assert _order("koeln", names)[0] == "Muenchen Land Koeln"
    assert _order("Koln", ["Bonn Koln Land", "Koelner Strasse"])[0] == "Bonn Koln Land"


def test_the_phrase_rule_does_not_change_the_matches_of_a_query_that_is_a_word_of_no_name() -> None:
    """A query that is a word of no name has the matches it had; an empty one holds nothing."""
    names = ["Kiel-Holtenau", "Kielce", "Hamburg", None]
    assert [index for index, _ in match_names("Kiel", names, 0.8)] == [0, 1]
    assert match_names("-", names, 0.8) == []
    assert match_names("", names, 0.8) == []


def test_a_threshold_of_1_stays_exact_for_a_name_that_holds_the_query() -> None:
    """GH-4215: the phrase rule passes any threshold below 1; at 1 only the names that score 100 match."""
    kiel = ["Kiel-Holtenau", "Kiel", "Kiel-Kronshagen", "Hamburg"]
    assert _order("Kiel", kiel, 1.0) == ["Kiel"]
    assert _order("Kiel", kiel)[:3] == ["Kiel", "Kiel-Holtenau", "Kiel-Kronshagen"]

    bad = ["Boll, Bad", "Bad", "Bad Kissingen", "Aach, Bad Segeberg Nord Ost Sued West Station", "Hamburg"]
    assert _order("Bad", bad, 1.0) == ["Bad"]
    assert _order("Bad", bad, 0.99) != ["Bad"], "below 1 the names that hold the query are in"
    at_default = _order("Bad", bad)
    assert at_default[0] == "Bad"
    assert set(at_default) == set(bad[:4]), "the long name that holds it is in, Hamburg is not"
