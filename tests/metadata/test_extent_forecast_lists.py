# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The station lists of `dwd/mosmix` and `dwd/dmo` (`icon`) reach the world, and their extent says so (GH-3456).

A model asked for the forecast for Los Angeles refused it because DWD is German. The lists hold stations of every
continent, which the live lists show (`test_station_catalogues_live.py`, remote); here the rows of the real lists, one
for each continent, are served to the readers and the stations they give are held to the extent the networks declare:
the reader puts each station where the list says (degrees and minutes in, degrees out), and no station is outside the
box. The stubs live here, and not in `tests/provider`, so that they take no part in the frame snapshot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl
import pytest

from tests.provider.station_catalogue import assert_in_extent, check_extent, continent_counts, extent_of
from tests.provider.station_catalogue_stubs import _serve, _stations
from wetterdienst import Wetterdienst
from wetterdienst.provider.dwd import catalogue as dwd_catalogue
from wetterdienst.provider.dwd.dmo import DwdDmoRequest
from wetterdienst.provider.dwd.dmo import api as dmo_api
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest

if TYPE_CHECKING:
    from collections.abc import Callable

# a station of each continent that both lists hold, as the live lists of 2026-10-26 give them: id, ICAO, name,
# latitude, longitude, elevation (the same position in `dwd/mosmix` and `dwd/dmo`)
CONTINENTS: dict[str, tuple[str, str, str, float, float, int]] = {
    "north_america": ("72295", "KLAX", "LOS ANGELES", 33.93, -118.4, 38),
    "south_america": ("87576", "SAEZ", "BUENOS AIRES AERO", -34.82, -58.53, 20),
    "africa": ("63740", "HKJK", "NAIROBI", -1.32, 36.92, 1624),
    "asia": ("47662", "RJTD", "TOKYO NARITA", 35.68, 139.77, 5),
    "oceania": ("94767", "YSSY", "SYDNEY AIRPORT", -33.95, 151.18, 6),
    "europe": ("10147", "EDDH", "HAMBURG-FU.", 53.63, 10.0, 16),
}

# how far a position read from the degrees and minutes of a list is from the decimal degrees it was written from: the
# list rounds to a whole minute (1/60 of a degree), the live frame to two decimals
POSITION_TOLERANCE = 0.02


def _degrees_minutes(value: float) -> str:
    """Write decimal degrees as the lists do: whole degrees, a point and the minutes in two digits (`33.56`)."""
    degrees, minutes = divmod(round(abs(value) * 60), 60)
    return f"{'-' if value < 0 else ''}{degrees}.{minutes:02d}"


def _catalogue(newline: str = "\n") -> bytes:
    """Write the stations as the station lists of DWD do: fixed columns, latitude and longitude in degrees.minutes."""
    lines = [
        "ID    ICAO NAME                 LAT    LON     ELEV",
        "----- ---- -------------------- -----  ------- -----",
    ]
    lines += [
        f"{station_id} {icao} {name:<20}{_degrees_minutes(latitude):>8}{_degrees_minutes(longitude):>8}{elevation:>10}"
        for station_id, icao, name, latitude, longitude, elevation in CONTINENTS.values()
    ]
    return (newline.join(lines) + newline).encode("latin-1")


def _serve_mosmix(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, dwd_catalogue, {"mosmix_stationskatalog": _catalogue()})


def _serve_dmo(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, dmo_api, {"dmo_stationsliste_txt": _catalogue("\r\n")})
    directories = [{"name": f"single_stations/{station[0]}/"} for station in CONTINENTS.values()]
    monkeypatch.setattr(dmo_api, "list_remote_directory_fsspec", lambda *_args, **_kwargs: directories)


@pytest.mark.parametrize(
    ("network", "serve", "request_class", "parameter"),
    [
        pytest.param("dwd/mosmix", _serve_mosmix, DwdMosmixRequest, ("hourly", "large"), id="mosmix-large"),
        pytest.param("dwd/mosmix", _serve_mosmix, DwdMosmixRequest, ("hourly", "small"), id="mosmix-small"),
        pytest.param("dwd/dmo", _serve_dmo, DwdDmoRequest, ("hourly", "icon"), id="dmo-icon"),
    ],
)
def test_the_readers_put_a_station_of_each_continent_where_the_list_does(
    network: str,
    serve: Callable[[pytest.MonkeyPatch], None],
    request_class: type,
    parameter: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each station of the rows served is read at its position, and in the extent of the network, which is global."""
    serve(monkeypatch)
    stations = _stations(request_class, parameter)
    provider, name = network.split("/")
    extent = Wetterdienst.resolve(provider, name).metadata.extent

    held = {row["station_id"]: row for row in stations.iter_rows(named=True)}
    for continent, (station_id, _icao, _name, latitude, longitude, _elevation) in CONTINENTS.items():
        assert station_id in held, f"{network} has no station of {continent}"
        assert abs(held[station_id]["latitude"] - latitude) < POSITION_TOLERANCE, (network, continent)
        assert abs(held[station_id]["longitude"] - longitude) < POSITION_TOLERANCE, (network, continent)
    assert extent.scope == "global"
    assert_in_extent(stations, network, extent)
    # a station on every continent the extent names, as far as the rows go: the live list holds the rest
    counts = continent_counts(stations.select(pl.col("latitude"), pl.col("longitude")))
    assert {continent for continent, count in counts.items() if count} >= set(CONTINENTS)


def test_the_european_list_of_dmo_is_in_the_extent_of_its_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    """`icon_eu` has the stations of Europe, which the extent of the dataset says and the one of the network does not.

    The list of the stub has a directory for Hamburg only, as the European model has none for Los Angeles.
    """
    _serve(monkeypatch, dmo_api, {"dmo_stationsliste_txt": _catalogue("\r\n")})
    europe = [{"name": "single_stations/10147/"}]
    monkeypatch.setattr(dmo_api, "list_remote_directory_fsspec", lambda *_args, **_kwargs: europe)
    metadata = Wetterdienst.resolve("dwd", "dmo").metadata

    stations = _stations(DwdDmoRequest, ("hourly", "icon_eu"))

    assert stations["station_id"].to_list() == ["10147"]
    own = extent_of(metadata, "hourly/icon_eu")
    assert own != metadata.extent
    assert own.scope == "regional"
    assert_in_extent(stations, "dwd/dmo hourly/icon_eu", own)
    # Los Angeles is in the box of the network and not in the box of the dataset
    assert extent_of(metadata, "hourly/icon").bbox == metadata.extent.bbox
    los_angeles = pl.DataFrame({"station_id": ["72295"], "latitude": [33.93], "longitude": [-118.4]})
    assert not check_extent(los_angeles, "dwd/dmo", metadata.extent)
    assert check_extent(los_angeles, "dwd/dmo hourly/icon_eu", own)
