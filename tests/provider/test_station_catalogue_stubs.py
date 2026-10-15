# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The stations a provider's reader gives for a stub of its catalogue break none of the catalogue rules (GH-2616)."""

import polars as pl
import pytest

from tests.provider.station_catalogue import assert_sound
from tests.provider.station_catalogue_stubs import STUBS, Stub
from wetterdienst.model.schema import STATIONS_SCHEMA


def assert_expected(stations: pl.DataFrame, stub: Stub) -> None:
    """Hold the stations a stub names to the fields the reader must give them, which no rule can tell.

    A rule tells a position that cannot be (off Earth, outside the country, swapped) from one that can, not a position
    read wrongly from one that is only somewhere else, nor a name that is cut or joined to its neighbour. Numbers
    compare to within 0.006, the two decimals a list in degrees and minutes is converted to.
    """
    by_id = {row["station_id"]: row for row in stations.iter_rows(named=True)}
    wrong = []
    for station_id, fields in stub.expected.items():
        row = by_id.get(station_id)
        if row is None:
            wrong.append(f"{stub.catalogue}: station {station_id!r} is not listed")
            continue
        wrong += [
            f"{stub.catalogue}: station {station_id!r} has {column} {row[column]!r}, not {value!r}"
            for column, value in fields.items()
            if row[column] != (pytest.approx(value, abs=0.006) if isinstance(value, float) else value)
        ]
    assert not wrong, "\n".join(wrong)


@pytest.mark.parametrize("stub", STUBS, ids=lambda stub: stub.catalogue)
def test_a_stub_catalogue_is_sound(stub: Stub, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold the stations of every stubbed catalogue to the rules, naming the provider, station and rule that fails."""
    stations = stub.build(monkeypatch)
    assert_sound(stations, stub.catalogue, bbox=stub.bbox, accepted=stub.accepted)
    assert_expected(stations, stub)


@pytest.mark.parametrize("stub", STUBS, ids=lambda stub: stub.catalogue)
def test_a_stub_catalogue_has_the_stations_schema(stub: Stub, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold the stations of every stubbed catalogue to `STATIONS_SCHEMA`: its columns, dtypes and relative order.

    A provider may put columns of its own among them, as the DWD forecast networks put `icao_id` after
    `station_id`, but the core columns are the ones a caller reads the same on every provider (GH-2633).
    """
    schema = stub.build(monkeypatch).schema
    core = {name: dtype for name, dtype in schema.items() if name in STATIONS_SCHEMA}
    assert core == dict(STATIONS_SCHEMA), stub.catalogue
    assert list(core) == list(STATIONS_SCHEMA), stub.catalogue
