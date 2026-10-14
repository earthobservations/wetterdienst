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
# decimal degrees, the minutes of the catalogues rounded to two decimals) and the position it is at (GH-2646).
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
# A position is replaced only while DWD publishes exactly the value recorded here, so the correction stops by itself
# when DWD fixes its files, rather than moving a corrected station a second time or one DWD has moved elsewhere.
STATION_POSITION_CORRECTIONS: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "08370": ((38.78, -0.17), (38.78, 0.17)),
    "40103": ((33.45, 35.8), (34.45, 35.8)),
}
_POSITION_TOLERANCE = 0.005


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

    A fetch failure is raised, save for ``NoInternetError``: ``raise_if_exception`` returns
    silently on that one, and an empty frame is returned so that a caller offline reports no
    stations rather than an error.
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
        return pl.DataFrame()
    # the catalogue is latin-1 encoded (station names carry umlauts)
    lines = StringIO(file.content.read().decode(encoding="latin-1")).readlines()
    header = lines.pop(0)
    # line 2 is the ``----- ---- ...`` rule under the header
    df = pl.DataFrame({"column_0": lines[1:]})
    df.columns = [header]
    df = read_fwf_from_df(df, _COLUMN_SPECS)
    df.columns = list(_COLUMNS)
    df = df.with_columns(
        pl.col("icao_id").replace("----", None),
        pl.col("latitude").cast(float).map_batches(convert_dm_to_dd, return_dtype=pl.Float64),
        pl.col("longitude").cast(float).map_batches(convert_dm_to_dd, return_dtype=pl.Float64),
        pl.col("elevation").cast(int),
    )
    return correct_station_positions(df)
