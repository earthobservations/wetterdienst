# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""MET Norway Frost API provider."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlparse

import polars as pl
from aiohttp import encode_basic_auth

from wetterdienst.exceptions import CredentialMissingError, DownloadError, InvalidTimeIntervalError, NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, LicenseModel, ParameterModel, build_metadata_model
from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.settings import Settings
from wetterdienst.util.network import (
    CREDENTIAL_REJECTED_STATUSES,
    PROBE_TIMEOUT,
    File,
    as_outage,
    download_file,
    raise_if_credential_rejected,
    read_refusal,
)
from wetterdienst.util.response_warnings import note_skipped_download

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel

log = logging.getLogger(__name__)

_MetnoFrostMetadataSpec = {
    "name_short": "MetNo Frost",
    "name_english": "Norwegian Meteorological Institute",
    "name_local": "Meteorologisk institutt",
    "country": "Norway",
    "country_code": "NO",
    "copyright": "© Norwegian Meteorological Institute (MET Norway)",
    "license": LicenseModel(
        # MET Norway: "all data and products are licensed under the Norwegian Licence for Open Government Data
        # (NLOD) 2.0 and Creative Commons 4.0 BY International licences" (https://api.met.no/doc/License, read
        # 2026-10-26): both, so `AND`; the conditions of both apply (NLOD 2.0 § 5 and 6, CC BY 4.0 § 3)
        spdx_id="CC-BY-4.0 AND NLOD-2.0",
        name="Creative Commons Attribution 4.0 International and Norwegian Licence for Open Government Data 2.0",
        url="https://api.met.no/doc/License",
    ),
    "attribution": "Data from MET Norway",
    "url": "https://frost.met.no",
    "kind": "observation",
    "extent": {
        "scope": "national",
        "continents": ["europe"],
        "country_codes": ["NO"],
        # declared from the documentation of MET Norway, no list was read (a key is needed): Norway with Svalbard and
        # Jan Mayen, and the platforms on the shelf of the North Sea (Ekofisk, 56.5 N), so the box reaches 55. The
        # research stations in Antarctica and on Bouvetoya are not declared: the documentation does not say. The list
        # (read in CI since) also holds about 237 foreign SYNOP stations, under `SN` + the WMO number x 100 (SN743400
        # is Limoges-Bellegarde). Frost serves observations for them (checked 2026-10-29, GH-3495), mostly with short
        # recent series (Limoges and De Kooy from 2026-10-26). The extent stays national and the box that of Norway,
        # because the network is Norway's; the live catalogue test excepts the foreign stations by their id pattern
        # (`FROST_FOREIGN_WMO` in tests/provider/station_catalogue.py)
        "bbox": [-10.0, 55.0, 32.0, 81.0],
    },
    "timezone": "Europe/Oslo",
    "auth": True,
    "resolutions": [
        {
            "name": "10_minutes",
            "name_original": "PT10M",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max(air_temperature PT10M)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min(air_temperature PT10M)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity_relative_max",
                            "name_original": "max(relative_humidity PT10M)",
                            "unit": "percent",
                        },
                        {
                            "name": "humidity_relative_min",
                            "name_original": "min(relative_humidity PT10M)",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "max(wind_speed_of_gust PT10M)",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "max(wind_from_direction_of_gust PT10M)",
                            "unit": "degree",
                        },
                        {
                            "name": "precipitation_amount",
                            "name_original": "sum(precipitation_amount PT10M)",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "hourly",
            "name_original": "PT1H",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_2m",
                            "name_original": "air_temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_2m",
                            "name_original": "dew_point_temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity_relative",
                            "name_original": "relative_humidity",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_speed_mean_last_10min",
                            "name_original": "wind_speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction_mean_last_10min",
                            "name_original": "wind_from_direction",
                            "unit": "degree",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "air_pressure_at_sea_level",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "surface_air_pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "cloud_area_fraction",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "radiation_global_intensity_mean",
                            "name_original": "mean(surface_downwelling_shortwave_flux_in_air PT1H)",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "precipitation_amount",
                            "name_original": "sum(precipitation_amount PT1H)",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "surface_snow_thickness",
                            "unit": "centimeter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "6_hours",
            "name_original": "PT6H",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "precipitation_amount",
                            "name_original": "sum(precipitation_amount PT6H)",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "daily",
            "name_original": "P1D",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "mean(air_temperature P1D)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max(air_temperature P1D)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min(air_temperature P1D)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_amount",
                            "name_original": "sum(precipitation_amount P1D)",
                            "unit": "millimeter",
                        },
                        {
                            "name": "wind_speed_mean",
                            "name_original": "mean(wind_speed P1D)",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed_rolling_mean_max",
                            "name_original": "max(wind_speed P1D)",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "humidity_relative_mean",
                            "name_original": "mean(relative_humidity P1D)",
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_sea_level_mean",
                            "name_original": "mean(air_pressure_at_sea_level P1D)",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site_mean",
                            "name_original": "mean(surface_air_pressure P1D)",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global_intensity_mean",
                            "name_original": "mean(surface_downwelling_shortwave_flux_in_air P1D)",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "surface_snow_thickness",
                            "unit": "centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sum(duration_of_sunshine P1D)",
                            "unit": "hour",
                        },
                    ],
                },
            ],
        },
        {
            "name": "monthly",
            "name_original": "P1M",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "mean(air_temperature P1M)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max(air_temperature P1M)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min(air_temperature P1M)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "mean(dew_point_temperature P1M)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_amount",
                            "name_original": "sum(precipitation_amount P1M)",
                            "unit": "millimeter",
                        },
                        {
                            "name": "wind_speed_mean",
                            "name_original": "mean(wind_speed P1M)",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed_rolling_mean_max",
                            "name_original": "max(wind_speed P1M)",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "humidity_relative_mean",
                            "name_original": "mean(relative_humidity P1M)",
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_sea_level_mean",
                            "name_original": "mean(air_pressure_at_sea_level P1M)",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site_mean",
                            "name_original": "mean(surface_air_pressure P1M)",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "cloud_cover_total_mean",
                            "name_original": "mean(cloud_area_fraction P1M)",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "snow_depth_mean",
                            "name_original": "mean(surface_snow_thickness P1M)",
                            "unit": "centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sum(duration_of_sunshine P1M)",
                            "unit": "hour",
                        },
                    ],
                },
            ],
        },
        {
            "name": "annual",
            "name_original": "P1Y",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "mean(air_temperature P1Y)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max(air_temperature P1Y)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min(air_temperature P1Y)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_amount",
                            "name_original": "sum(precipitation_amount P1Y)",
                            "unit": "millimeter",
                        },
                        {
                            "name": "cloud_cover_total_mean",
                            "name_original": "mean(cloud_area_fraction P1Y)",
                            "unit": "one_eighth",
                        },
                    ],
                },
            ],
        },
    ],
}
MetnoFrostMetadata = build_metadata_model(_MetnoFrostMetadataSpec, "MetnoFrostMetadata")


