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
from wetterdienst.model.quality_flags import (
    SPEED_BESIDE,
    NoReading,
    OutOfRange,
    Sentinel,
    calm,
    join_quality_flags,
    no_direction_code,
    null_sentinels,
    station_pressure_range,
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

# `tn12` is the minimum of the 12 hours and `tx12` the maximum, so they are equal only where the temperature held
# still. Three overseas stations write the maximum of the daytime into `tn12` as well, at some hours: Cayenne-Matoury
# (81405) at 00 UTC, Le Raizet (78897) and Lamentin (78925) at 00 and 18 UTC, 1296 rows of the 2026 file and 1116 of
# 2025 (read 2026-10-28); Cayenne at 2026-07-01T00:00Z has `tx12` and `tn12` 303.75 K (30.6 C) beside `t` 298.55 K.
# The file defines neither; a `tn12` that is the very text of the `tx12` of its own row is a copy, no minimum, so it is
# null and keeps its text as the `raw` token (GH-3540). A `tn12` above the `t` of its stamp, or a `tx12` below it, is
# not mapped: Kerguelen (61998) has 28 rows of either, up to 3.5 K, a timing offset that was not investigated
_SYNOP_MINIMUM_12H = "tn12"
_SYNOP_MAXIMUM_12H = "tx12"
_SYNOP_MAXIMUM_BESIDE = "__tx12_beside"

# The pressure at the station is also held to what the barometric formula expects at the station's elevation (`Altitude`
# of the station list), 6,000 Pa either way (`station_pressure_range`, GH-3627): the bounds below let through a `pres`
# typed wrong by a digit at a station near sea level, such as 41,450 Pa at LA DESIRADE (27 m) in 1996-06-02 or 100,500
# at the Mont Aigoual (1,567 m). The first of the two rules that matches decides, and both keep the number as `raw`.
_SYNOP_PRESSURE_COLUMN = "pres"
_PA_PER_HPA = 100.0

# A reading no sensor can have produced is null, and keeps the number the file wrote as the `raw` token (GH-3135, as
# GH-2797 does for DMI, RMI and the DWD road stations). The files hold a few, with no code to tell them: in the files
# of 1996, 2000, 2005, 2010 and 2015 `pres` reads 10,860 to 42,060 Pa in 31 rows (3, 23, 3, 0 and 2 per file; La
# Desirade 2005-01-10: 11,170 Pa beside a `pmer` of 101,550, and 41,450 Pa at 78890 on 1996-06-02 at 15 h, a station
# at 27 m), `t` 333.95 to 369.15 K in 20 rows, `td` in 14, `rr1` 800 mm (61976, 2000-07-06), and none in the files of
# 2020, 2022, 2024 and 2025. The bounds are in the unit of the file and sit inside the range of
# `tests/provider/physical_ranges.py`; each rests on a record, with room above it:
# - `pres`, the pressure at the station, 50,000 to 110,000 Pa: the highest sea level pressure is 108,480 Pa
#   (Tosontsengel, 2001) and the highest station of the archive is MONT AIGOUAL (07560, 1,567 m, about 840 hPa); 500 hPa
#   is the air at 5,500 m;
# - `pmer`, the pressure reduced to sea level, 85,000 to 110,000 Pa: 87,000 Pa is the lowest (typhoon Tip, 1979);
# - `t`, `td`, `tn12`, `tx12`, `tn24`, `tx24`, 183.15 to 333.15 K (-90 to 60 C): the lowest air temperature is -89.2 C
#   (Vostok, 1983), the highest 56.7 C (Furnace Creek, 1913);
# - `rr1`, 0 to 600 mm: the most in an hour is 401 mm (Shangdi, 1975);
# - `rr3`, `rr6`, `rr12`, 0 to 1,200 mm: the most in 12 hours is 1,144 mm (Foc-Foc, La Reunion, 1966), and a shorter
#   span cannot hold more;
# - `rr24`, 0 to 2,000 mm: the most in a day is 1,825 mm (Foc-Foc, 1966).
# The trace -0.1 is mapped to 0.0 before, so the lower bound of 0 leaves it alone. A `rr6` of 805 mm (78890, 2005-11-11)
# and a `rr24` of 999.4 mm (78897, 2005-08-18) are inside these bounds, as a tropical storm can bring them: they stay.
_SYNOP_RANGES: dict[str, tuple[float, float]] = {
    "pres": (50_000.0, 110_000.0),
    "pmer": (85_000.0, 110_000.0),
    "t": (183.15, 333.15),
    "td": (183.15, 333.15),
    "tn12": (183.15, 333.15),
    "tx12": (183.15, 333.15),
    "tn24": (183.15, 333.15),
    "tx24": (183.15, 333.15),
    "rr1": (0.0, 600.0),
    "rr3": (0.0, 1_200.0),
    "rr6": (0.0, 1_200.0),
    "rr12": (0.0, 1_200.0),
    "rr24": (0.0, 2_000.0),
}

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
# beside `td` of 255 K and less). The `td` is read for it whether it is asked for or not, as the `tx12` is for the
# `tn12`. No floor on the humidity itself: a `u` of 20 % is a reading in a dry spell, and only the dew point tells.
_SYNOP_DEW_POINT = "td"
_SYNOP_HUMIDITY = "u"
_SYNOP_DEW_POINT_BESIDE = "__td_beside"
_SYNOP_FROST = 273.15

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


def _frostless_rules(station_id: str) -> list[OutOfRange | NoReading]:
    """Give the rules of a station without frost (``_SYNOP_FROSTLESS_STATIONS``).

    A temperature below 0 C is none, and the humidity beside a dew point below 0 C is none either (GH-3629).
    """
    if station_id not in _SYNOP_FROSTLESS_STATIONS:
        return []
    return [
        OutOfRange(_SYNOP_FROST, math.inf, where=pl.col("parameter").is_in(_SYNOP_TEMPERATURE_COLUMNS)),
        NoReading(
            pl.col("parameter").eq(_SYNOP_HUMIDITY)
            & pl.col(_SYNOP_DEW_POINT_BESIDE).str.strip_chars().cast(pl.Float64, strict=False).lt(_SYNOP_FROST)
        ),
    ]


class MeteoFranceSynopValues(TimeseriesValues):
    """Values class for Météo-France SYNOP data."""

    def _station_pressure_rules(self, station_id: str) -> list[OutOfRange]:
        """Give the rule of the pressure at the station: what its elevation allows, in Pa (GH-3627)."""
        rule = station_pressure_range(
            self._station_elevation(station_id),
            per_hectopascal=_PA_PER_HPA,
            where=pl.col("parameter").eq(_SYNOP_PRESSURE_COLUMN),
        )
        return [] if rule is None else [rule]

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
        # the maximum of the 12 hours is read for the minimum to be held to it, whether it is asked for or not
        beside = [_SYNOP_MAXIMUM_12H] if _SYNOP_MINIMUM_12H in parameter_columns else []
        # and the dew point for the humidity at a station without frost
        frostless = station_id in _SYNOP_FROSTLESS_STATIONS
        dew_point_beside = frostless and _SYNOP_HUMIDITY in parameter_columns
        read_columns = [
            "geo_id_wmo",
            "validity_time",
            *dict.fromkeys([*parameter_columns, *beside, *([_SYNOP_DEW_POINT] if dew_point_beside else [])]),
        ]
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
        if beside:
            df = df.with_columns(pl.col(_SYNOP_MAXIMUM_12H).alias(_SYNOP_MAXIMUM_BESIDE))
        else:
            df = df.with_columns(pl.lit(None, dtype=pl.String).alias(_SYNOP_MAXIMUM_BESIDE))
        df = df.with_columns(
            (pl.col(_SYNOP_DEW_POINT) if dew_point_beside else pl.lit(None, dtype=pl.String)).alias(
                _SYNOP_DEW_POINT_BESIDE
            )
        )
        df = df.unpivot(
            on=parameter_columns,
            index=["validity_time", UPDATED, _SYNOP_MAXIMUM_BESIDE, _SYNOP_DEW_POINT_BESIDE],
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
            NoReading(
                pl.col("parameter").eq(_SYNOP_MINIMUM_12H)
                & pl.col("value")
                .str.strip_chars()
                .cast(pl.Float64, strict=False)
                .eq(pl.col(_SYNOP_MAXIMUM_BESIDE).str.strip_chars().cast(pl.Float64, strict=False))
            ),
            *(OutOfRange(low, high, where=pl.col("parameter").eq(name)) for name, (low, high) in _SYNOP_RANGES.items()),
            *self._station_pressure_rules(station_id),
            *_frostless_rules(station_id),
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
