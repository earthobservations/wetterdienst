# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The snapshot of the frames the core hands out (`frames.py`, GH-2627) is sound, and says what it does not cover.

Each test of `tests/provider` is compared to its entry when it ends (`recorded_frames` in `conftest.py`). What is
checked here is the file: that it is well formed, that its entries belong to tests that exist, and that every
network is either in it or in `NOT_COVERED` with the reason, so that a network whose fixtures are missing is a
decision on record and not a gap nobody saw.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.provider import frames
from wetterdienst import Wetterdienst
from wetterdienst.exceptions import MissingDependencyError

ROOT = Path(__file__).parents[2]

# the networks no offline test of `tests/provider` reaches the core's values step with, and the stations step, each with
# the reason. A fixture is a response of the source, as it is served; one that serves numbers that are no readings is
# marked `synthetic_values` and recorded all the same, since the shape of the frame is what is held here. A network
# that is in neither list is covered: its tests are in the snapshot.
NO_VALUES_FIXTURE = {
    "chmi/observation": "no offline test collects values; the source is a key-less CSV portal with three file layouts",
    "dwd/phenology": "no offline test collects values; the parsing is tested (`test_api.py`), not the collection",
    "imgw/meteorology": "no offline test collects values; the readers are tested on their files, not the collection",
    "dwd/radar": "standalone: no `TimeseriesValues`, the files are handed over as DWD wrote them",
    "dwd/alerts": "standalone: no `TimeseriesValues`, the alerts are CAP documents",
}
NO_STATIONS_FIXTURE = {
    "dwd/radar": "standalone: no stations",
    "dwd/alerts": "standalone: no stations",
}


def _requests() -> dict[str, type]:
    found = {}
    for provider, networks in sorted(Wetterdienst.registry.items()):
        for network in sorted(networks):
            if Wetterdienst.is_standalone(provider, network):
                continue
            try:
                found[f"{provider}/{network}"] = Wetterdienst.resolve(provider, network)
            except (MissingDependencyError, ImportError):  # pragma: no cover
                continue
    return found


@pytest.fixture(scope="module")
def snapshot() -> dict:
    """Give the committed snapshot."""
    return frames.load()


def test_the_schemas_of_the_snapshot_are_named_by_their_content(snapshot: dict) -> None:
    """A schema is kept under the hash of itself, and every entry names one that is there."""
    schemas = snapshot["schemas"]
    for name, schema in schemas.items():
        assert frames.schema_id(schema) == name
    used = {entry[1] for kind in ("values", "stations") for entries in snapshot[kind].values() for entry in entries}
    assert used <= set(schemas), sorted(used - set(schemas))
    assert set(schemas) <= used, f"a schema that no entry uses: {sorted(set(schemas) - used)}"


def test_every_entry_of_the_snapshot_belongs_to_a_test_that_exists(snapshot: dict) -> None:
    """A test that is renamed or removed leaves its entry behind, and the entry would hold nothing to account.

    The file and the name of the function are looked up, which is what a rename or a removal changes; the parameters
    of a test are not, so `uv run poe frames:snapshot` is what drops the entry of a case that is gone.
    """
    gone = []
    for nodeid in sorted(set(snapshot["values"]) | set(snapshot["stations"])):
        path, _, name = nodeid.partition("::")
        function = name.split("::")[-1].partition("[")[0]
        file = ROOT / path
        if not file.is_file() or f"def {function}(" not in file.read_text(encoding="utf-8"):
            gone.append(nodeid)
    assert gone == [], f"entries of tests that are gone, regenerate the snapshot: {gone[:5]}"


def test_the_snapshot_is_written_the_way_the_command_writes_it(snapshot: dict, tmp_path: Path) -> None:
    """The file is what `frames.write` gives for its own content, so that a hand edit or a merge shows as a diff."""
    written = tmp_path / "frames.snapshot.json"
    frames.write(snapshot["values"], snapshot["stations"], snapshot["schemas"], to=written)
    assert written.read_text(encoding="utf-8") == frames.SNAPSHOT.read_text(encoding="utf-8")


def test_every_network_has_its_frames_in_the_snapshot_or_a_reason(snapshot: dict) -> None:
    """A network added to the library takes a stand: its offline tests are recorded, or the reason they are not."""
    with_values = {entry[0].split(" ")[0] for entries in snapshot["values"].values() for entry in entries}
    with_stations = {entry[0] for entries in snapshot["stations"].values() for entry in entries}
    values_missing, stations_missing, covered = set(), set(), set()
    for network, request in _requests().items():
        values_class = getattr(request._values, "__name__", None)  # noqa: SLF001
        if values_class in with_values:
            covered.add(network)
        else:
            values_missing.add(network)
        if request.__name__ not in with_stations:
            stations_missing.add(network)
    standalone = {f"{provider}/{network}" for provider, network in Wetterdienst.standalone}
    values_missing |= standalone
    stations_missing |= standalone
    assert values_missing - set(NO_VALUES_FIXTURE) == set(), "record a test of its values, or give the reason"
    assert set(NO_VALUES_FIXTURE) - values_missing == set(), "NO_VALUES_FIXTURE names a network that is covered"
    assert stations_missing - set(NO_STATIONS_FIXTURE) == set(), "record a test of its stations, or give the reason"
    assert set(NO_STATIONS_FIXTURE) - stations_missing == set(), "NO_STATIONS_FIXTURE names a network that is covered"
    assert covered, "no network is covered, or the search found none"
