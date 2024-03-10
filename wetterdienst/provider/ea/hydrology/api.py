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

    from wetterdienst.metadata.parameter import Parameter
    from wetterdienst.settings import Settings

log = logging.getLogger(__file__)


class EaHydrologyResolution(Enum):
    MINUTE_15 = Resolution.MINUTE_15.value
    HOUR_6 = Resolution.HOUR_6.value
    DAILY = Resolution.DAILY.value


class EaHydrologyParameter(DatasetTreeCore):
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


class EaHydrologyUnit(DatasetTreeCore):
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


class EaHydrologyPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value


class EaHydrologyValues(TimeseriesValues):
    _base_url = "https://environment.data.gov.uk/hydrology/id/stations/{station_id}.json"
    _data_tz = Timezone.UK

    def _collect_station_parameter(
        self,
        station_id: str,
        parameter: Enum,
        dataset: Enum,  # noqa: ARG002
    ) -> pl.DataFrame:
        endpoint = self._base_url.format(station_id=station_id)
        log.info(f"Downloading file {endpoint}.")
        payload = download_file(endpoint, self.sr.stations.settings, CacheExpiry.NO_CACHE)
        measures_list = json.load(payload)["items"][0]["measures"]
        measures_list = pl.Series(name="measure", values=measures_list).to_frame()
        measures_list = measures_list.filter(
            pl.col("measure")
            .map_elements(lambda measure: measure["parameterName"])
            .str.to_lowercase()
            .str.replace(" ", "")
            .eq(parameter.value.lower().replace("_", "")),
        )
        try:
            measure_dict = measures_list.get_column("measure")[0]
        except IndexError:
            return pl.DataFrame()
        values_endpoint = f"{measure_dict['@id']}/readings.json"
        log.info(f"Downloading file {values_endpoint}.")
        payload = download_file(values_endpoint, CacheExpiry.FIVE_MINUTES)
        readings = json.loads(payload.read())["items"]
        df = pl.from_dicts(readings)
        df = df.select(pl.lit(parameter.value).alias("parameter"), pl.col("dateTime"), pl.col("value"))
        return df.rename(mapping={"dateTime": Columns.DATE.value, "value": Columns.VALUE.value})


class EaHydrologyRequest(TimeseriesRequest):
    _provider = Provider.EA
    _kind = Kind.OBSERVATION
    _tz = Timezone.UK
    _parameter_base = EaHydrologyParameter
    _unit_base = EaHydrologyUnit
    _resolution_base = EaHydrologyResolution
    _resolution_type = ResolutionType.MULTI
    _period_type = PeriodType.FIXED
    _period_base = EaHydrologyPeriod
    _has_datasets = False
    _data_range = DataRange.FIXED
    _values = EaHydrologyValues

    endpoint = "https://environment.data.gov.uk/hydrology/id/stations.json"

    def __init__(
        self,
        parameter: list[str | EaHydrologyParameter | Parameter],
        resolution: str | EaHydrologyResolution | Resolution,
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
        log.info(f"Acquiring station listing from {self.endpoint}")
        response = download_file(self.endpoint, self.settings, CacheExpiry.FIVE_MINUTES)
        payload = json.load(response)["items"]
        df = pl.DataFrame(payload).lazy()
        # filter for stations that have wanted resolution and parameter combinations
        df_measures = (
            df.select(pl.col("notation"), pl.col("measures"))
            .explode("measures")
            .with_columns(pl.col("measures").map_elements(lambda measure: measure["parameter"]))
            .group_by(["notation"])
            .agg(pl.col("measures").is_in(["flow", "level"]).any().alias("has_measures"))
        )
        df = df.join(df_measures.filter(pl.col("has_measures")), how="inner", on="notation")
        df = df.rename(mapping=lambda col: col.lower())

        return df.rename(
            mapping={
                "label": Columns.NAME.value,
                "lat": Columns.LATITUDE.value,
                "long": Columns.LONGITUDE.value,
                "notation": Columns.STATION_ID.value,
            },
        )
