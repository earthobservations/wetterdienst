# Copyright (c) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD road weather data provider."""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from enum import Enum
from functools import reduce
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urljoin

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import (
    DATASET_NAME_DEFAULT,
    DatasetModel,
    ParameterModel,
    build_metadata_model,
)
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.metadata import _METADATA
from wetterdienst.util.eccodes import require_bufr
from wetterdienst.util.network import File, download_file, download_files, list_remote_files_fsspec

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

#: the stamp a road file carries, exactly as long as `%y%m%d%H%M` reads. Ten and not "ten or
#: more": a longer run anywhere else in the name would otherwise be captured instead of this
DATE_REGEX = r"-(\d{10})-"
TIME_COLUMNS = ("year", "month", "day", "hour", "minute")


DwdRoadMetadata = {
    **_METADATA,
    "kind": "observation",
    "timezone": "Europe/Berlin",
    "resolutions": [
        {
            "name": "15_minutes",
            "name_original": "15_minutes",
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "periods": ["historical"],
                    "parameters": [
                        {
                            "name": "humidity",
                            "name_original": "relativeHumidity",
                            "unit": "percent",
                        },
                        {
                            # not `precipitation_form`, which every other provider fills with a
                            # single code from a table of its own -- DWD observation with `wrtr`,
                            # whose 0 means no precipitation and 6 liquid. `precipitationType` is
                            # BUFR 0 20 021, a 30-bit *flag* table with a bit per type, so rain
                            # arrives as 33554432 where `wrtr` would say 6. Reported under the same
                            # name the two would be one quantity with two incomparable encodings
                            "name": "precipitation_type_flags",
                            "name_original": "precipitationType",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "totalPrecipitationOrTotalWaterEquivalent",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_intensity",
                            "name_original": "intensityOfPrecipitation",
                            "unit": "millimeter_per_hour",
                        },
                        {
                            "name": "road_surface_condition",
                            "name_original": "roadSurfaceCondition",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "airTemperature",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "dewpointTemperature",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_surface_mean",
                            "name_original": "roadSurfaceTemperature",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "horizontalVisibility",
                            # BUFR 0 20 001 horizontalVisibility is metres, and nothing in this
                            # parser converts; the docs page already said m
                            "unit": "meter",
                        },
                        {
                            "name": "water_film_thickness",
                            "name_original": "waterFilmThickness",
                            "unit": "centimeter",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "windDirection",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "maximumWindGustDirection",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "maximumWindGustSpeed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "windSpeed",
                            "unit": "meter_per_second",
                        },
                    ],
                },
            ],
        },
    ],
}
DwdRoadMetadata = build_metadata_model(DwdRoadMetadata, "DwdRoadMetadata")


class DwdRoadStationGroup(Enum):
    """Enumeration of DWD road weather station groups."""

    DD = "DD"
    DF = "DF"
    ER = "ER"
    FN = "FN"
    HJ = "HJ"
    HL = "HL"
    HS = "HS"
    HV = "HV"
    JA = "JA"
    JH = "JH"
    JS = "JS"
    KK = "KK"
    KM = "KM"
    KO = "KO"
    LF = "LF"
    LH = "LH"
    LW = "LW"
    MC = "MC"
    NC = "NC"
    ND = "ND"
    RB = "RB"
    RH = "RH"
    SF = "SF"
    SP = "SP"
    WW = "WW"
    XX = "XX"


# TODO: it seems that the following station groups are temporarily unavailable
TEMPORARILY_UNAVAILABLE_STATION_GROUPS = [
    DwdRoadStationGroup.DF,
    DwdRoadStationGroup.LF,
    DwdRoadStationGroup.SF,
    DwdRoadStationGroup.XX,
]


#: `pdbufr`'s flat read names every value by its rank in the message -- `#1#airTemperature`, and
#: for a station carrying two road sensors `#1#roadSurfaceTemperature` beside
#: `#2#roadSurfaceTemperature`. The rank is what names the sensor
_RANKED_KEY = re.compile(r"^#(\d+)#(.+)$")

#: the shape `__parse_dwd_road_weather_data` returns, named so that a file holding nothing can be
#: returned in it and still concatenate with the files that hold something
_PARSED_SCHEMA = {
    "station_id": pl.String,
    "date": pl.Datetime(time_zone="UTC"),
    "parameter": pl.String,
    "value": pl.Float64,
    "quality": pl.Float64,
}


#: the station's own verdict on its sensors, BUFR 0 33 005, last descriptor of every road subset.
#: A 30-bit flag table, and BUFR numbers a flag table's bits from the most significant end, so bit
#: n of a 30-bit field is worth `1 << (30 - n)`
QUALITY_FLAG = "qualityInformationAwsData"


def _flag_bit(bit: int) -> int:
    """Give the value bit `bit` of a 30-bit BUFR flag table takes when it is set."""
    return 1 << (30 - bit)


#: bit 1, "no automated meteorological data checks performed" -- the station saying it did not look
#: rather than that it looked and found nothing. 817 of the 1199 subsets measured say this, so it
#: is the ordinary answer and not an exception, and what it means for a reading is that its quality
#: is unknown. Null, then, and not zero
_QUALITY_UNCHECKED = _flag_bit(1)

#: the top bit of a 30-bit flag table, which is how a BUFR flag table says it has nothing to
#: report -- `0 20 021` spells it out as "ALL 30 MISSING VALUE" and this table's entries simply
#: stop at 23, leaving the bit either that marker or undefined. Read as a verdict it would say the
#: station checked and was satisfied, which is the one answer it certainly does not mean
_QUALITY_MISSING = _flag_bit(30)

