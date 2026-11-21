# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Stand in for the station lists the search for a WMO, WIGOS or ICAO id reads (GH-4075).

`serve` replaces the read of one network's declared list (`station_search._read_network`) with rows of the test's own,
so that the selection, the equivalence of the ids, the failure of a network and the surfaces over them are held with no
network; the declarations, the registry and everything after the read are the real ones. The rows of the real lists
(and their readers) are `tests/provider/station_catalogue_stubs.py`'s.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import polars as pl

from wetterdienst.core import station_search

if TYPE_CHECKING:
    import pytest

    from wetterdienst.model.metadata import StationIdList
    from wetterdienst.settings import Settings
    from wetterdienst.util.response_warnings import ResponseWarning

#: the three networks that need a key, which the search asks only where the settings hold it
KEYED = ("aemet/observation", "knmi/observation", "metno/frost")


def station(
    station_id: str,
    name: str = "A station",
    *,
    wmo_id: str | None = None,
    wigos_id: str | None = None,
    icao_id: str | None = None,
    latitude: float | None = 53.63,
    longitude: float | None = 9.99,
    elevation: float | None = 11.0,
) -> dict[str, Any]:
    """Give one row of a station list, with the columns a list of `_read_network` has."""
    return {
        "station_id": station_id,
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
        "elevation": elevation,
        "wmo_id": wmo_id,
        "wigos_id": wigos_id,
        "icao_id": icao_id,
    }


def serve(
    monkeypatch: pytest.MonkeyPatch,
    networks: dict[str, list[dict[str, Any]] | BaseException],
    *,
    warnings: dict[str, list[ResponseWarning]] | None = None,
) -> list[str]:
    """Serve the declared list of each named network from rows, or raise `networks[name]` where it is an exception.

    A declared network the test does not name is a list with no station. Returns the names of the networks read, in
    the order the reads began, for a test that holds which networks were asked. The frame of a network is what
    `_read_network` makes of its stations: the four columns that name the list, the stations, and only those that carry
    an id.
    """
    asked: list[str] = []

    def read(
        provider: str,
        network: str,
        declared: StationIdList,
        settings: Settings,  # noqa: ARG001
    ) -> tuple[pl.DataFrame, list[ResponseWarning]]:
        name = f"{provider}/{network}"
        asked.append(name)
        rows = networks.get(name, [])
        if isinstance(rows, BaseException):
            raise rows
        schema = {
            "station_id": pl.String,
            "name": pl.String,
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "wmo_id": pl.String,
            "wigos_id": pl.String,
            "icao_id": pl.String,
        }
        stations = pl.DataFrame(rows, schema=schema).filter(
            pl.any_horizontal(pl.col(column).is_not_null() for column in ("wmo_id", "wigos_id", "icao_id"))
        )
        frame = stations.select(
            pl.lit(provider).alias("provider"),
            pl.lit(network).alias("network"),
            pl.lit(declared.resolution).alias("resolution"),
            pl.lit(declared.dataset).alias("dataset"),
            *schema,
        )
        return frame, list((warnings or {}).get(name, []))

    monkeypatch.setattr(station_search, "_read_network", read)
    return asked
