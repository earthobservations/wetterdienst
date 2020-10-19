import logging
from datetime import datetime, timedelta
from typing import Union, Optional

import pandas as pd

from wetterdienst.dwd.radar.access import collect_radar_data, RadarResult
from wetterdienst.dwd.radar.metadata import (
    RadarParameter,
    RadarDataFormat,
    RadarDate,
    RadarDataSubset,
    RADAR_PARAMETERS_RADOLAN,
    DWDRadarTimeResolution,
    DWDRadarPeriodType,
)
from wetterdienst.dwd.radar.sites import RadarSite, RADAR_LOCATIONS
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.datetime import round_minutes, raster_minutes

log = logging.getLogger(__name__)


class DWDRadarData:
    """
    API for DWD radar data requests.

    Request radar data from different places on the DWD data repository.

    - https://opendata.dwd.de/weather/radar/composit/
    - https://opendata.dwd.de/weather/radar/sites/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/hourly/radolan/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/5_minutes/radolan/
    """

    def __init__(
        self,
        parameter: Union[str, RadarParameter],
        site: Optional[RadarSite] = None,
        format: Optional[RadarDataFormat] = None,
        subset: Optional[RadarDataSubset] = None,
        elevation: Optional[int] = None,
        start_date: Optional[Union[str, datetime, RadarDate]] = None,
        end_date: Optional[Union[str, datetime, timedelta]] = None,
        time_resolution: Optional[Union[str, DWDRadarTimeResolution]] = None,
        period_type: Optional[Union[str, DWDRadarPeriodType]] = None,
    ) -> None:
        """
        :param parameter:       The radar moment to request
        :param site:            Site/station if parameter is one of
                                RADAR_PARAMETERS_SITES
        :param format:          Data format (BINARY, BUFR, HDF5)
        :param subset:          The subset (simple or polarimetric) for HDF5 data.
        :param start_date:      Start date
        :param end_date:        End date
        :param time_resolution: Time resolution for RadarParameter.RADOLAN_CDC,
                                either daily or hourly or 5 minutes.
        :param period_type:     Period type for RadarParameter.RADOLAN_CDC
        :return:                Nothing for now.
        """

        # Convert parameters to enum types.
        self.parameter = RadarParameter(parameter)
        self.site = parse_enumeration_from_template(site, RadarSite)
        self.format = parse_enumeration_from_template(format, RadarDataFormat)
        self.subset = parse_enumeration_from_template(subset, RadarDataSubset)
        self.elevation = elevation and int(elevation)
        self.time_resolution = parse_enumeration_from_template(
            time_resolution, DWDRadarTimeResolution
        )
        self.period_type = parse_enumeration_from_template(
            period_type, DWDRadarPeriodType
        )

        # Sanity checks.
        if self.parameter == RadarParameter.RADOLAN_CDC:

            if time_resolution not in (
                DWDRadarTimeResolution.DAILY,
                DWDRadarTimeResolution.HOURLY,
                DWDRadarTimeResolution.MINUTE_5,
            ):
                raise ValueError(
                    "RADOLAN_CDC only supports daily, hourly and 5 minutes resolutions"
                )

        elevation_parameters = [
            RadarParameter.SWEEP_VOL_VELOCITY_H,
            RadarParameter.SWEEP_VOL_REFLECTIVITY_H,
        ]
        if self.elevation is not None and self.parameter not in elevation_parameters:
            raise ValueError(
                f"Argument 'elevation' only valid for parameter={elevation_parameters}"
            )

        if start_date == RadarDate.LATEST:

            # HDF5 folders do not have "-latest-" files.
            if self.parameter == RadarParameter.RADOLAN_CDC:
                raise ValueError("RADOLAN_CDC data has no '-latest-' files")

            # HDF5 folders do not have "-latest-" files.
            if self.format == RadarDataFormat.HDF5:
                raise ValueError("HDF5 data has no '-latest-' files")

        if start_date == RadarDate.CURRENT and not self.period_type:
            self.period_type = DWDRadarPeriodType.RECENT

        # Evaluate "RadarDate.MOST_RECENT" for "start_date".
        #
        # HDF5 folders do not have "-latest-" files, so we will have to synthesize them
        # appropriately by going back to the second last volume of 5 minute intervals.
        #
        # The reason for this is that when requesting sweep data in HDF5 format at
        # e.g. 15:03, not all files will be available on the DWD data repository for
        # the whole volume (e.g. covering all elevation levels) within the time range
        # of 15:00-15:04:59 as they apparently will be added incrementally while the
        # scan is performed.
        #
        # So, we will be better off making the machinery retrieve the latest "full"
        # volume by addressing the **previous** volume. So, when requesting data at
        # 15:03, it will retrieve 14:55:00-14:59:59.
        #
        if format == RadarDataFormat.HDF5 and start_date == RadarDate.MOST_RECENT:
            start_date = datetime.utcnow() - timedelta(minutes=5)
            end_date = None

        if (
            start_date == RadarDate.MOST_RECENT
            and parameter == RadarParameter.RADOLAN_CDC
        ):
            start_date = datetime.utcnow() - timedelta(minutes=50)
            end_date = None

        # Evaluate "RadarDate.CURRENT" for "start_date".
        if start_date == RadarDate.CURRENT:
            start_date = datetime.utcnow()
            end_date = None

        # Evaluate "RadarDate.LATEST" for "start_date".
        if start_date == RadarDate.LATEST:
            self.start_date = start_date
            self.end_date = None

        # Evaluate any datetime for "start_date".
        else:
            self.start_date = pd.to_datetime(start_date, infer_datetime_format=True)
            self.end_date = end_date
            self.adjust_datetimes()

        log.info(
            f"DWDRadarRequest with {self.parameter}, {self.site}, "
            f"{self.format}, {self.time_resolution} "
            f"for {self.start_date}/{self.end_date}"
        )

        # print(self.start_date, self.end_date)

    def adjust_datetimes(self):
        """
        Adjust ``start_date`` and ``end_date`` attributes to match
        minute marks for respective RadarParameter.

        - RADOLAN_CDC is always published at HH:50.
          https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/recent/bin/  # noqa:E501,B950

        - RQ_REFLECTIVITY is published each 15 minutes.
          https://opendata.dwd.de/weather/radar/radvor/rq/

        - All other radar formats are published in intervals of 5 minutes.
          https://opendata.dwd.de/weather/radar/composit/fx/
          https://opendata.dwd.de/weather/radar/sites/dx/boo/

        """

        if (
            self.parameter == RadarParameter.RADOLAN_CDC
            or self.parameter in RADAR_PARAMETERS_RADOLAN
        ):

            # Align "start_date" to the most recent 50 minute mark available.
            self.start_date = raster_minutes(self.start_date, 50)

            # When "end_date" is given as timedelta, resolve it.
            if isinstance(self.end_date, timedelta):
                self.end_date = self.start_date + self.end_date

            # Use "end_date = start_date" to make the machinery
            # pick a single file from the fileindex.
            if self.end_date is None:
                self.end_date = self.start_date + timedelta(microseconds=1)

        elif self.parameter == RadarParameter.RQ_REFLECTIVITY:

            # Align "start_date" to the 15 minute mark before tm.
            self.start_date = round_minutes(self.start_date, 15)

            # When "end_date" is given as timedelta, resolve it.
            if isinstance(self.end_date, timedelta):
                self.end_date = self.start_date + self.end_date

            # Expand "end_date" to the end of the 5 minute mark.
            if self.end_date is None:
                self.end_date = self.start_date + timedelta(minutes=15)

        else:

            # Align "start_date" to the 5 minute mark before tm.
            self.start_date = round_minutes(self.start_date, 5)

            # When "end_date" is given as timedelta, resolve it.
            if isinstance(self.end_date, timedelta):
                self.end_date = self.start_date + self.end_date

            # Expand "end_date" to the end of the 5 minute mark.
            if self.end_date is None:
                self.end_date = self.start_date + timedelta(minutes=5)

    def __eq__(self, other):
        return (
            self.parameter == other.parameter
            and self.site == other.site
            and self.format == other.format
            and self.subset == other.subset
            and self.start_date == other.start_date
            and self.end_date == other.end_date
            and self.time_resolution == other.time_resolution
            and self.period_type == other.period_type
        )

    def collect_data(self) -> RadarResult:
        """
        Send request(s) and return generator of ``RadarResult`` instances.

        :return: Generator of ``RadarResult`` instances.
        """
        return collect_radar_data(
            parameter=self.parameter,
            site=self.site,
            format=self.format,
            subset=self.subset,
            elevation=self.elevation,
            start_date=self.start_date,
            end_date=self.end_date,
            time_resolution=self.time_resolution,
            period_type=self.period_type,
        )

    @staticmethod
    def get_sites():
        return RADAR_LOCATIONS
