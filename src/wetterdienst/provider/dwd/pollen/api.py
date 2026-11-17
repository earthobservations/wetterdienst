# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD pollen forecast provider (GH-4088).

DWD publishes the forecast of the pollen load for 27 regions of Germany as one small JSON file,
https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json, rewritten once a day in the morning (see
``Beschreibung_pollen_s31fg.pdf`` beside it)::

    {"name": "Pollenflug-Gefahrenindex ...", "sender": "...", "last_update": "2026-11-17 11:00 Uhr",
     "next_update": "2026-11-18 11:00 Uhr", "legend": {"id1": "0", "id1_desc": "keine Belastung", ...},
     "content": [{"region_id": 10, "partregion_id": 11, "region_name": "...", "partregion_name": "...",
                  "Pollen": {"Hasel": {"today": "0", "tomorrow": "0-1", "dayafter_to": "1"}, ...}}, ...]}

The file names no day but the one it was written: ``last_update`` is the German date ``today`` is of, so a region has
the load of each pollen type for that day, the next and the one after, which are the three daily values of the station
stamped at 00:00 UTC of their date. The file holds no earlier day and no other model run, so there is no ``issue``:
it is the latest forecast, and the date it was last written is the ``data_updated_at`` of the answer.

The regions are the stations (``regions.py``). DWD gives them no position, so ``_all`` is the table of 27 and its
latitude, longitude and elevation are null: listing the stations needs no request. A region of the file that the table
does not hold is skipped with a warning that names it, and a region of the table that the file does not hold is a
station without values, with a warning that names it and the `file-skipped` warning of the answer. A file that is not
the one described (not JSON, no ``content``, a region with no ``Pollen``, a pollen type without one of its three
days) is a `DownloadError`, never an answer without rows.

A level is one of the seven steps of the legend (``0``, ``0-1``, ``1``, ``1-2``, ``2``, ``2-3``, ``3``), served as 0,
0.5, 1, 1.5, 2, 2.5 and 3. Any other text, ``-1`` ("Fehlende Werte werden mit einer -1 gekennzeichnet") included, is no
reading: it is null, and the text stays beside it as ``raw:`` in ``quality_flags``.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple, NoReturn, cast

import polars as pl

from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.quality_flags import join_quality_flags
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import UPDATED, TimeseriesValues
from wetterdienst.provider.dwd.pollen.metadata import POLLEN_TYPES, DwdPollenMetadata
from wetterdienst.provider.dwd.pollen.regions import REGIONS, REGIONS_BY_ID, REGIONS_BY_KEY
from wetterdienst.util.network import download_file
from wetterdienst.util.response_warnings import SkipCause, note_skipped_download

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

URL = "https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json"
# the days of a pollen type in the file, with how many days after the day of `last_update` each is
# (`Beschreibung_pollen_s31fg.pdf`: heute, morgen, uebermorgen)
_DAYS = (("today", 0), ("tomorrow", 1), ("dayafter_to", 2))
# the seven steps of the legend of the file (`id1` to `id7`), by the text the file writes, and the number they are
# served as
LEVELS: dict[str, float] = {"0": 0.0, "0-1": 0.5, "1": 1.0, "1-2": 1.5, "2": 2.0, "2-3": 2.5, "3": 3.0}
# a file is 16 kB, so one that is far larger is not the file
_MAX_BYTES = 1024 * 1024
# `last_update` as the file writes it, `2026-11-17 11:00 Uhr`: only the date is read, as the German calendar date
_DATE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\b")

Days = tuple[str | None, str | None, str | None]


class PollenForecast(NamedTuple):
    """The content of a file: the day ``today`` is of, and for each region the text of the three days of each pollen."""

    day: dt.date
    #: by the pair of numbers of the region (``region_id``, ``partregion_id``), then by the pollen type of the file
    regions: dict[tuple[int, int], dict[str, Days]]
    #: the names of the file's regions, for the warning of a region the table does not hold
    names: dict[tuple[int, int], str]
    #: the pollen types of the file that are none of the eight
    unknown_pollen: tuple[str, ...]


def _refuse(reason: str, cause: BaseException | None = None) -> NoReturn:
    """Raise the error of a file that is not the pollen forecast: a fault of the source, not of the request."""
    error = DownloadError(URL, f"the file is not the pollen forecast it is described to be: {reason}")
    raise error from cause


