# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD UV index forecast provider (GH-4089).

DWD publishes the forecast of the UV index for 38 places as one small JSON file,
https://opendata.dwd.de/climate_environment/health/alerts/uvi.json, rewritten once a day in the morning (see
``Beschreibung_uvi.pdf`` beside it)::

    {"name": "UV-Gefahrenindex", "sender": "...", "last_update": "2026-11-17T07:30:00",
     "next_update": "2026-11-18T07:30:00", "forecast_day": "2026-11-17",
     "content": [{"city": "Norderney", "forecast": {"today": 0, "tomorrow": 0, "dayafter_to": 0}}, ...]}

``forecast_day`` is the day ``today`` is of, so a place has the highest UV index of that day, of the next and of the
one after, as whole numbers, which are the three daily values of the station stamped at 00:00 UTC of their date. The
file holds no earlier day and no other model run, so there is no ``issue``: it is the latest forecast, and the date it
was last written is the ``data_updated_at`` of the answer.

The places are the stations. The file names them by their city and gives no position, so ``places.py`` holds the 38
of them with an id, the position and where it is from, and ``_all`` is that table: listing the stations needs no
request. A city of the file that the table does not hold is skipped with a warning that names it, and a place of the
table that the file does not hold is a station without values, with a warning that names it and the `file-skipped`
warning of the answer. A file that is not the one described (not JSON, no ``content``, a place without one of the three
days) is a `DownloadError`, never an answer without rows.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple, NoReturn, cast

import polars as pl

from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.quality_flags import join_quality_flags, null_sentinels
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import UPDATED, TimeseriesValues
from wetterdienst.provider.dwd.uvi.metadata import DwdUviMetadata
from wetterdienst.provider.dwd.uvi.places import PLACES, PLACES_BY_NAME
from wetterdienst.util.network import download_file
from wetterdienst.util.response_warnings import SkipCause, note_skipped_download

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

URL = "https://opendata.dwd.de/climate_environment/health/alerts/uvi.json"
# the days of a place in the file, with how many days after `forecast_day` each is (`Beschreibung_uvi.pdf`: heute,
# morgen, uebermorgen)
_DAYS = (("today", 0), ("tomorrow", 1), ("dayafter_to", 2))
# a file is a few kilobytes, so one that is far larger is not the file
_MAX_BYTES = 1024 * 1024


class UviForecast(NamedTuple):
    """The content of a file: the day ``today`` is of, and for each city the text of the three days."""

    day: dt.date
    cities: dict[str, tuple[str | None, str | None, str | None]]


def _refuse(reason: str, cause: BaseException | None = None) -> NoReturn:
    """Raise the error of a file that is not the UV index forecast: a fault of the source, not of the request."""
    error = DownloadError(URL, f"the file is not the UV index forecast it is described to be: {reason}")
    raise error from cause


