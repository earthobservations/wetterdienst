# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tools for timeseries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.metadata.resolution import Frequency

if TYPE_CHECKING:
    import datetime as dt

    from wetterdienst.metadata.resolution import Resolution


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


def reduce_to_height(
    values: pl.Series,
    parameter_name: str,
    station_height: float | None,
    target_height: float | None,
) -> pl.Series:
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

    Args:
        values: the station's readings
        parameter_name: the canonical name, which carries the rate the quantity falls at
        station_height: the height the station stands at, in metres
        target_height: the height asked about, in metres

    Returns:
        The readings as they would read at the target height

    """
    if target_height is None or station_height is None:
        return values
    lapse_rate = PARAMETERS[parameter_name].lapse_rate
    if not lapse_rate:
        return values
    return values - lapse_rate * (target_height - station_height)


def extract_station_values(
    param_data: _ParameterData,
    result_series_param: pl.Series,
    min_gain_of_value_pairs: float,
    num_additional_stations: int,
    *,
    valid_station_groups_exists: bool,
) -> None:
    """Extract station values."""
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
    else:
        param_data.finished = True


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
