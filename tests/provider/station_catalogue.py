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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, NamedTuple

import polars as pl

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from wetterdienst.model.metadata import ExtentModel

# (south, north, west, east) in degrees, generous: the rule catches a station in another country, not a station near
# the border. A provider is left out where its catalogue is not one country's: the global lists (MOSMIX, DMO, SYNOP,
# GHCN, POI), Hubeau with its overseas departments, the NWS with its Pacific and Caribbean territories
COUNTRY_BBOX: dict[str, tuple[float, float, float, float]] = {
    "chmi/observation": (48.5, 51.1, 12.0, 18.9),
    "dmi/observation": (54.0, 84.0, -75.0, 16.0),  # Denmark with Greenland
    "dwd/derived": (47.2, 55.1, 5.8, 15.1),
    "dwd/observation": (47.2, 55.1, 5.8, 15.1),
    "dwd/phenology": (47.2, 55.1, 5.8, 15.1),
    "dwd/road": (47.2, 55.1, 5.8, 15.1),
    "dwd/swsmos": (47.2, 55.1, 5.8, 15.1),
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
# one of Europe and the one of Asia, the Arabian coast in the one of Africa and of Asia): a station that is in one of
# them is counted for it. They tell a network that has stations on five continents from one that has them on two, not
# which continent a station on a border is on
CONTINENT_BOXES: dict[str, tuple[tuple[float, float, float, float], ...]] = {
    "africa": ((-35.0, 37.5, -20.0, 34.0), (-35.0, 12.0, 34.0, 52.0), (-26.0, -12.0, 52.0, 58.0)),
    "antarctica": ((-90.0, -60.0, -180.0, 180.0),),
    "asia": ((12.0, 82.0, 34.0, 180.0), (-11.0, 12.0, 52.0, 180.0)),
    "europe": ((34.0, 82.0, -32.0, 60.0),),
    "north_america": ((7.0, 84.0, -170.0, -50.0), (59.0, 84.0, -73.0, -10.0)),
    "oceania": ((-48.0, 0.0, 110.0, 180.0), (-30.0, 30.0, -180.0, -130.0), (-48.0, -30.0, -180.0, -170.0)),
    "south_america": ((-57.0, 13.0, -82.0, -34.0),),
}
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
        if self.rule not in (*RULES, *COVERAGE_RULES):
            msg = f"unknown rule {self.rule!r}, the rules are {', '.join((*RULES, *COVERAGE_RULES))}"
            raise ValueError(msg)
        if not self.reason.strip():
            msg = f"the exception for {self.rule} has no reason"
            raise ValueError(msg)

    def covers(self, violation: Violation) -> bool:
        """Say whether the violation is one this exception names."""
        return violation.rule == self.rule and (self.where is None or self.where(violation.row))


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


def _fits(lat: float | None, lon: float | None, bbox: tuple[float, float, float, float]) -> bool:
    south, north, west, east = bbox
    return lat is not None and lon is not None and south <= lat <= north and west <= lon <= east


def check_catalogue(
    df: pl.DataFrame,
    catalogue: str,
    *,
    bbox: tuple[float, float, float, float] | None = None,
    now: dt.datetime | None = None,
) -> list[Violation]:
    """Apply every rule to a catalogue and return the violations, which are not yet filtered by `Accepted`.

    Args:
        df: the stations, with the base columns of a station request
        catalogue: how the failure names the catalogue, such as `chmi/observation daily/data`
        bbox: the (south, north, west, east) box of the country the catalogue is published for, if it is one
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

        south, north, west, east = bbox
        found += _violations(
            df,
            catalogue,
            "coordinates_outside_country",
            lat.is_not_null() & lon.is_not_null() & ~(lat.is_between(south, north) & lon.is_between(west, east)),
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
    bbox: tuple[float, float, float, float] | None = None,
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


def continent_counts(df: pl.DataFrame) -> dict[str, int]:
    """Count the stations of a catalogue in the box of each continent (`CONTINENT_BOXES`), a station in two for both."""
    counts = {}
    for continent, boxes in CONTINENT_BOXES.items():
        in_a_box = pl.any_horizontal(
            pl.col("latitude").is_between(south, north) & pl.col("longitude").is_between(west, east)
            for south, north, west, east in boxes
        )
        counts[continent] = df.filter(in_a_box).height
    return counts


def check_extent(df: pl.DataFrame, network: str, extent: ExtentModel, *, whole: bool = False) -> list[str]:
    """Hold the stations of a network to the extent its metadata declares, and say what they break (GH-3456).

    Every station has to be in the declared box, which the extent of a dataset that is a part of the network (the
    European list of `dwd/dmo`) does as well as the whole. With `whole`, the stations of all the datasets of the
    network, the rest is held too: the box is no more than `EXTENT_SLACK` degrees wider than the stations on each
    side, each continent it names has a station, and a global network has `GLOBAL_STATIONS_PER_CONTINENT` or more on
    five continents.
    """
    stations = df.filter(pl.col("latitude").is_not_null() & pl.col("longitude").is_not_null())
    if stations.is_empty():
        return [f"{network}: the catalogue has no station with a position, so no extent was checked"]
    west, south, east, north = extent.bbox
    outside = stations.filter(
        ~(pl.col("latitude").is_between(south, north) & pl.col("longitude").is_between(west, east))
    )
    problems = [
        f"{network}: station {row['station_id']} at ({row['latitude']}, {row['longitude']}) is outside the extent "
        f"[west {west}, south {south}, east {east}, north {north}]"
        for row in outside.head(5).iter_rows(named=True)
    ]
    if outside.height > 5:
        problems.append(f"{network}: ... and {outside.height - 5} more stations outside the extent")
    if not whole:
        return problems
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
    counts = continent_counts(stations)
    problems += [
        f"{network}: the extent names {continent}, and no station is in its box"
        for continent in extent.continents
        if not counts[continent]
    ]
    if extent.scope == "global":
        reached = [continent for continent, count in counts.items() if count >= GLOBAL_STATIONS_PER_CONTINENT]
        if len(reached) < 5:
            problems.append(f"{network}: a global network has stations on {len(reached)} continents ({reached})")
    return problems


def assert_in_extent(df: pl.DataFrame, network: str, extent: ExtentModel, *, whole: bool = False) -> None:
    """Raise an `AssertionError` that lists what the stations of a network break of the extent it declares."""
    problems = check_extent(df, network, extent, whole=whole)
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
