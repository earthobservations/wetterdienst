# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The extent a network declares: where its stations are, which its provider's country does not say (GH-3456).

What is held here is the declaration: that every network has one, that its scope is what its countries, continents and
box say, and that a national network agrees with the box the catalogue rules hold its list to (`COUNTRY_BBOX`). That
the stations are where the declaration says is held to the station lists: the stubs of `test_station_catalogue_stubs.py`
offline and the live lists of `test_station_catalogues_live.py` (remote).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from tests.provider.station_catalogue import CONTINENT_BOXES, COUNTRY_BBOX
from wetterdienst import Wetterdienst
from wetterdienst.model.metadata import ExtentModel, MetadataModel

# the networks whose declared box reaches beyond the box of their country, with the reason: a station of the network
# is somewhere else (`COUNTRY_BBOX` of the same network says the rest: the box of the country it is accepted from)
BEYOND_THE_COUNTRY = {
    "fmi/observation": "Aboa, the Finnish research station in Antarctica, is in the list (FMI_ANTARCTICA)",
    "wsv/pegel": "TIEL, a gauge on the Waal in the Netherlands, is in the list (WSV_TIEL)",
}

ALL_CONTINENTS = sorted(CONTINENT_BOXES)


def _extents() -> dict[str, ExtentModel]:
    """Give the extent of every network of the registry, a standalone one by its terms."""
    extents = {}
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if Wetterdienst.is_standalone(provider, network):
                extents[f"{provider}/{network}"] = Wetterdienst.resolve_standalone(provider, network).terms.extent
            else:
                extents[f"{provider}/{network}"] = Wetterdienst.resolve(provider, network).metadata.extent
    return extents


def _declared(**changes: Any) -> dict[str, Any]:  # noqa: ANN401
    """Give the declaration of a network, with the fields changed."""
    return {**Wetterdienst.resolve("dwd", "observation").metadata.extent.model_dump(), **changes}


def test_every_network_declares_its_extent() -> None:
    """A network of the registry, standalone or not, has an extent, which `MetadataModel` requires."""
    extents = _extents()
    assert len(extents) == sum(len(networks) for networks in Wetterdienst.registry.values())
    assert all(isinstance(extent, ExtentModel) for extent in extents.values())


def test_a_declaration_without_its_extent_is_refused() -> None:
    """A new network cannot leave the question out: the metadata model does not build without it."""
    declared = Wetterdienst.resolve("dwd", "observation").metadata.model_dump()
    del declared["extent"]
    with pytest.raises(ValidationError, match="extent"):
        MetadataModel.model_validate(declared)


def test_a_national_network_is_in_the_country_of_its_provider() -> None:
    """A national extent names the country of the provider, which a metadata model holds it to."""
    declared = Wetterdienst.resolve("dwd", "observation").metadata.model_dump()
    declared["extent"] = _declared(countries=["FR"])
    with pytest.raises(ValidationError, match="national extent names"):
        MetadataModel.model_validate(declared)
    for key, extent in _extents().items():
        if extent.scope == "national" and not Wetterdienst.is_standalone(*key.split("/")):
            metadata = Wetterdienst.resolve(*key.split("/")).metadata
            assert extent.countries == [metadata.country_code], key


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        pytest.param({"scope": "national", "countries": []}, "names its one country", id="national-without-country"),
        pytest.param({"scope": "national", "countries": ["DE", "FR"]}, "names its one country", id="national-two"),
        pytest.param({"scope": "global"}, "is bound to no country|box of the Earth", id="global-one-country"),
        pytest.param(
            {"scope": "global", "countries": [], "bbox": [-180.0, -90.0, 180.0, 90.0]},
            "at least five continents",
            id="global-one-continent",
        ),
        pytest.param({"scope": "continental", "countries": []}, "", id="continental-is-fine"),
        pytest.param(
            {"scope": "continental", "continents": ["europe", "asia"], "countries": []}, "one continent", id="c2"
        ),
        pytest.param({"scope": "regional", "countries": []}, "two to four continents", id="regional-one-continent"),
        pytest.param({"continents": []}, "at least 1", id="no-continent"),
        pytest.param({"continents": ["europe", "europe"]}, "twice", id="continent-twice"),
        pytest.param({"continents": ["atlantis"]}, "Input should be", id="no-such-continent"),
        pytest.param({"countries": ["de"]}, "ISO 3166-1 alpha-2", id="code-lowercase"),
        pytest.param({"countries": ["DE", "DE"]}, "twice", id="country-twice"),
        pytest.param({"bbox": [1.0, 2.0, 3.0]}, "at least 4", id="bbox-short"),
        pytest.param({"bbox": [10.0, 40.0, 5.0, 50.0]}, "west <= east", id="bbox-west-of-east-reversed"),
        pytest.param({"bbox": [5.0, 50.0, 10.0, 40.0]}, "south <= north", id="bbox-south-north-reversed"),
        pytest.param({"bbox": [5.0, 40.0, 190.0, 50.0]}, "on Earth", id="bbox-off-earth"),
        pytest.param({"extra": 1}, "Extra inputs", id="extra-member"),
    ],
)
def test_an_extent_that_contradicts_itself_is_refused(changes: dict[str, Any], message: str) -> None:
    """The scope, the countries, the continents and the box are held to one another when the declaration is built."""
    declared = _declared(**changes)
    if not message:
        assert ExtentModel.model_validate(declared).scope == "continental"
        return
    with pytest.raises(ValidationError, match=message):
        ExtentModel.model_validate(declared)


