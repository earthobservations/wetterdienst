# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Geosphere observation data provider."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import group_parameters_by_dataset
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


def _time_windows(
    start: dt.datetime, end: dt.datetime, span: timedelta | None
) -> Iterator[tuple[dt.datetime, dt.datetime]]:
    """Split ``[start, end]`` into ``(start, end)`` windows no longer than ``span``.

    The API includes both ends of a window, so a window stops one minute short of where the next
    one starts: a reading on the boundary is neither fetched twice nor lost. Readings sit on
    10-minute marks or coarser. ``span=None`` keeps the window whole.
    """
    if span is None:
        yield start, end
        return
    cursor = start
    while cursor <= end:
        yield cursor, min(cursor + span - timedelta(minutes=1), end)
        cursor += span


class GeosphereObservationValues(TimeseriesValues):
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

    # The API refuses a slice of more than 1,000,000 data points (timestamps times parameters times
    # stations; one parameter and one station here) with HTTP 400. Longer windows are split into
    # requests of at most this span. The spans are far below that limit on purpose: the API answers
    # only once it has built the whole slice, about 5 seconds per year at 10 minutes (measured 2026-10:
    # 10 s for 2 years, 30 s for 6 years) against the client's 30 s read timeout, and it allows 240
    # requests an hour, so they are not smaller either. Daily and monthly reach the limit only after
    # centuries and stay whole.
    _window_spans: ClassVar = {
        Resolution.MINUTE_10: timedelta(days=2 * 365),  # about 105,000 points
        Resolution.HOURLY: timedelta(days=10 * 365),  # about 88,000 points
    }

    def _collect_station_parameter_or_dataset(  # ty: ignore[invalid-method-override]
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        resolution = parameter_or_dataset.dataset.resolution.value
        start_date = self.sr.start or self._default_start_dates[resolution]
        # floored to the hour, so a repeat of an open-ended request builds the same URL (the cache key)
        # unless an hour boundary falls between them; the one-day buffer below still reaches past now
        end_date = self.sr.end or round_minutes(datetime.now(ZoneInfo("UTC")), 60)
        # add buffers; the windows are cut in UTC, where a day is 24 hours, whatever zone the request is in
        start_date = start_date.astimezone(ZoneInfo("UTC")) - timedelta(days=1)
        end_date = end_date.astimezone(ZoneInfo("UTC")) + timedelta(days=1)
        frames = []
        for window_start, window_end in _time_windows(start_date, end_date, self._window_spans.get(resolution)):
            frame = self._collect_window(station_id, parameter_or_dataset, window_start, window_end)
            # a window without internet comes back as a bare frame without columns (any other failure
            # raises); the whole result is then empty, not a series with years missing
            if not frame.width:
                return pl.DataFrame()
            frames.append(frame)
        return pl.concat(frames) if frames else pl.DataFrame()

    def _collect_window(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
        start_date: datetime,
        end_date: datetime,
    ) -> pl.DataFrame:
        url = self._endpoint.format(
            station_id=station_id,
            parameter=parameter_or_dataset.name_original,
            dataset=parameter_or_dataset.dataset.name_original,
            start_date=start_date.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M"),
            end_date=end_date.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M"),
        )
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.sr.stations.settings)
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
                                            parameter_or_dataset.name_original: pl.Struct(
                                                {
                                                    "data": pl.List(pl.Float64),
                                                },
                                            ),
                                        },
                                    ),
                                },
                            ),
                        },
                    ),
                ),
            },
        )
        series_timestamps = df.get_column("timestamps")
        series_timestamps = series_timestamps.explode(empty_as_null=True)
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
        )
        df = df.explode("value", empty_as_null=True)
        return df.select(
            pl.lit(parameter_or_dataset.dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter").str.to_lowercase(),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            series_timestamps.alias("timestamp").str.to_datetime("%Y-%m-%dT%H:%M+%Z").dt.replace_time_zone("UTC"),
            pl.col("value"),
            pl.lit(None, pl.Float64).alias("quality"),
        )


@dataclass
class GeosphereObservationRequest(TimeseriesRequest):
    """Request class for geosphere observation data."""

    metadata = GeosphereObservationMetadata
    _values = GeosphereObservationValues

    _endpoint = "https://dataset.api.hub.geosphere.at/v1/station/historical/{dataset}/metadata/stations"

    def _all(self) -> pl.LazyFrame:
        from typing import cast  # noqa: PLC0415

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
            df = pl.read_csv(file.content)
            df = df.lazy()
            df = df.drop("Sonnenschein", "Globalstrahlung")
            df = df.rename(
                mapping={
                    "id": "station_id",
                    "Stationsname": "name",
                    "Länge [°E]": "longitude",
                    "Breite [°N]": "latitude",
                    "Höhe [m]": "elevation",
                    "Startdatum": "start_timestamp",
                    "Enddatum": "end_timestamp",
                    "Bundesland": "region",
                },
            )
            df = df.with_columns(
                pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
                pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            )
            data.append(df)
        df = pl.concat(data)
        return df.with_columns(
            pl.col("start_timestamp").str.to_datetime(format="%Y-%m-%d %H:%M:%S%z", time_zone="UTC"),
            pl.col("end_timestamp").str.to_datetime(format="%Y-%m-%d %H:%M:%S%z", time_zone="UTC"),
        )