#: which bit of the flag speaks for which descriptor. The table is the WMO's generic one for an
#: automatic weather station and DWD writes the road quantities into it: bit 7, "ground temperature
#: data suspect", is the one this was verified against -- the four stations carrying it in a
#: network-wide file are exactly the four whose road surface temperature is impossible (65.6 C,
#: 57.8 C, -0.7 C and 0.0 C against an air temperature near 12 C), and no station within 5 K of its
#: own air temperature carries it. The others follow the table's own wording and are not
#: contradicted by the data, though a single dry night cannot confirm them: nothing was reporting a
#: water film to flag, and only one station flagged its dry bulb.
#:
#: `roadSurfaceCondition` and `waterFilmThickness` are deliberately absent, both being road
#: descriptors of DWD's own (`0 20 241` and `0 13 241`) rather than quantities this table names. Its
#: nearest offers are bit 19, "state of ground", which is about bare earth, and bit 21, "water
#: content", which is the moisture in it. Bit 7 shows DWD does write road quantities into the
#: table, but it is mapped here because the data confirms it and not because the wording is close,
#: and neither of those two has anything to confirm it: bit 19 is set nowhere at all, and the 14
#: stations setting bit 21 reported the same film as everyone else on a dry night. A wrong `0`
#: there would be worse than a null, telling a caller filtering on quality that a suspect reading
#: was checked and found sound
_QUALITY_BITS = {
    "windDirection": 3,
    "windSpeed": 3,
    "maximumWindGustDirection": 3,
    "maximumWindGustSpeed": 3,
    "airTemperature": 4,
    # the table has no dew point. A road station carries one probe for temperature and humidity and
    # computes the dew point from it, so the humidity's verdict is the dew point's too
    "relativeHumidity": 6,
    "dewpointTemperature": 6,
    "roadSurfaceTemperature": 7,
    "horizontalVisibility": 14,
    "precipitationType": 18,
    "totalPrecipitationOrTotalWaterEquivalent": 18,
    "intensityOfPrecipitation": 18,
}


#: the quantities a motionless reading is a fault in, and the run of them that says so.
#:
#: Measured over a day of five station groups, around 700 stations for each quantity: a working
#: sensor's longest run of one identical value is 14 readings for the air temperature, 17 for the
#: dew point and 9 for the road surface. A broken one holds its value for 86 to 96 of the day's 96,
#: and every one of those reported a single distinct value for the whole day rather than a long
#: spell inside a varying series. 24 readings -- six hours at this resolution -- sits between the
#: two with room on either side.
#:
#: Only these three quantities, because only for these is standing still a fault. Everything else
#: the dataset reports is legitimately constant for hours at a time: the road surface condition and
#: the water film sit at 0 for the whole of a dry day, as does the precipitation type, the humidity
#: saturates in fog, the wind falls calm, and the visibility rests against the top of its range.
#: Measured on the same day, a 24-reading rule would have called 547 of 571 stations' surface
#: condition a fault, and 61 of 581 humidities -- which is a quiet day reported as a broken network
_STUCK_PARAMETERS = ("airTemperature", "dewpointTemperature", "roadSurfaceTemperature")
_STUCK_RUN = 24

#: and the time those readings have to cover: what they cover at the quarter hour this network
#: publishes on, which is 23 intervals of it rather than 24, the first reading standing at zero.
#:
#: The count alone was measured there, so a station reporting more often would trip it on less
#: evidence than the measurement was taken from -- a working sensor having held one value for 14
#: readings, three and a half hours. A floor and not a divisor: a station reporting less often
#: still trips on the count, 24 readings half an hour apart covering half a day
_STUCK_MIN_SPAN = dt.timedelta(minutes=15) * (_STUCK_RUN - 1)

#: how much larger than a station's own usual interval a gap has to be before it ends a run. A run
#: is what a sensor did without moving, and that cannot be read across a window where nothing was
#: published: twelve readings, three days of nothing and twelve more are not a six-hour run.
#:
#: Against the station's own cadence rather than against a fixed number of minutes. Of 67134
#: intervals measured over five groups for a day, 99.5% are the quarter hour this network
#: publishes on, but the tail reaches 405 minutes -- so a fixed gap tight enough to end an outage
#: also ends the ordinary missed file, and FN/P367 holds one air temperature for 88 readings with
#: seven of those among them. Four times the usual interval separates them: P367's gaps are twice
#: its cadence, where a 405-minute hole is twenty-seven times it. Taking the cadence from the
#: readings also keeps the count meaning what it says for a station reporting on any other
#: interval, where dividing by a fixed quarter hour made a slower one impossible to flag at all
_STUCK_GAP_FACTOR = 4

#: melting ice holds a road surface at its melting point for as long as the ice lasts, which is
#: hours, and is exactly the condition this network exists to report. That plateau is indexed on
#: the September day this threshold was measured over, when no road was anywhere near it.
#:
#: It cannot be told from a sensor stopped at zero by the reading alone -- FN/P717 sits at 0.00 C
#: all day and is certainly broken -- so it is told by the air instead: ice does not melt on a road
#: whose station reports 26 C, which is what P717's does. A reading at the melting point is left
#: alone where the air at that minute was near enough to freezing for melting to be possible, and
#: where the air is unknown it is left alone too, a missed fault being the safer error than a
#: winter's worth of genuine readings marked suspect.
#:
#: Ten degrees and not five. An ordinary thaw runs to +6 or +10 C with snow still lying, and the
#: road under it stays at 0.00 for hours -- five would have marked that suspect, which is the very
#: thing this exemption exists to prevent, and nothing in a September measurement constrains the
#: number. What it costs is a sensor stopped at zero at a station whose air stays under 10 C: that
#: one is left unmarked. Neither of the two in the measured day is, P717's air reaching 11.6 C and
#: both of them carrying DWD's own bit 7 besides
_MELTING_POINT = 273.15
_MELTING_PLATEAU = 0.05

#: how far below freezing a treated road's plateau can sit. German roads are salted, and brine
#: depresses the freezing point -- so a salted road in a thaw is pinned at a constant sub-zero
#: surface temperature for as long, and by the same physics, as an untreated one is pinned at
#: 0.00 C. Rock salt works to about -8 C in practice, so ten degrees covers it with room.
#:
#: Bounded rather than open: it is what keeps a sensor stopped at -30 C in a frost from being
#: excused, that being 30 degrees below a freezing point no brine reaches
_MELTING_BRINE_DEPRESSION = 10.0
_MELTING_AIR_MARGIN = 10.0


