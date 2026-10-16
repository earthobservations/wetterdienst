# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Geosphere observation data provider."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, ClassVar, cast
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, group_parameters_by_dataset
from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.geosphere.observation.metadata import GeosphereObservationMetadata
from wetterdienst.util.datetime import round_minutes
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from wetterdienst.model.metadata import ParameterModel
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

# The daily dataset (klima-v2-1d) writes "none" as -1 in these columns; its metadata says so in each description, e.g.
# rr: "..., -1=kein Niederschlag, 0=weniger als 1/10 mm" and sh_manu: "..., -1=kein Schnee". The 10-minute, hourly and
# monthly datasets state no such code. -1 is no gap but a dry day or a day without snow, so it is 0.0 and not null:
# a null would drop the day from a sum and leave the series with holes. The columns declared by the provider are
# listed (rr_i and rr_iii carry the same code in the source and are not declared). The value keeps the code as the
# `raw` token of its `quality_flags` (GH-2759), written as the source writes it: -1.0 in the columns of decimals
# (rr and sh) and -1 in the integer ones (sh_manu and shneu_manu), checked on the live API for station 5904.
_NONE_IS_MINUS_ONE = {
    "klima-v2-1d": {"rr": "-1.0", "sh": "-1.0", "sh_manu": "-1", "shneu_manu": "-1"},
}

# The mean wind direction `dd` is "Windrichtung [360°]" (the API's description of the 10 minute and the hourly dataset)
# and is written 0 for a calm wind (the array of a response is written with decimals, `0.0`, when it holds a gap, and
# without, `0`, when it holds none): in the hourly dataset of 2024 for 25 stations spread over the list, and the 10
# minute dataset of June 2024, 816 of 170,385 hours and 638 of 99,019 intervals have a direction of 0, **all** of them
# with a wind speed `ff` of 0.0 (Aflenz, 2024-01-02 19:00: dd 0, ff 0.0), and 292 and 291 have 360. The direction of
# the gust, `ddx`, has no 0 in 170,280 and 99,014 values (the same hour has ddx 358 and ffx 2.1). The 0 is no bearing,
# so it is null (GH-2794).
_CALM_WIND = Sentinel("0", where=pl.col("parameter") == "dd")

# the year of the end date the station list gives to a station that still reports (2100-12-31)
_OPEN_END_YEAR = 2100


def _time_windows(start: dt.datetime, end: dt.datetime, span: timedelta) -> Iterator[tuple[dt.datetime, dt.datetime]]:
    """Split ``[start, end]`` into ``(start, end)`` windows no longer than ``span``.

    The API includes both ends of a window, so a window stops one minute short of where the next
    one starts: a reading on the boundary is neither fetched twice nor lost. Readings sit on
    10-minute marks or coarser.
    """
    cursor = start
    while cursor <= end:
        # compared as a difference, so a span of centuries cannot push the cursor past year 9999
        if end - cursor < span:
            yield cursor, end
            return
        yield cursor, cursor + span - timedelta(minutes=1)
        cursor += span


