# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import bz2
import datetime as dt
import gzip
import logging
import re
import tarfile
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
from fsspec.implementations.tar import TarFileSystem

from wetterdienst.metadata.extension import Extension
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.provider.dwd.radar.index import (
    create_fileindex_radar,
    create_fileindex_radolan_cdc,
)
from wetterdienst.provider.dwd.radar.metadata import (
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
from wetterdienst.provider.dwd.radar.util import RADAR_DT_PATTERN, get_date_from_filename, verify_hdf5
from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites
from wetterdienst.settings import Settings
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.datetime import raster_minutes, round_minutes
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterator

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()

log = logging.getLogger(__name__)


@dataclass
class RadarResult:
    """
    Result object encapsulating radar data and metadata.
    Currently, this will relate to exactly one radar data file.
    """

    data: BytesIO
    timestamp: dt.datetime = None
    url: str = None
    filename: str = None

    def __getitem__(self, index):
        """
        Backward compatibility to address this instance as a tuple.

        Formerly, this returned a tuple of ``(datetime, BytesIO)``.

        :param index:
        :return:
        """
        if index == 0:  # pragma: no cover
            return self.timestamp
        elif index == 1:
            return self.data
        else:  # pragma: no cover
            raise KeyError(f"Index {index} undefined on RadarResult")


# TODO: add core class information
class DwdRadarValues:
    """
    API for DWD radar data requests.

    Request radar data from different places on the DWD data repository.

    - https://opendata.dwd.de/weather/radar/composite/
    - https://opendata.dwd.de/weather/radar/sites/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/hourly/radolan/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/5_minutes/radolan/
    """

    def __init__(
        self,
        parameter: str | DwdRadarParameter,
        site: DwdRadarSite | None = None,
        fmt: DwdRadarDataFormat | None = None,
        subset: DwdRadarDataSubset | None = None,
        elevation: int | None = None,
        start_date: str | dt.datetime | DwdRadarDate | None = None,
        end_date: str | dt.datetime | dt.timedelta | None = None,
        resolution: str | Resolution | DwdRadarResolution | None = None,
        period: str | Period | DwdRadarPeriod | None = None,
        settings: Settings | None = None,
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
            start_date = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(minutes=5)
            end_date = None

        if start_date == DwdRadarDate.MOST_RECENT and parameter == DwdRadarParameter.RADOLAN_CDC:
            start_date = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(minutes=50)
            end_date = None

        # Evaluate "RadarDate.CURRENT" for "start_date".
        if start_date == DwdRadarDate.CURRENT:
            start_date = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None)
            if parameter == DwdRadarParameter.RADOLAN_CDC:
                if start_date.minute < 20:
                    start_date = start_date - dt.timedelta(hours=1)
            end_date = None

        # Evaluate "RadarDate.LATEST" for "start_date".
        if start_date == DwdRadarDate.LATEST:
            self.start_date = start_date
            self.end_date = None

        # Evaluate any datetime for "start_date".
        else:
            if isinstance(start_date, str):
                start_date = dt.datetime.fromisoformat(start_date)
            if end_date:
                if isinstance(end_date, str):
                    end_date = dt.datetime.fromisoformat(end_date)
            self.start_date = start_date
            self.end_date = end_date
            self.adjust_datetimes()

        self.settings = settings or Settings.default()

    def __str__(self):
        return (
            f"DWDRadarRequest("
            f"parameter={self.parameter}, "
            f"site={self.site}, "
            f"format={self.format}, "
            f"resolution={self.resolution},"
            f"date={self.start_date}/{self.end_date})"
        )

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

    def adjust_datetimes(self):
        """
        Adjust ``start_date`` and ``end_date`` attributes to match
        minute marks for respective RadarParameter.

        - RADOLAN_CDC is always published at HH:50.
          https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/recent/bin/

        - RW_REFLECTIVITY is published each 10 minutes.
          https://opendata.dwd.de/weather/radar/radolan/rw/

        - RQ_REFLECTIVITY is published each 15 minutes.
          https://opendata.dwd.de/weather/radar/radvor/rq/

        - All other radar formats are published in intervals of 5 minutes.
          https://opendata.dwd.de/weather/radar/composit/fx/
          https://opendata.dwd.de/weather/radar/sites/dx/boo/

        """

        if self.parameter == DwdRadarParameter.RADOLAN_CDC or self.parameter == DwdRadarParameter.SF_REFLECTIVITY:
            # Align "start_date" to the most recent 50 minute mark available.
            self.start_date = raster_minutes(self.start_date, 50)

            # When "end_date" is given as timedelta, resolve it.
            if isinstance(self.end_date, dt.timedelta):
                self.end_date = self.start_date + self.end_date

            # Use "end_date = start_date" to make the machinery
            # pick a single file from the fileindex.
            if not self.end_date:
                self.end_date = self.start_date + dt.timedelta(microseconds=1)

        elif self.parameter == DwdRadarParameter.RQ_REFLECTIVITY:
            # Align "start_date" to the 15 minute mark before tm.
            self.start_date = round_minutes(self.start_date, 15)

            # When "end_date" is given as timedelta, resolve it.
            if isinstance(self.end_date, dt.timedelta):
                self.end_date = self.start_date + self.end_date - dt.timedelta(seconds=1)

            # Expand "end_date" to the end of the 15 minute mark.
            if self.end_date is None:
                self.end_date = self.start_date + dt.timedelta(minutes=15) - dt.timedelta(seconds=1)

        elif self.parameter == DwdRadarParameter.RW_REFLECTIVITY:
            # Align "start_date" to the 5 minute mark before tm.
            self.start_date = round_minutes(self.start_date, 10)

            # When "end_date" is given as timedelta, resolve it.
            if isinstance(self.end_date, dt.timedelta):
                self.end_date = self.start_date + self.end_date - dt.timedelta(seconds=1)

            # Expand "end_date" to the end of the 10 minute mark.
            if self.end_date is None:
                self.end_date = self.start_date + dt.timedelta(minutes=10) - dt.timedelta(seconds=1)
        else:
            # Align "start_date" to the 5 minute mark before tm.
            self.start_date = round_minutes(self.start_date, 5)

            # When "end_date" is given as timedelta, resolve it.
            if isinstance(self.end_date, dt.timedelta):
                self.end_date = self.start_date + self.end_date - dt.timedelta(seconds=1)

            # Expand "end_date" to the end of the 5 minute mark.
            if self.end_date is None:
                self.end_date = self.start_date + dt.timedelta(minutes=5) - dt.timedelta(seconds=1)

    def query(self) -> Iterator[RadarResult]:
        """
        Send request(s) and return generator of ``RadarResult`` instances.

        :return: Generator of ``RadarResult`` instances.
        """
        log.info(f"acquiring radar data for {str(self)}")
        # Find latest file.
        if self.start_date == DwdRadarDate.LATEST:
            file_index = create_fileindex_radar(
                parameter=self.parameter,
                site=self.site,
                fmt=self.format,
                parse_datetime=False,
                settings=self.settings,
            )

            # Find "-latest-" or "LATEST" or similar file.
            latest_file = (
                file_index.filter(pl.col("filename").str.to_lowercase().str.contains("latest"))
                .get_column("filename")
                .item()
            )

            # Yield single "RadarResult" item.
            result = next(self._download_generic_data(url=latest_file))
            yield result

        else:
            if self.parameter == DwdRadarParameter.RADOLAN_CDC:
                if self.period:
                    period_types = [self.period]
                else:
                    period_types = [
                        Period.RECENT,
                        Period.HISTORICAL,
                    ]

                results = []
                for period in period_types:
                    file_index = create_fileindex_radolan_cdc(
                        resolution=self.resolution,
                        period=period,
                        settings=self.settings,
                    )

                    # Filter for dates range if start_date and end_date are defined.
                    if period == Period.RECENT:
                        file_index = file_index.filter(
                            pl.col("datetime").is_between(self.start_date, self.end_date, closed="both"),
                        )

                    # This is for matching historical data, e.g. "RW-200509.tar.gz".
                    else:
                        file_index = file_index.filter(
                            pl.col("datetime").dt.year().eq(self.start_date.year)
                            & pl.col("datetime").dt.month().eq(self.start_date.month),
                        )

                    results.append(file_index)

                file_index = pl.concat(results)

                if file_index.is_empty():
                    # TODO: Extend this log message.
                    log.warning(f"No radar file found for {self.parameter}, {self.site}, {self.format}")
                    return

                # Iterate list of files and yield "RadarResult" items.
                for row in file_index.iter_rows(named=True):
                    url = row["filename"]
                    yield from self._download_radolan_data(url, self.start_date, self.end_date)

            else:
                file_index = create_fileindex_radar(
                    parameter=self.parameter,
                    site=self.site,
                    fmt=self.format,
                    subset=self.subset,
                    parse_datetime=True,
                    settings=self.settings,
                )

                # Filter for dates range if start_date and end_date are defined.
                file_index = file_index.filter(
                    pl.col("datetime").is_between(self.start_date, self.end_date, closed="both"),
                )

                # Filter SWEEP_VOL_VELOCITY_H and SWEEP_VOL_REFLECTIVITY_H by elevation.
                if self.elevation is not None:
                    file_index = file_index.filter(
                        pl.col("filename").str.contains(f"vradh_{self.elevation:02d}")
                        | pl.col("filename").str.contains(f"sweep_vol_v_{self.elevation}")
                        | pl.col("filename").str.contains(f"dbzh_{self.elevation:02d}")
                        | pl.col("filename").str.contains(f"sweep_vol_z_{self.elevation}"),
                    )

                if file_index.is_empty():
                    log.warning(f"No radar file found for {self.parameter}, {self.site}, {self.format}")
                    return

                # Iterate list of files and yield "RadarResult" items.
                for row in file_index.iter_rows(named=True):
                    date_time = row["datetime"]
                    url = row["filename"]

                    for result in self._download_generic_data(url=url):
                        if not result.timestamp:
                            result.timestamp = date_time

                        if self.format == DwdRadarDataFormat.HDF5:
                            try:
                                verify_hdf5(result.data)
                            except Exception as e:  # pragma: no cover
                                log.exception(f"Unable to read HDF5 file. {e}")
                        yield result

    @staticmethod
    def _should_cache_download(url: str) -> bool:  # pragma: no cover
        """
        Determine whether this specific result should be cached.

        Here, we don't want to cache any files containing "-latest-" in their filenames.

        :param url: url string which is used to decide if result is cached
        :return: When cache should be dismissed, return False. Otherwise, return True.
        """
        if "-latest-" in url:
            return False
        return True

    def _download_generic_data(self, url: str) -> Iterator[RadarResult]:
        """
        Download radar data.

        :param url:         The URL to the file on the DWD server
        :return:            The file in binary, either an archive of one file
                            or an archive of multiple files.
        """

        ttl = CacheExpiry.FIVE_MINUTES
        if not self._should_cache_download(url):
            ttl = CacheExpiry.NO_CACHE
        log.info(f"Downloading file {url}.")
        data = download_file(url=url, ttl=ttl, settings=self.settings)

        # RadarParameter.FX_REFLECTIVITY
        if url.endswith(Extension.TAR_BZ2.value):
            tfs = TarFileSystem(data, compression="bz2")
            for file in tfs.glob("*"):
                try:
                    file_name = file.name
                except AttributeError:
                    file_name = file

                yield RadarResult(
                    data=BytesIO(tfs.open(file).read()),
                    timestamp=get_date_from_filename(
                        file_name,
                        pattern=RADAR_DT_PATTERN,
                        formats=[DatetimeFormat.ymdhm.value],
                    ),
                    filename=file_name,
                )

        # RadarParameter.WN_REFLECTIVITY, RADAR_PARAMETERS_SWEEPS (BUFR)  # noqa: E800, ERA001
        elif url.endswith(Extension.BZ2.value):
            with bz2.BZ2File(data, mode="rb") as archive:
                data = BytesIO(archive.read())
                yield RadarResult(
                    url=url,
                    data=data,
                    timestamp=get_date_from_filename(
                        url,
                        pattern=RADAR_DT_PATTERN,
                        formats=[DatetimeFormat.ymdhm.value],
                    ),
                )

        # RADAR_PARAMETERS_RADVOR
        elif url.endswith(Extension.GZ.value):
            with gzip.GzipFile(fileobj=data, mode="rb") as archive:
                data = BytesIO(archive.read())
                yield RadarResult(
                    url=url,
                    data=data,
                    timestamp=get_date_from_filename(
                        url,
                        pattern=RADAR_DT_PATTERN,
                        formats=[DatetimeFormat.ymdhm.value],
                    ),
                )

        else:
            yield RadarResult(
                url=url,
                data=data,
                timestamp=get_date_from_filename(url, pattern=RADAR_DT_PATTERN, formats=[DatetimeFormat.ymdhm.value]),
            )

    def _download_radolan_data(self, url: str, start_date, end_date) -> Iterator[RadarResult]:
        """
        Function used to download RADOLAN_CDC data for a given datetime. The function calls
        a separate download function that is cached for reuse which is especially used for
        historical data that comes packaged for multiple time steps within a single archive.
        :param url:         The URL to the file that has the data
                            for the requested datetime, either an archive of multiple files
                            for a datetime in historical time or an archive with one file
                            for the recent RADOLAN file
        :param start_date:
        :param end_date:
        :return:            ``RadarResult`` item
        """
        archive_in_bytes = self.__download_radolan_data(url=url, settings=self.settings)

        for result in self._extract_radolan_data(archive_in_bytes):
            if not result.timestamp:
                # if result has no timestamp, take it from main url instead of files in archive
                datetime_string = re.findall(r"\d{10}", url)[0]
                date_time = dt.datetime.strptime("20" + datetime_string, "%Y%m%d%H%M")
                result.timestamp = date_time
            if result.timestamp < start_date or result.timestamp > end_date:
                continue
            result.url = url

            yield result

    @staticmethod
    def __download_radolan_data(url: str, settings: Settings) -> BytesIO:
        """
        Function (cached) that downloads the RADOLAN_CDC file.

        Args:
            url: the file path to the file on the DWD server

        Returns:
            the file in binary, either an archive of one file or an archive of multiple
            files
        """
        log.info(f"Downloading file {url}.")
        return download_file(url=url, ttl=CacheExpiry.TWELVE_HOURS, settings=settings)

    @staticmethod
    def _extract_radolan_data(archive_in_bytes: BytesIO) -> Iterator[RadarResult]:
        """
        Function used to extract RADOLAN_CDC file for the requested datetime
        from the downloaded archive.

        Args:
            archive_in_bytes: downloaded archive of RADOLAN file
        Returns:
            the datetime formatted as string and the RADOLAN file for the datetime
        """
        # First try to unpack archive from archive (case for historical data)
        try:
            tfs = TarFileSystem(archive_in_bytes, compression="gzip")

            for file in tfs.glob("*"):
                datetime_string = re.findall(r"\d{10}", file)[0]
                date_time = dt.datetime.strptime("20" + datetime_string, "%Y%m%d%H%M")
                file_in_bytes = tfs.tar.extractfile(file).read()

                yield RadarResult(
                    data=BytesIO(file_in_bytes),
                    timestamp=date_time,
                    filename=file,
                )

        # Otherwise, if there's an error the data is from recent time period and only has to
        # be unpacked once
        except tarfile.ReadError:
            # Seek again for reused purpose
            archive_in_bytes.seek(0)
            with gzip.GzipFile(fileobj=archive_in_bytes, mode="rb") as gz_file:
                yield RadarResult(data=BytesIO(gz_file.read()), timestamp=None, filename=gz_file.name)


class DwdRadarSites(OperaRadarSites):
    def __init__(self):
        # Load all OPERA radar sites.
        super().__init__()

        # Restrict available sites to the list of OPERA radar sites in Germany.
        self.sites = self.by_country_name(country_name="Germany")
