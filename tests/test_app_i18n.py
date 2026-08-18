# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Test the app translation catalogs against what the backend actually serves.

The app labels every canonical parameter and every unit type in eleven languages. Nothing on
the app side can notice when a parameter or a unit type is *added here*: its own guard reads
the catalog and compares it against a number written down by hand, so a new entry upstream leaves
the catalog untouched, the guard passing, and the new name falling back to a prettified English id
in every language.

The direction that matters therefore has to be checked from here, where the additions happen.
Parsing the TypeScript with a regex is enough because these two files are generated in a fixed
`  key: 'label',` shape and the parity test on the app side keeps them that way.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from wetterdienst.api import Wetterdienst
from wetterdienst.metadata.parameter_table import PARAMETER_TABLE
from wetterdienst.model.unit import UnitConverter

APP = Path(__file__).parent.parent / "app"
GLOSSARY_EN = APP / "i18n" / "glossary" / "en.ts"
LOCALE_EN = APP / "i18n" / "locales" / "en.json"

pytestmark = pytest.mark.skipif(not APP.exists(), reason="app not part of this checkout")


def _record_keys(source: str, name: str) -> set[str]:
    """Return the keys of one `export const <name>` record in a glossary module."""
    block = source.split(f"export const {name}")[1].split("export const", maxsplit=1)[0]
    return set(re.findall(r"^ {2}'?([a-z0-9_]+)'?:", block, flags=re.MULTILINE))


def _settings_key(unit_type: str) -> str:
    """`energy_per_area` -> `unitEnergyPerArea`, the key `useUnitTypeLabel` builds."""
    return "unit" + re.sub(r"(?:^|_)(\w)", lambda match: match.group(1).upper(), unit_type)


def test_app_labels_every_canonical_parameter() -> None:
    """Every parameter the glossary endpoint serves must have an app label.

    `get_glossary` returns the whole of `PARAMETER_TABLE`, so adding a `CanonicalParameter` puts a
    new name in front of the user. Without a label it renders as its raw id with the underscores
    turned into spaces -- "Chlorid concentration" -- which reads as English in all eleven
    languages. Add the name to `app/i18n/glossary/*.ts`, in every locale.
    """
    labelled = _record_keys(GLOSSARY_EN.read_text(encoding="utf-8"), "parameters")
    served = {parameter.name for parameter in PARAMETER_TABLE}
    # the differences are named rather than asserted on directly: `assert not served - labelled`
    # makes pytest print both 514-element sets, which buries the one name that actually differs
    unlabelled = sorted(served - labelled)
    stale = sorted(labelled - served)
    assert not unlabelled, f"canonical parameters with no app label: {unlabelled}"
    assert not stale, f"app labels for parameters that are no longer served: {stale}"


def test_app_home_lists_every_provider() -> None:
    """The home page's provider list must be the registry's providers, exactly.

    The list is written out in `pages/index.vue` rather than fetched, because it is a static claim
    about what the app offers and not worth a request on the landing page. That makes it the one
    place in the app that can silently fall behind: a provider added here would keep serving
    data while the home page went on advertising the old set, and one removed would be advertised
    after it was gone. Neither is visible from the app's own tests, so it is checked here.
    """
    home = (APP / "app" / "pages" / "index.vue").read_text(encoding="utf-8")
    block = home.split("const providers = [")[1].split("]", maxsplit=1)[0]
    listed = set(re.findall(r"key: '([a-z]+)'", block))
    registered = set(Wetterdienst.registry)
    missing = sorted(registered - listed)
    stale = sorted(listed - registered)
    assert not missing, f"providers the home page does not mention: {missing}"
    assert not stale, f"providers the home page mentions but the registry does not have: {stale}"


def test_app_names_every_unit_type() -> None:
    """Every unit type the converter knows must have an app label.

    The glossary quantity filter and the Explorer unit rows name the quantity, and fall back to the
    raw id the same way. Add the label to `settings.unit*` in `app/i18n/locales/*.json`, in
    every locale -- the app parity test then holds the other ten to it.
    """
    settings = json.loads(LOCALE_EN.read_text(encoding="utf-8"))["settings"]
    missing = [unit_type for unit_type in UnitConverter().targets if not settings.get(_settings_key(unit_type))]
    assert not missing, f"unit types with no app label: {missing}"
