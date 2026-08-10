# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""WSV Pegelonline provider for water level data in Germany."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, ParameterModel, build_metadata_model
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

FLOAT_9_TIMES = tuple[
    float | None,
    float | None,
    float | None,
    float | None,
    float | None,
    float | None,
    float | None,
    float | None,
    float | None,
]


_STATIONS_ENDPOINT = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations.json?includeTimeseries=true&includeCharacteristicValues=true"

# Pegelonline publishes the unit per timeseries rather than per parameter, and stations disagree,
# so the declared unit in the metadata below is the unit values are scaled *to*. Each entry maps
# every source unit the service is known to use onto that declared unit. A parameter absent from
# this table is published in one unit everywhere; a unit absent from an entry is unhandled and the
# series is skipped rather than reported under the wrong unit.
#
# `m+NN` is metres above sea level and is used by the 66 gauges that have no gauge zero, so the
# datum differs from the cm gauges even after scaling -- see the `gauge_zero` station column.
_SOURCE_UNIT_FACTORS: dict[str, dict[str, float]] = {
    "W": {"cm": 1.0, "m+NN": 100.0, "m+PNP": 100.0},
    "LF": {"µS/cm": 1.0, "mS/cm": 1000.0},
    "VA": {"m/s": 1.0, "cm/s": 0.01},
    "SIGH": {"cm": 1.0, "m": 100.0},
    "MAXH": {"cm": 1.0, "m": 100.0},
    "TP": {"s": 1.0, "1/100s": 0.01},
}


WsvPegelMetadata = {
    "name_short": "WSV",
    "name_english": "Federal Waterways and Shipping Administration",
    "name_local": "Wasserstraßen- und Schifffahrtsverwaltung des Bundes",
    "country": "Germany",
    "copyright": "© Wasserstraßen- und Schifffahrtsverwaltung des Bundes (WSV), Pegelonline",
    "url": "https://pegelonline.wsv.de/webservice/ueberblick",
    "kind": "observation",
    "timezone": "Europe/Berlin",
    "timezone_data": "Europe/Berlin",
    "resolutions": [
        {
            "name": "dynamic",
            "name_original": "dynamic",
            "periods": ["recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "stage",
                            "name_original": "W",
                            "unit": "centimeter",
                        },
                        {
                            "name": "discharge",
                            "name_original": "Q",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "temperature_water",
                            "name_original": "WT",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "electric_conductivity",
                            "name_original": "LF",
                            "unit": "microsiemens_per_centimeter",
                        },
                        {
                            "name": "clearance_height",
                            "name_original": "DFH",
                            "unit": "centimeter",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "LT",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "flow_speed",
                            "name_original": "VA",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "groundwater_level",
                            "name_original": "GRU",
                            "unit": "meter",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "WG",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "humidity",
                            "name_original": "HL",
                            "unit": "percent",
                        },
                        {
                            "name": "oxygen_level",
                            "name_original": "O2",
                            "unit": "milligram_per_liter",
                        },
                        {
                            "name": "turbidity",
                            "name_original": "TR",
                            "unit": "nephelometric_turbidity",
                        },
                        {
                            "name": "flow_direction",
                            "name_original": "R",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "WR",
                            "unit": "degree",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "NIEDERSCHLAG",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_intensity",
                            "name_original": "NIEDERSCHLAGSINTENSITÄT",
                            "unit": "millimeter_per_hour",
                        },
                        {
                            "name": "wave_period",
                            "name_original": "TP",
                            "unit": "second",
                        },
                        {
                            "name": "wave_height_sign",
                            "name_original": "SIGH",
                            "unit": "centimeter",
                        },
                        {
                            "name": "wave_height_max",
                            "name_original": "MAXH",
                            "unit": "centimeter",
                        },
                        {
                            "name": "ph_value",
                            "name_original": "PH",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "chlorid_concentration",
                            "name_original": "CL",
                            "unit": "milligram_per_liter",
                        },
                    ],
                },
            ],
        },
    ],
}
WsvPegelMetadata = build_metadata_model(WsvPegelMetadata, "WsvPegelMetadata")


