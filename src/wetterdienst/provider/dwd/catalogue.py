# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Reader for DWD's MOSMIX station catalogue.

The catalogue lists every station DWD runs MOSMIX for, with its ICAO id, name, position and
height. It is shared by more than one network: ``dwd/mosmix`` forecasts for these stations and
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
_COLUMNS = ("station_id", "icao_id", "name", "latitude", "longitude", "height")


def read_mosmix_station_catalogue(settings: Settings, url: str = MOSMIX_STATION_CATALOGUE_URL) -> pl.DataFrame:
    """Read the MOSMIX station catalogue, returning one row per station.

    Returns an empty frame when the catalogue cannot be fetched, so that callers report no stations
    rather than raising -- the network error itself is raised by ``raise_if_exception``.
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
    return df.with_columns(
        pl.col("icao_id").replace("----", None),
        pl.col("latitude").cast(float).map_batches(convert_dm_to_dd, return_dtype=pl.Float64),
        pl.col("longitude").cast(float).map_batches(convert_dm_to_dd, return_dtype=pl.Float64),
        pl.col("height").cast(int),
    )
