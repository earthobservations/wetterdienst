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
