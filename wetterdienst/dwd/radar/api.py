from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Union, Optional, List, Generator, Tuple

import pandas as pd

from wetterdienst import TimeResolution, PeriodType
from wetterdienst.dwd.metadata.constants import DWD_FOLDER_MAIN
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.radar.access import collect_radar_data
from wetterdienst.dwd.radar.index import create_file_index_for_radolan,\
    _create_fileindex_radar
from wetterdienst.dwd.radar.metadata import (
    RadarParameter,
    RadarDataType
)
from wetterdienst.dwd.radar.sites import RadarSites
from wetterdienst.dwd.util import parse_enumeration_from_template


class DWDRadarRequest:
    """
    API for DWD RADOLAN data requests.
    """

    def __init__(
        self,
        time_resolution: Union[str, TimeResolution],
        radar_parameter: Union[str, RadarParameter],
        period_type: Optional[PeriodType] = None,
        radar_site: Optional[RadarSites] = None,
        radar_data_type: Optional[RadarDataType] = None,
        date_times: Optional[Union[str, List[Union[str, datetime]]]] = None,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        prefer_local: bool = False,
        write_file: bool = False,
        folder: Union[str, Path] = DWD_FOLDER_MAIN,
    ) -> None:
        """

        :param time_resolution: Time resolution enumeration, either hourly or daily
        :param radar_parameter: Radar parameter enumeration for different radar moments and derived data
        :param period_type:     period type of PeriodType enumeration
        :param radar_site:      Site of the radar if parameter is one of RADAR_PARAMETERS_SITES
        :param radar_data_type: Some radar data are available in different data types
        :param date_times:      List of datetimes for which radar data is requested.
                                Minutes have o be defined (HOUR:50), otherwise rounded
                                to 50 minutes as of its provision.
        :param start_date:      Alternative to datetimes, giving a start and end date
        :param end_date:        Alternative to datetimes, giving a start and end date
        :param prefer_local:    Radar data should rather be loaded from disk, for
                                processing purposes
        :param write_file:      File should be stored on drive
        :param folder:          Folder where to store radar data

        :return:                Nothing for now.
        """
        time_resolution = parse_enumeration_from_template(
            time_resolution, TimeResolution
        )
        self.radar_parameter = RadarParameter(radar_parameter)

        if time_resolution not in (TimeResolution.HOURLY, TimeResolution.DAILY) and self.radar_parameter == RadarParameter.RADOLAN:
            raise ValueError("RADOLAN only supports hourly and daily resolution.")

        self.time_resolution = time_resolution

        if self.radar_parameter == RadarParameter.RADOLAN:
            file_index = create_file_index_for_radolan(time_resolution)
        else:
            file_index = _create_fileindex_radar(
                self.radar_parameter,
                time_resolution,
                period_type,
                radar_site,
                radar_data_type
            )

        self.__build_date_times(file_index,
                                date_times,
                                start_date,
                                end_date)

        if self.radar_parameter == RadarParameter.RADOLAN:
            self.date_times = self.date_times.dt.floor(freq="H") + pd.Timedelta(minutes=50)

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
                parameter=self.radar_parameter,
                time_resolution=self.time_resolution,
                date_times=[date_time],
                write_file=self.write_file,
                folder=self.folder,
            )[0]

            yield date_time, file_in_bytes

    def __build_date_times(self,
                           file_index: Optional[pd.DataFrame] = None,
                           date_times: Optional[Union[str, List[Union[str, datetime]]]] = None,
                            start_date: Optional[Union[str, datetime]] = None,
                            end_date: Optional[Union[str, datetime]] = None
                           ):
        """
        builds a pd.Series contains datetime objects
        based on the fileindex or other given parameters
        @todo: use pd.DateTimeIndex instead of pd.Series
        """
        if date_times == "latest":
            self.date_times = pd.Series(
                file_index[DWDMetaColumns.DATETIME.value][-1:]
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

        self.date_times = self.date_times.drop_duplicates().sort_values()