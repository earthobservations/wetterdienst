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
from wetterdienst.model.quality_flags import OutOfRange, Sentinel, join_quality_flags, null_sentinels
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
# DMI's other fields (`max_precip_24h` of 04320, 2013-09). It is null and keeps `raw:999.0`.
_MISSING_SNOW_DEPTH = Sentinel("999.0", where=pl.col("parameterId").eq("max_snow_depth"))

# The range of a reading per resolution and parameterId, in the unit DMI writes it in (but the radiation of a day, a
# month and a year, whose bounds are in kJ/m2, the unit the metadata declares: `_TO_DECLARED_UNIT`), outside which no
# sensor can have produced it: the physical ranges of `tests/provider/physical_ranges.py`, generous on purpose, in the
# unit of the source, and no wider than they are (`test_physical_ranges.py` holds them to it). The rain of a span grows
# with it, so `acc_precip` has a bound per resolution; those of a day, a month and a year are narrower than the
# world's, because DMI covers Denmark, the Faroe Islands and Greenland. Read on 2026-10-16 (every station the API
# lists, 4.1 million days and 136,000 months), the values DMI marks `validity: true` run to 183.5 mm in a day (04390,
# 1964), 641.8 in a month and 3,291.3 in a year (04390, 1965), and the values above are marked `validity: false`, among
# them 1978 mm on 14 and 989 mm on 3 days of 2011 at 04339 and 1770 mm on 2021-12-03 at 04360 (24 days of 04360 and
# 04320 are above 500 mm); 17,802 mm (04339, 2011-10), 8,661 mm (04360, 2022-01) and 3,229.9 mm (04339, 2012-10) in a
# month (18 months are above 1,500 mm); 9,574 mm (04339, 2014), 7,196 mm (04390, 2016) and 4,178.9 mm (04320, 2014) in
# a year, none of which a gauge read (GH-2797). Such a value is read as null and keeps its text as `raw:17802`. The
# largest amount of a day in a month (`max_precip_24h`) and the largest of 30 minutes in a day (`max_precip_30m`) are
# no more than a day, so they are held to the day's 500 mm: the monthly `max_precip_24h` has six months above 500,
# among them 1978 mm (04339, 2011-10), 1770 mm (04360, 2021-12) and a 999.0 (04320, 2013-09, the same in the year).
# What lies below a bound stays, and DMI's flag says what it thinks of it: the 3,253.4 mm of 04339 in 2012 is the sum
# of that 3,229.9 and two months of 8.4 and 15.1, and no range separates it from the 3,291.3 mm that DMI validated for
# 04390 (the bound of a year is 4,000).
_AIR_TEMPERATURE = (-90.0, 60.0)  # degree Celsius
_DAY_PRECIPITATION = (0.0, 500.0)  # mm, the most of a day, which the maxima of a part of it cannot pass
_WIND_SPEED = (0.0, 115.0)  # m/s
_HUMIDITY = (0.0, 130.0)  # percent; a hygrometer reads past 100 now and then
# metObs documents 112 for a cloud cover of "sky obscured by fog and/or other meteorological phenomena" beside the 0 to
# 100 of its oktas (https://www.dmi.dk/friedata/dokumentation/meteorological-observations-data, "Cloud_cover", read
# 2026-10-30). No hourly value of January to June 2019 (68,107, 15 stations) nor daily one of 2011 to 2025 (93,519) is
# above 100, but a 112 would be more than the whole sky, and the mean of a day or a month with one in it a wrong one
_CLOUD_COVER = (0.0, 100.0)  # percent
_PRESSURE = (300.0, 1_100.0)  # hPa
_VAPOUR_PRESSURE = (0.0, 100.0)  # hPa; read 2026-10-31 DMI's daily values run to 16.7 (06014) and a year's to 11.3
# at the stations of Denmark, while 109.3 (04219, 2023, `validity: true`) and 312.1 (04211, 2017-01) are not readings
_SOIL_TEMPERATURE = (-90.0, 100.0)  # degree Celsius, the range of any temperature
_SNOW_DEPTH = (-50.0, 1_500.0)  # cm, the range of a snow depth
_COMMON_RANGES: dict[str, tuple[float, float]] = {
    "mean_temp": _AIR_TEMPERATURE,
    "max_temp_w_date": _AIR_TEMPERATURE,
    "min_temp": _AIR_TEMPERATURE,
    "mean_relative_hum": _HUMIDITY,
    "mean_pressure": _PRESSURE,
    "mean_wind_speed": _WIND_SPEED,
    "max_wind_speed_10min": _WIND_SPEED,
    "max_wind_speed_3sec": _WIND_SPEED,
    "mean_wind_dir": (0.0, 360.0),  # degree
    "mean_cloud_cover": _CLOUD_COVER,
}
_HEATING_DEGREE_DAYS = (
    0.0,
    20_000.0,
)  # degree Celsius days; the most of a year read is 18,022.8 (04416 Summit, Greenland, 2011)
# DMI's heating degree days of Greenland (base 19) are the field `acc_heating_degree_days_19`, where those of Denmark
# (base 17) are `acc_heating_degree_days_17`: no station has both, so the one is read as the other and the two are the
# one parameter, `heating_degree_day`. Its range holds for either base: the highest year DMI publishes is 18,022.8
# (04416 Summit on the ice sheet, 2011; 17,747.8 in 2009 and 17,612.7 in 2013) and the highest month 2,114.3 (2011-12),
# so the bound of 20,000 leaves about 10 % above the highest year (read 2026-10-31)
_FIELD_SERVED_AS = {"acc_heating_degree_days_19": "acc_heating_degree_days_17"}
# the highest and lowest pressure of a day, a month and a year, in hPa at sea level
_PRESSURE_EXTREMES = {"max_pressure": _PRESSURE, "min_pressure": _PRESSURE}
# the sunshine cannot last longer than the span it is measured over, with a tenth to spare for an hour, a day and the
# longest month (the range of `physical_ranges.py`), and none for a leap year, whose range has none: minutes of an hour,
# hours of a day, of a month and of a year. DMI's highest (read 2026-10-30) are 60 minutes, 16.5 hours in a day,
# 386.3 in a month and 2,234.4 in a year. The counts of days are those of a year at most
_SUNSHINE_OF_AN_HOUR = (0.0, 66.0)  # minutes
_SUNSHINE_OF_A_DAY = (0.0, 26.4)  # hours
_SUNSHINE_OF_A_MONTH = (0.0, 818.4)  # hours
_SUNSHINE_OF_A_YEAR = (0.0, 8_784.0)  # hours
_DAYS = (0.0, 366.0)
# The radiation of a day, a month and a year is a sum in MJ/m2 that the reader writes in kJ/m2 (`_TO_DECLARED_UNIT`),
# so these bounds are in kJ/m2. No day brings more than 60 MJ/m2 (the sun at the top of the atmosphere on the day of
# the longest daylight at 82 degrees north, where DMI's northernmost station is, is 48), a month is 31 such days, and
# a year keeps the 5,000 MJ/m2 of the range of any year (DMI's highest valid year is 4,533.2, 06141, 2020). The daily
# records of 04339 in January 2021 (up to 284 MJ/m2, `validity: true`, in the polar night) lie above the day's bound.
_RADIATION_OF_A_DAY = (0.0, 60_000.0)
_RADIATION_OF_A_MONTH = (0.0, 1_860_000.0)
_RADIATION_OF_A_YEAR = (0.0, 5_000_000.0)
# DMI's value of a parameter that the metadata declares in another unit is multiplied by this factor after the
# ranges, which are in the unit of the source (the megajoules), have been applied
_TO_DECLARED_UNIT: dict[str, dict[str, float]] = {
    "daily": {"mean_radiation": 1_000.0},
    "monthly": {"mean_radiation": 1_000.0},
    "annual": {"mean_radiation": 1_000.0},
}
_DAY_COUNT_PARAMETERS = (
    "no_ice_days",
    "no_frost_days",
    "no_summer_days",
    "no_tropical_nights",
    "no_days_acc_precip_01",
    "no_days_acc_precip_1",
    "no_days_acc_precip_10",
    "no_cold_days",
    "no_windy_days",
    "no_stormy_days",
    "no_days_w_storm",
    "no_days_w_hurricane",
    "no_days_snow_cover",
    "no_clear_days",
    "no_cloudy_days",
)
_MONTHLY_RANGES: dict[str, tuple[float, float]] = {
    **_COMMON_RANGES,
    "acc_precip": (0.0, 1_500.0),
    "max_precip_24h": _DAY_PRECIPITATION,
    "mean_daily_max_temp": _AIR_TEMPERATURE,
    "mean_daily_min_temp": _AIR_TEMPERATURE,
    "max_relative_hum": _HUMIDITY,
    "min_relative_hum": _HUMIDITY,
    "acc_heating_degree_days_17": _HEATING_DEGREE_DAYS,
    "bright_sunshine": _SUNSHINE_OF_A_MONTH,
    "mean_radiation": _RADIATION_OF_A_MONTH,
    "mean_vapour_pressure": _VAPOUR_PRESSURE,
    "max_snow_depth": _SNOW_DEPTH,
    **_PRESSURE_EXTREMES,
    **dict.fromkeys(_DAY_COUNT_PARAMETERS, _DAYS),
}
_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "hourly": {
        **_COMMON_RANGES,
        "acc_precip": (0.0, 600.0),
        "bright_sunshine": _SUNSHINE_OF_AN_HOUR,
        "mean_radiation": (-200.0, 2_000.0),  # W/m2; the solar constant is 1,361
        "max_temp_12h": _AIR_TEMPERATURE,
        "min_temperature_12h": _AIR_TEMPERATURE,
        # the most of 12 and of 24 hours is no more than the day's; DMI's 989 mm (04339, 2011-10) and 393.6 mm
        # (04360, 2026-04) are `validity: false`
        "acc_precip_past12h": _DAY_PRECIPITATION,
        "acc_precip_past24h": _DAY_PRECIPITATION,
        "temp_soil_10": _SOIL_TEMPERATURE,
    },
    "daily": {
        **_COMMON_RANGES,
        "acc_precip": _DAY_PRECIPITATION,
        "max_precip_30m": _DAY_PRECIPITATION,
        "max_relative_hum": _HUMIDITY,
        "min_relative_hum": _HUMIDITY,
        "acc_heating_degree_days_17": _HEATING_DEGREE_DAYS,
        **_PRESSURE_EXTREMES,
        "bright_sunshine": _SUNSHINE_OF_A_DAY,
        "snow_depth": (-50.0, 1_500.0),  # cm
        "mean_radiation": _RADIATION_OF_A_DAY,
        "mean_vapour_pressure": _VAPOUR_PRESSURE,
        "temp_soil_10": _SOIL_TEMPERATURE,
        **dict.fromkeys(("no_clear_days", "no_cloudy_days"), _DAYS),
    },
    "monthly": _MONTHLY_RANGES,
    "annual": {
        **_MONTHLY_RANGES,
        "acc_precip": (0.0, 4_000.0),
        "bright_sunshine": _SUNSHINE_OF_A_YEAR,
        "mean_radiation": _RADIATION_OF_A_YEAR,
    },
}
# the bounds above are in the unit the metadata declares, and the rules read the value as DMI wrote it
_OUT_OF_RANGE = {
    resolution: tuple(
        OutOfRange(
            low / _TO_DECLARED_UNIT.get(resolution, {}).get(name, 1.0),
            high / _TO_DECLARED_UNIT.get(resolution, {}).get(name, 1.0),
            where=pl.col("parameterId").eq(name),
        )
        for name, (low, high) in ranges.items()
    )
    for resolution, ranges in _RANGES.items()
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

        DMI labels each aggregate by the start of its period. Hourly data is aligned to UTC
        (``from`` carries a ``+00:00`` offset), so it is parsed and normalised to UTC directly.
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
        # the 0 of a calm wind, the -0.1 of a trace and a value outside the range of its parameter are mapped before
        # anything is made of the value, and stay as `raw:0` (GH-2794), `raw:-0.1` (GH-3621) and `raw:17802`
        # (GH-2797); the trace comes before the ranges, whose lower bound would null it
        value, raw = null_sentinels(
            pl.col("value"),
            _CALM_WIND,
            _TRACE,
            _MISSING_SNOW_DEPTH,
            *_OUT_OF_RANGE[dataset.resolution.name],
            text=False,
        )
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
