# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Eaufrance Hubeau API."""

from __future__ import annotations

import datetime as dt
import json
import logging
import math
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import (
    DATASET_NAME_DEFAULT,
    ParameterModel,
    build_metadata_model,
)
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.settings import Settings


log = logging.getLogger(__name__)


_OBSERVATIONS_ENDPOINT = "https://hubeau.eaufrance.fr/api/v2/hydrometrie/observations_tr"
_STATIONS_FIELDS = (
    "code_station",
    "libelle_station",
    "longitude_station",
    "latitude_station",
    "altitude_ref_alti_station",
    "libelle_departement",
    "date_ouverture_station",
    "date_fermeture_station",
)
# `size` is not a nicety: the referential answers with its first thousand stations of four thousand
# and a cursor to the rest, so a query that names no size and follows no cursor quietly serves a
# quarter of the network.
_STATIONS_ENDPOINT = (
    "https://hubeau.eaufrance.fr/api/v2/hydrometrie/referentiel/stations?format=json&en_service=true"
    f"&size=10000&fields={','.join(_STATIONS_FIELDS)}"
)

# Hubeau declares no recording interval anywhere: not in the station referential, not on the
# observations, and the v2 API defines no field for one -- unlike Pegelonline, which publishes an
# `equidistance` per timeseries. A station's interval is therefore measured from the timestamps it
# has just published. The network does transmit on a grid, so the modal spacing of a few hours of
# records recovers it: measured across the whole network on 2026-08-21, 2987 of 3018 reporting
# stations resolved to one of the five intervals below (5 min x 1643, 10 x 903, 15 x 251, 6 x 33,
# 60 x 120), and re-measuring a 45-station sample over 48 hours returned the same interval for all
# 45 of them. An interval outside this table belongs to no resolution and is reported rather than
# filed under a neighbouring one -- 20 and 30 minutes are the two the network uses today.
_STEP_TO_RESOLUTION: dict[int, str] = {
    5: "5_minutes",
    6: "6_minutes",
    10: "10_minutes",
    15: "15_minutes",
    60: "hourly",
}
_RESOLUTION_TO_STEP: dict[str, int] = {resolution: step for step, resolution in _STEP_TO_RESOLUTION.items()}

# Two hours of the whole network's stage observations names every station transmitting at least
# every fifteen minutes, which is seven in eight of them, for two pages and about thirty seconds.
# Widening the window buys the slower stations at a steep price -- six hours is 145k records and
# nine pages -- so they are left to the second pass below, which asks about them by name. The
# window is closed at both ends and anchored to a six-hour boundary, so that it and every URL
# built from it stay the same between calls and the cache can hold what they returned.
_SNIFF_WINDOW = dt.timedelta(hours=2)
_SNIFF_ANCHOR = dt.timedelta(hours=6)
# A station too quiet for that window is asked about again over a longer one, in batches, by
# name. Roughly a thousand of the in-service stations are quiet in any given window and most are
# genuinely dead -- of a 40-station sample, 29 had published nothing in 30 days -- but the rest are
# alive and would lose the data they do have. Stage is asked first and discharge only for whatever
# is still missing, since the 17 stations that publish discharge and no stage are the only ones the
# second pass can add. Both are asked separately: interleaving two grids of one station halves the
# spacing and would name the interval wrong.
_SNIFF_WINDOW_QUIET = dt.timedelta(hours=24)
_SNIFF_QUIET_BATCH = 120
_SNIFF_PAGE_SIZE = 20000
# Twenty thousand records is the largest page the service serves and, at some ten to twenty seconds
# each, the fewest round trips -- but well past the thirty seconds a single file is given. The
# timeout is per call, so this raises it only for the pages that ask about the whole network.
_SNIFF_TIMEOUT = 120
# The referential is one page of four thousand stations and answers in a second or two, so it keeps
# the ordinary budget.
_STATIONS_TIMEOUT = 30
# One page of observations per request, followed by its cursor. The window is chunked to about a
# page so that most requests need only one.
_VALUES_PAGE_SIZE = 20000
_VALUES_TIMEOUT = 120
_VALUES_SCHEMA = {
    "code_station": pl.String,
    "date_obs": pl.String,
    "resultat_obs": pl.Float64,
    "code_qualification_obs": pl.Float64,
}
# Three intervals is the least that can carry a majority, so it is the least that names a station.
_SNIFF_MIN_INTERVALS = 3
# Every query here is cursor-driven, and a cursor that stopped advancing would loop forever. Two
# hours of the network is three pages and the referential is one; this is a backstop, not a limit
# anyone should reach.
_MAX_PAGES = 40