# Frost writes in-band codes into the value itself, where nothing tells them apart from a measurement. It states
# them in its data clarifications (https://frost.met.no/dataclarifications.html, "Explanations for some coded
# negative value elements"); the description of an element states one only for the snow depth and the cloud cover.
# Of the elements this module reads the table lists these (all "not converted"; the precipitation sums are below):
#
# - `wind_from_direction` -3: "No unique wind direction is given when winds are weak". It is null here, with the code
#   kept (the range check used to take it for a bearing below 0: null as `rejected:range` in hard mode, and the
#   value `-3.0` with `suspect:range` in soft mode). Read on 2026-11-06, 22 October to 5 November, at the foreign WMO
#   stations Frost lists since 2026-11-03: 72 of 9,255 hourly readings at 12 of the 249 stations with wind readings,
#   all beside a wind speed of 0.5 to 2.6 m/s, and none in 108,161 readings of 328 stations in 10 to 24 January 2026.
#   The 0 of the direction is not in the table; at those foreign stations it stands beside a speed of 0 in 359 of 372
#   readings, and it is returned as the 0.0 it is written as (GH-3137)
# - `surface_snow_thickness` -1: "Zero snowdepth or partial snow cover" (the description of the element: "Code=-1
#   means no snow"), read as a depth of zero rather than an absent one. It reaches the caller as -1 cm otherwise, and
#   it is not rare: at SN18700 across one summer, 93 of 185 daily observations are -1 against 92 measured zeros.
#   Beside the daily `snow_coverage_type` (0 or -1 no snow, 1 mostly free, 2 half, 3 mostly covered, 4 covered) of the
#   same station and day (16 stations, 2015-10 to 2016-06), 11.2 % of the 954 days of a -1 from November to April have
#   a cover of 1 to 4 (107 days), and 1.6 % of the 888 from May to October; a 0 has it on 8.7 % of 196 days from
#   November to April. Read as 0.0
# - `surface_snow_thickness` 0: "Snowdepth less than 0.5 cm", returned as the 0.0 it is written as, with no token. By
#   the same definition (0 or -1 is no snow) it is no snow in 91.6 % of 474 days
# - `surface_snow_thickness` -3: "Not possible to measure snowdepth". That is no depth: null, with the code kept. It
#   was not mapped, and a -3 would have come back as -3 cm, a value inside the range of the parameter. None was seen in
#   about 150,000 snow depths read (daily and hourly, Norwegian and foreign stations). Negative depths the table does
#   not list are returned as they are: one -2 at SN91500 on 2017-07-24 (daily, quality 2), and 12 hourly values of
#   -0.29 to -0.01 at SN18700 on 2016-08-04 and 05 (quality 0)
# - cloud cover -3 and 9 both mean the cover could not be estimated, the sky being obscured (the clarifications state
#   the -3: "Cloud cover is not estimated because of fog or analogous phenomena"; the description of the element states
#   both). In eighths those convert to -0.375 and 1.125 of the sky, the second of which looks like a plausible reading
#   rather than a code. Of the hourly readings the 9 is 19,669 of 572,955 at the five Norwegian stations with an open
#   series of the element (seven have one; 2008 to 2025) and 35 of 8,743 at the foreign ones; a -3 was in none of them
# - precipitation -1 is "No precipitation": for `sum(precipitation_amount PT6H)` and `PT12H` (not converted), for
#   `sum(precipitation_amount P1D)` (converted to 0.0 mm) and for `sum_over_undefined_period(precipitation_amount
#   PT1H)` (not converted). The range check took it for a reading below 0 mm and dropped it, so a station whose
#   6-hourly readings were all -1 had "no values" (GH-3748)
#
# What is read of the precipitation -1, measured on 2026-11-06 and 07 (the evidence is in
# docs/data/provider/metno/frost/index.md):
#
# - 6-hourly: 0.0 from 1982 on, null before, both with `raw:-1`. Frost states no date limit; we depart from it on data
#   grounds. The series has 0.2 % of its readings -1 in 1981 and 53 % in 1982. From 1982 on the 12-hourly sum that
#   holds a -1 is dry (-1 or 0) in 86.4 % of the cases, where the station-year's own 12-hourly sums are dry in 57.0 %
#   and the sum that holds a reading above 0 in 0.8 %. Before 1982 the -1 tells little: 61.6 % against 60.4 % in
#   1920-59 (11,600 -1), 70.6 % against 49.1 % in 1960-81 (891), where it is 0.2 to 3.2 % of the readings. In the 1940s
#   and 1950s every reading of a station is -1, wet days included (SN39040: 1,096 of 1,096 in 1950-52; on 1951-08-05
#   the 12-hourly sum that holds the 12 UTC reading is 67.3 mm, the daily sum of the 18-18 series 79.3 mm, the
#   6-hourly reading -1). The cut stays at 1982: the share of -1 goes from 0.2 to 53 %, the median lift of a
#   station-year is 1.9 points before and 31.1 from 1982, and a null is the safe side of a false 0.0
# - hourly: the same, 0.0 from 1982 on and null before. `sum(precipitation_amount PT1H)` is not an element of Frost's
#   table (`sum_over_undefined_period(... PT1H)` is), so this is our reading. The evidence is the WMO stations Frost
#   lists since 2026-11-03 (10,576 of 11,119 hourly readings are -1; a daily -1 holds 24 dry hours in 213 of 213),
#   less the Norwegian hourly series: 250 of 796,636 readings, in 1994 to 2004, and no day of them has all 24 hours
#   (66 of 78 days agree with the daily sum)
# - daily: Frost states 0.0 mm, and the -1 stays below the range here: null, `rejected:range,raw:-1`, as before. At the
#   stations that read once a week it also marks a day that was not read (SN81930 in 1990: eight -1, 17.5, eight -1,
#   32.5), so it is left until GH-3820 has measured it
# - not for the 10-minute sum (no -1 in 394,188 readings), the monthly sum (305, none since 1954) and the annual sum
#   (none in 70,022), where Frost states nothing and nothing supports it: a -1 there is null by the range check
#
# A few 6-hourly station-years since 1982 do not fit (the docs page lists them, SN18960 in 1996 among them); they are
# returned as 0.0 all the same.
#
# The code is a `raw:` token, which exempts the reading from the checks, as snow depth's: the 0.0 is not judged by
# `limits`, and a -1 of quality 7 comes back without `suspect:source`.
#
# Only the elements themselves. Frost leaves the codes out of its own monthly and annual means --
# checked over nine years at SN18700, where neither mean goes negative or above eight.
_SNOW_DEPTH = "surface_snow_thickness"
_NO_SNOW = "-1"
_WIND_DIRECTION = "wind_from_direction"
# "No unique wind direction is given when winds are weak" for the direction, "Not possible to measure snowdepth" for the
# snow depth
_NOT_GIVEN = "-3"
_CLOUD_COVER = "cloud_area_fraction"
_CLOUD_COVER_NOT_ESTIMATED = ("-3", "9")
_PRECIPITATION_SUMS = (
    "sum(precipitation_amount PT6H)",
    "sum(precipitation_amount PT1H)",
)
_NO_PRECIPITATION = "-1"
_NO_PRECIPITATION_FROM_YEAR = 1982
_DAILY = "daily"


