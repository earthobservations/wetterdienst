# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The stations of KNMI's network, read from its EDR API (GH-3928).

`GET /collections/{collection}/locations` lists every station, the same 77 for every collection, with its name,
position,
height above sea level, type and WMO number, and the WIGOS identifier (`wigos_id`) as its `id`. It has no dates: what
tells a station that has closed from one that is open is another request, and when it closed a third, so that a
listing for a window leaves a closed station out (GH-4008: Soesterberg `06265`, closed in 2008, was in every listing).

- `/locations?datetime=<instant>/<instant>` lists the stations that were open then (read 2026-11-12: 72 of the 77 for
  2026-01-01 to 2026-02-01, 61 for 2005, 15 for 1960, the same for every collection). The stations that the list of
  every station has and this one has not are closed. It filters by the dates of the station in KNMI's catalogue and not
  by those of its data: Schiphol `06240` is not in the list for 1960, and has daily values from 1951. So it is used to
  tell closed from open, never to cut a window by the start of a station, which stays empty.
- The data of a closed station says when it ended: its last monthly value. The monthly collection holds one value for
  each month since 1901, 23 parameters, which is some 35,000 points for a station, so a request names as many closed
  stations as fit under the limit (8), and a week's cache is enough for a fact that changes when a station closes.
  The annual collection would do for a station that closed long ago, and has no value for the year a station closed in
  (Soesterberg's last is 2006, its monthly one 2008-12).

Three requests of the quota in all, for the stations of every resolution, and the two that are not a listing kept for a
day and a week.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.knmi.observation import edr
from wetterdienst.provider.knmi.observation.edr import (
    _STAMP_FORMAT,
    COLLECTION_BY_RESOLUTION,
    FIRST_STAMP,
    Chunk,
    client_kwargs,
    fetch,
    raise_if_unanswered,
    request_url,
    stations_per_request,
    to_stamp,
)
from wetterdienst.provider.knmi.observation.grid import floor
from wetterdienst.provider.knmi.observation.metadata import KnmiObservationMetadata
from wetterdienst.provider.knmi.observation.parser import public_station_id
from wetterdienst.util.network import _without_url_secrets, drop_cached_file

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

#: How long the list of the stations and the list of those that are open are kept: a station that is opened or closed is
#: in them within half a day
_LISTING_EXPIRY = CacheExpiry.TWELVE_HOURS

#: How long the date a station closed is kept: it changes when a station closes, which the list of those that are open
#: says within half a day, and the URL that asks for it names the closed stations, so a new one is asked for at once
_ENDS_EXPIRY = CacheExpiry.ONE_WEEK

_SCHEMA = {
    "station_id": pl.String,
    "wigos_id": pl.String,
    "name": pl.String,
    "latitude": pl.Float64,
    "longitude": pl.Float64,
    "elevation": pl.Float64,
    "type": pl.String,
}


def _listing(url: str, settings: Settings) -> dict | None:
    """Read a listing of the API as GeoJSON; None for one that is gone or is none (warned about).

    Raises:
        CredentialRejectedError: the key is refused. NoInternetError, DownloadError: no answer.

    """
    file = fetch(url, settings, _LISTING_EXPIRY)
    raise_if_unanswered(file)
    if isinstance(file.content, Exception):
        log.warning(f"KNMI's EDR API has no listing {_without_url_secrets(url)} (status {file.status})")
        return None
    try:
        listing = json.load(file.content)
        listing["features"][0]["id"]
    except (ValueError, KeyError, IndexError, TypeError):
        # a 200 that is no listing would be kept as one for the whole expiry
        drop_cached_file(
            url,
            settings.cache_dir,
            _LISTING_EXPIRY,
            client_kwargs(settings),
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        log.warning(f"KNMI's EDR API answered {_without_url_secrets(url)} with no list of stations")
        return None
    return listing


def _station_id(feature: dict) -> str:
    properties = feature["properties"]
    wmo = properties.get("wmoId")
    return wmo if isinstance(wmo, str) and wmo else public_station_id(feature["id"])


def _last_data(settings: Settings, wsis: list[str], now: dt.datetime) -> dict[str, dt.datetime]:
    """Read when the data of closed stations ends: the stamp (the end of the month) of the last monthly value of each.

    A station without a value is not in the answer, nor is one the API has no data for (a 404): its end is not known.
    """
    parameters = [parameter.name_original for dataset in KnmiObservationMetadata["monthly"] for parameter in dataset]
    chunk = Chunk(FIRST_STAMP[Resolution.MONTHLY], to_stamp(floor(now, Resolution.MONTHLY), Resolution.MONTHLY))
    size = stations_per_request(chunk, Resolution.MONTHLY, len(parameters))
    ends: dict[str, dt.datetime] = {}
    for start in range(0, len(wsis), size):
        url = request_url(
            COLLECTION_BY_RESOLUTION[Resolution.MONTHLY],
            wsis[start : start + size],
            parameters,
            chunk,
            Resolution.MONTHLY,
        )
        file = fetch(url, settings, _ENDS_EXPIRY)
        raise_if_unanswered(file)
        if isinstance(file.content, Exception):
            continue
        try:
            for coverage in json.load(file.content)["coverages"]:
                times = coverage["domain"]["axes"]["t"]["values"]
                held = [
                    index
                    for index in range(len(times))
                    if any(series["values"][index] is not None for series in coverage["ranges"].values())
                ]
                if held:
                    ends[public_station_id(coverage["eumetnet:locationId"])] = dt.datetime.strptime(
                        times[held[-1]], _STAMP_FORMAT
                    ).replace(tzinfo=dt.UTC)
        except (ValueError, KeyError, TypeError, IndexError):
            log.warning(f"KNMI's EDR API answered {_without_url_secrets(url)} with something that is no CoverageJSON")
    return ends


def read_stations(settings: Settings, now: dt.datetime) -> pl.DataFrame:
    """Read the stations of KNMI's network, one row each, with `end_timestamp` for those that have closed.

    The empty frame where the API has no list. `end_timestamp` is the end of the last month with a value, and empty for
    a station that is open, which is still reporting, and for a closed one that has no value. `start_timestamp` is
    empty:
    the start of a station in KNMI's catalogue is not that of its data (Schiphol's data begins in 1951 and its
    station in
    1990, 15 of the 77 stations are such), so none is stated.

    Raises:
        CredentialRejectedError: the key is refused. NoInternetError, DownloadError: no answer.

    """
    all_stations = _listing(
        f"{edr.EDR_BASE_URL}/collections/{COLLECTION_BY_RESOLUTION[Resolution.DAILY]}/locations", settings
    )
    if all_stations is None:
        return pl.DataFrame(schema=_SCHEMA)
    features = all_stations["features"]
    df = pl.DataFrame(
        {
            "station_id": [_station_id(feature) for feature in features],
            "wigos_id": [feature["id"] for feature in features],
            "name": [feature["properties"].get("name", "").strip() for feature in features],
            "latitude": [feature["geometry"]["coordinates"][1] for feature in features],
            "longitude": [feature["geometry"]["coordinates"][0] for feature in features],
            "elevation": [feature["properties"].get("height_above_mean_sea_level") for feature in features],
            "type": [feature["properties"].get("type", "") for feature in features],
        },
        schema=_SCHEMA,
    )
    today = floor(now, Resolution.DAILY).strftime(_STAMP_FORMAT)
    open_now = _listing(
        f"{edr.EDR_BASE_URL}/collections/{COLLECTION_BY_RESOLUTION[Resolution.DAILY]}/locations?datetime={today}/{today}",
        settings,
    )
    closed = [] if open_now is None else sorted({f["id"] for f in features} - {f["id"] for f in open_now["features"]})
    ends = _last_data(settings, closed, now) if closed else {}
    end = (
        pl.col("station_id").replace_strict(ends, default=None, return_dtype=pl.Datetime("us", "UTC"))
        if ends
        else pl.lit(None, dtype=pl.Datetime("us", "UTC"))
    )
    return df.with_columns(end.alias("end_timestamp"))
