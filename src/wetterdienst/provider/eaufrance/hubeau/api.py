# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Eaufrance Hubeau API."""

from __future__ import annotations

import datetime as dt
import json
import logging
import math
from dataclasses import dataclass, field
from itertools import pairwise
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

import polars as pl
from aiohttp import ClientError

from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import (
    DATASET_NAME_DEFAULT,
    ETALAB_2_0,
    ParameterModel,
    build_metadata_model,
)
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.util.network import download_file, fetchable_link
from wetterdienst.util.response_warnings import warn_response

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.settings import Settings


log = logging.getLogger(__name__)


_OBSERVATIONS_ENDPOINT = "https://hubeau.eaufrance.fr/api/v2/hydrometrie/observations_tr"
_STATIONS_FIELDS = (
    "code_station",
    "code_site",
    "libelle_station",
    "longitude_station",
    "latitude_station",
    "altitude_ref_alti_station",
    "code_systeme_alti_site",
    "libelle_departement",
    "date_ouverture_station",
    "date_fermeture_station",
)
# The vertical reference system `altitude_ref_alti_station` is given in, by its `code_systeme_alti_site`
# in Sandre nomenclature 76 ("Système altimétrique de référence"), labelled as Sandre labels it
# (`LbElement`): https://api.sandre.eaufrance.fr/referentiels/v1/nsa/76.json, read 2026-10-02, 34
# elements, updated by Sandre 2026-04-15. A code not listed here is given as the code itself.
_SYSTEME_ALTI_LABELS = {
    0: "Système altimétrique inconnu",
    1: "Bourdeloue 1857",
    2: "Nivellement Général de la France 1884",
    3: "IGN 1969",
    4: "Nivellement Général de la Corse",
    5: "IGN 1978 (Corse)",
    6: "IGN 1958 (Réunion)",
    7: "IGN 1989 (Réunion)",
    8: "IGN 1955 (Martinique)",
    9: "IGN 1987 (Martinique)",
    10: "IGN 1951 (Guadeloupe)",
    11: "IGN 1988 (Guadeloupe)",
    12: "IGN 1988 (Guadeloupe Les Saintes)",
    13: "IGN 1988 (Guadeloupe Marie-Galante)",
    14: "IGN 1988 (Guadeloupe Saint-Martin)",
    15: "IGN 1988 (Guadeloupe Saint-Barthélemy)",
    16: "IGN 1942 (Guyane)",
    17: "Niv. Général de la Guyane 1977",
    18: "IGN 1950 (Mayotte)",
    19: "Equipe 1979 (Mayotte)",
    20: "Danger 1950 (St Pierre et Miquelon)",
    21: "NGNC 1969 (Nelle Calédonie)",
    22: "IGN 1984 (Wallis et Futuna)",
    23: "SHOM 1953 (Mayotte)",
    24: "Tahiti IGN 1966 (Polynésie)",
    25: "SHOM 1981 (Iles Loyauté)",
    26: "SHOM 1976 (Iles Loyauté)",
    27: "SHOM 1970 (Iles Loyauté)",
    28: "IGN 1962 (Iles Kerguelen)",
    29: "EPF 1952 (Terre Adélie)",
    30: "SHOM 1977 (Ile du canal du Mozambique)",
    31: "Système local - hauteur relative",
    32: "IGN 1992 (Guadeloupe La Désirade)",
    33: "IGN 2023 Mayotte",
}
# `size` is not a nicety: the referential answers with its first thousand stations of four thousand
# and a cursor to the rest, so a query that names no size and follows no cursor quietly serves a
# quarter of the network.
_STATIONS_ENDPOINT = (
    "https://hubeau.eaufrance.fr/api/v2/hydrometrie/referentiel/stations?format=json&en_service=true"
    f"&size=10000&fields={','.join(_STATIONS_FIELDS)}"
)
# The station referential publishes no altitude of the ground. The sites referential does, one per
# hydrometric site, and each station names its site in `code_site`. Sites are not filtered to those
# in service, so that a station in service finds its site whatever the site's own flag says.
_SITES_ENDPOINT = (
    "https://hubeau.eaufrance.fr/api/v2/hydrometrie/referentiel/sites?format=json"
    "&size=10000&fields=code_site,altitude_site"
)
# `altitude_site` is taken as a station's elevation only where it is not exactly 0 and lies between
# -10 m, the lowest ground in France (Etang de Lavalduc), and 4810 m, above its highest (Mont Blanc,
# about 4806 m). Of the 4178 stations in service on 2026-10-01, 48 were on a site at 0 m -- inland
# ones among them, whose gauge zero lies 100 to 630 m up, so 0 stands for unknown there -- 3 on a
# site at -999 m and 4 on one at 12000 to 130000 m.
_ELEVATION_MIN = -10.0
_ELEVATION_MAX = 4810.0

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
# each, the fewest round trips. A timeout bounds how long the service may stay silent, not the whole
# page (GH-2258). These pages were not timed to their first byte; the referential below waited up
# to 50 seconds for its own, so they keep the same budget rather than assume they answer sooner.
# The timeout is per call, so this raises it only for the pages that ask about the whole network.
_SNIFF_TIMEOUT = 120
# The station referential is one page of four thousand stations, but not a quick one: on 2026-10-01
# it took 25 to 78 seconds to arrive, streaming at 16 to 32 KB/s, and 5 to 50 seconds before its
# first byte did (GH-2221). That wait is silence, so it gets the same budget, as does the sites
# referential beside it.
_REFERENTIAL_TIMEOUT = 120
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
# it runs, and every filter runs it, so a single station on an unmapped interval would otherwise
# warn on every call
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


