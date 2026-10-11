# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""ECCC observation data provider."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.eccc.observation.metadata import EcccObservationMetadata
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel, ParameterModel
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

# ECCC publishes ~8600 stations; the OGC default page size is 500
_STATIONS_LIMIT = 10000
# the collections page at 500 features by default, which silently truncates a station-year
_PAGE_SIZE = 10000


def _localize(value: dt.datetime | None, timezone: str | None) -> dt.datetime | None:
    """Attach the station's timezone and convert to UTC.

    Converted here in Python rather than handed to polars tz-aware: stations opened before
    standard time carry an LMT offset that is not a whole number of minutes (America/Toronto is
    -5:17:32 in 1895), which polars rejects outright. A handful of stations publish no timezone at
    all, which only shows up once the full catalogue is fetched rather than its first 500 rows.
    """
    if value is None:
        return None
    tz = ZoneInfo(timezone) if timezone else dt.UTC
    return value.replace(tzinfo=tz).astimezone(dt.UTC)


class EcccObservationValues(TimeseriesValues):
    """Values class for Environment and Climate Change Canada (ECCC) observation data."""

    _endpoint = "https://api.weather.gc.ca"

    _resolution_to_dataset_mapping: ClassVar[dict[Resolution, str]] = {
        Resolution.HOURLY: "climate-hourly",
        Resolution.DAILY: "climate-daily",
        Resolution.MONTHLY: "climate-monthly",
    }

    @staticmethod
    def _tidy_up_df(df: pl.LazyFrame) -> pl.LazyFrame:
        """Convert wide-format dataframe to long format, pairing value columns with their *_flag quality columns."""
        # column names arrive lower-cased; `date` is the time axis, made `timestamp` further down
        schema_names = df.collect_schema().names()
        flag_columns = {col for col in schema_names if col.endswith("_flag")}
        value_columns = [col for col in schema_names if col != "date" and col not in flag_columns]
        if not value_columns:
            return pl.LazyFrame()
        # Unpivot value columns to long format
        df_values = df.select(["date", *value_columns]).unpivot(
            on=value_columns,
            index="date",
            variable_name="parameter",
            value_name="value",
        )
        # Unpivot flag columns (strip _flag suffix so parameter names align)
        df_flags = df.select(["date", *flag_columns]).rename({col: col.removesuffix("_flag") for col in flag_columns})
        flag_value_columns = [col for col in df_flags.collect_schema().names() if col != "date"]
        df_flags = df_flags.unpivot(
            on=flag_value_columns,
            index="date",
            variable_name="parameter",
            value_name="quality",
        )
        return df_values.join(df_flags, on=["date", "parameter"], how="left").with_columns(
            pl.col("value").cast(pl.Float64),
        )

    @staticmethod
    def _year_window(year: int, *, hourly: bool) -> str:
        """Return the query parameter that selects a year of a station's rows."""
        if hourly:
            # The year of UTC_DATE, which is what the rows are stamped with. A `datetime` window filters
            # LOCAL_DATE, the station's Local Standard Time, and a window built from the civil zone of
            # the station (tzfpy) misses the edge hour wherever that zone's offset is not the one ECCC
            # states for the station, such as 50837 FORT ST. JOHN A, whose TIMEZONE is PST (-8) while
            # tzfpy has Dawson Creek (-7).
            return f"UTC_YEAR={year}"
        # Daily and monthly rows carry a calendar date or month in LOCAL_DATE, and the stamp is that date at 00:00 UTC
        # whatever the station's zone (GH-2683), so the year is cut from LOCAL_DATE as it is written.
        return f"datetime={year}-01-01T00:00:00/{year}-12-31T23:59:59"

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        """Collect station dataset."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.sr.stations.settings)
        # Normalize parameter_or_dataset to a DatasetModel for uniform access below.
        from wetterdienst.model.metadata import DatasetModel as _DatasetModel  # noqa: PLC0415

        if isinstance(parameter_or_dataset, _DatasetModel):
            dataset = parameter_or_dataset
        else:
            dataset = parameter_or_dataset.dataset
        # The row of this resolution and dataset: the first and last date differ between resolutions (GH-2730), and the
        # first row of the station is the one of whichever resolution was requested first.
        station_meta = self.sr.df.filter(
            (pl.col("station_id") == station_id)
            & (pl.col("resolution") == dataset.resolution.name)
            & (pl.col("dataset") == dataset.name)
        ).to_dicts()[0]
        # Derived from the declarations rather than hard-coded: the three lists used to be
        # maintained by hand and the hourly one had drifted to a copy of the daily fields, none of
        # which the hourly collection publishes, so the resolution returned nothing. Built once
        # here rather than per year, since it depends only on the dataset.
        fields = []
        for parameter in dataset.parameters:
            if parameter.name == "quality":
                continue
            field = parameter.name_original.upper()
            fields.append(field)
            if dataset.resolution.value in (Resolution.HOURLY, Resolution.DAILY):
                # monthly carries no per-value flags
                fields.append(f"{field}_FLAG")
        # Hourly rows are stamped from UTC_DATE. The hourly LOCAL_DATE is Local Standard Time, which does not follow
        # daylight saving (the bulk CSV header reads "Date/Time (LST)"), and it was read as the station's civil time:
        # in summer every value was an hour early, the LST hour that does not exist on the civil clock of spring got
        # no timestamp and the UTC hour after the autumn change was left a hole (GH-2675). UTC_DATE is LOCAL_DATE
        # plus the station's standard offset all year. Daily and monthly rows carry a civil date and stay on
        # LOCAL_DATE.
        hourly = dataset.resolution.value == Resolution.HOURLY
        date_field = "UTC_DATE" if hourly else "LOCAL_DATE"
        _properties_schema = pl.Struct(
            {date_field: pl.String} | {f: (pl.String if f.endswith("FLAG") else pl.Float64) for f in fields}
        )
        data = []
        start_year = self.sr.start.year if self.sr.start else station_meta["start_timestamp"].year
        end_year = self.sr.end.year if self.sr.end else station_meta["end_timestamp"].year
        for year in range(start_year, end_year + 1):
            window = self._year_window(year, hourly=hourly)
            # The endpoint pages at 500 features and a station-year of hourly data is ~8800, so a
            # single request returns an arbitrary slice of the year and silently drops the rest.
            # Page until a short page comes back.
            pages = []
            offset = 0
            while True:
                url = (
                    f"{self._endpoint}/collections/"
                    f"{self._resolution_to_dataset_mapping[dataset.resolution.value]}/"
                    f"items?STN_ID={station_id}&{window}"
                    f"&limit={_PAGE_SIZE}&offset={offset}&f=json"
                )
                file = download_file(
                    url=url,
                    cache_dir=settings.cache_dir,
                    ttl=CacheExpiry.FIVE_MINUTES,
                    client_kwargs=settings.fsspec_client_kwargs,
                    cache_disable=settings.cache_disable,
                    use_certifi=settings.use_certifi,
                )
                file.raise_if_exception()
                if isinstance(file.content, Exception):
                    return pl.DataFrame()
                df_page = pl.read_json(
                    file.content,
                    schema=pl.Schema(
                        {
                            "features": pl.List(
                                pl.Struct(
                                    {
                                        "properties": _properties_schema,
                                    }
                                )
                            ),
                        }
                    ),
                )
                df_page = df_page.lazy()
                df_page = df_page.select(
                    pl.col("features").explode(empty_as_null=True).struct.field("properties")
                ).unnest("properties")
                df_page = df_page.rename(str.lower).rename({date_field.lower(): "date"}).collect()
                pages.append(df_page)
                if df_page.height < _PAGE_SIZE:
                    break
                offset += _PAGE_SIZE
            df = pl.concat(pages).lazy()
            df = self._tidy_up_df(df)
            # ECCC publishes both gust direction (daily) and wind direction (hourly) in tens of degrees --
            # its own docs call the daily column
            # "Dir of Max Gust (10s deg)" -- so 23 means 230 degrees. Decoded here rather than
            # declared as a unit, because tens of degrees is a source encoding rather than a unit
            # anyone reports in. Without it every bearing came back 10x too small and inside
            # 0..36, which no range check on degrees would ever flag.
            df = df.with_columns(
                pl.when(pl.col("parameter").is_in(["direction_max_gust", "wind_direction"]))
                .then(pl.col("value") * 10)
                .otherwise(pl.col("value"))
                .alias("value"),
            )
            if hourly:
                # "2025-07-01T16:00:00", already UTC
                timestamp = pl.col("date").str.to_datetime("%Y-%m-%dT%H:%M:%S", time_zone="UTC")
            else:
                # a calendar date (daily "2025-01-15 00:00:00") or month (monthly "2023-06"), stamped at 00:00 UTC of it
                # whatever the station's zone: the date names the day or month, which is no instant of the local
                # clock, and a request for that one day bounds the window at 00:00 UTC (GH-2683)
                timestamp = (
                    pl.col("date")
                    .str.to_datetime("%Y-%m" if dataset.resolution.value == Resolution.MONTHLY else "%Y-%m-%d %H:%M:%S")
                    .dt.replace_time_zone("UTC")
                )
            df = df.select(
                pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
                pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
                "parameter",
                pl.lit(station_id, dtype=pl.String).alias("station_id"),
                timestamp.alias("timestamp"),
                "value",
                pl.lit(None, dtype=pl.Float64).alias("quality"),
            )
            data.append(df)
        return pl.concat(data).collect()


@dataclass
class EcccObservationRequest(TimeseriesRequest):
    """Download weather data from Environment and Climate Change Canada (ECCC).

    - https://www.canada.ca/en/environment-climate-change.html
    - https://www.canada.ca/en/services/environment/weather.html

    Original code by Trevor James Smith. Thanks!
    - https://github.com/Zeitsperre/canada-climate-python

    """

    _endpoint = "https://api.weather.gc.ca"

    metadata = EcccObservationMetadata
    # _values is a class object (subclass of TimeseriesValues). Use cast to
    # satisfy the static typechecker which expects a TimeseriesValues value.
    _values = cast("TimeseriesValues", EcccObservationValues)

    # Mapping of Canadian timezone abbreviations to IANA timezone identifiers
    _timezone_mapping: ClassVar[dict] = {
        "ADT": "America/Halifax",  # Atlantic Daylight Time
        "AST": "America/Halifax",  # Atlantic Standard Time
        "CDT": "America/Winnipeg",  # Central Daylight Time
        "CST": "America/Winnipeg",  # Central Standard Time
        "EDT": "America/Toronto",  # Eastern Daylight Time
        "EST": "America/Toronto",  # Eastern Standard Time
        "MDT": "America/Edmonton",  # Mountain Daylight Time
        "MST": "America/Edmonton",  # Mountain Standard Time
        "NDT": "America/St_Johns",  # Newfoundland Daylight Time
        "NST": "America/St_Johns",  # Newfoundland Standard Time
        "PDT": "America/Vancouver",  # Pacific Daylight Time
        "PST": "America/Vancouver",  # Pacific Standard Time
        "YDT": "America/Whitehorse",  # Yukon Daylight Time
        "YST": "America/Whitehorse",  # Yukon Standard Time
    }

    def _all(self) -> pl.LazyFrame:
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        # The OGC endpoint defaults to 500 features, and ECCC has ~8600 stations, so the default
        # silently reduced the network to its first 500 station ids -- every other station was
        # simply unreachable. `limit` is the collection's documented maximum.
        file = download_file(
            url=f"{self._endpoint}/collections/climate-stations/items?limit={_STATIONS_LIMIT}&f=json",
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        df_raw = pl.read_json(
            file.content,
            schema=pl.Schema(
                {
                    "features": pl.List(
                        pl.Struct(
                            {
                                "type": pl.String,
                                "properties": pl.Struct(
                                    {
                                        "STN_ID": pl.Int64,
                                        "STATION_NAME": pl.String,
                                        "PROV_STATE_TERR_CODE": pl.String,  # alternative: ENG_PROV_NAME
                                        "LATITUDE": pl.Int64,
                                        "LONGITUDE": pl.Int64,
                                        "TIMEZONE": pl.String,
                                        "ELEVATION": pl.String,
                                        "FIRST_DATE": pl.String,
                                        "LAST_DATE": pl.String,
                                    }
                                ),
                            }
                        )
                    ),
                }
            ),
        )
        df_raw = df_raw.lazy()
        df_raw = df_raw.select(pl.col("features").explode(empty_as_null=True))
        df_raw = df_raw.select(
            pl.col("features").struct.field("properties").struct.field("STN_ID").alias("station_id"),
            pl.col("features").struct.field("properties").struct.field("STATION_NAME").alias("name"),
            pl.col("features").struct.field("properties").struct.field("PROV_STATE_TERR_CODE").alias("region"),
            pl.col("features").struct.field("properties").struct.field("LATITUDE").alias("latitude"),
            pl.col("features").struct.field("properties").struct.field("LONGITUDE").alias("longitude"),
            pl.col("features").struct.field("properties").struct.field("ELEVATION").alias("elevation"),
            pl.col("features").struct.field("properties").struct.field("FIRST_DATE").alias("start_timestamp"),
            pl.col("features").struct.field("properties").struct.field("LAST_DATE").alias("end_timestamp"),
            pl.col("features").struct.field("properties").struct.field("TIMEZONE").alias("timezone"),
        )
        # Map timezone abbreviations to IANA timezone names
        df_raw = df_raw.with_columns(
            pl.col("timezone").replace_strict(self._timezone_mapping, default=pl.col("timezone")),
        )
        # parse start_timestamp and end_timestamp as naive local datetimes; `_stamp_bounds` stamps them per resolution
        df_raw = df_raw.with_columns(
            pl.col("station_id").cast(pl.String),
            pl.col("start_timestamp").str.to_datetime("%Y-%m-%d %H:%M:%S"),
            pl.col("end_timestamp").str.to_datetime("%Y-%m-%d %H:%M:%S"),
            pl.col("elevation").cast(pl.Float64),
        )
        df_raw = df_raw.with_columns(
            pl.col("latitude") / 10_000_000,
            pl.col("longitude") / 10_000_000,
        )
        # combinations of resolution and dataset
        from wetterdienst.model.metadata import ParameterModel  # noqa: PLC0415

        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        }
        data = []
        # for each combination of resolution and dataset create a new DataFrame with the columns
        for resolution, dataset in resolutions_and_datasets:
            data.append(
                self._stamp_bounds(df_raw, resolution=Resolution(resolution)).with_columns(
                    pl.lit(resolution, pl.String).alias("resolution"),
                    pl.lit(dataset, pl.String).alias("dataset"),
                ),
            )
        return pl.concat(data)

    @staticmethod
    def _stamp_bounds(df: pl.LazyFrame, *, resolution: Resolution) -> pl.LazyFrame:
        """Give the first and last date of the station as the stamps of the resolution's first and last value.

        FIRST_DATE and LAST_DATE are written in the station's local time. Hourly rows are stamped with an instant, so
        the date is converted from the station's zone to UTC. Daily and monthly rows are stamped at 00:00 UTC of their
        date or month whatever the zone (GH-2683), so the date is cut to the day or month it names and stamped the same
        way: converted to UTC, the first day of a station read 2013-06-11 13:00 UTC, after the 00:00 UTC window of a
        request for that one day, and the station was skipped though it has a value dated that day (GH-2730).
        """
        if resolution in (Resolution.DAILY, Resolution.MONTHLY):
            unit = "1mo" if resolution == Resolution.MONTHLY else "1d"
            return df.select(pl.all().exclude("timezone")).with_columns(
                pl.col("start_timestamp", "end_timestamp").dt.truncate(unit).dt.replace_time_zone("UTC"),
            )
        return df.with_columns(
            pl.struct(["start_timestamp", "timezone"])
            .map_elements(
                lambda row: _localize(row["start_timestamp"], row["timezone"]),
                return_dtype=pl.Datetime(time_zone="UTC"),
            )
            .alias("start_timestamp"),
            pl.struct(["end_timestamp", "timezone"])
            .map_elements(
                lambda row: _localize(row["end_timestamp"], row["timezone"]),
                return_dtype=pl.Datetime(time_zone="UTC"),
            )
            .alias("end_timestamp"),
        ).select(pl.all().exclude("timezone"))
