# -*- coding: utf-8 -*-
# Copyright (c) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from datetime import datetime

import pandas as pd
from requests.exceptions import HTTPError

from wetterdienst.exceptions import MetaFileNotFound
from wetterdienst.metadata.columns import Columns
from wetterdienst.util.cache import CacheExpiry

REMOTE_META_INDEX_FILE_PATH = (
    "https://www.dwd.de/DE/leistungen/opendata/help/stationen/" "sws_stations_xls.xlsx?__blob=publicationFile&v=11"
)

ROAD_METADATA_COLUMNS = [
    Columns.STATION_ID.value,
    Columns.STATION_GROUP.value,
    Columns.NAME.value,
    Columns.STATE.value,
    Columns.LATITUDE.value,
    Columns.LONGITUDE.value,
    Columns.STATE.value,
    Columns.ROAD_NAME.value,
    Columns.ROAD_SECTOR.value,
    Columns.ROAD_TYPE.value,
    Columns.ROAD_SURFACE_TYPE.value,
    Columns.ROAD_SURROUNDINGS_TYPE.value,
]

ROAD_METADATA_COLUMNS_MAPPING = {
    "Kennung": Columns.STATION_ID.value,
    "GMA-Name": Columns.NAME.value,
    "Bundesland  ": Columns.STATE.value,
    "Straße / Fahrtrichtung": Columns.ROAD_NAME.value,
    "Strecken-kilometer 100 m": Columns.ROAD_SECTOR.value,
    'Streckenlage (Register "Typen")': Columns.ROAD_SURROUNDINGS_TYPE.value,
    'Streckenbelag (Register "Typen")': Columns.ROAD_SURFACE_TYPE.value,
    "Breite (Dezimalangabe)": Columns.LATITUDE.value,
    "Länge (Dezimalangabe)": Columns.LONGITUDE.value,
    "Höhe in m über NN": Columns.HEIGHT.value,
    "GDS-Verzeichnis": Columns.STATION_GROUP.value,
    "außer Betrieb (gemeldet)": Columns.HAS_FILE.value,
}
DEFAULT_FROM_DATE = datetime(2020, 1, 1)
DEFAULT_TO_DATE = datetime.utcnow()


def create_meta_index_for_road_weather(ttl: CacheExpiry = CacheExpiry.METAINDEX) -> pd.DataFrame:
    """
    Calls remote station list for road weather stations and parses
    the data into a unified DataFrame with defined `Columns` names
    Returns:
        pandas.DataFrame with meta index for all Road Weather Stations
    """
    try:
        metaindex = pd.read_excel(REMOTE_META_INDEX_FILE_PATH)
    except HTTPError:
        raise MetaFileNotFound(f"The file at location {REMOTE_META_INDEX_FILE_PATH}")

    metaindex.rename(ROAD_METADATA_COLUMNS_MAPPING, axis=1, inplace=True)
    metaindex[Columns.LONGITUDE.value] = metaindex[Columns.LONGITUDE.value].replace(",", ".", regex=True).astype(float)
    metaindex[Columns.LATITUDE.value] = metaindex[Columns.LATITUDE.value].replace(",", ".", regex=True).astype(float)

    metaindex[Columns.FROM_DATE.value] = DEFAULT_FROM_DATE
    metaindex[Columns.TO_DATE.value] = DEFAULT_TO_DATE

    return metaindex.loc[metaindex[Columns.HAS_FILE.value].isna(), ROAD_METADATA_COLUMNS]
