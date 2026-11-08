# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""MET Norway Frost API provider."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING, NamedTuple, cast
from urllib.parse import parse_qs, quote, urlparse

import polars as pl
from aiohttp import encode_basic_auth

from wetterdienst.exceptions import CredentialMissingError, DownloadError, InvalidTimeIntervalError, NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, LicenseModel, ParameterModel, build_metadata_model
from wetterdienst.model.quality_flags import (
    SPEED_BESIDE,
    Sentinel,
    calm,
    join_quality_flags,
    null_sentinels,
    with_speed_beside,
)
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.settings import Settings
from wetterdienst.util.network import (
    CREDENTIAL_REJECTED_STATUSES,
    PROBE_TIMEOUT,
    File,
    as_outage,
    download_file,
    drop_cached_file,
    raise_if_credential_rejected,
    read_refusal,
)
from wetterdienst.util.response_warnings import note_left_out, note_open_window, note_skipped_download

if TYPE_CHECKING:
    from io import BytesIO

    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.options import Options

log = logging.getLogger(__name__)

# how Frost writes a stamp of the sources and the series: `2026-11-07T00:00:00.000Z`
_FROST_STAMP = "%Y-%m-%dT%H:%M:%S%.fZ"
# the seconds a read of the series listing may stall for (the answer takes about 30 s in all, the server computing
# the first 8 of them before it sends)
_SERIES_TIMEOUT = 120
# how long the list of the series is kept: a week, where the sources are kept for twelve hours. A start is history and
# an end changes only when a series closes, so a list that is old costs a station that closed since a place in the
# searches of a window (the walk asks it and finds nothing), and a station that opened since keeps the dates of its
# source (the fallback of a station with no declared series). The 30 s it takes are paid once a week
_SERIES_EXPIRY = CacheExpiry.ONE_WEEK

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
        # (`FROST_FOREIGN_WMO` in tests/provider/station_catalogue.py). The list holds the closed stations as well
        # (GH-3847), three of which lie off the box, two on the coast of Greenland and one in the Barents Sea beyond
        # 32 E: the test excepts them by id (`FROST_OFF_THE_BOX`)
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
#   The 0 of the direction is not in the table, but a calm: the element's own text says "360 degrees is north", and 360
#   exists (276 foreign and 463 Norwegian readings, about twice the neighbouring degrees). The 0 stands beside a speed
#   of 0 in 359 of 372 readings at the foreign stations and, at 20 Norwegian stations picked for having the most zeros
#   (10 to 24 January 2026), in 1,014 of 1,068; 1,014 of their 1,030 readings of a speed of 0 have a direction of 0. It
#   is null with `raw:0` beside a speed of 0 of the same reading and level, as every provider that writes a calm
#   returns it (`calm`, GH-3833), and a 0 beside a speed above 0 stays. The dataset is requested whole, so its reading
#   has the speed; the single and the discovery readers ask for the direction alone, and a 0 stays there. A station
#   may measure the wind at several heights (`_prefer_standard_height`, GH-3844): the speed and the direction of a
#   time are of one height (the 10 m one where it has both, else the nearest that has both), a calm or a -3 there is
#   what the hour is, and the bearing of another height does not fill it; only where no height has both are they
#   chosen apart
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
# - daily (`sum(precipitation_amount P1D)`, the 06-06 series that is returned): 0.0 at every station and in every year,
#   with `raw:-1`, as Frost states ("converted to 0.0 mm"), with one named exception (GH-3820, the census of 2026-11-07,
#   every catalogue station with a daily series, all years: 13,869 -1 of 8,940,078 rows, none in `PT18H`). SN81930
#   (Storstilla) is a weekly reader, and up to and including 1993 its -1 is a day nobody read the gauge on (1,860 days,
#   1987-12 to 1993-11: the neighbours are wet on 48.0 % of them against 49.2 % of all its days, and a reading after a
#   run of -1 follows the run's total, Spearman 0.63, and not the day's, 0.28, so the week's rain sits in the next
#   reading): null, with `raw:-1`, for `_UNREAD_DAYS_THROUGH`. From 1994 its -1 are dry-like (neighbours 18.9 % wet) and
#   0.0. The rule that finds such a station is a median gap of 4 days or more between the readings and at least half of
#   the rows -1 in a calendar year: it gives exactly SN81930 for 1987 to 1993 and nothing else (a live test holds it for
#   SN81930 and four look-alikes; the census is the evidence for the other stations). The rest is dry: Bjornoya
#   (SN99700) 11,174 days up to 1956 (1 mm or more on 25.6 % of them against 25.3 % at the station beside it), the
#   WMO series of 2026-11 (472 of 472 days whose two 12-hourly halves are both -1), and 88 isolated days (neighbours
#   wet on 9.4 %)
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
# the speed of the same reading, which tells a calm (a direction of 0 beside a speed of 0) from a north written as 0
_WIND_SPEED = "wind_speed"
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
# the daily sum, whose -1 is 0.0 in every year but for the station-years below
_DAILY_PRECIPITATION_SUM = "sum(precipitation_amount P1D)"
# the stations whose daily -1 is a day nobody read the gauge on, up to and including the year: a weekly reader (GH-3820)
_UNREAD_DAYS_THROUGH = {"SN81930": 1993}
_DAILY = "daily"
_MONTHLY = "monthly"
_ANNUAL = "annual"
# the resolutions whose value is the aggregate of a window that can be open at the request (GH-3856), and the length of
# the period the stamp starts, by resolution: the daily value is left out while it is open, the others are marked
_PERIODS = {_DAILY: "1d", _MONTHLY: "1mo", _ANNUAL: "1y"}

