"""A name a source gives two parameters is humanized to the right one for each (GH-3605).

The name the source gives a parameter (`name_original`) is only unique within a dataset of a resolution: chmi's `T` is
`temperature_air_2m` at 10 minutes and `temperature_air_mean_2m` daily. The mapping from the one to the other has to be
looked up on the resolution and the dataset as well, or a request that asks for both gets some readings under the
other's name. This holds every such name in the metadata of every provider to that, so a new one is covered without a
test of its own.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, NamedTuple

import polars as pl
import pytest

from wetterdienst import Wetterdienst
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from wetterdienst.model.values import TimeseriesValues

#: a credential of each provider that wants one, so that a request can be made without a call
_AUTH = {"aemet": "stub", "knmi": "stub", "metno_frost": ("stub", "stub"), "ceda": ("stub", "stub")}


class Entry(NamedTuple):
    """One parameter that carries a shared name: where it is declared and what it is called."""

    resolution: str
    dataset: str
    name: str


def _shared_names() -> dict[tuple[str, str, str], list[Entry]]:
    """Give, per provider, network and `name_original`, the parameters that carry it, for the names that differ."""
    shared: dict[tuple[str, str, str], list[Entry]] = {}
    for provider, networks in sorted(Wetterdienst.registry.items()):
        for network in sorted(networks):
            if Wetterdienst.is_standalone(provider, network):
                continue
            found: dict[str, list[Entry]] = defaultdict(list)
            for resolution in Wetterdienst.resolve(provider, network).metadata:
                for dataset in resolution:
                    for parameter in dataset:
                        found[parameter.name_original].append(
                            Entry(resolution.name, dataset.name.lower(), parameter.name)
                        )
            for name_original, entries in found.items():
                if len({entry.name for entry in entries}) > 1:
                    shared[provider, network, name_original] = entries
    return shared


SHARED = _shared_names()

#: the names the issue found by hand (GH-3605); the scan must find at least these
FOUND_BY_HAND = {
    ("chmi", "observation"): {"T", "H", "P", "F", "TMA", "TMI"},
    ("geosphere", "observation"): {"p", "sh", "tsmin", "tl_mittel"},
    ("meteofrance", "observation"): {"TN", "TX"},
    ("aemet", "observation"): {"hr"},
}


def _values(provider: str, network: str, entries: list[Entry]) -> TimeseriesValues:
    """Stand a values object up for the parameters, without a station and without a call."""
    request = Wetterdienst.resolve(provider, network)(
        parameters=[(entry.resolution, entry.dataset, entry.name) for entry in entries],
        start="2020-01-01",
        end="2020-01-02",
        settings=Settings(cache_disable=True, auth=_AUTH),
    )
    sr = StationsResult(request=request, df=pl.DataFrame(), _df_all=pl.DataFrame(), _stations_filter=StationsFilter.ALL)
    return request._values(sr=sr)  # noqa: SLF001


def test_the_scan_finds_the_shared_names_the_issue_found_by_hand() -> None:
    """The scan is sound if it finds what was found by hand: the four providers and their names."""
    found: dict[tuple[str, str], set[str]] = defaultdict(set)
    for provider, network, name_original in SHARED:
        found[provider, network].add(name_original)
    for network, names in FOUND_BY_HAND.items():
        assert names <= found[network], network


@pytest.mark.parametrize(
    ("provider", "network", "name_original"), [pytest.param(*key, id="/".join(key)) for key in SHARED]
)
def test_a_name_shared_by_parameters_is_humanized_to_each_parameter_when_they_are_asked_together(
    provider: str, network: str, name_original: str
) -> None:
    """Every parameter that carries the name, requested together, keeps its own canonical name."""
    entries = SHARED[provider, network, name_original]
    values = _values(provider, network, entries)
    df = pl.DataFrame(
        {
            "station_id": ["01"] * len(entries),
            "resolution": [entry.resolution for entry in entries],
            "dataset": [entry.dataset for entry in entries],
            "parameter": [name_original] * len(entries),
            "value": [float(index) for index in range(len(entries))],
        }
    )
    humanized = values._humanize(df, values._create_humanized_parameters_mapping())  # noqa: SLF001
    assert humanized.columns == df.columns
    assert humanized["value"].to_list() == df["value"].to_list()
    assert humanized["parameter"].to_list() == [entry.name for entry in entries]


def test_a_name_the_mapping_does_not_hold_stays_as_the_source_wrote_it() -> None:
    """A name the request does not account for, or a row of another resolution, is not renamed."""
    entries = [Entry("10_minutes", "data", "temperature_air_2m")]
    values = _values("chmi", "observation", entries)
    df = pl.DataFrame(
        {
            "resolution": ["10_minutes", "10_minutes", "daily"],
            "dataset": ["data", "data", "data"],
            "parameter": ["T", "Td", "T"],
        }
    )
    humanized = values._humanize(df, values._create_humanized_parameters_mapping())  # noqa: SLF001
    assert humanized["parameter"].to_list() == ["temperature_air_2m", "Td", "T"]