# Where the stations of the referential are, one box for each area, `(south, north, west, east)` in degrees and a
# little wider than the stations of 2026-10-26 (metropolitan France with Corsica: latitude 41.55 to 50.92, longitude
# -4.68 to 9.47; Guadeloupe and Martinique, Guyane, Reunion and Mayotte as named). The north edge of metropolitan
# France is 51.1, as France reaches 51.09 at Bray-Dunes (Dunkerque is at 51.03): a station there is in, and its swapped
# position is told. The declared extent of the network is one box over all of them, which is no help against a swapped
# position: the swapped position of a station in Nord (latitude 4.1, longitude 50.0) is in it too.
_AREAS: dict[str, tuple[float, float, float, float]] = {
    "metropolitan France": (41.0, 51.1, -5.5, 10.0),
    "Guadeloupe and Martinique": (14.3, 16.6, -61.9, -60.7),
    "Guyane": (2.0, 5.9, -54.8, -51.5),
    "Reunion": (-21.5, -20.7, 55.1, 55.9),
    "Mayotte": (-13.1, -12.5, 44.9, 45.4),
}


def _in_an_area(latitude: pl.Expr, longitude: pl.Expr) -> pl.Expr:
    """Tell whether a position is in one of ``_AREAS``, null where it has none."""
    return pl.any_horizontal(
        latitude.is_between(south, north) & longitude.is_between(west, east)
        for south, north, west, east in _AREAS.values()
    )


# the warnings already logged by this process, by their text: the answer of every request that concerns an unplaced
# station records the warning (`warn_response`), but a library caller has it once in its log, as `_reported_steps` does
_reported_unplaced: set[str] = set()

#: the code of the warning that names the stations whose position the referential writes in no area of France, also
#: swapped, and which are listed without one (GH-3468)
POSITION_UNPLACED = "position-unplaced"
# how many stations that warning names; the others are counted
_UNPLACED_LISTED = 10


def _written(row: dict) -> str:
    """Say what the referential wrote for a station's position, in the form of the `raw:` token of a reading."""
    return f"{row['station_id']} raw:{row['latitude']},{row['longitude']}"


