# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Selecting stations by the ``region`` their provider lists them under (GH-4418).

``region`` is a column of every stations frame (`wetterdienst.model.schema.STATIONS_SCHEMA`): the sub-national unit
*the source* names, whatever it is called there, null where the source names none. What it holds differs by provider
(DWD's federal state written out, ``Hamburg``; the two letters of the same state on ``dwd/road``, ``HH``; Météo-France's
département number; Hub'Eau's département in capitals, ``FINISTERE``; Environment Canada's province, ``BC``), and a
station is in the region its provider puts it in, which is not always where it stands: DWD's ``Hamburg`` also holds a
lightship, a platform and a buoy in the North Sea. The region is the source's, and so is the spelling: ``Hesse`` is
not ``Hessen`` and no table of names in other languages stands between the two, since a table would have to be right
for every provider.

A region asked for is compared with the ones the list has the way a name is, whole (not fuzzily): without regard to
case, accents or transliteration, and with a hyphen, an apostrophe or a space counting as the same break between words
(`wetterdienst.util.names.fold_name`). ``hamburg``, ``HAMBURG`` and ``Hamburg`` are one region, ``Baden Wuerttemberg``
and ``Baden-Württemberg`` are one, ``Cotes d'Armor`` is ``COTES-D'ARMOR``. A region the list does not have is refused
with the closest ones, if there are any, and the regions there are (a few, with the number of the others); a network
whose list has none is refused with that reason. Neither is an answer without stations, which a caller could not tell
from a region without stations in the window.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from rapidfuzz import fuzz, process
from rapidfuzz import utils as fuzz_utils

from wetterdienst.exceptions import NoRegionsError, UnknownRegionError
from wetterdienst.util.names import fold_name

if TYPE_CHECKING:
    from collections.abc import Iterable

#: how many of the regions there are a refusal names: a list of 164 municipalities (FMI) is no help in a sentence, and
#: the closest ones come first in any case
MAX_REGIONS_NAMED = 20
#: how long a region is written in a refusal; the source's own names are short, a name beyond this is cut
_MAX_NAME_LENGTH = 60
#: the least `WRatio` of a region to be offered as the one meant
_HINT_CUTOFF = 70.0
#: how many close regions are offered
_MAX_HINTS = 3


def _words(text: str) -> str:
    """Give the text as the scorers read it, in lower case with its words one space apart."""
    return " ".join(fuzz_utils.default_process(text).split())


def region_keys(region: str) -> tuple[str, str]:
    """Give the two forms a region is compared in: the plain and the transliterated one, folded to words.

    ``Baden-Württemberg`` is ``("baden wurttemberg", "baden wuerttemberg")``: the first matches ``Baden Wurttemberg``
    and the second ``Baden Wuerttemberg``, as `fold_name` does for a station name.
    """
    plain, spelled = fold_name(region)
    return _words(plain), _words(spelled)


def search_regions(regions: str | Sequence[str]) -> list[str]:
    """Read the regions of a search: a text or a sequence of texts, each stripped, none empty, each named once.

    A text is one region, whatever it holds: a comma is no separator here (the command line, the REST API and MCP
    split a list at it before they come here).

    Raises:
        TypeError: a region is not a text.
        ValueError: no region is named, or one is blank.

    """
    if not isinstance(regions, str) and not isinstance(regions, Sequence):
        msg = f"region has to be a text or a sequence of texts, got {type(regions).__name__} {regions!r}"
        raise TypeError(msg)
    items = [regions] if isinstance(regions, str) else list(regions)
    found: list[str] = []
    for item in items:
        if not isinstance(item, str):
            msg = f"region has to be a text, got {type(item).__name__} {item!r}"
            raise TypeError(msg)
        text = item.strip()
        if not text:
            msg = "a region is blank; name the region as the `region` column of the stations writes it"
            raise ValueError(msg)
        found.append(text)
    if not found:
        msg = "region names no region"
        raise ValueError(msg)
    return list(dict.fromkeys(found))


def _shown(name: str) -> str:
    return name if len(name) <= _MAX_NAME_LENGTH else f"{name[: _MAX_NAME_LENGTH - 1]}…"


def _list_of(names: Sequence[str]) -> str:
    shown = ", ".join(_shown(name) for name in names[:MAX_REGIONS_NAMED])
    return shown if len(names) <= MAX_REGIONS_NAMED else f"{shown} and {len(names) - MAX_REGIONS_NAMED} more"


def select_regions(known: Iterable[str | None], asked: Sequence[str], *, network: str) -> list[str]:
    """Give the regions of the list that the regions asked for are, each as the list writes it.

    Args:
        known: the ``region`` of every station of the list, nulls and repeats included.
        asked: the regions asked for, as `search_regions` read them.
        network: the name of the network, for a refusal.

    Raises:
        NoRegionsError: the list names no region at all.
        UnknownRegionError: a region asked for is none of the list's. It names every one that is not, with the
            closest regions of the list to each, and the regions there are.

    """
    names = sorted({name.strip() for name in known if name and name.strip()}, key=lambda name: (name.casefold(), name))
    if not names:
        msg = (
            f"{network} lists no region: the stations of this network have no `region`, so none can be selected by "
            "it. Select the stations by `name`, a point or a bounding box instead."
        )
        raise NoRegionsError(msg)
    keys_of = {name: region_keys(name) for name in names}
    by_key: dict[str, list[str]] = {}
    for name, keys in keys_of.items():
        for key in dict.fromkeys(keys):
            by_key.setdefault(key, []).append(name)
    matched: dict[str, None] = {}
    unknown: list[str] = []
    for region in asked:
        found = [name for key in dict.fromkeys(region_keys(region)) for name in by_key.get(key, [])]
        if not found:
            unknown.append(region)
        matched.update(dict.fromkeys(found))
    if unknown:
        raise _unknown(unknown, names, keys_of, network)
    return list(matched)


def _unknown(
    unknown: Sequence[str], names: Sequence[str], keys_of: dict[str, tuple[str, str]], network: str
) -> UnknownRegionError:
    """Build the refusal of regions the list does not have: which, the closest ones, and the regions there are."""
    plain = [keys_of[name][0] for name in names]
    hints: dict[str, list[str]] = {}
    for region in unknown:
        close = process.extract(
            region_keys(region)[0], plain, scorer=fuzz.WRatio, score_cutoff=_HINT_CUTOFF, limit=_MAX_HINTS
        )
        if close:
            hints[region] = [names[index] for _, _, index in close]
    which = ", ".join(f"'{_shown(region)}'" for region in unknown)
    head = f"{network} has no station in the region{'s' if len(unknown) > 1 else ''} {which}."
    if hints:
        guessed = "; ".join(
            f"'{_shown(region)}': " + " or ".join(f"'{_shown(name)}'" for name in close)
            for region, close in hints.items()
        )
        head += f" Closest: {guessed}."
    message = f"{head} The regions there are: {_list_of(names)}."
    return UnknownRegionError(message, unknown=list(unknown), known=list(names), hints=hints)
