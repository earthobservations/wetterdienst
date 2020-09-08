from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Union, Optional, List, Generator, Tuple

import pandas as pd

from wetterdienst import TimeResolution
from wetterdienst.dwd.metadata.constants import DWD_FOLDER_MAIN
from wetterdienst.dwd.radolan.access import collect_radar_data
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.radolan.index import create_file_index_for_radolan
from wetterdienst.dwd.util import parse_enumeration_from_template


class DWDRadolanRequest:
    """
    API for DWD RADOLAN data requests.
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
    ) -> None:
        """

        :param time_resolution: Time resolution enumeration, either hourly or daily
        :param date_times:      List of datetimes for which RADOLAN is requested.
                                Minutes have o be defined (HOUR:50), otherwise rounded
                                to 50 minutes as of its provision.
        :param start_date:      Alternative to datetimes, giving a start and end date
        :param end_date:        Alternative to datetimes, giving a start and end date
        :param prefer_local:    RADOLAN should rather be loaded from disk, for
                                processing purposes
        :param write_file:      File should be stored on drive
        :param folder:          Folder where to store RADOLAN data

        :return:                Nothing for now.
        """
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

        :return: For each datetime, the same datetime and file in bytes
        """
        for date_time in self.date_times:
            _, file_in_bytes = collect_radar_data(
                time_resolution=self.time_resolution,
                date_times=[date_time],
                write_file=self.write_file,
                folder=self.folder,
            )[0]

            yield date_time, file_in_bytes