# Frost keeps several series of an element at a station that differ in `timeOffset` only ("Sometimes multiple
# timeseries are available at the same station, with the only difference being the timeOffset value",
# https://frost.met.no/dataclarifications.html, "Standard time offsets"), and answers all of them where no
# `timeoffsets` is asked for: two rows for one `referenceTime`, of which the core kept the first, the one whose offset
# sorts first as a text, `PT18H` before `PT6H`. So the precipitation sums came back as the 18-18 UTC sum under a
# description of 06-06 (GH-3832). The table of that page names the offset to take:
#
#     sum(precipitation_amount P1D)  P1D  PT6H  "Standard sampling period for precipitation is 07-06 UTC"
#     sum(precipitation_amount P1M)  P1M  PT6H  "Standard sampling period for precipitation is 07-06 UTC"
#
# and https://frost.met.no/concepts2.html says what it means: "If timeOffset != PT0H, the observation represents the
# last 24 hr, at the time after midnight equal to timeOffset. E.g. elementId = sum(precipitation_amount P1D) has
# timeOffset PT6H. This means that the observation period lasts continuously from the previous date at 06 UTC to
# current date 06 UTC" (for the month: from the last day of the previous month). The rows of that offset are kept, and
# the choice is made on the rows of the answer, not by asking Frost for `timeoffsets=PT6H` or `default`: the request
# holds every element of the dataset, a `PT6H` filter drops each of them that has only `PT0H`, and `default` would
# move the temperature extremes too (below). A date that only the other series has is not returned, as it would be a
# sum of another window under this one's name; the answer says so (`other-window-left-out`, `_tell_left_out`), and it is
# no "the source has no values" (`parameter-without-rows`), as the source has them.
#
# The daily `max` and `min(air_temperature P1D)` are chosen the same way (GH-3843): they have `PT0H` (the calendar
# day, the hourly readings stamped 00:00 to 23:00) and `PT18H` at 579 and 574 stations of Frost's listing (550 and 545
# of the catalogue's), and the table prefers `PT18H` ("Standard sampling period for temperature extremes is 19-18
# UTC": the 24 hours ending 18 UTC, the hourly readings stamped `D-1` 19:00 to `D` 18:00). `PT0H` sorts first, so a
# station with both returned the calendar day, where its `PT18H` series had a date that `PT0H` had not (before `PT0H`
# began, 1.8 million station-days) the 18-18 window: the window of one parameter changed along the series, and from
# station to station. The maintainer decided on 2026-11-07 that the extremes are strict, like the precipitation: only
# `PT18H` is returned, a station without that series returns no extremes, and a date that only the other series has is
# left out and told, so that the answer does not depend on the window asked for.
#
# The daily and monthly `mean(air_temperature)` are chosen the same way (GH-3855): the calendar day (`PT0H`, the hourly
# readings stamped 00:00 to 23:00), which Frost prefers ("For cases not listed above, PT0H is always the preferred
# offset when multiple offsets are returned"). `PT0H` sorts first, so a station with both series returned it where it
# has a date and the 06-06 UTC mean (`PT6H`) on a date it lacks, one parameter in two windows: at least 3,694 days
# at 11 catalogue stations (SN25830 2,966) and 901 months at 179 (the monthly count has 804 gaps inside the validity of
# `PT0H`, so the daily one is a lower bound; docs/data/provider/metno/frost/index.md). The
# maintainer decided on 2026-11-07 that the mean is the calendar day alone, by the same mechanism: any other offset's
# rows are left out and told, a station without a `PT0H` series (none in the catalogue) returns no mean, and the answer
# does not depend on the window.
_STANDARD_OFFSET = {
    "sum(precipitation_amount P1D)": "PT6H",
    "sum(precipitation_amount P1M)": "PT6H",
    "max(air_temperature P1D)": "PT18H",
    "min(air_temperature P1D)": "PT18H",
    "mean(air_temperature P1D)": "PT0H",
    "mean(air_temperature P1M)": "PT0H",
}
# the series a standard offset is not, as the `other-window-left-out` warning names them: the precipitation's is
# `PT18H`; the extremes' is `PT0H` at the stations that have both, or `PT6H` at the 9 minimum stations of Frost's
# listing that have only that; the mean's is `PT6H` (06-06 UTC), or `PT18H` at the one station of Frost's listing that
# has only that. The clause is no more than that
_OTHER_SERIES = {
    "PT6H": "18-18 UTC series (`timeOffset` PT18H)",
    "PT18H": "other series (`timeOffset` PT0H, the hourly readings stamped 00:00 to 23:00, or PT6H)",
    "PT0H": "other series (`timeOffset` PT6H, the 06-06 UTC mean, or PT18H)",
}
# the series a standard offset is, as the warning names it: the 24 hours ending at the offset (06-06, 18-18 UTC), and
# `PT0H` by its stamps only, the hourly readings stamped 00:00 to 23:00 (the hours it ends are another reading of them)
_STANDARD_SERIES = {
    "PT6H": "06-06 UTC series (`timeOffset` PT6H)",
    "PT18H": "18-18 UTC series (`timeOffset` PT18H)",
    "PT0H": "calendar-day series (`timeOffset` PT0H, the hourly readings stamped 00:00 to 23:00)",
}
# a month is not a day, and the daily wording would describe it wrongly (GH-3863, GH-3867): the calendar month
# (`PT0H`) is midnight to midnight of the month, not "the hourly readings stamped 00:00 to 23:00"; the monthly `PT6H`
# sum and mean run from 06 UTC on the last day of the month before to 06 UTC on the last day of the month, not a 06-06
# window of a day, and so does the `PT18H` one at 18 UTC
_MONTHLY_STANDARD_SERIES = {
    "PT6H": "month series from 06 UTC on the last day of the previous month to 06 UTC on the last day of the month "
    "(`timeOffset` PT6H)",
    "PT0H": "calendar-month series (`timeOffset` PT0H, midnight to midnight of the calendar month)",
}
_MONTHLY_OTHER_SERIES = {
    "PT6H": "month series from 18 UTC on the last day of the previous month to 18 UTC on the last day of the month "
    "(`timeOffset` PT18H)",
    "PT0H": "other series (`timeOffset` PT6H, 06 UTC to 06 UTC on the last days of the months, or PT18H)",
}


def _because(element: str, offset: str) -> str:
    """Say what the `other-window-left-out` warning says of the dates only the other series of `element` has.

    The daily and the monthly element differ in the window, so the text is keyed by the element, which names its
    resolution: Frost names the standard of the sums and of the extremes in its table, and prefers `PT0H` for every
    other element.
    """
    monthly = element.endswith(" P1M)")
    other = (_MONTHLY_OTHER_SERIES if monthly else _OTHER_SERIES)[offset]
    own = (_MONTHLY_STANDARD_SERIES if monthly else _STANDARD_SERIES)[offset]
    return (
        f"these dates have a value in Frost's {other} only, and this parameter is the {own}, "
        f"the one Frost {'prefers' if offset == 'PT0H' else 'names its standard'}"
    )


