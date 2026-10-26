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
from wetterdienst.model.metadata import Extent, MetadataModel, ProviderTerms

# the networks whose declared box reaches beyond the box of their country, with the reason: a station of the network
# is somewhere else (`COUNTRY_BBOX` of the same network says the rest: the box of the country it is accepted from)
BEYOND_THE_COUNTRY = {
    "fmi/observation": "Aboa, the Finnish research station in Antarctica, is in the list (FMI_ANTARCTICA)",
    "wsv/pegel": "TIEL, a gauge on the Waal in the Netherlands, is in the list (WSV_TIEL)",
}

ALL_CONTINENTS = sorted(CONTINENT_BOXES)


def _extents() -> dict[str, Extent]:
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
    assert all(isinstance(extent, Extent) for extent in extents.values())


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
        pytest.param({"scope": "national", "countries": ["DE", "FR"]}, "one country's", id="national-two"),
        pytest.param({"scope": "global"}, "is bound to no country|box of the Earth", id="global-one-country"),
        pytest.param(
            {"scope": "global", "countries": [], "bbox": [-180.0, -90.0, 180.0, 90.0]},
            "at least five continents",
            id="global-one-continent",
        ),
        pytest.param({"scope": "continental", "countries": []}, "Input should be", id="no-continental-scope"),
        pytest.param({"scope": "regional", "countries": []}, "", id="regional-one-continent-is-fine"),
        pytest.param({"scope": "regional", "countries": ["DE"]}, "which is a national one", id="regional-one-country"),
        pytest.param(
            {
                "scope": "regional",
                "continents": ALL_CONTINENTS,
                "countries": [],
                "bbox": [-180.0, -90.0, 180.0, 90.0],
            },
            "is a global one",
            id="regional-is-global",
        ),
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
        assert Extent.model_validate(declared).scope == "regional"
        return
    with pytest.raises(ValidationError, match=message):
        Extent.model_validate(declared)


def test_the_scope_is_what_the_continents_and_countries_say() -> None:
    """Across the registry: global has five continents and no country, national one country, regional not one."""
    for key, extent in _extents().items():
        if extent.scope == "global":
            assert len(extent.continents) >= 5, key
            assert extent.countries == [], key
        elif extent.scope == "regional":
            assert len(extent.countries) != 1, key
        else:
            assert len(extent.countries) == 1, key


def _datasets_with_an_extent() -> list[tuple[str, str, Any]]:
    """Give the datasets of the registry that declare an extent of their own: the network, the label and the extent."""
    found = []
    for key in _extents():
        if Wetterdienst.is_standalone(*key.split("/")):
            continue
        for resolution in Wetterdienst.resolve(*key.split("/")).metadata:
            found += [
                (key, f"{resolution.name}/{dataset.name}", dataset.extent)
                for dataset in resolution
                if dataset.extent is not None
            ]
    return found


def test_a_dataset_narrower_than_its_network_declares_its_own_extent() -> None:
    """`dwd/dmo` is global and its `icon_eu` list is Europe's; a dataset that declares none has its network's."""
    declared = {(key, label): extent for key, label, extent in _datasets_with_an_extent()}
    assert set(declared) == {("dwd/dmo", "hourly/icon_eu")}
    icon_eu = declared["dwd/dmo", "hourly/icon_eu"]
    assert icon_eu.scope == "regional"
    assert "europe" in icon_eu.continents
    assert Wetterdienst.resolve("dwd", "dmo").metadata.hourly.icon.extent is None


def test_the_extent_of_a_dataset_lies_within_its_network() -> None:
    """Across the registry; and the metadata model refuses a dataset extent that reaches beyond or is its network's."""
    extents = _extents()
    for key, label, extent in _datasets_with_an_extent():
        west, south, east, north = extents[key].bbox
        assert west <= extent.bbox[0], (key, label)
        assert south <= extent.bbox[1], (key, label)
        assert extent.bbox[2] <= east, (key, label)
        assert extent.bbox[3] <= north, (key, label)
        assert set(extent.continents) <= set(extents[key].continents), (key, label)

    declared = Wetterdienst.resolve("dwd", "dmo").metadata.model_dump()
    icon_eu = next(d for d in declared["resolutions"][0]["datasets"] if d["name"] == "icon_eu")
    with pytest.raises(ValidationError, match="not within the network"):
        MetadataModel.model_validate({**declared, "extent": _declared()})
    # a network of the extent of its dataset: the dataset has nothing of its own to say
    narrowed = {**declared, "extent": icon_eu["extent"]}
    with pytest.raises(ValidationError, match="which a dataset leaves out"):
        MetadataModel.model_validate(narrowed)


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


