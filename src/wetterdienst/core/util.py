# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tools for timeseries."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple

import polars as pl

from wetterdienst.exceptions import NoStationsWithHeightError
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.metadata.resolution import Frequency
from wetterdienst.model.metadata import ParameterModel

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Iterable

    from wetterdienst.metadata.resolution import Resolution
    from wetterdienst.model.unit import UnitConverter
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)


@dataclass
class _ParameterData:
    values: pl.DataFrame
    station_ids: list[str] | None = None
    additional_station_counter: int = 0
    finished: bool = False


def build_date_grid(resolution: Resolution, start_date: dt.datetime, end_date: dt.datetime) -> pl.DataFrame:
    """Lay out the timestamps an interpolation or a summary answers for, as a single `date` column.

    Every station's readings are joined onto this grid, so it is what decides which timestamps the
    result has an answer for, and the join is exact -- a reading taken off the grid contributes to
    neither.

    The range is generated from the window and then rounded to the same interval, which is what
    snaps a request opening at half past onto the wall clock rather than carrying its own phase
    through the whole series.

    The interval comes from `Frequency` rather than from `resolution.reading_interval`, which is
    the only place the two differ: `Frequency` answers for `subdaily` and calls it hourly, where
    `reading_interval` declines to, since subdaily is a bucket rather than an interval and its
    providers disagree on one -- DWD takes three Termin readings a day where Meteo-France SYNOP
    reports every three hours. Naming an interval too fine over-completes the grid, leaving rows
    no station has a reading for, which is harmless here in a way it is not where a station is
    being measured against how much of a window it filled.
    """
    frequency = Frequency[resolution.name].value
    return pl.DataFrame(
        {
            "date": pl.datetime_range(
                start=start_date,
                end=end_date,
                interval=frequency,
                time_zone="UTC",
                eager=True,
            ).dt.round(frequency),
        },
        orient="col",
    )


def lapse_rate_for(
    parameter: ParameterModel,
    unit_converter: UnitConverter,
    *,
    convert_units: bool,
) -> float | None:
    """Give the rate a quantity falls at, in the unit its values are written in.

    The table declares it per kelvin, which is per degree Celsius too, those being the same step.
    A step of a degree Fahrenheit is not: with `ts_unit_targets={"temperature": "degree_fahrenheit"}`
    the values are 1.8 times as far apart as their Celsius readings, and a rate left in kelvin would
    move them by 8.45 where 15.21 is meant.

    Args:
        parameter: the parameter whose values are being corrected
        unit_converter: the converter the values went through
        convert_units: whether they went through it at all

    Returns:
        The rate in the values' own unit, or None for a quantity that does not fall with height

    """
    lapse_rate = PARAMETERS[parameter.name].lapse_rate
    if not lapse_rate:
        return None
    unit = unit_converter.targets[parameter.unit_type].name if convert_units else parameter.unit
    return lapse_rate * unit_converter.increment_factor("degree_celsius", unit)


def open_parameter_data(
    param_dict: dict,
    param_key: tuple[str, str, str],
    resolution: Resolution,
    start_date: dt.datetime | None,
    end_date: dt.datetime | None,
) -> _ParameterData | None:
    """Get the parameter's data, opening it on the date grid the request asks over.

    None where the request named no window, there being no grid to lay the readings on then.
    """
    if param_key in param_dict:
        return param_dict[param_key]
    if start_date is None or end_date is None:
        return None
    param_dict[param_key] = _ParameterData(build_date_grid(resolution, start_date, end_date))
    return param_dict[param_key]


def can_answer_at_height(station_height: float | None, lapse_rate: float | None, target_height: float | None) -> bool:
    """Whether a station has anything to say about a quantity at a given height.

    It has not when the quantity falls with height, a height was asked about, and the station's own
    is unknown: its reading cannot be placed against the target, and letting it through would put
    it at its own altitude among neighbours moved to the caller's.
    """
    return not (target_height is not None and lapse_rate and station_height is None)


class StationsInReach(NamedTuple):
    """How many stations a parameter has to draw on, and how many of those report a height."""

    total: int
    with_height: int


