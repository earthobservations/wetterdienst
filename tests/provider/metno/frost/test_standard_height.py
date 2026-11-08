# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A parameter that Frost measures at several heights is served from one: the standard one, or the nearest (GH-3844).

Frost answers every height of a station, the highest first, and the core keeps the first row of a reading that has a
value: the air temperature came from 10 m in 83 % of the hours at 5 of the 6 stations that have 2 m and 10 m, the
humidity from 1 m or 10 m in 99.8 %, and the 10 minute gust of the platforms from 47 to 120 m in 96 % of the intervals
(measured 2026-11-07). The maintainer decided that for each time the standard height of Frost (2 m for the temperature
and the humidity, 10 m for the wind speed, the direction and the gust) is served where it has a value, the other height
where it has not, and that the speed and the direction of a time are a pair of one height: the standard one if it has
both, else the nearest height that has both, else the speed standard-first and the direction of its height.

The readings below are real ones, as Frost answered them on 2026-11-07 (the station, the stamp, the height, the value
and the `qualityCode`), in the order Frost gave them. The quality code tells which height a value is from: it is the
code of that sensor's reading.
"""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from tests.provider.metno.frost.test_values_failures import _answered_by, _values
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.util.response_warnings import begin_response

UTC = dt.UTC
PATHS = ["batch", "single", "discovery"]
AVAILABLE = {
    "data": [
        {
            "validFrom": "1940-01-01T00:00:00Z",
            "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0",
        }
    ]
}
TEMPERATURE = "air_temperature"
HUMIDITY = "relative_humidity"
SPEED = "wind_speed"
DIRECTION = "wind_from_direction"
GUST = "max(wind_speed_of_gust PT10M)"

# (stamp, [(element, height, value, qualityCode, timeOffset)]): an hour as Frost answers it
Hour = tuple[str, list[tuple[str, float, float, int, str]]]


def _answer(hours: list[Hour]) -> dict:
    """Give Frost's answer for the hours: one entry for each stamp, one observation for each reading."""
    return {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": f"{stamp}:00.000Z",
                "observations": [
                    {
                        "elementId": element,
                        "value": value,
                        "qualityCode": quality,
                        "timeOffset": offset,
                        "level": {"levelType": "height_above_ground", "unit": "m", "value": height},
                    }
                    for element, height, value, quality, offset in readings
                ],
            }
            for stamp, readings in hours
        ]
    }


def _read(
    monkeypatch: pytest.MonkeyPatch,
    answer: dict,
    parameters: list[tuple[str, str, str]],
    start: str,
    end: str,
    station: str = "SN18700",
    path: str = "batch",
    options: dict | None = None,
) -> pl.DataFrame:
    """Give the values of ``parameters`` that Frost's ``answer`` makes by the reader ``path`` reaches."""
    requested = list(parameters)
    if path == "single":
        # the single reader is reached by a parameter of a dataset whose batch 404s
        resolution = parameters[0][0]
        helper = {"hourly": "pressure_air_site", "10_minutes": "precipitation_amount", "daily": "snow_depth"}
        requested.append((resolution, "data", helper.get(resolution, "precipitation_amount")))
    values, _ = _values(
        monkeypatch,
        _answered_by(path, answer, AVAILABLE),
        requested,
        start=dt.datetime.fromisoformat(start).replace(tzinfo=UTC),
        end=dt.datetime.fromisoformat(end).replace(tzinfo=UTC),
        station=station,
        options=options,
    )
    begin_response()
    return values.all().df.sort("parameter", "timestamp")


def _of(df: pl.DataFrame, name: str) -> pl.DataFrame:
    return df.filter(pl.col("parameter") == name)


# SN18700 (Oslo - Blindern) measures the temperature at 2 m and at 10 m. Frost answers the 10 m reading first, which the
# core kept: the 10 m sensor reads 0.1 degC lower than the 2 m one in these hours, and has a quality code of 2
OSLO = [
    (
        "2025-11-01T00:00",
        [(TEMPERATURE, 10, 2.4, 2, "PT0H"), (TEMPERATURE, 2, 2.5, 0, "PT0H")],
    ),
    (
        "2025-11-01T01:00",
        [(TEMPERATURE, 10, 2.6, 2, "PT0H"), (TEMPERATURE, 2, 2.7, 0, "PT0H")],
    ),
    (
        "2025-11-01T02:00",
        [(TEMPERATURE, 10, 2.9, 2, "PT0H"), (TEMPERATURE, 2, 3.0, 0, "PT0H")],
    ),
    # 2026-03-05 11:00 has a 2 m reading only
    ("2026-03-05T11:00", [(TEMPERATURE, 2, 4.7, 1, "PT0H")]),
]


