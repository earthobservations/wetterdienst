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


_STATIONS_ENDPOINT = (
    "https://pegelonline.wsv.de/webservices/rest-api/v2/"
    "stations.json?includeTimeseries=true&includeCharacteristicValues=true"
)

# Pegelonline publishes the unit per timeseries rather than per parameter, and stations disagree,
# so the declared unit in the metadata below is the unit values are scaled *to*. Each entry maps
# every source unit the service is known to use onto that declared unit. A unit absent from an
# entry is unhandled and the series is skipped rather than reported under the wrong unit. Every
# parameter observed with more than one source unit is listed here; the rest were checked once and
# published one unit everywhere, so a table entry would only ever be an identity.
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
    # FNU and TE/F are the infrared and German names for the same formazin scale as NTU, so they
    # need no scaling; they are listed so that a turbidity unit that is *not* on that scale is
    # skipped rather than passed through
    "TR": {"NTU": 1.0, "FNU": 1.0, "TE/F": 1.0},
}


# Pegelonline publishes an ``equidistance`` in minutes on every timeseries it serves, so a station's
# resolution is a fact read from the station listing rather than something to infer from the data.
# These are the five values the service uses. A timeseries carrying anything else has no matching
# resolution; ``_log_unmapped_equidistances`` reports it rather than letting it disappear.
_EQUIDISTANCE_TO_RESOLUTION: dict[int, str] = {
    1: "1_minute",
    5: "5_minutes",
    10: "10_minutes",
    15: "15_minutes",
    60: "hourly",
}
_RESOLUTION_TO_EQUIDISTANCE: dict[str, int] = {
    resolution: equidistance for equidistance, resolution in _EQUIDISTANCE_TO_RESOLUTION.items()
}


@dataclass(frozen=True)
class TimeseriesMeta:
    """What a station declares about one of its own timeseries.

    Both fields are optional because they are read from the listing rather than promised by it:
    every timeseries carries them today, but a missing one has to mean "unknown" rather than
    silently defaulting to whatever the metadata declares.
    """

    unit: str | None
    equidistance: int | None

    @property
    def resolution(self) -> str | None:
        """The resolution name this interval belongs to, or None if the service uses a new one."""
        if self.equidistance is None:
            return None
        return _EQUIDISTANCE_TO_RESOLUTION.get(self.equidistance)


# reported once per process rather than per request: the listing is scanned whole every time
# `_all` runs, and `filter_by_name` and `filter_by_rank` each run it twice, so a single new
# interval anywhere in the network would otherwise warn on every call
_reported_equidistances: set[int] = set()


def _log_unmapped_equidistances(df: pl.DataFrame) -> None:
    """Report intervals the service publishes that no resolution covers.

    A timeseries recorded at an interval absent from ``_EQUIDISTANCE_TO_RESOLUTION`` belongs to no
    resolution, so it is served under none and its station is listed only for whatever other
    timeseries it records at a mapped interval. That is the right outcome -- better than filing it
    under a neighbouring interval and quietly misdescribing it -- but it is a silent one, and the
    service adding a sixth interval is exactly the change that would need a new member here.
    """
    equidistances = (
        df.select(pl.col("timeseries").list.eval(pl.element().struct.field("equidistance")))
        .explode("timeseries", empty_as_null=True)
        .to_series()
        .drop_nulls()
        .unique()
        .to_list()
    )
    unmapped = sorted(e for e in equidistances if e not in _EQUIDISTANCE_TO_RESOLUTION)
    unreported = [e for e in unmapped if e not in _reported_equidistances]
    if unreported:
        _reported_equidistances.update(unreported)
        log.warning(
            f"WSV Pegelonline publishes timeseries at {unreported} minute intervals, which no "
            f"resolution covers; those timeseries are not served under any resolution",
        )


# Declared once and shared by every resolution below. Which of these a station publishes, and at
# which interval, is a property of that station rather than of the network, and the station listing
# is what answers it -- so a parameter that no station happens to serve at some interval simply
# yields no stations there. `build_metadata_model` copies each parameter dict per resolution, so
# sharing the list here cannot leak one resolution's description into another.
_PARAMETERS = [
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
]


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
            "name": resolution,
            "name_original": resolution,
            "periods": ["recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": _PARAMETERS,
                },
            ],
        }
        for resolution in _EQUIDISTANCE_TO_RESOLUTION.values()
    ],
}
WsvPegelMetadata = build_metadata_model(WsvPegelMetadata, "WsvPegelMetadata")


