# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""NWS observation provider."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from urllib.parse import urlencode

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, DatasetModel, LicenseModel, build_metadata_model
from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.util.network import download_file
from wetterdienst.util.polars_util import read_csv_without_header

if TYPE_CHECKING:
    from io import IOBase

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

# A calm wind is written `00000KT` in a METAR and reaches the endpoint as a direction of 0. The National Weather
# Service's METAR decode key (weather.gov/media/wrh/mesowest/metar_decode_key.pdf) gives "00000KT for calm" and the
# direction "from true north", so north is 360. In the last 500 observations of each of KDEN, KSEA, KPHX, KBOS, KMIA,
# KORD and KJFK (read 2026-10-12) all 322 observations with a direction of 0 have a wind speed of 0, 76 have a
# direction of 360, and a `VRB` wind has no direction at all (null). A calm wind has no direction, so the 0 is no
# bearing (GH-2794).
_CALM_WIND = Sentinel("0", where=pl.col("parameter").eq("winddirection"))

# The endpoint serves every observation it holds, about 12 an hour: the 5-minute ASOS rows (minutes 0, 5, 10, ...; whole
# degrees Celsius, no sea level pressure, no precipitation) and beside them the routine METAR, one an hour at a minute
# of the station's own (:54 at KBOS, :53 at KDEN, :51 at KORD), and the SPECI and other reports filed between (GH-2857).
# `hourly` keeps one of them per hour (`_one_report_per_hour`). A METAR or SPECI is told from a 5-minute row by the
# `precipitationLastHour` key, the precipitation group of the METAR code: the endpoint leaves it out of every 5-minute
# row and carries it in every report. Of the last 500 observations of KBOS, KDEN, KSEA, KMIA, KORD, KJFK, PANC, PHNL,
# KFOE and KLAX (read 2026-10-15) 4,056 rows lack the key, all of them on the 5-minute grid and none with a
# `rawMessage`, and 618 carry it. The text of the report is no marker: 151 of those 618 (10 to 33 % per station) have
# an empty `rawMessage`, and are reports all the same (SLP, tenths of a degree). Read into a struct, a key the endpoint
# leaves out is a null struct.
_REPORT_MARKER = "precipitationlasthour"
# The endpoint answers at most 500 observations to a request, newest first, and names the rest in `pagination.next`, a
# cursor URL that carries the stamp of the oldest row returned and walks backwards: KBOS, a window of 5 days (read
# 2026-10-17), pages of 500 rows from 2026-10-17T13:50 to 2026-10-15T21:10, to 2026-10-14T04:50, to 2026-10-12T12:50 and
# to 2026-10-10T20:05, then 81 rows to 2026-10-10T13:20, the end of the week it keeps. Each page ends where the next
# begins, five minutes later in the past. A page that holds fewer rows than the limit is the last one though it names a
# `next` as well, and a window of three hours, 34 rows, does: that cursor alone walks out of the window (500 rows older
# than its `start`), where the cursor with the `start` of the window answers with none. The `start` is honoured with a
# cursor, an `end` is not (GH-2994).
_PAGE_SIZE = 500
# a report belongs to the full hour it is nearest to, so an hour reaches half an hour to either side of its full hour
_HALF_HOUR = dt.timedelta(minutes=30)

