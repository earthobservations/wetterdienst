# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Reader for DWD's MOSMIX station catalogue.

The catalogue lists every station DWD runs MOSMIX for, with its ICAO id, name, position and
elevation. It is shared by more than one network: ``dwd/mosmix`` forecasts for these stations and
``dwd/poi`` publishes their observed weather reports, so both take their station list from here
rather than parsing the same fixed-width file twice.

Positions are in degrees and minutes (``70.56`` is 70°56'), which is why they go through
``convert_dm_to_dd`` and not a plain cast.
"""

from __future__ import annotations

import logging
from io import StringIO
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.station_ids import wmo_id_expr
from wetterdienst.util.geo import convert_dm_to_dd
from wetterdienst.util.network import download_file
from wetterdienst.util.polars_util import read_fwf_from_df

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

MOSMIX_STATION_CATALOGUE_URL = (
    "https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/mosmix_stationskatalog.cfg?view=nasPublication"
)

_COLUMN_SPECS = ((0, 5), (6, 9), (11, 30), (32, 38), (39, 46), (48, 56))
_COLUMNS = ("station_id", "icao_id", "name", "latitude", "longitude", "elevation")

# Stations DWD publishes at a wrong position, each with the position DWD gives (latitude, longitude, as read here:
# decimal degrees, the minutes of the catalogues rounded to two decimals) and the position it is at (GH-2646, GH-2897).
# Each was checked against more than the DWD files, which all agree with one another (Javea: the catalogues and the
# placemarks of the MOSMIX and DMO runs; Tripoli, in no catalogue: the placemarks of the `icon` and `icon_eu` runs), so
# there is no second DWD source to take the right one from:
#
# - 08370 JAVEA/YUNTAMIEN is published at 0 deg 10' west (-0.17), and Javea (Xabia) lies east of Greenwich: GHCN
#   hourly `SPM00008370` (the same WMO id) 38.7842 / 0.1667, OpenStreetMap (relation 346031) 38.7894 / 0.1634 and
#   Spanish Wikipedia (Javea) 38.7892 / 0.1631 all put it at +0.16 to +0.17, which is 0.34 degrees (about 30 km) east
#   of where DWD has it.
# - 40103 TRIPOLI is published at latitude 33.45, and is Tripoli in Lebanon: GHCN hourly and daily `LEM00040103` (the
#   same WMO id) 34.45 / 35.80, OpenStreetMap (relation 4869639) 34.4374 / 35.8349 and Wikipedia (Tripoli, Lebanon)
#   34.4367 / 35.8344 all put it at 34.44 to 34.45, which is one degree (111 km) north of DWD's latitude.
#
# The rest lost the sign of one coordinate (GH-2897). Where a DMO field has no whole degrees (`.22`), nothing in it says
# west or south once the minus is gone, which is why the reader cannot recover it (`_dm_degrees`). DWD's placemarks for
# these stations carry the same wrong sign, bar P0563:
#
# - P0563 LONDON LUTON is written `.22` by `dmo_stationsliste_txt.asc` (the MOSMIX catalogue has `-0.22`, and DWD's
#   placemark `-0.37,51.87`), which is read at +0.37 although Luton Airport lies at -0.37: GHCN hourly `UKI0000EGGW`
#   (160.3 m, as DWD) 51.8747 / -0.3683, OurAirports `EGGW` 51.874699 / -0.368333, OpenStreetMap (way 110273499)
#   51.8781 / -0.3664 and Wikipedia (Luton Airport) 51.8747 / -0.3683. It is 50 km east of the airport as read.
# - 03377 WADDINGTON, 03768 FARNBOROUGH and 08286 CASTELLON DE LA PLANA are published at 0.52, 0.77 and 0.07 east, in
#   both catalogues and in the placemarks. RAF Waddington lies at -0.52 (GHCN hourly `UKI0000EGXW` 53.1662 / -0.5238,
#   OurAirports `EGXW` 53.166199 / -0.523811, OpenStreetMap way 219355109 53.1662 / -0.5212, Wikipedia 53.1725 /
#   -0.5308), Farnborough Airport at -0.77 (GHCN hourly `UKI0000EGUF` 51.283 / -0.767 and `EGLF` 51.2758 / -0.7763,
#   OurAirports `EGLF` 51.275799 / -0.776333, Wikipedia 51.2753 / -0.7775; DWD's own F9706 FARNBOROUGH has -0.47 /
#   -0.78), and Castellon de la Plana (Almassora) at -0.07 (GHCN hourly `SPN0008500A` CASTELLON-ALMASSORA 39.957 /
#   -0.072, Wikipedia Almassora 39.9403 / -0.0625; +0.07 at 39.95 is in the Mediterranean, off the coast).
# - F9424 BAURU/AREALVA APT. is published at latitude +22.15, in both catalogues and in the placemark, and Bauru is
#   south of the equator: OurAirports `SBAE` -22.1608 / -49.0703 and OpenStreetMap (relation 8527439) -22.1571 /
#   -49.0752 agree on -22.16 (GHCN hourly has no `SBAE`; its nearest Bauru stations are 17 km south, at -22.32).
#
# A position is replaced only while DWD publishes exactly the value recorded here, so the correction stops by itself
# when DWD fixes its files, rather than moving a corrected station a second time or one DWD has moved elsewhere.
STATION_POSITION_CORRECTIONS: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "08370": ((38.78, -0.17), (38.78, 0.17)),
    "40103": ((33.45, 35.8), (34.45, 35.8)),
    "P0563": ((51.87, 0.37), (51.87, -0.37)),
    "03377": ((53.17, 0.52), (53.17, -0.52)),
    "03768": ((51.28, 0.77), (51.28, -0.77)),
    "08286": ((39.95, 0.07), (39.95, -0.07)),
    "F9424": ((22.15, -49.07), (-22.15, -49.07)),
}
_POSITION_TOLERANCE = 0.005


# The five digits that DWD's catalogues write as a station's id are taken as its WMO number
# (`with_wmo_id_of_station_id`), which DWD does not state. Compared with WMO's register OSCAR/Surface (read 2026-11-19,
# `0-20000-0-<id>`), 90.5 % of the 2,696 numbers of MOSMIX are the register's and 256 are not in it at all: those are
# kept, as a station can lack in the register without its number being wrong. Two kinds of number are no station's WMO
# number, and are nulled (GH-4074):
#
# - Block 99 is no block of land stations: OSCAR has four `0-20000-0-99xxx` stations, two of them radars. The one id
#   of it in the catalogues is 99953 LONGBOAT KEY (27.38 / -82.63, Florida), which the register does not have.
# - The stations below, whose number the register holds for another station 100 km or more away; for five of the seven
#   it has a station of DWD's name within 6 km of DWD's position, under another number. Checked one by one (name,
#   position, OSCAR's station of the number and the nearest station of OSCAR to DWD's position):
#
#   - 02830 KITTILA (EFKT, 67.70 / 24.85): `0-20000-0-02830` is KOUVOLA ANJALA (60.70 / 26.81, since 1941), and
#     KITTILA AIRPORT is `02720`, 1.0 km from DWD's position.
#   - 03930 LIVERPOOL (EGGP): `03930` is ALMONDSBURY (51.55 / -2.56, 199 km), and SPEKE, the airport of Liverpool, is
#     `03323`.
#   - 16741 PAROS (LGPA, 37.02 / 25.13): `16741` is EL VENIZELOS, the airport of Athens (37.92 / 23.93, 146 km); the
#     register has no station on Paros.
#   - 71515 DRYDEN (CYHD, 49.83 / -92.75): `71515` is INDIAN HEAD CDA, SASK (779 km), and DRYDEN REGIONAL, ONT is
#     `71527`, 0.5 km from DWD's position.
#   - 71888 JASPER,ALTA. (52.88 / -118.07): `71888` is VIKING AGCM, ALTA (425 km, closed 2024), and JASPER WARDEN, ALTA
#     is `71486`, 5.8 km from DWD's position.
#   - 72388 SAN JOSE INT. (KSJC, 37.37 / -121.93): `72388` is Las Vegas, NV (619 km); the register has no station in
#     San Jose.
#   - 72522 HARRISBURG INT. (KMDT, 40.20 / -76.77): `72522` is GLENN FALLS, NY (437 km), and HARRISBURG INT. ARPT is
#     `72399`, 0.9 km from DWD's position.
#
#   Not nulled, though the register puts the number elsewhere: 40437 RIAD INT.AIRPORT (OERK) and 40377 KING KHALID MIL
#   CTY (OEKK), where the register's station of the number is closed (2024, 2025) and its position for 40377 (21.2 /
#   51.8, in the Empty Quarter) is no place near Hafr Al-Batin, which it is named for, so the register may be the stale
#   side; and 71060 CAMSELL RIVER N.W.T., a number the register has given to NORDEGG CS, ALTA since 2000 (1,464 km from
#   DWD's position; no station of the register near it to say which number it has now).
#
# A number is nulled only while DWD publishes the id under exactly this name, so the correction stops by itself when
# DWD fixes its catalogue. Each is held against OSCAR by a test that reads the register
# (`tests/provider/dwd/test_wmo_id_corrections.py`): the station of the number is 100 km or more from DWD's position.
WMO_ID_CORRECTIONS: dict[str, tuple[str, float, float]] = {
    "02830": ("KITTILA", 67.7, 24.85),
    "03930": ("LIVERPOOL", 53.33, -2.87),
    "16741": ("PAROS", 37.02, 25.13),
    "71515": ("DRYDEN", 49.83, -92.75),
    "71888": ("JASPER,ALTA.", 52.88, -118.07),
    "72388": ("SAN JOSE INT.", 37.37, -121.93),
    "72522": ("HARRISBURG INT.", 40.2, -76.77),
}
#: the block of the numbers that no land station has
_NO_LAND_STATIONS_BLOCK = "99"


def with_wmo_id_of_station_id(df: pl.DataFrame) -> pl.DataFrame:
    """Add ``wmo_id`` to a catalogue of the forecast networks: the ``station_id`` where that is a WMO number.

    DWD's catalogues (MOSMIX, DMO, and POI, which reads MOSMIX's) key a station by its WMO number where it has one
    (`10147`, `01001`: five digits), and by an id DWD assigns where it has not (`A191`, `F9424`, `P0563`: 52 % of the
    MOSMIX list). The five digits are the number, so ``wmo_id`` is that and the others are null, since an id of
    DWD's own is no WMO number however much it looks like one. A number of block 99 is none, and nor are those of
    ``WMO_ID_CORRECTIONS`` (see there): null.
    """
    wrong = pl.col("station_id").str.starts_with(_NO_LAND_STATIONS_BLOCK)
    if "name" in df.columns:
        for station_id, (name, _latitude, _longitude) in WMO_ID_CORRECTIONS.items():
            wrong |= (pl.col("station_id") == station_id) & (pl.col("name").str.strip_chars() == name)
    return df.with_columns(pl.when(~wrong).then(wmo_id_expr("station_id")).alias("wmo_id"))


def correct_station_positions(df: pl.DataFrame) -> pl.DataFrame:
    """Move the stations of ``STATION_POSITION_CORRECTIONS`` that DWD still publishes at the wrong position."""
    for station_id, ((published_lat, published_lon), (lat, lon)) in STATION_POSITION_CORRECTIONS.items():
        published = (
            (pl.col("station_id") == station_id)
            & ((pl.col("latitude") - published_lat).abs() < _POSITION_TOLERANCE)
            & ((pl.col("longitude") - published_lon).abs() < _POSITION_TOLERANCE)
        )
        df = df.with_columns(
            pl.when(published).then(lat).otherwise(pl.col("latitude")).alias("latitude"),
            pl.when(published).then(lon).otherwise(pl.col("longitude")).alias("longitude"),
        )
    return df


def read_mosmix_station_catalogue(settings: Settings, url: str = MOSMIX_STATION_CATALOGUE_URL) -> pl.DataFrame:
    """Read the MOSMIX station catalogue, returning one row per station.

    A fetch failure is raised, ``NoInternetError`` included: a catalogue that could not be read is
    not a network without stations (GH-2640).
    """
    file = download_file(
        url=url,
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.METAINDEX,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    file.raise_if_exception()
    if isinstance(file.content, Exception):
        # narrows the type; `raise_if_exception` has raised for any failed download
        return pl.DataFrame()
    # the catalogue is latin-1 encoded (station names carry umlauts)
    lines = StringIO(file.content.read().decode(encoding="latin-1")).readlines()
    header = lines.pop(0)
    if not lines[1:]:
        # a list of the header and the rule alone: a column without a row is Null, `str.slice` raises on it
        return pl.DataFrame()
    # line 2 is the ``----- ---- ...`` rule under the header
    df = pl.DataFrame({"column_0": lines[1:]})
    df.columns = [header]
    df = read_fwf_from_df(df, _COLUMN_SPECS)
    df.columns = list(_COLUMNS)
    df = df.with_columns(
        pl.col("icao_id").replace("----", None),
        convert_dm_to_dd(pl.col("latitude").cast(float)),
        convert_dm_to_dd(pl.col("longitude").cast(float)),
    )
    return with_wmo_id_of_station_id(correct_station_positions(df))
