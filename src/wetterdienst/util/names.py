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


def match_names(query: str, names: Sequence[str | None], threshold: float) -> list[tuple[int, float]]:
    """Score the names against the query, best match first, equal scores in the order of the names.

    The score is rapidfuzz's ``WRatio`` (a weighted composite of ratio, partial, token-sort and token-set
    ratio, so that a short place name matches a longer station name: ``Kiel`` -> ``Kiel-Holtenau``) of the
    folded names, the better of the plain and the transliterated form. A name that is null never matches.

    Args:
        query: The name asked for.
        names: The names to match it against, nulls allowed.
        threshold: The least score, from 0 to 1, a name must reach.

    Returns:
        The index into ``names`` and the score (0 to 100) of every name that reaches the threshold.

    """
    cutoff = threshold * 100
    query_plain, query_spelled = fold_name(query)
    folded = [None if name is None else fold_name(name) for name in names]
    best = _scores(query_plain, [None if pair is None else pair[0] for pair in folded], cutoff)
    # nothing differs between the forms of a name without an accent, and of a query without one: the
    # second pass would give the first one's answer
    if query_spelled != query_plain or any(pair is not None and pair[0] != pair[1] for pair in folded):
        spelled = [None if pair is None else pair[1] for pair in folded]
        for index, score in _scores(query_spelled, spelled, cutoff).items():
            best[index] = max(score, best.get(index, 0.0))
    return sorted(best.items(), key=lambda match: (-match[1], match[0]))
