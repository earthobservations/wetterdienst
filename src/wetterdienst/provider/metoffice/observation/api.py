# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Met Office (UK) observation provider -- MIDAS Open on CEDA.

Data is the Met Office MIDAS Open archive (UK Open Government Licence) on CEDA. See ``metadata.py``
for the archive/licensing background and ``download.py``/``fileindex.py`` for the auth and
file-layout details.

Provider-specific handling, each established by live testing against the real archive:

- **Multiple report types per period.** A daily station may transmit an overnight and a daytime
  12-hour reading (``NCM``/``AWSDLY``) *and* a 24-hour one (``DLY3208``/``SYNOP``) for the same day.
  ``parser.parse_values`` collapses these to one value per calendar day (``max`` for max-type
  parameters, ``min`` for ``_MIN_COLUMNS``), which is idempotent over the 12h/24h duplication.
  Hourly datasets have one reading per hour, so the aggregation is a no-op there.
- **Multi-day accumulations.** Daily rain gauges read every N days post an N-day accumulated total
  on the read date with ``ob_day_cnt=N``; only ``ob_day_cnt==1`` rows are kept (see
  ``_DATASET_CONFIG``).
- **Units.** Verified against real values / the Met Office GL-table docs -- wind in knots,
  temperatures °C, pressure hPa, precipitation mm, radiation kJ/m². ``visibility`` is native
  decametres and is scaled to metres via ``_SCALE``.
- **Quality.** The ``*_q`` column is MIDAS's raw ``MESQL`` five-digit compound QC flag (each digit a
  separate aspect; see https://dap.ceda.ac.uk/badc/ukmo-midas/metadata/doc/QC_J_flags.html), *not* a
  linear quality level. It is passed through unchanged into ``quality`` -- do not treat a larger
  value as "worse".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import cast

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.metoffice.observation.download import get_ceda_token
from wetterdienst.provider.metoffice.observation.fileindex import download_url, latest_release_version
from wetterdienst.provider.metoffice.observation.metadata import MetOfficeObservationMetadata
from wetterdienst.provider.metoffice.observation.parser import parse_station_metadata, parse_values
from wetterdienst.settings import Settings
from wetterdienst.util.network import download_file

log = logging.getLogger(__name__)

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality": pl.Float64,
}

# per MIDAS dataset slug: the timestamp column and the ``ob_day_cnt``-style multi-period-accumulation
# column (only daily rain has one -- see parser.parse_values). ``granularity`` is derived from the
# resolution in _collect_year. The timestamp columns were read off the real file headers during
# scoping; the uk-daily-rain-obs ob_day_cnt=1 filter is confirmed live.
_DATASET_CONFIG: dict[str, dict] = {
    "uk-daily-rain-obs": {"time_column": "ob_date", "period_count_column": "ob_day_cnt"},
    "uk-daily-temperature-obs": {"time_column": "ob_end_time", "period_count_column": None},
    "uk-daily-weather-obs": {"time_column": "ob_end_time", "period_count_column": None},
    "uk-hourly-rain-obs": {"time_column": "ob_end_time", "period_count_column": None},
    "uk-hourly-weather-obs": {"time_column": "ob_time", "period_count_column": None},
    "uk-mean-wind-obs": {"time_column": "ob_end_time", "period_count_column": None},
    "uk-radiation-obs": {"time_column": "ob_end_time", "period_count_column": None},
    "uk-soil-temperature-obs": {"time_column": "ob_time", "period_count_column": None},
}

# raw MIDAS columns aggregated with ``min`` rather than ``max`` when collapsing a day's multiple
# report types (see parser.parse_values). Only the daily-temperature min-type readings qualify.
_MIN_COLUMNS = frozenset({"min_air_temp", "min_grss_temp"})

# raw MIDAS columns whose native unit differs from the one declared in metadata.py, with the factor
# that reconciles them. Confirmed live: visibility is stored in decametres, scaled to metres.
_SCALE = {"visibility": 10.0}


def _station_path_url(
    midas_dataset: str,
    version: str,
    county: str,
    station_id: str,
    slug: str,
    qc_version: int,
    year: int,
) -> str:
    stem = f"midas-open_{midas_dataset}_dv-{version}_{county}_{station_id}_{slug}_qcv-{qc_version}_{year}"
    return download_url(
        f"data/{midas_dataset}/dataset-version-{version}/{county}/{station_id}_{slug}/"
        f"qc-version-{qc_version}/{stem}.csv",
    )


def _station_metadata_url(midas_dataset: str, version: str) -> str:
    return download_url(
        f"data/{midas_dataset}/dataset-version-{version}/midas-open_{midas_dataset}_dv-{version}_station-metadata.csv",
    )