class GeosphereObservationValues(TimeseriesValues[DatasetModel]):
    """Values class for geosphere observation data."""

    _endpoint = (
        "https://dataset.api.hub.geosphere.at/v1/station/historical/{dataset}?"
        "parameters={parameter}&"
        "start={start_date}&"
        "end={end_date}&"
        "station_ids={station_id}&"
        "output_format=geojson"
    )
    # dates collected from ZAMG website, end date will be set to now if not given
    _default_start_dates: ClassVar = {
        Resolution.MINUTE_10: dt.datetime(1992, 5, 20, tzinfo=ZoneInfo("UTC")),
        Resolution.HOURLY: dt.datetime(1880, 3, 31, tzinfo=ZoneInfo("UTC")),
        Resolution.DAILY: dt.datetime(1774, 12, 31, tzinfo=ZoneInfo("UTC")),
        Resolution.MONTHLY: dt.datetime(1767, 11, 30, tzinfo=ZoneInfo("UTC")),
    }

    # The API refuses a slice of more than 1,000,000 data points with HTTP 400. It counts the points the window
    # asks for, timestamps times parameters (times stations; one here), whatever the station holds. A window is
    # therefore cut to at most _window_points / (number of parameters requested) timestamps, and at most
    # _window_timestamps for one parameter at 10 minutes and hourly. The API answers only once it has built
    # the whole slice, against the client's 30 s read timeout; measured 2026-10 for station 5904, the time
    # grows with the timestamps far more than with the parameters: 10 s for 2 years at 10 minutes with one
    # parameter (105,000 points), 4.1 s for 17,000 timestamps with 23 (400,000 points), 8.4 s for 34,000
    # (790,000), 4.4 s for 21,000 hourly timestamps with 19. The budget keeps a request near 4 s and the
    # cap keeps a few parameters at the 10 s of one. It allows 240 requests an hour, so windows are not
    # smaller: a whole 10-minute dataset is about 105 requests, hourly about 62, daily 4 and monthly 1.
    _window_points = 400_000
    _window_timestamps: ClassVar = {
        Resolution.MINUTE_10: 2 * 365 * 144,  # two years
        Resolution.HOURLY: 10 * 365 * 24,  # ten years
    }
    # the shortest time between two readings, so that a window of n steps never holds more than n of them
    _timesteps: ClassVar = {
        Resolution.MINUTE_10: timedelta(minutes=10),
        Resolution.HOURLY: timedelta(hours=1),
        Resolution.DAILY: timedelta(days=1),
        Resolution.MONTHLY: timedelta(days=28),
    }

    def _window_span(self, resolution: Resolution, n_parameters: int) -> timedelta:
        """Return the longest window the API accepts and answers in time for this many parameters."""
        timestamps = self._window_points // n_parameters
        if resolution in self._window_timestamps:
            timestamps = min(timestamps, self._window_timestamps[resolution])
        return timestamps * self._timesteps[resolution]

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        dataset = parameter_or_dataset
        resolution = dataset.resolution.value
        # the API takes several parameters in one request: those asked for from this dataset, not all of
        # its parameters, so a request for one parameter stays a request for one parameter
        parameters = [
            parameter.name_original
            for parameter in cast("Iterable[ParameterModel]", self.sr.request.parameters)
            if parameter.dataset.resolution.name == dataset.resolution.name and parameter.dataset.name == dataset.name
        ]
        start_date = self.sr.start or self._default_start_dates[resolution]
        # floored to the hour, so a repeat of an open-ended request builds the same URL (the cache key)
        # unless an hour boundary falls between them; the one-day buffer below still reaches past now
        end_date = self.sr.end or round_minutes(datetime.now(ZoneInfo("UTC")), 60)
        # add buffers; the bounds are UTC, where a day is 24 hours, whatever zone the request was made in
        start_date -= timedelta(days=1)
        end_date += timedelta(days=1)
        frames = []
        for window_start, window_end in _time_windows(
            start_date, end_date, self._window_span(resolution, len(parameters))
        ):
            frame = self._collect_window(station_id, dataset, parameters, window_start, window_end)
            # a window without internet comes back as a bare frame without columns (any other failure
            # raises); the whole result is then empty, not a series with years missing
            if not frame.width:
                return pl.DataFrame()
            frames.append(frame)
        return pl.concat(frames) if frames else pl.DataFrame()

    def _collect_window(
        self,
        station_id: str,
        dataset: DatasetModel,
        parameters: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pl.DataFrame:
        url = self._endpoint.format(
            station_id=station_id,
            parameter=",".join(parameters),
            dataset=dataset.name_original,
            start_date=start_date.strftime("%Y-%m-%dT%H:%M"),
            end_date=end_date.strftime("%Y-%m-%dT%H:%M"),
        )
        settings = cast("Settings", self.sr.request.settings)
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=self.sr.settings.fsspec_client_kwargs,
            cache_disable=self.sr.settings.cache_disable,
            use_certifi=self.sr.settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.DataFrame()
        df = pl.read_json(
            file.content,
            schema={
                "timestamps": pl.List(pl.String),
                "features": pl.List(
                    pl.Struct(
                        {
                            "properties": pl.Struct(
                                {
                                    "parameters": pl.Struct(
                                        {
                                            parameter: pl.Struct({"data": pl.List(pl.Float64)})
                                            for parameter in parameters
                                        },
                                    ),
                                },
                            ),
                        },
                    ),
                ),
            },
        )
        # every parameter shares the timestamps, so each row of the unpivoted frame below is one
        # parameter's list of values next to the one list of timestamps
        timestamps = df.get_column("timestamps").to_list()[0]
        df = df.select("features")
        df = df.explode("features", empty_as_null=True)
        df = df.select(pl.col("features").struct.unnest())
        df = df.select(pl.col("properties").struct.field("parameters").struct.unnest())
        df = df.unpivot(
            variable_name="parameter",
            value_name="value",
        )
        df = df.with_columns(
            pl.col("value").struct.field("data").alias("value"),
            pl.lit(timestamps, dtype=pl.List(pl.String)).alias("timestamp"),
        )
        df = df.explode(["value", "timestamp"], empty_as_null=True)
        # before the unit conversion, which would take the -1 for an amount of one unit
        none_coded = [
            Sentinel(text, where=pl.col("parameter") == parameter, to=0.0)
            for parameter, text in _NONE_IS_MINUS_ONE.get(dataset.name_original, {}).items()
        ]
        value, raw = null_sentinels(pl.col("value"), *none_coded, _CALM_WIND, text=False)
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter").str.to_lowercase(),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("timestamp").str.to_datetime("%Y-%m-%dT%H:%M+%Z").dt.replace_time_zone("UTC"),
            value.alias("value"),
            # the -1 the 0.0 was made from, as the source writes it
            join_quality_flags(None, raw=raw),
        )


