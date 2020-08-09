""" Functions for DWD RADOLAN collection """
from pathlib import Path
from typing import Union
import datetime as dt

import pandas as pd

from wetterdienst.constants.access_credentials import DWDCDCDataPath
from wetterdienst.constants.metadata import DWD_FOLDER_MAIN
from wetterdienst.data_storing import store_radolan_data, restore_radolan_data
from wetterdienst.download.download import download_radolan_data
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.exceptions.start_date_end_date_exception import DatetimeOutOfRangeError
from wetterdienst.indexing.file_index_creation import create_file_index_for_radolan


def collect_radolan_data(
        datetime: Union[str, dt.datetime],
        time_resolution: TimeResolution,
        folder: Union[str, Path] = DWD_FOLDER_MAIN,
):
    datetime = pd.to_datetime(datetime).replace(tzinfo=None)

    # RADOLAN is only offered ina 10 minute interval respective 1hour
    if datetime.minute % 10 != 0:
        raise ValueError("date_minute must be one of 0, 10, 20, 30, 40, 50")

    if time_resolution == TimeResolution.DAILY and datetime.minute != 50:
        raise ValueError("daily RADOLAN is set for minute 50")

    if time_resolution not in (TimeResolution.HOURLY, TimeResolution.DAILY):
        raise ValueError("RADOLAN is only offered in hourly and daily resolution.")

    file_index = create_file_index_for_radolan(time_resolution)

    if datetime < file_index[DWDMetaColumns.DATETIME.value].min() or datetime > file_index[DWDMetaColumns.DATETIME.value].max():
        raise DatetimeOutOfRangeError("RADOLAN is not available for defined")

    try:
        return restore_radolan_data(
            datetime,
            time_resolution,
            folder
        )
    except FileNotFoundError:
        file_in_bytes, period_type = download_radolan_data(datetime, time_resolution)

        store_radolan_data(
            datetime,
            file_in_bytes,
            time_resolution,
            period_type,
            folder
        )

        return restore_radolan_data(
            datetime,
            time_resolution,
            folder
        )


if __name__ == "__main__":
    collect_radolan_data(pd.Timestamp("2020-08-08 00:50:00"), TimeResolution.DAILY)