_NwsObservationMetadataSpec = {
    "name_short": "NWS",
    "name_english": "NOAA National Weather Service",
    "name_local": "NOAA National Weather Service",
    "country": "United States Of America",
    "country_code": "US",
    "copyright": "© NOAA NWS (National Weather Service), Observations",
    "license": LicenseModel(
        spdx_id=None,
        name="Open data, free to use for any purpose (NWS API documentation)",
        url="https://www.weather.gov/documentation/services-web-api",
    ),
    "attribution": None,
    "url": "https://api.weather.gov/",
    "kind": "observation",
    "timezone": "America/New_York",
    "resolutions": [
        {
            "name": "hourly",
            "name_original": "hourly",
            "periods": ["recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_2m",
                            "name_original": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_2m",
                            "name_original": "dewpoint",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_direction_mean_last_2min",
                            "name_original": "winddirection",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_speed_mean_last_2min",
                            "name_original": "windspeed",
                            "unit": "kilometer_per_hour",
                        },
                        {
                            "name": "wind_gust_max_last_10min",
                            "name_original": "windgust",
                            "unit": "kilometer_per_hour",
                        },
                        {
                            "name": "pressure_air_site_reduced",
                            "name_original": "barometricpressure",
                            "unit": "pascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "sealevelpressure",
                            "unit": "pascal",
                        },
                        {
                            "name": "visibility",
                            "name_original": "visibility",
                            "unit": "meter",
                        },
                        {
                            "name": "temperature_air_max_2m_last_24h",
                            "name_original": "maxtemperaturelast24hours",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m_last_24h",
                            "name_original": "mintemperaturelast24hours",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_amount_since_last_routine_report",
                            "name_original": "precipitationlasthour",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_amount_last_3h",
                            "name_original": "precipitationlast3hours",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_amount_last_6h",
                            "name_original": "precipitationlast6hours",
                            "unit": "millimeter",
                        },
                        {
                            "name": "humidity_relative",
                            "name_original": "relativehumidity",
                            "unit": "percent",
                        },
                        {
                            "name": "temperature_wind_chill",
                            "name_original": "windchill",
                            "unit": "degree_celsius",
                        },
                    ],
                },
            ],
        },
    ],
}
NwsObservationMetadata = build_metadata_model(_NwsObservationMetadataSpec, "NwsObservationMetadata")


def _quantity(dtype: pl.DataType | type[pl.DataType]) -> pl.Struct:
    """Give the schema of an observation's quantity: its value and the MADIS quality control flag it carries."""
    return pl.Struct([pl.Field("value", dtype), pl.Field("qualityControl", pl.String)])


def _one_report_per_hour(df: pl.DataFrame) -> pl.DataFrame:
    """Keep one observation for each full hour, the report nearest to it (GH-2857).

    An observation belongs to the full hour it is nearest to (14:53 to 15:00, 14:20 to 14:00; 14:30 to 15:00). Of an
    hour's observations the one kept is, in this order:

    1. a report (METAR or SPECI, see `_REPORT_MARKER`) rather than a 5-minute ASOS row, because the 5-minute row at
       the full hour is the nearer one and a poorer reading: whole degrees, no sea level pressure, no precipitation;
    2. the one nearest to the full hour, which is the routine METAR at :51 to :54 unless a SPECI was filed closer;
    3. the earlier of two at the same distance, 14:57 over 15:03.

    The kept row is stamped with the full hour (15:00 for the METAR of 14:54), as DWD and ECCC stamp their hourly
    readings, the instant ones among them (DWD's are those of about ten minutes before the stamp, as a METAR at :51
    to :54 is). On the full-hour grid that `interpolate` and `summarize` join on, a row at :54 would count for
    nothing, and `skip_empty` counts the rows of an hour by its truncated hour. Hours with no report at all keep the
    nearest 5-minute row. The result holds at most one row for each full hour, and for a day of 5-minute rows with
    one METAR an hour 24 rows.
    """
    timestamp = pl.col("timestamp")
    hour = (timestamp + _HALF_HOUR).dt.truncate("1h")
    return (
        df.with_columns(
            hour.alias("_hour"),
            pl.col(_REPORT_MARKER).is_not_null().alias("_report"),
            (timestamp - hour).dt.total_microseconds().abs().alias("_distance"),
        )
        .sort(
            ["_report", "_distance", "timestamp"],
            descending=[True, False, False],
            nulls_last=True,
            maintain_order=True,
        )
        .unique(subset="_hour", keep="first", maintain_order=True)
        .with_columns(pl.col("_hour").alias("timestamp"))
        .drop("_hour", "_report", "_distance")
    )