@dataclass
class GeosphereObservationRequest(TimeseriesRequest):
    """Request class for geosphere observation data."""

    metadata = GeosphereObservationMetadata
    _values = GeosphereObservationValues

    _endpoint = "https://dataset.api.hub.geosphere.at/v1/station/historical/{dataset}/metadata/stations"

    # extend base columns of core class with the station's WMO number, which cross-references it with
    # the WMO lists and with the other providers' stations
    _base_columns: ClassVar = (
        *TimeseriesRequest._base_columns,  # noqa: SLF001
        "wmo_id",
    )

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        data = []
        for dataset, _ in group_parameters_by_dataset(cast("Iterable[ParameterModel]", self.parameters)):
            url = self._endpoint.format(dataset=dataset.name_original)
            file = download_file(
                url=url,
                cache_dir=settings.cache_dir,
                ttl=CacheExpiry.METAINDEX,
                client_kwargs=settings.fsspec_client_kwargs,
                cache_disable=settings.cache_disable,
                use_certifi=settings.use_certifi,
            )
            file.raise_if_exception()
            if isinstance(file.content, Exception):
                return pl.LazyFrame()
            # the WMO number is read as text: it is an identifier, and the catalogue also writes a 7-digit number
            df = pl.read_csv(file.content, schema_overrides={"Synopstationsnummer": pl.String})
            df = df.lazy()
            # only what the request declares is kept: the list also has the flags of the sunshine and radiation
            # sensors and the columns that describe how a station's series is chained to its predecessor's
            df = df.select(
                pl.col("id").alias("station_id"),
                pl.col("Stationsname").alias("name"),
                pl.col("Länge [°E]").alias("longitude"),
                pl.col("Breite [°N]").alias("latitude"),
                pl.col("Höhe [m]").alias("elevation"),
                pl.col("Startdatum").alias("start_timestamp"),
                pl.col("Enddatum").alias("end_timestamp"),
                pl.col("Bundesland").alias("region"),
                # a WMO number is 5 digits; the 7-digit numbers (8989xxx) of 19 stations are no WMO numbers
                pl.when(pl.col("Synopstationsnummer").str.contains(r"^\d{5}$"))
                .then(pl.col("Synopstationsnummer"))
                .alias("wmo_id"),
            )
            df = df.with_columns(
                pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
                pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            )
            data.append(df)
        df = pl.concat(data)
        df = df.with_columns(
            pl.col("start_timestamp").str.to_datetime(format="%Y-%m-%d %H:%M:%S%z", time_zone="UTC"),
            pl.col("end_timestamp").str.to_datetime(format="%Y-%m-%d %H:%M:%S%z", time_zone="UTC"),
        )
        # a station that still reports ends on 2100-12-31 in the list. It has no end, as chmi leaves a station whose
        # list ends it in the year 3999
        return df.with_columns(
            pl.when(pl.col("end_timestamp").dt.year() >= _OPEN_END_YEAR)
            .then(None)
            .otherwise(pl.col("end_timestamp"))
            .alias("end_timestamp"),
        )
