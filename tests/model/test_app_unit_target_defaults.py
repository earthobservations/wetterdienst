"""The app's catalogue of unit targets (app/app/utils/unit-targets.ts) is held to what the backend converts to."""

import json
from pathlib import Path

import pytest

from wetterdienst.model.unit import UnitConverter

FIXTURE = Path(__file__).parents[2] / "app" / "tests" / "unit" / "unit-target-defaults.json"
CATALOGUE = json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def converter() -> UnitConverter:
    """Return the backend's converter, with its own default targets."""
    return UnitConverter()


@pytest.mark.parametrize("unit_type", sorted(CATALOGUE))
def test_app_default_is_the_backends_default(converter: UnitConverter, unit_type: str) -> None:
    """The unit the app starts a type in is the one the backend converts to where a request names none."""
    assert CATALOGUE[unit_type]["default"] == converter.targets[unit_type].name


@pytest.mark.parametrize("unit_type", sorted(CATALOGUE))
def test_app_units_are_units_of_the_type(converter: UnitConverter, unit_type: str) -> None:
    """Every unit the app offers for a type is one the backend has for it (the app may offer fewer)."""
    backend = {unit.name for unit in converter.units[unit_type]}
    assert set(CATALOGUE[unit_type]["units"]) <= backend
    assert CATALOGUE[unit_type]["default"] in CATALOGUE[unit_type]["units"]
