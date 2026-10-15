# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""ECCC observation data provider."""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, cast

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels
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

# The daily gust is published only when it exceeds 30 km/h ("The stations do not report if less than 31 km/h", ECCC's
# glossary under "Speed of Maximum Gust"), and the direction, in tens of degrees where "36 means 360 degrees true" and
# so north, "only if the maximum gust speed for the day exceeds 29 km/h". A day below that has 0 in both fields of the
# collection on most days, where the bulk CSV of the same day (ALERT, 1975-07-01) writes "<31" for the speed. In the
# first 60,000 rows of each of 1975, 1995 and 2019, 4597 of the 8885 days with a gust read 0 for the speed and 0 for
# the direction, without a flag. Neither 0 is a measurement: no gust is 0 km/h, and no direction of 0 exists. The
# direction is 0 on a few days with a reported speed as well (ST CATHARINES A, 1974-11-26: 42 km/h). The reverse also
# exists and is left alone: 14,128 days with a speed of 0 and a direction (CHURCHILL A, 1973-05-13: 340 degrees).
_GUST_NOT_REPORTED = Sentinel("0", where=pl.col("parameter").is_in(["speed_max_gust", "direction_max_gust"]))

# The hourly wind direction is "10's deg" too, and ECCC's glossary (climate.weather.gc.ca/glossary_e.html, "Wind
# Direction") says "36 means 360 degrees true or a wind blowing from the geographic North Pole. A value of zero (0)
# denotes a calm wind." Of the 43,469 hours with a direction of 1998 and 2019 at five stations (read 2026-10-12) 1824
# are 0, **all** with a wind speed of 0, and every hour with a speed of 0 has a direction of 0; 1342 are 36. A calm has
# no direction, so the 0 is no bearing (GH-2794).
_CALM_WIND = Sentinel("0", where=pl.col("parameter").eq("wind_direction"))


#: Local Standard Time of the station list's TIMEZONE codes, as the offset from UTC all year: the codes name
#: standard time, which the station keeps whether or not daylight saving time is adopted for other purposes
#: (https://climate.weather.gc.ca/glossary_e.html). The civil zones of the same name have summer time, which
#: moved a date in the summer months one hour early (GH-2693); Saskatchewan's CST stations keep no summer time at all.
_STANDARD_TIME_OFFSETS = {
    "AST": dt.timedelta(hours=-4),
    "EST": dt.timedelta(hours=-5),
    "CST": dt.timedelta(hours=-6),
    "MST": dt.timedelta(hours=-7),
    "PST": dt.timedelta(hours=-8),
    "NST": dt.timedelta(hours=-3, minutes=-30),
}

#: The columns of the station list that give the first and last date of the station in each collection. FIRST_DATE and
#: LAST_DATE are the station's, whichever collection starts first or ends last: STN_ID 14 has FIRST_DATE 1984-01-01,
#: DLY_FIRST_DATE 1984-07-01 and no hourly dates, 51459 FIRST_DATE 2013-06-11 09:00 and DLY_FIRST_DATE 2013-06-13
#: (read 2026-10-13), so the station list gives each resolution the dates of its own collection (GH-2747). Null for a
#: station without a date in it: for monthly that is no sign of absent rows, it is null for 763 stations that have
#: monthly values.
_COLLECTION_DATE_COLUMNS = {
    Resolution.HOURLY: ("HLY_FIRST_DATE", "HLY_LAST_DATE"),
    Resolution.DAILY: ("DLY_FIRST_DATE", "DLY_LAST_DATE"),
    Resolution.MONTHLY: ("MLY_FIRST_DATE", "MLY_LAST_DATE"),
}
_COLLECTION_DATE_COLUMN_NAMES = tuple(column for columns in _COLLECTION_DATE_COLUMNS.values() for column in columns)

#: The collections whose first date in the station list decides whether a station is listed for the resolution at
#: all. A station without a hourly or daily first date has no row in that collection that holds a value (read
#: 2026-10-15): none of the 95 without a DLY_FIRST_DATE has a daily row, and of the 6750 without a HLY_FIRST_DATE 1049
#: drawn at random have none (hits of ``STN_ID=``), where 2 of the 1961 that GH-2820 probed have: 4333 has 6865 rows of
#: 1995-1997 with no value in any column, and 27490 has 7035 of 2008, after its LAST_DATE 2007-11-30, with
#: PRECIP_AMOUNT (HAS_HOURLY_DATA is N for both). The loss of the second is taken: the station list says it has no
#: hourly collection, and an allow-list of ids would be a table of ECCC's mistakes in the library (GH-2867). Such a
#: station is not listed for the resolution, where it was listed with null dates (GH-2747) and a dated request
#: asked for its years.
#: Monthly is not here: MLY_FIRST_DATE is null for 763 stations that have monthly rows.
#: The dates do not bound the rows of a station that has them: they follow the temperature and not every series.
#: 6813 has HLY_FIRST_DATE 1995-02-16 and 7088 hours of wind from 1994, 27174 has 2013-12-10 and hourly precipitation
#: from 2007, and 5006 has DLY_LAST_DATE 1957-10-31 and daily minimum temperatures in 1961, so the years come from the
#: rows (``_edge_year``), not from these dates (GH-2820, GH-2864).
_LISTED_BY_FIRST_DATE = (Resolution.HOURLY, Resolution.DAILY)


