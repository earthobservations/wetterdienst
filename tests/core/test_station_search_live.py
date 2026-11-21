# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The search for a WMO, WIGOS or ICAO id against the live station lists (GH-4075)."""

from __future__ import annotations

import pytest

from wetterdienst.core.station_search import find_stations_by_id


@pytest.mark.remote
def test_wmo_10381_is_berlin_dahlem_at_dwd_and_noaa_and_the_icao_of_hamburg_finds_its_number() -> None:
    """Berlin-Dahlem is DWD's `00403` and its MOSMIX `10381`, and `EDDH` finds Hamburg's stations that list no code."""
    berlin = find_stations_by_id(wmo_id="10381")

    found = {(row["provider"], row["network"]): row for row in berlin.df.iter_rows(named=True)}
    assert found[("dwd", "observation")]["station_id"] == "00403"
    assert found[("dwd", "mosmix")]["station_id"] == "10381"
    assert {row["match"] for row in found.values()} == {"direct"}
    assert [n.status for n in berlin.searched if n.provider == "dwd"] == ["searched"] * 5

    hamburg = find_stations_by_id(icao_id="EDDH")

    by_station = {(row["provider"], row["network"]): row for row in hamburg.df.iter_rows(named=True)}
    assert by_station[("dwd", "mosmix")]["match"] == "direct"
    assert by_station[("dwd", "observation")]["station_id"] == "01975"
    assert by_station[("dwd", "observation")]["match"] == "equivalent"
    assert by_station[("noaa", "ghcn")]["station_id"] == "GM000010147"
    assert hamburg.also_searched["wmo_id"] == ["10147"]