class NwsObservationValues(TimeseriesValues[DatasetModel]):
    """Values class for NWS observation."""

    _endpoint = "https://api.weather.gov/stations/{station_id}/observations"
    # the API answers ISO 8601 instants and reads them back the same way
    _date_format = "%Y-%m-%dT%H:%M:%SZ"

    def _build_url(self, station_id: str) -> str:
        """Address the observations of a station, narrowed to the window the request asked for.

        Asked for nothing in particular the endpoint answers with its whole retention, which is a
        rolling week of some 2,000 readings -- 2 MB for each page of 500, to answer for a single day. It
        clips a window to what it still holds rather than refusing one that reaches further back,
        so naming the request's own window costs nothing and returns the same readings. The window is
        widened by half an hour on both sides, the reach of an hour's reports, so that which report an
        hour at the edge of the window keeps does not depend on where the window is cut. What lies
        outside the request's own window is cut away after the hours have been decided.

        A request carries no dates unless it is made to: `date_required` is enforced at the CLI and
        the REST API but not in the Python API, and without them there is no window to name.

        The endpoint answers 500 observations at most, and the limit is named so that a page shorter than it
        can be taken for the last one (GH-2994).
        """
        url = self._endpoint.format(station_id=station_id)
        if not self.sr.start or not self.sr.end:
            return f"{url}?{urlencode({'limit': _PAGE_SIZE})}"
        query = urlencode(
            {
                "start": self._window_start().strftime(self._date_format),
                "end": (self.sr.end + _HALF_HOUR).strftime(self._date_format),
                "limit": _PAGE_SIZE,
            },
        )
        return f"{url}?{query}"

    def _window_start(self) -> dt.datetime:
        """Give the first instant the endpoint is asked for, half an hour before the request's own."""
        return cast("dt.datetime", self.sr.start) - _HALF_HOUR

    def _next_page(self, next_url: str | None, oldest: dt.datetime | None) -> str | None:
        """Give the address of the page that follows, None if the window has been read to its start.

        The cursor URL does not carry the window, so the `start` is named again: without it the endpoint walks on
        beyond the window to the end of its week (GH-2994).
        """
        if not next_url:
            return None
        if not self.sr.start or not self.sr.end:
            return next_url
        if oldest is not None and oldest <= self._window_start():
            return None
        query = urlencode({"start": self._window_start().strftime(self._date_format)})
        return f"{next_url}&{query}"

    @staticmethod
    def _read_page(content: IOBase) -> tuple[pl.DataFrame, str | None]:
        """Read a page of observations, and the address of the next page that the endpoint names, if it names one."""
        # Every quantity is read as a float: the endpoint types `value` as a number, and polars truncates a
        # float read into an integer field -- 0.8 mm of rain reads as 0. Gust, station pressure, visibility and
        # precipitation carry fractions; the direction was whole degrees in 2406 of 2406 readings of KBOS, KDEN,
        # KSEA, KMIA and KORD (2026-10-13), which nothing promises (GH-2849).
        df = pl.read_json(
            content,
            schema={
                "pagination": pl.Struct({"next": pl.String}),
                "features": pl.List(
                    pl.Struct(
                        {
                            "properties": pl.Struct(
                                {
                                    "station": pl.String,
                                    "timestamp": pl.String,
                                    "temperature": _quantity(pl.Float64),
                                    "dewpoint": _quantity(pl.Float64),
                                    "windDirection": _quantity(pl.Float64),
                                    "windSpeed": _quantity(pl.Float64),
                                    "windGust": _quantity(pl.Float64),
                                    "barometricPressure": _quantity(pl.Float64),
                                    "seaLevelPressure": _quantity(pl.Float64),
                                    "visibility": _quantity(pl.Float64),
                                    "maxTemperatureLast24Hours": _quantity(pl.Float64),
                                    "minTemperatureLast24Hours": _quantity(pl.Float64),
                                    "precipitationLastHour": _quantity(pl.Float64),
                                    "precipitationLast3Hours": _quantity(pl.Float64),
                                    "precipitationLast6Hours": _quantity(pl.Float64),
                                    "relativeHumidity": _quantity(pl.Float64),
                                    "windChill": _quantity(pl.Float64),
                                },
                            ),
                        },
                    ),
                ),
            },
        )
        next_url = df.select(pl.col("pagination").struct.field("next")).item() if df.height else None
        df = df.explode("features", empty_as_null=True)
        df = df.select(pl.col("features").struct.field("properties"))
        df = df.select(pl.col("properties").struct.unnest())
        df = df.rename(str.lower)
        df = df.rename(mapping={"station": "station_id"})
        df = df.with_columns(pl.col("timestamp").str.to_datetime(format="%Y-%m-%dT%H:%M:%S%z"))
        # a page without observations explodes to one null row, which is no observation
        df = df.filter(pl.col("timestamp").is_not_null())
        return df, next_url

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        settings = cast("Settings", self.sr.request.settings)
        pages = []
        url: str | None = self._build_url(station_id)
        read: set[str] = set()
        # the endpoint answers 500 observations at most, newest first, and names the rest in `pagination.next`:
        # follow it until a page is short, the window has been read to its start, or the cursor repeats (GH-2994)
        while url and url not in read:
            read.add(url)
            log.info(f"acquiring data from {url}")
            file = download_file(
                url=url,
                cache_dir=settings.cache_dir,
                ttl=CacheExpiry.FIVE_MINUTES,
                client_kwargs=settings.fsspec_client_kwargs,
                cache_disable=settings.cache_disable,
                use_certifi=settings.use_certifi,
            )
            file.raise_if_exception()
            # narrows the type; `raise_if_exception` has raised for any failed download
            if isinstance(file.content, Exception):
                return pl.DataFrame()
            page, next_url = self._read_page(file.content)
            pages.append(page)
            if page.height < _PAGE_SIZE:
                break
            url = self._next_page(next_url, cast("dt.datetime", page.get_column("timestamp").min()))
        df = pl.concat(pages)
        df = _one_report_per_hour(df)
        df = df.unpivot(
            index=["station_id", "timestamp"],
            variable_name="parameter",
            value_name="value",
        )
        # the 0 of a calm wind is mapped before anything is made of the value, and stays as `raw:0` (GH-2794)
        value, raw = null_sentinels(pl.col("value").struct.field("value").cast(pl.Float64), _CALM_WIND, text=False)
        return df.with_columns(
            pl.lit(parameter_or_dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.name, dtype=pl.String).alias("dataset"),
            # the MADIS flag of the quantity (Z, C, S, V, X, Q, G, B, T), verbatim (GH-2018), then the `raw:` token
            join_quality_flags(pl.col("value").struct.field("qualityControl"), raw=raw),
            value.alias("value"),
        )


