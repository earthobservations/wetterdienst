# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The rules every provider's station catalogue is held to (GH-2616).

A defect in a catalogue is silent: a station whose coordinates are swapped lands in another country and is picked by
a nearest-station search, a duplicated id doubles its values, an elevation of -999 breaks a height filter, and an end
date before the start date drops the station from every period filter. The tests of a provider mostly assert that a
known station is listed, not that the list is sound, so the rules live here once and are applied to every catalogue
by `test_station_catalogue_stubs.py` (offline, to a stub of each provider's list) and by
`test_station_catalogues_live.py` (against the live lists, which show what a stub cannot).

A rule that a catalogue breaks on purpose or by the source's own doing is named in `Accepted` with its reason, never
skipped, and in the offline test an `Accepted` that matches nothing fails, so a fixed defect cannot leave its
exception behind. The live test cannot hold to that, as a source that fixes a defect is no failure of ours.

To hold a new provider to the rules, add a stub of its catalogue to `station_catalogue_stubs.py` and, if it is
published for one country, its bounding box to `COUNTRY_BBOX`.

Two rules need the data files beside the list (GH-3248): a listed station has data in its resolution, and every data
file has a station in the catalogue. `check_coverage` applies them to the ids that `station_data_index.py` reads, and
`Accepted` names the mismatches of a source in the same way.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, NamedTuple

import polars as pl

from wetterdienst.provider.eaufrance.hubeau import api as hubeau_api

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from wetterdienst.model.metadata import Extent, MetadataModel

#: (south, north, west, east) in degrees
Bbox = tuple[float, float, float, float]

# (south, north, west, east) in degrees, generous: the rule catches a station in another country, not a station near
# the border. A provider is left out where its catalogue is not one country's: the global lists (MOSMIX, DMO, SYNOP,
# GHCN, POI), the NWS with its Pacific and Caribbean territories. Hubeau has overseas departments, so its country is
# several boxes (GH-3468), the very boxes its reader swaps a misplaced position by: a station is in the country when it
# is in one of them
COUNTRY_BBOX: dict[str, Bbox | tuple[Bbox, ...]] = {
    "chmi/observation": (48.5, 51.1, 12.0, 18.9),
    "dmi/observation": (54.0, 84.0, -75.0, 16.0),  # Denmark with Greenland
    "dwd/derived": (47.2, 55.1, 5.8, 15.1),
    "dwd/observation": (47.2, 55.1, 5.8, 15.1),
    "dwd/phenology": (47.2, 55.1, 5.8, 15.1),
    "dwd/road": (47.2, 55.1, 5.8, 15.1),
    "dwd/swsmos": (47.2, 55.1, 5.8, 15.1),
    "eaufrance/hubeau": tuple(hubeau_api._AREAS.values()),  # noqa: SLF001
    "eccc/observation": (41.0, 84.0, -142.0, -52.0),
    "ea/hydrology": (49.8, 55.9, -6.0, 2.0),
    "fmi/observation": (59.0, 70.2, 19.0, 32.0),
    "geosphere/observation": (46.3, 49.1, 9.4, 17.3),
    "imgw/hydrology": (49.0, 54.9, 14.1, 24.2),
    "imgw/meteorology": (49.0, 54.9, 14.1, 24.2),
    "ipma/observation": (30.0, 42.2, -31.5, -6.1),  # with Madeira and the Azores
    "lhmt/observation": (53.8, 56.5, 20.9, 26.9),
    "meteoswiss/observation": (45.7, 47.9, 5.9, 10.6),
    "rmi/observation": (49.4, 51.6, 2.5, 6.5),
    "smhi/observation": (55.0, 69.1, 10.9, 24.2),
    "wsv/pegel": (47.2, 55.1, 5.8, 15.1),
}

# the boxes of the continents, `(south, north, west, east)`, coarse and generous where two meet (Russia is in the
# one of Europe and the one of Asia, Turkey east of 34 degrees east in the one of Asia too). They are no map: a station
# on a border may be in two or none, and they serve two sanity checks only. A declared continent has a station within
# `CONTINENT_MARGIN` degrees of its boxes, and a global network has stations on five continents. Which continents a
# network *names* is declared by hand, as the areas it is meant to serve, see `tests/metadata/test_extent.py`
CONTINENT_BOXES: dict[str, tuple[tuple[float, float, float, float], ...]] = {
    "africa": (
        (-35.0, 33.0, -20.0, 34.0),  # with the Canary Islands and Madeira
        (33.0, 36.0, -13.0, -1.0),  # Morocco to Ceuta
        (30.0, 37.4, -1.0, 12.0),  # Algeria and Tunisia, not the south of Spain
        (-35.0, 12.0, 34.0, 52.0),
        (12.0, 24.0, 34.0, 38.0),  # the Red Sea coast of Sudan and Eritrea
        (-26.0, -12.0, 52.0, 58.0),  # Reunion, Mauritius
    ),
    "antarctica": ((-90.0, -60.0, -180.0, 180.0),),
    "asia": ((21.0, 82.0, 34.0, 180.0), (12.0, 21.0, 34.0, 130.0), (-11.0, 12.0, 52.0, 130.0)),
    "europe": ((34.0, 82.0, -32.0, 60.0),),
    "north_america": (
        (7.0, 84.0, -170.0, -50.0),
        (59.0, 84.0, -73.0, -26.0),  # Greenland, without Iceland (63 to 66.5 north, 13 to 24 west)
        (67.0, 84.0, -26.0, -10.0),
        (50.0, 56.0, 170.0, 180.0),  # the Aleutians
    ),
    "oceania": (
        (-48.0, -10.5, 112.0, 180.0),
        (-10.5, 21.0, 130.0, 180.0),  # New Guinea, Micronesia, Guam
        (-30.0, 30.0, -180.0, -130.0),  # Polynesia, Hawaii
        (-48.0, -30.0, -180.0, -170.0),
    ),
    "south_america": ((-57.0, 13.0, -82.0, -34.0),),
}
# the margin, in degrees, a declared continent has to find a station within: a territory is a little outside its box
CONTINENT_MARGIN = 2.0
# how many degrees the declared box of a network may reach beyond the box of its stations, on each side: a box of the
# whole Earth for a network of one country is no extent
EXTENT_SLACK = 5.0
# the stations a continent needs for a global network to count it
GLOBAL_STATIONS_PER_CONTINENT = 3

# the lowest and the highest dry land on Earth: the Dead Sea shore and Mount Everest
ELEVATION_RANGE = (-430.0, 8849.0)
# the numbers sources use for a missing height
ELEVATION_SENTINELS = (-99999.0, -9999.0, -999.9, -999.0, -99.0, 9999.0, 99999.0)
# no station catalogue lists a station that began before this
EARLIEST_START = dt.datetime(1600, 1, 1, tzinfo=dt.UTC)

RULES = (
    "id_empty",
    "id_whitespace",
    "id_duplicate",
    "id_collision",
    "coordinates_missing",
    "coordinates_out_of_range",
    "coordinates_null_island",
    "coordinates_outside_country",
    "elevation_sentinel",
    "elevation_out_of_range",
    "date_order",
    "date_in_the_future",
    "date_implausible",
    "name_empty",
    "name_padding",
    "name_encoding",
)

# the two rules that need the data beside the list (GH-3248, point 6 of GH-2616), applied by `check_coverage` to a
# catalogue and the ids of the data files of its resolution: a station that is listed and has no data, and a data file
# of a station the list does not carry. An id that differs from the file name only in padding or case breaks both,
# where the reader does not join the list to the files
COVERAGE_RULES = ("data_missing", "data_orphan")

# the rule of `check_extent` (GH-3456): a station outside the box its network declares. An `Accepted` may cover it,
# for a source that lists a station where the network is not
EXTENT_RULES = ("coordinates_outside_extent",)
#: the stations outside the extent that a failure names, each once: the log of CI is all that is read of a live list
#: that needs a key, so the remaining ones are named in full, and a network that is wrong as a whole is not
EXTENT_LISTED = 100

# what a UTF-8 text read as Latin-1 or Windows-1252 turns into: the lead byte of a two-byte character (Ã, Â for the
# Latin-1 letters, Å, Ä for Latin Extended-A such as ż and č) followed by a continuation byte read as a control
# character, a symbol or one of the Windows-1252 punctuation marks (Ã¼ for ü, Ã\u0178 for ß, Å¼ for ż), â€ for a dash,
# the replacement character, and the question mark a lossy conversion leaves for a character it could not encode.
# A capital Ã, Â, Å or Ä followed by a letter is a letter of Portuguese, Finnish or Swedish (SÃO PAULO, ÄÄNEKOSKI).
# The Windows-1252 punctuation stands in for the bytes 0x82 to 0x9F
_CP1252_PUNCTUATION = "".join(
    rf"\x{{{c}}}"
    for c in (
        "201A",
        "0192",
        "201E",
        "2026",
        "2020",
        "2021",
        "02C6",
        "2030",
        "0160",
        "2039",
        "0152",
        "017D",
        "2018",
        "2019",
        "201C",
        "201D",
        "2022",
        "2013",
        "2014",
        "02DC",
        "2122",
        "0161",
        "203A",
        "0153",
        "017E",
        "0178",
    )
)
_CONTINUATION = rf"\x{{80}}-\x{{BF}}{_CP1252_PUNCTUATION}"
_ENCODING_DAMAGE = rf"\x{{FFFD}}|[ÃÂÅÄ][{_CONTINUATION}]|â€|\?"


def has_encoding_damage(text: str, *, question_marks: bool = True) -> bool:
    """Say whether a name has damaged characters, leaving the question marks out of it if `question_marks` is False."""
    series = pl.Series([text if question_marks else text.replace("?", " ")], dtype=pl.String)
    return bool(series.str.contains(_ENCODING_DAMAGE)[0])


class Violation(NamedTuple):
    """One station that breaks one rule."""

    catalogue: str
    rule: str
    station_id: str | None
    detail: str
    row: dict[str, Any]

    def __str__(self) -> str:
        """Name the catalogue, the rule and the station, which is what a failure has to say."""
        return f"{self.catalogue}: {self.rule}: station {self.station_id!r}: {self.detail}"


@dataclass(frozen=True)
class Accepted:
    """A rule a catalogue breaks on purpose or through its source, with the reason, for the stations it matches."""

    rule: str
    reason: str
    # the stations it covers, as a test of the catalogue row; every station that breaks the rule when None
    where: Callable[[dict[str, Any]], bool] | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        """Refuse a rule that does not exist and an exception that gives no reason."""
        if self.rule not in (*RULES, *COVERAGE_RULES, *EXTENT_RULES):
            msg = f"unknown rule {self.rule!r}, the rules are {', '.join((*RULES, *COVERAGE_RULES, *EXTENT_RULES))}"
            raise ValueError(msg)
        if not self.reason.strip():
            msg = f"the exception for {self.rule} has no reason"
            raise ValueError(msg)

    def covers(self, violation: Violation) -> bool:
        """Say whether the violation is one this exception names."""
        return violation.rule == self.rule and (self.where is None or self.where(violation.row))


# Frost lists the foreign SYNOP stations it holds beside the Norwegian ones: `SN` + the WMO number x 100, so six or
# seven digits ending in `00`, where a Norwegian id has at most five (GH-3488)
FROST_FOREIGN_WMO = Accepted(
    "coordinates_outside_extent",
    "Frost lists the foreign SYNOP stations it holds beside the Norwegian ones, as `SN` + the WMO number x 100 (six or "
    "seven digits ending in 00; the Norwegian ids have at most five): SN1039300 is 10393 Lindenberg (DE; DWD's list "
    "has 03015 at 52.2085, 14.1180, 200 m from the listed position), SN743400 is 07434 Limoges-Bellegarde (FR; NOAA's "
    "isd-history has 45.863, 1.179), SN623500 is 06235 De Kooy (NL), SN848200 is 08482 Malaga (ES), SN1240000 is "
    "12400 Zielona Gora (PL), SN1298200 is 12982 Szeged (HU): more than two hundred in all, with positions that are "
    "right and stations that are not in Norway. The library passes them on, and the extent stays that of Norway; "
    "a Norwegian id outside the box is still a failure",
    where=lambda row: re.fullmatch(r"SN\d{4,5}00", row["station_id"]) is not None,
)


# Norway has research stations in Antarctica (Troll and its surroundings in Queen Maud Land, near 72 S): a station south
# of 60 S, the limit of the Antarctic Treaty, is taken for one of them. It lies outside the national extent, which stays
# that of Norway (GH-3488). Known from the log of CI: SN99990 at (-72.012, 2.5408) and SN92100 at (-71.9563, 2.4668);
# the list itself needs a key and was not read
FROST_ANTARCTIC = Accepted(
    "coordinates_outside_extent",
    "Norway has research stations in Antarctica (Troll and its surroundings in Queen Maud Land, near 72 S), which "
    "Frost lists with the others: SN99990 at (-72.012, 2.5408) and SN92100 at (-71.9563, 2.4668). A station south of "
    "60 S, the limit of the Antarctic Treaty, is taken for one of them, and the extent stays that of Norway",
    where=lambda row: row["latitude"] < -60.0,
)


def _violations(
    df: pl.DataFrame,
    catalogue: str,
    rule: str,
    mask: pl.Expr,
    detail: Callable[[dict[str, Any]], str],
) -> list[Violation]:
    return [
        Violation(catalogue, rule, row["station_id"], detail(row), row) for row in df.filter(mask).iter_rows(named=True)
    ]


def boxes_of(bbox: Bbox | tuple[Bbox, ...]) -> tuple[Bbox, ...]:
    """Give the boxes of a country: the one box, or the several of a country with territories far from it."""
    return (bbox,) if isinstance(bbox[0], float | int) else bbox  # ty: ignore[invalid-return-type]


def _fits(lat: float | None, lon: float | None, bbox: Bbox | tuple[Bbox, ...]) -> bool:
    return (
        lat is not None
        and lon is not None
        and any(south <= lat <= north and west <= lon <= east for south, north, west, east in boxes_of(bbox))
    )


def check_catalogue(
    df: pl.DataFrame,
    catalogue: str,
    *,
    bbox: Bbox | tuple[Bbox, ...] | None = None,
    now: dt.datetime | None = None,
) -> list[Violation]:
    """Apply every rule to a catalogue and return the violations, which are not yet filtered by `Accepted`.

    Args:
        df: the stations, with the base columns of a station request
        catalogue: how the failure names the catalogue, such as `chmi/observation daily/data`
        bbox: the (south, north, west, east) box of the country the catalogue is published for, if it is one, or the
            several boxes of a country with territories far from it: a station has to be in one of them
        now: the time the end of a station is held against, the present when None

    """
    now = now or dt.datetime.now(dt.UTC)
    tomorrow = now + dt.timedelta(days=1)
    station = pl.col("station_id")
    lat, lon, elevation = pl.col("latitude"), pl.col("longitude"), pl.col("elevation")
    start, end = pl.col("start_timestamp"), pl.col("end_timestamp")
    name = pl.col("name")
    # the identity of a station is its id within one resolution and dataset: several of them share a catalogue
    scope = ["resolution", "dataset"]
    found: list[Violation] = []

    found += _violations(
        df, catalogue, "id_empty", station.is_null() | (station.str.strip_chars() == ""), lambda _: "the id is empty"
    )
    found += _violations(
        df,
        catalogue,
        "id_whitespace",
        station.is_not_null() & (station != station.str.strip_chars()),
        lambda row: f"the id {row['station_id']!r} has whitespace around it",
    )
    found += _violations(
        df,
        catalogue,
        "id_duplicate",
        station.is_not_null() & (station.count().over([*scope, station]) > 1),
        lambda row: f"listed more than once in {row['resolution']}/{row['dataset']}",
    )
    # ids that differ only in padding, case or whitespace name one station twice for a caller who types it differently
    normal = station.str.strip_chars().str.to_uppercase().str.strip_chars_start("0")
    found += _violations(
        df.filter(station.is_not_null()),
        catalogue,
        "id_collision",
        station.n_unique().over([*scope, normal]) > 1,
        lambda row: f"{row['station_id']!r} equals another id but for padding, case or whitespace",
    )

    found += _violations(
        df,
        catalogue,
        "coordinates_missing",
        lat.is_null() | lon.is_null(),
        lambda row: f"latitude {row['latitude']}, longitude {row['longitude']}",
    )
    found += _violations(
        df,
        catalogue,
        "coordinates_out_of_range",
        (lat.abs() > 90) | (lon.abs() > 180),
        lambda row: f"latitude {row['latitude']}, longitude {row['longitude']} is not a place on Earth",
    )
    found += _violations(
        df,
        catalogue,
        "coordinates_null_island",
        (lat == 0) & (lon == 0),
        lambda _: "latitude and longitude are both 0, a missing value read as a position",
    )
    if bbox:

        def outside(row: dict[str, Any]) -> str:
            lat_, lon_ = row["latitude"], row["longitude"]
            hint = ""
            if _fits(lon_, lat_, bbox):
                hint = ", latitude and longitude are swapped"
            elif _fits(lat_, -lon_, bbox):
                hint = ", the longitude lost its sign"
            elif _fits(-lat_, lon_, bbox):
                hint = ", the latitude lost its sign"
            return f"({lat_}, {lon_}) is outside {bbox}{hint}"

        in_the_country = pl.any_horizontal(
            lat.is_between(south, north) & lon.is_between(west, east) for south, north, west, east in boxes_of(bbox)
        )
        found += _violations(
            df,
            catalogue,
            "coordinates_outside_country",
            lat.is_not_null() & lon.is_not_null() & ~in_the_country,
            outside,
        )

    found += _violations(
        df,
        catalogue,
        "elevation_sentinel",
        elevation.is_in(list(ELEVATION_SENTINELS)),
        lambda row: f"elevation {row['elevation']} is how a source marks a missing height",
    )
    low, high = ELEVATION_RANGE
    found += _violations(
        df,
        catalogue,
        "elevation_out_of_range",
        (elevation < low) | (elevation > high),
        lambda row: f"elevation {row['elevation']} m is beyond the lowest and the highest dry land",
    )

    found += _violations(
        df,
        catalogue,
        "date_order",
        start > end,
        lambda row: f"starts {row['start_timestamp']} and ends {row['end_timestamp']}",
    )
    found += _violations(
        df,
        catalogue,
        "date_in_the_future",
        (start > tomorrow) | (end > tomorrow),
        lambda row: f"starts {row['start_timestamp']} and ends {row['end_timestamp']}, after {now:%Y-%m-%d}",
    )
    found += _violations(
        df,
        catalogue,
        "date_implausible",
        (start < EARLIEST_START) | (end < EARLIEST_START),
        lambda row: f"starts {row['start_timestamp']} and ends {row['end_timestamp']}",
    )

    found += _violations(
        df, catalogue, "name_empty", name.is_null() | (name.str.strip_chars() == ""), lambda _: "the name is empty"
    )
    found += _violations(
        df,
        catalogue,
        "name_padding",
        name.is_not_null() & (name != name.str.strip_chars()),
        lambda row: f"the name {row['name']!r} has whitespace around it",
    )
    found += _violations(
        df,
        catalogue,
        "name_encoding",
        name.is_not_null() & name.str.contains(_ENCODING_DAMAGE),
        lambda row: f"the name {row['name']!r} has damaged characters",
    )
    return found


def unaccepted(
    violations: Iterable[Violation],
    accepted: Iterable[Accepted] = (),
) -> tuple[list[Violation], list[Accepted]]:
    """Split off the violations that are named exceptions, and return the rest with the exceptions that matched none.

    Returns:
        the violations no `Accepted` covers, and the `Accepted` entries that cover no violation

    """
    violations = list(violations)
    accepted = list(accepted)
    used: set[int] = set()
    left = []
    for violation in violations:
        covered = False
        for index, exception in enumerate(accepted):
            if exception.covers(violation):
                used.add(index)
                covered = True
        if not covered:
            left.append(violation)
    stale = [exception for index, exception in enumerate(accepted) if index not in used]
    return left, stale


def assert_sound(
    df: pl.DataFrame,
    catalogue: str,
    *,
    bbox: Bbox | tuple[Bbox, ...] | None = None,
    accepted: Iterable[Accepted] = (),
    now: dt.datetime | None = None,
    limit: int = 10,
    fail_on_stale: bool = True,
) -> None:
    """Raise an `AssertionError` that lists the provider, station and rule of every violation left after `accepted`.

    A stale exception fails as well, unless `fail_on_stale` is False, and an empty catalogue does: a rule over no
    stations passes whatever is wrong. A live catalogue turns `fail_on_stale` off, as a source that fixes a defect is
    no failure of ours.
    """
    assert not df.is_empty(), f"{catalogue}: the catalogue is empty, so no rule was applied"
    left, stale = unaccepted(check_catalogue(df, catalogue, bbox=bbox, now=now), accepted)
    _assert_none_left(left, stale if fail_on_stale else [], catalogue, limit)


def continent_counts(df: pl.DataFrame, margin: float = 0.0) -> dict[str, int]:
    """Count the stations in the boxes of each continent, widened by `margin`; one in two boxes counts for both."""
    counts = {}
    for continent, boxes in CONTINENT_BOXES.items():
        in_a_box = pl.any_horizontal(
            pl.col("latitude").is_between(south - margin, north + margin)
            & pl.col("longitude").is_between(west - margin, east + margin)
            for south, north, west, east in boxes
        )
        counts[continent] = df.filter(in_a_box).height
    return counts


def check_extent(
    df: pl.DataFrame,
    network: str,
    extent: Extent,
    *,
    whole: bool = False,
    accepted: Iterable[Accepted] = (),
) -> list[str]:
    """Hold the stations of a network to the extent its metadata declares, and say what they break (GH-3456).

    Every station has to be in the declared box, which the extent of a dataset that is a part of the network (the
    European list of `dwd/dmo`) does as well as the whole. With `whole`, the stations of all the datasets of the
    network, the rest is held too: the box is no more than `EXTENT_SLACK` degrees wider than the stations on each
    side, each continent it names has a station near its box (`CONTINENT_MARGIN`), and a global network has
    `GLOBAL_STATIONS_PER_CONTINENT` or more on five continents.

    A station outside the box that an `Accepted` of the rule `coordinates_outside_extent` covers is no failure, and
    is not one of the stations the box and the continents are compared with.
    """
    stations = df.filter(pl.col("latitude").is_not_null() & pl.col("longitude").is_not_null())
    if stations.is_empty():
        return [f"{network}: the catalogue has no station with a position, so no extent was checked"]
    west, south, east, north = extent.bbox
    outside = stations.filter(
        ~(pl.col("latitude").is_between(south, north) & pl.col("longitude").is_between(west, east))
    )
    violations = [
        Violation(network, "coordinates_outside_extent", row["station_id"], "outside the extent", row)
        for row in outside.iter_rows(named=True)
    ]
    left, _ = unaccepted(violations, accepted)
    # a station once, whatever the number of datasets that list it: the lists of the datasets of a network are held
    # together, and the same station again is not another station to the reader of the failure
    listed = list({violation.station_id: violation for violation in left}.values())
    problems = [
        f"{network}: station {violation.station_id} at ({violation.row['latitude']}, {violation.row['longitude']}) "
        f"is outside the extent [west {west}, south {south}, east {east}, north {north}]"
        for violation in listed[:EXTENT_LISTED]
    ]
    if len(listed) > EXTENT_LISTED:
        problems.append(f"{network}: ... and {len(listed) - EXTENT_LISTED} more stations outside the extent")
    if not whole:
        return problems
    left_ids = {violation.station_id for violation in left}
    excused = [violation.station_id for violation in violations if violation.station_id not in left_ids]
    stations = stations.filter(~pl.col("station_id").is_in(excused))
    if stations.is_empty():
        return [*problems, f"{network}: no station is left in the extent, so it was not compared with the stations"]
    held = (
        stations["longitude"].min(),
        stations["latitude"].min(),
        stations["longitude"].max(),
        stations["latitude"].max(),
    )
    if extent.scope != "global":
        sides = ("west", "south", "east", "north")
        slack = (held[0] - west, held[1] - south, east - held[2], north - held[3])
        problems += [
            f"{network}: the extent reaches {amount:.1f} degrees {side} of its stations, more than {EXTENT_SLACK}"
            for side, amount in zip(sides, slack, strict=True)
            if amount > EXTENT_SLACK
        ]
    # one direction only: the continents are the areas the network is meant to serve, declared by hand, so each has to
    # have a station near its box; a station on a continent that is not named is no failure (a territory may be
    # left out)
    near = continent_counts(stations, CONTINENT_MARGIN)
    problems += [
        f"{network}: the extent names {continent}, and no station is within {CONTINENT_MARGIN} degrees of its box"
        for continent in extent.continents
        if not near[continent]
    ]
    if extent.scope == "global":
        counts = continent_counts(stations)
        reached = [continent for continent, count in counts.items() if count >= GLOBAL_STATIONS_PER_CONTINENT]
        if len(reached) < 5:
            problems.append(f"{network}: a global network has stations on {len(reached)} continents ({reached})")
    return problems


def extent_of(metadata: MetadataModel, label: str) -> Extent:
    """Give the extent a catalogue is held to: its dataset's where it declares one, else its network's.

    `label` is `resolution/dataset` as a stub names it, or `resolution+resolution/dataset` for a catalogue of two.
    """
    resolutions, _, dataset = label.rpartition("/")
    for resolution in resolutions.split("+"):
        own = metadata[resolution][dataset].extent
        if own is not None:
            return own
    return metadata.extent


def assert_in_extent(
    df: pl.DataFrame,
    network: str,
    extent: Extent,
    *,
    whole: bool = False,
    accepted: Iterable[Accepted] = (),
) -> None:
    """Raise an `AssertionError` that lists what the stations of a network break of the extent it declares."""
    problems = check_extent(df, network, extent, whole=whole, accepted=accepted)
    assert not problems, "\n".join(problems)


def _assert_none_left(left: list[Violation], stale: list[Accepted], catalogue: str, limit: int) -> None:
    # at most `limit` of each rule, so that a rule broken by thousands of stations does not hide the others
    problems = []
    for rule in dict.fromkeys(violation.rule for violation in left):
        broken = [violation for violation in left if violation.rule == rule]
        problems += [str(violation) for violation in broken[:limit]]
        if len(broken) > limit:
            problems.append(f"{catalogue}: {rule}: ... and {len(broken) - limit} more")
    problems += [
        f"{catalogue}: the exception for {exception.rule} matches no station: {exception.reason}" for exception in stale
    ]
    assert not problems, "\n".join(problems)


def _same_id(station_id: str) -> str:
    """Give an id as the rule `id_collision` reads it: without whitespace, case or the zeros of a padding."""
    return station_id.strip().upper().lstrip("0")


def check_coverage(
    df: pl.DataFrame,
    data_ids: Iterable[str],
    catalogue: str,
    *,
    rules: Iterable[str] = COVERAGE_RULES,
) -> list[Violation]:
    """Compare the stations of a catalogue with the ids of the data files of the same resolution and dataset.

    Args:
        df: the stations of one resolution and dataset, with the base columns of a station request
        data_ids: the station ids the data files of that resolution and dataset are named for
        catalogue: how the failure names the catalogue, such as `chmi/observation daily/data`
        rules: the coverage rules to apply, for a source whose data cannot be held to both

    Returns:
        a violation for every station without a data file and for every data file without a station, which an
        `Accepted` may still cover. Where the one is the other under another spelling (padding, case), the detail
        says which, so the reader that normalises one side and not the other is found.

    """
    rules = set(rules)
    assert rules <= set(COVERAGE_RULES), f"unknown coverage rules {sorted(rules - set(COVERAGE_RULES))}"
    listed = {station_id for station_id in df.get_column("station_id") if station_id is not None}
    data = set(data_ids)
    resolution, dataset = df.row(0, named=True)["resolution"], df.row(0, named=True)["dataset"]
    spelled_as_data = {_same_id(station_id): station_id for station_id in data - listed}
    spelled_as_listed = {_same_id(station_id): station_id for station_id in listed - data}
    found: list[Violation] = []
    if "data_missing" in rules:
        for row in df.sort("station_id").iter_rows(named=True):
            station_id = row["station_id"]
            if station_id is None or station_id in data:
                continue
            detail = f"listed in {resolution}/{dataset} and no data file is named for it"
            if (other := spelled_as_data.get(_same_id(station_id))) is not None:
                detail += f", the data files name {other!r}, the same id but for padding or case"
            found.append(Violation(catalogue, "data_missing", station_id, detail, row))
    if "data_orphan" in rules:
        for station_id in sorted(data - listed):
            detail = f"a data file of {resolution}/{dataset} is named for it and the catalogue does not list it"
            if (other := spelled_as_listed.get(_same_id(station_id))) is not None:
                detail += f", the catalogue lists {other!r}, the same id but for padding or case"
            row = {"station_id": station_id, "resolution": resolution, "dataset": dataset}
            found.append(Violation(catalogue, "data_orphan", station_id, detail, row))
    return found


def assert_covered(
    df: pl.DataFrame,
    data_ids: Iterable[str],
    catalogue: str,
    *,
    accepted: Iterable[Accepted] = (),
    rules: Iterable[str] = COVERAGE_RULES,
    limit: int = 10,
    fail_on_stale: bool = True,
) -> None:
    """Raise an `AssertionError` that lists the station and rule of every coverage violation left after `accepted`.

    An empty catalogue fails, and so does an empty list of data ids: a rule over nothing passes whatever is wrong, and
    a source whose listing came back empty is a listing that failed, not a network without data.
    """
    data_ids = list(data_ids)
    assert not df.is_empty(), f"{catalogue}: the catalogue is empty, so no rule was applied"
    assert data_ids, f"{catalogue}: no data file is listed, so no rule was applied"
    rules, accepted = tuple(rules), list(accepted)
    not_applied = [exception.rule for exception in accepted if exception.rule not in rules]
    assert not not_applied, f"{catalogue}: an exception names {not_applied}, which is not applied to this source"
    left, stale = unaccepted(check_coverage(df, data_ids, catalogue, rules=rules), accepted)
    _assert_none_left(left, stale if fail_on_stale else [], catalogue, limit)
