""" Functions for DWD RADOLAN collection """
from io import BytesIO
from pathlib import Path
from typing import Union, List, Tuple, Optional, Generator
from datetime import datetime
import logging

import pandas as pd

from wetterdienst.additionals.functions import parse_enumeration_from_template
from wetterdienst.constants.metadata import DWD_FOLDER_MAIN
from wetterdienst.data_storing import store_radolan_data, restore_radolan_data
from wetterdienst.download.download import download_radolan_data
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.file_path_handling.file_list_creation import (
    create_filepath_for_radolan,
)
from wetterdienst.indexing.file_index_creation import create_file_index_for_radolan

log = logging.getLogger(__name__)


class DWDRadolanRequest:
    """
    API for DWD RADOLAN data requests
    """

    def __init__(
        self,
        time_resolution: Union[str, TimeResolution],
        date_times: Optional[Union[str, List[Union[str, datetime]]]] = None,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        prefer_local: bool = False,
        write_file: bool = False,
        folder: Union[str, Path] = DWD_FOLDER_MAIN,
    ):

        time_resolution = parse_enumeration_from_template(
            time_resolution, TimeResolution
        )

        if time_resolution not in (TimeResolution.HOURLY, TimeResolution.DAILY):
            raise ValueError("RADOLAN only supports hourly and daily resolution.")

        self.time_resolution = time_resolution

        if date_times == "latest":
            file_index_radolan = create_file_index_for_radolan(time_resolution)

            self.date_times = pd.Series(
                file_index_radolan[DWDMetaColumns.DATETIME.value][-1:]
            )
        elif date_times:
            self.date_times = pd.Series(
                pd.to_datetime(date_times, infer_datetime_format=True)
            )
        else:
            self.date_times = pd.Series(
                pd.date_range(
                    pd.to_datetime(start_date, infer_datetime_format=True),
                    pd.to_datetime(end_date, infer_datetime_format=True),
                )
            )

        self.date_times = self.date_times.dt.floor(freq="H") + pd.Timedelta(minutes=50)

        self.date_times = self.date_times.drop_duplicates().sort_values()

        self.prefer_local = prefer_local
        self.write_file = write_file
        self.folder = folder

    def __eq__(self, other):
        return (
            self.time_resolution == other.time_resolution
            and self.date_times.values.tolist() == other.date_times.values.tolist()
        )

    def __str__(self):
        return ", ".join(
            [
                self.time_resolution.value,
                "& ".join([str(date_time) for date_time in self.date_times]),
            ]
        )

    def collect_data(self) -> Generator[Tuple[datetime, BytesIO], None, None]:
        """
        Function used to get the data for the request returned as generator.

        Returns:
            for each datetime the same datetime and file in bytes
        """
        for date_time in self.date_times:
            _, file_in_bytes = collect_radolan_data(
                time_resolution=self.time_resolution,
                date_times=[date_time],
                write_file=self.write_file,
                folder=self.folder,
            )[0]

            yield date_time, file_in_bytes


def collect_radolan_data(
    date_times: List[datetime],
    time_resolution: TimeResolution,
    prefer_local: bool = False,
    write_file: bool = False,
    folder: Union[str, Path] = DWD_FOLDER_MAIN,
) -> List[Tuple[datetime, BytesIO]]:
    """
    Function used to collect RADOLAN data for given datetimes and a time resolution.
    Additionally the file can be written to a local folder and read from there as well.
    Args:
        date_times: list of datetime objects for which RADOLAN shall be acquired
        time_resolution: the time resolution for requested data, either hourly or daily
        prefer_local: boolean if file should be read from local store instead
        write_file: boolean if file should be stored on the drive
        folder: path for storage

    Returns:
        list of tuples of a datetime and the corresponding file in bytes
    """
    if time_resolution not in (TimeResolution.HOURLY, TimeResolution.DAILY):
        raise ValueError("RADOLAN is only offered in hourly and daily resolution.")

    data = []
    # datetime = pd.to_datetime(datetime).replace(tzinfo=None)
    for date_time in date_times:
        if prefer_local:
            try:
                data.append(
                    (
                        date_time,
                        restore_radolan_data(date_time, time_resolution, folder),
                    )
                )

                log.info(f"RADOLAN data for {str(date_time)} restored from local")

                continue
            except FileNotFoundError:
                log.info(
                    f"RADOLAN data for {str(date_time)} will be collected from internet"
                )

        remote_radolan_file_path = create_filepath_for_radolan(
            date_time, time_resolution
        )

        if remote_radolan_file_path == "":
            log.warning(f"RADOLAN not found for {str(date_time)}, will be skipped.")
            continue

        date_time_and_file = download_radolan_data(date_time, remote_radolan_file_path)

        data.append(date_time_and_file)

        if write_file:
            store_radolan_data(date_time_and_file, time_resolution, folder)

    return data