@dataclass
class NwsObservationRequest(TimeseriesRequest):
    """Request class for NWS observation."""

    metadata = NwsObservationMetadata
    _values = NwsObservationValues

    # the station list is METAR only and comes from MADIS rather than from api.weather.gov, whose
    # own listing runs to some fifty thousand stations across four hundred cursor-paged requests --
    # mostly mesonet sites the observations endpoint of this provider is not asked for
    _endpoint = "https://madis-data.ncep.noaa.gov/madisPublic1/data/stations/METARTable.txt"

    # American stations the country column files under a state code instead. They are named one by
    # one because the column cannot be read as a state code in general: `PR` in it is Peru, all 27
    # of them, and `GU` is Guatemala; and of the four rows reading `VI`, two are the US Virgin
    # Islands and two are British -- Anguilla and Tortola, which the ICAO prefix tells apart and
    # the country column does not. All three report: they returned 257, 165 and 185 observations
    # over the endpoint's rolling week
    _stations_filed_under_a_state_code = ("PHBK", "TIST", "TISX")

    # MADIS writes a missing elevation as 9999, which is the only elevation above 5000 m in the table
    _elevation_missing = 9999.0

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        file = download_file(
            url=self._endpoint,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        df = read_csv_without_header(file.content, separator="\t", infer_schema_length=0).lazy()
        # the table is the global METAR listing; api.weather.gov serves the United States alone,
        # and column 7 is the country that narrows it to them. No coordinate box is laid over the
        # result on top of that: one excludes American ground for being in the wrong hemisphere --
        # the Aleutians west of Amchitka lie beyond the antimeridian, Pago Pago below the equator
        # and Tinian east of the prime meridian, none of which stops them being the United States
        df = df.filter(
            pl.col("column_7").eq("US")
            | pl.col("column_2").str.strip_chars().is_in(self._stations_filed_under_a_state_code),
        )
        df = df.select(
            pl.col("column_2"),
            pl.col("column_3"),
            pl.col("column_4"),
            pl.col("column_5"),
            pl.col("column_6"),
        )
        df = df.rename(
            mapping={
                "column_2": "station_id",
                "column_3": "latitude",
                "column_4": "longitude",
                "column_5": "elevation",
                "column_6": "name",
            },
        )
        df = df.with_columns(pl.all().str.strip_chars())
        return df.with_columns(
            pl.lit(self.metadata[0].name, dtype=pl.String).alias("resolution"),
            pl.lit(self.metadata[0][0].name, dtype=pl.String).alias("dataset"),
            pl.col("latitude").cast(pl.Float64),
            pl.col("longitude").cast(pl.Float64),
            # a station of unknown elevation reads as null rather than as standing 9999 m up,
            # which interpolation would otherwise take at its word when it moves a reading by elevation
            pl.col("elevation").cast(pl.Float64).replace(self._elevation_missing, None),
        )
