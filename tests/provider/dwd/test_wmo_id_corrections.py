# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The WMO numbers of the forecast catalogues that are none: block 99 and the corrected stations (GH-4074).

DWD's catalogues write a station's id as the five digits of its WMO number, which DWD does not state. Held against
WMO's register OSCAR/Surface, a number of block 99 (no land station has one) and seven numbers whose register station
is 100 km or more from DWD's position are no WMO number of the station DWD lists them for: `wmo_id` is null for them.
The remote test reads the register for each, so that a number that OSCAR gives to DWD's station after all, or a
position that has moved, is told.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.oscar import OSCAR_SEARCH_URL
from wetterdienst.provider.dwd.catalogue import WMO_ID_CORRECTIONS, with_wmo_id_of_station_id
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from pathlib import Path


def _wmo_ids(rows: dict[str, str]) -> dict[str, str | None]:
    """Give the `wmo_id` that the catalogues' reading gives each station id of `rows` (id and name)."""
    frame = pl.DataFrame({"station_id": list(rows), "name": list(rows.values())})
    found = with_wmo_id_of_station_id(frame)
    return dict(zip(found["station_id"], found["wmo_id"], strict=True))


def test_a_number_of_block_99_is_no_wmo_number() -> None:
    """99953 LONGBOAT KEY (Florida) has no `0-20000-0-99953` in the register, and block 99 has no land station."""
    assert _wmo_ids({"99953": "LONGBOAT KEY", "99001": "ANYWHERE", "10147": "HAMBURG-FUHLSBUETTEL"}) == {
        "99953": None,
        "99001": None,
        "10147": "10147",
    }


def test_a_corrected_station_has_no_wmo_number_under_the_name_it_is_corrected_for() -> None:
    """The seven are nulled by id and name: DWD's `02830` KITTILA is not `02830`, the number of Kouvola Anjala."""
    assert set(WMO_ID_CORRECTIONS) == {"02830", "03930", "16741", "71515", "71888", "72388", "72522"}
    found = _wmo_ids({station_id: name for station_id, (name, _lat, _lon) in WMO_ID_CORRECTIONS.items()})
    assert found == dict.fromkeys(WMO_ID_CORRECTIONS)


def test_the_correction_stops_when_dwd_publishes_the_id_for_another_station() -> None:
    """A number that DWD has moved to a station of another name is not nulled; nor are the ones that were left."""
    assert _wmo_ids({"02830": "KOUVOLA ANJALA", "40437": "RIAD INT.AIRPORT", "40377": "KING KHALID MIL CTY"}) == {
        "02830": "02830",
        "40437": "40437",
        "40377": "40377",
    }
    assert _wmo_ids({"71060": "CAMSELL RIVER N.W.T."}) == {"71060": "71060"}


def test_a_catalogue_without_names_has_block_99_nulled_and_the_rest_read() -> None:
    """The dmo catalogue reader hands over a name, but a frame without one must not fail."""
    frame = with_wmo_id_of_station_id(pl.DataFrame({"station_id": ["99953", "02830", "A191"]}))
    assert frame["wmo_id"].to_list() == [None, "02830", None]


def _distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    p = math.pi / 180
    x = (
        math.sin((b[0] - a[0]) * p / 2) ** 2
        + math.cos(a[0] * p) * math.cos(b[0] * p) * math.sin((b[1] - a[1]) * p / 2) ** 2
    )
    return 12742 * math.asin(math.sqrt(x))


def _oscar_stations_of(wigos_id: str, cache_dir: Path) -> list[dict]:
    """Ask OSCAR for the stations that have a WIGOS id: a small answer, one request."""
    settings = Settings(cache_dir=cache_dir)
    file = download_file(
        url=f"{OSCAR_SEARCH_URL}?wigosId={wigos_id}",
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.ONE_HOUR,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    file.raise_if_exception()
    assert not isinstance(file.content, Exception)
    found = json.loads(file.content.read())["stationSearchResults"]
    # the search finds the id as asked, and nothing else
    return [
        station
        for station in found
        if wigos_id in {i["wigosStationIdentifier"] for i in station["wigosStationIdentifiers"]}
    ]


@pytest.mark.remote
@pytest.mark.parametrize("station_id", sorted(WMO_ID_CORRECTIONS))
def test_oscar_has_the_number_of_a_corrected_station_for_a_place_100_km_away(station_id: str, tmp_path: Path) -> None:
    """Read 2026-11-19: the register's `0-20000-0-<id>` is another station, 146 to 779 km from DWD's position."""
    name, latitude, longitude = WMO_ID_CORRECTIONS[station_id]
    stations = _oscar_stations_of(f"0-20000-0-{station_id}", tmp_path)
    assert len(stations) == 1, f"{station_id} {name}: OSCAR lists no station of the number, or more than one"
    (station,) = stations
    distance = _distance_km((latitude, longitude), (station["latitude"], station["longitude"]))
    assert distance >= 100, f"{station_id} {name} is {distance:.0f} km from OSCAR's {station['name']}: not a correction"


@pytest.mark.remote
def test_oscar_has_no_land_station_in_block_99_for_longboat_key(tmp_path: Path) -> None:
    """Read 2026-11-19: no `0-20000-0-99953`."""
    assert _oscar_stations_of("0-20000-0-99953", tmp_path) == []
