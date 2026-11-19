# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Matching a station name the way a person writes it: without regard to case, diacritics or transliteration.

A name is folded to two forms before it is scored, the query and the station names alike, and the better
of the two scores counts (`match_names`):

- the *plain* form drops the accent: ``Köln`` -> ``koln``, ``Düsseldorf`` -> ``dusseldorf``,
  ``Łódź`` -> ``lodz``, ``Tromsø`` -> ``tromso``, ``Straße`` -> ``strasse``;
- the *transliterated* form spells the umlaut and the Nordic letters out: ``Köln`` -> ``koeln``,
  ``Düsseldorf`` -> ``duesseldorf``, ``Århus`` -> ``aarhus``, ``Tromsø`` -> ``tromsoe``.

The two forms are compared like with like, so ``koeln`` finds ``Köln`` through the transliterated form,
``Koln`` through the plain one, and ``Köln`` both: an umlaut written ``oe`` and an umlaut dropped are the
two ways a German name is typed without one. No dependency: ``unicodedata`` takes the accents off, a small
table covers the letters that do not decompose (``ß``, ``ø``, ``ł``, ``đ``, ``æ``, ...).
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

from rapidfuzz import fuzz, process
from rapidfuzz import utils as fuzz_utils

if TYPE_CHECKING:
    from collections.abc import Sequence

# letters that Unicode does not decompose into a base letter and a mark, to the letters they are written with
# when the accent is dropped (casefolding already makes ``ß`` ``ss``)
_PLAIN = str.maketrans(
    {
        "ø": "o",
        "đ": "d",
        "ð": "d",
        "ł": "l",
        "ħ": "h",
        "\u0131": "i",  # dotless i
        "ŧ": "t",
        "ĸ": "k",
        "æ": "ae",
        "œ": "oe",
        "þ": "th",
    },
)

# the same letters as they are spelled out where the accent cannot be typed: the German umlaut and the Nordic
# ``å``/``ø``; applied before the accents are taken off, as ``ä`` would otherwise be ``a``
_SPELLED = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "å": "aa", "ø": "oe"})


def _strip_marks(text: str) -> str:
    """Return the text without its combining marks (``é`` -> ``e``), after the compatibility decomposition."""
    return "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char))


def fold_name(name: str) -> tuple[str, str]:
    """Fold a name to its plain and its transliterated form, both case-folded.

    >>> fold_name("Köln")
    ('koln', 'koeln')
    >>> fold_name("Łódź")
    ('lodz', 'lodz')
    """
    if name.isascii():
        folded = name.casefold()
        return folded, folded
    composed = unicodedata.normalize("NFC", name).casefold()
    return _strip_marks(composed.translate(_PLAIN)), _strip_marks(composed.translate(_SPELLED).translate(_PLAIN))


def _scores(query: str, choices: Sequence[str | None], cutoff: float) -> dict[int, float]:
    """Return the WRatio of the query against each choice that reaches the cutoff, by index."""
    return {
        index: score
        for _, score, index in process.extract(
            query=query,
            choices=choices,
            scorer=fuzz.WRatio,
            score_cutoff=cutoff,
            processor=fuzz_utils.default_process,
            limit=None,
        )
    }


def _closeness(
    query_plain: str,
    query_spelled: str,
    folded: Sequence[tuple[str, str] | None],
    matched: dict[int, float],
) -> dict[int, float]:
    """Return how close each matched name is to the query as a whole: ``fuzz.ratio``, the better form.

    It is the tie-break among equal ``WRatio`` scores, so it is only taken of the names that matched.
    """
    closeness: dict[int, float] = {}
    for index in matched:
        pair = folded[index]
        if pair is None:  # a null name never matches, so never gets here
            continue
        closeness[index] = max(
            fuzz.ratio(query_plain, pair[0], processor=fuzz_utils.default_process),
            fuzz.ratio(query_spelled, pair[1], processor=fuzz_utils.default_process),
        )
    return closeness


def _tokens(text: str) -> str:
    """Return the text as the scorers read it, its words one space apart: ``Sachsen-Anhalt`` -> ``sachsen anhalt``."""
    return " ".join(fuzz_utils.default_process(text).split())


