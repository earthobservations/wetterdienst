from io import StringIO

import pandas as pd
import requests

from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.util.cache import metaindex_cache

MOSMIX_STATION_LIST = (
    "https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/"
    "mosmix_stationskatalog.cfg?view=nasPublication"
)

MOSMIX_STATION_LIST_COLSPECS = [
    (0, 5),
    (6, 11),
    (12, 17),
    (18, 22),
    (23, 44),
    (45, 51),
    (52, 58),
    (59, 64),
    (65, 71),
    (72, 76),
]

MOSMIX_METADATA_COLUMNS = [
    DWDMetaColumns.WMO_ID.value,
    DWDMetaColumns.ICAO_ID.value,
    DWDMetaColumns.STATION_NAME.value,
    DWDMetaColumns.LATITUDE.value,
    DWDMetaColumns.LONGITUDE.value,
    DWDMetaColumns.STATION_HEIGHT.value,
]


@metaindex_cache.cache_on_arguments()
def metadata_for_forecasts() -> pd.DataFrame:
    """ Create meta data DataFrame from available station list """
    payload = requests.get(MOSMIX_STATION_LIST, headers={"User-Agent": ""})

    # List is unsorted with repeating interruptions with "TABLE" string in the beginning
    # of the line
    lines = payload.text.split("\n")
    table_lines = [i for i, line in enumerate(lines) if line.startswith("TABLE")]

    lines_filtered = []

    for start, end in zip(table_lines[:-1], table_lines[1:]):
        lines_filtered.extend(lines[start + 3 : end - 1])

    data = StringIO("\n".join(lines_filtered))

    df = pd.read_fwf(
        data,
        colspecs=MOSMIX_STATION_LIST_COLSPECS,
        na_values=["----"],
        header=None,
        dtype="str",
    )

    df = df.iloc[:, [2, 3, 4, 5, 6, 7]]

    df.columns = MOSMIX_METADATA_COLUMNS

    return df