# what the `other-window-left-out` warning says of the dates that only the other series has, by element
_LEFT_OUT_BECAUSE = {element: _because(element, offset) for element, offset in _STANDARD_OFFSET.items()}
# the column that carries the height of a reading's sensor beside it: a station may measure the wind at 10 m and 2 m,
# and the speed that tells a calm is the one of the direction's own level. Blank where Frost gives none
_LEVEL = "__level"
# the columns `_prefer_standard_height` works with: the height as a number, and the standard height of the element
_HEIGHT = "__height"
_STANDARD = "__standard"
# the base names of the elements that Frost serves at several heights, and the height Frost names the standard of
# each: `levels=default` "will exclude any data which is not measured at a standard level for each element"
# (https://frost.met.no/concepts2.html, "Default level and timeoffset"). The heights are the ones it answers, read
# 2026-11-08: 2 m for `air_temperature` (SN18700, SN17850, SN18950), `relative_humidity` (SN17850, SN99990) and the
# daily `mean(air_temperature P1D)` (SN18210); 10 m for `wind_speed` (SN76530), `wind_from_direction` (SN44300), the
# daily and monthly `max` and `mean(wind_speed)` (SN44300) and the 10 minute `wind_speed_of_gust` (SN76959, SN76960).
# `levels=default` is not used alone for the wind: it drops the wind of the 36 of 67 stations whose 10 m series has no
# data. The element ids that carry a name are the daily, monthly and 10 minute ones too (`mean(wind_speed P1D)`,
# `max(wind_speed_of_gust PT10M)`). The other elements are at one height or none: the pressure at 2 m only, the dew
# point, the radiation, the clouds, the sums and the snow depth with none
_STANDARD_HEIGHT = {
    "air_temperature": 2.0,
    "relative_humidity": 2.0,
    "wind_speed": 10.0,
    "wind_speed_of_gust": 10.0,
    "wind_from_direction": 10.0,
}
# the base name of an element id: `mean(wind_speed P1D)` and `max(wind_speed_of_gust PT10M)` have the name inside, the
# hourly ones are the name
_BASE_NAME = r"(?:^|\()([a-z_]+)(?:[ )]|$)"
# the column that carries the time the window of an observation closes (`_closes`), and whether it had not closed when
# the request was served (`_OPEN`, which `_decode_sentinels` writes as `completeness:Incomplete`)
_CLOSES = "__closes"
_OPEN = "__open"
# the elements of a daily value that is the reading of an instant, stamped at its time, whose window is over when it
# is read: Frost's snow depth, one reading a day at 06 UTC. The aggregates of a window (mean, maximum, minimum, sum) are
# not
_INSTANTANEOUS = ("surface_snow_thickness",)
# the code of the token `completeness` for such a value, the one the Environment Agency's own flag uses for a value
# based on incomplete data (`quality_legend.py`)
_INCOMPLETE = "Incomplete"


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


def _stamp_keys(df: pl.DataFrame, resolution: str) -> pl.DataFrame:
    """Cut the stamps to what names the period of a value: the day of a daily one, the month, the year.

    The frame the station returns has its daily stamps cut to the day (`_stamp_days`), so every comparison of its dates
    with those of another frame of the same answer is made on this key, and not on the raw `referenceTime`, which a
    series may stamp off midnight (the `PT6H` precipitation at 06:00, GH-3865). A stamp of another resolution is its own
    key.
    """
    if resolution == _DAILY:
        return _stamp_days(df, resolution)
    if resolution in _PERIODS:
        return df.with_columns(pl.col("timestamp").dt.truncate(_PERIODS[resolution]))
    return df


def _now() -> datetime:
    """Give the time a request is served at, UTC: the clock that decides which windows have closed (GH-3856).

    A function of its own so that a test sets the time (`monkeypatch.setattr(frost_api, "_now", ...)`).
    """
    return datetime.now(UTC)


def _served_at(file: File, asked_at: datetime) -> datetime:
    """Give the time the answer in hand is of: when it was asked for, or when its copy was made if that was before.

    ``asked_at`` is `_now` taken before the download began. An answer is cached for five minutes
    (`CacheExpiry.FIVE_MINUTES`), so one read after a window closed may have been fetched before: Frost's state at 17:57
    is no final value of a window that closes at 18:00, whoever reads it at 18:01. A copy that has no time (the cache is
    off, a save was skipped, a download that is stubbed) is of the time the download began, and not of the time it
    ended: a window that closes while the answer is on its way is not closed in it.
    """
    if file.cached_at is None:
        return asked_at
    return min(asked_at, datetime.fromtimestamp(file.cached_at, UTC))


def _closes(df: pl.DataFrame, resolution: str) -> pl.Expr:
    """Give, for each observation of a daily, monthly or annual element, the time its value's window closes (GH-3856).

    The window is the one `timeOffset` names ("If timeOffset != PT0H, the observation represents the last 24 hr, at the
    time after midnight equal to timeOffset", https://frost.met.no/concepts2.html). Daily, the value of the date ``D``:
    ``PT0H`` the calendar day, closing at the end of ``D``, any other offset at ``D`` + the offset (`PT6H`: 06 UTC of
    ``D``, `PT18H`: 18 UTC). Monthly, the same around the last day of the month: ``PT0H`` closes at the end of the
    month, ``PT6H`` at 06 UTC and ``PT18H`` at 18 UTC of its last day. Annual, around the last day of the year (31
    December): Frost has annual data "follow the same conventions as for seasonal and monthly data". The date, month
    or year is the key of the stamp (`_stamp_keys`). The offset is the row's own, or the one the element names
    (`_STANDARD_OFFSET`) where the row gives none, or `PT0H`.

    Null for an instantaneous element (`_INSTANTANEOUS`: the daily snow depth is the reading of an instant, which is
    over when it is read) and for any other resolution: no window.
    """
    if resolution not in _PERIODS:
        return pl.lit(None, dtype=pl.Datetime("us", "UTC"))
    key = pl.col("referenceTime").dt.truncate(_PERIODS[resolution])
    last_day = key if resolution == _DAILY else key.dt.offset_by(_PERIODS[resolution]).dt.offset_by("-1d")
    offset = pl.col("timeOffset") if "timeOffset" in df.columns else pl.lit(None, dtype=pl.String)
    standard = pl.col("elementId").replace_strict(_STANDARD_OFFSET, default=None, return_dtype=pl.String)
    hours = (
        offset.fill_null(standard)
        .fill_null("PT0H")
        .str.extract(r"^PT(\d+)H$", 1)
        .cast(pl.Int64, strict=False)
        .fill_null(0)
    )
    closes = pl.when(hours == 0).then(last_day.dt.offset_by("1d")).otherwise(last_day + pl.duration(hours=hours))
    return pl.when(pl.col("elementId").is_in(_INSTANTANEOUS)).then(None).otherwise(closes)