class WsvPegelValues(TimeseriesValues):
    """Values class for WSV Pegelonline."""

    _endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_id}/{parameter}/measurements.json"
    # Used for getting frequency of timeseries
    _station_endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_id}/{parameter}/"
    _source_units_cache: dict[tuple[str, str], str] | None = None

    def _source_units(self, settings: Settings) -> dict[tuple[str, str], str]:
        """Map (station id, parameter) to the unit that station publishes that parameter in.

        Pegelonline reports the unit per *timeseries*, and stations disagree: water level is cm at
        most gauges but m+NN at 66 of them, conductivity µS/cm or mS/cm, wave height cm or m, wave
        period s or 1/100s. No single declaration in the metadata can be right for all of them, so
        the value has to be scaled to the declared unit per station.

        Read from the same station listing the request already downloads, so this costs no extra
        request beyond what a cached response serves.
        """
        if self._source_units_cache is not None:
            return self._source_units_cache
        file = download_file(
            url=_STATIONS_ENDPOINT,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.ONE_HOUR,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            # deliberately not cached: an empty mapping makes every lookup below miss, which would
            # skip every scaled parameter for the lifetime of the process, long after the listing
            # became reachable again
            return {}
        units: dict[tuple[str, str], str] = {}
        for station in json.load(file.content):
            for timeseries in station.get("timeseries") or []:
                shortname, unit = timeseries.get("shortname"), timeseries.get("unit")
                if shortname and unit:
                    units[station["number"], shortname] = unit
        self._source_units_cache = units
        return units

    def _collect_station_parameter_or_dataset(  # ty: ignore[invalid-method-override]
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        """Collect data for station parameter from WSV Pegelonline.

        REST-API at https://pegelonline.wsv.de/webservices/rest-api/v2/stations/.

        """
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.sr.stations.settings)
        url = self._endpoint.format(station_id=station_id, parameter=parameter_or_dataset.name_original)
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.NO_CACHE,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        if file.is_no_internet_error:
            return pl.DataFrame()
        if isinstance(file.content, FileNotFoundError):
            return pl.DataFrame()
        if isinstance(file.content, Exception):
            raise file.content
        df = pl.read_json(file.content)
        df = df.rename(mapping={"timestamp": "date", "value": "value"})

        name_original = parameter_or_dataset.name_original
        factors = _SOURCE_UNIT_FACTORS.get(name_original)
        factor = 1.0
        if factors is not None:
            source_unit = self._source_units(settings).get((station_id, name_original))
            if source_unit is None:
                # either the station listing was unreachable or this station does not publish the
                # timeseries; in both cases the unit is unknown rather than known to be unhandled
                log.error(
                    f"WSV station {station_id} has no published unit for {name_original} in the "
                    f"station listing; skipping rather than assuming {parameter_or_dataset.unit}",
                )
                return pl.DataFrame()
            if source_unit not in factors:
                # An unrecognised source unit is why this scaling exists at all: values used to be
                # passed through as if every station published the declared unit. Dropping the
                # series is worse than returning it, but returning a number that is silently wrong
                # by a factor of 100 is worse still.
                log.error(
                    f"WSV station {station_id} publishes {name_original} in unhandled unit "
                    f"{source_unit!r}; skipping rather than reporting it as "
                    f"{parameter_or_dataset.unit}",
                )
                return pl.DataFrame()
            factor = factors[source_unit]

        return df.with_columns(
            pl.lit(parameter_or_dataset.dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.dataset.name, dtype=pl.String).alias("dataset"),
            pl.lit(parameter_or_dataset.name_original.lower()).alias("parameter"),
            pl.col("date").str.to_datetime("%Y-%m-%dT%H:%M:%S%z"),
            (pl.col("value") * factor) if factor != 1.0 else pl.col("value"),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )


@dataclass
class WsvPegelRequest(TimeseriesRequest):
    """Request class for WSV Pegelonline.

    Pegelonline is a German river management facility and
    provider of river-based measurements for last 30 days.
    """

    metadata = WsvPegelMetadata
    _values = WsvPegelValues

    _endpoint = _STATIONS_ENDPOINT

    # Characteristic/statistical values may be provided for stations_result
    characteristic_values: ClassVar = {
        "m_i": "first flood marking",
        "m_ii": "second flood marking",
        "m_iii": "third flood marking",
        "mnw": "mean of low water level",
        "mw": "mean of water level",
        "mhw": "mean of high water level",
        "hhw": "highest water level",
        "hsw": "highest of shipping water level",
    }

    # extend base columns of core class with those of characteristic values plus gauge zero
    _base_columns: ClassVar = (
        *TimeseriesRequest._base_columns,  # noqa: SLF001
        "gauge_zero",
        *characteristic_values.keys(),
    )

    def _all(self) -> pl.LazyFrame:
        """Get stations for WSV Pegelonline.

        It involves reading the REST API, doing some transformations
        and adding characteristic values in extra columns if given for each station.
        """
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        file = download_file(
            url=self._endpoint,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.ONE_HOUR,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        df = pl.read_json(
            file.content,
            schema={
                "number": pl.String,
                "shortname": pl.String,
                "km": pl.Float64,
                "latitude": pl.Float64,
                "longitude": pl.Float64,
                "water": pl.Struct(
                    {
                        "shortname": pl.String,
                    },
                ),
                "timeseries": pl.List(
                    pl.Struct(
                        {
                            "shortname": pl.String,
                            "gaugeZero": pl.Struct(
                                {
                                    "value": pl.Float64,
                                },
                            ),
                            "characteristicValues": pl.List(
                                pl.Struct(
                                    {
                                        "shortname": pl.String,
                                        "value": pl.Float64,
                                    },
                                ),
                            ),
                        },
                    ),
                ),
            },
        )
        df = df.lazy()
        df = df.rename(mapping={"number": "station_id", "shortname": "name", "km": "river_kilometer"})
        df = df.with_columns(
            pl.col("water").struct.field("shortname"),
            pl.col("timeseries").list.eval(pl.element().struct.field("shortname").str.to_lowercase()).alias("ts"),
        )
        parameters = {
            parameter.name_original.lower() for parameter in self.parameters if isinstance(parameter, ParameterModel)
        }
        df = df.filter(pl.col("ts").list.set_intersection(list(parameters)).list.len() > 0)
        df = df.with_columns(
            pl.col("timeseries")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "W"))
            .list.first()
            .alias("ts_water"),
        )
        return df.select(
            pl.lit(self.metadata[0].name, dtype=pl.String).alias("resolution"),
            pl.lit(self.metadata[0][0].name, dtype=pl.String).alias("dataset"),
            pl.all().exclude(["timeseries", "ts", "ts_water"]),
            pl.col("ts_water").struct.field("gaugeZero").struct.field("value").alias("gauge_datum"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "M_I"))
            .list.first()
            .struct.field("value")
            .alias("m_i"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "M_II"))
            .list.first()
            .struct.field("value")
            .alias("m_ii"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "M_III"))
            .list.first()
            .struct.field("value")
            .alias("m_iii"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "MNW"))
            .list.first()
            .struct.field("value")
            .alias("mnw"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "MW"))
            .list.first()
            .struct.field("value")
            .alias("mw"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "MHW"))
            .list.first()
            .struct.field("value")
            .alias("mhw"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "HHW"))
            .list.first()
            .struct.field("value")
            .alias("hhw"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "HSW"))
            .list.first()
            .struct.field("value")
            .alias("hsw"),
        )