def _raise_if_rejected(file: File) -> None:
    """Raise the `CredentialRejectedError` of a download that Frost answered with a 401 or a 403 (GH-2665, GH-3018)."""
    raise_if_credential_rejected(file, "Frost API", "METNO_FROST", "client ID")


# Frost's own words for a request it will not compute, in the body of a 403 (the estimate and then the limit)
_TOO_MANY_OBSERVATIONS = re.compile(
    r"estimated number of observations \((\d+)\) exceeds the maximum number allowed \((\d+)\)", re.IGNORECASE
)


def _raise_if_window_too_large(file: File, settings: Settings | None, client_kwargs: dict | None) -> None:
    """Raise `InvalidTimeIntervalError` for a 403 that Frost gives a window it will not compute (GH-3748).

    Frost answers a request for more than 100,000 observations with a 403, the same status it gives a client ID it
    refuses, and says which in the body: "The estimated number of observations (...) exceeds the maximum number
    allowed (100000)". The key is fine then, and the caller has to ask for less. The body is not kept by the
    download, so the refusal is asked for again, once, and only when the status is a 403.
    """
    if settings is None or file.status != HTTPStatus.FORBIDDEN or not isinstance(file.content, Exception):
        return
    headers = (client_kwargs or {}).get("headers")
    reason = read_refusal(
        file.url,
        headers=headers,
        client_kwargs={key: value for key, value in (client_kwargs or {}).items() if key != "headers"},
        use_certifi=settings.use_certifi,
    )
    match = _TOO_MANY_OBSERVATIONS.search(reason or "")
    if match is None:
        return
    query = parse_qs(urlparse(file.url).query)
    asked = (
        f"{query.get('elements', ['?'])[0]} of {query.get('sources', ['?'])[0]}, {query.get('referencetime', ['?'])[0]}"
    )
    estimate, limit = (int(number) for number in match.groups())
    msg = (
        f"Frost answers at most {limit:,} observations to a request, and the window asked for ({asked}) would hold an "
        f"estimated {estimate:,}. Your client ID is accepted; narrow the window (start and end) and ask again."
    )
    raise InvalidTimeIntervalError(msg)