def _flag_stuck_sensors(df: pl.DataFrame, source: str) -> pl.DataFrame:
    """Mark a reading suspect where the sensor that took it has not moved for hours.

    DWD's own flag catches four of the twenty-one stations in a network-wide file that sit more
    than 10 K from their own air temperature; the rest report "no automated checks performed". This
    is the one fault that can be told from the data itself without knowing the season: a sensor
    reading identical to a hundredth of a degree for six hours is not measuring a road.

    It marks rather than removes. The value stays exactly as DWD published it and `quality` becomes
    1, which is what that column is for -- a caller filtering on it drops the reading, and one that
    is not sees what upstream sent. Nothing here is confident enough to delete a measurement.

    This is also the whole of what the flagged "sentinel" readings turn out to be: the exact
    `-75.00`, `-30.00` and `-25.00` degree values repeating across one group's stations are not a
    value to be recognised but sensors that have stopped, each reporting one distinct value for a
    whole day. Matching them by value would have been worse than useless -- -25 and -30 are both
    reachable in a German winter.
    """
    if df.is_empty():
        return df
    keys = ["station_id", "parameter"]
    # what the question is asked of: one row per station, parameter and minute, and only where
    # there is a reading. A minute arriving twice -- a group publishing under two families, a file
    # republished -- is one minute, and counting it twice put a zero in the middle of the intervals
    # and so a zero in their median, which ended every run at every reading and quietly answered
    # that nothing anywhere had stopped. A row saying null is not a reading at all: it is the same
    # dropout as a row that never arrived, and treated as a value it ended runs that an absent row
    # is allowed to span
    readings = (
        # narrowed first: only these three can be marked, and the dedupe, the join and four window
        # passes over the other eleven parameters are work whose result is thrown away. On a month
        # of one group -- the size the group cache is bounded to hold -- that is 4.96 GB of peak
        # memory against 2.06, and 4.2 seconds against 0.83. `airTemperature` is one of the three,
        # so the air the melting exemption reads survives the narrowing
        df.filter(pl.col("parameter").is_in(_STUCK_PARAMETERS) & pl.col("value").is_not_null())
        .unique(subset=[*keys, "date"], keep="first")
        .sort(*keys, "date")
    )
    # the station's air beside each reading, because the question is whether ice could be melting
    # at that minute. Asked of a whole run, or worse of the whole request, one cold hour at the end
    # of a fortnight excuses every plateau in it -- and the same day then answers differently
    # depending on how much of the year the caller asked for
    air = readings.filter(pl.col("parameter").eq("airTemperature")).select(
        "station_id",
        "date",
        pl.col("value").alias("_air"),
    )
    marked = (
        readings.join(air, on=["station_id", "date"], how="left")
        # sorted after the join and not only before it: the run below reads each row against the
        # one before it, and `join` promises nothing about the order it returns. Left unsorted, a
        # reordering would put a negative interval among the gaps and so drag their median under
        # every ordinary one, ending a run at every reading and answering that nothing had stopped
        .sort(*keys, "date")
        .with_columns(
            # a run breaks where the value changes and where the readings stop for longer than
            # this station usually leaves between them: a gap is not evidence that the sensor held
            # still across it, and the hole ends the run and nothing more -- a sensor stopped on
            # both sides of one is still stopped on both sides of it
            _gap=pl.col("date").diff().over(keys),
        )
        .with_columns(
            _run=(
                pl.col("value").ne(pl.col("value").shift().over(keys)).fill_null(value=True)
                | pl.col("_gap").gt(pl.col("_gap").median().over(keys).mul(_STUCK_GAP_FACTOR)).fill_null(value=False)
            )
            .cum_sum()
            .over(keys),
        )
        .with_columns(
            _stuck=pl.len().over(*keys, "_run").ge(_STUCK_RUN)
            & (pl.col("date").max().over(*keys, "_run") - pl.col("date").min().over(*keys, "_run")).ge(
                _STUCK_MIN_SPAN,
            ),
        )
        .with_columns(
            _stuck=pl.col("_stuck")
            & pl.col("parameter").is_in(_STUCK_PARAMETERS)
            # melting ice holds a road at its melting point for hours, which is a reading and not
            # a fault. Told from a sensor stopped at zero by the air the station reports, ice not
            # melting on a road whose own air is at 26 C
            & ~(
                pl.col("parameter").eq("roadSurfaceTemperature")
                & pl.col("value").le(_MELTING_POINT + _MELTING_PLATEAU)
                & pl.col("value").ge(_MELTING_POINT - _MELTING_BRINE_DEPRESSION)
                # within ten degrees of freezing on either side: brine cannot pin a road at -4 C
                # while the air stands at -20, any more than ice can hold one at 0.00 while the air
                # is at 26
                & pl.col("_air")
                .is_between(_MELTING_POINT - _MELTING_AIR_MARGIN, _MELTING_POINT + _MELTING_AIR_MARGIN)
                .fill_null(value=True)
            ),
        )
        .filter(pl.col("_stuck"))
        # the value too, so the verdict stays with the reading it was reached from. A station-minute
        # arriving twice is judged from the first copy, and joining on the minute alone marked the
        # second as well -- including one holding a value that had moved and belonged to no run
        .select("station_id", "parameter", "date", "value", "_stuck")
    )
    if marked.is_empty():
        return df
    # asked only when it will be said, like the line about dropped sensors: this filters, uniques
    # and sorts a frame that may hold a month of a group, to write one line nobody is listening for
    #
    # and at debug for that line's reason too -- the road values are collected a station at a time
    # and each of them parses the whole group again, so at info this group-wide line is printed
    # once per station asked for
    if log.isEnabledFor(logging.DEBUG):
        _log_stuck_sensors(marked, source)
    # the index is taken before the join and restored after it, `join` promising nothing about the
    # order it returns. `marked` holds each station-minute once, so a frame that holds one twice is
    # answered for both rows and gains none
    return (
        df.with_row_index("_row")
        .join(marked, on=["station_id", "parameter", "date", "value"], how="left")
        .sort("_row")
        # and only where there is a reading to judge, as the parse itself does: a station-minute
        # arriving twice, once with the reading and once with a null for this descriptor, would
        # otherwise have the null marked suspect too
        .with_columns(
            quality=pl.when(pl.col("_stuck") & pl.col("value").is_not_null())
            .then(pl.lit(1.0))
            .otherwise(pl.col("quality")),
        )
        .select(df.columns)
    )