@pytest.mark.parametrize("path", PATHS)
def test_metno_frost_temperature_is_the_2_m_sensor_where_it_has_a_value(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Test that SN18700 returns the 2 m temperature, whichever height Frost answers first, on every reader.

    The three hours have a value at both heights, and the 10 m one came first and was returned (2.4, 2.6, 2.9; quality
    code 2). The hour of 2026-03-05 has 2 m only, and is returned as it was.
    """
    df = _read(
        monkeypatch,
        _answer(OSLO),
        [("hourly", "data", "temperature_air_2m")],
        "2025-11-01T00:00",
        "2026-03-06T00:00",
        path=path,
    )
    assert df["value"].to_list() == [2.5, 2.7, 3.0, 4.7]
    # the codes are those of the 2 m sensor
    assert df["quality_flags"].to_list() == ["0", "0", "0", "1"]


def test_metno_frost_the_order_of_frost_s_rows_does_not_decide_the_height(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the 2 m reading is served when Frost answers it first as well as when it answers it last."""
    reversed_hours = [(stamp, list(reversed(readings))) for stamp, readings in OSLO]
    df = _read(
        monkeypatch,
        _answer(reversed_hours),
        [("hourly", "data", "temperature_air_2m")],
        "2025-11-01T00:00",
        "2026-03-06T00:00",
    )
    assert df["value"].to_list() == [2.5, 2.7, 3.0, 4.7]


# SN17850 has the humidity at 1 m, 2 m and 50 m: 99 at 2 m is served, whatever 1 m and 50 m say
FORNEBU_HUMIDITY = [
    ("2025-11-01T00:00", [(HUMIDITY, 50, 98, 2, "PT0H"), (HUMIDITY, 2, 99, 0, "PT0H"), (HUMIDITY, 1, 92, 2, "PT0H")]),
    # no 2 m reading: the height nearest to 2 m is served, 1 m (the one at 50 m is the farthest); the values of this
    # hour are those of the hour before
    ("2025-11-01T01:00", [(HUMIDITY, 50, 98, 2, "PT0H"), (HUMIDITY, 1, 92, 2, "PT0H")]),
]


@pytest.mark.parametrize("path", PATHS)
def test_metno_frost_humidity_is_the_2_m_sensor_and_the_nearest_height_fills_a_gap(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Test that the humidity of a station with three heights is the 2 m one, and the nearest one where it has none.

    The 1 m sensor came last in Frost's answer, so the core served the 50 m one (98 %) in the first hour.
    """
    df = _read(
        monkeypatch,
        _answer(FORNEBU_HUMIDITY),
        [("hourly", "data", "humidity_relative")],
        "2025-11-01T00:00",
        "2025-11-01T01:00",
        station="SN17850",
        path=path,
    )
    assert df["value"].to_list() == [99.0, 92.0]
    assert df["quality_flags"].to_list() == ["0", "2"]


# SN44300 (the station with most mixed pairs, 8.8 % of its hours) has the wind at 10 m and 2 m: the first hour has both
# heights, the second only 2 m for both the speed and the bearing (the 10 m sensor has a gap), the third a speed at 10 m
# with a bearing at 2 m only
WIND_PAIRS = [
    (
        "2025-11-01T00:00",
        [
            (SPEED, 10, 8.8, 0, "PT0H"),
            (SPEED, 2, 5.0, 2, "PT0H"),
            (DIRECTION, 10, 119, 0, "PT0H"),
            (DIRECTION, 2, 135, 2, "PT0H"),
        ],
    ),
    ("2026-06-02T12:00", [(SPEED, 2, 5.5, 2, "PT0H"), (DIRECTION, 2, 346, 2, "PT0H")]),
    (
        "2026-06-04T07:00",
        [(SPEED, 10, 7.8, 6, "PT0H"), (SPEED, 2, 5.7, 2, "PT0H"), (DIRECTION, 2, 346, 2, "PT0H")],
    ),
    (
        "2026-06-04T08:00",
        [(SPEED, 10, 8.4, 6, "PT0H"), (SPEED, 2, 5.7, 2, "PT0H"), (DIRECTION, 2, 346, 2, "PT0H")],
    ),
    (
        "2026-06-04T09:00",
        [(SPEED, 10, 8.1, 6, "PT0H"), (SPEED, 2, 5.7, 2, "PT0H"), (DIRECTION, 2, 346, 2, "PT0H")],
    ),
]
WIND = [("hourly", "data", "wind_speed_mean_last_10min"), ("hourly", "data", "wind_direction_mean_last_10min")]


def test_metno_frost_the_speed_and_the_bearing_are_a_pair_of_one_height(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that SN44300's speed and bearing are of one height: the 10 m pair if it is whole, else the 2 m one.

    - 2025-11-01 00:00: both heights have both: the 10 m pair (8.8 m/s, 119 degrees), as the core served it.
    - 2026-06-02 12:00: 10 m has neither, 2 m has both: the 2 m pair (5.5 m/s, 346 degrees).
    - 2026-06-04 07:00 to 09:00: 10 m has a speed (7.8, 8.4 and 8.1) and no bearing, and the bearing of 2 m (346) stood
      beside it, 502 of the station's hours in a year (8.8 %). The pair is the 2 m one, speed and bearing (5.7 m/s, 346
      degrees): no mixed pair, and no bearing lost. The 10 m speed is not served though it is the standard height's.
    """
    df = _read(monkeypatch, _answer(WIND_PAIRS), WIND, "2025-11-01T00:00", "2026-06-05T00:00", station="SN44300")
    speed = _of(df, "wind_speed_mean_last_10min")
    direction = _of(df, "wind_direction_mean_last_10min")
    assert speed["value"].to_list() == [8.8, 5.5, 5.7, 5.7, 5.7]
    assert speed["quality_flags"].to_list() == ["0", "2", "2", "2", "2"]
    assert direction["value"].to_list() == [119.0, 346.0, 346.0, 346.0, 346.0]
    assert direction["quality_flags"].to_list() == ["0", "2", "2", "2", "2"]


def test_metno_frost_a_time_with_no_whole_pair_has_each_standard_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the last step of the rule: no height has both, so the speed and the bearing are each chosen apart.

    A built answer: a speed at 10 m and 2 m, a bearing at 5 m. No height has both, so the speed is the 10 m one and the
    bearing is served beside it, of 5 m: a bearing is not lost because Frost never measured the two at one height.
    """
    hours = [
        (
            "2025-11-01T00:00",
            [(SPEED, 10, 7.8, 6, "PT0H"), (SPEED, 2, 5.7, 2, "PT0H"), (DIRECTION, 5, 346, 2, "PT0H")],
        )
    ]
    df = _read(monkeypatch, _answer(hours), WIND, "2025-11-01T00:00", "2025-11-01T01:00", station="SN44300")
    assert _of(df, "wind_speed_mean_last_10min")["value"].to_list() == [7.8]
    assert _of(df, "wind_direction_mean_last_10min")["value"].to_list() == [346.0]


# SN92120, 1993-06-01 to 03, as Frost answered it (the whole answer, 48 hours): the speed at 2 m only, every third hour,
# the bearing at 10 m only, every hour. The station and SN92130 measured so from 1992-02 to 1993-12, and SN49490 for 4
# days in 2013: no height has both, so the pair rule has no pair to give
SN92120_SPEEDS = {
    0: 17.7, 3: 15.6, 6: 14.4, 9: 11.8, 12: 10.4, 15: 9.0, 18: 8.4, 21: 6.6,
    24: 8.5, 27: 9.2, 30: 7.3, 33: 6.9, 36: 8.0, 39: 6.0, 42: 5.4, 45: 4.4,
}  # fmt: skip
SN92120_BEARINGS = [
    27, 26, 32, 32, 36, 33, 33, 38, 40, 40, 47, 58, 58, 48, 53, 53, 50, 72, 72, 80, 87, 87, 101, 101,
    101, 101, 101, 101, 82, 82, 82, 72, 64, 64, 54, 59, 59, 55, 54, 54, 51, 57, 57, 54, 72, 72, 86, 107,
]  # fmt: skip


def test_metno_frost_a_station_that_never_measured_both_at_one_height_keeps_every_bearing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that all 48 bearings of SN92120 are served, beside the 2 m speeds that exist, measured at another height.

    The speed is at 2 m (every third hour) and the bearing at 10 m (every hour): no height has both. A rule that gave
    the bearing only to the speed's height kept 16 of the 48 bearings; the maintainer decided that no bearing is lost
    where Frost never measured the two at one height, and that the mixed pair is documented.
    """
    hours = [
        (
            f"1993-06-0{1 + hour // 24}T{hour % 24:02d}:00",
            [
                *([(SPEED, 2, SN92120_SPEEDS[hour], 2, "PT0H")] if hour in SN92120_SPEEDS else []),
                (DIRECTION, 10, SN92120_BEARINGS[hour], 2, "PT0H"),
            ],
        )
        for hour in range(48)
    ]
    df = _read(monkeypatch, _answer(hours), WIND, "1993-06-01T00:00", "1993-06-03T00:00", station="SN92120")
    speed = _of(df, "wind_speed_mean_last_10min")
    direction = _of(df, "wind_direction_mean_last_10min")
    assert speed["value"].to_list() == list(SN92120_SPEEDS.values())
    assert direction["value"].to_list() == [float(value) for value in SN92120_BEARINGS]


def test_metno_frost_a_bearing_follows_its_speed_to_the_other_height_of_a_station_with_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a bearing of 2 m stands beside the speed of 2 m, though 10 m has a bearing too (a built answer).

    The 10 m speed has a gap, and the 10 m bearing has a value: only 2 m has both, so the pair is the 2 m one. (No hour
    of the sample has this: it is the case that the rule decides, not the one Frost has.)
    """
    hours = [
        (
            "2025-11-01T00:00",
            [(SPEED, 2, 5.0, 2, "PT0H"), (DIRECTION, 10, 119, 0, "PT0H"), (DIRECTION, 2, 135, 2, "PT0H")],
        )
    ]
    df = _read(monkeypatch, _answer(hours), WIND, "2025-11-01T00:00", "2025-11-01T01:00", station="SN44300")
    assert _of(df, "wind_speed_mean_last_10min")["value"].to_list() == [5.0]
    assert _of(df, "wind_direction_mean_last_10min")["value"].to_list() == [135.0]


def test_metno_frost_a_bearing_asked_for_alone_is_the_standard_height_where_it_has_a_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the direction is the 10 m one, then the other, when it is read without the speed.

    The batch holds the whole dataset, so the speed is read and the pair is chosen (the hour of 07:00 has the 2 m pair).
    A bearing read by itself (the single and the discovery readers, which are reached only after a 404 of the whole)
    has no speed to pair with and is the standard height where it has a value.
    """
    df = _read(
        monkeypatch,
        _answer(WIND_PAIRS),
        [WIND[1]],
        "2025-11-01T00:00",
        "2026-06-05T00:00",
        station="SN44300",
        path="single",
    )
    # the bearing of 2 m is the only one at 10 m's gap, and is served by itself
    assert df["value"].to_list() == [119.0, 346.0, 346.0, 346.0, 346.0]


# SN12550 lists a wind speed at 10 m, which holds 2 hours of the year: its wind is the 2 m one (36 of the 67 stations
# with two heights are like it)
NO_TEN_METRES = [
    (
        "2019-03-01T00:00",
        [(SPEED, 2, 0.5, 0, "PT0H"), (DIRECTION, 2, 179, 0, "PT0H")],
    ),
    (
        "2019-03-01T01:00",
        [(SPEED, 2, 1.1, 0, "PT0H"), (DIRECTION, 2, 315, 0, "PT0H")],
    ),
    (
        "2019-03-01T02:00",
        [(SPEED, 2, 0.6, 0, "PT0H"), (DIRECTION, 2, 276, 0, "PT0H")],
    ),
]


def test_metno_frost_a_station_whose_10_m_series_is_empty_is_served_from_2_m(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the wind of SN12550 is returned from 2 m, which is why `levels=default` alone is not used.

    `levels=default` answers a 404 for the station: the 10 m series is the standard one and has no data in the window.
    """
    df = _read(monkeypatch, _answer(NO_TEN_METRES), WIND, "2019-03-01T00:00", "2019-03-01T03:00", station="SN12550")
    assert _of(df, "wind_speed_mean_last_10min")["value"].to_list() == [0.5, 1.1, 0.6]
    assert _of(df, "wind_direction_mean_last_10min")["value"].to_list() == [179.0, 315.0, 276.0]


# the 10 minute gust of the platforms: SN76922 has 10 m, 50 m and 121 m. Frost answers the highest first
OFFSHORE = [
    (
        "2022-07-22T00:00",
        [(GUST, 121, 9.6, 2, "PT0H"), (GUST, 10, 7.1, 0, "PT0H")],
    ),
    (
        "2022-07-22T05:50",
        [(GUST, 50, 9.1, 2, "PT0H"), (GUST, 10, 6.7, 0, "PT0H")],
    ),
]


@pytest.mark.parametrize("path", PATHS)
def test_metno_frost_the_gust_of_a_platform_is_the_10_m_one(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    """Test that SN76922 returns the 10 m gust, where the core returned the one of 121 m (9.6) and 50 m (9.1)."""
    df = _read(
        monkeypatch,
        _answer(OFFSHORE),
        [("10_minutes", "data", "wind_gust_max")],
        "2022-07-22T00:00",
        "2022-07-22T06:00",
        station="SN76922",
        path=path,
    )
    assert df["value"].to_list() == [7.1, 6.7]
    assert df["quality_flags"].to_list() == ["0", "0"]


def test_metno_frost_a_gust_without_10_m_is_the_nearest_height(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a gust whose 10 m has a gap is the height nearest to 10 m, and the only one if it is the only one.

    SN76960 at 2026-10-09 03:30 has 84 m and 126 m, SN76926 at 2026-10-02 10:50 has 136 m alone.
    """
    nearest = _read(
        monkeypatch,
        _answer([("2026-10-09T03:30", [(GUST, 126, 10.4, 2, "PT0H"), (GUST, 84, 10.0, 2, "PT0H")])]),
        [("10_minutes", "data", "wind_gust_max")],
        "2026-10-09T03:30",
        "2026-10-09T03:40",
        station="SN76960",
    )
    assert nearest["value"].to_list() == [10.0]
    alone = _read(
        monkeypatch,
        _answer([("2026-10-02T10:50", [(GUST, 136, 16.4, 2, "PT0H")])]),
        [("10_minutes", "data", "wind_gust_max")],
        "2026-10-02T10:50",
        "2026-10-02T11:00",
        station="SN76926",
    )
    assert alone["value"].to_list() == [16.4]


# daily and monthly wind and temperature have the heights too (SN44300 wind, SN18210 temperature)
DAILY_WIND = [
    (
        "2025-11-01T00:00",
        [
            ("mean(wind_speed P1D)", 10, 7.6, 2, "PT0H"),
            ("mean(wind_speed P1D)", 2, 4.9, 0, "PT0H"),
            ("max(wind_speed P1D)", 10, 9.7, 0, "PT0H"),
            ("max(wind_speed P1D)", 2, 8.0, 0, "PT0H"),
        ],
    ),
]
MONTHLY_WIND = [
    (
        "2019-04-01T00:00",
        [
            ("mean(wind_speed P1M)", 10, 3.3, 2, "PT0H"),
            ("mean(wind_speed P1M)", 2, 2.3, 2, "PT0H"),
            ("max(wind_speed P1M)", 10, 11.1, 2, "PT0H"),
            ("max(wind_speed P1M)", 2, 7.7, 2, "PT0H"),
        ],
    ),
]


def test_metno_frost_the_daily_and_monthly_wind_is_the_10_m_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the daily and the monthly mean and maximum of the wind are of 10 m where it has them."""
    daily = _read(
        monkeypatch,
        _answer(DAILY_WIND),
        [("daily", "data", "wind_speed_mean"), ("daily", "data", "wind_speed_rolling_mean_max")],
        "2025-11-01T00:00",
        "2025-11-01T00:00",
        station="SN44300",
    )
    assert _of(daily, "wind_speed_mean")["value"].to_list() == [7.6]
    assert _of(daily, "wind_speed_rolling_mean_max")["value"].to_list() == [9.7]
    monthly = _read(
        monkeypatch,
        _answer(MONTHLY_WIND),
        [("monthly", "data", "wind_speed_mean"), ("monthly", "data", "wind_speed_rolling_mean_max")],
        "2019-04-01T00:00",
        "2019-04-01T00:00",
        station="SN44300",
    )
    assert _of(monthly, "wind_speed_mean")["value"].to_list() == [3.3]
    assert _of(monthly, "wind_speed_rolling_mean_max")["value"].to_list() == [11.1]


def test_metno_frost_the_daily_temperature_is_the_2_m_calendar_day(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that SN18210's daily mean is the 2 m calendar day: not the 10 m one (6.5), nor the 06-06 UTC series (-0.9).

    The 2 m sensor has both series, which `_keep_standard_offset` reduces to `PT0H`, and the 10 m sensor has one.
    """
    hours = [
        (
            "2017-11-23T00:00",
            [
                ("mean(air_temperature P1D)", 10, 6.5, 2, "PT0H"),
                ("mean(air_temperature P1D)", 2, 6.4, 0, "PT0H"),
                ("mean(air_temperature P1D)", 2, -0.9, 2, "PT6H"),
            ],
        )
    ]
    df = _read(
        monkeypatch,
        _answer(hours),
        [("daily", "data", "temperature_air_mean_2m")],
        "2017-11-23T00:00",
        "2017-11-23T00:00",
        station="SN18210",
    )
    assert df["value"].to_list() == [6.4]
    assert df["quality_flags"].to_list() == ["0"]


def test_metno_frost_the_offset_is_chosen_before_the_height(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a date whose 2 m series is of another offset is served from the 10 m one of the standard offset.

    A built answer (no date of the sample has it): the 2 m sensor has the 06-06 UTC mean only, the 10 m sensor the
    calendar day. The offset is chosen first (`_keep_standard_offset`), so the 2 m row is gone when the height is
    chosen, and the 10 m calendar day is the answer; chosen the other way round, the 2 m row would win and be left out
    with it, and the date would be lost.
    """
    hours = [
        (
            "2017-11-23T00:00",
            [("mean(air_temperature P1D)", 10, 6.5, 2, "PT0H"), ("mean(air_temperature P1D)", 2, -0.9, 2, "PT6H")],
        )
    ]
    df = _read(
        monkeypatch,
        _answer(hours),
        [("daily", "data", "temperature_air_mean_2m")],
        "2017-11-23T00:00",
        "2017-11-23T00:00",
        station="SN18210",
    )
    assert df["value"].to_list() == [6.5]


# the frame `_read_observations` hands to the choice: parameter, timestamp, value, the height as text
def _frame(rows: list[tuple[str, int, str, float | None]]) -> pl.DataFrame:
    """Give the frame of readings (parameter, hour, height, value)."""
    return pl.DataFrame(
        {
            "parameter": [parameter for parameter, _, _, _ in rows],
            "timestamp": [dt.datetime(2020, 1, 1, hour, tzinfo=UTC) for _, hour, _, _ in rows],
            "value": [value for _, _, _, value in rows],
            "quality_flags": ["0"] * len(rows),
            frost_api._LEVEL: [height for _, _, height, _ in rows],  # noqa: SLF001
        },
        schema_overrides={"value": pl.Float64},
    )


def _kept(rows: list[tuple[str, int, str, float | None]]) -> list[tuple[str, int, str]]:
    """Give the (parameter, hour, height) of the readings the choice keeps, in their order."""
    kept = frost_api._prefer_standard_height(_frame(rows))  # noqa: SLF001
    return [(row[0], row[1].hour, row[2]) for row in kept.select("parameter", "timestamp", frost_api._LEVEL).rows()]  # noqa: SLF001


def test_metno_frost_height_choice_prefers_the_standard_and_then_the_nearest_with_a_value() -> None:
    """Test the choice on frames: the standard first, then the nearest, a null being a gap, a tie going to the lower."""
    t = "air_temperature"
    assert _kept([(t, 0, "10", 1.0), (t, 0, "2", 2.0)]) == [(t, 0, "2")]
    # a gap at the standard height is filled by the nearest height that has a value
    assert _kept([(t, 0, "2", None), (t, 0, "50", 3.0), (t, 0, "10", 1.0)]) == [(t, 0, "10")]
    # as near as each other: the lower
    assert _kept([("wind_speed", 0, "5", 1.0), ("wind_speed", 0, "15", 2.0)]) == [("wind_speed", 0, "5")]
    # no height has a value: every row stays, as the core merges them to a null
    assert _kept([(t, 0, "2", None), (t, 0, "10", None)]) == [(t, 0, "2"), (t, 0, "10")]
    # each time is chosen for itself
    assert _kept([(t, 0, "10", 1.0), (t, 0, "2", 2.0), (t, 1, "10", 3.0), (t, 1, "2", None)]) == [
        (t, 0, "2"),
        (t, 1, "10"),
    ]


def test_metno_frost_height_choice_leaves_the_other_parameters_alone() -> None:
    """Test that an element with no standard height, and a frame with no height, are not touched."""
    pressure = [("surface_air_pressure", 0, "2", 1000.0), ("surface_air_pressure", 0, "10", 999.0)]
    assert _kept(pressure) == [("surface_air_pressure", 0, "2"), ("surface_air_pressure", 0, "10")]
    assert frost_api._prefer_standard_height(_frame(pressure).drop(frost_api._LEVEL)).height == 2  # noqa: SLF001
    assert frost_api._prefer_standard_height(_frame([])).is_empty()  # noqa: SLF001
    # a reading with no height competes as the farthest
    assert _kept([("air_temperature", 0, "", 1.0), ("air_temperature", 0, "10", 2.0)]) == [("air_temperature", 0, "10")]


def test_metno_frost_height_choice_reads_the_element_by_its_base_name() -> None:
    """Test that the daily, monthly and 10 minute elements are chosen by the name inside the id."""
    for element, standard in [
        ("mean(air_temperature P1D)", "2"),
        ("max(air_temperature P1M)", "2"),
        ("mean(relative_humidity P1D)", "2"),
        ("mean(wind_speed P1D)", "10"),
        ("max(wind_speed P1M)", "10"),
        ("max(wind_speed_of_gust PT10M)", "10"),
    ]:
        other = "30" if standard == "10" else "10"
        assert _kept([(element, 0, other, 1.0), (element, 0, standard, 2.0)]) == [(element, 0, standard)], element


def test_metno_frost_height_choice_makes_the_speed_and_the_bearing_a_pair_of_one_height() -> None:
    """Test the pairing on frames: the standard pair, else the nearest whole one, else the speed and its own bearing."""
    s, d = "wind_speed", "wind_from_direction"
    # the standard height has both: it is the pair, whatever the other height has
    assert _kept([(s, 0, "10", 7.8), (s, 0, "2", 5.7), (d, 0, "10", 119.0), (d, 0, "2", 135.0)]) == [
        (s, 0, "10"),
        (d, 0, "10"),
    ]
    # the speed is at 10 m, the bearing at 2 m only: the pair is the 2 m one, and the speed of 10 m is not served
    assert _kept([(s, 0, "10", 7.8), (s, 0, "2", 5.7), (d, 0, "2", 346.0)]) == [(s, 0, "2"), (d, 0, "2")]
    # the speed is at 2 m (10 m has none): the bearing is of 2 m, though 10 m has one
    assert _kept([(s, 0, "2", 5.0), (d, 0, "10", 119.0), (d, 0, "2", 135.0)]) == [(s, 0, "2"), (d, 0, "2")]
    # a gap of the bearing at 10 m: 2 m has both and is the pair
    assert _kept([(s, 0, "10", 7.8), (d, 0, "10", None), (s, 0, "2", 5.7), (d, 0, "2", 346.0)]) == [
        (s, 0, "2"),
        (d, 0, "2"),
    ]
    # no standard pair: the nearest height that has both (5 m is nearer to 10 m than 100 m), the lower of two as near
    assert _kept([(s, 0, "100", 9.0), (d, 0, "100", 1.0), (s, 0, "5", 3.0), (d, 0, "5", 2.0), (s, 0, "10", 4.0)]) == [
        (s, 0, "5"),
        (d, 0, "5"),
    ]
    assert _kept([(s, 0, "5", 3.0), (d, 0, "5", 2.0), (s, 0, "15", 4.0), (d, 0, "15", 1.0)]) == [
        (s, 0, "5"),
        (d, 0, "5"),
    ]
    # a code is a bearing: a calm at 10 m has both, and the bearing of 2 m does not replace it
    assert _kept([(s, 0, "10", 0.0), (d, 0, "10", 0.0), (s, 0, "2", 0.0), (d, 0, "2", 170.0)]) == [
        (s, 0, "10"),
        (d, 0, "10"),
    ]
    # no height has both: each is chosen apart, the speed the 10 m one and the bearing the one it has (never lost)
    assert _kept([(s, 0, "10", 7.8), (s, 0, "2", 5.7), (d, 0, "5", 346.0)]) == [(s, 0, "10"), (d, 0, "5")]
    assert _kept([(s, 0, "2", 7.8), (d, 0, "10", 346.0)]) == [(s, 0, "2"), (d, 0, "10")]
    # a gap of the bearing at 10 m, a bearing at 2 m with no speed there: the bearing is the one it has
    assert _kept([(s, 0, "10", 7.8), (d, 0, "10", None), (d, 0, "2", 346.0)]) == [(s, 0, "10"), (d, 0, "2")]
    # no speed at the time: the bearing is the standard height where it has a value, else the nearest
    assert _kept([(d, 0, "10", 119.0), (d, 0, "2", 135.0)]) == [(d, 0, "10")]
    assert _kept([(d, 0, "10", None), (d, 0, "2", 135.0)]) == [(d, 0, "2")]
    # a speed that has no value at any height does not decide
    assert _kept([(s, 0, "10", None), (d, 0, "10", 119.0), (d, 0, "2", 135.0)]) == [(s, 0, "10"), (d, 0, "10")]
    # no direction in the frame: the speed is standard-first (the readers that read a parameter by itself)
    assert _kept([(s, 0, "10", 7.8), (s, 0, "2", 5.7)]) == [(s, 0, "10")]
    # each time is paired for itself
    assert _kept([(s, 0, "10", 7.8), (d, 0, "10", 119.0), (s, 1, "10", 7.8), (s, 1, "2", 5.7), (d, 1, "2", 346.0)]) == [
        (s, 0, "10"),
        (d, 0, "10"),
        (s, 1, "2"),
        (d, 1, "2"),
    ]
    # the daily wind speed and the gust are no speed of a pair
    assert _kept(
        [("mean(wind_speed P1D)", 0, "10", 5.0), ("mean(wind_speed P1D)", 0, "2", 4.0), (d, 0, "2", 119.0)]
    ) == [
        ("mean(wind_speed P1D)", 0, "10"),
        (d, 0, "2"),
    ]
    gust = "max(wind_speed_of_gust PT10M)"
    assert _kept([(gust, 0, "10", 9.0), (gust, 0, "86", 12.0), (d, 0, "86", 119.0)]) == [(gust, 0, "10"), (d, 0, "86")]


def test_metno_frost_a_code_of_the_chosen_height_is_the_hour(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a calm or a `-3` at the pair's height is the hour, and the bearing of the other height is not served.

    The choice is on what Frost answered, before the codes are decoded: a 0 beside a speed of 0 is a calm (null with
    `raw:0`), and a -3 is null with `raw:-3`, at the height of the pair, whatever the other height says. A code is a
    bearing: the 10 m height with a calm or a -3 has both, and is the pair.
    """
    hours = [
        # a calm at 10 m, a bearing at 2 m beside a speed of 0 as well
        (
            "2020-01-01T00:00",
            [
                (SPEED, 10, 0.0, 0, "PT0H"),
                (SPEED, 2, 0.0, 0, "PT0H"),
                (DIRECTION, 10, 0, 0, "PT0H"),
                (DIRECTION, 2, 170, 0, "PT0H"),
            ],
        ),
        # no unique direction at 10 m
        (
            "2020-01-01T01:00",
            [
                (SPEED, 10, 1.0, 0, "PT0H"),
                (SPEED, 2, 1.0, 0, "PT0H"),
                (DIRECTION, 10, -3, 0, "PT0H"),
                (DIRECTION, 2, 200, 0, "PT0H"),
            ],
        ),
        # no bearing at 10 m (no row): the pair is the 2 m one, a bearing of 90
        (
            "2020-01-01T02:00",
            [(SPEED, 10, 1.0, 0, "PT0H"), (SPEED, 2, 1.0, 0, "PT0H"), (DIRECTION, 2, 90, 0, "PT0H")],
        ),
        # the speed is at 2 m: its calm is the hour
        (
            "2020-01-01T03:00",
            [(SPEED, 2, 0.0, 0, "PT0H"), (DIRECTION, 10, 45, 0, "PT0H"), (DIRECTION, 2, 0, 0, "PT0H")],
        ),
    ]
    df = _read(
        monkeypatch,
        _answer(hours),
        WIND,
        "2020-01-01T00:00",
        "2020-01-01T04:00",
        options={"drop_nulls": False},
    )
    direction = _of(df, "wind_direction_mean_last_10min")
    assert direction["value"].to_list() == [None, None, 90.0, None]
    assert [flag.split(",")[-1] for flag in direction["quality_flags"].to_list()] == ["raw:0", "raw:-3", "0", "raw:0"]