# reported once per process rather than per request: `_all` measures the network whole every time
# it runs, and `filter_by_name` and `filter_by_rank` each run it twice, so a single station on an
# unmapped interval would otherwise warn on every call
_reported_steps: set[int] = set()


def _log_unmapped_steps(df: pl.DataFrame) -> None:
    """Report intervals stations transmit at that no resolution covers.

    A station whose modal interval is absent from ``_STEP_TO_RESOLUTION`` belongs to no resolution
    and is listed under none, which is better than filing it under a neighbouring interval and
    quietly misdescribing it. It is a silent outcome though, and the network moving onto a sixth
    interval is exactly the change that would need a new member.
    """
    steps = set(df.get_column("step").unique().to_list()) - set(_STEP_TO_RESOLUTION)
    new = steps - _reported_steps
    if not new:
        return
    _reported_steps.update(new)
    log.info(
        f"Hubeau stations transmitting every {', '.join(f'{step} minutes' for step in sorted(new))} "
        f"are served under no resolution, as no resolution covers those intervals.",
    )


def _paged_rows(url: str, settings: Settings, *, ttl: CacheExpiry, timeout: int) -> list[dict]:
    """Follow one Hubeau query through its cursor pages.

    Every endpoint here answers a page at a time and hands back a cursor to the next, and a caller
    that reads only the first page gets a silently short answer -- which is how the station list
    came to hold a quarter of the network.

    Returns:
        Every record the pages carried. A page the service refuses raises rather than returning
        what came before it: a silently short answer would file stations under the wrong
        resolution, or truncate a series, which is worse than saying the service could not be read.

    """
    query = url
    rows: list[dict] = []
    for _ in range(_MAX_PAGES):
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=ttl,
            client_kwargs={**settings.fsspec_client_kwargs, "timeout": timeout},
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            break
        payload = json.load(file.content)
        page = payload.get("data")
        if not page:
            break
        rows.extend(page)
        url = payload.get("next")
        if not url:
            break
    else:
        log.warning(f"Hubeau paging stopped at {_MAX_PAGES} pages for {query}; the result is incomplete.")
    return rows


def _modal_steps(df: pl.DataFrame) -> pl.DataFrame:
    """Reduce observation timestamps to one interval per station.

    Args:
        df: Frame of ``station_id`` and ``date``, one row per observation.

    Returns:
        Frame of ``station_id`` and ``step``, the station's modal interval in minutes.

    """
    if df.is_empty():
        return pl.DataFrame(schema={"station_id": pl.String, "step": pl.Int64})
    df = df.unique(subset=["station_id", "date"]).sort("station_id", "date")
    # rounded to the nearest minute rather than truncated: a gauge whose transmissions drift by
    # seconds spaces them 4 m 55 s apart as readily as 5 m 00 s, and truncation would call that a
    # four-minute station -- an interval no resolution covers, which drops it from the list
    df = df.with_columns(
        (pl.col("date").diff().over("station_id").dt.total_seconds() / 60).round().cast(pl.Int64).alias("step"),
    )
    # a null step is a station's first observation, which spans nothing; a zero step would be two
    # records at one timestamp, which `unique` above has already ruled out
    df = df.drop_nulls("step").filter(pl.col("step") > 0)
    counts = df.group_by("station_id", "step").len()
    return (
        counts.group_by("station_id")
        .agg(
            # ties go to the shorter interval, so that a station is named the same way on every
            # run rather than by whichever step the grouping happened to emit first
            pl.col("step").sort_by(pl.col("len"), pl.col("step"), descending=[True, False]).first(),
            pl.col("len").sum().alias("intervals"),
        )
        .filter(pl.col("intervals") >= _SNIFF_MIN_INTERVALS)
        .select("station_id", "step")
    )


_PARAMETERS = [
    {
        "name": "discharge",
        "name_original": "Q",
        "unit": "liter_per_second",
    },
    {
        "name": "stage",
        "name_original": "H",
        "unit": "millimeter",
    },
]