def _swap_misplaced_positions(df: pl.DataFrame) -> pl.DataFrame:
    """Swap latitude and longitude of the stations the referential lists with the two the wrong way round.

    The referential writes some metropolitan stations with the latitude in the longitude field and the other way
    round (54 of 4,200 on 2026-10-26, such as H000000201 at latitude 4.10 and longitude 49.99, a point near Somalia),
    and a swapped pair is a valid position, so it is told by where it lies: a position is swapped when it is in none of
    ``_AREAS`` and swapped is in one. A position in an area is never touched, so no station overseas is, and one that
    is in none either way is left as it is for `_null_unplaced_positions` (J543211003, the Blavet, is listed at
    latitude 35.1 and longitude 0.84, in Algeria, which is no swap).

    A station frame has no column for a note on a row (`quality_flags` belongs to a reading), so what the source wrote
    is kept in the debug line that names the stations swapped, as `raw:<latitude>,<longitude>` after the id, as the
    GHCN table of the lost longitude sign keeps the position its list gave.

    Args:
        df: stations with ``station_id``, ``latitude`` and ``longitude`` columns

    Returns:
        the stations with the pair swapped where the rule says so, in the same order

    """
    latitude, longitude = pl.col("latitude"), pl.col("longitude")
    swap = (
        latitude.is_not_null() & longitude.is_not_null() & ~_in_an_area(latitude, longitude)
        & _in_an_area(longitude, latitude)
    )  # fmt: skip
    swapped = df.filter(swap)
    if swapped.is_empty():
        return df
    written = ", ".join(_written(row) for row in swapped.iter_rows(named=True))
    log.debug(
        f"Hubeau: swapped latitude and longitude of {swapped.height} stations whose position is in no area of "
        f"France, as the referential wrote them: {written}"
    )
    return df.with_columns(
        pl.when(swap).then(longitude).otherwise(latitude).alias("latitude"),
        pl.when(swap).then(latitude).otherwise(longitude).alias("longitude"),
    )


def _null_unplaced_positions(df: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, str]]:
    """Give no position to the stations whose position is in no area of France, swapped or not (GH-3468).

    A position that is in none of ``_AREAS`` once `_swap_misplaced_positions` has run is the source's error and no
    swap puts it right: J543211003, the Blavet in Morbihan, is listed in Algeria and swapped it is in Kenya. The
    station stays in the list with a null latitude and longitude, so that no search by place picks it. What the
    referential wrote is kept for `HubeauRequest._warn_unplaced`, which tells it where it concerns an answer. A
    station that has no position to begin with is not one of these.

    Args:
        df: stations with ``station_id``, ``latitude`` and ``longitude`` columns

    Returns:
        the stations, the unplaced with a null ``latitude`` and ``longitude``, in the same order; and for each
        unplaced station its id and what the referential wrote, as ``raw:<latitude>,<longitude>``

    """
    latitude, longitude = pl.col("latitude"), pl.col("longitude")
    unplaced = latitude.is_not_null() & longitude.is_not_null() & ~_in_an_area(latitude, longitude)
    rows = df.filter(unplaced)
    if rows.is_empty():
        return df, {}
    written = {row["station_id"]: f"raw:{row['latitude']},{row['longitude']}" for row in rows.iter_rows(named=True)}
    return (
        df.with_columns(
            pl.when(unplaced).then(None).otherwise(latitude).alias("latitude"),
            pl.when(unplaced).then(None).otherwise(longitude).alias("longitude"),
        ),
        written,
    )


def _unplaced_message(written: dict[str, str]) -> str:
    """Say which stations are listed without a position, and what the referential wrote for them."""
    count = len(written)
    one = count == 1
    named = ", ".join(f"{station_id} {text}" for station_id, text in list(written.items())[:_UNPLACED_LISTED])
    more = f" and {count - _UNPLACED_LISTED} more" if count > _UNPLACED_LISTED else ""
    return (
        f"Hub'Eau lists {'a station' if one else f'{count} stations'} at a position in none of metropolitan "
        f"France, Guadeloupe, Martinique, Guyane, Reunion and Mayotte, also with latitude and longitude swapped: "
        f"{'its' if one else 'their'} latitude and longitude are null, so no search by place finds "
        f"{'it' if one else 'them'}. The referential wrote {named}{more}."
    )