def _holds_phrase(query: str, choices: Sequence[str | None]) -> set[int]:
    """Return the indices of the choices that hold the query as a run of whole words (both already folded).

    ``sachsen anhalt`` is a run of ``sachsen anhalt tiefland sachsen anhalt`` and ``sachsen`` is one of
    ``sachsen anhalt tiefland``, but not of ``niedersachsen``: the words are compared whole, and the run is
    of consecutive words.
    """
    phrase = _tokens(query)
    if not phrase:
        return set()
    first = phrase.split(maxsplit=1)[0]
    padded = f" {phrase} "
    return {
        index
        for index, choice in enumerate(choices)
        # the cheap test first: only a name that holds the letters of the first word is read word by word
        if choice is not None and first in choice and padded in f" {_tokens(choice)} "
    }


def match_names(query: str, names: Sequence[str | None], threshold: float) -> list[tuple[int, float]]:
    """Score the names against the query, best match first: a name that holds it whole, then the rest.

    The score is rapidfuzz's ``WRatio`` (a weighted composite of ratio, partial, token-sort and token-set
    ratio, so that a short place name matches a longer station name: ``Kiel`` -> ``Kiel-Holtenau``) of the
    folded names, the better of the plain and the transliterated form. A name that is null never matches.

    A name that holds the whole query as a run of whole words (``Tiefland Sachsen-Anhalt`` in ``Sachsen-Anhalt:
    Tiefland Sachsen-Anhalt``, ``Bayern`` in ``Bayern: Mainfranken``, but not ``Sachsen`` in ``Niedersachsen``)
    reaches any threshold below 1 and comes before every name that does not: ``WRatio`` alone ranks a name
    that only shares words with the query (``Sachsen: Tiefland Sachsen``) above one that holds all of it, and
    a long name that holds it (``Bayern: Bayern nördl. der Donau, o. Bayr. Wald, o. Mainfranken``) misses
    the threshold. The words are those of ``default_process``, compared in the plain and in the transliterated
    form like the score. A name that holds the query is ordered by its own ``WRatio`` however low, and is
    reported with the threshold as its score where that is less: this score is no ``WRatio``, and scores are
    not monotone across the two groups (a phrase name reported with 80 comes before a name of 95). A threshold
    of 1 stays exact: the rule is off, and only the names scoring 100 match, in the order they had. A short
    query on a big catalogue (``San`` among 130,000 names) so lists more names than before, the long ones that
    hold it as a word (``Ost`` admits ``Ost Mittelgebirgsbereichsstation``), which costs a caller nothing:
    ``filter_by_name`` keeps the best ``rank`` stations.

    Within each of the two groups, ``WRatio`` gives every name that holds a short query the same score (90, the
    partial ratio weighted down), so among equal scores the name closer to the query as a whole comes first, by
    ``fuzz.ratio`` of the same folded forms (``Saarland`` -> ``Rheinland-Pfalz und Saarland: Saarland`` before
    ``Rheinland-Pfalz und Saarland: Rhein, Pfalz, Nahe und Mosel``). Only a tie on both is left in the order of
    the names.

    Args:
        query: The name asked for.
        names: The names to match it against, nulls allowed.
        threshold: The least score, from 0 to 1, a name must reach (a name that holds the query as words reaches
            any below 1).

    Returns:
        The index into ``names`` and the score (0 to 100) of every name that reaches the threshold.

    """
    cutoff = threshold * 100
    query_plain, query_spelled = fold_name(query)
    folded = [None if name is None else fold_name(name) for name in names]
    plain = [None if pair is None else pair[0] for pair in folded]
    best = _scores(query_plain, plain, cutoff)
    # a threshold of 1 asks for the exact name: the rule admits nothing there
    exact = cutoff >= 100
    whole = set() if exact else _holds_phrase(query_plain, plain)
    # nothing differs between the forms of a name without an accent, and of a query without one: the
    # second pass would give the first one's answer
    if query_spelled != query_plain or any(pair is not None and pair[0] != pair[1] for pair in folded):
        spelled = [None if pair is None else pair[1] for pair in folded]
        for index, score in _scores(query_spelled, spelled, cutoff).items():
            best[index] = max(score, best.get(index, 0.0))
        if not exact:
            whole |= _holds_phrase(query_spelled, spelled)
    # the score a name that holds the query has, where it is under the threshold: for the order among them
    for index in whole - best.keys():
        pair = folded[index]
        if pair is not None:
            best[index] = max(
                fuzz.WRatio(query_plain, pair[0], processor=fuzz_utils.default_process),
                fuzz.WRatio(query_spelled, pair[1], processor=fuzz_utils.default_process),
            )
    closeness = _closeness(query_plain, query_spelled, folded, best)
    ranked = sorted(best.items(), key=lambda match: (match[0] not in whole, -match[1], -closeness[match[0]], match[0]))
    return [(index, max(score, cutoff) if index in whole else score) for index, score in ranked]