# the continents of a network are declared by hand, as the areas it is meant to serve, and are descriptive: a territory
# may be named or left out, and `bbox` and the station lists are the exact answer. The convention for an outlying
# territory is "named if the network has stations there": the table lists those that are named, with the continent
# and the reason, and `test_a_territory_is_named_where_the_convention_says` holds the declarations to it. For the
# border cases that no network names by itself, a station counts for the box it is in (`CONTINENT_BOXES`): Turkey east
# of 34 degrees east is Asia and Europe both, Turkey west of it and Cyprus are Europe, Russia is Europe west of 60
# degrees east and Asia east of 34, the Azores are Europe, Greenland and the Caribbean are North America, Guam and
# Hawaii are Oceania.
NAMED_TERRITORIES = {
    "aemet/observation": {
        "africa": "the Canary Islands, Ceuta and Melilla",
        "antarctica": "the Spanish bases (declared from documentation)",
    },
    "dmi/observation": {"north_america": "Greenland"},
    "eaufrance/hubeau": {
        "africa": "Reunion and Mayotte",
        "north_america": "Guadeloupe and Martinique",
        "south_america": "Guyane",
    },
    "fmi/observation": {"antarctica": "Aboa"},
    "ipma/observation": {"africa": "Madeira and the Selvagens"},
    "knmi/observation": {"north_america": "the Caribbean Netherlands"},
    "meteofrance/observation": {
        "africa": "Reunion, Mayotte",
        "antarctica": "Dumont d'Urville",
        "north_america": "the Antilles, Saint-Pierre-et-Miquelon",
        "oceania": "New Caledonia, Polynesia, Wallis",
        "south_america": "Guyane",
    },
    "meteofrance/synop": {
        "africa": "Reunion, Mayotte",
        "antarctica": "Dumont d'Urville",
        "north_america": "the Antilles, Saint-Pierre-et-Miquelon",
        "oceania": "New Caledonia, Polynesia, Wallis",
        "south_america": "Guyane",
    },
    "nws/observation": {"oceania": "Hawaii, Guam, American Samoa"},
}


@pytest.mark.parametrize("key", sorted(NAMED_TERRITORIES))
def test_a_territory_is_named_where_the_convention_says(key: str) -> None:
    """A network that has stations in an outlying territory names its continent, the same way for every network."""
    extent = _extents()[key]
    assert set(NAMED_TERRITORIES[key]) <= set(extent.continents), key


def test_the_continents_are_listed_in_alphabetical_order() -> None:
    """Every extent names its continents in the one order, which is the order of the schema's enumeration."""
    for key, extent in _extents().items():
        assert extent.continents == sorted(extent.continents), key


def _dmo_with(extent: dict[str, Any], dataset_extent: dict[str, Any]) -> dict[str, Any]:
    """Give the declaration of `dwd/dmo`, with the extents of its network and of its `icon_eu` dataset changed."""
    declared = Wetterdienst.resolve("dwd", "dmo").metadata.model_dump()
    datasets = [
        {**dataset, "extent": dataset_extent} if dataset["name"] == "icon_eu" else dataset
        for dataset in declared["resolutions"][0]["datasets"]
    ]
    return {**declared, "extent": extent, "resolutions": [{**declared["resolutions"][0], "datasets": datasets}]}


def test_a_dataset_of_a_national_network_is_national_and_of_the_providers_country() -> None:
    """`dwd/observation` is Germany's: a dataset of it is no regional one, and names no other country than DE."""
    german = _declared()
    narrower = {**german, "bbox": [6.0, 48.0, 14.0, 54.0]}
    assert MetadataModel.model_validate(_dmo_with(german, narrower)).extent.countries == ["DE"]
    for changes, message in [
        ({"scope": "regional", "countries": []}, "a dataset of a national network is national"),
        ({"countries": ["FR"]}, "national extent names"),
    ]:
        with pytest.raises(ValidationError, match=message):
            MetadataModel.model_validate(_dmo_with(german, {**narrower, **changes}))


def test_a_dataset_extent_that_is_the_networks_in_another_order_is_refused() -> None:
    """The comparison is of what the extents say, not of how their lists are ordered."""
    network = {
        "scope": "regional",
        "continents": ["asia", "europe"],
        "countries": [],
        "bbox": [-10.0, 20.0, 60.0, 70.0],
    }
    reordered = {**network, "continents": ["europe", "asia"]}
    with pytest.raises(ValidationError, match="which a dataset leaves out"):
        MetadataModel.model_validate(_dmo_with(network, reordered))
    assert Extent.model_validate(network).same_as(Extent.model_validate(reordered))


def test_a_standalone_network_is_held_to_the_country_of_its_provider() -> None:
    """`dwd/radar` has terms and no metadata model, and its national extent has to name the provider's country."""
    terms = Wetterdienst.resolve_standalone("dwd", "radar").terms
    assert terms.extent.countries == [terms.country_code]
    fields = {name: getattr(terms, name) for name in terms.__dataclass_fields__}
    with pytest.raises(ValueError, match="national extent names"):
        ProviderTerms(**{**fields, "extent": Extent.model_validate(_declared(countries=["FR"]))})


def test_an_extent_in_an_answer_is_short() -> None:
    """In JSON, no `countries` for a national or a country-less network, and a whole degree without its `.0`."""
    national = Extent.model_validate(_declared())
    assert national.model_dump()["countries"] == ["DE"]
    assert "countries" not in national.model_dump(mode="json")
    regional = Extent.model_validate(
        {"scope": "regional", "continents": ["europe"], "countries": ["DE", "FR"], "bbox": [-4.5, 42.0, 15.0, 55.0]}
    )
    assert regional.model_dump(mode="json")["countries"] == ["DE", "FR"]
    assert regional.model_dump_json().count('"bbox":[-4.5,42,15,55]') == 1