def _log_stuck_sensors(marked: pl.DataFrame, source: str) -> None:
    """Name the sensors marked as stopped, for the run where someone wants to know which."""
    stations = marked.select("station_id", "parameter").unique().sort("station_id", "parameter")
    log.debug(
        f"{source}: {stations.height} sensors reported one value for "
        f"{_STUCK_RUN} readings or more and are marked suspect "
        f"({', '.join(f'{s}/{p}' for s, p in stations.head(5).iter_rows())}"
        f"{', ...' if stations.height > 5 else ''}); the readings are kept as published (GH-1917)",
    )


def _quality(flag: pl.Expr, bit: pl.Expr) -> pl.Expr:
    """Read one reading's quality off the station's flag: 1 suspect, 0 checked and not, null unknown.

    Three answers rather than two, because the flag distinguishes a station that checked and found
    nothing wrong from one that did not check. Collapsing those onto zero would report the second
    as a clean bill of health, which is the opposite of what it says.
    """
    unknown = flag.is_null() | bit.is_null() | (flag & _QUALITY_UNCHECKED).gt(0) | (flag & _QUALITY_MISSING).gt(0)
    return (
        pl.when(unknown)
        .then(pl.lit(None, dtype=pl.Float64))
        .when((flag & bit).gt(0))
        .then(pl.lit(1.0))
        .otherwise(pl.lit(0.0))
    )


def _columns_by_rank(columns: Iterable[str], wanted: Collection[str]) -> dict[str, dict[int, str]]:
    """Group a flat read's columns by the descriptor they carry, keyed by rank.

    `#1#roadSurfaceTemperature` and `#2#roadSurfaceTemperature` become one entry holding both, so
    that what replicates can be told from what does not by asking how many ranks it has.
    """
    by_name: dict[str, dict[int, str]] = {}
    for column in columns:
        match = _RANKED_KEY.match(column)
        if not match:
            continue
        rank, name = int(match.group(1)), match.group(2)
        if name in wanted:
            by_name.setdefault(name, {})[rank] = column
    return by_name


def _identity(columns: dict[int, str]) -> pl.Expr:
    """Read a key that identifies a reading -- its station, or one part of its minute.

    Rank 1 is not promised. A key absent from a file's first subset and present in a later one is
    numbered from where it appears, and a file whose messages do not agree on their structure --
    which is every road file, and what the read's own warning is about -- can carry one subset's
    station at `#1#` and the next one's at `#2#`. Taken from the lowest rank alone, every subset
    numbered otherwise loses its station and is dropped for having none.

    Coalesced instead, because these occur once per subset: whichever rank a row carries it at is
    the one it has, and there is no second value for the coalesce to choose wrongly between.
    """
    return pl.coalesce([pl.col(column) for _rank, column in sorted(columns.items())])


def _contested(columns: dict[int, str]) -> pl.Expr:
    """Whether more than one road sensor reported this descriptor for the row.

    Contested is the only case that needs deciding, and two sensors reporting the same number are
    not deciding anything: of the 36 readings one populated group's file reports twice, 25 are
    identical to the one kept. Counted as contests they would inflate what the log says was
    dropped, and credit a sensor in the choice below for settling a question nobody asked.

    Two sensors reporting different quantities are not a contest either -- the whole of the DD
    group, where one carries the surface temperature and the other the surface condition -- and
    taking both composes a row the way every row in this library is composed, out of the several
    instruments a station is fitted with.
    """
    # cast, as the readings themselves are: a descriptor no subset of the file carries comes back
    # from pandas as a column of nulls typed as strings, and coalescing that beside a float column
    # makes both strings, which will not compare
    order = [pl.col(column).cast(pl.Float64) for _rank, column in sorted(columns.items())]
    reported = pl.sum_horizontal([column.is_not_null().cast(pl.Int32) for column in order])
    # more than one reading, and not all of them the same
    first = pl.coalesce(order)
    differs = pl.any_horizontal([column.ne(first) for column in order])
    return reported.gt(1) & differs.fill_null(value=False)


def _sensor_choice(replicated: dict[str, dict[int, str]], ranks: list[int]) -> pl.Expr:
    """Name the sensor a row is answered from: most contests settled, then most reported.

    Two questions in one order. First, which sensor settles the most of what this row has twice --
    a sensor carrying nothing contested cannot answer a contest, and counting everything it does
    carry would let it win one. Then, among sensors that settle as many, which reported the most
    altogether: where two both answer one contest and only one of them also took a temperature, the
    fuller sensor gives a row that is wholly its own, where the other leaves a reading to be
    fetched from elsewhere.

    The two are weighed as one score rather than in sequence, a contest being worth more than the
    four quantities a sensor can report, so that no amount of the second outweighs the first.

    The first sensor on a tie, which is the ordinary case -- two sensors fitted alike report the
    same three quantities, so neither count separates them and the order DWD encodes them in is the
    only thing left. Arbitrary between the two, but fixed: the same file parses the same way twice,
    and the reading that is dropped is named in the log rather than lost quietly. Fixed within a
    row, that is, and not across them: a station with three sensors can be answered from one at
    noon and another at a quarter past, which a caller reading a series should know.
    """
    contested = {name: _contested(columns) for name, columns in replicated.items()}
    # more than any count of reported quantities can reach, so a contest settled always outweighs
    # a quantity merely reported
    if not replicated or not ranks:
        # nothing in this file is reported twice, so there is no sensor to name
        return pl.lit(None, dtype=pl.Int32)
    contest_weight = len(replicated) + 1
    scores = []
    for rank in ranks:
        mine = [(name, columns[rank]) for name, columns in replicated.items() if rank in columns]
        settles = pl.sum_horizontal(
            [pl.when(contested[name] & pl.col(column).is_not_null()).then(1).otherwise(0) for name, column in mine]
            or [pl.lit(0, dtype=pl.Int32)],
        )
        reported = pl.sum_horizontal(
            [pl.col(column).is_not_null().cast(pl.Int32) for _name, column in mine] or [pl.lit(0, dtype=pl.Int32)],
        )
        scores.append(settles * contest_weight + reported)
    # the best score, then the first rank holding it. Written as one horizontal maximum and a
    # coalesce rather than as a running maximum: carrying the winner so far from rank to rank
    # names it twice per step, once to compare against and once to keep, so the expression doubles
    # with every sensor -- 0.02s to build and run for two of them, 0.14 for four, 13.5 for eight,
    # where a station fitted with eight makes every file of its group pay that. Stations with four
    # are already published
    best = pl.max_horizontal(scores)
    return pl.coalesce(
        [
            pl.when(score.eq(best) & best.gt(0)).then(pl.lit(rank, dtype=pl.Int32))
            for rank, score in zip(ranks, scores, strict=True)
        ],
    )