def _text(value: object) -> str | None:
    """Give the text of a day's value, so that what the source writes is kept beside a value that is no number.

    A number is written as the file writes it and a null is none. A text is kept, and so is anything else the file holds
    (a list, a dict, ``true``): the core reads it as a value that is no number, with the text as its ``raw:`` token.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def read_forecast(content: bytes) -> UviForecast:
    """Read the file: the day of ``today`` and the three days of every city, as the text the file writes.

    Raises:
        DownloadError: the file is not JSON, is not the object described, holds no city, a city twice, or a city without
            one of its three days. Nothing is guessed: such a file is an upstream change, and answering from what can
            be read of it would hide it.

    """
    try:
        data = json.loads(content)
    except ValueError as error:
        _refuse("it is not JSON", error)
    if not isinstance(data, dict):
        _refuse("it is not a JSON object")
    try:
        day = dt.date.fromisoformat(str(data["forecast_day"])[:10])
    except (KeyError, ValueError) as error:
        _refuse("`forecast_day` is missing or is no date", error)
    entries = data.get("content")
    if not isinstance(entries, list) or not entries:
        _refuse("`content` is missing or holds no place")
    cities: dict[str, tuple[str | None, str | None, str | None]] = {}
    for entry in entries:
        city = entry.get("city") if isinstance(entry, dict) else None
        forecast = entry.get("forecast") if isinstance(entry, dict) else None
        if not isinstance(city, str) or not isinstance(forecast, dict):
            _refuse("a place of `content` has no `city` or no `forecast`")
        missing = [key for key, _ in _DAYS if key not in forecast]
        if missing:
            _refuse(f"the forecast of {city} has no {', '.join(missing)}")
        if city in cities:
            _refuse(f"{city} is listed twice")
        cities[city] = cast(
            "tuple[str | None, str | None, str | None]", tuple(_text(forecast[key]) for key, _ in _DAYS)
        )
    return UviForecast(day, cities)


class DwdUviValues(TimeseriesValues):
    """Values class for DWD UV index forecast."""

    def __post_init__(self) -> None:
        """Post-initialization of the DwdUviValues class."""
        super().__post_init__()
        # the file of this request, read once for all its stations: `None` is "not asked yet", an empty tuple "asked,
        # and there is no file"
        self._file: tuple[UviForecast, dt.datetime | None] | tuple[()] | None = None
        # why there is none, told for every station of the walk, as the core wants it told where a file serves them all
        self._unavailable: SkipCause | None = None

    def _read(self) -> tuple[UviForecast, dt.datetime | None] | tuple[()]:
        """Fetch the file and read it, once for the request, and warn of the cities it holds that no place is kept for.

        A 404 is a file DWD has withdrawn and an empty 200 one it is rewriting: both are warned about and told by
        `file-skipped` as a file let go (`dwd/poi` does the same). Any other failure of the download is an outage,
        which swallowed would read as a day without a forecast, and a file that cannot be read is a
        `DownloadError` (`read_forecast`).
        """
        if self._file is not None:
            return self._file
        settings = cast("Settings", self.sr.request.settings)
        file = download_file(
            url=URL,
            cache_dir=settings.cache_dir,
            # rewritten once a day, in the morning; five minutes is what the other DWD files of one day's use are held
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
            max_bytes=_MAX_BYTES,
        )
        if file.status != 404:
            file.raise_if_exception()
        if isinstance(file.content, Exception):
            self._unavailable = file.skip_cause
            log.warning(f"Failed to fetch the UV index forecast {URL}: {file.content}")
            self._file = ()
            return self._file
        if file.is_empty:
            self._unavailable = SkipCause.MAINTENANCE
            log.warning(f"The UV index forecast {URL} is empty")
            self._file = ()
            return self._file
        forecast = read_forecast(file.content.read())
        unknown = sorted(set(forecast.cities) - set(PLACES_BY_NAME))
        if unknown:
            log.warning(
                f"The UV index forecast holds {len(unknown)} place(s) that have no position here and are skipped: "
                f"{', '.join(unknown)} (GH-4089)"
            )
        self._file = (forecast, file.last_modified)
        return self._file

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        if isinstance(parameter_or_dataset, ParameterModel):
            dataset = parameter_or_dataset.dataset
        elif isinstance(parameter_or_dataset, DatasetModel):
            dataset = parameter_or_dataset
        else:
            return pl.DataFrame()
        read = self._read()
        if not read:
            note_skipped_download(cast("SkipCause", self._unavailable), whole_request=True)
            return pl.DataFrame()
        forecast, last_modified = read
        place = next((place for place in PLACES if place.station_id == station_id), None)
        days = None if place is None else forecast.cities.get(place.name)
        if place is None or days is None:
            # a station of the table that the file does not hold: DWD has dropped the place, or renamed it
            note_skipped_download(SkipCause.UNPARSEABLE)
            log.warning(f"The UV index forecast of {station_id} is not in the file of {forecast.day}")
            return pl.DataFrame()
        columns = [parameter.name_original for parameter in dataset.parameters]
        if not columns:
            return pl.DataFrame()
        df = pl.DataFrame(
            {
                "parameter": [columns[0]] * len(_DAYS),
                # the day of the forecast is a German date: at 00:00 UTC, as every daily stamp of the library is
                "timestamp": [
                    dt.datetime.combine(forecast.day + dt.timedelta(days=offset), dt.time()) for _, offset in _DAYS
                ],
                "value": list(days),
            },
            schema={"parameter": pl.String, "timestamp": pl.Datetime("us"), "value": pl.String},
        )
        # a whole number is the file's, and a text that is no number is no reading: it becomes null and the text stays
        # beside the value as `raw:`, where it would otherwise be a day without a value that says nothing about why
        value, raw = null_sentinels(pl.col("value"), non_numeric=True)
        df = df.select(
            pl.col("parameter"),
            pl.col("timestamp"),
            value.alias("value"),
            join_quality_flags(None, raw=raw),
            pl.lit(last_modified, dtype=pl.Datetime("us", "UTC")).alias(UPDATED),
        )
        return self._note_files_with_rows(df, dataset)


@dataclass
class DwdUviRequest(TimeseriesRequest):
    """Request class for DWD UV index forecast."""

    metadata = DwdUviMetadata
    _values = DwdUviValues

    def _all(self) -> pl.LazyFrame:
        """Return the 38 places of the forecast: the table of `places.py`, which needs no request."""
        return pl.LazyFrame(
            {
                "station_id": [place.station_id for place in PLACES],
                "name": [place.name for place in PLACES],
                "latitude": [place.latitude for place in PLACES],
                "longitude": [place.longitude for place in PLACES],
                "elevation": [place.elevation for place in PLACES],
            },
        )