HubeauMetadata = {
    "name_short": "Eaufrance",
    "name_english": "Eaufrance",
    "name_local": "Eaufrance",
    "country": "France",
    "copyright": "© Eaufrance",
    "url": "https://www.eaufrance.fr/",
    "kind": "observation",
    "timezone": "Europe/Paris",
    "timezone_data": "dynamic",
    "resolutions": [
        {
            "name": resolution,
            "name_original": resolution,
            "periods": ["historical"],
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
        for resolution in _STEP_TO_RESOLUTION.values()
    ],
}
HubeauMetadata = build_metadata_model(HubeauMetadata, "HubeauMetadata")


class HubeauValues(TimeseriesValues):
    """Values class for Eaufrance Hubeau data."""

    _endpoint = (
        "https://hubeau.eaufrance.fr/api/v2/hydrometrie/observations_tr?code_entite={station_id}"
        "&grandeur_hydro={grandeur_hydro}&sort=asc&date_debut_obs={start_date}&date_fin_obs={end_date}"
        f"&size={_VALUES_PAGE_SIZE}"
    )

    def _get_hubeau_dates(self, parameter: ParameterModel) -> Iterator[tuple[dt.datetime, dt.datetime]]:
        """Split the served window into chunks of a page of observations each.

        The interval comes from the resolution the station is listed under, which is what the
        station list measured it to be, so the split no longer costs a request of its own. It is a
        forecast of how many records a window holds rather than a promise: the station list
        measures stage, and a station whose discharge arrives more often would hold more. The
        chunks are therefore sized to a page and the pages are followed, so an underestimate costs
        another request rather than the records past the first page.
        """
        end = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None)
        start = end - dt.timedelta(days=30)
        delta = end - start
        data_delta = dt.timedelta(minutes=_RESOLUTION_TO_STEP[parameter.dataset.resolution.name])
        n_dates = delta / data_delta
        periods = math.ceil(n_dates / _VALUES_PAGE_SIZE)
        request_date_range = pl.datetime_range(start=start, end=end, interval=delta / periods, eager=True)
        return pairwise(request_date_range)

    def _collect_station_parameter_or_dataset(  # ty: ignore[invalid-method-override]
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        """Collect the last 30 days of one parameter of one station."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.sr.stations.settings)
        data = []
        for start_date, end_date in self._get_hubeau_dates(parameter=parameter_or_dataset):
            url = self._endpoint.format(
                station_id=station_id,
                grandeur_hydro=parameter_or_dataset.name_original,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )
            rows = _paged_rows(url, settings, ttl=CacheExpiry.FIVE_MINUTES, timeout=_VALUES_TIMEOUT)
            if rows:
                data.append(pl.from_dicts(rows, schema=_VALUES_SCHEMA))
        if not data:
            return pl.DataFrame()
        df = pl.concat(data)
        df = df.rename(
            mapping={
                "code_station": "station_id",
                "date_obs": "date",
                "resultat_obs": "value",
                "code_qualification_obs": "quality",
            },
        )
        return df.select(
            pl.lit(parameter_or_dataset.dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.dataset.name, dtype=pl.String).alias("dataset"),
            # not lowercased: `_create_humanized_parameters_mapping` and the skip-criteria check
            # both key on `name_original` as declared, so a lowercased value never matched --
            # Hubeau silently never humanized and every station counted as having no data
            pl.lit(parameter_or_dataset.name_original).alias("parameter"),
            "station_id",
            pl.col("date").str.to_datetime(format="%Y-%m-%dT%H:%M:%SZ").dt.replace_time_zone("UTC"),
            "value",
            "quality",
        )


@dataclass
class HubeauRequest(TimeseriesRequest):
    """Request class for Eaufrance Hubeau data."""

    metadata = HubeauMetadata
    _values = HubeauValues

    _endpoint = _STATIONS_ENDPOINT

    def _observation_dates(self, url: str) -> pl.DataFrame:
        """Read the timestamps one observations query carries.

        Returns:
            Frame of ``station_id`` and ``date``, one row per observation.

        """
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        rows = _paged_rows(url, settings, ttl=CacheExpiry.METAINDEX, timeout=_SNIFF_TIMEOUT)
        if not rows:
            return pl.DataFrame(schema={"station_id": pl.String, "date": pl.Datetime(time_unit="us")})
        df = pl.from_dicts(rows, schema={"code_station": pl.String, "date_obs": pl.String})
        return df.select(
            pl.col("code_station").alias("station_id"),
            pl.col("date_obs").str.to_datetime(format="%Y-%m-%dT%H:%M:%SZ").alias("date"),
        )

    def _station_steps(self, station_ids: list[str]) -> pl.DataFrame:
        """Measure the interval each station transmits at.

        Args:
            station_ids: The stations the referential lists, so that a station quiet during the
                first window can be asked about by name.

        Returns:
            Frame of ``station_id`` and ``step``, the station's interval in minutes. A station
            that published nothing to measure is absent.

        """
        # floored to the anchor so that the window, and with it every URL below, stays the same
        # for six hours at a time and the cache can hold what they returned
        now = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None)
        anchor = now - (now - now.replace(hour=0, minute=0, second=0, microsecond=0)) % _SNIFF_ANCHOR
        window = self._observations_url(start=anchor - _SNIFF_WINDOW, end=anchor, grandeur="H")
        steps = _modal_steps(self._observation_dates(window))
        missing = sorted(set(station_ids) - set(steps.get_column("station_id")))
        for grandeur in ("H", "Q"):
            if not missing:
                break
            frames = [
                self._observation_dates(
                    self._observations_url(
                        start=anchor - _SNIFF_WINDOW_QUIET,
                        end=anchor,
                        grandeur=grandeur,
                        station_ids=missing[batch : batch + _SNIFF_QUIET_BATCH],
                    ),
                )
                for batch in range(0, len(missing), _SNIFF_QUIET_BATCH)
            ]
            quiet = _modal_steps(pl.concat(frames))
            steps = pl.concat([steps, quiet])
            missing = sorted(set(missing) - set(quiet.get_column("station_id")))
        _log_unmapped_steps(steps)
        return steps

    @staticmethod
    def _observations_url(
        start: dt.datetime,
        end: dt.datetime,
        grandeur: str,
        station_ids: list[str] | None = None,
    ) -> str:
        """Build one observations query, asking for the two fields an interval is measured from."""
        entite = f"code_entite={','.join(station_ids)}&" if station_ids else ""
        return (
            f"{_OBSERVATIONS_ENDPOINT}?{entite}grandeur_hydro={grandeur}&sort=asc&size={_SNIFF_PAGE_SIZE}"
            f"&fields=code_station,date_obs"
            f"&date_debut_obs={start.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            f"&date_fin_obs={end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        )

    def _all(self) -> pl.LazyFrame:
        """List each station under the resolution it transmits at."""
        requested = {
            parameter.dataset.resolution.name for parameter in self.parameters if isinstance(parameter, ParameterModel)
        }
        if not requested:
            return pl.LazyFrame()
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        rows = _paged_rows(self._endpoint, settings, ttl=CacheExpiry.METAINDEX, timeout=_STATIONS_TIMEOUT)
        if not rows:
            return pl.LazyFrame()
        df_raw = pl.from_dicts(
            rows,
            schema={
                "code_station": pl.String,
                "libelle_station": pl.String,
                "longitude_station": pl.Float64,
                "latitude_station": pl.Float64,
                "altitude_ref_alti_station": pl.Float64,
                "libelle_departement": pl.String,
                "date_ouverture_station": pl.String,
                "date_fermeture_station": pl.String,
            },
        )
        df_raw = df_raw.rename(
            mapping={
                "code_station": "station_id",
                "libelle_station": "name",
                "longitude_station": "longitude",
                "latitude_station": "latitude",
                "altitude_ref_alti_station": "height",
                "libelle_departement": "state",
                "date_ouverture_station": "start_date",
                "date_fermeture_station": "end_date",
            },
        )
        df_raw = df_raw.with_columns(
            pl.col("start_date").str.to_datetime(time_zone="UTC"),
            pl.when(pl.col("end_date").is_null())
            .then(dt.datetime.now(ZoneInfo("UTC")))
            .otherwise(pl.col("end_date").str.to_datetime(time_zone="UTC"))
            .alias("end_date"),
        )
        # A station belongs to the resolution it transmits at, which is measured rather than
        # declared -- see `_STEP_TO_RESOLUTION`. One that has published nothing to measure is
        # listed under no resolution: naming an interval for it would be a guess, and the join
        # below drops it. It returns to the list as soon as it transmits again.
        steps = self._station_steps(df_raw.get_column("station_id").to_list())
        df = df_raw.join(steps, on="station_id", how="inner")
        df = df.with_columns(
            pl.col("step").replace_strict(_STEP_TO_RESOLUTION, default=None).alias("resolution"),
            pl.lit(DATASET_NAME_DEFAULT, pl.String).alias("dataset"),
        )
        df = df.filter(pl.col("resolution").is_in(requested))
        df = df.select(self._base_columns)
        return df.lazy()