def _raise_if_unanswered(file: File, settings: Settings | None = None, client_kwargs: dict | None = None) -> None:
    """Raise for a download that Frost did not answer, or answered with a refusal (GH-3022, GH-3018, GH-3748).

    A window that Frost will not compute (a 403 whose body says so) is the `InvalidTimeIntervalError` the caller can
    rephrase. A client ID that Frost refuses (401, 403) is the `CredentialRejectedError`, whoever runs the process
    has to replace it. A timeout, a dropped connection, a body cut short, a 5xx and a connection that could not be made
    are the `DownloadError` and the `NoInternetError` (`as_outage`): none of them is Frost saying there is no data,
    and answered as an empty frame they read as a station without data. What Frost does answer stays with the
    caller, which reads the status: a 404 and a 412 are no data, and any other 4xx is warned about.

    ``settings`` and ``client_kwargs`` are those the download was made with, for the 403 to be read again.
    """
    _raise_if_window_too_large(file, settings, client_kwargs)
    _raise_if_rejected(file)
    if isinstance(file.content, Exception):
        failure = as_outage(file.content, file.url)
        if isinstance(failure, (NoInternetError, DownloadError)):
            raise failure


def _has_observations(df: pl.DataFrame) -> bool:
    """Tell whether Frost's answer has a `data` entry with an observation in it (GH-3750).

    `{"data": []}`, `{"data": null}`, an entry without the key `observations` and one whose `observations` is `[]`
    or `null` all answer no: read as they are, each is a column of nulls or a missing column that cannot be unnested.
    """
    if "data" not in df.columns:
        return False
    entries = df.get_column("data").explode().drop_nulls()
    if entries.dtype != pl.Struct or "observations" not in entries.struct.fields:
        return False
    observations = entries.struct.field("observations")
    return observations.dtype == pl.List and not observations.explode().drop_nulls().is_empty()


def _quality_flags(df: pl.DataFrame) -> pl.Expr:
    """Give Frost's `qualityCode` as the plain flag of `quality_flags`, null where the observations carry none.

    Frost leaves the key out of an observation that has no code (SN30320 `daily`, 2015-05-01), so that an answer in
    which none has one has no such column to select (GH-3748).
    """
    if "qualityCode" not in df.columns:
        return pl.lit(None, dtype=pl.String).alias("quality_flags")
    return pl.col("qualityCode").cast(pl.Int64).cast(pl.String).alias("quality_flags")


def _frost_time(value: datetime) -> str:
    """Give a request bound as Frost reads it: the text of its UTC wall clock.

    Frost takes the time of `referencetime` as UTC and has no way to be told otherwise. The bounds
    of a request are UTC, whatever zone they were given in (GH-2681, GH-2682), so their wall clock is
    the one to write down.
    """
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def _frost_end_exclusive(value: datetime, resolution: str) -> datetime:
    """Give the exclusive end Frost needs to return the stamp at the end of a closed window.

    Frost's intervals are open-ended: "[t0,t1>, i.e. representing times later than or equal to t0 and earlier
    than t1" (https://frost.met.no/concepts2.html), while the window of a request is closed at both ends. An
    end sent unchanged lost the value stamped at it, the 00:00 reading of a one-hour request or the month that
    starts at it (GH-2746). A second later names it; what lies beyond the window is cut off by the framework.

    A daily value belongs to the date of its stamp, which is the date of the reading for an instantaneous element
    (`_stamp_days`), so a request whose end is 00:00 UTC of a date asks for the whole of that date, the 06:00 UTC
    reading of the snow depth being its value (GH-2729): its end is 00:00 UTC of the date after. The end is UTC, as
    the bounds of a request are.
    """
    if resolution == _DAILY:
        return value.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return value + timedelta(seconds=1)


def _frost_end(value: datetime, resolution: str) -> str:
    """Give the end of a request as Frost reads it (see `_frost_end_exclusive`)."""
    return _frost_time(_frost_end_exclusive(value, resolution))