def _keep_standard_offset(df: pl.DataFrame) -> pl.DataFrame:
    """Keep, of an element that has several series by `timeOffset`, the rows of the one that is named (GH-3832).

    ``df`` is the observations of an answer, one row each, with `elementId` and `timeOffset`. An element that is not in
    `_STANDARD_OFFSET`, and a row that gives no offset, are kept as they are.
    """
    if "timeOffset" not in df.columns:
        return df
    return df.filter(_is_standard_offset())


def _is_standard_offset() -> pl.Expr:
    """Tell the observations that are of the offset their element names, or of an element that names none."""
    standard = pl.col("elementId").replace_strict(_STANDARD_OFFSET, default=None, return_dtype=pl.String)
    return standard.is_null() | pl.col("timeOffset").is_null() | (pl.col("timeOffset") == standard)


def _left_out_dates(df: pl.DataFrame, parameter: pl.Expr, resolution: str) -> pl.DataFrame:
    """Give the `parameter` and `timestamp` of the observations `_keep_standard_offset` leaves out, one row per date.

    The stamp is the key of the date (`_stamp_keys`), as the frame the station returns has it (GH-3865).
    """
    if "timeOffset" not in df.columns:
        return pl.DataFrame()
    return _stamp_keys(
        df.filter(~_is_standard_offset()).select(
            parameter.alias("parameter"), pl.col("referenceTime").alias("timestamp")
        ),
        resolution,
    ).unique()


def _full_name(parameter: ParameterModel) -> str:
    """Give the name a warning calls a parameter by: `resolution/dataset/parameter`."""
    return f"{parameter.dataset.resolution.name}/{parameter.dataset.name}/{parameter.name}"


def _tell_left_out(
    left_out: pl.DataFrame,
    kept: pl.DataFrame,
    names: dict[str, str],
    start: datetime,
    end: datetime,
    resolution: str,
    open_window: pl.DataFrame | None = None,
) -> None:
    """Tell the walk of the dates, of the parameters asked for, that only the series of another offset has (GH-3832).

    ``left_out`` is what `_left_out_dates` gave, ``kept`` the frame the station returns, ``names`` the name
    (`resolution/dataset/parameter`) of each parameter that was asked for by the name Frost gives it, ``start`` and
    ``end`` the window the core cuts the answer to, and ``resolution`` the name of the resolution they were asked for.
    A date the returned series has is no date left out, and neither is one the returned series has but for its window
    not having closed (``open_window``, the frame `_read_observations` gave, which `_tell_open_window` tells). The dates
    are compared by the key of the date (`_stamp_keys`) on both sides, and the window is cut on it: a stamp of the
    other series that is off midnight is the date of the returned one (GH-3865). The warning is `other-window-left-out`,
    and is why `parameter-without-rows` says nothing of such a parameter.
    """
    if left_out.is_empty():
        return
    present = [
        _stamp_keys(frame.select("parameter", "timestamp"), resolution)
        for frame in (kept, open_window)
        if frame is not None and not frame.is_empty()
    ]
    if present:
        left_out = left_out.join(pl.concat(present).unique(), on=["parameter", "timestamp"], how="anti")
    left_out = left_out.filter(pl.col("timestamp").is_between(start, end))
    for parameter, count in left_out.group_by("parameter").len().iter_rows():
        if parameter in names:
            note_left_out(names[parameter], count, _LEFT_OUT_BECAUSE[parameter])


def _tell_open_window(
    open_window: pl.DataFrame, names: dict[str, str], start: datetime, end: datetime, *, returned: bool
) -> None:
    """Tell the walk of the values, of the parameters asked for, whose window had not closed (GH-3856).

    ``open_window`` is what `_read_observations` gave: the `parameter`, the `timestamp` (the key of the date) and the
    time the window `closes`, one row for each. ``returned`` is whether they are in the answer (marked, `_OPEN`) or left
    out of it (`_leaves_open_out`), so the warning says which. A value the core cuts off (beyond the window of the
    request) is not counted. The warning is `window-not-closed`.
    """
    if open_window.is_empty():
        return
    inside = open_window.filter(pl.col("timestamp").is_between(start, end))
    summary = inside.group_by("parameter").agg(pl.len().alias("count"), pl.col("closes").min())
    for parameter, count, closes in summary.iter_rows():
        if parameter in names:
            note_open_window(names[parameter], count, closes, returned=returned)


def _no_open_window() -> pl.DataFrame:
    """Give the frame of the values of a window that had not closed (`_Read.open_window`) with none."""
    return pl.DataFrame(
        schema={"parameter": pl.String, "timestamp": pl.Datetime("us", "UTC"), "closes": pl.Datetime("us", "UTC")}
    )


def _leaves_open_out(resolution: str, *, estimate: bool) -> bool:
    """Give whether a value of a window that had not closed is left out of the answer, and not returned marked.

    A daily one always is: it looks like the day's (GH-3856). A monthly or annual one is returned marked
    `completeness:Incomplete` in `quality_flags`, which an estimate drops, so it is left out of an estimate and told as
    such (GH-3883); `values` still returns it.
    """
    return resolution == _DAILY or (estimate and resolution in _PERIODS)