def _text(value: object) -> str | None:
    """Give the text of a day's level, so that what the source writes is kept beside a value that is no step.

    A text is written as the file writes it and a null is none. A number is its JSON text, and so is anything else the
    file holds (a list, a dict, ``true``): the reader takes it for a level or, where it is none, for a value that is no
    number with the text as its ``raw:`` token.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _number(entry: dict[str, object], key: str) -> int:
    """Read a region's ``region_id`` or ``partregion_id``, which the file writes as an integer."""
    value = entry.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        _refuse(f"a region of `content` has no whole number `{key}`")
    return value


def _read_day(data: dict[str, object]) -> dt.date:
    """Read the day ``today`` is of: the German date ``last_update`` begins with (``2026-11-17 11:00 Uhr``)."""
    match = _DATE.match(str(data.get("last_update", "")))
    if match:
        with contextlib.suppress(ValueError):
            return dt.date.fromisoformat(match.group(1))
    _refuse("`last_update` is missing or does not begin with a date")


def _read_pollen(pollen: dict[str, object], key: tuple[int, int], unknown: set[str]) -> dict[str, Days]:
    """Read the three days of every pollen type of a region, and note the types that are none of the eight."""
    by_type: dict[str, Days] = {}
    for pollen_type, days in pollen.items():
        if not isinstance(days, dict):
            _refuse(f"the forecast of {pollen_type} of the region {key} is no object")
        missing = [name for name, _ in _DAYS if name not in days]
        if missing:
            _refuse(f"the forecast of {pollen_type} of the region {key} has no {', '.join(missing)}")
        if pollen_type not in POLLEN_TYPES:
            unknown.add(str(pollen_type))
            continue
        by_type[pollen_type] = cast("Days", tuple(_text(days[name]) for name, _ in _DAYS))
    return by_type


def read_forecast(content: bytes) -> PollenForecast:
    """Read the file: the day of ``today`` and the three days of every pollen type of every region, as the file writes.

    Raises:
        DownloadError: the file is not JSON, is not the object described, has no ``last_update`` date, holds no region,
            a region twice, a region without ``Pollen``, a pollen type without one of its three days, or a pollen type
            of the eight that no region has. Nothing is guessed: such a file is an upstream change, and answering from
            what can be read of it would hide it.

    """
    try:
        data = json.loads(content)
    except ValueError as error:
        _refuse("it is not JSON", error)
    if not isinstance(data, dict):
        _refuse("it is not a JSON object")
    day = _read_day(data)
    entries = data.get("content")
    if not isinstance(entries, list) or not entries:
        _refuse("`content` is missing or holds no region")
    regions: dict[tuple[int, int], dict[str, Days]] = {}
    names: dict[tuple[int, int], str] = {}
    unknown: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            _refuse("a region of `content` is no object")
        key = (_number(entry, "region_id"), _number(entry, "partregion_id"))
        pollen = entry.get("Pollen")
        if not isinstance(pollen, dict):
            _refuse(f"the region {key} has no `Pollen`")
        if key in regions:
            _refuse(f"the region {key} is listed twice")
        regions[key] = _read_pollen(pollen, key, unknown)
        names[key] = ": ".join(str(entry.get(name) or "") for name in ("region_name", "partregion_name")).rstrip(": ")
    for pollen_type in POLLEN_TYPES:
        if not any(pollen_type in by_type for by_type in regions.values()):
            _refuse(f"no region has {pollen_type}")
    return PollenForecast(day, regions, names, tuple(sorted(unknown)))


