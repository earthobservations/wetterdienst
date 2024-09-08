# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import json
import logging
from enum import Enum
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file
from wetterdienst.util.parameter import DatasetTreeCore

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Sequence

    from wetterdienst.metadata.parameter import Parameter
    from wetterdienst.settings import Settings

log = logging.getLogger(__file__)


class EAHydrologyResolution(Enum):
    MINUTE_15 = Resolution.MINUTE_15.value
    HOUR_6 = Resolution.HOUR_6.value
    DAILY = Resolution.DAILY.value


class EAHydrologyParameter(DatasetTreeCore):
    class MINUTE_15(DatasetTreeCore):
        class MINUTE_15(Enum):
            DISCHARGE = "flow"
            GROUNDWATER_LEVEL = "groundwater_level"

        DISCHARGE = MINUTE_15.DISCHARGE
        GROUNDWATER_LEVEL = MINUTE_15.GROUNDWATER_LEVEL

    class HOUR_6(DatasetTreeCore):
        class HOUR_6(Enum):
            DISCHARGE = "flow"
            GROUNDWATER_LEVEL = "groundwater_level"

        DISCHARGE = HOUR_6.DISCHARGE
        GROUNDWATER_LEVEL = HOUR_6.GROUNDWATER_LEVEL

    class DAILY(DatasetTreeCore):
        class DAILY(Enum):
            DISCHARGE = "flow"
            GROUNDWATER_LEVEL = "groundwater_level"

        DISCHARGE = DAILY.DISCHARGE
        GROUNDWATER_LEVEL = DAILY.GROUNDWATER_LEVEL


PARAMETER_MAPPING = {"discharge": "Water Flow", "groundwater_level": "Groundwater level"}


class EAHydrologyUnit(DatasetTreeCore):
    class MINUTE_15(DatasetTreeCore):
        class MINUTE_15(UnitEnum):
            DISCHARGE = OriginUnit.CUBIC_METERS_PER_SECOND.value, SIUnit.CUBIC_METERS_PER_SECOND.value
            GROUNDWATER_LEVEL = OriginUnit.METER.value, SIUnit.METER.value

    class HOUR_6(DatasetTreeCore):
        class HOUR_6(UnitEnum):
            DISCHARGE = OriginUnit.CUBIC_METERS_PER_SECOND.value, SIUnit.CUBIC_METERS_PER_SECOND.value
            GROUNDWATER_LEVEL = OriginUnit.METER.value, SIUnit.METER.value

    class DAILY(DatasetTreeCore):
        class DAILY(UnitEnum):
            DISCHARGE = OriginUnit.CUBIC_METERS_PER_SECOND.value, SIUnit.CUBIC_METERS_PER_SECOND.value
            GROUNDWATER_LEVEL = OriginUnit.METER.value, SIUnit.METER.value


class EAHydrologyPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value


class EAHydrologyValues(TimeseriesValues):
    _url = "https://environment.data.gov.uk/hydrology/id/stations/{station_id}.json"
    _data_tz = Timezone.UK

    def _collect_station_parameter(
        self,
        station_id: str,
        parameter: Enum,
        dataset: Enum,  # noqa: ARG002
    ) -> pl.DataFrame:
        url = self._url.format(station_id=station_id)
        log.info(f"Downloading file {url}.")
        payload = download_file(url=url, settings=self.sr.stations.settings, ttl=CacheExpiry.NO_CACHE)
        measures_data = json.load(payload)["items"][0]["measures"]
        s_measures = pl.Series(name="measure", values=measures_data).to_frame()
        s_measures = s_measures.filter(
            pl.col("measure")
            .struct.field("parameterName")
            .str.to_lowercase()
            .str.replace(" ", "")
            .eq(parameter.value.lower().replace("_", "")),
        )
        try:
            measure_dict = s_measures.get_column("measure")[0]
        except IndexError:
            return pl.DataFrame()
        readings_url = f"{measure_dict['@id']}/readings.json"
        log.info(f"Downloading file {readings_url}.")
        payload = download_file(url=readings_url, settings=self.sr.stations.settings, ttl=CacheExpiry.FIVE_MINUTES)
        data = json.loads(payload.read())["items"]
        df = pl.from_dicts(data)
        df = df.select(pl.lit(parameter.value).alias("parameter"), pl.col("dateTime"), pl.col("value"))
        df = df.rename(mapping={"dateTime": Columns.DATE.value, "value": Columns.VALUE.value})
        return df.with_columns(pl.col(Columns.DATE.value).str.to_datetime(format="%Y-%m-%dT%H:%M:%S", time_zone="UTC"))