def _tell_not_returned(
    read: _Read,
    kept: pl.DataFrame,
    names: dict[str, str],
    start: datetime,
    end: datetime,
    resolution: str,
    *,
    estimate: bool,
) -> None:
    """Tell what a read of the observations left out of the answer or marked (`_tell_left_out`, `_tell_open_window`).

    ``kept`` is the frame the station returns (all the series of a discovery), whose dates a date left out is not.
    ``estimate`` is whether the values are read for `interpolate` or `summarize` (`_leaves_open_out`).
    """
    leaves_out = _leaves_open_out(resolution, estimate=estimate)
    # a value of a window not closed that is left out is no date left out for another series (GH-3856)
    _tell_left_out(read.left_out, kept, names, start, end, resolution, read.open_window if leaves_out else None)
    _tell_open_window(read.open_window, names, start, end, returned=not leaves_out)


def _level(df: pl.DataFrame) -> pl.Expr:
    """Give the height of the sensor of each observation as text (blank where Frost gives none), as `_LEVEL`."""
    level = df.schema.get("level")
    if isinstance(level, pl.Struct) and "value" in level.to_schema():
        return pl.col("level").struct.field("value").cast(pl.String).fill_null("").alias(_LEVEL)
    return pl.lit("", dtype=pl.String).alias(_LEVEL)


class _Read(NamedTuple):
    """What `_read_observations` takes from the observations of an answer."""

    #: the frame the core takes
    frame: pl.DataFrame
    #: the dates of another series that was left out (`_left_out_dates`)
    left_out: pl.DataFrame
    #: the values of a window that had not closed (`parameter`, `timestamp`, `closes`; `_tell_open_window`)
    open_window: pl.DataFrame


def _read_observations(
    df: pl.DataFrame,
    parameter: pl.Expr,
    resolution: str,
    station_id: str,
    served_at: datetime,
    *,
    estimate: bool = False,
) -> _Read:
    """Give the frame the core takes from the observations of an answer, and what it left out or marked.

    ``df`` has one row per observation (`elementId`, `referenceTime`, `value`, `timeOffset`, ...), ``parameter`` is
    the expression of the name the rows are given, ``resolution`` the name of the resolution they were asked for and
    ``station_id`` the station they are of. The frame has the columns parameter, timestamp, value and quality flags.
    The other two are `_left_out_dates` and the values of a window that had not closed at ``served_at``, the time of
    the answer (`_served_at`; GH-3856): of a daily one, which is left out, and of a monthly or annual one, which stays
    and has `completeness:Incomplete` in its quality flags, unless ``estimate``, which leaves it out too
    (`_leaves_open_out`).
    """
    left_out = _left_out_dates(df, parameter, resolution)
    df = _keep_standard_offset(df)
    open_window = _no_open_window()
    if not df.is_empty() and resolution in _PERIODS:
        df = df.with_columns(_closes(df, resolution).alias(_CLOSES))
        is_open = (pl.col(_CLOSES) > served_at).fill_null(value=False)
        open_window = (
            _stamp_keys(
                df.filter(is_open).select(
                    parameter.alias("parameter"),
                    pl.col("referenceTime").alias("timestamp"),
                    pl.col(_CLOSES).alias("closes"),
                ),
                resolution,
            )
            .group_by("parameter", "timestamp")
            .agg(pl.col("closes").min())
        )
        df = df.with_columns(is_open.alias(_OPEN))
        if _leaves_open_out(resolution, estimate=estimate):
            # a daily value of a window that has not closed is partial and looks like the day's, and a monthly or annual
            # one is partial and an estimate cannot carry its mark: left out
            df = df.filter(~pl.col(_OPEN))
    if df.is_empty():
        # every row was of another series, or of a window not closed: nothing to return, and what was left out is told
        return _Read(pl.DataFrame(), left_out, open_window)
    # the height is chosen on what Frost answered, so after the offset and the open window (`closes` does not depend on
    # the height, and a row left out must not stand for a reading of a height) and before the codes are decoded: the
    # `-3` and the calm `0` of the height decide the hour, and `calm` finds the one height of a direction's speed
    frame = _stamp_days(
        _decode_sentinels(
            _prefer_standard_height(
                df.select(
                    parameter.alias("parameter"),
                    pl.col("referenceTime").alias("timestamp"),
                    pl.col("value"),
                    _quality_flags(df),
                    _level(df),
                    *([pl.col(_OPEN)] if _OPEN in df.columns else []),
                )
            ),
            station_id,
        ),
        resolution,
    )
    return _Read(_a_reading_beats_a_minus_one(frame), left_out, open_window)


def _a_reading_beats_a_minus_one(df: pl.DataFrame) -> pl.DataFrame:
    """Leave out the `-1` of a day of the daily precipitation sum that another stamp of the day has a reading for.

    A few stations of the WMO series Frost lists since 2026-11-03 write several rows for one date, stamped at different
    times (SN644700: on 2026-11-07 eight rows of `-1` from 00:00 to 08:00 and five of 0.1 from 10:00 to 16:00). The
    stamp is cut to the day, and the core keeps the first row of a reading that has a value
    (`merge_duplicate_readings`): in 0.184.0 the `-1` was not decoded, a `-1` that came first won the merge as `-1.0`
    and the range check, which runs after it, made the day null (`rejected:range,raw:-1`); as the 0.0 it is now, it
    would stand and the reading be lost (GH-3820). The reading is the day's, so the rows of `-1` of such a day are left
    out. A day with `-1` alone, and a `-1` beside another `-1`, are as they were.
    """
    minus_one = (
        (pl.col("parameter") == _DAILY_PRECIPITATION_SUM)
        & pl.col("value").is_not_null()
        & pl.col("quality_flags").fill_null("").str.ends_with(f"raw:{_NO_PRECIPITATION}")
    )
    reading = pl.col("value").is_not_null() & ~minus_one
    return df.filter(~(minus_one & reading.any().over("parameter", "timestamp")))


