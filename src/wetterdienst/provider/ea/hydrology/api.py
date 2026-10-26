# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Environment Agency hydrology API."""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution, count_readings
from wetterdienst.model.metadata import (
    DATASET_NAME_DEFAULT,
    OGL_UK_3_0,
    ParameterModel,
    build_metadata_model,
)
from wetterdienst.model.quality_flags import join_quality_flags
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.util.network import download_file, fetchable_link

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

# the listing answers with a page of 100 stations unless asked for more, and gives 9537 (2026-10-15)
_STATIONS_LIMIT = 20_000


_EAHydrologyMetadataSpec = {
    "name_short": "EA",
    "name_english": "Environment Agency",
    "name_local": "Environment Agency",
    "country": "United Kingdom",
    "country_code": "GB",
    "copyright": "© Environment Agency of UK",
    "license": OGL_UK_3_0,
    "attribution": "Environment Agency",
    "url": "https://environment.data.gov.uk/",
    "kind": "observation",
    "extent": {
        "scope": "national",
        "continents": ["europe"],
        "countries": ["GB"],
        "bbox": [-6.0, 49.8, 2.0, 55.9],
    },
    "timezone": "Europe/London",
    "resolutions": [
        {
            "name": "15_minutes",
            "name_original": "15_minutes",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "discharge",
                            "name_original": "flow-i-900",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "stage",
                            "name_original": "level-i-900",
                            "unit": "meter",
                        },
                        {
                            "name": "groundwater_level",
                            "name_original": "gw-logged-i-subdaily",
                            "unit": "meter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "daily",
            "name_original": "daily",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "periods": ["historical"],
                    "parameters": [
                        {
                            "name": "discharge_max",
                            "name_original": "flow-max-86400",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "discharge_mean",
                            "name_original": "flow-m-86400",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "discharge_min",
                            "name_original": "flow-min-86400",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "stage_max",
                            "name_original": "level-max-86400",
                            "unit": "meter",
                        },
                        {
                            "name": "stage_min",
                            "name_original": "level-min-86400",
                            "unit": "meter",
                        },
                    ],
                },
            ],
        },
    ],
}
EAHydrologyMetadata = build_metadata_model(_EAHydrologyMetadataSpec, "EAHydrologyMetadata")


# a measure is notated `{parameter}-{statistic}-{period}`, so `flow-i-900` is the flow measured every 900 seconds and
# `level-max-86400` the daily maximum level. The groundwater logger is the one notation that spells its period out
# (`gw-logged-i-subdaily`), and the station endpoints call that period 900 seconds. The notation, not
# the `parameter` the listing names, tells what a measure is: the listing calls the level of a river and the level
# of the groundwater table both `level`, with the same period of 900, and only the measure id sets them apart (GH-2632).
_NOTATION_PERIODS = {"subdaily": "900"}


def _measure_period(parameter: ParameterModel) -> str:
    """Give the period, in seconds, of the measure a wetterdienst parameter is taken from."""
    token = parameter.name_original.split("-")[-1]
    return _NOTATION_PERIODS.get(token, token)


def _measure_id_contains(notation: str) -> pl.Expr:
    """Select the measure ids that carry a notation, which sits between the station's id and the unit."""
    return pl.col("@id").str.contains(f"-{notation}-", literal=True)


# the period of each measure, in seconds, and the resolution it is served under. Read off the
# trailing token of the notations the metadata declares, so a resolution added there is served
# without a second table having to learn its period.
_RESOLUTIONS_BY_PERIOD: dict[str, str] = {
    _measure_period(parameter): resolution.name
    for resolution in EAHydrologyMetadata
    for dataset in resolution
    for parameter in dataset.parameters
}


# the readings endpoint answers an unbounded request with a default page of 100_000 readings,
# oldest first, and says nothing about having stopped there. Daily never reaches it -- 100_000
# daily readings is 274 years -- but 15-minute readings run out after some 2.8 years, so an
# unbounded request answered every recent window with the readings of 2008 to 2011 and the
# post-filter then dropped every one of them. The window is asked for instead, and, for the
# resolutions that need it, the page raised to the number of readings that window can hold, so
# neither end is silently cut. Daily is left on the default page (see `_readings_url`).
_READINGS_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
# the endpoint reports its timestamps without a zone and they are read as UTC below. A day either
# side keeps that assumption from costing the edges of the window, which the caller trims anyway.
_READINGS_MARGIN = dt.timedelta(days=1)
# a daily value of the day D covers the 24 h from D 09:00 to D+1 09:00 and is dated inside them, so the readings of
# the last day of a window are dated up to 09:00 of the day after the window's end (GH-2683)
_DAILY_DAY_START = dt.timedelta(hours=9)


