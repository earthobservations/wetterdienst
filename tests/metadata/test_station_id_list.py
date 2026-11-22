# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The `station_id_list` a network declares is the list it fills the ids of (GH-4075).

The search for a WMO, WIGOS or ICAO id asks every network that declares the list to look the ids up in. The declaration
is held to the stub of that list (the rows of the real catalogue, served through the network's own reader), so that a
network that starts to publish an id, or stops, or a list renamed, fails here and is not found out by a search that
misses a station. The page that tells the lists to a person is held to the declarations too.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.provider.station_catalogue_stubs import STUBS, Stub
from wetterdienst import Wetterdienst
from wetterdienst.model.metadata import StationIdList, build_metadata_model
from wetterdienst.provider.rmi.observation.metadata import _RmiObservationMetadataSpec

ID_COLUMNS = ("wmo_id", "wigos_id", "icao_id")
PAGE = Path(__file__).parents[2] / "docs" / "usage" / "station_ids.md"


def _declarations() -> dict[str, StationIdList]:
    """Give the declared list of every network that has one, by `provider/network`."""
    declared = {}
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if Wetterdienst.is_standalone(provider, network):
                continue
            declaration = Wetterdienst.resolve(provider, network).metadata.station_id_list
            if declaration is not None:
                declared[f"{provider}/{network}"] = declaration
    return declared


DECLARED = _declarations()


def _split(stub: Stub) -> tuple[str, str]:
    """Give the network and the `resolution/dataset` of a stub's catalogue."""
    network, label = stub.catalogue.split(" ")
    return network, label


def _filled(stub: Stub, monkeypatch: pytest.MonkeyPatch) -> tuple[str, ...]:
    """Give the id columns the stations of a stub fill, in the order of `ID_COLUMNS`."""
    stations = stub.build(monkeypatch)
    return tuple(column for column in ID_COLUMNS if stations.get_column(column).is_not_null().any())


def test_the_networks_that_declare_a_list_are_the_ones_the_search_was_decided_for() -> None:
    """Fifteen networks with no key and three with one, as the survey of the issue found them."""
    assert sorted(DECLARED) == sorted(
        [
            "aemet/observation",
            "chmi/observation",
            "dmi/observation",
            "dwd/derived",
            "dwd/dmo",
            "dwd/mosmix",
            "dwd/observation",
            "dwd/poi",
            "eccc/observation",
            "fmi/observation",
            "geosphere/observation",
            "knmi/observation",
            "meteofrance/synop",
            "meteoswiss/observation",
            "metno/frost",
            "noaa/ghcn",
            "nws/observation",
            "rmi/observation",
        ]
    )
    keyed = {name for name in DECLARED if Wetterdienst.resolve(*name.split("/")).metadata.auth}
    assert keyed == {"aemet/observation", "knmi/observation", "metno/frost"}


@pytest.mark.parametrize("name", sorted(DECLARED))
def test_a_declared_list_has_a_stub_that_fills_exactly_its_columns(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The columns a network declares are the ones the stations of its declared list carry, no more and no fewer."""
    declared = DECLARED[name]
    label = f"{declared.resolution}/{declared.dataset}"
    stubs = [stub for stub in STUBS if _split(stub) == (name, label)]

    assert stubs, f"{name} declares {label}, of which there is no stub of the catalogue to hold it to"
    for stub in stubs:
        assert _filled(stub, monkeypatch) == tuple(column for column in ID_COLUMNS if column in declared.ids), (
            f"{name} {label}: the stations fill other ids than the declaration says"
        )


@pytest.mark.parametrize("stub", STUBS, ids=lambda stub: stub.catalogue)
def test_a_network_that_fills_an_id_declares_it(stub: Stub, monkeypatch: pytest.MonkeyPatch) -> None:
    """A network no search asks has no id on the stations of its stubs, whichever list; a declared one fills its own."""
    network, label = _split(stub)
    filled = _filled(stub, monkeypatch)
    declared = DECLARED.get(network)
    if declared is None:
        assert filled == (), f"{stub.catalogue} fills {list(filled)}: declare `station_id_list` for {network}"
    elif label != f"{declared.resolution}/{declared.dataset}":
        # another list of a network that declares one: it may fill other ids, which the search does not read
        assert set(filled) <= set(ID_COLUMNS)


@pytest.mark.parametrize(
    ("resolution", "dataset", "known"),
    [
        pytest.param("daily", "no_such_dataset", "datasets", id="dataset"),
        pytest.param("no_such_resolution", "data", "resolutions", id="resolution"),
    ],
)
def test_a_declaration_names_a_resolution_and_a_dataset_the_network_has(
    resolution: str, dataset: str, known: str
) -> None:
    """A list the network does not have is refused when the metadata is built, naming what it has."""
    spec = {
        **_RmiObservationMetadataSpec,
        "station_id_list": {"resolution": resolution, "dataset": dataset, "ids": ["wmo_id"]},
    }

    with pytest.raises(ValueError, match=f"station_id_list.*{known}"):
        build_metadata_model(spec, "TestMetadata")


def test_the_spec_with_a_real_list_builds() -> None:
    """The check above is not one that refuses everything."""
    spec = {
        **_RmiObservationMetadataSpec,
        "station_id_list": {"resolution": "daily", "dataset": "data", "ids": ["wmo_id"]},
    }

    assert build_metadata_model(spec, "TestMetadata").station_id_list == StationIdList(
        resolution="daily", dataset="data", ids=("wmo_id",)
    )


def test_a_declaration_names_each_id_once_and_at_least_one() -> None:
    """The columns are three, and an empty or a repeated one is no declaration."""
    with pytest.raises(ValueError, match="more than once"):
        StationIdList(resolution="daily", dataset="data", ids=("wmo_id", "wmo_id"))
    with pytest.raises(ValueError, match="at least 1"):
        StationIdList(resolution="daily", dataset="data", ids=())
    with pytest.raises(ValueError, match="wmo_id"):
        StationIdList(resolution="daily", dataset="data", ids=("station_id",))  # ty: ignore[invalid-argument-type]


def test_the_page_tells_the_lists_the_networks_declare() -> None:
    """The table of `docs/usage/station_ids.md` is the declarations: the same networks, lists and id columns."""
    rows = {}
    for line in PAGE.read_text(encoding="utf8").splitlines():
        found = re.match(r"^\| `([a-z]+/[a-z_]+)`(?: \(key\))? \| `([a-z0-9_]+/[a-z_]+)`[^|]*\| (`[^|]*`) \|$", line)
        if found:
            rows[found.group(1)] = (found.group(2), tuple(re.findall(r"`([a-z_]+)`", found.group(3))))

    assert rows == {
        name: (f"{declared.resolution}/{declared.dataset}", declared.ids) for name, declared in DECLARED.items()
    }