def _reading(name: str, columns: dict[int, str], chosen: pl.Expr) -> pl.Expr:
    """One descriptor's value for a row.

    From the chosen sensor wherever that sensor reported it, so that what the row has twice is
    settled once and it does not pair one sensor's surface temperature against another's surface
    condition. Where the chosen sensor reported nothing, the first sensor that did stands instead:
    that is the whole of a row with nothing contested, and it is also the only answer left where
    three sensors contest different quantities and the one settling this row's contests never took
    this reading. So the row is one sensor's wherever the question arose, and not a promise that
    every number in it came from the same instrument.
    """
    if not columns:
        return pl.lit(None, dtype=pl.Float64).alias(name)
    if len(columns) == 1:
        return pl.col(next(iter(columns.values()))).cast(pl.Float64).alias(name)
    order = sorted(columns.items())
    from_chosen = pl.coalesce(
        [pl.when(chosen.eq(rank)).then(pl.col(column).cast(pl.Float64)) for rank, column in order]
    )
    as_reported = pl.coalesce([pl.col(column).cast(pl.Float64) for _, column in order])
    # the chosen sensor's reading, falling back to the first that reported one. The fallback is
    # what answers a row with nothing contested, `chosen` being null there and the first reading
    # the only one. It also answers the case that row cannot: with three sensors, the one carrying
    # this row's contests need not carry this descriptor at all, and then there is nothing of the
    # chosen sensor's to pair against -- which is not a reason to lose the reading, only a reason
    # it cannot come from the chosen sensor
    return pl.coalesce([from_chosen, as_reported]).alias(name)


def _flag(columns: dict[int, str]) -> pl.Expr:
    """Take the station's quality flag for the row, as an integer to read bits out of.

    A file whose stations carry no flag at all has no column for it, which is the same to a caller
    as a station that carried one and left it empty: nothing is known about the reading either way.
    """
    if not columns:
        return pl.lit(None, dtype=pl.Int64).alias("_flag")
    return _identity(columns).cast(pl.Int64).alias("_flag")


def _one_row_per_reading(rows: pl.DataFrame, source: str) -> pl.DataFrame:
    """Keep a station and minute to one row, folding a repeat onto the readings it is missing.

    A road file holds one subset per station -- 1199 subsets of fifteen groups, and not one station
    twice -- so this ordinarily does nothing but ask. What it guards is the file that does: the
    batched read folded a station-minute with `first`, which prefers a reading to a null, where one
    row per subset leaves two rows for the caller and the deduplication every provider passes
    through afterwards keeps whichever came first, null or not. A repeat would then cost the
    reading rather than the duplicate, quietly, on the way out.

    Asked with a count rather than answered with a fold, the fold being the per-file cost this
    parse was rewritten to drop and a repeat being something no published file has yet done.
    """
    keys = ["station_id", "date"]
    if rows.height == rows.select(keys).n_unique():
        return rows
    log.warning(
        f"{source} reports {rows.height - rows.select(keys).n_unique()} station-minutes more than "
        f"once, which no road file has been seen to do; folding each onto the first reading of it",
    )
    return rows.group_by(keys, maintain_order=True).agg(pl.exclude(keys).drop_nulls().first())


def _kept_rank(columns: dict[int, str], chosen: pl.Expr) -> pl.Expr:
    """Which sensor a descriptor's reading comes from, mirroring `_reading`'s own answer."""
    order = sorted(columns.items())
    from_chosen = pl.coalesce(
        [
            pl.when(chosen.eq(rank) & pl.col(column).is_not_null()).then(pl.lit(rank, dtype=pl.Int32))
            for rank, column in order
        ],
    )
    as_reported = pl.coalesce(
        [pl.when(pl.col(column).is_not_null()).then(pl.lit(rank, dtype=pl.Int32)) for rank, column in order],
    )
    return pl.coalesce([from_chosen, as_reported])


def _log_dropped_sensors(
    df: pl.DataFrame,
    ranked: dict[str, dict[int, str]],
    replicated: dict[str, dict[int, str]],
    ranks: list[int],
    chosen: pl.Expr,
    source: str,
) -> None:
    """Say which stations reported one quantity from two road sensors, and how much went.

    At debug, because it is per file and routine -- a tenth of the stations of a populated group
    carry a second sensor, so a month of road data is thousands of these and the CLI logs at info.
    What the choice is and why is in `__parse_dwd_road_weather_data` and in GH-1908, which is where
    someone would look; this is for the run where they want to know which stations, and when.
    """
    contested = {name: _contested(columns) for name, columns in replicated.items()}
    # against the rank the reading actually comes from, which is not always the chosen sensor:
    # where that sensor did not report a descriptor, `_reading` falls back to the first that did,
    # and counting every rank but the chosen one called that fallback lost while it was being kept
    kept = {name: _kept_rank(columns, chosen) for name, columns in replicated.items()}
    lost = pl.sum_horizontal(
        [
            pl.when(contested[name] & pl.col(columns[rank]).is_not_null() & kept[name].ne(rank)).then(1).otherwise(0)
            for name, columns in replicated.items()
            for rank in ranks
            if rank in columns
        ],
    )
    dropped = df.select(
        _identity(ranked["shortStationName"]).cast(pl.String).alias("station"),
        lost.alias("lost"),
    ).filter(pl.col("lost").gt(0) & pl.col("station").is_not_null())
    if dropped.is_empty():
        return
    # distinct stations: a file carries one minute today, so a row is a station -- but the fold
    # above exists because one need not, and then this counted station-minutes and could name the
    # same station twice in the sample
    stations = sorted(dropped.get_column("station").unique().to_list())
    log.debug(
        f"{source}: {len(stations)} stations reported the same quantity from more than one road "
        f"sensor ({', '.join(stations[:5])}{', ...' if len(stations) > 5 else ''}); answered from "
        f"the one carrying most of {', '.join(sorted(replicated))}, dropping "
        f"{dropped.get_column('lost').sum()} readings from the others (GH-1908)",
    )