class WsvPegelValues(TimeseriesValues):
    """Values class for WSV Pegelonline."""

    _endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_id}/{parameter}/measurements.json"
    _timeseries_meta_cache: dict[tuple[str, str], TimeseriesMeta] | None = None

    def _timeseries_meta(self, settings: Settings) -> dict[tuple[str, str], TimeseriesMeta]:
        """Map (station id, parameter) to what that station declares about that timeseries.

        Two things are declared per *timeseries* rather than per parameter, and stations disagree
        on both:

        - the unit. Water level is cm at most gauges but m+NN at 66 of them, conductivity µS/cm or
          mS/cm, wave height cm or m, wave period s or 1/100s. No single declaration in the
          metadata can be right for all of them, so the value is scaled to the declared unit per
          station.
        - the ``equidistance``, the interval in minutes. It is what makes a station belong to one
          of the resolutions rather than another, and 77 of 787 stations mix intervals across
          their own parameters -- PASSAU DONAU records stage every 15 minutes and air temperature
          every 60 -- so it has to be read per timeseries too.

        Read from the same station listing the request already downloads, so this costs no extra
        request beyond what a cached response serves.
        """
        if self._timeseries_meta_cache is not None:
            return self._timeseries_meta_cache
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
        meta: dict[tuple[str, str], TimeseriesMeta] = {}
        for station in json.load(file.content):
            for timeseries in station.get("timeseries") or []:
                shortname = timeseries.get("shortname")
                if shortname:
                    meta[station["number"], shortname] = TimeseriesMeta(
                        unit=timeseries.get("unit"),
                        equidistance=timeseries.get("equidistance"),
                    )
        self._timeseries_meta_cache = meta
        return meta

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
        name_original = parameter_or_dataset.name_original
        meta = self._timeseries_meta(settings).get((station_id, name_original))
        requested_resolution = parameter_or_dataset.dataset.resolution.name
        if meta is None or meta.resolution != requested_resolution:
            # A station that mixes intervals across its own parameters is in the station list under
            # every resolution any of them uses, so asking it for `hourly/data` reaches this method
            # for its 15-minute stage too. Serving that would label a 15-minute series hourly and,
            # with `ts_complete`, reindex it onto an hourly grid that throws away three values in
            # four. The station list already says which resolution this parameter belongs to.
            #
            # `meta is None` is treated the same rather than waved through: it means the station
            # does not publish this timeseries at all, or that the listing was unreachable. In the
            # first case there is nothing to download and the request would only spend a 404; in
            # the second the interval is unknown, and stamping the series with whatever resolution
            # happened to be asked for is the mislabelling this guard exists to prevent.
            return pl.DataFrame()
        url = self._endpoint.format(station_id=station_id, parameter=name_original)
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

        factors = _SOURCE_UNIT_FACTORS.get(name_original)
        factor = 1.0
        if factors is not None:
            source_unit = meta.unit
            if source_unit is None:
                # the timeseries is listed but declares no unit, so the unit is unknown rather than
                # known to be unhandled; the unreachable-listing case is already gone by here
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
            pl.lit(requested_resolution, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.dataset.name, dtype=pl.String).alias("dataset"),
            # not lowercased: `_create_humanized_parameters_mapping` keys on `name_original` as
            # declared, so a lowercased value never matched and WSV silently never humanized --
            # values came back as `sigh` and `r` rather than `wave_height_sign` and
            # `flow_direction`. Unit conversion keys case-insensitively and is unaffected.
            pl.lit(parameter_or_dataset.name_original).alias("parameter"),
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
                            "equidistance": pl.Int64,
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
        _log_unmapped_equidistances(df)
        df = df.lazy()
        df = df.rename(mapping={"number": "station_id", "shortname": "name", "km": "river_kilometer"})
        # matched as published: Pegelonline names every timeseries in upper case, the same case the
        # parameters are declared in, so there is nothing to normalize away here
        # the requested parameters grouped by the resolution they were requested at. Matching the
        # two independently -- any requested parameter, at any requested interval -- lets a station
        # in on a pair nobody asked for: `15_minutes/stage` plus `hourly/temperature_air_mean_2m`
        # would list the gauges that record air temperature every 15 minutes and no stage at all,
        # which then cost a 404 apiece at collection and return nothing
        requested: dict[str, list[str]] = {}
        for parameter in self.parameters:
            if isinstance(parameter, ParameterModel):
                requested.setdefault(parameter.dataset.resolution.name, []).append(parameter.name_original)
        if not requested:
            # unreachable while the dataset stays `grouped: False`, since a dataset request then
            # expands to its parameters. It guards the `concat_list` below, which builds one branch
            # per requested resolution and has no inputs at all to concatenate if there are none
            return pl.LazyFrame()
        df = df.with_columns(
            pl.col("water").struct.field("shortname"),
            # a station belongs to a resolution because it records one of the parameters requested
            # there at that very interval -- not because of anything the network as a whole does.
            # Stations that mix intervals get one row per resolution they record in, and the values
            # class then serves each row only the parameters that belong to it.
            pl.concat_list(
                # ordered by the mapping rather than by the request, so a station that records at
                # two intervals lands in the station list in the same order on every run
                pl.when(
                    pl.col("timeseries")
                    .list.eval(
                        pl.element().filter(
                            pl.element().struct.field("shortname").is_in(requested[resolution])
                            & (pl.element().struct.field("equidistance") == _RESOLUTION_TO_EQUIDISTANCE[resolution]),
                        ),
                    )
                    .list.len()
                    > 0,
                )
                .then(pl.lit(resolution, dtype=pl.String))
                .otherwise(pl.lit(None, dtype=pl.String))
                for resolution in _EQUIDISTANCE_TO_RESOLUTION.values()
                if resolution in requested
            )
            .list.drop_nulls()
            .alias("resolution"),
        )
        # `empty_as_null=False` drops the row outright: an empty list means this station records
        # none of the requested parameters at any of the requested resolutions, which is the same
        # thing the parameter filter used to say and not a station with an unknown resolution
        df = df.explode("resolution", empty_as_null=False)
        df = df.with_columns(
            pl.col("timeseries")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "W"))
            .list.first()
            .alias("ts_water"),
        )
        return df.select(
            pl.col("resolution"),
            pl.lit(DATASET_NAME_DEFAULT, dtype=pl.String).alias("dataset"),
            pl.all().exclude(["timeseries", "ts_water", "resolution"]),
            # must match the name in `_base_columns`, or the reindex there drops it and leaves an
            # all-null `gauge_zero` -- which is the column that says which datum a stage is on
            pl.col("ts_water").struct.field("gaugeZero").struct.field("value").alias("gauge_zero"),
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