def test_the_scope_is_what_the_continents_and_countries_say() -> None:
    """Across the registry: global has five continents or more, continental one, regional two to four."""
    for key, extent in _extents().items():
        if extent.scope == "global":
            assert len(extent.continents) >= 5, key
            assert extent.countries == [], key
        elif extent.scope == "continental":
            assert len(extent.continents) == 1, key
        elif extent.scope == "regional":
            assert 2 <= len(extent.continents) <= 4, key
        else:
            assert len(extent.countries) == 1, key


@pytest.mark.parametrize(("key", "box"), sorted(COUNTRY_BBOX.items()))
def test_a_national_network_has_the_box_its_catalogue_is_held_to(key: str, box: tuple[float, ...]) -> None:
    """The extent of a network the catalogue rules hold to the box of a country is that box, as `[w, s, e, n]`.

    `COUNTRY_BBOX` is `(south, north, west, east)`. A network with a station beyond its country is named with the
    reason in `BEYOND_THE_COUNTRY` and reaches farther, never less far.
    """
    south, north, west, east = box
    extent = _extents()[key]
    assert extent.scope == "national", key
    if key in BEYOND_THE_COUNTRY:
        declared_west, declared_south, declared_east, declared_north = extent.bbox
        assert declared_west <= west and declared_south <= south and declared_east >= east, key  # noqa: PT018
        assert declared_north >= north, key
        assert extent.bbox != [west, south, east, north], f"{key} no longer reaches beyond its country"
    else:
        assert extent.bbox == [west, south, east, north], key


def test_the_networks_that_reach_beyond_their_country_are_named() -> None:
    """An entry of `BEYOND_THE_COUNTRY` is a network that has a box of its country to reach beyond."""
    assert set(BEYOND_THE_COUNTRY) <= set(COUNTRY_BBOX)


def test_the_continents_of_a_network_are_where_its_box_is() -> None:
    """Each continent a network names has a box that meets the box of the network, and a global one is the Earth."""
    for key, extent in _extents().items():
        west, south, east, north = extent.bbox
        for continent in extent.continents:
            assert any(
                box_south <= north and box_north >= south and box_west <= east and box_east >= west
                for box_south, box_north, box_west, box_east in CONTINENT_BOXES[continent]
            ), f"{key} names {continent}, which its box does not reach"
        if extent.scope == "global":
            assert set(extent.continents) <= set(ALL_CONTINENTS), key


def test_the_dwd_forecast_networks_are_global_and_the_german_ones_national() -> None:
    """What the issue found: `dwd/mosmix` and `dwd/dmo` reach the world, and `dwd/observation` is Germany."""
    extents = _extents()
    assert extents["dwd/mosmix"].scope == extents["dwd/dmo"].scope == "global"
    assert extents["dwd/observation"].scope == "national"
    assert extents["dwd/observation"].countries == ["DE"]
    assert extents["noaa/ghcn"].scope == "global"
