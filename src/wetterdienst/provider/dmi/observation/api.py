# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DMI (Danish Meteorological Institute) climate data observation provider.

DMI publishes quality-controlled climate data through an open, key-less OGC API Features
service (GeoJSON). The ``climateData`` service exposes aggregated ``stationValue`` records
that can be filtered by station, parameter, time resolution and datetime range in a single
request -- see https://www.dmi.dk/friedata/dokumentation/climate-data.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast

import polars as pl

from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dmi.observation.metadata import DmiObservationMetadata
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.settings import Settings


_BASE_URL = "https://opendataapi.dmi.dk/v2/climateData/collections"
# DMI accepts a limit of up to 300000 records per page, so a short range is one page. DMI always
# returns a "next" link regardless, so pagination stops on a short page.
_PAGE_LIMIT = 300_000
# DMI answers a request whose offset is above 500000 with a 400 ("Offset cannot be greater than
# 500000"). Pages start at offsets 0 and 300000, so a window of 600000 records or more is not
# paged through but halved.
_MAX_OFFSET = 500_000
# The span a request covers at most, per resolution, so that a long range is fetched as a series
# of windows each far below that cap: an hourly station answers about 300 records a day, a daily
# one fewer than 100. A resolution not listed is requested in one window. A window that still
# fills the pages is halved (see `_fetch_station_value_pages`), so these only keep that rare.
_WINDOW_SPAN: dict[Resolution, dt.timedelta] = {
    Resolution.HOURLY: dt.timedelta(days=365),
    Resolution.DAILY: dt.timedelta(days=3650),
}
_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class _OffsetCapReachedError(Exception):
    """Raised when a window holds more records than the pages below DMI's offset cap can carry."""


# DMI writes a mean wind direction of 0 for an aggregate whose mean wind speed is 0, and north as 360 or 0. Over the
# hourly records of 2020 and 2021 of stations 06180, 06070, 04339, 06058 and 06096 (read 2026-10-12), 1530 of the 1616
# hours with a speed of 0 have a direction of 0 (the other 86 are at 04339), while at a speed of 1 m/s or more a
# direction of 0 comes in 3 to 20 hours per station against 13 to 31 hours of 360: the two half degrees either side of
# north, since the direction is rounded to whole degrees. So the 0 is a bearing in a wind that blows, and a code in
# one that does not. Between 0 and 1 m/s it is both (474 of 1856 hours at 06070, 14 of 2402 at 04339), and DMI documents
# no limit (the documentation host, opendatadocs.dmi.govcloud.dk, answers 404), so only the aggregate whose mean speed
# is exactly 0 is taken for a calm. The same holds for the daily records: 04339 has 870 days with a speed of 0 and a
# direction of 0, 06180 five days with a 0 beside a speed of 2 to 7 m/s (GH-2794).
_MEAN_WIND_SPEED = "mean_wind_speed"
_CALM_WIND = Sentinel(
    "0",
    where=pl.col("parameterId").eq("mean_wind_dir")
    & pl.col("value").filter(pl.col("parameterId").eq(_MEAN_WIND_SPEED)).first().over("from", "to").eq(0),
)

# DMI documents -0.1 as a code, not an amount: "Precipitation Codes: the parameters acc_precip, max_precip_past24h,
# acc_precip_past12h, acc_precip_past24h and max_precip_30m return the amount of precipitation within the given period
# in mm with the exception of the codes listed below. -0.1: traces of precipitation, less than 0.1 kg/m2"
# (https://www.dmi.dk/friedata/dokumentation/climate-data, read 2026-10-30). It is some rain below what the gauge
# reports, so it is 0.0 and no negative amount, as the trace of KNMI, AEMET and Meteo-France's synop is. It keeps
# the text as the `raw:-0.1` token of `quality_flags` (GH-2759), which is how those providers mark a trace and so how
# a caller finds one. Without the rule the lower bound of 0 below read it as out of range and null (GH-3621).
_PRECIPITATION_AMOUNTS = (
    "acc_precip",
    "max_precip_24h",
    "max_precip_30m",
    "acc_precip_past12h",
    "acc_precip_past24h",
)
_TRACE = Sentinel("-0.1", where=pl.col("parameterId").is_in(_PRECIPITATION_AMOUNTS), to=0.0)