def _referential_stations(rows: list[dict]) -> tuple[pl.DataFrame, dict[str, str]]:
    """Make the frame of the referential's stations, with a position the source got wrong put right or taken away.

    Returns:
        the stations under the names of the stations frame, one row for each station of the referential (the
        resolution a station transmits at is not in it), with `_swap_misplaced_positions` and then
        `_null_unplaced_positions` applied; and what that wrote of the stations it left without a position

    """
    df = pl.from_dicts(
        rows,
        schema={
            "code_station": pl.String,
            "code_site": pl.String,
            "libelle_station": pl.String,
            "longitude_station": pl.Float64,
            "latitude_station": pl.Float64,
            "altitude_ref_alti_station": pl.Float64,
            "code_systeme_alti_site": pl.Int64,
            "libelle_departement": pl.String,
            "date_ouverture_station": pl.String,
            "date_fermeture_station": pl.String,
        },
    ).rename(
        mapping={
            "code_station": "station_id",
            "libelle_station": "name",
            "longitude_station": "longitude",
            "latitude_station": "latitude",
            "altitude_ref_alti_station": "gauge_zero",
            "libelle_departement": "region",
            "date_ouverture_station": "start_timestamp",
            "date_fermeture_station": "end_timestamp",
        },
    )
    return _null_unplaced_positions(_swap_misplaced_positions(df))


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
        # the cursor is the answer's to name, and is followed only at the host that was asked (GH-3339)
        url = fetchable_link(url, query)
    else:
        log.warning(f"Hubeau paging stopped at {_MAX_PAGES} pages for {query}; the result is incomplete.")
    return rows