def _stamp_days(df: pl.DataFrame, resolution: str) -> pl.DataFrame:
    """Stamp a daily value at 00:00 UTC of the day it belongs to (GH-2729).

    Frost stores a daily value with a date only, `referenceTime` `<date>T00:00`, except for an instantaneous
    observation, which "is stored with date and time" and whose `referenceTime` "is equal to the observation
    time" (https://frost.met.no/concepts2.html). Of the daily elements that is `surface_snow_thickness`,
    stamped at the time of its reading, so it sat besides the other daily parameters at a time of its own, which
    a window of whole days, as the one of a request for a day, does not keep (GH-2683 for SMHI). The reading
    on a date belongs to that date; the other daily stamps are at 00:00 UTC already.

    ``resolution`` is the name of the resolution the frame was collected for: the frame has no column of it, the core
    writes that (`shape_provider_frame`).
    """
    if resolution != _DAILY:
        return df
    return df.with_columns(pl.col("timestamp").dt.truncate("1d"))


def _decode_sentinels(df: pl.DataFrame) -> pl.DataFrame:
    """Turn Frost's in-band codes into the value they stand for, before anything reads them.

    The code stays beside the value as the last token of `quality_flags`, `0,raw:-1`, written as Frost documents the
    code: the value is a JSON number, so its text is not at hand (GH-2759).
    """
    _precipitation = pl.col("parameter").is_in(_PRECIPITATION_SUMS)
    _year = pl.col("timestamp").dt.year()
    value, raw = null_sentinels(
        pl.col("value"),
        Sentinel(_NO_SNOW, where=pl.col("parameter") == _SNOW_DEPTH, to=0.0),
        Sentinel(_NO_PRECIPITATION, where=_precipitation & (_year >= _NO_PRECIPITATION_FROM_YEAR), to=0.0),
        Sentinel(_NO_PRECIPITATION, where=_precipitation & (_year < _NO_PRECIPITATION_FROM_YEAR)),
        Sentinel(*_CLOUD_COVER_NOT_ESTIMATED, where=pl.col("parameter") == _CLOUD_COVER),
        Sentinel(_NOT_GIVEN, where=pl.col("parameter").is_in([_WIND_DIRECTION, _SNOW_DEPTH])),
        text=False,
    )
    quality = pl.col("quality_flags") if "quality_flags" in df.columns else None
    return df.with_columns(value.alias("value"), join_quality_flags(quality, raw=raw))


