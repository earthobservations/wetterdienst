# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Météo-France SYNOP data provider."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.quality_flags import (
    SPEED_BESIDE,
    Sentinel,
    calm,
    join_quality_flags,
    no_direction_code,
    null_sentinels,
    with_speed_beside,
)
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import UPDATED, TimeseriesValues
from wetterdienst.provider.meteofrance.synop.metadata import MeteoFranceSynopMetadata
from wetterdienst.util.archive import gunzip
from wetterdienst.util.network import cached_copy_is_held, download_file
from wetterdienst.util.response_warnings import note_skipped_download

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel, ParameterModel
    from wetterdienst.settings import Settings
    from wetterdienst.util.network import File

log = logging.getLogger(__name__)

# "Archive Synop OMM" dataset on data.gouv.fr: one gzipped csv per year, covering all ~190
# SYNOP stations at their native 3-hourly reporting interval. The yearly files are the resources data.gouv.fr lists
# under `data/OBS/SYNOP/`. The `data/synchro_ftp/OBS/SYNOP/` copy of the same names is a mirror that stopped being
# refreshed: on 2026-10-26 its synop_2026.csv.gz (23.3 MB) ended at 2026-09-08T21:00Z and was last modified on
# 2026-09-09, the maintained file (27.7 MB, same 65 columns, every row of the mirror in it unchanged) ended at
# 2026-10-25T21:00Z. The finished years are the same bytes in both (2025 checked), so only the current year differs.
# The station list is not in `data/OBS/SYNOP/` (404): data.gouv.fr lists it under `synchro_ftp`
_SYNOP_ENDPOINT = "https://meteofrance.s3.sbg.io.cloud.ovh.net/data/OBS/SYNOP/synop_{year}.csv.gz"
_SYNOP_STATIONS_ENDPOINT = "https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/OBS/SYNOP/postes_synop.geojson"
# earliest year for which a yearly archive is published
_SYNOP_ARCHIVE_START_YEAR = 1996

# codes the source writes in place of a number (GH-2674); the file defines neither, they are read off the data:
# `-0.1` in the precipitation columns is a trace (WMO element 013011 has a reference value of -1 at scale 1), some rain
# below what the gauge reports, so it is 0.0 rather than a negative amount; `101` in `n` is outside the classes 0 to
# 100 and comes with a visibility of metres and a cloud base class 9, the sky was obscured, so there is no amount.
# The reading keeps the code as the `raw` token of its `quality_flags` (GH-2759); the 2024 file (7 MB, checked
# 2026-10-12) writes `-0.1` 12733 times in rr6 and 8862 times in rr1, and `101` 2388 times in n
_SYNOP_TRACE_COLUMNS = ("rr1", "rr3", "rr6", "rr12", "rr24")
_SYNOP_TRACE = "-0.1"
_SYNOP_SKY_OBSCURED = "101"

# `dd` is a direction in degrees with north written 360 (3230 rows in 2024), and the file writes 0 where there is no
# direction: the WMO code table of the wind direction (0877) has 0 for calm and 360 for north (GH-2856). Every one of
# the 3495 zeros of 2024 has `ff` = 0 (5444 of 5444 in 2019, 3999 of 3999 in 2023); in 1996, 2005 and 2012 32, 1 and 59
# of 8350, 7750 and 7525 have an `ff` of 1 to 8 m/s (one of 41). The 0 beside an `ff` of 0 is a calm, and null; the 0
# beside a wind that blows stays, as in every provider (`calm`, GH-3222), where it was null too. `ff` = 0 is no calm by
# itself: the integer `ff` cuts 0.5 to 0.9 m/s to 0, and 10925 of those rows of 2024 have a direction, which stays.
# The 1996 file also holds `dd` = 400 in 14 rows (13 of DUMONT D'URVILLE from 1996-04-03 to 1996-06-21, 1 of
# EUROPA), each beside an `ff` of 1 or 2 m/s; no other year of 1996 to 2026 has a `dd` above 360 (checked
# 2026-10-14). The file does not define it and it is no bearing, so it is read off the data, as `-0.1` and `101`
# are above (GH-2873)
_SYNOP_NO_WIND_DIRECTION = ("400",)
_SYNOP_WIND_DIRECTION_COLUMN = "dd"
_SYNOP_WIND_SPEED_OF_DIRECTION = {_SYNOP_WIND_DIRECTION_COLUMN: "ff"}