def _prefer_standard_height(df: pl.DataFrame) -> pl.DataFrame:
    """Keep, of an element that is measured at several heights, the readings of one height for each time (GH-3844).

    ``df`` is the frame of `_read_observations` before the codes are decoded: `parameter`, `timestamp`, `value` and the
    height of the sensor as text (`_LEVEL`), one row for each reading. Frost answers all heights of a station, 10 m
    first, and the core keeps the first row of a reading that has a value (`merge_duplicate_readings`): the air
    temperature came from 10 m in 83 % of the hours at 5 of 6 stations that have 2 m and 10 m, the 10 minute gust of
    the platforms from 47 to 120 m in 96 %, and a gap at one height was filled from another with nothing to say so.

    For each parameter and time the height kept is the standard one (`_STANDARD_HEIGHT`: 2 m for the temperature and
    the humidity, 10 m for the wind speed, the gust and the direction) if it has a value, otherwise the height of the
    other readings that has a value and is nearest to the standard one (the lower of two as near), and no other
    height's reading stays. A reading "has a value" as Frost answers it, before the decoding: the `-3` and the `0` of
    a wind direction are of the height, as the hour (GH-3833), and a null is a gap, which another height fills. A
    time with no value at any height keeps all its rows.

    The wind speed and the direction are a pair, of one height, so that a bearing never stands beside a speed of another
    height. The height of a time's pair is, in this order:

    1. the standard height (10 m), if it has both a speed and a direction;
    2. else the height that has both and is nearest to the standard one (the lower of two as near): the speed and the
       bearing are both of it, though the standard height has a speed;
    3. else (no height has both: Frost never measured them at one height, as at SN92120 and SN92130 in 1992-02 to
       1993-12, the speed at 2 m and the bearing at 10 m) each is chosen as any parameter is, the standard height
       first. That is the one case in which a bearing stands beside a speed of another height, and it is served so
       that no bearing is lost.

    The speed and the direction are in the frame whatever was asked for, the dataset being read whole, so the speed of
    a request for the speed alone is the speed of the pair too: it is the same for an hour in every request. The two
    readers that read a parameter by itself (after a 404 of the whole dataset, where no data was found) have no pair to
    see, and choose the speed, or the direction, as any other parameter. The gust is no part of the pair.

    A parameter that is not in `_STANDARD_HEIGHT`, and a frame without `_LEVEL`, are as they were.
    """
    if _LEVEL not in df.columns or df.is_empty():
        return df
    keys = ["parameter", "timestamp"]
    answered = pl.col("value").is_not_null()
    distance = (pl.col(_HEIGHT) - pl.col(_STANDARD)).abs().fill_null(float("inf"))
    nearest = pl.when(answered).then(distance).min().over(keys)
    df = df.with_columns(
        pl.col("parameter")
        .str.extract(_BASE_NAME, 1)
        .replace_strict(_STANDARD_HEIGHT, default=None, return_dtype=pl.Float64)
        .alias(_STANDARD),
        pl.col(_LEVEL).cast(pl.Float64, strict=False).alias(_HEIGHT),
    ).with_columns(
        pl.when(answered & (distance == nearest)).then(pl.col(_HEIGHT)).min().over(keys).alias("__chosen"),
        answered.any().over(keys).alias("__answered"),
    )
    # the heights that have both a speed and a direction at a time, and the one of them that is the pair's
    is_speed = pl.col("parameter") == _WIND_SPEED
    is_direction = pl.col("parameter") == _WIND_DIRECTION
    at_height = ["timestamp", _HEIGHT]
    both = (
        (is_speed | is_direction)
        & (is_speed & answered).any().over(at_height)
        & (is_direction & answered).any().over(at_height)
    )
    nearest_pair = pl.when(both).then(distance).min().over("timestamp")
    df = df.with_columns(
        both.any().over("timestamp").alias("__paired"),
        pl.when(both & (distance == nearest_pair)).then(pl.col(_HEIGHT)).min().over("timestamp").alias("__pair"),
    )
    paired = (is_speed | is_direction) & pl.col("__paired")
    wanted = pl.when(paired).then(pl.col("__pair")).otherwise(pl.col("__chosen"))
    decided = pl.col(_STANDARD).is_not_null() & (paired | pl.col("__answered"))
    return df.filter(~decided | pl.col(_HEIGHT).eq_missing(wanted)).drop(
        _HEIGHT, _STANDARD, "__chosen", "__answered", "__paired", "__pair"
    )