class MetOfficeObservationValues(TimeseriesValues):
    """Values class for Met Office (MIDAS Open) observation data."""

    def _token(self, settings: Settings) -> str | None:
        # get_ceda_token caches the minted token in-process until shortly before its own expiry, so
        # calling this once per station (as the values collection does) reuses one token rather than
        # re-minting per station (see download.py).
        return get_ceda_token(settings)

    def _download(self, url: str, settings: Settings, token: str | None) -> bytes | None:
        headers = {**settings.fsspec_client_kwargs.get("headers", {})}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.TWELVE_HOURS,
            client_kwargs={**settings.fsspec_client_kwargs, "headers": headers},
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        if isinstance(file.content, Exception):
            if not file.is_no_internet_error:
                log.debug(f"No MetOffice file {url}: {file.content}")
            return None
        return file.content.read()

    def _station_slug_and_county(
        self,
        station_id: str,
        midas_dataset: str,
        version: str,
        settings: Settings,
        token: str | None,
    ) -> tuple[str, str] | None:
        """Resolve a station's (historic_county, station_file_name) for URL building.

        Re-downloads (cache-hit after the first call) the same ``station-metadata.csv`` used in
        ``_all()`` -- ``_base_columns`` only keeps the framework's fixed station columns, so
        provider-specific fields like the MIDAS path components don't survive into ``self.sr.df``.
        """
        content = self._download(_station_metadata_url(midas_dataset, version), settings, token)
        if content is None:
            return None
        stations = parse_station_metadata(content)
        row = stations.filter(pl.col("station_id") == station_id)
        if row.is_empty():
            return None
        return row.item(0, "historic_county"), row.item(0, "station_file_name")

    def _collect_year(
        self,
        midas_dataset: str,
        version: str,
        county: str,
        station_id: str,
        slug: str,
        year: int,
        config: dict,
        columns: list[str],
        granularity: str,
        settings: Settings,
        token: str | None,
    ) -> pl.DataFrame | None:
        content = None
        for qc_version in (1, 0):  # prefer the QC'd version, fall back to the raw one
            url = _station_path_url(midas_dataset, version, county, station_id, slug, qc_version, year)
            content = self._download(url, settings, token)
            if content is not None:
                break
        if content is None:
            return None
        df = parse_values(
            content,
            time_column=config["time_column"],
            columns=columns,
            granularity=granularity,
            min_columns=_MIN_COLUMNS,
            scale=_SCALE,
            period_count_column=config["period_count_column"],
        )
        return df if not df.is_empty() else None

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        if not isinstance(parameter_or_dataset, DatasetModel):
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        dataset = parameter_or_dataset
        midas_dataset = dataset.name_original
        config = _DATASET_CONFIG[midas_dataset]

        settings = cast("Settings", self.sr.stations.settings)
        token = self._token(settings)
        version = latest_release_version(settings, token)
        if version is None:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        located = self._station_slug_and_county(station_id, midas_dataset, version, settings, token)
        if located is None:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        county, slug = located

        station_row = self.sr.df.filter(pl.col("station_id") == station_id)
        start = self.sr.start_date or station_row.item(0, "start_date")
        end = self.sr.end_date or station_row.item(0, "end_date")
        if start is None or end is None:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        columns = [p.name_original for p in dataset.parameters]
        granularity = "1d" if dataset.resolution.name == "daily" else "1h"
        frames = [
            df
            for year in range(start.year, end.year + 1)
            if (
                df := self._collect_year(
                    midas_dataset,
                    version,
                    county,
                    station_id,
                    slug,
                    year,
                    config,
                    columns,
                    granularity,
                    settings,
                    token,
                )
            )
            is not None
        ]
        if not frames:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        df = pl.concat(frames)
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("date"),
            pl.col("value"),
            pl.col("quality"),
        )


@dataclass
class MetOfficeObservationRequest(TimeseriesRequest):
    """Request class for Met Office (MIDAS Open) observation data."""

    metadata = MetOfficeObservationMetadata
    _values = MetOfficeObservationValues

    @classmethod
    def is_configured(cls) -> bool:
        """Whether CEDA credentials are available (needed for any MIDAS Open request)."""
        return bool(Settings().auth.ceda)

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        token = get_ceda_token(settings)

        # DatasetModel isn't hashable, so dedupe on (resolution, name) like CHMI does
        datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name): parameter.dataset
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        }.values()
        frames = []
        for dataset in datasets:
            midas_dataset = dataset.name_original
            version = latest_release_version(settings, token)
            if version is None:
                continue
            content = None
            headers = {**settings.fsspec_client_kwargs.get("headers", {})}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            file = download_file(
                url=_station_metadata_url(midas_dataset, version),
                cache_dir=settings.cache_dir,
                ttl=CacheExpiry.METAINDEX,
                client_kwargs={**settings.fsspec_client_kwargs, "headers": headers},
                cache_disable=settings.cache_disable,
                use_certifi=settings.use_certifi,
            )
            if isinstance(file.content, Exception):
                log.warning(f"Failed to fetch MetOffice station catalogue for {midas_dataset}: {file.content}")
                continue
            content = file.content.read()
            stations = parse_station_metadata(content)
            if stations.is_empty():
                continue
            frames.append(
                stations.with_columns(
                    pl.lit(dataset.resolution.name, pl.String).alias("resolution"),
                    pl.lit(dataset.name, pl.String).alias("dataset"),
                ),
            )
        if not frames:
            return pl.LazyFrame()
        # TimeseriesRequest.all() selects _base_columns and fills any the catalogue omits (state)
        # with null; historic_county/station_file_name are dropped there and re-resolved from the
        # same station-metadata.csv (cached) in MetOfficeObservationValues when needed.
        return pl.concat(frames).lazy()
