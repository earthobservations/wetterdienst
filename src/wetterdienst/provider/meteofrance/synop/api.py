# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Météo-France SYNOP data provider."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.judge import Beside, Bound, Rule
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

# No frost at these stations (GH-3135, as the stations of `meteofrance/observation` of the same departments). The
# stations are the WMO ids of the geojson, as the file has no department, and they are the ones of the departments of
# that rule that the archive has: Guadeloupe (LA DESIRADE 78890, ST-BARTHELEMY 78894, LE RAIZET 78897), Martinique
# (TRINITE-CARAVEL 78922, LAMENTIN 78925), Guyane (81401, 81405, 81408 and MARIPASOULA 81415; 3.6 to 5.5 N, 4 to
# 106 m), Mayotte (PAMANDZI 67005), the Iles Eparses (GLORIEUSES 61968, JUAN DE NOVA 61970, EUROPA 61972, TROMELIN
# 61976; 11.6 to 22.3 S, 3 to 9 m), Wallis-et-Futuna (HIHIFO 91753, MAOPOOPO 91754) and French Polynesia (HIVA-OA
# 91925, BORA-BORA-MOTU-AERO 91929, TAIARAPU-EST 91936, FAAA 91938, TAKAROA 91943, HAO 91944, MANGAREVA 91948 and RAPA
# 91958 at 27.6 S): all at 2 to 106 m, between 3.6 N and 27.6 S. A temperature below 0 C (273.15 K) of the air, its 12
# and 24 hour extremes or its dew point is no reading there. The nine files of 1996 to 2025 read hold 135 of them:
# `td` 115 (TROMELIN 73, of which 44 in 2015 and 24 in 2022; MARIPASOULA 16, 12 of them in 2025; SAINT GEORGES 81408 9
# in 2000), `t` 9 (242 to 252 K; EUROPA, TROMELIN, ST-BARTHELEMY, SAINT LAURENT, PAMANDZI), `tn24` 9 (8 at 81415 in
# 2025) and `tn12` 2. The `t` of RAPA, the southernmost, reaches 12.4 C at the lowest. Out of the list: GILLOT (61980,
# La Reunion, where frost occurs at altitude), SAINT-PIERRE (71805), New Caledonia (91570 to 91592) and the southern
# territories (Kerguelen 61998, Crozet 61997, Nouvelle-Amsterdam 61996, Dumont d'Urville 89642).
_SYNOP_FROSTLESS_STATIONS = frozenset(
    {
        "78890",
        "78894",
        "78897",
        "78922",
        "78925",
        "81401",
        "81405",
        "81408",
        "81415",
        "67005",
        "61968",
        "61970",
        "61972",
        "61976",
        "91753",
        "91754",
        "91925",
        "91929",
        "91936",
        "91938",
        "91943",
        "91944",
        "91948",
        "91958",
    }
)
_SYNOP_TEMPERATURE_COLUMNS = ("t", "td", "tn12", "tx12", "tn24", "tx24")
# The relative humidity of a reading whose dew point that rule nulls is null too (GH-3629): the same hygrometer failed,
# and its `u` is as wrong as the `td` that was computed from it (4 to 5 % at MARIPASOULA 81415 and TROMELIN 61976,
# beside `td` of 255 K and less). No floor on the humidity itself: a `u` of 20 % is a reading in a dry spell, and only
# the dew point tells.
_SYNOP_DEW_POINT = "td"
_SYNOP_HUMIDITY = "u"
_SYNOP_FROST_CELSIUS = 0.0

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


def _canonical(*originals: str) -> tuple[str, ...]:
    """Give the canonical names of the parameters the file calls ``originals``."""
    names = {
        parameter.name_original: parameter.name
        for dataset in MeteoFranceSynopMetadata.subdaily
        for parameter in dataset
    }
    return tuple(names[original] for original in originals)


# `tn12` is the minimum of the 12 hours and `tx12` the maximum, so they are equal only where the temperature held
# still. Three overseas stations write the maximum of the daytime into `tn12` as well, at some hours: Cayenne-Matoury
# (81405) at 00 UTC, Le Raizet (78897) and Lamentin (78925) at 00 and 18 UTC, 1296 rows of the 2026 file and 1116 of
# 2025 (read 2026-10-28); Cayenne at 2026-07-01T00:00Z has `tx12` and `tn12` 303.75 K (30.6 C) beside `t` 298.55 K.
# The file defines neither; a `tn12` that is the very text of the `tx12` of its own row is a copy, no minimum, so it is
# null and keeps its text as the `raw` token (GH-3540). A `tn12` above the `t` of its stamp, or a `tx12` below it, is
# not mapped: Kerguelen (61998) has 28 rows of either, up to 3.5 K, a timing offset that was not investigated
_MINIMUM_COPIES_MAXIMUM = Beside(
    target=_canonical("tn12")[0],
    partner=_canonical("tx12")[0],
    when=lambda minimum, maximum: minimum.eq(maximum),
)
_FROSTLESS_RULES: tuple[Rule, ...] = (
    Bound(high=math.inf, low=_SYNOP_FROST_CELSIUS, names=_canonical(*_SYNOP_TEMPERATURE_COLUMNS)),
    Beside(
        target=_canonical(_SYNOP_HUMIDITY)[0],
        partner=_canonical(_SYNOP_DEW_POINT)[0],
        when=lambda _, dew_point: dew_point.lt(_SYNOP_FROST_CELSIUS),
    ),
)


class MeteoFranceSynopValues(TimeseriesValues):
    """Values class for Météo-France SYNOP data."""

    def _plausibility_rules(self, station_id: str, dataset: DatasetModel) -> tuple[Rule, ...]:  # noqa: ARG002
        """Give the rules of the file: no `tn12` that copies `tx12`, and no frost at the stations of the tropics."""
        return (_MINIMUM_COPIES_MAXIMUM, *(_FROSTLESS_RULES if station_id in _SYNOP_FROSTLESS_STATIONS else ()))

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
        read_columns = ["geo_id_wmo", "validity_time", *dict.fromkeys(parameter_columns)]
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
        # before the unit conversion; what is no reading by its range or its neighbours is the core's to judge
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
            # the text the file wrote, which the core writes in the `raw:` token of a value it rejects
            pl.col("value").alias("source_text"),
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
