# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""API for DWD radar data requests."""

from __future__ import annotations

import bz2
import datetime as dt
import gzip
import logging
import re
import tarfile
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING, ClassVar, Self, cast
from zoneinfo import ZoneInfo

import polars as pl
from fsspec.implementations.tar import TarFileSystem

from wetterdienst.exceptions import InvalidEnumerationError, MissingDependencyError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.extension import Extension
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.renamed import refuse_renamed_arguments
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import ProviderTerms
from wetterdienst.provider.dwd.metadata import _METADATA
from wetterdienst.provider.dwd.radar.index import (
    create_fileindex_radar,
    create_fileindex_radolan_cdc,
)
from wetterdienst.provider.dwd.radar.metadata import (
    RADAR_DATA_FORMATS_NOT_PUBLISHED,
    RADAR_DATA_SUBSETS,
    RADAR_PARAMETERS_NOT_PUBLISHED,
    RADAR_PARAMETERS_SLOW,
    RADAR_PARAMETERS_SWEEPS,
    RADAR_PARAMETERS_SWEEPS_VOLUME,
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarPeriod,
    DwdRadarPolarization,
    DwdRadarResolution,
    radar_data_format,
    radar_data_subset,
    radar_polarization,
)
from wetterdienst.provider.dwd.radar.metadata.parameter import (
    DwdRadarDate,
    DwdRadarParameter,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite
from wetterdienst.provider.dwd.radar.util import (
    RADAR_DT_PATTERN,
    get_date_string_from_filename,
    read_scan_time,
    verify_hdf5,
)
from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites
from wetterdienst.settings import Settings
from wetterdienst.util.datetime import _parse_datetime_from_formats, raster_minutes, round_minutes
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterator

log = logging.getLogger(__name__)


DATETIME_FORMATS = ["%y%m%d%H%M", "%Y%m%d%H%M"]


@dataclass
class RadarResult:
    """Data class for radar data."""

    data: BytesIO
    timestamp: dt.datetime | None = None
    url: str | None = None
    filename: str | None = None

    def __getitem__(self, index: int) -> dt.datetime | BytesIO | None:
        """Backward compatibility to address this instance as a tuple.

        Formerly, this returned a tuple of ``(datetime, BytesIO)``.

        Args:
            index: index of the item to return

        Returns:
            either the timestamp or the data

        """
        if index == 0:  # pragma: no cover
            return self.timestamp
        if index == 1:
            return self.data
        # pragma: no cover
        msg = f"Index {index} undefined on RadarResult"
        raise KeyError(msg)


def _as_utc(timestamp: dt.datetime) -> dt.datetime:
    """Give the instant a bound names in UTC, a naive one being taken as UTC already."""
    utc = ZoneInfo("UTC")
    return timestamp.replace(tzinfo=utc) if timestamp.tzinfo is None else timestamp.astimezone(utc)


# TODO: add core class information
class DwdRadarValues:  # noqa: PLW1641
    """API for DWD radar data requests.

    Request radar data from different places on the DWD data repository.

    - https://opendata.dwd.de/weather/radar/composite/
    - https://opendata.dwd.de/weather/radar/radolan/
    - https://opendata.dwd.de/weather/radar/konrad3d/
    - https://opendata.dwd.de/weather/radar/mesocyclones/
    - https://opendata.dwd.de/weather/radar/sites/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/hourly/radolan/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/5_minutes/radolan/
    """

    # how `Wetterdienst.discover()` lists the network, which is no timeseries network and has no metadata model: the
    # name and the country are the provider's, the url is where the radar products are
    listing: ClassVar = {
        "name_short": _METADATA["name_short"],
        "country": _METADATA["country"],
        "kind": "radar",
        "url": "https://opendata.dwd.de/weather/radar/",
    }

    # who published the products and under which terms, which an answer about them names as a network with a
    # metadata model does through its `MetadataModel` (GH-3059)
    terms: ClassVar = ProviderTerms(
        name_local=_METADATA["name_local"],
        name_english=_METADATA["name_english"],
        country=_METADATA["country"],
        country_code=_METADATA["country_code"],
        copyright="© Deutscher Wetterdienst (DWD), radar products",
        license=_METADATA["license"],
        attribution=_METADATA["attribution"],
        url="https://opendata.dwd.de/weather/radar/",
    )

    def __new__(cls, *args: object, **kwargs: object) -> Self:  # noqa: ARG004
        """Refuse a renamed argument by naming the new one, as `TimeseriesRequest` does."""
        refuse_renamed_arguments(cls.__name__, kwargs)
        return super().__new__(cls)

    def __init__(  # noqa: C901
        self,
        parameter: str | DwdRadarParameter,
        site: DwdRadarSite | None = None,
        fmt: DwdRadarDataFormat | None = None,
        subset: DwdRadarDataSubset | None = None,
        elevation: int | None = None,
        start: str | dt.datetime | DwdRadarDate | None = None,
        end: str | dt.datetime | dt.timedelta | None = None,
        resolution: str | Resolution | DwdRadarResolution | None = None,
        period: str | Period | DwdRadarPeriod | None = None,
        settings: Settings | None = None,
        polarization: str | DwdRadarPolarization | None = None,
    ) -> None:
        """Initialize the request object.

        Args:
            parameter: requested parameter (e.g. RADOLAN_CDC)
            site: requested site (e.g. DX_REFLECTIVITY)
            fmt: requested format (e.g. BINARY), which a product is served in only one of: see RADAR_DATA_FORMATS
            subset: requested folder of a sweep (SIMPLE, POLARIMETRIC or UNFILTERED): see RADAR_DATA_SUBSETS
            elevation: requested elevation (e.g. 10)
            start: start of the requested data
            end: end of the requested data
            resolution: requested resolution (e.g. MINUTE_5)
            period: requested period (e.g. RECENT)
            settings: settings for the request
            polarization: HORIZONTAL (TH) or VERTICAL (TV) to read the files of one polarization of the unfiltered
                reflectivity sweeps, which are answered for both without it: see RADAR_PARAMETERS_POLARIZED

        """
        # A product DWD no longer publishes is refused with the reason, which the list of valid values does not give.
        if isinstance(parameter, str):
            reason = RADAR_PARAMETERS_NOT_PUBLISHED.get(parameter.lower().removesuffix("_reflectivity"))
            if reason:
                msg = f"{parameter} is not published any more: {reason}"
                raise InvalidEnumerationError(msg)

        # A format DWD no longer publishes is refused with the reason, as a product is.
        if isinstance(fmt, str):
            reason = RADAR_DATA_FORMATS_NOT_PUBLISHED.get(fmt.lower())
            if reason:
                msg = f"{fmt} is not offered any more: {reason}"
                raise InvalidEnumerationError(msg)

        # Convert parameters to enum types.
        self.parameter = parse_enumeration_from_template(parameter, DwdRadarParameter)
        self.site = parse_enumeration_from_template(site, DwdRadarSite)
        # a product is served in one format, which a request need not name; one it is not served in is refused
        self.format = radar_data_format(self.parameter, parse_enumeration_from_template(fmt, DwdRadarDataFormat))
        # a sweep with one folder need not be asked for it; one with two is, and a folder it has not is refused
        self.subset = radar_data_subset(self.parameter, parse_enumeration_from_template(subset, DwdRadarDataSubset))
        # the unfiltered reflectivity has a file for each polarization, all of which are read where none is asked for
        self.polarization = radar_polarization(
            self.parameter, self.subset, parse_enumeration_from_template(polarization, DwdRadarPolarization)
        )
        self.elevation = elevation and int(elevation)
        self.resolution: Resolution | None = parse_enumeration_from_template(resolution, DwdRadarResolution, Resolution)
        self.period: Period | None = parse_enumeration_from_template(period, DwdRadarPeriod, Period)

        # Sanity checks.
        if self.parameter == DwdRadarParameter.RADOLAN_CDC and self.resolution not in (
            Resolution.HOURLY,
            Resolution.DAILY,
        ):
            msg = "RADOLAN_CDC only supports daily and hourly resolutions"
            raise ValueError(msg)

        if self.elevation is not None and self.parameter not in RADAR_PARAMETERS_SWEEPS_VOLUME:
            msg = f"Argument 'elevation' only valid for parameter={RADAR_PARAMETERS_SWEEPS_VOLUME}"
            raise ValueError(msg)

        if start == DwdRadarDate.LATEST:
            if self.parameter == DwdRadarParameter.RADOLAN_CDC:
                msg = "RADOLAN_CDC data has no '-latest-' files"
                raise ValueError(msg)

            # The folders of a filter have no latest file, the composites and the other site products do. The unfiltered
            # folders have one for each sweep: the precipitation scan one (two for the reflectivity, TH and TV), the
            # volume scan ten, which DWD replaces one by one as the scan is published, so that for minutes they are of
            # two volumes (read 2026-10-22 15:53 UTC: the sweeps 0 to 4 listed 15:51 to 15:53 and 5 to 9 at 15:48 to
            # 15:49; the scan time inside the files of 0, 3 and 4 is 15:50, inside that of 9 15:45).
            if self.parameter in RADAR_PARAMETERS_SWEEPS and self.subset != DwdRadarDataSubset.UNFILTERED:
                msg = "HDF5 sweep data has no '-latest-' files"
                if (
                    DwdRadarDataSubset.UNFILTERED in RADAR_DATA_SUBSETS.get(self.parameter, ())
                    and self.parameter not in RADAR_PARAMETERS_SWEEPS_VOLUME
                ):
                    msg += " (the unfiltered folder has them: subset=UNFILTERED)"
                raise ValueError(msg)
            if self.parameter in RADAR_PARAMETERS_SWEEPS_VOLUME:
                msg = (
                    "HDF5 sweep data has no '-latest-' files of a whole volume (the unfiltered folders have one for "
                    "each elevation, replaced one by one, so they can be of two volumes): ask for a time instead"
                )
                raise ValueError(msg)

            # nor has KONRAD3D, as the mesocyclones have
            if self.parameter == DwdRadarParameter.KONRAD3D_CONVECTIVE_CELLS:
                msg = "KONRAD3D data has no 'latest' file"
                raise ValueError(msg)

        if start == DwdRadarDate.CURRENT and not self.period:
            self.period = Period.RECENT

        # Evaluate "RadarDate.MOST_RECENT" for "start".
        #
        # The most recent HDF5 and XML file is a time, not the "-latest-" file: the sweeps of the filtered folders and
        # KONRAD3D have none, and those of the unfiltered folders are replaced one by one as the scan is published.
        # So we will have to synthesize the latest appropriately by going back to the second last volume of 5 minute
        # intervals. The other products have a latest file but are asked for in the same way.
        #
        # The reason for this is that when requesting sweep data in HDF5 format at
        # e.g. 15:03, not all files will be available on the DWD data repository for
        # the whole volume (e.g. covering all elevation levels) within the time range
        # of 15:00-15:04:59 as they apparently will be added incrementally while the
        # scan is performed.
        #
        # So, we will be better off making the machinery retrieve the latest "full"
        # volume by addressing the **previous** volume. So, when requesting data at
        # 15:03, it will retrieve 14:55:00-14:59:59. The volume sweeps are listed up to 485 s late, so they, as the
        # other products of RADAR_PARAMETERS_SLOW, go back one more slot: 14:50:00-14:54:59 (GH-3302).
        #
        if self.format in (DwdRadarDataFormat.HDF5, DwdRadarDataFormat.XML) and start == DwdRadarDate.MOST_RECENT:
            # the products that DWD publishes late are gone back another 5 minutes, to a file that is there
            lag = 10 if self.parameter in RADAR_PARAMETERS_SLOW else 5
            start = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(minutes=lag)
            end = None

        if start == DwdRadarDate.MOST_RECENT and parameter == DwdRadarParameter.RADOLAN_CDC:
            start = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) - dt.timedelta(minutes=50)
            end = None

        # Evaluate "RadarDate.CURRENT" for "start".
        if start == DwdRadarDate.CURRENT:
            start = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None)
            if parameter == DwdRadarParameter.RADOLAN_CDC and start.minute < 20:
                start = start - dt.timedelta(hours=1)
            end = None

        # Evaluate "RadarDate.LATEST" for "start".
        if start == DwdRadarDate.LATEST:
            self.start = start
            self.end = None

        # Evaluate any datetime for "start".
        else:
            if isinstance(start, str):
                start = dt.datetime.fromisoformat(start)
            if end and isinstance(end, str):
                end = dt.datetime.fromisoformat(end)
            # a naive bound is UTC and an aware one is the instant it names, in UTC: the files are
            # selected and aligned on the UTC clock they are published on, so a bound left in its
            # own zone selected another file than the same instant written in UTC
            if isinstance(start, dt.datetime):
                start = _as_utc(start)
            if end and isinstance(end, dt.datetime):
                end = _as_utc(end)
            self.start = start
            self.end = end
            self.adjust_datetimes()

        self.settings = settings or Settings()
        self._warned_missing_h5py = False

    def __str__(self) -> str:
        """Return a string representation of the object."""
        return (
            f"DWDRadarRequest("
            f"parameter={self.parameter}, "
            f"site={self.site}, "
            f"format={self.format}, "
            f"resolution={self.resolution},"
            f"date={self.start}/{self.end})"
        )

    def __eq__(self, other: object) -> bool:
        """Compare two DwdRadarValues objects."""
        if not isinstance(other, DwdRadarValues):
            return False
        return (
            self.parameter == other.parameter
            and self.site == other.site
            and self.format == other.format
            and self.subset == other.subset
            and self.polarization == other.polarization
            and self.start == other.start
            and self.end == other.end
            and self.resolution == other.resolution
            and self.period == other.period
        )

    def adjust_datetimes(self) -> None:
        """Adjust ``start`` and ``end`` attributes to match minute marks for RadarParameter.

        - RADOLAN_CDC is always published at HH:50.
          https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/recent/bin/

        - RW_REFLECTIVITY is published each 10 minutes.
          https://opendata.dwd.de/weather/radar/radolan/rw/

        - All other radar formats are published in intervals of 5 minutes.
          https://opendata.dwd.de/weather/radar/composite/rv/
          https://opendata.dwd.de/weather/radar/sites/dx/boo/

        """
        if not isinstance(self.start, dt.datetime):
            return
        if self.parameter in (DwdRadarParameter.RADOLAN_CDC, DwdRadarParameter.SF_REFLECTIVITY):
            # Align "start" to the most recent 50 minute mark available.
            self.start = raster_minutes(self.start, 50)

            # When "end" is given as timedelta, resolve it.
            if isinstance(self.end, dt.timedelta):
                self.end = self.start + self.end

            # Use "end = start" to make the machinery
            # pick a single file from the fileindex.
            if not self.end:
                self.end = self.start + dt.timedelta(microseconds=1)

        elif self.parameter == DwdRadarParameter.RW_REFLECTIVITY:
            # Align "start" to the 5 minute mark before tm.
            self.start = round_minutes(self.start, 10)

            # When "end" is given as timedelta, resolve it.
            if isinstance(self.end, dt.timedelta):
                self.end = self.start + self.end - dt.timedelta(seconds=1)

            # Expand "end" to the end of the 10 minute mark.
            if self.end is None:
                self.end = self.start + dt.timedelta(minutes=10) - dt.timedelta(seconds=1)
        else:
            # Align "start" to the 5 minute mark before tm.
            self.start = round_minutes(self.start, 5)

            # When "end" is given as timedelta, resolve it.
            if isinstance(self.end, dt.timedelta):
                self.end = self.start + self.end - dt.timedelta(seconds=1)

            # Expand "end" to the end of the 5 minute mark.
            if self.end is None:
                self.end = self.start + dt.timedelta(minutes=5) - dt.timedelta(seconds=1)

    def query(self) -> Iterator[RadarResult]:  # noqa: C901
        """Query radar data from the DWD server."""
        log.info(f"acquiring radar data for {self!s}")
        # Find latest file.
        if self.start == DwdRadarDate.LATEST:
            file_index = create_fileindex_radar(
                parameter=self.parameter,
                site=self.site,
                fmt=self.format,
                subset=self.subset,
                parse_datetime=False,
                settings=self.settings,
            )

            # Find "-latest-" or "LATEST" or similar file.
            file_index = self._of_polarization(
                file_index.filter(pl.col("filename").str.to_lowercase().str.contains("latest"))
            )

            # a listing with no such file is no error but no result, as a time with no file is
            if file_index.is_empty():
                log.warning(f"No radar file found for {self.parameter}, {self.site}, {self.format}")
                return

            if self.parameter in RADAR_PARAMETERS_SWEEPS:
                # the one sweep of the precipitation scan, the two files TH and TV of the reflectivity
                for url in file_index.sort("filename").get_column("filename"):
                    for result in self._download_generic_data(url=url):
                        yield self._dated_by_content(result)
                return

            # Yield a single "RadarResult" item for the file: the first of a .tar, which is the analysis of the run.
            for url in file_index.sort("filename").get_column("filename"):
                result = next(self._download_generic_data(url=url), None)
                if result is None:
                    # a .tar with no member: a download that failed has been raised by now
                    log.warning(f"No radar data found in {url}")
                    continue
                yield self._dated_by_content(result)

        elif self.parameter == DwdRadarParameter.RADOLAN_CDC:
            period_types = [self.period] if self.period else [Period.RECENT, Period.HISTORICAL]

            results = []
            for period in period_types:
                file_index = create_fileindex_radolan_cdc(
                    # __init__ refused RADOLAN_CDC for any resolution but hourly and daily
                    resolution=cast("Resolution", self.resolution),
                    period=period,
                    settings=self.settings,
                )

                # Filter for dates range if start and end are defined.
                if period == Period.RECENT:
                    file_index = file_index.filter(
                        # typed as all __init__ accepts; a window is datetimes (an open one is None, as before)
                        pl.col("datetime").is_between(
                            cast("dt.datetime", self.start), cast("dt.datetime", self.end), closed="both"
                        ),
                    )

                # This is for matching historical data, e.g. "RW-200509.tar.gz", one file a month,
                # dated to the first: every month the window touches, not only the one it opens in.
                else:
                    start_date_dt = cast("dt.datetime", self.start)
                    first_month = start_date_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    file_index = file_index.filter(
                        pl.col("datetime").is_between(first_month, cast("dt.datetime", self.end), closed="both"),
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
                yield from self._download_radolan_data(
                    url,
                    cast("dt.datetime", self.start),
                    cast("dt.datetime", self.end),
                )

        else:
            file_index = create_fileindex_radar(
                parameter=self.parameter,
                site=self.site,
                fmt=self.format,
                subset=self.subset,
                parse_datetime=True,
                settings=self.settings,
            )

            # Filter for dates range if start and end are defined.
            file_index = file_index.filter(
                # typed as all __init__ accepts; a window is datetimes (an open one is None, as before)
                pl.col("datetime").is_between(
                    cast("dt.datetime", self.start), cast("dt.datetime", self.end), closed="both"
                ),
            )

            file_index = self._of_polarization(file_index)

            # Filter the sweeps of the volume scan by elevation: the number of the sweep follows the moment in the
            # name, `..._vradh_00-`, `..._dbzh_00-`, `..._th_00-`, `..._tv_00-`, `..._uzdr_00-`, `..._urhohv_00-`,
            # `..._uphidp_00-`.
            if self.elevation is not None:
                file_index = file_index.filter(
                    pl.col("filename").str.contains(f"vradh_{self.elevation:02d}")
                    | pl.col("filename").str.contains(f"sweep_vol_v_{self.elevation}")
                    | pl.col("filename").str.contains(f"dbzh_{self.elevation:02d}")
                    | pl.col("filename").str.contains(f"sweep_vol_z_{self.elevation}")
                    | pl.col("filename").str.contains(f"_th_{self.elevation:02d}")
                    | pl.col("filename").str.contains(f"_tv_{self.elevation:02d}")
                    | pl.col("filename").str.contains(f"uzdr_{self.elevation:02d}")
                    | pl.col("filename").str.contains(f"urhohv_{self.elevation:02d}")
                    | pl.col("filename").str.contains(f"uphidp_{self.elevation:02d}"),
                )

            if file_index.is_empty():
                log.warning(f"No radar file found for {self.parameter}, {self.site}, {self.format}")
                return

            # Iterate list of files and yield "RadarResult" items.
            verify_hdf5_files = self.format == DwdRadarDataFormat.HDF5
            for row in file_index.iter_rows(named=True):
                date_time = row["datetime"]
                url = row["filename"]

                for result in self._download_generic_data(url=url):
                    if not result.timestamp:
                        result.timestamp = date_time

                    if verify_hdf5_files:
                        try:
                            verify_hdf5(result.data)
                        except MissingDependencyError as exc:
                            # no h5py: every file would say the same, so say it once and go on without
                            verify_hdf5_files = False
                            log.warning(f"{str(exc).rstrip('.')}. The HDF5 files are returned unverified.")
                        except Exception:  # pragma: no cover
                            log.exception("Unable to read HDF5 file.")
                    yield result

    def _of_polarization(self, file_index: pl.DataFrame) -> pl.DataFrame:
        """Keep the files of the polarization asked for, `..._th_00-...` or `..._tv_00-...`, or all where none is."""
        if self.polarization is None:
            return file_index
        return file_index.filter(pl.col("filename").str.contains(f"_{self.polarization.value}_\\d{{2}}-"))

    def _dated_by_content(self, result: RadarResult) -> RadarResult:
        """Date a latest file by what it says, which its name does not (GH-3299).

        The `-latest-` and `LATEST` files of the sites, the sweeps of the precipitation scan, the composites and RADOLAN
        have no time in the name; the time of the scan is in the file, in the `/what` group of an ODIM HDF5 file, which
        h5py reads, in the header of a DX file, or in the first event of `meso_latest.xml`. A file that says none (that
        of a run with no event) stays undated, as one does without h5py, which is said once.
        """
        if result.timestamp is not None:
            return result
        try:
            result.timestamp = read_scan_time(result.data)
        except MissingDependencyError as exc:
            if not self._warned_missing_h5py:
                self._warned_missing_h5py = True
                log.warning(f"{str(exc).rstrip('.')}. The latest HDF5 files are returned without a timestamp.")
        return result

    @staticmethod
    def _should_cache_download(url: str) -> bool:
        """Determine whether this specific result should be cached.

        Here, we don't want to cache any files named "latest", whatever the case: "-latest-" of the sites,
        "_latest-" and "_LATEST." of the composites.

        Args:
            url: URL of the file to be downloaded

        Returns:
            Whether the file should be cached or not

        """
        return "latest" not in url.lower()

    def _download_generic_data(self, url: str) -> Iterator[RadarResult]:  # noqa: C901
        """Download radar data."""
        ttl = CacheExpiry.FIVE_MINUTES
        if not self._should_cache_download(url):
            ttl = CacheExpiry.NO_CACHE
        file = download_file(
            url=url,
            cache_dir=self.settings.cache_dir,
            ttl=ttl,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
            use_certifi=self.settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return
        # RV_REFLECTIVITY, WN_REFLECTIVITY: a tar of one ODIM HDF5 file for every lead time
        if url.endswith(f".{Extension.TAR.value}"):
            tfs = TarFileSystem(file.content)
            for file in tfs.glob("*"):
                try:
                    file_name = file.name
                except AttributeError:
                    file_name = file
                date_string = get_date_string_from_filename(file_name, pattern=RADAR_DT_PATTERN)
                timestamp = None
                if date_string:
                    timestamp = _parse_datetime_from_formats(string=date_string, formats=DATETIME_FORMATS)
                    timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
                yield RadarResult(
                    url=url,
                    data=BytesIO(tfs.open(file).read()),
                    timestamp=timestamp,
                    filename=file_name,
                )

        elif url.endswith(Extension.BZ2.value):
            with bz2.BZ2File(file.content, mode="rb") as archive:
                data = BytesIO(archive.read())
                date_string = get_date_string_from_filename(url, pattern=RADAR_DT_PATTERN)
                timestamp = None
                if date_string:
                    timestamp = _parse_datetime_from_formats(string=date_string, formats=DATETIME_FORMATS)
                    timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
                yield RadarResult(
                    url=url,
                    data=data,
                    timestamp=timestamp,
                )

        # a gzipped file: the RADVOR products of the earlier layout, which no product is served as now
        elif url.endswith(Extension.GZ.value):
            with gzip.GzipFile(fileobj=file.content, mode="rb") as archive:
                data = BytesIO(archive.read())
                date_string = get_date_string_from_filename(url, pattern=RADAR_DT_PATTERN)
                timestamp = None
                if date_string:
                    timestamp = _parse_datetime_from_formats(string=date_string, formats=DATETIME_FORMATS)
                    timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
                yield RadarResult(
                    url=url,
                    data=data,
                    timestamp=timestamp,
                )

        else:
            date_string = get_date_string_from_filename(url, pattern=RADAR_DT_PATTERN)
            timestamp = None
            if date_string:
                timestamp = _parse_datetime_from_formats(string=date_string, formats=DATETIME_FORMATS)
                timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
            yield RadarResult(
                url=url,
                data=file.content,
                timestamp=timestamp,
            )

    def _download_radolan_data(self, url: str, start_date: dt.datetime, end_date: dt.datetime) -> Iterator[RadarResult]:
        """Download RADOLAN_CDC data for a given datetime."""
        file = download_file(
            url=url,
            cache_dir=self.settings.cache_dir,
            ttl=CacheExpiry.TWELVE_HOURS,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
            use_certifi=self.settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return
        for result in self._extract_radolan_data(file.content):
            if not result.timestamp:
                # if result has no timestamp, take it from main url instead of files in archive
                datetime_string = re.findall(r"\d{10}", url)[0]
                date_time = dt.datetime.strptime("20" + datetime_string, "%Y%m%d%H%M").replace(tzinfo=ZoneInfo("UTC"))
                result.timestamp = date_time
            if result.timestamp < start_date or result.timestamp > end_date:
                continue
            result.url = url

            yield result

    @staticmethod
    def _extract_radolan_data(archive_in_bytes: BytesIO) -> Iterator[RadarResult]:
        """Extract the RADOLAN_CDC data from the archive."""
        # First try to unpack archive from archive (case for historical data)
        try:
            tfs = TarFileSystem(archive_in_bytes, compression="gzip")

            for file in tfs.glob("*"):
                datetime_string = re.findall(r"\d{10}", file)[0]
                date_time = dt.datetime.strptime("20" + datetime_string, "%Y%m%d%H%M").replace(tzinfo=ZoneInfo("UTC"))
                file_handle = tfs.tar.extractfile(file)
                if file_handle is None:
                    continue
                file_in_bytes = file_handle.read()

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
                yield RadarResult(data=BytesIO(gz_file.read()), timestamp=None, filename=gz_file.name or "")


# help() and IPython read the arguments off __init__ rather than the variadic refusal, as on TimeseriesRequest
# (`__wrapped__` is no attribute a function is declared to have, which is how `inspect` looks it up)
DwdRadarValues.__new__.__wrapped__ = DwdRadarValues.__init__  # ty: ignore[unresolved-attribute]


class DwdRadarSites(OperaRadarSites):
    """API for DWD radar sites."""

    def __init__(self) -> None:
        """Load all DWD radar sites."""
        super().__init__()

        # Restrict available sites to the list of OPERA radar sites in Germany.
        self.sites = self.by_country_name(country_name="Germany")
