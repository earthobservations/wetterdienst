# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from datetime import datetime, timedelta
from typing import Optional, Union

import pandas as pd
from tqdm import tqdm

from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.radar.access import RadarResult, collect_radar_data
from wetterdienst.provider.dwd.radar.metadata import (
    RADAR_PARAMETERS_RADOLAN,
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarPeriod,
    DwdRadarResolution,
)
from wetterdienst.provider.dwd.radar.metadata.parameter import (
    DwdRadarDate,
    DwdRadarParameter,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite
from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites
from wetterdienst.util.datetime import raster_minutes, round_minutes
from wetterdienst.util.enumeration import parse_enumeration_from_template

log = logging.getLogger(__name__)


# TODO: add core class information
class DwdRadarValues:
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
        parameter: Union[str, DwdRadarParameter],
        site: Optional[DwdRadarSite] = None,
        fmt: Optional[DwdRadarDataFormat] = None,
        subset: Optional[DwdRadarDataSubset] = None,
        elevation: Optional[int] = None,
        start_date: Optional[Union[str, datetime, DwdRadarDate]] = None,
        end_date: Optional[Union[str, datetime, timedelta]] = None,
        resolution: Optional[Union[str, Resolution, DwdRadarResolution]] = None,
        period: Optional[Union[str, Period, DwdRadarPeriod]] = None,
    ) -> None:
        """
        :param parameter:       The radar moment to request
        :param site:            Site/station if parameter is one of
                                RADAR_PARAMETERS_SITES
        :param fmt:          Data format (BINARY, BUFR, HDF5)
        :param subset:          The subset (simple or polarimetric) for HDF5 data.
        :param start_date:      Start date
        :param end_date:        End date
        :param resolution: Time resolution for RadarParameter.RADOLAN_CDC,
                                either daily or hourly or 5 minutes.
        :param period:     Period type for RadarParameter.RADOLAN_CDC
        """

        # Convert parameters to enum types.
        self.parameter = parse_enumeration_from_template(parameter, DwdRadarParameter)
        self.site = parse_enumeration_from_template(site, DwdRadarSite)
        self.format = parse_enumeration_from_template(fmt, DwdRadarDataFormat)
        self.subset = parse_enumeration_from_template(subset, DwdRadarDataSubset)
        self.elevation = elevation and int(elevation)
        self.resolution: Resolution = parse_enumeration_from_template(resolution, DwdRadarResolution, Resolution)
        self.period: Period = parse_enumeration_from_template(period, DwdRadarPeriod, Period)

        # Sanity checks.
        if self.parameter == DwdRadarParameter.RADOLAN_CDC:

            if self.resolution not in (
                Resolution.HOURLY,
                Resolution.DAILY,
            ):
                raise ValueError("RADOLAN_CDC only supports daily and hourly resolutions")

        elevation_parameters = [
            DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
            DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H,
        ]
        if self.elevation is not None and self.parameter not in elevation_parameters:
            raise ValueError(f"Argument 'elevation' only valid for parameter={elevation_parameters}")

        if start_date == DwdRadarDate.LATEST:

            # HDF5 folders do not have "-latest-" files.
            if self.parameter == DwdRadarParameter.RADOLAN_CDC:
                raise ValueError("RADOLAN_CDC data has no '-latest-' files")

            # HDF5 folders do not have "-latest-" files.
            if self.format == DwdRadarDataFormat.HDF5:
                raise ValueError("HDF5 data has no '-latest-' files")

        if start_date == DwdRadarDate.CURRENT and not self.period:
            self.period = Period.RECENT

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
        if fmt == DwdRadarDataFormat.HDF5 and start_date == DwdRadarDate.MOST_RECENT:
            start_date = datetime.utcnow() - timedelta(minutes=5)
            end_date = None

        if start_date == DwdRadarDate.MOST_RECENT and parameter == DwdRadarParameter.RADOLAN_CDC:
            start_date = datetime.utcnow() - timedelta(minutes=50)
            end_date = None

        # Evaluate "RadarDate.CURRENT" for "start_date".
        if start_date == DwdRadarDate.CURRENT:
            start_date = datetime.utcnow()
            end_date = None

        # Evaluate "RadarDate.LATEST" for "start_date".
        if start_date == DwdRadarDate.LATEST:
            self.start_date = start_date
            self.end_date = None

        # Evaluate any datetime for "start_date".
        else:
            self.start_date = pd.to_datetime(start_date, infer_datetime_format=True)
            self.end_date = end_date
            self.adjust_datetimes()

        log.info(
            f"DWDRadarRequest with {self.parameter}, {self.site}, "
            f"{self.format}, {self.resolution} "
            f"for {self.start_date}/{self.end_date}"
        )

    def adjust_datetimes(self):
        """
        Adjust ``start_date`` and ``end_date`` attributes to match
        minute marks for respective RadarParameter.

        - RADOLAN_CDC is always published at HH:50.
          https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/recent/bin/

        - RQ_REFLECTIVITY is published each 15 minutes.
          https://opendata.dwd.de/weather/radar/radvor/rq/

        - All other radar formats are published in intervals of 5 minutes.
          https://opendata.dwd.de/weather/radar/composit/fx/
          https://opendata.dwd.de/weather/radar/sites/dx/boo/

        """

        if self.parameter == DwdRadarParameter.RADOLAN_CDC or self.parameter in RADAR_PARAMETERS_RADOLAN:

            # Align "start_date" to the most recent 50 minute mark available.
            self.start_date = raster_minutes(self.start_date, 50)

            # When "end_date" is given as timedelta, resolve it.
            if isinstance(self.end_date, timedelta):
                self.end_date = self.start_date + self.end_date

            # Use "end_date = start_date" to make the machinery
            # pick a single file from the fileindex.
            if self.end_date is None:
                self.end_date = self.start_date + timedelta(microseconds=1)

        elif self.parameter == DwdRadarParameter.RQ_REFLECTIVITY:

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
            and self.resolution == other.resolution
            and self.period == other.period
        )

    def query(self) -> RadarResult:
        """
        Send request(s) and return generator of ``RadarResult`` instances.

        :return: Generator of ``RadarResult`` instances.
        """
        log.info(
            f"Collecting radar data for "
            f"site={self.site}, "
            f"parameter={self.parameter}, "
            f"subset={self.subset}, "
            f"elevation={self.elevation}, "
            f"resolution={self.resolution}, "
            f"period={self.period}"
        )
        progressbar = tqdm(total=240)
        for item in collect_radar_data(
            parameter=self.parameter,
            site=self.site,
            fmt=self.format,
            subset=self.subset,
            elevation=self.elevation,
            start_date=self.start_date,
            end_date=self.end_date,
            resolution=self.resolution,
            period=self.period,
        ):
            progressbar.update()
            yield item


class DwdRadarSites(OperaRadarSites):
    def __init__(self):

        # Load all OPERA radar sites.
        super().__init__()

        # Restrict available sites to the list of OPERA radar sites in Germany.
        self.sites = self.by_countryname(name="Germany")