class MetnoFrostValues(TimeseriesValues):
    """Values class for MET Norway Frost API."""

    _observations_url = (
        "https://frost.met.no/observations/v0.jsonld"
        "?sources={station_id}"
        "&elements={element}"
        "&referencetime={start}/{end}"
        "&timeresolutions={time_resolution}"
    )
    _available_time_series_url = (
        "https://frost.met.no/observations/availableTimeSeries/v0.jsonld"
        "?sources={station_id}"
        "&elements={element}"
        "&timeresolutions={time_resolution}"
    )
    _observations_url_ts = (
        "https://frost.met.no/observations/v0.jsonld"
        "?sources={source_id}"
        "&elements={element}"
        "&referencetime={start}/{end}"
        "&timeresolutions={time_resolution}"
        "&timeseriesids={ts_id}"
        "&performancecategories={perf_cats}"
        "&exposurecategories={expo_cats}"
    )

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        from wetterdienst.model.metadata import DatasetModel  # noqa: PLC0415

        if isinstance(parameter_or_dataset, DatasetModel):
            dataset = parameter_or_dataset
            parameters = parameter_or_dataset.parameters
        else:
            dataset = parameter_or_dataset.dataset
            parameters = [parameter_or_dataset]

        start_date = self.sr.start
        end_date = self.sr.end
        if not start_date or not end_date:
            # nothing is asked of Frost without a window. The library refuses such a request (every Frost dataset is
            # `date_required`), so this is reached only without its check, as a test does: no file is let go that
            # `file-skipped` could name, and `parameter-without-rows` says nothing of a dataset that needs a window
            return pl.DataFrame()

        settings = self.sr.settings
        client_kwargs = {**settings.fsspec_client_kwargs}
        if settings.auth.metno_frost:
            client_id, secret = settings.auth.metno_frost
            client_kwargs["headers"] = {
                **client_kwargs.get("headers", {}),
                "Authorization": encode_basic_auth(client_id.get_secret_value(), secret.get_secret_value()),
            }

        # Fetch all elements of the dataset in a single request instead of one request per
        # parameter. The Frost API accepts a comma-separated `elements` list and returns
        # observations for all of them together.
        elements = ",".join(parameter.name_original for parameter in parameters)
        url = self._observations_url.format(
            station_id=station_id,
            element=elements,
            start=_frost_time(start_date),
            end=_frost_end(end_date, dataset.resolution.name),
            time_resolution=dataset.resolution.name_original,
        )
        log.info(f"Acquiring data from {url}")
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # the status is read before the generic failure warning below: a 404 or 412 says there is
        # nothing (or that a fallback applies), not that the request failed
        # 412: no data for this station/elements/period combination
        _raise_if_unanswered(file, settings, client_kwargs)
        if file.status == 412:
            return pl.DataFrame()
        # 404: Frost's "No data found" for a window without data. The elements are resolved one by one and then
        # through the time series, which found data in none of the 12 such series of a sample of 208 (GH-3137)
        if file.status == 404:
            return self._collect_after_batch_404(
                station_id, dataset, parameters, start_date, end_date, settings, client_kwargs
            )
        if isinstance(file.content, Exception):
            note_skipped_download()
            log.warning(f"Failed to download {url}: {file.content}")
            return pl.DataFrame()
        # a 200 with no body
        if file.is_empty:
            note_skipped_download()
            log.warning(f"Frost answered {file.url} with an empty body")
            return pl.DataFrame()

        df = pl.read_json(file.content)
        if not _has_observations(df):
            return pl.DataFrame()

        df = df.select(pl.col("data").explode(empty_as_null=True))
        df = df.unnest("data")
        # columns: sourceId, referenceTime, observations (list of structs)
        df = df.with_columns(
            pl.col("referenceTime")
            .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
            .dt.replace_time_zone("UTC"),
        )
        df = df.explode("observations", empty_as_null=True)
        df = df.unnest("observations")
        return _stamp_days(
            _decode_sentinels(
                df.select(
                    pl.col("elementId").alias("parameter"),
                    pl.col("referenceTime").alias("timestamp"),
                    pl.col("value"),
                    _quality_flags(df),
                ),
            ),
            dataset.resolution.name,
        )

    def _collect_after_batch_404(
        self,
        station_id: str,
        dataset: DatasetModel,
        batched: list[ParameterModel],
        start_date: datetime,
        end_date: datetime,
        settings: Settings,
        client_kwargs: dict,
    ) -> pl.DataFrame:
        """Resolve the requested parameters one by one after the request for `batched` 404'd.

        Only the parameters that were asked for: the batch fetched the whole dataset, but its extra
        rows are dropped later, so resolving them would spend requests on nothing. A batch of one
        element is the single request itself, which just failed, so that goes straight to discovery.
        """
        requested = {
            parameter.name_original
            for parameter in self.sr.parameters
            if (parameter.dataset.resolution.name, parameter.dataset.name) == (dataset.resolution.name, dataset.name)
        }
        resolve = self._collect_via_time_series_discovery if len(batched) == 1 else self._collect_single_parameter
        frames = [
            resolve(station_id, parameter, start_date, end_date, settings, client_kwargs)
            for parameter in batched
            if parameter.name_original in requested
        ]
        frames = [frame for frame in frames if not frame.is_empty()]
        return pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame()

    def _collect_single_parameter(
        self,
        station_id: str,
        parameter: ParameterModel,
        start_date: datetime,
        end_date: datetime,
        settings: Settings,
        client_kwargs: dict,
    ) -> pl.DataFrame:
        """Fetch a single parameter directly, falling back to time-series discovery on 404.

        Used when a batched multi-element request 404s, to resolve each parameter
        individually before the time series are asked for (`_collect_via_time_series_discovery`).
        """
        url = self._observations_url.format(
            station_id=station_id,
            element=parameter.name_original,
            start=_frost_time(start_date),
            end=_frost_end(end_date, parameter.dataset.resolution.name),
            time_resolution=parameter.dataset.resolution.name_original,
        )
        log.info(f"Acquiring data from {url}")
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # the status before the body, as in `_collect_station_parameter_or_dataset`
        # 412: no data for this station/element/period combination
        _raise_if_unanswered(file, settings, client_kwargs)
        if file.status == 412:
            return pl.DataFrame()
        # 404: no data in the window; the time series are asked for (see `_collect_via_time_series_discovery`)
        if file.status == 404:
            return self._collect_via_time_series_discovery(
                station_id, parameter, start_date, end_date, settings, client_kwargs
            )
        if isinstance(file.content, Exception):
            note_skipped_download()
            log.warning(f"Failed to download {url}: {file.content}")
            return pl.DataFrame()
        # a 200 with no body
        if file.is_empty:
            note_skipped_download()
            log.warning(f"Frost answered {file.url} with an empty body")
            return pl.DataFrame()

        df = pl.read_json(file.content)
        if not _has_observations(df):
            return pl.DataFrame()

        df = df.select(pl.col("data").explode(empty_as_null=True))
        df = df.unnest("data")
        df = df.with_columns(
            pl.col("referenceTime")
            .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
            .dt.replace_time_zone("UTC"),
        )
        df = df.explode("observations", empty_as_null=True)
        df = df.unnest("observations")
        # keep only matching elementId (the Frost response may include multiple elements)
        df = df.filter(pl.col("elementId").eq(parameter.name_original))
        return _stamp_days(
            _decode_sentinels(
                df.select(
                    pl.lit(parameter.name_original, dtype=pl.String).alias("parameter"),
                    pl.col("referenceTime").alias("timestamp"),
                    pl.col("value"),
                    _quality_flags(df),
                ),
            ),
            parameter.dataset.resolution.name,
        )

    def _collect_via_time_series_discovery(  # noqa: C901
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
        start_date: datetime,
        end_date: datetime,
        settings: Settings,
        client_kwargs: dict,
    ) -> pl.DataFrame:
        """Fall back to availableTimeSeries discovery when the direct query returns 404.

        The time series of an element carry a `timeseriesids`, `performancecategories` and `exposurecategories`
        that the availableTimeSeries endpoint lists, and the query is asked once more with them. Frost's 404 is "No
        data found" for a window without data, and it was the same 404 with them in each of the 12 series that
        answered one in a sample of 208 (4 stations, 2026-11-06, GH-3137): the step has not been seen to find data
        that the direct query did not.
        """
        element = parameter_or_dataset.name_original
        resolution = parameter_or_dataset.dataset.resolution.name_original
        resolution_name = parameter_or_dataset.dataset.resolution.name

        avail_url = self._available_time_series_url.format(
            station_id=station_id,
            element=element,
            time_resolution=resolution,
        )
        log.info(f"Discovering time series via {avail_url}")
        avail_file = download_file(
            url=avail_url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.ONE_HOUR,
            client_kwargs=client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # as for the observations below, a 404 or 412 says there is nothing, not that the request failed
        _raise_if_unanswered(avail_file, settings, client_kwargs)
        if avail_file.status in (404, 412):
            return pl.DataFrame()
        if isinstance(avail_file.content, Exception):
            note_skipped_download()
            log.warning(f"Failed to download {avail_url}: {avail_file.content}")
            return pl.DataFrame()
        if avail_file.is_empty:
            note_skipped_download()
            log.warning(f"Frost answered {avail_file.url} with an empty body")
            return pl.DataFrame()

        ts_list = json.loads(avail_file.content.read()).get("data", [])
        frames = []
        for ts in ts_list:
            valid_from = datetime.fromisoformat(ts["validFrom"].rstrip("Z")).replace(tzinfo=UTC)
            valid_to_str = ts.get("validTo")
            valid_to = (
                datetime.fromisoformat(valid_to_str.rstrip("Z")).replace(tzinfo=UTC) if valid_to_str else end_date
            )
            range_start = max(start_date, valid_from)
            range_end = min(end_date, valid_to)
            # a series that starts after the end but on its date, as a daily snow depth read at 06:00 UTC, has
            # values in the window (GH-2729)
            if range_start >= _frost_end_exclusive(range_end, resolution_name):
                continue

            params = parse_qs(urlparse(ts["uri"]).query)
            obs_url = self._observations_url_ts.format(
                source_id=params.get("sources", [station_id])[0],
                element=element,
                start=_frost_time(range_start),
                end=_frost_end(range_end, resolution_name),
                time_resolution=resolution,
                ts_id=params.get("timeseriesids", ["0"])[0],
                perf_cats=params.get("performancecategories", [""])[0],
                expo_cats=params.get("exposurecategories", [""])[0],
            )
            log.info(f"Acquiring data from {obs_url}")
            obs_file = download_file(
                url=obs_url,
                cache_dir=settings.cache_dir,
                ttl=CacheExpiry.FIVE_MINUTES,
                client_kwargs=client_kwargs,
                cache_disable=settings.cache_disable,
                use_certifi=settings.use_certifi,
            )
            _raise_if_unanswered(obs_file, settings, client_kwargs)
            # Frost's own "no data": 404 "No data was found for the query parameters" (a series the listing named
            # may have a gap in the window), 412 "No available time series for the query parameters"
            if obs_file.status in (404, 412):
                continue
            if isinstance(obs_file.content, Exception):
                note_skipped_download()
                log.warning(f"Failed to download {obs_url}: {obs_file.content}")
                continue
            if obs_file.is_empty:
                note_skipped_download()
                log.warning(f"Frost answered {obs_file.url} with an empty body")
                continue

            df = pl.read_json(obs_file.content)
            if not _has_observations(df):
                continue
            df = df.select(pl.col("data").explode(empty_as_null=True)).unnest("data")
            df = df.with_columns(
                pl.col("referenceTime")
                .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
                .dt.replace_time_zone("UTC"),
            )
            df = df.explode("observations", empty_as_null=True).unnest("observations")
            df = df.filter(pl.col("elementId").eq(element))
            frames.append(
                _stamp_days(
                    _decode_sentinels(
                        df.select(
                            pl.lit(element, dtype=pl.String).alias("parameter"),
                            pl.col("referenceTime").alias("timestamp"),
                            pl.col("value"),
                            _quality_flags(df),
                        ),
                    ),
                    resolution_name,
                )
            )

        if not frames:
            return pl.DataFrame()
        return pl.concat(frames, how="diagonal_relaxed")


def _probe_frost_credentials(settings: Settings) -> bool | None:
    """Probe the Frost API, once and for `PROBE_TIMEOUT_SECONDS`; an acceptance is cached on disk for ONE_MINUTE.

    Returns False only for the answers that say the client ID is refused (HTTP 401 and 403), True for
    a 200, and None for any other outcome -- no network, a failed TLS verification, a timeout, a 429,
    a 5xx -- which says nothing about the credentials.

    Only a 200 is cached: Frost answers a refusal or a failure with an HTTP error status, which
    `download_file` does not keep. It is kept for a minute and not an hour (GH-2750), so a client ID
    that is revoked stops reading `True` within the minute (within two minutes through `/api/auth`, which
    keeps its answer for a minute as well).
    """
    if not settings.auth.metno_frost:
        return False
    client_id, secret = settings.auth.metno_frost
    # a fresh headers dict, as every other authenticated provider builds: `{**settings...}` copies
    # one level, so `setdefault("headers", {})[...] = ...` wrote the Authorization header into the
    # dict `Settings` holds. Every later request from that `Settings` -- any provider, not only
    # this one -- then carried met.no's basic auth, which since GH-1959 also moves its blobs off
    # the shared cache directory onto a credential-named one
    client_kwargs = {
        **settings.fsspec_client_kwargs,
        "headers": {
            **settings.fsspec_client_kwargs.get("headers", {}),
            "Authorization": encode_basic_auth(client_id.get_secret_value(), secret.get_secret_value()),
        },
        # bounded: this is asked while a page waits for it (GH-2564)
        "timeout": PROBE_TIMEOUT,
    }
    file = download_file(
        url="https://frost.met.no/sources/v0.jsonld?ids=SN18700&fields=id",
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.ONE_MINUTE,
        client_kwargs=client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
        attempts=1,
    )
    if file.status in CREDENTIAL_REJECTED_STATUSES:
        return False
    if not isinstance(file.content, Exception) and file.status == 200:
        return True
    log.warning("Could not check the Frost credentials (status %s): %s", file.status, file.content)
    return None


class MetnoFrostRequest(TimeseriesRequest):
    """Request class for MET Norway Frost API."""

    metadata = MetnoFrostMetadata
    _values = MetnoFrostValues

    _sources_url = "https://frost.met.no/sources/v0.jsonld?types=SensorSystem&fields=id,name,validFrom,validTo,geometry,county,countryCode,masl"

    @classmethod
    def is_configured(cls) -> bool:  # noqa: D102
        return bool(Settings().auth.metno_frost)

    @classmethod
    def is_valid(cls, settings: Settings | None = None) -> bool | None:  # noqa: D102
        return _probe_frost_credentials(settings or Settings())

    def __post_init__(self) -> None:  # noqa: D105
        super().__post_init__()
        settings = cast("Settings", self.settings)
        if not settings.auth.metno_frost:
            msg = (
                "MET Norway Frost API requires authentication. "
                "Register a free client ID at https://frost.met.no/auth/requestCredentials.html "
                "and set WD_AUTH__METNO_FROST=<client_id> (env var) "
                "or Settings(auth={'metno_frost': '<client_id>'}) (Python)."
            )
            raise CredentialMissingError(msg)

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        client_kwargs = {**settings.fsspec_client_kwargs}
        if settings.auth.metno_frost:
            client_id, secret = settings.auth.metno_frost
            client_kwargs["headers"] = {
                **client_kwargs.get("headers", {}),
                "Authorization": encode_basic_auth(client_id.get_secret_value(), secret.get_secret_value()),
            }
        file = download_file(
            url=self._sources_url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        _raise_if_rejected(file)
        # the catalogue is one required file, so any other failure of it -- a 404 included -- is an
        # outage, which swallowed would read as a network without stations (GH-2599). A failed
        # connection (NoInternetError) is raised as well (GH-2640)
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()

        df = pl.read_json(file.content)
        df = df.select(pl.col("data").explode(empty_as_null=True)).drop_nulls()
        if df.is_empty():
            # `{"data": []}` is a list without a source, a column of nulls that cannot be unnested
            return pl.LazyFrame()
        df = df.unnest("data")
        # geometry.coordinates: [longitude, latitude, elevation?]. 24 of the 2235 sources (2026-10-19) have
        # no geometry and no position in any other field: ships, rigs and gliders (SN76999 SCARABEO 8,
        # SN20930 POLARSTERN, SN20957 SG644 GLIDER), which move. They stay in the list with a null position,
        # as the GHCN placeholders do (GH-2655): no distance search, interpolation or summary picks them
        df = df.with_columns(
            pl.col("geometry").struct.field("coordinates").list.get(0).alias("longitude"),
            pl.col("geometry").struct.field("coordinates").list.get(1).alias("latitude"),
            pl.col("geometry")
            .struct.field("coordinates")
            .list.get(2, null_on_oob=True)
            .cast(pl.Float64)
            .alias("_elevation"),
        )
        df = df.with_columns(
            pl.when(pl.col("masl").is_not_null())
            .then(pl.col("masl"))
            .otherwise(pl.col("_elevation"))
            .alias("elevation"),
        )
        if "validTo" not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=pl.String).alias("validTo"))
        df = df.with_columns(
            pl.col("validFrom")
            .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
            .alias("start_timestamp"),
            # a station still in service has no validTo, which parses to null
            pl.col("validTo").str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us").alias("end_timestamp"),
        )
        df = df.rename({"id": "station_id", "name": "name", "county": "region", "countryCode": "country"})
        # Frost pads some names with a blank (`KVANNDALEN `), which a comparison of the name misses
        df = df.select(
            "station_id",
            pl.col("name").str.strip_chars(),
            "region",
            "latitude",
            "longitude",
            "elevation",
            "start_timestamp",
            "end_timestamp",
        )
        # one catalogue for every dataset: the core copies it over the request's datasets
        return df.lazy()