# explicit schema of the exact columns published by the source, read as strings throughout since
# many columns are entirely empty for a given station or year, which would otherwise lead to
# inconsistent dtype inference (e.g. an all-null column inferred as Boolean in one year and
# Float64 in another) and break the concat below. Column order matches the source CSV, as
# required by polars' `schema` argument.
_SYNOP_CSV_SCHEMA = {
    "lat": pl.String,
    "lon": pl.String,
    "geo_id_wmo": pl.String,
    "geo_id_wigos": pl.String,
    "name": pl.String,
    "reference_time": pl.String,
    "insert_time": pl.String,
    "validity_time": pl.String,
    "pmer": pl.String,
    "tend": pl.String,
    "cod_tend": pl.String,
    "dd": pl.String,
    "ff": pl.String,
    "t": pl.String,
    "td": pl.String,
    "u": pl.String,
    "vv": pl.String,
    "ww": pl.String,
    "w1": pl.String,
    "w2": pl.String,
    "n": pl.String,
    "nbas": pl.String,
    "hbas": pl.String,
    "cl": pl.String,
    "cm": pl.String,
    "ch": pl.String,
    "pres": pl.String,
    "niv_bar": pl.String,
    "geop": pl.String,
    "tend24": pl.String,
    "tn12": pl.String,
    "tn24": pl.String,
    "tx12": pl.String,
    "tx24": pl.String,
    "tminsol": pl.String,
    "sw": pl.String,
    "tw": pl.String,
    "raf10": pl.String,
    "rafper": pl.String,
    "per": pl.String,
    "etat_sol": pl.String,
    "ht_neige": pl.String,
    "ssfrai": pl.String,
    "perssfrai": pl.String,
    "rr1": pl.String,
    "rr3": pl.String,
    "rr6": pl.String,
    "rr12": pl.String,
    "rr24": pl.String,
    "phenspe1": pl.String,
    "phenspe2": pl.String,
    "phenspe3": pl.String,
    "phenspe4": pl.String,
    "nnuage1": pl.String,
    "ctype1": pl.String,
    "hnuage1": pl.String,
    "nnuage2": pl.String,
    "ctype2": pl.String,
    "hnuage2": pl.String,
    "nnuage3": pl.String,
    "ctype3": pl.String,
    "hnuage3": pl.String,
    "nnuage4": pl.String,
    "ctype4": pl.String,
    "hnuage4": pl.String,
}