# DMI's greatest snow depth of a month and of a year is 999.0 for September 2020 at 24043 and 31259 (and for 2020 as a
# year), both marked `validity: true` with 7 values in the calculation: a snow depth of 9.99 m in a Danish September.
# DMI documents no code for it (the climate data documentation, read 2026-10-31, mentions 999 nowhere), the other
# 8,490 monthly and 1,229 annual values run to 138 cm, and 999.0 is the value that stands for a missing one in
# DMI's other fields (`max_precip_24h` of 04320, 2013-09). It is null and keeps `raw:999`.
_MISSING_SNOW_DEPTH = Sentinel("999", where=pl.col("parameterId").eq("max_snow_depth"))

# DMI's heating degree days of Greenland (base 19) are the field `acc_heating_degree_days_19`, where those of Denmark
# (base 17) are `acc_heating_degree_days_17`: no station has both, so the one is read as the other and the two are the
# one parameter, `heating_degree_day`. Its range holds for either base: the highest year DMI publishes is 18,022.8
# (04416 Summit on the ice sheet, 2011; 17,747.8 in 2009 and 17,612.7 in 2013) and the highest month 2,114.3 (2011-12),
# so the bound of 20,000 of the range table leaves about 10 % above the highest year (read 2026-10-31)
_FIELD_SERVED_AS = {"acc_heating_degree_days_19": "acc_heating_degree_days_17"}
# DMI's value of a parameter that the metadata declares in another unit is multiplied by this factor: the radiation of
# a day, a month and a year is a sum in MJ/m2 that the metadata declares in kJ/m2 (GH-3622)
_TO_DECLARED_UNIT: dict[str, dict[str, float]] = {
    "daily": {"mean_radiation": 1_000.0},
    "monthly": {"mean_radiation": 1_000.0},
    "annual": {"mean_radiation": 1_000.0},
}
_STATION_VALUE_SCHEMA = pl.Schema(
    {
        "features": pl.List(
            pl.Struct(
                {
                    "properties": pl.Struct(
                        {
                            "parameterId": pl.String,
                            "from": pl.String,
                            "to": pl.String,
                            "value": pl.Float64,
                            "qcStatus": pl.String,
                            "validity": pl.Boolean,
                        }
                    ),
                }
            )
        ),
    }
)

_STATION_SCHEMA = pl.Schema(
    {
        "features": pl.List(
            pl.Struct(
                {
                    "geometry": pl.Struct({"coordinates": pl.List(pl.Float64)}),
                    "properties": pl.Struct(
                        {
                            "stationId": pl.String,
                            "name": pl.String,
                            "country": pl.String,
                            "stationHeight": pl.Float64,
                            "validFrom": pl.String,
                            "validTo": pl.String,
                            "created": pl.String,
                        }
                    ),
                }
            )
        ),
    }
)


# The extremes and sums of the last 12 and 24 hours are stamped by the end of the window, as dwd/poi, meteofrance/synop
# and noaa/ghcn stamp theirs: DMI's `from` is the start of the last hour of the window (`from` 17:00, `to` 18:00 UTC for
# the 18 UTC report, whose 12 hours start at 06:00), so the `to` of the record is the report time (GH-3622).
_STAMPED_BY_THE_END_OF_THE_WINDOW = ("max_temp_12h", "min_temperature_12h", "acc_precip_past12h", "acc_precip_past24h")