def count_stations_in_reach(
    df_stations_ranked: pl.DataFrame,
    parameters: Iterable[object],
    settings: Settings,
) -> dict[tuple[str, str, str], StationsInReach]:
    """Count what each parameter has within its own radius, before a single value is downloaded.

    Per parameter, because the radius is: a quantity that decorrelates fast in space is given a
    narrower one, so "is there a station of known height in reach" has a different answer for
    temperature at 20 km than for precipitation at 40 km, and one answer for the whole request
    would be the wrong one for at least one of them.

    Two counts come out of it. The total says whether the exclusions can be blamed for an
    unanswered parameter: where fewer stations were ever in reach than the calculation needs, the
    heights are not what emptied it. The height count says whether walking further can help: where
    no station in reach reports one, nothing this walk downloads will change that.
    """
    counts = {}
    for parameter in parameters:
        if not isinstance(parameter, ParameterModel):
            continue
        dataset = parameter.dataset
        radius = settings.ts_geo_station_distance_for(parameter.name, dataset.resolution.name)
        in_reach = df_stations_ranked.filter(pl.col("distance").le(radius)).unique(subset=["station_id"])
        counts[(dataset.resolution.name, dataset.name, parameter.name)] = StationsInReach(
            total=in_reach.height,
            with_height=in_reach.drop_nulls("height").height,
        )
    return counts


def unanswerable_at_height(
    counts: dict[tuple[str, str, str], StationsInReach],
    elevation: float | None,
) -> set[tuple[str, str, str]]:
    """Find the parameters no station in reach can answer at the height asked about.

    A quantity that falls with height needs a station whose own height is known to be brought to
    another one. Where not one station inside its radius reports a height -- which is every station
    FMI, IPMA and the Environment Agency publish -- the parameter is unanswerable before anything
    is downloaded, and the walk down the ranking has nothing to look for.
    """
    if elevation is None:
        return set()
    return {
        param_key
        for param_key, in_reach in counts.items()
        if not in_reach.with_height and PARAMETERS[param_key[2]].lapse_rate
    }


def collection_is_done(param_dict: dict, waiting_on: set[tuple[str, str, str]]) -> bool:
    """Whether every parameter has the stations it needs, so the walk down the ranking can stop.

    A parameter every station so far was turned away from for having no height never opened an
    entry of its own, so it cannot hold the walk open by being unfinished. Stopping there would
    report it as unanswerable while a station further out, still inside the radius, has a height
    and could have answered it -- so a parameter that lost a station and has yet to take one keeps
    the walk going.

    `waiting_on` is those of them that a further station could still answer: a parameter with no
    station of known height anywhere inside its radius is not among them, since holding the walk
    open for it would download the rest of the ranking to arrive at the answer the fourth station
    already gave.
    """
    return (
        bool(param_dict)
        and all(param_data.finished for param_data in param_dict.values())
        and not waiting_on.difference(param_dict)
    )


def report_height_exclusions(
    df: pl.DataFrame,
    param_dict: dict,
    dropped_for_height: set[tuple[str, str, str]],
    counts: dict[tuple[str, str, str], StationsInReach],
    elevation: float | None,
    *,
    stations_needed: int,
) -> None:
    """Say what asking about a height cost, once the answer is in.

    A station whose own height is unknown is turned away from a quantity that falls with height,
    and thirteen providers have such stations -- every one of FMI's, IPMA's and the Environment
    Agency's among them. Where that leaves a parameter unanswered, the result is not "no data for
    those dates": it is a question that cannot be answered as asked, and one the caller can fix.
    Left alone it comes back as an empty frame with the reason in a server-side log, which is the
    one place the caller cannot look.

    Whether a parameter was answered is read off the finished frame rather than off the columns
    that were collected for it, because the two are not the same question. A summary answers from
    one station, so a column is an answer; an interpolation wants four that surround the point, so
    a parameter left with three by the exclusions holds columns and still comes back all null --
    which is the silent empty result this is here to do away with.

    A parameter some other station answered is not reported at all: a station turned away where
    the rest sufficed cost the answer nothing. Nor is one the exclusions cannot be blamed for --
    a parameter that kept the stations its calculation asks for and still came back null failed on
    the geometry of where they stand or on the data they hold, and telling such a caller to ask
    without an elevation would send them back for the same nulls under a wrong diagnosis. Nor is a
    parameter that never had enough stations in reach to answer with: keeping every one of them
    would still have left it short, so the exclusions are not what emptied it.

    Args:
        df: the interpolated or summarized frame, before any nulls are dropped from it
        param_dict: the parameters that were collected, each holding the columns it took
        dropped_for_height: the parameters that lost a station for having no height
        elevation: the height that was asked about
        counts: how many stations each parameter had in reach, and how many reported a height
        stations_needed: how many stations the calculation wants before it can answer -- four
            surrounding the point for an interpolation, one for a summary

    Raises:
        NoStationsWithHeightError: where nothing was answered at all, there being no result for a
            warning to be read against

    """
    if not dropped_for_height:
        return
    answered = set(df.drop_nulls("value").select("resolution", "dataset", "parameter").unique().iter_rows())
    emptied = sorted(
        param_key
        for param_key in dropped_for_height - answered
        # minus the date column the values are laid on
        if (param_dict[param_key].values.width - 1 if param_key in param_dict else 0)
        < stations_needed
        <= counts[param_key].total
    )
    if not emptied:
        return
    listing = ", ".join("/".join(param_key) for param_key in emptied)
    if answered:
        log.warning(
            f"leaving out the stations of unknown height leaves nothing that can answer {listing} "
            f"at {elevation} m; the rest of the result stands",
        )
        return
    msg = (
        f"leaving out the stations of unknown height leaves nothing that can answer {listing} at "
        f"{elevation} m. Ask by coordinates and without an elevation to take each station's "
        f"readings as they came -- naming a station id instead asks at that station's own height "
        f"-- or use a provider that publishes the heights of its stations."
    )
    raise NoStationsWithHeightError(msg)