class DwdPollenValues(TimeseriesValues):
    """Values class for DWD pollen forecast."""

    def __post_init__(self) -> None:
        """Post-initialization of the DwdPollenValues class."""
        super().__post_init__()
        # the file of this request, read once for all its stations: `None` is "not asked yet", an empty tuple "asked,
        # and there is no file"
        self._file: tuple[PollenForecast, dt.datetime | None] | tuple[()] | None = None
        # why there is none, told for every station of the walk, as the core wants it told where a file serves them all
        self._unavailable: SkipCause | None = None

    def _read(self) -> tuple[PollenForecast, dt.datetime | None] | tuple[()]:
        """Fetch the file and read it, once for the request, and warn of what it holds that the table does not.

        A 404 is a file DWD has withdrawn and an empty 200 one it is rewriting: both are warned about and told by
        `file-skipped` as a file let go (`dwd/poi` does the same). Any other failure of the download is an outage,
        which swallowed would read as a day without a forecast (a 429 is the `ProviderRateLimitError`), and a file that
        cannot be read is a `DownloadError` (`read_forecast`).
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
            log.warning(f"Failed to fetch the pollen forecast {URL}: {file.content}")
            self._file = ()
            return self._file
        if file.is_empty:
            self._unavailable = SkipCause.MAINTENANCE
            log.warning(f"The pollen forecast {URL} is empty")
            self._file = ()
            return self._file
        forecast = read_forecast(file.content.read())
        unknown = sorted(forecast.names[key] for key in set(forecast.regions) - set(REGIONS_BY_KEY))
        if unknown:
            log.warning(
                f"The pollen forecast holds {len(unknown)} region(s) that are not known here and are skipped: "
                f"{', '.join(unknown)} (GH-4088)"
            )
        if forecast.unknown_pollen:
            log.warning(
                f"The pollen forecast holds {len(forecast.unknown_pollen)} pollen type(s) that are not known here and "
                f"are skipped: {', '.join(forecast.unknown_pollen)} (GH-4088)"
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
        region = REGIONS_BY_ID.get(station_id)
        by_type = None if region is None else forecast.regions.get((region.region_id, region.partregion_id))
        if region is None or by_type is None:
            # a station of the table that the file does not hold: DWD has dropped the region, or renumbered it
            note_skipped_download(SkipCause.NO_FORECAST)
            log.warning(f"The pollen forecast of {station_id} is not in the file of {forecast.day}")
            return pl.DataFrame()
        parameters = [parameter.name_original for parameter in dataset.parameters]
        rows = [(name, days) for name in parameters if (days := by_type.get(name)) is not None]
        for name in parameters:
            if name not in by_type:
                log.warning(f"The pollen forecast of {station_id} holds no {name} in the file of {forecast.day}")
        if not rows:
            return pl.DataFrame()
        df = pl.DataFrame(
            {
                "parameter": [name for name, _ in rows for _ in _DAYS],
                # the day of the forecast is a German date: at 00:00 UTC, as every daily stamp of the library is
                "timestamp": [
                    dt.datetime.combine(forecast.day + dt.timedelta(days=offset), dt.time())
                    for _ in rows
                    for _, offset in _DAYS
                ],
                "value": [text for _, days in rows for text in days],
            },
            schema={"parameter": pl.String, "timestamp": pl.Datetime("us"), "value": pl.String},
        )
        # a level is one of the seven steps of the legend, and a text that is none is no reading: it becomes null and
        # the text stays beside the value as `raw:` (a comma in it written as a semicolon, as the tokens are separated
        # by commas), where it would otherwise be a day without a value that says nothing about why
        text = pl.col("value").str.strip_chars()
        level = text.replace_strict(LEVELS, default=None, return_dtype=pl.Float64)
        raw = pl.when(level.is_null() & (text.str.len_chars() > 0)).then(text.str.replace_all(",", ";"))
        df = df.select(
            pl.col("parameter"),
            pl.col("timestamp"),
            level.alias("value"),
            join_quality_flags(None, raw=raw),
            pl.lit(last_modified, dtype=pl.Datetime("us", "UTC")).alias(UPDATED),
        )
        return self._note_files_with_rows(df, dataset)


@dataclass
class DwdPollenRequest(TimeseriesRequest):
    """Request class for DWD pollen forecast."""

    metadata = DwdPollenMetadata
    _values = DwdPollenValues
    # DWD ships no shape and no position of the regions: a search by place says so (`positions-unavailable`)
    stations_have_positions = False

    def _all(self) -> pl.LazyFrame:
        """Return the 27 regions of the forecast: the table of `regions.py`, which needs no request and no position."""
        return pl.LazyFrame(
            {
                "station_id": [region.station_id for region in REGIONS],
                "name": [region.name for region in REGIONS],
                "region": [region.region_name for region in REGIONS],
                # DWD gives the regions no shape and no position, so a search by place finds none of them
                "latitude": pl.Series([None] * len(REGIONS), dtype=pl.Float64),
                "longitude": pl.Series([None] * len(REGIONS), dtype=pl.Float64),
                "elevation": pl.Series([None] * len(REGIONS), dtype=pl.Float64),
            },
        )
