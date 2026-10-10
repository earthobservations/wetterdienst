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
`dwd/observation` and found them sound. `eaufrance/hubeau` is held at one resolution: its catalogue is made by reading
a station list for each of the resolutions it could be, which takes minutes. The providers that need a credential
(`aemet`, `knmi`, `metno`, `metoffice`) are held when the credential is set.
"""

from __future__ import annotations

import pytest

from tests.conftest import skip_if_upstream_unavailable
from tests.provider.station_catalogue import COUNTRY_BBOX, Accepted, assert_sound
from tests.provider.station_catalogue_stubs import (
    CHMI_NAME,
    DWD_NAMES,
    GHCN_DAILY_END,
    GHCN_NAMES,
    GHCN_NO_POSITION,
)
from wetterdienst import Wetterdienst

# the networks whose station list is not the same for every dataset of a resolution
_EVERY_DATASET = {"dwd/dmo", "dwd/mosmix"}
# the resolutions of a network that are held, where it is not every one
_RESOLUTIONS = {"eaufrance/hubeau": {"hourly"}}


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
    "fmi/observation": (
        Accepted(
            "coordinates_outside_country",
            "Antarktis Aboa is the Finnish research station in Antarctica",
            where=lambda row: row["station_id"] == "112275",
        ),
    ),
    "geosphere/observation": (
        Accepted(
            "date_in_the_future",
            "the list gives station 151 an end of 2026-11-30, its own date, which the library passes on",
            where=lambda row: row["station_id"] == "151",
        ),
    ),
    "noaa/ghcn": (GHCN_NO_POSITION, GHCN_NAMES, GHCN_DAILY_END),
    "wsv/pegel": (
        Accepted(
            "coordinates_missing",
            "PEGELONLINE publishes no position for these gauges, among them those of the Austrian Danube",
        ),
        Accepted(
            "coordinates_outside_country",
            "PEGELONLINE lists TIEL, a gauge on the Waal in the Netherlands",
            where=lambda row: row["station_id"] == "123456781",
        ),
    ),
}


def _cases() -> list[object]:
    cases = []
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            key = f"{provider}/{network}"
            try:
                api = Wetterdienst(provider, network)
            except ImportError:
                # an optional extra that is not installed
                cases.append(
                    pytest.param(
                        provider,
                        network,
                        "",
                        "",
                        marks=pytest.mark.skip(reason=f"{key} needs an extra that is not installed"),
                        id=f"{key} (not installed)",
                    )
                )
                continue
            metadata = getattr(api, "metadata", None)
            if metadata is None:  # radar and alerts have no station catalogue
                continue
            unconfigured = bool(metadata.auth) and not Wetterdienst.is_configured(api)
            for resolution in metadata:
                if key in _RESOLUTIONS and resolution.name not in _RESOLUTIONS[key]:
                    continue
                datasets = resolution.datasets if key in _EVERY_DATASET else resolution.datasets[:1]
                for dataset in datasets:
                    marks = [pytest.mark.skipif(unconfigured, reason=f"{key} needs its credential")]
                    if key == "eaufrance/hubeau":
                        marks.append(pytest.mark.slow)
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
    with skip_if_upstream_unavailable():
        stations = Wetterdienst(provider, network)(parameters=[(resolution, dataset)]).all().df
    assert_sound(
        stations,
        f"{key} {resolution}/{dataset}",
        bbox=COUNTRY_BBOX.get(key),
        accepted=ACCEPTED.get(key, ()),
        fail_on_stale=False,
    )