def _modal_steps(df: pl.DataFrame) -> pl.DataFrame:
    """Reduce observation timestamps to one interval per station.

    Args:
        df: Frame of ``station_id`` and ``timestamp``, one row per observation.

    Returns:
        Frame of ``station_id`` and ``step``, the station's modal interval in minutes.

    """
    if df.is_empty():
        return pl.DataFrame(schema={"station_id": pl.String, "step": pl.Int64})
    df = df.unique(subset=["station_id", "timestamp"]).sort("station_id", "timestamp")
    # rounded to the nearest minute rather than truncated: a gauge whose transmissions drift by
    # seconds spaces them 4 m 55 s apart as readily as 5 m 00 s, and truncation would call that a
    # four-minute station -- an interval no resolution covers, which drops it from the list
    df = df.with_columns(
        (pl.col("timestamp").diff().over("station_id").dt.total_seconds() / 60).round().cast(pl.Int64).alias("step"),
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

_HubeauMetadataSpec = {
    "name_short": "Eaufrance",
    "name_english": "Eaufrance",
    "name_local": "Eaufrance",
    "country": "France",
    "country_code": "FR",
    "copyright": "© Eaufrance",
    "license": ETALAB_2_0,
    "attribution": "Eaufrance",
    "url": "https://www.eaufrance.fr/",
    "kind": "observation",
    "extent": {
        "scope": "national",
        "continents": ["africa", "europe", "north_america", "south_america"],
        "country_codes": ["FR"],
        # Guadeloupe and Martinique, Guyane, Reunion, Mayotte and Corsica, read from the referential the reader lists
        # the stations of (`referentiel/stations?en_service=true`, 4,200 stations, each with a position, on 2026-10-27:
        # longitude -61.78 to 55.72, latitude -21.38 to 50.92, the box reaching to 51.1 as France does, Bray-Dunes at
        # 51.09), which `test_the_hubeau_referential_is_in_the_extent_of_its_network` reads
        "bbox": [-62.0, -22.0, 56.0, 51.1],
    },
    "timezone": "Europe/Paris",
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
HubeauMetadata = build_metadata_model(_HubeauMetadataSpec, "HubeauMetadata")


class HubeauValues(TimeseriesValues[ParameterModel]):
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

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        """Collect the last 30 days of one parameter of one station."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.sr.request.settings)
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
                "date_obs": "timestamp",
                "resultat_obs": "value",
                "code_qualification_obs": "quality_flags",
            },
        )
        return df.select(
            # not lowercased: `_create_humanized_parameters_mapping` and the skip-criteria check
            # both key on `name_original` as declared, so a lowercased value never matched --
            # Hubeau silently never humanized and every station counted as having no data
            pl.lit(parameter_or_dataset.name_original).alias("parameter"),
            pl.col("timestamp").str.to_datetime(format="%Y-%m-%dT%H:%M:%SZ").dt.replace_time_zone("UTC"),
            "value",
            # the qualification code as Hubeau writes it, a whole number: "12", not "12.0"
            pl.col("quality_flags").cast(pl.Int64).cast(pl.String),
        )


@dataclass
class HubeauRequest(TimeseriesRequest):
    """Request class for Eaufrance Hubeau data."""

    metadata = HubeauMetadata
    _values = HubeauValues

    _endpoint = _STATIONS_ENDPOINT

    # the stations the last `_all` left without a position, with what the referential wrote of it (`_warn_unplaced`).
    # Filled in place, so that the copy `interpolate` and `summarize` make of the request has it too
    _unplaced_positions: dict[str, str] = field(default_factory=dict, init=False, repr=False, compare=False)

    # `altitude_ref_alti_station` is the altitude of the gauge's zero in metres -- the datum a stage
    # is read from, below sea level on tidal reaches (-1.809 m at Bordeaux) -- not the ground the
    # station stands on. It goes in `gauge_zero`, as Pegelonline's does, and `elevation` is the
    # altitude of the station's site, from the sites referential. `gauge_zero_datum` names the
    # vertical reference system `gauge_zero` is given in, which differs between stations.
    _base_columns: ClassVar = (
        *TimeseriesRequest._base_columns,  # noqa: SLF001
        "gauge_zero",
        "gauge_zero_datum",
    )

    def _warn_unplaced(self, df: pl.DataFrame, *, named: bool) -> None:
        """Tell, once for the answer, which of the stations are listed without a position (GH-3468).

        The core asks where the warning concerns the answer: for the stations it holds, or for every station when a
        search by place had to leave them out. For the whole list and a search by place, an answer cut to the window
        of the request tells only the stations that survive the cut; one named by id or SQL is told whatever the
        window does to it. The warning is recorded for the answer of every request it concerns and logged once by the
        process, as the next ones would repeat it.
        """
        if not self._unplaced_positions:
            return
        if not named:
            df = self._within_answer_window(df)
        wanted = set(df.get_column("station_id"))
        written = {station_id: text for station_id, text in self._unplaced_positions.items() if station_id in wanted}
        if not written:
            return
        message = _unplaced_message(written)
        first = message not in _reported_unplaced
        _reported_unplaced.add(message)
        warn_response(log, POSITION_UNPLACED, message, level=logging.WARNING if first else logging.DEBUG)

    def _observation_dates(self, url: str) -> pl.DataFrame:
        """Read the timestamps one observations query carries.

        Returns:
            Frame of ``station_id`` and ``timestamp``, one row per observation.

        """
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        rows = _paged_rows(url, settings, ttl=CacheExpiry.METAINDEX, timeout=_SNIFF_TIMEOUT)
        if not rows:
            return pl.DataFrame(schema={"station_id": pl.String, "timestamp": pl.Datetime(time_unit="us")})
        df = pl.from_dicts(rows, schema={"code_station": pl.String, "date_obs": pl.String})
        return df.select(
            pl.col("code_station").alias("station_id"),
            pl.col("date_obs").str.to_datetime(format="%Y-%m-%dT%H:%M:%SZ").alias("timestamp"),
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

    def _site_elevations(self) -> pl.DataFrame:
        """Read the altitude of every hydrometric site.

        Returns:
            Frame of ``code_site`` and ``elevation``, null where the site publishes no altitude or
            one that cannot be the ground's -- see ``_ELEVATION_MIN``. Empty when the referential
            cannot be read: the elevation is all it supplies, and a station list without one is
            better than none at all. Not when no connection can be made, which raises
            ``NoInternetError`` as the station list it enriches would.

        """
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        error: Exception | None = None
        try:
            rows = _paged_rows(_SITES_ENDPOINT, settings, ttl=CacheExpiry.METAINDEX, timeout=_REFERENTIAL_TIMEOUT)
        except NoInternetError:
            # not a referential that is unreadable: a library that is offline, which the station
            # list this enriches would be too (GH-2640)
            raise
        except (DownloadError, OSError, ClientError, ValueError) as e:
            # `DownloadError` is what `raise_if_exception` raises for a timeout, a missing file, and
            # a refused or broken response (GH-2460); a body that is not JSON is a `ValueError`, and
            # a cache dir that cannot be written an `OSError`, as is a timeout. The aiohttp types
            # are what the download raised itself before GH-2460, kept for a caller that still
            # sends them
            rows, error = [], e
        # no rows without an error is a referential that answered with no page -- it always lists
        # thousands of sites
        if not rows:
            reason = f": {error!r}" if error else ""
            log.warning(f"Hubeau's sites referential could not be read, stations are listed without elevation{reason}")
        df = pl.from_dicts(rows, schema={"code_site": pl.String, "altitude_site": pl.Float64})
        altitude = pl.col("altitude_site")
        return df.select(
            "code_site",
            pl.when(altitude.is_between(_ELEVATION_MIN, _ELEVATION_MAX, closed="left") & (altitude != 0))
            .then(altitude)
            .alias("elevation"),
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
        rows = _paged_rows(self._endpoint, settings, ttl=CacheExpiry.METAINDEX, timeout=_REFERENTIAL_TIMEOUT)
        if not rows:
            return pl.LazyFrame()
        df_raw, unplaced = _referential_stations(rows)
        self._unplaced_positions.clear()
        self._unplaced_positions.update(unplaced)
        df_raw = df_raw.with_columns(
            pl.col("code_systeme_alti_site")
            .replace_strict(_SYSTEME_ALTI_LABELS, default=pl.col("code_systeme_alti_site").cast(pl.String))
            .alias("gauge_zero_datum"),
            pl.col("start_timestamp").str.to_datetime(time_zone="UTC"),
            # a station in service has no `date_fermeture_station`, so it has no end: null, as other
            # providers give it, rather than the time of the call
            pl.col("end_timestamp").str.to_datetime(time_zone="UTC"),
        )
        # A station belongs to the resolution it transmits at, which is measured rather than
        # declared -- see `_STEP_TO_RESOLUTION`. One that has published nothing to measure is
        # listed under no resolution: naming an interval for it would be a guess, and the join
        # below drops it. It returns to the list as soon as it transmits again.
        steps = self._station_steps(df_raw.get_column("station_id").to_list())
        df = df_raw.join(steps, on="station_id", how="inner")
        df = df.join(self._site_elevations(), on="code_site", how="left")
        df = df.with_columns(
            pl.col("step").replace_strict(_STEP_TO_RESOLUTION, default=None).alias("resolution"),
            pl.lit(DATASET_NAME_DEFAULT, pl.String).alias("dataset"),
        )
        # what the join needed and the stations frame has no column for
        return (
            df.filter(pl.col("resolution").is_in(requested)).drop("code_site", "code_systeme_alti_site", "step").lazy()
        )