class DwdRoadValues(TimeseriesValues):
    """Values class for DWD road weather data."""

    def __post_init__(self) -> None:
        """Post-initialization of the DwdRoadValues class."""
        super().__post_init__()
        # asked here so the answer comes back with the request rather than out of the middle of a
        # parse. It used to call `ensure_pdbufr()` and throw the answer away, which guarded nothing
        require_bufr("DWD road weather data")
        # the group parsed for the station asked about before this one, and the key it answers for.
        # See `_collect_data_by_station_group`
        self._group_cache: tuple[tuple[str, tuple[str, ...]], pl.DataFrame] | None = None

    def _collect_station_parameter_or_dataset(  # ty: ignore[invalid-method-override]
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect data from DWD Road Weather stations."""
        station_group = self.sr.df.filter(pl.col("station_id").eq(station_id)).get_column("station_group").item()
        station_group = DwdRoadStationGroup(station_group)
        parameters = list(parameter_or_dataset)
        df = self._collect_data_by_station_group(station_group, parameters)
        # nothing to answer with is a shape rather than a special case: the group published no file
        # for the window, or every file it published held nothing, and either way what comes back
        # is a frame of no readings rather than a frame of no columns. So the filter has a station
        # id to look for and the select has columns to name, and one row of this function answers
        # for the empty case and the populated one alike -- there being one less place to hand a
        # frame on before asking whether it holds anything, which is how this went wrong four
        # times over
        df = df.filter(pl.col("station_id").eq(station_id))
        return df.select(
            pl.lit(parameter_or_dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.name, dtype=pl.String).alias("dataset"),
            "parameter",
            "station_id",
            "date",
            "value",
            "quality",
        )

    def _create_file_index_for_dwd_road_weather_station(
        self,
        road_weather_station_group: DwdRoadStationGroup,
    ) -> pl.DataFrame:
        """Create a file index for DWD Road Weather stations."""
        files = list_remote_files_fsspec(
            reduce(
                urljoin,
                [
                    "https://opendata.dwd.de/weather/weather_reports/road_weather_stations/",
                    road_weather_station_group.value,
                ],
            ),
            settings=self.sr.settings,
        )
        df = (
            pl.DataFrame({"filename": files}, schema={"filename": pl.String})
            .with_columns(
                pl.col("filename").str.split("/").list.last().alias("name"),
            )
            .with_columns(
                pl.col("name")
                .str.extract(DATE_REGEX, 1)
                # not strict: ten digits are not necessarily a date, and `26091319ZZ` or `2699999999`
                # would raise here and take the request with it. A match that will not parse becomes a
                # null and is dropped below beside the entries that never matched -- one rule for what
                # counts as a file, rather than a crash for one kind of not-a-file and a drop for the
                # other
                .str.to_datetime("%y%m%d%H%M", time_zone="UTC", strict=False)
                .alias("date"),
            )
        )
        # what is dropped below and expected to be: the listing of a group that exists and holds
        # nothing is the group itself, which comes back named for the group or not named at all
        # depending on whether the URL it was asked for ended in a slash, and each family a group
        # publishes under keeps a `LATEST` alias duplicating its newest file -- FN publishes two,
        # under `DWFN` and `DWNB`. Left in, either is downloaded and handed to the reader as
        # though it were a file
        expected = pl.col("name").is_in(["", road_weather_station_group.value]) | pl.col("name").str.contains("LATEST")
        unreadable = df.filter(pl.col("date").is_null() & ~expected).get_column("name").to_list()
        if unreadable:
            # a name the index cannot read, which is asked of every listing rather than only of one
            # that came back empty: a group publishing under two families loses half its readings
            # when one of them is renamed, and the drop is as quiet as the alias's -- so the
            # request would simply return less, with nothing said anywhere
            log.warning(
                f"{len(unreadable)} of {df.height} entries listed for "
                f"{road_weather_station_group.value} carry no timestamp the file index reads "
                f"({', '.join(sorted(unreadable)[:3])}); the file names may have changed",
            )
        df = df.drop_nulls("date")
        if df.is_empty():
            log.info(f"No files found for {road_weather_station_group.value}.")
            if road_weather_station_group in TEMPORARILY_UNAVAILABLE_STATION_GROUPS:
                log.info(f"Station group {road_weather_station_group.value} may be temporarily unavailable.")
        return df

    def _collect_data_by_station_group(
        self,
        road_weather_station_group: DwdRoadStationGroup,
        parameters: list[ParameterModel],
    ) -> pl.DataFrame:
        """Collect data from DWD Road Weather stations, once per group rather than per station.

        A road file holds a whole station group, where the collection above it asks for one station
        at a time -- so every file of a group was read, decoded and built into a frame once per
        station of that group, and all but one station's rows thrown away each time. Three stations
        of one group over two hours parsed nine files twenty-seven times. The files themselves come
        from the cache; what was repeated is the BUFR decode, which is the expensive half.

        One group is kept, not all of them. Stations arrive in group order -- 1653 of them across 19
        groups change group 21 times -- so holding the last is worth almost exactly what holding
        every one would be, 22 parses against 19, and it bounds what this keeps to a single group's
        readings rather than to every group a request touches. A month of one group is some
        thirteen million rows, so that difference is the whole of whether a wide request fits in
        memory.

        Keyed by the parameters as well as the group: a caller asking for two datasets would
        otherwise be answered for the second from a frame parsed for the first.
        """
        key = (road_weather_station_group.value, tuple(parameter.name_original for parameter in parameters))
        if self._group_cache is not None and self._group_cache[0] == key:
            return self._group_cache[1]
        df = self.__collect_data_by_station_group(road_weather_station_group, parameters)
        self._group_cache = (key, df)
        return df

    def __collect_data_by_station_group(
        self,
        road_weather_station_group: DwdRoadStationGroup,
        parameters: list[ParameterModel],
    ) -> pl.DataFrame:
        """Read every file the group published for the window."""
        df_files = self._create_file_index_for_dwd_road_weather_station(road_weather_station_group)
        if self.sr.start_date:
            df_files = df_files.filter(
                pl.col("date").is_between(self.sr.start_date, self.sr.end_date),
            )
        remote_files = df_files.get_column("filename").to_list()
        files = download_files(
            urls=remote_files,
            cache_dir=self.sr.settings.cache_dir,
            ttl=CacheExpiry.TWELVE_HOURS,
            client_kwargs=self.sr.settings.fsspec_client_kwargs,
            cache_disable=self.sr.settings.cache_disable,
        )
        # files may be empty, see https://github.com/earthobservations/wetterdienst/issues/1526
        # -> those files had only 142 bytes
        # -> skip empty files with equal or less size
        files = [file for file in files if file.nbytes > 142]
        return self._parse_dwd_road_weather_data(files, parameters)

    def _parse_dwd_road_weather_data(
        self,
        files: list[File],
        parameters: list[ParameterModel],
    ) -> pl.DataFrame:
        """Parse the road weather station data from a given file and returns a DataFrame."""
        data = [self.__parse_dwd_road_weather_data(file, parameters) for file in files]
        if not data:
            return pl.DataFrame(schema=_PARSED_SCHEMA)
        # here rather than in the per-file parse: a sensor that has stopped can only be told from
        # one that is merely steady by watching it over hours, and one file is one minute
        return _flag_stuck_sensors(pl.concat(data), files[0].url.rsplit("/", 1)[0] or "road")

    @staticmethod
    def __parse_dwd_road_weather_data(
        file: File,
        parameters: list[ParameterModel],
    ) -> pl.DataFrame:
        """Read one road file as one row per station, minute and parameter.

        A road file holds one subset per station -- 1199 subsets across fifteen groups, and no
        station appeared in two of them -- and the road sensors sit inside that subset as a delayed
        replication: `1 09 000` and `0 31 001` wrapping `positionOfRoadSensors`,
        `roadSurfaceTemperature`, the sub-surface temperatures at their depths, `waterFilmThickness`
        and `roadSurfaceCondition`. A station with two sensors carries that group twice, and one
        with four carries it four times.

        Read flat, the replication comes back as the rank on the key -- `#1#roadSurfaceTemperature`
        beside `#2#roadSurfaceTemperature` -- and the rank is what names the sensor. Nothing else
        does: `positionOfRoadSensors` reads 0 or missing in all 1199 subsets, and `road_sector` is
        in the station index, one row per station, so it says where the station is rather than
        which of its sensors spoke.

        So only what is inside that replication can arrive twice. Of the fourteen descriptors this
        dataset maps, three do -- the surface temperature, the surface condition and the water film
        -- and the other eleven, air temperature and dew point and humidity and visibility and the
        wind and the precipitation among them, are outside it and come once per station. A row can
        therefore never hold one sensor's air temperature beside another's road surface temperature,
        there being only ever one air temperature to hold.

        Two sensors are two things, and which of the two a station is doing can be read off what
        they reported. Where they carry the same quantity they are measuring one road twice, from
        different points of it. They mostly agree closely -- of 75 stations whose sensors both
        reported a surface temperature, the median disagreement was 0.3 K and 97 in 100 were inside
        3 K -- so which one answers rarely changes the reading. Two of the 75 were nothing like
        that, at 22 K and 18 K, and both were a broken sensor rather than a property of the road:
        one stuck at 273.14 K for a whole day of readings, the other running some 22 K hot while
        keeping a normal daily swing. The network carries such readings at about one station in
        forty, on stations with one sensor as much as two, and none of that is decided here: a
        sensor has to be chosen, everything contested is then taken from that one so the row is a
        road rather than an average of two, and where the two disagree wildly the choice is the
        rank order and nothing better. This library does not judge whether a reading is plausible,
        here or anywhere else.

        Where they carry different quantities they are two instruments of one installation -- the
        whole of the DD group, where the first sensor holds the surface temperature and the second
        the surface condition, for 24 of its 25 stations. Nothing is contested there, so both are
        kept: composing that row is what this library does with every station, whose air temperature
        and wind and humidity are three instruments already.

        What is dropped is only ever a reading that a station reported twice and differently, which
        is 11 of a populated group's file -- the same file reports 36 twice, and 25 of those are
        the same number arriving again, which decides nothing and loses nothing. Each is named in
        the log. Keeping the ones that differ would want an axis this frame has not got, GH-1908.
        """
        import pdbufr  # noqa: PLC0415

        parameter_names = [parameter.name_original for parameter in parameters]
        with NamedTemporaryFile("w+b") as tf:
            if isinstance(file.content, Exception):
                raise file.content
            tf.write(file.content.read())
            tf.seek(0)
            # pdbufr warns here that the file's subsets do not all carry the same keys, which for
            # this network is every file -- road stations are fitted differently, so one carries a
            # second sensor where the next does not. It warns about the column order it returns
            # them in, and nothing below reads a column by position. It is left to reach the caller
            # rather than filtered: Python shows it once per process whatever the request asks for,
            # and suppressing it means editing the process's global warning filters, which are not
            # this library's to edit -- it would go on suppressing the same warning for anything
            # else reading BUFR alongside it
            #
            # "data", so the read returns the message's values and not its header too: the
            # twenty-one header keys of a road file are read, converted and dropped again, being
            # none of the fourteen this parse is after
            #
            # and every data key rather than the fourteen: flat, a read that names its columns
            # returns the first rank of each and drops the rest, which is the sensor thrown away
            # before anything can choose between them
            # "data", so the read returns the message's values and not its header too: the
            # twenty-one header keys of a road file are read, converted and dropped again, being
            # none of the fourteen this parse is after
            #
            # and every data key rather than the fourteen: flat, a read that names its columns
            # returns the first rank of each and drops the rest, which is the sensor thrown away
            # before anything can choose between them
            df = pdbufr.read_bufr(tf.name, "data", flat=True)
        ranked = _columns_by_rank(df.columns, {*TIME_COLUMNS, "shortStationName", QUALITY_FLAG, *parameter_names})
        # a file whose messages decode to no subsets comes back with no columns at all, and one
        # that decodes to subsets carrying no station is as unreadable. Either is nothing to
        # answer with rather than something to fail on -- the group published, and what it
        # published held no readings
        if df.empty or not {"shortStationName", *TIME_COLUMNS} <= ranked.keys():
            log.info(f"{file.url} holds no readings")
            return pl.DataFrame(schema=_PARSED_SCHEMA)
        df = pl.from_pandas(df)
        replicated = {name: columns for name, columns in ranked.items() if name in parameter_names and len(columns) > 1}
        ranks = sorted({rank for columns in replicated.values() for rank in columns})
        chosen = _sensor_choice(replicated, ranks)
        if replicated:
            # worked out once and held as a column, rather than handed on as an expression for
            # every reading and every log term to carry a copy of. The choice names each rank's
            # score, so re-embedding it once per rank per descriptor cubes it: eight sensors cost
            # 1.2s a file that way against 0.05 held as a column, and the cost falls on every file
            # of the group, not only on the station fitted with them
            df = df.with_columns(_chosen=chosen)
            chosen = pl.col("_chosen")
        if replicated and log.isEnabledFor(logging.DEBUG):
            _log_dropped_sensors(df, ranked, replicated, ranks, chosen, file.url)
        rows = (
            df.select(
                _identity(ranked["shortStationName"]).cast(pl.String).alias("station_id"),
                pl.concat_str(
                    exprs=[
                        # through `Int64` rather than straight to `String`: a subset that carries
                        # no minute makes the whole of pandas' column a float, and 2026 written as
                        # a float is "2026.0", which takes the timestamp of every station in the
                        # file with it. Not strict, so a key that is somehow not a whole number is
                        # a null date and one dropped reading rather than a failed request
                        _identity(ranked[name])
                        .cast(pl.Int64, strict=False)
                        .cast(pl.String)
                        .str.pad_start(4 if name == "year" else 2, "0")
                        for name in TIME_COLUMNS
                    ],
                )
                .str.to_datetime("%Y%m%d%H%M", time_zone="UTC")
                .alias("date"),
                # the station's verdict on its own sensors, carried through the unpivot so that
                # each reading can be told apart from the others it was reported beside. Outside
                # the sensor replication, so one per station and minute however many sensors it has
                _flag(ranked.get(QUALITY_FLAG, {})),
                # a descriptor no subset in the file carries is not a column of the read at all,
                # and is null here for the same reason a station that did not report it is: absent
                # and unreported are the same thing to a caller
                *(_reading(name, ranked.get(name, {}), chosen) for name in parameter_names),
            )
            # what the read no longer filters: required of nothing but its own structure, a subset
            # that names no station or no minute arrives like any other, and there is nowhere to
            # put a reading that does not say where or when it was taken
            .filter(pl.col("station_id").is_not_null() & pl.col("date").is_not_null())
        )
        return (
            _one_row_per_reading(rows, file.url)
            .unpivot(
                index=["station_id", "date", "_flag"],
                variable_name="parameter",
                value_name="value",
            )
            .with_columns(
                # only where there is a reading to judge: a station that checked its sensors and
                # found nothing wrong says nothing about the twelve quantities it does not report,
                # and answering 0 for those reads as "checked, not suspect"
                pl.when(pl.col("value").is_not_null())
                .then(
                    _quality(
                        pl.col("_flag"),
                        # the bit that speaks for this reading, which for a descriptor the flag table
                        # has no entry for is none at all
                        pl.col("parameter").replace_strict(
                            {name: _flag_bit(bit) for name, bit in _QUALITY_BITS.items()},
                            default=None,
                            return_dtype=pl.Int64,
                        ),
                    ),
                )
                .alias("quality"),
            )
            .drop("_flag")
        )


@dataclass
class DwdRoadRequest(TimeseriesRequest):
    """Request class for DWD road weather data."""

    metadata = DwdRoadMetadata
    _values = DwdRoadValues

    _base_columns: ClassVar = (
        "resolution",
        "dataset",
        "station_id",
        "start_date",
        "end_date",
        "latitude",
        "longitude",
        "height",
        "name",
        "state",
        "station_group",
        "road_name",
        "road_sector",
        "road_type",
        "road_surface_type",
        "road_surroundings_type",
    )
    _endpoint = (
        "https://www.dwd.de/DE/leistungen/opendata/help/stationen/sws_stations_xls.xlsx?__blob=publicationFile&v=11"
    )
    _column_mapping: ClassVar = {
        "Kennung": "station_id",
        "GMA-Name": "name",
        "Bundesland  ": "state",
        "Straße / Fahrtrichtung": "road_name",
        "Strecken-kilometer 100 m": "road_sector",
        """Streckentyp (Register "Typen")""": "road_type",
        """Streckenlage (Register "Typen")""": "road_surroundings_type",
        """Streckenbelag (Register "Typen")""": "road_surface_type",
        "Breite (Dezimalangabe)": "latitude",
        "Länge (Dezimalangabe)": "longitude",
        "Höhe in m über NN": "height",
        "GDS-Verzeichnis": "station_group",
        "außer Betrieb (gemeldet)": "has_file",
    }
    _dtypes: ClassVar = {
        "station_id": pl.String,
        "name": pl.String,
        "state": pl.String,
        "road_name": pl.String,
        "road_sector": pl.Utf8,
        "road_type": pl.Int64,
        "road_surroundings_type": pl.Int64,
        "road_surface_type": pl.Int64,
        "latitude": pl.Float64,
        "longitude": pl.Float64,
        "height": pl.Float64,
        "station_group": pl.Utf8,
        "has_file": pl.Utf8,
    }

    def _all(self) -> pl.LazyFrame:
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        file = download_file(
            url=self._endpoint,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        df = pl.read_excel(source=file.content, sheet_name="Tabelle1", infer_schema_length=0)
        df = df.rename(mapping=self._column_mapping)
        df = df.select(pl.col(col) for col in self._column_mapping.values())
        df = df.filter(
            pl.col("has_file").ne("x") & pl.col("station_group").ne("0") & pl.col("station_id").is_not_null(),
        )
        df = df.with_columns(
            pl.lit(self.metadata[0].name, dtype=pl.String).alias("resolution"),
            pl.lit(self.metadata[0].datasets[0].name, dtype=pl.String).alias("dataset"),
            pl.col("longitude").str.replace(",", "."),
            pl.col("latitude").str.replace(",", "."),
            pl.when(~pl.col("road_type").str.contains("x")).then(pl.col("road_type")),
            pl.when(~pl.col("road_surroundings_type").str.contains("x")).then(
                pl.col("road_surroundings_type"),
            ),
            pl.when(~pl.col("road_surface_type").str.contains("x")).then(
                pl.col("road_surface_type"),
            ),
        )
        df = df.with_columns(pl.col(col).cast(dtype) for col, dtype in self._dtypes.items())
        return df.lazy()
