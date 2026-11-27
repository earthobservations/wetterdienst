# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Geosphere observation data provider."""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, ClassVar, cast
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.exceptions import DownloadError
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
    from typing import BinaryIO

    from wetterdienst.model.metadata import ParameterModel
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

# The daily dataset (klima-v2-1d) writes "none" as -1 in these columns; its metadata says so in each description, e.g.
# rr: "..., -1=kein Niederschlag, 0=weniger als 1/10 mm" and sh_manu: "..., -1=kein Schnee". The 10-minute, hourly and
# monthly datasets state no such code. -1 is no gap but a dry day or a day without snow, so it is 0.0 and not null:
# a null would drop the day from a sum and leave the series with holes. The columns declared by the provider are
# listed (rr_i and rr_iii carry the same code in the source and are not declared). The value keeps the code as the
# `raw` token of its `quality_flags` (GH-2759), as the response writes it (GH-4489): the response is read with its
# numbers as text (`_read_response`), because a column writes -1.0 where it holds a gap and -1 where it holds none
# (station 5904 in `rr`: -1 for 1991-04-01 to 03 and -1.0 in 2024), which a number no longer tells.
_NONE_IS_MINUS_ONE = {
    "klima-v2-1d": ("rr", "sh", "sh_manu", "shneu_manu"),
}

# The mean wind direction `dd` is "Windrichtung [360°]" (the API's description of the 10 minute and the hourly dataset)
# and is written 0 for a calm wind (the array of a response is written with decimals, `0.0`, when it holds a gap, and
# without, `0`, when it holds none): in the hourly dataset of 2024 for 25 stations spread over the list, and the 10
# minute dataset of June 2024, 816 of 170,385 hours and 638 of 99,019 intervals have a direction of 0, **all** of them
# with a wind speed `ff` of 0.0 (Aflenz, 2024-01-02 19:00: dd 0, ff 0.0), and 292 and 291 have 360. The direction of
# the gust, `ddx`, has no 0 in 170,280 and 99,014 values (the same hour has ddx 358 and ffx 2.1). The 0 is no bearing,
# so it is null (GH-2794), with the text the response wrote for it (`0`, or `0.0`) as the `raw` token.
_CALM_WIND = Sentinel("0", where=pl.col("parameter") == "dd")