def reduce_to_height(
    values: pl.Series,
    lapse_rate: float | None,
    station_height: float | None,
    target_height: float | None,
) -> pl.Series | None:
    """Bring a station's readings to the height they are being asked about.

    A quantity that falls with height -- air temperature at about 0.65 K per 100 m, a dew point at
    0.2 -- says something different at a valley station than at a summit one, and interpolating the
    two as they come fits that vertical difference as though it were horizontal. Around Garmisch
    the stations within 40 km span 630 m to 2956 m, which is 15 K of air temperature; even the flat
    country around Frankfurt spans 495 m, or 3.2 K.

    The correction needs a height for the target, which the interpolation cannot supply itself: a
    height taken from the same linear interpolation cancels out of it exactly, leaving the result
    unchanged. So it is applied only when a caller says where the point is, and otherwise the
    readings are left as they came.

    A station whose own height is unknown cannot be placed against that target at all, and
    thirteen providers have such stations -- every one of FMI's, IPMA's and the Environment
    Agency's, and a scattering of ECCC's and met.no's. Letting its readings through uncorrected
    would put them at their own altitude while their neighbours are moved to the caller's, which
    is a worse answer than leaving the station out: hence `None`, meaning it has nothing to
    contribute to a question about this height.

    Args:
        values: the station's readings
        lapse_rate: the rate the quantity falls at, in the values' own unit per metre
        station_height: the height the station stands at, in metres
        target_height: the height asked about, in metres

    Returns:
        The readings as they would read at the target height, or None where the station cannot be
        placed against it

    """
    if target_height is None or not lapse_rate:
        return values
    if station_height is None:
        return None
    return values - lapse_rate * (target_height - station_height)


def extract_station_values(
    param_data: _ParameterData,
    result_series_param: pl.Series,
    min_gain_of_value_pairs: float,
    num_additional_stations: int,
    *,
    valid_station_groups_exists: bool,
) -> bool:
    """Extract station values.

    Returns whether the station's column was taken. It is not, once the parameter has what it
    needs, and a caller counting the stations an answer draws on has to tell the two apart.
    """
    # Three rules:
    # 1. only add further stations if not a minimum of 4 stations is reached OR
    # 2. a gain of 10% of timestamps with at least 4 existing values over all stations is seen OR
    # 3. an additional stations_counter is below 3 (used if a station has really no or few values)
    cond1 = param_data.values.shape[1] < 5  # 5: dates plus 4 values
    cond2 = calculate_gain_of_value_pairs(param_data.values, result_series_param) >= min_gain_of_value_pairs
    cond3 = param_data.additional_station_counter < num_additional_stations
    if not valid_station_groups_exists or cond1 or cond2 or cond3:  # timestamps + 4 stations
        if not (cond1 or cond2):
            param_data.additional_station_counter += 1
        param_data.values = param_data.values.with_columns(result_series_param)
        return True
    param_data.finished = True
    return False


def calculate_gain_of_value_pairs(old_values: pl.DataFrame, new_values: pl.Series) -> float:
    """Calculate the gain of value pairs.

    The gain of value pairs is calculated by the following formula:

    number of value pairs with at least 4 values in old_values and new_values /
    number of value pairs with at least 4 values in old_values - 1

    """
    old_score = (
        old_values.select(pl.fold(acc=0, function=lambda acc, s: acc + s.is_not_null(), exprs=pl.all()) >= 5)
        .sum()
        .item()
    )  # 5: dates plus 4 values
    old_values = old_values.with_columns(pl.lit(new_values).alias(new_values.name))
    new_score = (
        old_values.select(pl.fold(acc=0, function=lambda acc, s: acc + s.is_not_null(), exprs=pl.all()) >= 5)
        .sum()
        .item()
    )  # 5: dates plus 4 values
    if old_score == 0:
        if new_score == 0:
            return 0.0
        return 1.0
    return new_score / old_score - 1.0
