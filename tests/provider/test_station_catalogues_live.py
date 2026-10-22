# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The live station catalogues break none of the catalogue rules (GH-2616).

The stubs of `test_station_catalogue_stubs.py` hold a reader to the rules on a few rows. What only the whole list shows
is here: a swapped pair of coordinates in row 10,000, an id listed twice by a source that changed, a station in the
wrong country. A rule a live list breaks by the source's own doing is named in `ACCEPTED` with its reason; one that
would hide a new defect is narrowed to the stations it is about. The gauges of `wsv/pegel` without a position cannot
be told from one that lost it, so that exception covers all of them.

This pass holds one catalogue per resolution of a provider and network, the first dataset of it, and every dataset of
the networks whose catalogue differs from one to the next. The one-time run of GH-2616 held all 62 datasets of
`dwd/observation` and found them sound. `eaufrance/hubeau` is not held here: its catalogue is made by reading a
station list for each of the resolutions it could be, which takes about 7 minutes, in every leg of the matrix; the
one-time run found it sound. The providers that need a credential (`aemet`, `knmi`, `metno`, `metoffice`) are held
when the credential is set.

The coverage rules (GH-3248), that a listed station has data and that every data file has a station, are held below for
the networks of `station_data_index.INDEXES` whose index is a directory listing or one file the catalogue pass reads
anyway, a dataset at a time.
The networks that are held in their stub only, and those that cannot be held, are named there with the reason.
"""

from __future__ import annotations

import pytest

from tests.provider.station_catalogue import COUNTRY_BBOX, Accepted, assert_covered, assert_sound
from tests.provider.station_catalogue_stubs import (
    CHMI_NAME,
    DWD_NAMES,
    EA_NO_POSITION,
    FMI_ANTARCTICA,
    GHCN_NAMES,
    GHCN_NO_POSITION,
    WSV_NO_POSITION,
    WSV_TIEL,
)
from tests.provider.station_data_index import (
    ACCEPTED_LIVE,
    INDEXES,
    NOT_HELD_DATASETS,
    NOT_LIVE,
    dataset_of,
)
from wetterdienst import Wetterdienst
from wetterdienst.ui.core import resolve_network

# the networks whose station list is not the same for every dataset of a resolution
_EVERY_DATASET = {"dwd/derived", "dwd/dmo", "dwd/mosmix"}
# the networks that are not held, with the reason
_NOT_HELD = {"eaufrance/hubeau": "building its catalogue takes minutes"}


ACCEPTED: dict[str, tuple[Accepted, ...]] = {
    "chmi/observation": (CHMI_NAME,),
    "dwd/derived": (
        Accepted(
            "coordinates_missing",
            "climate_correction_factor is listed per postal code, all 100,000 five-digit numbers, with no position",
            where=lambda row: row["dataset"] == "climate_correction_factor",
        ),
        Accepted(
            "name_empty",
            "climate_correction_factor is listed per postal code, all 100,000 five-digit numbers, with no name",
            where=lambda row: row["dataset"] == "climate_correction_factor",
        ),
    ),
    "dwd/dmo": (DWD_NAMES,),
    "dwd/mosmix": (DWD_NAMES,),
    "ea/hydrology": (EA_NO_POSITION,),
    "fmi/observation": (FMI_ANTARCTICA,),
    "geosphere/observation": (
        Accepted(
            "date_in_the_future",
            "the list gives station 151 an end of 2026-11-30, its own date, which the library passes on",
            where=lambda row: row["station_id"] == "151",
        ),
    ),
    "metno/frost": (
        Accepted(
            "coordinates_missing",
            "24 of the 2235 SensorSystem sources have no geometry and no position in any other field: ships, "
            "rigs and gliders (SN76999 SCARABEO 8, SN20930 POLARSTERN, SN20957 SG644 GLIDER), 20 with "
            "shipCodes, which move; they stay in the list and no search picks them (GH-2655)",
        ),
    ),
    "noaa/ghcn": (GHCN_NO_POSITION, GHCN_NAMES),
    "wsv/pegel": (WSV_NO_POSITION, WSV_TIEL),
}


def _cases() -> list[object]:
    cases = []
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            key = f"{provider}/{network}"
            if key in _NOT_HELD:
                continue
            try:
                api = resolve_network(provider, network)
            except ImportError as error:
                cases.append(
                    pytest.param(
                        provider,
                        network,
                        "",
                        "",
                        marks=pytest.mark.skip(reason=f"{key} cannot be imported: {error}"),
                        id=f"{key} (cannot be imported)",
                    )
                )
                continue
            metadata = getattr(api, "metadata", None)
            if metadata is None:  # radar and alerts have no station catalogue
                continue
            unconfigured = bool(metadata.auth) and not Wetterdienst.is_configured(api)
            for resolution in metadata:
                datasets = resolution.datasets if key in _EVERY_DATASET else resolution.datasets[:1]
                for dataset in datasets:
                    marks = [pytest.mark.skipif(unconfigured, reason=f"{key} needs its credential")]
                    cases.append(
                        pytest.param(
                            provider,
                            network,
                            resolution.name,
                            dataset.name,
                            marks=marks,
                            id=f"{key} {resolution.name}/{dataset.name}",
                        ),
                    )
    return cases


@pytest.mark.remote
@pytest.mark.parametrize(("provider", "network", "resolution", "dataset"), _cases())
def test_a_live_catalogue_is_sound(provider: str, network: str, resolution: str, dataset: str) -> None:
    """Hold the whole live station list to the rules, naming the provider, station and rule that fails."""
    key = f"{provider}/{network}"
    stations = Wetterdienst.resolve(provider, network)(parameters=[(resolution, dataset)]).all().df
    assert_sound(
        stations,
        f"{key} {resolution}/{dataset}",
        bbox=COUNTRY_BBOX.get(key),
        accepted=ACCEPTED.get(key, ()),
        fail_on_stale=False,
    )


def _coverage_cases() -> list[object]:
    cases = []
    for key in INDEXES:
        if key in NOT_LIVE:
            continue
        provider, network = key.split("/")
        for resolution in resolve_network(provider, network).metadata:
            for dataset in resolution.datasets:
                if f"{key} {resolution.name}/{dataset.name}" in NOT_HELD_DATASETS:
                    continue
                cases.append(
                    pytest.param(key, resolution.name, dataset.name, id=f"{key} {resolution.name}/{dataset.name}")
                )
    return cases


@pytest.mark.remote
@pytest.mark.parametrize(("key", "resolution", "dataset"), _coverage_cases())
def test_a_live_catalogue_has_its_data(key: str, resolution: str, dataset: str) -> None:
    """Hold the live station list to the data files beside it, naming the provider, station and rule that fails."""
    provider, network = key.split("/")
    request = Wetterdienst.resolve(provider, network)(parameters=[(resolution, dataset)])
    index = INDEXES[key]
    assert_covered(
        request.all().df,
        index.ids(request.settings, dataset_of(key, resolution, dataset)),
        f"{key} {resolution}/{dataset}",
        accepted=ACCEPTED_LIVE.get(key, ()),
        rules=index.rules,
        fail_on_stale=False,
    )