class EAHydrologyRequest(TimeseriesRequest):
    _provider = Provider.EA
    _kind = Kind.OBSERVATION
    _tz = Timezone.UK
    _parameter_base = EAHydrologyParameter
    _unit_base = EAHydrologyUnit
    _resolution_base = EAHydrologyResolution
    _resolution_type = ResolutionType.MULTI
    _period_type = PeriodType.FIXED
    _period_base = EAHydrologyPeriod
    _has_datasets = False
    _data_range = DataRange.FIXED
    _values = EAHydrologyValues

    _url = "https://environment.data.gov.uk/hydrology/id/stations.json"

    def __init__(
        self,
        parameter: str | EAHydrologyParameter | Parameter | Sequence[str | EAHydrologyParameter | Parameter],
        resolution: str | EAHydrologyResolution | Resolution,
        start_date: str | dt.datetime | None = None,
        end_date: str | dt.datetime | None = None,
        settings: Settings | None = None,
    ):
        super().__init__(
            parameter=parameter,
            resolution=resolution,
            period=Period.HISTORICAL,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

        if self.resolution == Resolution.MINUTE_15:
            self._resolution_as_int = 900
        elif self.resolution == Resolution.HOUR_6:
            self._resolution_as_int = 3600
        else:
            self._resolution_as_int = 86400

    def _all(self) -> pl.LazyFrame:
        """
        Get stations listing UK environment agency data
        :return:
        """
        log.info(f"Acquiring station listing from {self._url}")
        payload = download_file(self._url, self.settings, CacheExpiry.FIVE_MINUTES)
        data = json.load(payload)["items"]
        for station in data:
            self._transform_station(station)
        df = pl.from_dicts(data)
        # filter for stations that have wanted resolution and parameter combinations
        df_measures = (
            df.select(pl.col("notation"), pl.col("measures"))
            .explode("measures")
            .with_columns(pl.col("measures").struct.field("parameter"))
        )
        df_measures = df_measures.group_by(["notation"]).agg(
            (pl.col("parameter").list.set_intersection(["flow", "level"]).len() > 0).alias("has_measures")
        )
        df_measures = df_measures.filter("has_measures").select("notation")
        df = df.join(df_measures, how="inner", on="notation")
        df = df.rename(mapping=lambda col: col.lower())
        df = df.rename(
            mapping={
                "label": Columns.NAME.value,
                "lat": Columns.LATITUDE.value,
                "long": Columns.LONGITUDE.value,
                "notation": Columns.STATION_ID.value,
                "dateopened": Columns.START_DATE.value,
                "dateclosed": Columns.END_DATE.value,
            },
        )
        df = df.with_columns(
            pl.col("start_date").str.to_datetime(format="%Y-%m-%d"),
            pl.col("end_date").str.to_datetime(format="%Y-%m-%d"),
        )
        return df.lazy()

    @staticmethod
    def _transform_station(station: dict) -> None:
        """Reduce station dictionary to required keys and format dateOpened and dateClosed."""
        required_keys = ["label", "notation", "lat", "long", "dateOpened", "dateClosed", "measures"]
        for key in list(station.keys()):
            if key not in required_keys:
                del station[key]
        if isinstance(station["dateOpened"], list):
            station["dateOpened"] = station["dateOpened"][1]
        if "dateClosed" not in station:
            station["dateClosed"] = None