def _decode_sentinels(df: pl.DataFrame, station_id: str | None = None) -> pl.DataFrame:
    """Turn Frost's in-band codes into the value they stand for, before anything reads them.

    The code stays beside the value as the last token of `quality_flags`, `0,raw:-1`, written as Frost documents the
    code: the value is a JSON number, so its text is not at hand (GH-2759). A wind direction of 0 beside a wind speed
    of 0 of the same time and height is a calm, and null with `raw:0`; where the frame has no speed it stays (GH-3833).

    ``station_id`` is the station the rows are of. It matters for one code: the daily precipitation `-1` is 0.0, but the
    one of a weekly reader's unread days (`_UNREAD_DAYS_THROUGH`) is null (GH-3820).
    """
    _precipitation = pl.col("parameter").is_in(_PRECIPITATION_SUMS)
    _year = pl.col("timestamp").dt.year()
    _daily_sum = pl.col("parameter") == _DAILY_PRECIPITATION_SUM
    unread_through = _UNREAD_DAYS_THROUGH.get(station_id or "")
    _unread = _daily_sum & (_year <= unread_through) if unread_through is not None else pl.lit(value=False)
    df = with_speed_beside(
        df, {_WIND_DIRECTION: _WIND_SPEED}, on=["timestamp", _LEVEL] if _LEVEL in df.columns else ["timestamp"]
    )
    value, raw = null_sentinels(
        pl.col("value"),
        Sentinel(_NO_SNOW, where=pl.col("parameter") == _SNOW_DEPTH, to=0.0),
        Sentinel(_NO_PRECIPITATION, where=_precipitation & (_year >= _NO_PRECIPITATION_FROM_YEAR), to=0.0),
        Sentinel(_NO_PRECIPITATION, where=_precipitation & (_year < _NO_PRECIPITATION_FROM_YEAR)),
        # the first that matches decides: the unread days of a weekly reader are null, the rest of the daily sum 0.0
        Sentinel(_NO_PRECIPITATION, where=_unread),
        Sentinel(_NO_PRECIPITATION, where=_daily_sum, to=0.0),
        Sentinel(*_CLOUD_COVER_NOT_ESTIMATED, where=pl.col("parameter") == _CLOUD_COVER),
        Sentinel(_NOT_GIVEN, where=pl.col("parameter").is_in([_WIND_DIRECTION, _SNOW_DEPTH])),
        calm(pl.col(SPEED_BESIDE), where=pl.col("parameter") == _WIND_DIRECTION),
        text=False,
    )
    quality = pl.col("quality_flags") if "quality_flags" in df.columns else None
    # a value of a window that had not closed (`_read_observations`) is incomplete; none that has is marked as complete
    incomplete = (
        pl.when(pl.col(_OPEN)).then(pl.lit(_INCOMPLETE)) if _OPEN in df.columns else pl.lit(None, dtype=pl.String)
    )
    decoded = df.with_columns(value.alias("value"), join_quality_flags(quality, completeness=incomplete, raw=raw))
    return decoded.drop(SPEED_BESIDE, _LEVEL, _OPEN, strict=False)


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
        asked_at = _now()
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
        read = _read_observations(
            df,
            pl.col("elementId"),
            dataset.resolution.name,
            station_id,
            _served_at(file, asked_at),
            estimate=self._left_out_of_estimate is not None,
        )
        # the batch holds the whole dataset: what is told is of the parameters asked for
        asked = {
            parameter.name_original: _full_name(parameter)
            for parameter in self.sr.parameters
            if (parameter.dataset.resolution.name, parameter.dataset.name) == (dataset.resolution.name, dataset.name)
        }
        _tell_not_returned(
            read,
            read.frame,
            asked,
            start_date,
            end_date,
            dataset.resolution.name,
            estimate=self._left_out_of_estimate is not None,
        )
        return read.frame

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
        asked_at = _now()
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
        read = _read_observations(
            df,
            pl.lit(parameter.name_original, dtype=pl.String),
            parameter.dataset.resolution.name,
            station_id,
            _served_at(file, asked_at),
            estimate=self._left_out_of_estimate is not None,
        )
        _tell_not_returned(
            read,
            read.frame,
            {parameter.name_original: _full_name(parameter)},
            start_date,
            end_date,
            parameter.dataset.resolution.name,
            estimate=self._left_out_of_estimate is not None,
        )
        return read.frame

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
        left_outs = []
        open_windows = []
        asked: set[str] = set()
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
            # the series of one element that differ in `timeOffset` only are listed apart and have one `timeseriesids`:
            # their query is the same where their validity is, and answers the rows of every offset (GH-3832)
            if obs_url in asked:
                continue
            asked.add(obs_url)
            log.info(f"Acquiring data from {obs_url}")
            asked_at = _now()
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
            read = _read_observations(
                df,
                pl.lit(element, dtype=pl.String),
                resolution_name,
                station_id,
                _served_at(obs_file, asked_at),
                estimate=self._left_out_of_estimate is not None,
            )
            left_outs.append(read.left_out)
            open_windows.append(read.open_window)
            if not read.frame.is_empty():
                frames.append(read.frame)

        kept = pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame()
        # the series of one station are read apart: a `-1` of one can come first to a reading of another (idempotent)
        if not kept.is_empty():
            kept = _a_reading_beats_a_minus_one(kept)
        # a date is left out when no series of the station returned it
        read = _Read(
            kept,
            pl.concat([frame for frame in left_outs if not frame.is_empty()] or [pl.DataFrame()]).unique(),
            pl.concat(open_windows).group_by("parameter", "timestamp").agg(pl.col("closes").min())
            if open_windows
            else _no_open_window(),
        )
        _tell_not_returned(
            read,
            kept,
            {element: _full_name(parameter_or_dataset)},
            start_date,
            end_date,
            resolution_name,
            estimate=self._left_out_of_estimate is not None,
        )
        return kept


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


def _listing_rows(file: File, settings: Settings, ttl: CacheExpiry, client_kwargs: dict) -> pl.DataFrame:
    """Give the rows of `data` of a listing that Frost answered with a 200, and drop it from the cache if it is none.

    A body that is no JSON (a page of a proxy or a CDN) or has no `data` is a `DownloadError`, which names the file and
    has the polars error as its cause. Either is dropped from the cache first, as `download_file` holds a 200 for the
    whole `ttl`, and the next request would read the same page back for hours. A listing with no row is returned as
    an empty frame, which the caller decides on (and drops, for the cache holds that for as long).
    """
    try:
        listing = pl.read_json(cast("BytesIO", file.content))
    except pl.exceptions.PolarsError as error:
        _drop_listing(file, settings, ttl, client_kwargs)
        msg = "the answer is not a JSON listing"
        raise DownloadError(file.url.split("?", maxsplit=1)[0], msg) from error
    if "data" not in listing.columns:
        _drop_listing(file, settings, ttl, client_kwargs)
        msg = "the answer has no `data`"
        raise DownloadError(file.url.split("?", maxsplit=1)[0], msg)
    return listing.select(pl.col("data").explode(empty_as_null=True)).drop_nulls()


def _drop_listing(file: File, settings: Settings, ttl: CacheExpiry, client_kwargs: dict) -> None:
    """Drop the cached copy of a listing that is no good, with the arguments it was downloaded with."""
    drop_cached_file(
        file.url,
        settings.cache_dir,
        ttl,
        client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )


class MetnoFrostRequest(TimeseriesRequest):
    """Request class for MET Norway Frost API."""

    metadata = MetnoFrostMetadata
    _values = MetnoFrostValues

    # `validtime` makes the list hold the stations that are closed as well: without it Frost answers the stations valid
    # now only (2,234 of the 4,179 on 2026-11-07), and `ids=` of a closed station is a 404 either way (GH-3847)
    _sources_url = (
        "https://frost.met.no/sources/v0.jsonld?types=SensorSystem&validtime=1700-01-01/now"
        "&fields=id,name,validFrom,validTo,geometry,county,countryCode,masl"
    )
    # the series Frost lists for the elements and resolutions the network declares: one request for every station,
    # 71,363 rows and 13.2 MB on 2026-11-07, about 30 s of which the server computes 8 and does not compress
    _series_url = (
        "https://frost.met.no/observations/availableTimeSeries/v0.jsonld"
        "?elements={elements}&timeresolutions={time_resolutions}&fields=sourceId,validFrom,validTo,timeResolution,elementId"
    )

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

    def _stations_to_search(self, df_all: pl.DataFrame) -> pl.DataFrame:
        """Narrow a search by place to the stations with a record in the window, where there is one (GH-3847).

        The end of a station is that of its last declared series, which Frost sets once every one of them has closed:
        it does not lag a station that is still reporting (that one has no end), so a station that ended before the
        window is neither counted nor asked for. Without it a request by distance or box counted the 78 closed stations
        of 25 km around Oslo against `WD_RESTAPI_MAX_STATIONS`, and a rank asked each closed station before the first in
        service three times. Without a window the whole list is searched, closed stations included. A search by id,
        by name (which applies the window itself) or by SQL is not narrowed.
        """
        from wetterdienst.model.request import limit_to_window  # noqa: PLC0415

        return limit_to_window(
            df_all,
            cast("datetime | None", self.start),
            cast("datetime | None", self.end),
            cast("Options", self.options).station_window_end_buffer,
        )

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

        df = _listing_rows(file, settings, CacheExpiry.METAINDEX, client_kwargs)
        if df.is_empty():
            # `{"data": []}` is a list without a source, a column of nulls that cannot be unnested. Frost has 4,179, so
            # it is not kept for twelve hours as the network without a station it would read as
            _drop_listing(file, settings, CacheExpiry.METAINDEX, client_kwargs)
            return pl.LazyFrame()
        df = df.unnest("data")
        # geometry.coordinates: [longitude, latitude, elevation?]. 52 of the 4179 sources (2026-11-07) have
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
            pl.col("validFrom").str.to_datetime(format=_FROST_STAMP, time_unit="us").alias("_source_from"),
            # a station still in service has no validTo, which parses to null
            pl.col("validTo").str.to_datetime(format=_FROST_STAMP, time_unit="us").alias("_source_to"),
        )
        df = self._with_series_bounds(df.rename({"id": "station_id"}), settings, client_kwargs)
        df = df.rename({"name": "name", "county": "region", "countryCode": "country"})
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

    def _with_series_bounds(self, df: pl.DataFrame, settings: Settings, client_kwargs: dict) -> pl.DataFrame:
        """Give each station the start and the end of its declared series (GH-3864, GH-3847).

        The source's own `validFrom` and `validTo` are not the span of the data: data begins before `validFrom` at
        about one station in ten (SN99700, 1895-07-07 against a source from 1956), and the source's end is earlier
        than the latest series' end at 1,156 of 1,868 stations. The span of the series the network declares is read
        from one request, listing them for every station:

        - `start_timestamp` is the earlier of the source's `validFrom` and the earliest `validFrom` of a declared
          series;
        - `end_timestamp` is the latest `validTo` of a declared series, and null if any declared series is open.

        A station with no declared series keeps the span the source gives it. A series of a station that is no source
        of the list (58 on 2026-11-07) is dropped with it. The listing is asked as the catalogue is (kept for a week,
        `_SERIES_EXPIRY`), and its failure is raised as the catalogue's is: read as no series, every station would keep
        the source's span and the catalogue would be wrong without a word.
        """
        declared = [
            (parameter.name_original, resolution.name_original)
            for resolution in self.metadata
            for dataset in resolution.datasets
            for parameter in dataset.parameters
        ]
        elements = sorted({element for element, _ in declared})
        resolutions = sorted({resolution for _, resolution in declared})
        url = self._series_url.format(
            elements=quote(",".join(elements), safe=",()"),
            time_resolutions=",".join(resolutions),
        )
        # the answer takes about 30 s: a stall of the default 30 s between two reads is not an outage
        timeout = client_kwargs.get("timeout")
        series_kwargs = (
            {**client_kwargs, "timeout": _SERIES_TIMEOUT}
            if isinstance(timeout, int | float) and timeout < _SERIES_TIMEOUT
            else client_kwargs
        )
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=_SERIES_EXPIRY,
            client_kwargs=series_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        _raise_if_rejected(file)
        file.raise_if_exception()
        series = _listing_rows(file, settings, _SERIES_EXPIRY, series_kwargs)
        if series.is_empty():
            # the sources of the list are there, so series are: an answer without any is not a station without data,
            # and is not kept for a week
            _drop_listing(file, settings, _SERIES_EXPIRY, series_kwargs)
            msg = "Frost listed no time series for the elements the network declares"
            raise DownloadError(url.split("?", maxsplit=1)[0], msg)
        series = series.unnest("data")
        if "validTo" not in series.columns:
            series = series.with_columns(pl.lit(None, dtype=pl.String).alias("validTo"))
        pairs = pl.DataFrame(declared, schema={"elementId": pl.String, "timeResolution": pl.String}, orient="row")
        series = (
            series.join(pairs, on=["elementId", "timeResolution"], how="semi")
            .with_columns(
                pl.col("validFrom").str.to_datetime(format=_FROST_STAMP, time_unit="us").alias("_series_from"),
                pl.col("validTo").str.to_datetime(format=_FROST_STAMP, time_unit="us").alias("_series_to"),
            )
            # the listing names a series by its sensor system: `SN99700:0`, the station `SN99700`
            .with_columns(pl.col("sourceId").str.split(":").list.first().alias("sourceId"))
            .group_by("sourceId")
            .agg(
                pl.col("_series_from").min(),
                # open if any series is open
                pl.when(pl.col("_series_to").null_count() > 0)
                .then(None)
                .otherwise(pl.col("_series_to").max())
                .alias("_series_to"),
                pl.lit(value=True).alias("_has_series"),
            )
            .rename({"sourceId": "station_id"})
        )
        df = df.join(series, on="station_id", how="left", maintain_order="left")
        return df.with_columns(
            pl.min_horizontal("_source_from", "_series_from").alias("start_timestamp"),
            pl.when(pl.col("_has_series").fill_null(value=False))
            .then(pl.col("_series_to"))
            .otherwise(pl.col("_source_to"))
            .alias("end_timestamp"),
        )
