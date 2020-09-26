import re

import pandas as pd
from dateparser import parse

from wetterdienst import TimeResolution, Parameter, PeriodType
from wetterdienst.dwd.metadata.constants import DWDCDCBase, ArchiveFormat
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.dwd.index import _create_file_index_for_dwd_server
from wetterdienst.util.cache import fileindex_cache_five_minutes


RADOLAN_HISTORICAL_DT_REGEX = r"(?<!\d)\d{6}(?!\d)"
RADOLAN_RECENT_DT_REGEX = r"(?<!\d)\d{10}(?!\d)"


@fileindex_cache_five_minutes.cache_on_arguments()
def create_file_index_for_radolan(time_resolution: TimeResolution) -> pd.DataFrame:
    """
    Function used to create a file index for the RADOLAN product. The file index will
    include both recent as well as historical files. A datetime column is created from
    the filenames which contain some datetime formats. This datetime column is required
    for later filtering for the requested file.

    Args:
        time_resolution: time resolution enumeration for the requesed RADOLAN product,
        where two are possible: hourly and daily

    Returns:
        file index as DataFrame
    """
    file_index = pd.concat(
        [
            _create_file_index_for_dwd_server(
                Parameter.RADOLAN,
                time_resolution,
                period_type,
                DWDCDCBase.GRIDS_GERMANY,
            )
            for period_type in (PeriodType.HISTORICAL, PeriodType.RECENT)
        ]
    )

    file_index = file_index[
        file_index[DWDMetaColumns.FILENAME.value].str.contains("/bin/")
        & file_index[DWDMetaColumns.FILENAME.value].str.endswith(
            (ArchiveFormat.GZ.value, ArchiveFormat.TAR_GZ.value)
        )
    ]

    r = re.compile(f"{RADOLAN_HISTORICAL_DT_REGEX}|{RADOLAN_RECENT_DT_REGEX}")

    # Require datetime of file for filtering
    file_index[DWDMetaColumns.DATETIME.value] = file_index[
        DWDMetaColumns.FILENAME.value
    ].apply(
        lambda filename: parse(
            r.findall(filename)[0],
            date_formats=[DatetimeFormat.YM.value, DatetimeFormat.ymdhm.value],
        )
    )

    return file_index