def _localize(value: dt.datetime | None, timezone: str | None) -> dt.datetime | None:
    """Read a date of the station list as Local Standard Time of the station and convert it to UTC.

    A fixed offset, not a zone: the dates are on the LST clock of the hourly ``LOCAL_DATE``, and a zone
    such as America/Toronto would add the hour of summer time. A handful of stations publish no timezone at
    all, which only shows up once the full catalogue is fetched rather than its first 500 rows; their dates
    are read as UTC.
    """
    if value is None:
        return None
    if not timezone:
        return value.replace(tzinfo=dt.UTC)
    if timezone not in _STANDARD_TIME_OFFSETS:
        msg = (
            f"Unknown TIMEZONE {timezone!r} in the ECCC station list, expected one of {sorted(_STANDARD_TIME_OFFSETS)}"
        )
        raise ValueError(msg)
    return value.replace(tzinfo=dt.timezone(_STANDARD_TIME_OFFSETS[timezone])).astimezone(dt.UTC)


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
        """Convert wide-format dataframe to long format, pairing value columns with their *_flag columns.

        The flag is the source's own letter (`M` missing, `E` estimated, `T` trace, ...), kept verbatim
        in `quality_flags`. Monthly rows carry no flags, so theirs is null.
        """
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
        if not flag_columns:
            return df_values.with_columns(
                pl.col("value").cast(pl.Float64),
                pl.lit(None, dtype=pl.String).alias("quality_flags"),
            )
        # Unpivot flag columns (strip _flag suffix so parameter names align)
        df_flags = df.select(["date", *flag_columns]).rename({col: col.removesuffix("_flag") for col in flag_columns})
        flag_value_columns = [col for col in df_flags.collect_schema().names() if col != "date"]
        df_flags = df_flags.unpivot(
            on=flag_value_columns,
            index="date",
            variable_name="parameter",
            value_name="quality_flags",
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

    def _begins_after_window(self, df_station_meta: pl.DataFrame) -> bool:
        """Say whether the station began after the window ended, by the station's own FIRST_DATE.

        The ``start_timestamp`` of a row is the first date of its collection, which does not bound the rows of the
        collection: it follows the temperature and not every series. 27174 has HLY_FIRST_DATE 2013-12-10 and hourly
        precipitation from 2007, 6813 has 1995-02-16 and wind from 1994 (read 2026-10-13), so a window of 2010 would
        have skipped 27174 for the rows it has. FIRST_DATE, which the stamp of the rows did not follow either (1765 has
        rows before it), is the bound the walk had before the dates of the collections were read (GH-2747, GH-2864).
        A station that the list gives no first date, or a result of stations built by hand, is kept.
        """
        bounds = cast("EcccObservationRequest", self.sr.stations)._collection_bounds  # noqa: SLF001
        if not self.sr.end or bounds is None:
            return False
        first_dates = df_station_meta.select("station_id", "resolution", "dataset").join(
            bounds, on=["station_id", "resolution", "dataset"], how="left"
        )["first_date"]
        if first_dates.null_count():
            return False
        return cast("dt.datetime", first_dates.min()) > self.sr.end

    def _edge_year(
        self, station_id: str, dataset: DatasetModel, *, date_field: str, descending: bool = False
    ) -> int | None:
        """Give the year of the first (or last) row of a station in a collection, None if it has no row.

        One request with ``limit=1`` and a sort, which the API answered in under a second for most stations and
        slowly, up to 27 s, for some, as it does for any request (an empty year of 5006 took 27 s too; read 2026-10-14).
        The station list cannot say it: its first and last date of a collection follow the temperature and not every
        series, and FIRST_DATE is not the first row either. 1765 has hourly rows from 1955-10-01 and FIRST_DATE
        1956-01-06; 6813 has HLY_FIRST_DATE 1995-02-16 and wind from 1994 (GH-2864). It is no guess in the other
        direction either: White Rock (925), FIRST_DATE 1929, has its first hourly row in 1994 (GH-2820).
        """
        settings = cast("Settings", self.sr.stations.settings)
        file = download_file(
            url=(
                f"{self._endpoint}/collections/{self._resolution_to_dataset_mapping[dataset.resolution.value]}/"
                f"items?STN_ID={station_id}&sortby={'-' if descending else ''}{date_field}&limit=1&f=json"
            ),
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            # no connection: nothing to ask for, as for a year
            return None
        features = json.load(file.content).get("features") or []
        date = features[0]["properties"].get(date_field) if features else None
        # "1994-02-06T06:00:00", "1929-01-01 00:00:00" or the month "1929-01": the year comes first in each
        return int(date[:4]) if date else None

    def _years(
        self, station_id: str, dataset: DatasetModel, *, date_field: str, station_end: dt.datetime | None
    ) -> range:
        """Give the years to ask for: those of the request, and for a request without dates those of the rows.

        A request has both dates or none. Without them the years begin with the first row of the collection
        (``_edge_year``). They end with its last row for the hourly and the monthly collection; the daily collection
        answers a descending sort with the rows without a value that it carries up to today for many closed stations
        (390, 962, 2898, read 2026-10-13), so it ends with the station's LAST_DATE.

        A hourly or daily station without a first date in the station list is not listed for the resolution, so it is
        never asked for here (``_LISTED_BY_FIRST_DATE``, GH-2867).
        """
        if self.sr.start and self.sr.end:
            return range(self.sr.start.year, self.sr.end.year + 1)
        bounds = cast("EcccObservationRequest", self.sr.stations)._collection_bounds  # noqa: SLF001
        row = None
        if bounds is not None:
            rows = bounds.filter(
                (pl.col("station_id") == station_id)
                & (pl.col("resolution") == dataset.resolution.name)
                & (pl.col("dataset") == dataset.name)
            ).to_dicts()
            row = rows[0] if rows else None
        first = self._edge_year(station_id, dataset, date_field=date_field)
        if first is None:
            return range(0)
        if dataset.resolution.value == Resolution.DAILY:
            # a result of stations built by hand has no LAST_DATE: the end stamped on its row stands in, or today
            last_date = (row["last_date"] if row is not None else None) or station_end or dt.datetime.now(dt.UTC)
            last = last_date.year
        else:
            last = self._edge_year(station_id, dataset, date_field=date_field, descending=True)
        return range(first, last + 1) if last is not None else range(0)

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        """Collect station dataset."""
        settings = cast("Settings", self.sr.stations.settings)
        # Normalize parameter_or_dataset to a DatasetModel for uniform access below.
        from wetterdienst.model.metadata import DatasetModel as _DatasetModel  # noqa: PLC0415

        if isinstance(parameter_or_dataset, _DatasetModel):
            dataset = parameter_or_dataset
        else:
            dataset = parameter_or_dataset.dataset
        # The row of this resolution and dataset, whose dates are those of its collection (GH-2730, GH-2747)
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
        for year in self._years(station_id, dataset, date_field=date_field, station_end=station_meta["end_timestamp"]):
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
            # the sentinel is mapped before the tens of degrees are decoded and the unit is converted, and the 0 the
            # source wrote stays on the value as a `raw:` token
            value, raw = null_sentinels(pl.col("value"), _GUST_NOT_REPORTED, _CALM_WIND, text=False)
            df = df.with_columns(value.alias("value"), raw.alias("raw"))
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
                join_quality_flags(pl.col("quality_flags"), raw=pl.col("raw")),
            )
            data.append(df)
        # the in-memory engine on purpose: polars 2 collects with the streaming engine by default, which took
        # the unpivot and join of 60 years of daily rows 4 times as long, for the same rows (GH-2781)
        return pl.concat(data).collect(engine="in-memory") if data else pl.DataFrame()


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
    _values = EcccObservationValues

    # What the values read of the station list and the stations do not carry: for each station and dataset the station's
    # FIRST_DATE and LAST_DATE stamped like the dates of the resolution (GH-2864); the hourly LAST_DATE is null, as the
    # last hourly row is asked for. They are no column of the stations, whose dates are those of the collection
    # (GH-2747).
    _collection_bounds: pl.DataFrame | None = field(default=None, init=False, repr=False, compare=False)

    def _all(self) -> pl.LazyFrame:

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
                                # decimal degrees, longitude first
                                "geometry": pl.Struct({"coordinates": pl.List(pl.Float64)}),
                                "properties": pl.Struct(
                                    {
                                        "STN_ID": pl.Int64,
                                        "STATION_NAME": pl.String,
                                        "PROV_STATE_TERR_CODE": pl.String,  # alternative: ENG_PROV_NAME
                                        "TIMEZONE": pl.String,
                                        "ELEVATION": pl.String,
                                        "FIRST_DATE": pl.String,
                                        "LAST_DATE": pl.String,
                                        **dict.fromkeys(_COLLECTION_DATE_COLUMN_NAMES, pl.String),
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
            # not `LATITUDE` and `LONGITUDE` of the properties: they pack degrees, minutes and seconds into one
            # integer (`485500000` is 48 deg 55' 00"), which read as degrees times 10^7 put 8431 of the 8435 stations
            # up to 0.4 degrees off the feature's own geometry (GH-2942)
            pl.col("features")
            .struct.field("geometry")
            .struct.field("coordinates")
            .list.get(1, null_on_oob=True)
            .alias("latitude"),
            pl.col("features")
            .struct.field("geometry")
            .struct.field("coordinates")
            .list.get(0, null_on_oob=True)
            .alias("longitude"),
            pl.col("features").struct.field("properties").struct.field("ELEVATION").alias("elevation"),
            pl.col("features").struct.field("properties").struct.field("FIRST_DATE").alias("first_date"),
            pl.col("features").struct.field("properties").struct.field("LAST_DATE").alias("last_date"),
            pl.col("features").struct.field("properties").struct.field("TIMEZONE").alias("timezone"),
            *(
                pl.col("features").struct.field("properties").struct.field(column).alias(column.lower())
                for column in _COLLECTION_DATE_COLUMN_NAMES
            ),
        )
        # parse the dates as naive local datetimes; `_stamp_bounds` stamps them per resolution
        df_raw = df_raw.with_columns(
            pl.col("station_id").cast(pl.String),
            pl.col(
                "first_date", "last_date", *(column.lower() for column in _COLLECTION_DATE_COLUMN_NAMES)
            ).str.to_datetime("%Y-%m-%d %H:%M:%S"),
            pl.col("elevation").cast(pl.Float64),
        )
        # combinations of resolution and dataset
        from wetterdienst.model.metadata import ParameterModel  # noqa: PLC0415

        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        }
        collection_columns = [column.lower() for column in _COLLECTION_DATE_COLUMN_NAMES]
        data = []
        # for each combination of resolution and dataset create a new DataFrame with the columns
        for resolution, dataset in resolutions_and_datasets:
            first, last = (column.lower() for column in _COLLECTION_DATE_COLUMNS[Resolution(resolution)])
            # a station is listed for a resolution whose first date the list gives it (GH-2867)
            listed = (
                df_raw.filter(pl.col(first).is_not_null())
                if Resolution(resolution) in _LISTED_BY_FIRST_DATE
                else df_raw
            )
            data.append(
                self._stamp_bounds(
                    listed.with_columns(
                        pl.col(first).alias("start_timestamp"),
                        pl.col(last).alias("end_timestamp"),
                    ).select(pl.all().exclude(collection_columns)),
                    resolution=Resolution(resolution),
                ).with_columns(
                    pl.lit(resolution, pl.String).alias("resolution"),
                    pl.lit(dataset, pl.String).alias("dataset"),
                ),
            )
        df = pl.concat(data).collect()
        self._collection_bounds = df.select("station_id", "resolution", "dataset", "first_date", "last_date")
        return df.drop("first_date", "last_date").lazy()

    @staticmethod
    def _stamp_bounds(df: pl.LazyFrame, *, resolution: Resolution) -> pl.LazyFrame:
        """Give the first and last date of the collection as the stamps of its first and last value.

        The dates are written in the station's Local Standard Time, the clock of the hourly LOCAL_DATE with no summer
        time (GH-2693). Hourly rows are stamped with an instant, so the date is converted from that offset to UTC. Daily
        and monthly rows are stamped at 00:00 UTC of their date or month whatever the zone (GH-2683), so the date is
        cut to the day or month it names and stamped the same way: converted to UTC, the first day of a station read
        2013-06-11 14:00 UTC, after the 00:00 UTC window of a request for that one day, and the station was skipped
        though it has a value dated that day (GH-2730).
        """
        if resolution in (Resolution.DAILY, Resolution.MONTHLY):
            unit = "1mo" if resolution == Resolution.MONTHLY else "1d"
            return df.select(pl.all().exclude("timezone")).with_columns(
                pl.col("start_timestamp", "end_timestamp", "first_date", "last_date")
                .dt.truncate(unit)
                .dt.replace_time_zone("UTC"),
            )
        # the last year of the hourly rows is that of the last row (``_years``), so LAST_DATE is not carried
        return df.with_columns(
            pl.lit(None, dtype=pl.Datetime(time_zone="UTC")).alias("last_date"),
            *(
                pl.struct([column, "timezone"])
                .map_elements(
                    lambda row, column=column: _localize(row[column], row["timezone"]),
                    return_dtype=pl.Datetime(time_zone="UTC"),
                )
                .alias(column)
                for column in ("start_timestamp", "end_timestamp", "first_date")
            ),
        ).select(pl.all().exclude("timezone"))