# The quality flag of a parameter is the parameter's name and this suffix (`tl` and `tl_flag`), in the four klima-v2
# datasets alike, and the API serves it as a parameter of its own: asked for beside the value, so that both come in
# the one response (GH-4480). Its code list is q21 (`code_lists` of the dataset's `/metadata`): null undefiniert,
# 0 ungeprüfte Daten, 10 to 12 automatisch geprüft, 20 to 22 manuell geprüft. It is the plain code of `quality_flags`.
# One exception: the flag of the reduced air pressure (`pred`) of the hourly dataset has no `code_list_ref` in the
# metadata, so it is not documented with a code list; it is read like the others, and its value is written as the
# source gives it.
_FLAG_SUFFIX = "_flag"

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
    # The flags are asked for beside the values and count as points too, so a request holds twice the points the
    # budget was made for: at most 800,000, still under the limit (measured 2026-11: 24 parameters and their 24 flags
    # for 16,666 timestamps at 10 minutes, 800,000 points, answered in 6.9 s), and the windows stay as many.
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
        # the flag of each parameter, in the one request that holds the values
        asked = [*parameters, *(f"{parameter}{_FLAG_SUFFIX}" for parameter in parameters)]
        url = self._endpoint.format(
            station_id=station_id,
            parameter=",".join(asked),
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
        df = _read_response(url, file.content, parameters)
        # before the unit conversion, which would take the -1 for an amount of one unit
        none_coded = [
            Sentinel("-1", where=pl.col("parameter") == parameter, to=0.0)
            for parameter in _NONE_IS_MINUS_ONE.get(dataset.name_original, ())
        ]
        # the value is the text of the response, so the `raw` token is the text as the source wrote it (`-1`, `-1.0`)
        value, raw = null_sentinels(pl.col("value"), *none_coded, _CALM_WIND, text=True)
        # the station, resolution and dataset are the core's to write (`shape_provider_frame`)
        return df.select(
            pl.col("parameter").str.to_lowercase(),
            pl.col("timestamp").str.to_datetime("%Y-%m-%dT%H:%M+%Z"),
            value.cast(pl.Float64, strict=False).alias("value"),
            # the source's flag first, as it writes it (`10`), then the -1 the 0.0 was made from, as it writes that
            join_quality_flags(pl.col("flag"), raw=raw),
        )


def _incomplete(url: str, what: str) -> DownloadError:
    """Make the error of a response that cannot be read as the values it was asked for, naming the URL."""
    return DownloadError(url, f"the response is incomplete: {what}")


def _parameters_of(url: str, content: BinaryIO) -> tuple[list[str], dict[str, object]]:
    """Read the timestamps and the parameters of the one feature of a response, the numbers still the text it wrote.

    The standard library's reader hands the text of a number to ``parse_int`` and ``parse_float``: ``-1`` and ``-1.0``
    are two texts, which polars' JSON reader makes one number. It costs no more than polars' (5 MB in 0.05 s).
    """
    try:
        body = json.load(content, parse_int=str, parse_float=str, parse_constant=str)
    except (ValueError, UnicodeDecodeError) as error:
        raise _incomplete(url, "it is no JSON") from error
    timestamps = body.get("timestamps") if isinstance(body, dict) else None
    features = body.get("features") if isinstance(body, dict) else None
    if not isinstance(timestamps, list):
        raise _incomplete(url, "it has no timestamps")
    if not isinstance(features, list) or not features:
        raise _incomplete(url, "it has no feature, and so no data of the station")
    if len(features) > 1:
        raise _incomplete(url, f"it has {len(features)} features for the one station asked for")
    try:
        data = features[0]["properties"]["parameters"]
    except (KeyError, TypeError) as error:
        raise _incomplete(url, "the feature has no parameters") from error
    if not isinstance(data, dict):
        raise _incomplete(url, "the feature has no parameters")
    return timestamps, data


def _read_response(url: str, content: BinaryIO, parameters: list[str]) -> pl.DataFrame:
    """Read the response of one window as the frame of a reading per row, with its numbers as the source wrote them.

    The columns are ``parameter``, ``timestamp`` (text), ``value`` (text, as the response writes the number) and
    ``flag`` (the flag as a whole number, null where the source gives none).

    A response that cannot be read as the readings of every parameter asked for is no gap in the data but a broken
    answer, so it is a `DownloadError` that names the URL (GH-4490): no feature (the station was asked for), a
    parameter's array that is left out or does not have one value to each timestamp. The flag of a parameter may be
    left out (an archive that serves the values only), and is then a list of gaps.
    """
    timestamps, data = _parameters_of(url, content)

    def _array(name: str, *, required: bool) -> pl.Series | None:
        entry = data.get(name)
        array = entry.get("data") if isinstance(entry, dict) else None
        if array is None and not required:
            return None
        if not isinstance(array, list):
            raise _incomplete(url, f"the data of {name} are left out")
        if len(array) != len(timestamps):
            raise _incomplete(url, f"{name} has {len(array)} values for {len(timestamps)} timestamps")
        try:
            return pl.Series(array, dtype=pl.String)
        except (TypeError, pl.exceptions.PolarsError) as error:
            raise _incomplete(url, f"{name} holds something that is no number") from error

    frames = []
    for name in parameters:
        values = _array(name, required=True)
        flags = _array(f"{name}{_FLAG_SUFFIX}", required=False)
        # a flag is a whole number, but the source writes a column that has a gap with decimals (`10.0`)
        flag = (
            flags.cast(pl.Float64, strict=False).cast(pl.Int64, strict=False)
            if flags is not None
            else pl.Series([None] * len(timestamps), dtype=pl.Int64)
        )
        frames.append(
            pl.DataFrame(
                {
                    "parameter": pl.Series([name] * len(timestamps), dtype=pl.String),
                    "timestamp": pl.Series(timestamps, dtype=pl.String),
                    "value": values,
                    "flag": flag,
                }
            )
        )
    return pl.concat(frames)


@dataclass
class GeosphereObservationRequest(TimeseriesRequest):
    """Request class for geosphere observation data."""

    metadata = GeosphereObservationMetadata
    _values = GeosphereObservationValues

    _endpoint = "https://dataset.api.hub.geosphere.at/v1/station/historical/{dataset}/metadata/stations"

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