def _download_year(year: int, current_year: int, settings: Settings) -> File:
    """Download the file of a year; a finished year cached before dates were kept is fetched once more (GH-2567).

    The finished years are cached for good and are rewritten rarely, so a copy made by a version that did not keep the
    `Last-Modified` of a download would never have a date: it is fetched once more, which dates it (a few to some
    twenty megabytes a year, once), in one attempt. Where that fails, whatever the status, the copy that is held is read
    as it was, with no date and with a warning that says so, and not an error: nobody who has the years cached is to
    lose them for a date. Where no copy is held there is nothing to fetch once more, and the year is downloaded as any.
    """
    url = _SYNOP_ENDPOINT.format(year=year)
    ttl = CacheExpiry.FIVE_MINUTES if year == current_year else CacheExpiry.INFINITE

    def fetch(*, once_more: bool = False) -> File:
        return download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=ttl,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
            attempts=1 if once_more else 2,
            refetch_undated=once_more,
        )

    held = cached_copy_is_held(
        url,
        settings.cache_dir,
        ttl,
        settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    if year == current_year or not held:
        return fetch()
    file = fetch(once_more=True)
    if not isinstance(file.content, Exception):
        return file
    copy = fetch()
    if not isinstance(copy.content, Exception):
        log.warning(
            f"{url} could not be downloaded again to date it ({file.content!r}): the copy held is read, with no date"
        )
    return copy


class MeteoFranceSynopValues(TimeseriesValues):
    """Values class for Météo-France SYNOP data."""

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        dataset = cast("DatasetModel", parameter_or_dataset)
        current_year = datetime.now(tz=ZoneInfo("UTC")).year
        start_date = self.sr.start or datetime(_SYNOP_ARCHIVE_START_YEAR, 1, 1, tzinfo=ZoneInfo("UTC"))
        end_date = self.sr.end or datetime.now(tz=ZoneInfo("UTC"))
        settings = cast("Settings", self.sr.request.settings)
        parameter_columns = [parameter.name_original for parameter in dataset]
        read_columns = ["geo_id_wmo", "validity_time", *parameter_columns]
        dfs = []
        # clamp to the years actually covered by the archive: station opening dates (used as a
        # request start by e.g. the app) can predate 1996, and requesting a year
        # outside [1996, current_year] would 404
        first_year = max(start_date.year, _SYNOP_ARCHIVE_START_YEAR)
        last_year = min(end_date.year, current_year)
        for year in range(first_year, last_year + 1):
            file = _download_year(year, current_year, settings)
            # the year range above is already clamped to the archive's known coverage and each year's
            # file holds every station, so only the current year's, not yet published in early January,
            # can be missing: that 404 is dropped. Any other failure is an outage, and is raised
            # rather than leaving the year out of a result that reads as complete (GH-2461)
            if file.status != 404 or year != current_year:
                file.raise_if_exception()
            if isinstance(file.content, Exception):
                note_skipped_download()
                log.warning(f"Failed to download {file.url}: {file.content}")
                continue
            df = pl.read_csv(gunzip(file), separator=";", schema=_SYNOP_CSV_SCHEMA, columns=read_columns)
            df = df.filter(pl.col("geo_id_wmo").eq(station_id))
            if not df.is_empty():
                # the date Météo-France wrote the file of the year travels with its rows (`_note_files_with_rows`), the
                # date of the most recent update that the Licence Ouverte asks for (GH-2567)
                dfs.append(df.with_columns(pl.lit(file.last_modified, dtype=pl.Datetime("us", "UTC")).alias(UPDATED)))
        if not dfs:
            return pl.DataFrame()
        df = pl.concat(dfs, how="diagonal")
        df = df.unpivot(
            on=parameter_columns,
            index=["validity_time", UPDATED],
            variable_name="parameter",
            value_name="value",
        )
        df = with_speed_beside(df, _SYNOP_WIND_SPEED_OF_DIRECTION, on=["validity_time"])
        # before the unit conversion
        value, raw = null_sentinels(
            pl.col("value"),
            Sentinel(_SYNOP_TRACE, where=pl.col("parameter").is_in(_SYNOP_TRACE_COLUMNS), to=0.0),
            Sentinel(_SYNOP_SKY_OBSCURED, where=pl.col("parameter").eq("n")),
            no_direction_code(*_SYNOP_NO_WIND_DIRECTION, where=pl.col("parameter").eq(_SYNOP_WIND_DIRECTION_COLUMN)),
            calm(pl.col(SPEED_BESIDE)),
            # a missing reading is an empty field; a text that is no number was nulled by the cast alone
            # (the 2024 file holds none) and now keeps its text too
            non_numeric=True,
        )
        # the station, resolution and dataset are the core's to write (`shape_provider_frame`)
        df = df.select(
            pl.col("parameter").str.to_lowercase(),
            pl.col("validity_time").str.to_datetime("%Y-%m-%dT%H:%M:%SZ", strict=False).alias("timestamp"),
            value.alias("value"),
            join_quality_flags(None, raw=raw),
            UPDATED,
        )
        return self._note_files_with_rows(df, dataset)


@dataclass
class MeteoFranceSynopRequest(TimeseriesRequest):
    """Request class for Météo-France SYNOP data."""

    metadata = MeteoFranceSynopMetadata
    _values = MeteoFranceSynopValues

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        file = download_file(
            url=_SYNOP_STATIONS_ENDPOINT,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        collection = json.loads(file.content.read())
        rows = []
        for feature in collection.get("features", []):
            properties = feature["properties"]
            longitude, latitude = feature["geometry"]["coordinates"]
            rows.append(
                {
                    "station_id": properties["Id"],
                    "name": properties["Nom"],
                    "elevation": properties["Altitude"],
                    "start_timestamp": properties["Date_ouverture"],
                    "latitude": latitude,
                    "longitude": longitude,
                },
            )
        df = pl.DataFrame(
            rows,
            schema={
                "station_id": pl.String,
                "name": pl.String,
                "elevation": pl.Float64,
                "start_timestamp": pl.String,
                "latitude": pl.Float64,
                "longitude": pl.Float64,
            },
        )
        df = df.lazy()
        return df.with_columns(
            pl.col("start_timestamp").str.to_datetime("%Y-%m-%d", strict=False),
        )
        # one catalogue for every dataset: the core copies it over the request's datasets