class EAHydrologyValues(TimeseriesValues[ParameterModel]):
    """Values class for Environment Agency hydrology data."""

    _url = "https://environment.data.gov.uk/hydrology/id/stations/{station_id}.json"

    def _readings_url(self, measure_url: str, parameter: ParameterModel) -> str:
        """Give the readings URL of a measure, bounded by the window the request asks for."""
        url = f"{measure_url}/readings.json"
        if not self.sr.start or not self.sr.end:
            return url
        start_date = self.sr.start - _READINGS_MARGIN
        end_date = self.sr.end + _READINGS_MARGIN
        daily = parameter.dataset.resolution.value == Resolution.DAILY
        if daily:
            end_date += _DAILY_DAY_START
        query: dict[str, str | int] = {
            "mineq-dateTime": start_date.strftime(_READINGS_DATETIME_FORMAT),
            "maxeq-dateTime": end_date.strftime(_READINGS_DATETIME_FORMAT),
        }
        # a daily window holds more readings than days -- the maximum and minimum are dated at their instant
        # and the endpoint answers a window twice at times -- so the count of days would cut the newest
        # readings (GH-2732). It is left to the default page of 100_000 readings, which a daily window never fills
        limit = None if daily else count_readings(parameter.dataset.resolution.value, start_date, end_date)
        if limit:
            query["_limit"] = limit
        return f"{url}?{urlencode(query)}"

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        """Collect data for a station, parameter or dataset."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.sr.request.settings)
        url = self._url.format(station_id=station_id)
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.NO_CACHE,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.DataFrame()
        df_measures = pl.read_json(
            file.content,
            schema={
                "items": pl.List(
                    pl.Struct(
                        {
                            "measures": pl.List(
                                pl.Struct(
                                    {
                                        "parameterName": pl.String,
                                        "parameter": pl.String,
                                        "period": pl.Int64,
                                        "@id": pl.String,
                                    },
                                ),
                            ),
                        },
                    ),
                ),
            },
        )
        df_measures = df_measures.explode("items", empty_as_null=True)
        df_measures = df_measures.select(pl.col("items").struct.field("measures"))
        df_measures = df_measures.explode("measures", empty_as_null=True)
        df_measures = df_measures.select(pl.col("measures").struct.unnest())
        df_measures = df_measures.with_columns(
            pl.col("period").cast(pl.String).replace(_RESOLUTIONS_BY_PERIOD).alias("resolution"),
        )
        df_measures = df_measures.filter(
            pl.col("resolution").eq(parameter_or_dataset.dataset.resolution.name)
            & _measure_id_contains(parameter_or_dataset.name_original),
        )
        try:
            readings_id_url = df_measures.get_column("@id")[0]
        except IndexError:
            return pl.DataFrame()
        # the `@id` is the answer's to name: read at the API's own host, and over https where it is written as
        # `http`, which it is (GH-3339)
        readings_id_url = fetchable_link(readings_id_url, url)
        readings_url = self._readings_url(readings_id_url, parameter_or_dataset)
        file = download_file(
            url=readings_url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.DataFrame()
        df = pl.read_json(
            file.content,
            schema={
                "items": pl.List(
                    pl.Struct(
                        {
                            "dateTime": pl.String,
                            "value": pl.Float64,
                            "quality": pl.String,
                            "completeness": pl.String,
                        },
                    ),
                ),
            },
        )
        df = df.explode("items", empty_as_null=True)
        df = df.select(pl.col("items").struct.unnest())
        timestamp = pl.col("dateTime").str.to_datetime(format="%Y-%m-%dT%H:%M:%S", time_zone="UTC")
        if parameter_or_dataset.dataset.resolution.value == Resolution.DAILY:
            # A daily value covers the 24 h from 09:00 of the day D it names to 09:00 of D+1. The mean is dated at
            # D 09:00, but the maximum and minimum are dated at the instant of the extreme inside that window, and
            # so are filed under D by taking the day from 9 hours earlier. It is stamped at 00:00 UTC of D, which a
            # request for that one day reaches (GH-2683).
            timestamp = (timestamp - _DAILY_DAY_START).dt.truncate("1d")
            # The endpoint sometimes answers a window twice, with an unchecked or incomplete reading (or a null with
            # the quality Missing) beside the complete one, and the two have the same stamp now. The one with a value
            # is kept, then the complete one, then the one of quality Good, and of equal standing the later one.
            df = (
                df.with_columns(timestamp.alias("day"))
                .sort(
                    "day",
                    pl.col("value").is_null(),
                    pl.col("completeness").ne("Complete").fill_null(value=True),
                    pl.col("quality").ne("Good").fill_null(value=True),
                    "dateTime",
                    descending=[False, False, False, False, True],
                )
                .unique(subset="day", keep="first", maintain_order=True)
            )
            timestamp = pl.col("day")
        return df.select(
            pl.lit(parameter_or_dataset.name_original).alias("parameter"),
            timestamp.alias("timestamp"),
            pl.col("value"),
            # the reading's own "quality" word (Good, Estimated, Suspect, Unchecked, Missing), verbatim (GH-2018),
            # then, where the endpoint gives one, its "completeness" (Complete, Incomplete): whether the value is
            # based on complete data, which says how much of the day a daily value covers (GH-2762)
            join_quality_flags(pl.col("quality"), completeness=pl.col("completeness")),
        )


def _station_row(item: dict[str, Any]) -> dict[str, Any]:
    """Give the fields of one station of the listing that the reader keeps, each as a scalar.

    A field the listing holds more than once for a station is an array there: `label` for a station with two
    spellings of its name, `dateClosed` for one that closed twice (GH-2933). The first label is taken, the first
    spelling the listing gives. The latest `dateClosed` is taken, for the station reported until then.
    """
    label = item.get("label")
    if isinstance(label, list):
        label = label[0] if label else None
    closed = item.get("dateClosed")
    if isinstance(closed, list):
        closed = max(closed, default=None)
    return {
        "label": label,
        "notation": item.get("notation"),
        "lat": item.get("lat"),
        "long": item.get("long"),
        "dateOpened": item.get("dateOpened"),
        "dateClosed": closed,
        "measures": [
            {"@id": measure.get("@id"), "period": measure.get("period")} for measure in item.get("measures") or []
        ],
    }


@dataclass
class EAHydrologyRequest(TimeseriesRequest):
    """Request class for Environment Agency hydrology data."""

    metadata = EAHydrologyMetadata
    _values = EAHydrologyValues

    _url = "https://environment.data.gov.uk/hydrology/id/stations.json"

    def _all(self) -> pl.LazyFrame:
        """Acquire all stations and filter for stations that have wanted resolution and parameter combinations."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        file = download_file(
            url=f"{self._url}?{urlencode({'_limit': _STATIONS_LIMIT})}",
            cache_dir=settings.cache_dir,
            # the whole listing is 17 MB, and the stations of the Environment Agency change on the scale of days
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        listing = json.load(file.content)
        items = listing["items"]
        # the endpoint does not say that it stopped at the limit, and `meta.limit` is the one it applied (GH-2933)
        limit = min(_STATIONS_LIMIT, listing.get("meta", {}).get("limit") or _STATIONS_LIMIT)
        if len(items) >= limit:
            log.warning("The EA hydrology station listing holds %d stations, the page limit: it may be cut", len(items))
        df = pl.DataFrame(
            [_station_row(item) for item in items],
            schema={
                "label": pl.String,
                "notation": pl.String,
                "lat": pl.Float64,
                "long": pl.Float64,
                "dateOpened": pl.String,
                "dateClosed": pl.String,
                "measures": pl.List(pl.Struct({"@id": pl.String, "period": pl.Int64})),
            },
        )
        df = df.lazy()
        df = df.explode("measures", empty_as_null=True)
        df = df.with_columns(pl.col("measures").struct.unnest())
        df = df.rename(
            mapping={
                "label": "name",
                "lat": "latitude",
                "long": "longitude",
                "notation": "station_id",
                "dateOpened": "start_timestamp",
                "dateClosed": "end_timestamp",
                "period": "resolution",
            },
        )
        df = df.with_columns(
            pl.col("resolution").cast(pl.String).replace(_RESOLUTIONS_BY_PERIOD),
        )
        df = df.drop_nulls("resolution")
        requested = [parameter for parameter in self.parameters if isinstance(parameter, ParameterModel)]
        result = df.collect(background=False)
        if not isinstance(result, pl.DataFrame):
            msg = "Expected DataFrame, got InProcessQuery"
            raise TypeError(msg)
        # by the measure id, which names the notation of each parameter asked for: the `parameter` of the listing would
        # list a station that measures the level of a river for the groundwater level, and the other way round
        df = result.filter(
            pl.any_horizontal(
                [
                    pl.col("resolution").eq(parameter.dataset.resolution.name)
                    & _measure_id_contains(parameter.name_original)
                    for parameter in requested
                ],
            ),
        )
        df = df.lazy()
        df = df.select(
            "resolution",
            pl.lit(DATASET_NAME_DEFAULT, dtype=pl.String).alias("dataset"),
            "station_id",
            pl.col("start_timestamp").str.to_datetime(format="%Y-%m-%d"),
            pl.col("end_timestamp").str.to_datetime(format="%Y-%m-%d"),
            "latitude",
            "longitude",
            "name",
        )
        # the listing carries one row per measure, so a station recording two of the requested
        # parameters (or the daily maximum and minimum) arrives once per measure. Left in, the
        # duplicates make `filter_by_rank` answer with more stations than were asked for
        return df.unique(subset=["resolution", "dataset", "station_id"], keep="first", maintain_order=True)
