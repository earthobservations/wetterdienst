""" Functions for DWD RADOLAN collection """
from io import BytesIO
from pathlib import Path
from typing import Union, List, Tuple, Optional, Generator
from datetime import datetime
import logging

import pandas as pd

from wetterdienst.additionals.functions import parse_enumeration_from_template
from wetterdienst.constants.access_credentials import DWDCDCBase
from wetterdienst.constants.metadata import DWD_FOLDER_MAIN
from wetterdienst.data_storing import store_radolan_data, restore_radolan_data
from wetterdienst.download.download import download_radolan_data
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.exceptions.start_date_end_date_exception import DatetimeOutOfRangeError
from wetterdienst.file_path_handling.file_list_creation import create_filepath_for_radolan
from wetterdienst.indexing.file_index_creation import create_file_index_for_radolan

log = logging.getLogger(__name__)


class DWDRadolanRequest:
    """
    API for DWD RADOLAN data requests
    """
    def __init__(self,
                 time_resolution: Union[str, TimeResolution],
                 date_times: Optional[Union[str, List[Union[str, datetime]]]] = None,
                 start_date: Optional[Union[str, datetime]] = None,
                 end_date: Optional[Union[str, datetime]] = None,
                 prefer_local: bool = False,
                 write_file: bool = False,
                 folder: Union[str, Path] = DWD_FOLDER_MAIN):

        self.time_resolution = parse_enumeration_from_template(time_resolution, TimeResolution)

        if date_times == "latest":
            pass
        elif date_times:
            pass
        else:
            self.date_times = pd.date_range(start_date, end_date)

        self.prefer_local = prefer_local
        self.write_file = write_file

    def __eq__(self, other):
        return [
            self.station_ids,
            self.parameter,
            self.time_resolution,
            self.period_type,
            self.start_date,
            self.end_date,
        ] == other

    def __str__(self):
        station_ids_joined = "& ".join(
            [str(station_id) for station_id in self.station_ids]
        )
        return ", ".join(
            [
                f"station_ids {station_ids_joined}",
                "& ".join([parameter.value for parameter in self.parameter]),
                self.time_resolution.value,
                "& ".join([period_type.value for period_type in self.period_type]),
                self.start_date.value,
                self.end_date.value,
            ]
        )

    def collect_data(self) -> Generator[Tuple[datetime, BytesIO], None, None]:
        pass


def collect_radolan_data(
        date_times: List[datetime],
        time_resolution: TimeResolution,
        prefer_local: bool = False,
        write_file: bool = False,
        folder: Union[str, Path] = DWD_FOLDER_MAIN
) -> List[Tuple[datetime, BytesIO]]:
    if time_resolution not in (TimeResolution.HOURLY, TimeResolution.DAILY):
        raise ValueError("RADOLAN is only offered in hourly and daily resolution.")

    data = []
    # datetime = pd.to_datetime(datetime).replace(tzinfo=None)
    for date_time in date_times:
        # RADOLAN is only offered ina 10 minute interval respective 1hour
        if date_time.minute % 10 != 0:
            raise ValueError("date_minute must be one of 0, 10, 20, 30, 40, 50")

        if time_resolution == TimeResolution.DAILY and date_time.minute != 50:
            raise ValueError("daily RADOLAN is set for minute 50")

        file_index = create_file_index_for_radolan(time_resolution)

        if date_time < file_index[DWDMetaColumns.DATETIME.value].min() or date_time > file_index[DWDMetaColumns.DATETIME.value].max():
            raise DatetimeOutOfRangeError(
                f"RADOLAN is not available for datetime {str(date_time)}")

        if prefer_local:
            try:
                data.append(
                    (
                        date_time,
                        restore_radolan_data(
                            date_time,
                            time_resolution,
                            folder
                        )
                    )
                )

                log.info(f"RADOLAN data for {str(date_time)} restored from local")

                continue
            except FileNotFoundError:
                log.info(f"RADOLAN data for {str(date_time)} will be collected from internet")

        remote_radolan_file_path = create_filepath_for_radolan(date_time, time_resolution)

        date_time_and_file = download_radolan_data(date_time, remote_radolan_file_path)

        data.append(date_time_and_file)

        if write_file:
            store_radolan_data(
                date_time_and_file,
                time_resolution,
                folder
            )

    return data