class DmiObservationValues(TimeseriesValues):
    """Values class for DMI climate data observations."""

    _resolution_to_time_resolution: ClassVar[dict[Resolution, str]] = {
        Resolution.HOURLY: "hour",
        Resolution.DAILY: "day",
        Resolution.MONTHLY: "month",
        Resolution.ANNUAL: "year",
    }

    @staticmethod
    def _date_expression(resolution: Resolution) -> pl.Expr:
        """Build the ``timestamp`` column expression from DMI's ``from`` and ``to`` timestamps.

        DMI labels each aggregate by the start of its period, but for the extremes and sums of the last 12 and 24 hours,
        whose ``from`` is the start of the last hour of the window: those are stamped by their ``to``, the end of the
        window (``_STAMPED_BY_THE_END_OF_THE_WINDOW``, applied in the collection, not here). Hourly data is
        aligned to UTC (``from`` carries a ``+00:00`` offset), so it is parsed and normalised to UTC directly.
        Day/month/year aggregates use *local civil* period boundaries (``from`` carries the
        station's local offset, e.g. ``2023-06-02T00:00:00.001000+02:00``). Their civil date
        is taken straight from the leading characters of the string -- this is timezone
        independent and therefore correct for Danish, Greenlandic and Faroese stations alike
        -- and stamped at UTC midnight of that civil date, matching the codebase convention
        of expressing nominal calendar dates as UTC.

        A daily value is dated by its ``to`` instead: ``to`` is the end of the day (the next
        civil midnight, or 06:00 UTC for Greenland and the Faroe Islands), so the day is the
        date before it. ``from`` of ``max_precip_30m`` is 23:31 of the previous day, which
        would name the previous day.
        """
        if resolution == Resolution.HOURLY:
            # %.f tolerates an optional fractional-seconds part: hourly `from` is observed at
            # second precision (e.g. `...00+00:00`), but DMI emits fractional seconds on the
            # coarser resolutions (`.001000`), so parse defensively in case hourly does too.
            return pl.col("from").str.to_datetime("%Y-%m-%dT%H:%M:%S%.f%z", time_unit="us").dt.convert_time_zone("UTC")
        year = pl.col("from").str.slice(0, 4).cast(pl.Int32)
        if resolution == Resolution.DAILY:
            end = pl.date(
                pl.col("to").str.slice(0, 4).cast(pl.Int32),
                pl.col("to").str.slice(5, 2).cast(pl.Int32),
                pl.col("to").str.slice(8, 2).cast(pl.Int32),
            )
            local = end - pl.duration(days=1)
        elif resolution == Resolution.MONTHLY:
            month = pl.col("from").str.slice(5, 2).cast(pl.Int32)
            local = pl.date(year, month, 1)
        else:  # ANNUAL
            local = pl.date(year, 1, 1)
        return local.cast(pl.Datetime(time_unit="us")).dt.replace_time_zone("UTC")

    def _iter_station_value_pages(
        self,
        station_id: str,
        time_resolution: str,
        start: str,
        end: str,
        settings: Settings,
    ) -> Iterator[pl.DataFrame]:
        """Yield each page of DMI stationValue records for a station/resolution/date range.

        DMI paginates via limit/offset and always emits a "next" link, so pages are walked
        until a short (or empty) page marks the end. Yields the parsed ``properties`` of each
        non-empty page; raises on the first download error, ``NoInternetError`` included.

        DMI refuses an offset above ``_MAX_OFFSET``, so no page is requested beyond it: a range
        that fills every page below it raises ``_OffsetCapReachedError`` once the last one is read.
        """
        for offset in range(0, _MAX_OFFSET + 1, _PAGE_LIMIT):
            url = (
                f"{_BASE_URL}/stationValue/items?stationId={station_id}"
                f"&timeResolution={time_resolution}&datetime={start}/{end}"
                f"&limit={_PAGE_LIMIT}&offset={offset}"
            )
            file = download_file(
                url=url,
                cache_dir=settings.cache_dir,
                ttl=CacheExpiry.FIVE_MINUTES,
                client_kwargs=settings.fsspec_client_kwargs,
                cache_disable=settings.cache_disable,
                use_certifi=settings.use_certifi,
            )
            # a station with no data for the window answers an empty (200) page, so any failure here
            # is an outage, a 404 included, and is raised: swallowed it read as a station without
            # data (GH-2461). A failed connection (NoInternetError) is raised the same way, ending the
            # whole read: the next window would meet it too (GH-2640)
            file.raise_if_exception()
            if isinstance(file.content, Exception):
                raise file.content
            df = pl.read_json(file.content, schema=_STATION_VALUE_SCHEMA)
            df = df.select(pl.col("features").explode(empty_as_null=True).struct.field("properties")).unnest(
                "properties"
            )
            if not df.is_empty():
                yield df
            if df.height < _PAGE_LIMIT:
                return
        msg = f"{start}/{end} holds more records than the pages up to offset {_MAX_OFFSET} carry"
        raise _OffsetCapReachedError(msg)

    def _fetch_station_value_pages(
        self,
        station_id: str,
        time_resolution: str,
        start: dt.datetime,
        end: dt.datetime,
        settings: Settings,
        records: list[pl.DataFrame],
    ) -> None:
        """Append every page of DMI stationValue records for a station/resolution/date range to ``records``.

        A range whose records fill all the pages DMI lets one request reach is halved and each half
        read on its own, down to a span of a second, so no request asks for an offset above the cap.
        The two halves share their boundary instant, as DMI's datetime filter includes both ends.
        """
        read = len(records)
        try:
            records.extend(
                self._iter_station_value_pages(
                    station_id,
                    time_resolution,
                    start.strftime(_DATETIME_FORMAT),
                    end.strftime(_DATETIME_FORMAT),
                    settings,
                )
            )
        except _OffsetCapReachedError as error:
            del records[read:]
            middle = start + dt.timedelta(seconds=int((end - start).total_seconds() // 2))
            if middle <= start:
                url = f"{_BASE_URL}/stationValue/items"
                raise DownloadError(url, str(error)) from error
            self._fetch_station_value_pages(station_id, time_resolution, start, middle, settings, records)
            self._fetch_station_value_pages(station_id, time_resolution, middle, end, settings, records)

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        if isinstance(parameter_or_dataset, DatasetModel):
            dataset = parameter_or_dataset
        elif isinstance(parameter_or_dataset, ParameterModel):
            dataset = parameter_or_dataset.dataset
        else:
            return pl.DataFrame()

        settings = cast("Settings", self.sr.request.settings)
        start_date = self.sr.start
        end_date = self.sr.end
        if not start_date or not end_date:
            return pl.DataFrame()
        resolution = dataset.resolution.value
        time_resolution = self._resolution_to_time_resolution[resolution]
        # DMI matches its datetime filter against each aggregate's `from` *instant*. For
        # day/month/year aggregates `from` is the local civil period start, which sits a few
        # hours off the UTC-midnight label this provider assigns (e.g. a Danish summer day
        # starts at 22:00Z the previous day), so a boundary period would otherwise be dropped.
        # Widen the requested window by a day on each side for those resolutions;
        # TimeseriesValues.query() trims the result back to the exact requested range by the
        # assigned `timestamp`. Hourly aggregates are already UTC-aligned (label == `from`), so no
        # margin is needed at the end and none is added -- widening would only fetch extra data. The
        # values of the last 12 and 24 hours are stamped by their `to`, an hour after their `from`, so
        # a value stamped at the start of the window has its `from` an hour before it. The
        # request's bounds are UTC, so the "Z" filter is true.
        margin = dt.timedelta(0) if resolution == Resolution.HOURLY else dt.timedelta(days=1)
        start = start_date - (dt.timedelta(hours=1) if resolution == Resolution.HOURLY else margin)
        end = end_date + margin

        # DMI returns every parameter for the station in one response; keep only the ones
        # mapped in this dataset's metadata (their raw parameterId is name_original).
        known_parameters = {parameter.name_original for parameter in dataset.parameters}

        # a long range is read as consecutive windows, DMI refusing offsets above _MAX_OFFSET; the
        # windows share their boundary instant (DMI's datetime filter includes both ends), so a
        # record at it is read twice and the identical rows are dropped. Without a connection the
        # read ends with the pages got so far, as it always did
        span = _WINDOW_SPAN.get(resolution)
        window_start = start
        records: list[pl.DataFrame] = []
        while True:
            window_end = min(window_start + span, end) if span else end
            self._fetch_station_value_pages(station_id, time_resolution, window_start, window_end, settings, records)
            if window_end >= end:
                break
            window_start = window_end
        if not records:
            return pl.DataFrame()

        # the heating degree days of Greenland are read as those of Denmark: one parameter, `heating_degree_day`
        df = (
            pl.concat(records)
            .with_columns(pl.col("parameterId").replace(_FIELD_SERVED_AS))
            .filter(pl.col("parameterId").is_in(known_parameters))
            .unique(maintain_order=True)
        )
        if df.is_empty():
            return pl.DataFrame()
        # the 0 of a calm wind, the -0.1 of a trace and the 999 of a missing snow depth are mapped before anything is
        # made of the value, and stay as `raw:0` (GH-2794), `raw:-0.1` (GH-3621) and `raw:999`; a value outside the
        # range of its parameter is the core's to judge (`model/judge.py`)
        value, raw = null_sentinels(pl.col("value"), _CALM_WIND, _TRACE, _MISSING_SNOW_DEPTH, text=False)
        # the radiation of a day, a month and a year is written in MJ/m2 and declared in kJ/m2 (GH-3622); the rounding
        # takes the float error of the product away, DMI's values having one decimal
        for name, factor in _TO_DECLARED_UNIT.get(dataset.resolution.name, {}).items():
            value = pl.when(pl.col("parameterId").eq(name)).then((value * factor).round(3)).otherwise(value)
        # the station, resolution and dataset, the order of the columns and the dtypes are the core's to write
        # (`shape_provider_frame`); a frame without a row is the empty long form there, whatever it holds
        timestamp = self._date_expression(resolution)
        if resolution == Resolution.HOURLY:
            end_of_window = (
                pl.col("to").str.to_datetime("%Y-%m-%dT%H:%M:%S%.f%z", time_unit="us").dt.convert_time_zone("UTC")
            )
            timestamp = (
                pl.when(pl.col("parameterId").is_in(_STAMPED_BY_THE_END_OF_THE_WINDOW))
                .then(end_of_window)
                .otherwise(timestamp)
            )
        return df.select(
            pl.col("parameterId").alias("parameter"),
            timestamp.alias("timestamp"),
            value.alias("value"),
            _quality_flags(raw),
        )


def _quality_flags(raw: pl.Expr) -> pl.Expr:
    """Write DMI's ``qcStatus`` and ``validity`` of a record as its ``quality_flags``.

    ``qcStatus`` (``manual``: quality controlled by DMI's climatologists, ``none``: not controlled) is the
    plain code and ``validity`` follows as ``validity:true`` or ``validity:false``. DMI documents
    ``validity`` as "whether or not the value is considered valid by the climatologists. Invalid data is
    generally not correct", and sets it ``false`` for Greenland and, rarely, Denmark. The value of such a
    record is kept unless it is outside the physical range of its parameter, so a caller can drop it by the flag
    (GH-2797). ``raw`` is the text a mapped sentinel or an impossible value was written with (``raw:0`` of a calm
    wind, GH-2794; ``raw:-0.1`` of a trace of precipitation, GH-3621; ``raw:17802`` of a month of rain, GH-2797),
    which closes the column.
    """
    return join_quality_flags(pl.col("qcStatus"), validity=pl.col("validity"), raw=raw)


@dataclass
class DmiObservationRequest(TimeseriesRequest):
    """Request class for DMI (Danish Meteorological Institute) climate data observations.

    - https://www.dmi.dk/friedata/
    - https://www.dmi.dk/friedata/dokumentation/climate-data
    """

    metadata = DmiObservationMetadata
    _values = DmiObservationValues

    _endpoint = f"{_BASE_URL}/station/items?limit={_PAGE_LIMIT}"

    # extend base columns of core class with the country a station is in, as DMI's three-letter code
    # (`DNK`, `GRL` or `FRO`). DMI gives no sub-national region, so `region` stays null
    _base_columns: ClassVar = (
        *TimeseriesRequest._base_columns,  # noqa: SLF001
        "country",
    )

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
        df = pl.read_json(file.content, schema=_STATION_SCHEMA)
        # `explode` makes a null row of an empty list: a list without a station is no station, not a null one
        df = df.select(pl.col("features").explode(empty_as_null=True)).drop_nulls()
        if df.is_empty():
            return pl.LazyFrame()
        df = df.unnest("features")
        df = df.select(
            pl.col("properties").struct.field("stationId").alias("station_id"),
            pl.col("properties").struct.field("name").alias("name"),
            pl.col("properties").struct.field("country").alias("country"),
            pl.col("geometry").struct.field("coordinates").list.get(1).alias("latitude"),
            pl.col("geometry").struct.field("coordinates").list.get(0).alias("longitude"),
            pl.col("properties").struct.field("stationHeight").alias("elevation"),
            # %.f tolerates an optional fractional-seconds part; DMI's station timestamps are
            # observed at second precision but emit fractional seconds elsewhere, so parse
            # defensively (matching the hourly `from` parser).
            pl.col("properties")
            .struct.field("validFrom")
            .str.to_datetime("%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
            .alias("start_timestamp"),
            pl.col("properties")
            .struct.field("validTo")
            .str.to_datetime("%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
            .alias("end_timestamp"),
            pl.col("properties").struct.field("created").alias("created"),
        )
        # DMI lists a station once per validity period. Collapse to one row per station: keep the
        # current metadata (name, country, coordinates, elevation) and span the full active range
        # (earliest validFrom; a null validTo on any record means "still active" -> null).
        # The current record is the one still open (validTo null), else the one that ended last, and
        # of records that tie the one that began last, was written last, and stands last in the list.
        # `created` is the time DMI wrote a record to the list, not the time its metadata began, and
        # is the same on 964 of the 967 stations with several records, so it only breaks a tie
        # (GH-2946). The sort sits inside the aggregation, which makes it independent of the order
        # of the groups.
        current = [
            pl.col("end_timestamp").is_null(),
            pl.col("end_timestamp"),
            pl.col("start_timestamp"),
            pl.col("created"),
            pl.int_range(pl.len()),
        ]

        def newest(column: str) -> pl.Expr:
            return pl.col(column).sort_by(current, descending=True, nulls_last=True).first().alias(column)

        df = df.group_by("station_id", maintain_order=True).agg(
            newest("name"),
            newest("country"),
            newest("latitude"),
            newest("longitude"),
            newest("elevation"),
            pl.col("start_timestamp").min(),
            pl.when(pl.col("end_timestamp").is_null().any())
            .then(None)
            .otherwise(pl.col("end_timestamp").max())
            .alias("end_timestamp"),
        )
        # one catalogue for every dataset: the core copies it over the request's datasets
        return df.lazy()
