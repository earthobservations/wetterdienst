# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The check `step` for every provider, in both modes (GH-3681).

A change between two consecutive readings, and a reading that jumps away and back, beyond the limits of the table of
`model/rate_of_change.py`.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl
import pytest

from tests.provider.judging import judged
from wetterdienst import Wetterdienst
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.model import judge
from wetterdienst.model.judge import Beside, Bound
from wetterdienst.model.persistence import rule_for as run_rule_for
from wetterdienst.model.plausibility import Plausibility
from wetterdienst.model.rate_of_change import RESOLUTIONS, RULES, StepRule, rule_for

UTC = dt.UTC
PAGE = Path(__file__).parent.parent.parent / "docs" / "data" / "plausibility.md"
SOFT = Plausibility()
HARD = Plausibility(step="hard")
STEPS = {"10_minutes": dt.timedelta(minutes=10), "hourly": dt.timedelta(hours=1), "daily": dt.timedelta(days=1)}
START = dt.datetime(2024, 1, 1, tzinfo=UTC)
AIR = ("dwd/observation", "hourly", "temperature_air", "temperature_air_2m")


def _dataset(network: str, resolution: str, dataset: str) -> object:
    provider, name = network.split("/")
    for res in Wetterdienst.resolve(provider, name).metadata:
        for candidate in res:
            if (res.name, candidate.name) == (resolution, dataset):
                return candidate
    message = f"{network} has no {resolution}/{dataset}"
    raise AssertionError(message)


def _name(dataset: object, canonical: str) -> str:
    """Give the name the source has for a canonical parameter of a dataset."""
    return next(p.name_original for p in dataset if p.name == canonical)


def _frame(
    name: str, values: list[float | None], step: dt.timedelta, stamps: list[dt.datetime] | None = None
) -> pl.DataFrame:
    stamps = stamps or [START + step * i for i in range(len(values))]
    return pl.DataFrame(
        {"parameter": name, "timestamp": stamps, "value": values, "quality_flags": None},
        schema_overrides={"value": pl.Float64, "quality_flags": pl.String},
    )


def _flagged(
    network: str,
    resolution: str,
    dataset: str,
    canonical: str,
    values: list[float | None],
    modes: Plausibility = SOFT,
    stamps: list[dt.datetime] | None = None,
) -> list[int]:
    """Give the positions of the readings the check `step` flagged."""
    ds = _dataset(network, resolution, dataset)
    df = _frame(_name(ds, canonical), values, STEPS[resolution], stamps)
    out = judged(df, network=network, dataset=ds, modes=modes)
    flags = out.get_column("quality_flags").str.contains("step").fill_null(value=False).to_list()
    return [i for i, flag in enumerate(flags) if flag]


# --- the table is a table of sources ------------------------------------------------------------------------------


def test_the_table_names_canonical_parameters_and_the_resolutions_with_a_source() -> None:
    """Every rule is for a canonical parameter, at a resolution with a fixed step, and names its source and unit."""
    resolutions = {resolution for by_resolution in RULES.values() for resolution in by_resolution}
    assert resolutions == set(RESOLUTIONS) == {"10_minutes", "hourly", "daily"}
    for name, by_resolution in RULES.items():
        assert name in PARAMETERS, name
        for resolution, rule in by_resolution.items():
            assert rule.source.startswith(("ISD", "DMI", "MADIS", "DNMI", "Durre et al.", "own derivation")), (
                name,
                resolution,
            )
            assert rule.unit, (name, resolution)
            assert rule.spike is not None or rule.step is not None, (name, resolution)
            for limit in (rule.spike, rule.step):
                assert limit is None or limit > 0, (name, resolution)
            if rule.spike is not None and rule.step is not None:
                assert rule.spike <= rule.step, f"{name} {resolution}: the spike is not the higher limit"


def test_the_limits_of_a_10_minute_series_are_the_limits_of_the_hour() -> None:
    """No source gives a limit at 10 minutes: the hourly one, which a change in 10 minutes cannot exceed, is taken."""
    for name, by_resolution in RULES.items():
        if "10_minutes" in by_resolution:
            hourly, ten = by_resolution["hourly"], by_resolution["10_minutes"]
            assert (ten.spike, ten.step, ten.unit) == (hourly.spike, hourly.step, hourly.unit), name
            assert ten.source.startswith("own derivation"), name


def test_what_the_check_does_not_judge_is_not_in_the_table() -> None:
    """Amounts, directions, gusts, humidity and soil temperature are not judged, and no extreme of an interval is."""
    for name in RULES:
        assert not re.search(r"(_last_\d+h|_yesterday|_multiday|_normal|_night|_day)$", name), name
        assert not re.search(r"^(precipitation|sunshine|snow|radiation|wind_direction|wind_gust|humidity|cloud)", name)
        assert not name.startswith("temperature_soil"), name
    assert "temperature_air_max_2m" not in RULES or set(RULES["temperature_air_max_2m"]) == {"daily"}
    assert set(RULES["temperature_air_2m"]) == {"10_minutes", "hourly", "daily"}
    # the daily limit is a spike and no step: 25 K from one day to the next is a front, and no source says more
    daily = rule_for("temperature_air_mean_2m", "daily")
    assert daily is not None
    assert daily == rule_for("temperature_air_min_2m", "daily")
    assert daily.step is None


def _page_table() -> dict[tuple[str, str], tuple[str, str, str, str]]:
    """Read the table of limits of the page: `{(parameters, resolution): (spike, step, unit, source)}`."""
    text = PAGE.read_text(encoding="utf-8")
    block = text.split("<!-- rate-of-change:start -->")[1].split("<!-- rate-of-change:end -->")[0]
    rows = {}
    for line in block.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 6 or cells[0] in {"parameters", "---"}:
            continue
        names, resolution, spike, step, unit, source = cells
        rows[(names, resolution)] = (spike, step, unit, source)
    return rows


def _limit(value: float | None) -> str:
    return "-" if value is None else f"{value:g}"


def test_the_limits_on_the_page_are_the_table_of_the_code() -> None:
    """Every row of the page is a rule of the table, and no rule is missing: the page cannot drift from the code."""
    grouped: dict[tuple[str, StepRule], list[str]] = {}
    for name, by_resolution in RULES.items():
        for resolution, rule in by_resolution.items():
            grouped.setdefault((resolution, rule), []).append(name)
    expected = {
        (", ".join(f"`{name}`" for name in sorted(names)), resolution): (
            _limit(rule.spike),
            _limit(rule.step),
            rule.unit,
            rule.source,
        )
        for (resolution, rule), names in grouped.items()
    }
    assert _page_table() == expected


def test_the_page_says_what_the_check_does_not_judge() -> None:
    """The page names what `step` leaves out, with the measured reason for humidity and soil temperature."""
    text = PAGE.read_text(encoding="utf-8")
    section = text.split("### What `step` does not judge")[1].split("\n## ")[0]
    for word in ("relative humidity", "gusts", "soil temperature", "wind direction", "radiation"):
        assert word in section.lower(), word
    assert "1,463" in section
    assert "17,690" in section


@pytest.mark.parametrize(
    ("network", "resolution", "dataset", "canonical", "quiet", "jump"),
    [
        # a quantity the run table judges (`stuck`) and this table does not: the jump is no judgement of `step`
        ("dwd/observation", "daily", "climate_summary", "wind_gust_max", 5.0, 60.0),
        ("dwd/observation", "daily", "climate_summary", "pressure_air_site_mean", 1010.0, 960.0),
        ("dwd/observation", "daily", "precipitation_more", "snow_depth", 5.0, 400.0),
        ("dwd/observation", "daily", "climate_summary", "precipitation_amount", 1.0, 300.0),
    ],
)
def test_a_parameter_with_a_run_rule_and_no_jump_rule_is_not_judged_for_jumps_on_a_frame(
    network: str, resolution: str, dataset: str, canonical: str, quiet: float, jump: float
) -> None:
    """A jump of a parameter that has only a run rule is no verdict, in either mode, where a temperature's is."""
    assert run_rule_for(canonical, resolution) is not None
    assert rule_for(canonical, resolution) is None
    ds = _dataset(network, resolution, dataset)
    df = _frame(_name(ds, canonical), [quiet, quiet, jump, quiet, quiet], STEPS[resolution])
    for modes in (SOFT, Plausibility.model_validate("hard")):
        out = judged(df, network=network, dataset=ds, modes=modes)
        assert out.get_column("value").null_count() == 0
        assert "step" not in " ".join(out.get_column("quality_flags").drop_nulls().to_list())
    if dataset == "climate_summary":
        # while a jump of the daily mean temperature of the same dataset is a spike
        air = _frame(_name(ds, "temperature_air_mean_2m"), [5.0, 5.0, 35.0, 5.0, 5.0], STEPS[resolution])
        assert _flags_of(judged(air, network=network, dataset=ds)) == [None, None, "suspect:step", None, None]


def _flags_of(df: pl.DataFrame) -> list[str | None]:
    return df.get_column("quality_flags").to_list()


# --- the limits ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("network", "resolution", "dataset", "canonical", "base", "spike", "step"),
    [
        # an hour: 8 K as a spike (ISD, DMI), 20 K as a step (MADIS)
        ("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", 5.0, 8.0, 20.0),
        ("dwd/observation", "hourly", "moisture", "temperature_dew_point_2m", 5.0, 8.0, 20.0),
        # the pressure: 60 hPa for both (own data: Hurricane Irma changes 43 hPa an hour, the smallest slip 64)
        ("dwd/observation", "hourly", "pressure", "pressure_air_sea_level", 1010.0, 60.0, 60.0),
        ("dwd/observation", "hourly", "pressure", "pressure_air_site", 1010.0, 60.0, 60.0),
        # the mean wind speed: a spike of 10 m/s, a step of 15 m/s
        ("dwd/observation", "hourly", "wind", "wind_speed_mean", 25.0, 10.0, 15.0),
        # 10 minutes: the limits of the hour
        ("dwd/observation", "10_minutes", "temperature_air", "temperature_air_2m", 5.0, 8.0, 20.0),
        ("dwd/observation", "10_minutes", "temperature_air", "temperature_dew_point_2m", 5.0, 8.0, 20.0),
        ("dwd/observation", "10_minutes", "temperature_air", "pressure_air_site", 1010.0, 60.0, 60.0),
        ("dwd/observation", "10_minutes", "wind", "wind_speed_mean", 25.0, 10.0, 15.0),
        # a network that is not DWD: the same table
        ("metno/frost", "hourly", "data", "temperature_air_2m", 5.0, 8.0, 20.0),
    ],
)
def test_a_jump_is_flagged_beyond_the_limit_of_its_parameter_and_resolution(
    network: str, resolution: str, dataset: str, canonical: str, base: float, spike: float, step: float
) -> None:
    """A spike of exactly the limit is none, one more tenth is one, and only the middle reading is flagged.

    Likewise for a step: a change of the limit that holds is none, one tenth more flags the reading it arrives with.
    """
    at = lambda values: _flagged(network, resolution, dataset, canonical, values)  # noqa: E731
    quiet = [base] * 5
    for sign in (1.0, -1.0):
        assert at([*quiet, base + sign * spike, *quiet]) == [], f"a spike of {spike} is the limit"
        assert at([*quiet, base + sign * (spike + 0.1), *quiet]) == [5], f"a spike of {spike + 0.1} up or down"
        # a change that holds is no spike: it is a step, and one only where the step limit is passed
        assert at([*quiet, *[base + sign * (spike + 0.1)] * 5]) == ([] if spike + 0.1 <= step else [5])
        assert at([*quiet, *[base + sign * step] * 5]) == [], f"a step of {step} is the limit"
        assert at([*quiet, *[base + sign * (step + 0.1)] * 5]) == [5], f"a step of {step + 0.1}"


def test_the_jump_out_of_a_spike_is_no_step_but_a_second_jump_after_a_step_is() -> None:
    """The reading after a spike is the good one: it is not flagged for the change back, which is the spike's."""
    # up 30 K and back: the spike is the middle; the way back is not a step of the good reading
    assert _flagged(*AIR, [5.0, 5.0, 35.0, 5.0, 5.0]) == [2]
    # up 25 K and on up another 25 K: two steps, both flagged (no reading comes back)
    assert _flagged(*AIR, [5.0, 5.0, 30.0, 55.0, 55.0]) == [2, 3]
    # a zigzag is spikes all the way: every reading but the first and the last
    assert _flagged(*AIR, [5.0, 15.0, 5.0, 15.0, 5.0, 15.0]) == [1, 2, 3, 4]


def test_a_small_spike_does_not_hide_a_level_shift_after_it() -> None:
    """The reading after a spike is judged against the one before the spike: 10, 10, 19, -20 hides a shift."""
    # the 19 is the spike (up 9, down 39); the -20 is 30 K below the 10 before the spike, which is a step
    assert _flagged(*AIR, [10.0, 10.0, 19.0, -20.0, -21.0, -21.0]) == [2, 3]
    # back where the series was, or less than the limit from it, is no step
    assert _flagged(*AIR, [10.0, 10.0, 19.0, 10.0, 10.0]) == [2]
    assert _flagged(*AIR, [10.0, 10.0, 19.0, -9.0, -9.0, -9.0]) == [2]  # 19 K below the 10: under the limit of 20
    assert _flagged(*AIR, [10.0, 10.0, 19.0, -10.1, -10.1]) == [2, 3]  # 20.1 K below it
    # a missing hour before the 19 leaves it no spike (it has no predecessor), and the -20 is a step from it
    hour = dt.timedelta(hours=1)
    stamps = [START + hour * i for i in (0, 1, 3, 4, 5)]
    assert _flagged(*AIR, [10.0, 10.0, 19.0, -20.0, -20.0], stamps=stamps) == [3]


def test_adjacent_spikes_are_both_skipped_and_the_reading_after_them_is_judged_against_the_one_before_them() -> None:
    """10, 40, 0, 10 has two spikes in a row, and the good 10 is not compared with the 0 (or the 40)."""
    # the good 10 after two spikes is back where the series was: no step (it was flagged against the 0)
    assert _flagged(*AIR, [10.0, 40.0, 0.0, 10.0, 10.0]) == [1, 2]
    # the 35 after them is 25 K from the 10 before them, which is a step (it went unflagged against the 0)
    assert _flagged(*AIR, [10.0, 40.0, 0.0, 35.0, 35.0]) == [1, 2, 3]
    # three in a row
    assert _flagged(*AIR, [10.0, 40.0, 0.0, 40.0, 10.0, 10.0]) == [1, 2, 3]
    # Zugspitze, hourly mean wind, 1983-11-27 (m/s): 38.5 and 7.8 are the spikes, the 21.7 after them is not a step
    wind = ("dwd/observation", "hourly", "wind", "wind_speed_mean")
    assert _flagged(*wind, [20.6, 38.5, 7.8, 21.7, 23.2]) == [1, 2]
    # a missing hour between the spikes and the reading leaves that reading unjudged, as any other
    hour = dt.timedelta(hours=1)
    stamps = [START + hour * i for i in (0, 1, 2, 4, 5)]
    assert _flagged(*AIR, [10.0, 40.0, 0.0, 35.0, 35.0], stamps=stamps) == [1]
    # and a missing hour before the 0: the 40 has no successor to come back to and is a step, the 0 has no
    # predecessor, and the 35 after it is a step from the 0
    stamps = [START + hour * i for i in (0, 1, 3, 4, 5)]
    assert _flagged(*AIR, [10.0, 40.0, 0.0, 35.0, 35.0], stamps=stamps) == [1, 3]


def test_a_false_alarm_of_another_check_can_hide_a_spike_and_move_the_flag_to_the_good_reading() -> None:
    """40 h pinned at 0.0 are `stuck`'s: the 30.0 after them has no neighbour, and the good 0.2 after it is the step."""
    ds = _dataset(*AIR[:3])
    values = [*[0.0] * 50, 30.0, 0.2, 0.3, 0.2]
    out = judged(_frame(_name(ds, AIR[3]), values, STEPS["hourly"]), network=AIR[0], dataset=ds)
    flags = out.get_column("quality_flags").to_list()
    assert flags[:50] == ["suspect:stuck"] * 50
    # the consequence of the rule that a reading another check flagged is no neighbour, documented on the page
    assert flags[50:] == [None, "suspect:step", None, None]


def test_the_first_reading_is_never_flagged_and_the_last_is_no_spike() -> None:
    """The first reading of a series has no predecessor, the last no successor: the window-edge caveat of `stuck`."""
    assert _flagged(*AIR, [40.0, 5.0, 5.0, 5.0]) == [
        1
    ]  # the first is never flagged: the change arrives with the second
    assert _flagged(*AIR, [5.0, 5.0, 5.0, 40.0]) == [3]  # a step (the series ends on it), not a spike
    assert _flagged(*AIR, [5.0, 5.0, 5.0, 14.0]) == []  # a jump of 9 K is a spike or nothing, and it has no successor
    assert _flagged(*AIR, [14.0, 5.0, 5.0, 5.0]) == []


def test_a_spike_needs_the_opposite_direction_on_both_sides() -> None:
    """Two rises of 9 K in a row are no spike: nothing comes back."""
    assert _flagged(*AIR, [5.0, 5.0, 14.0, 23.0, 23.0, 23.0]) == []
    assert _flagged(*AIR, [5.0, 5.0, 14.0, 5.0, 5.0]) == [2]
    # one side only above the limit: the spike needs both
    assert _flagged(*AIR, [5.0, 5.0, 14.0, 9.0, 9.0]) == []


# --- gaps and nulls -----------------------------------------------------------------------------------------------


def test_a_null_between_two_readings_leaves_them_unjudged() -> None:
    """The check stands aside where the neighbour is missing: a null, a gap of a missing row."""
    assert _flagged(*AIR, [5.0, 5.0, None, 35.0, 35.0]) == []
    assert _flagged(*AIR, [5.0, 5.0, 14.0, None, 5.0, 5.0]) == []  # a spike needs both neighbours
    assert _flagged(*AIR, [5.0, 5.0, 35.0, None, 5.0, 5.0]) == [2]  # a step needs the one before only
    assert _flagged(*AIR, [5.0, None, 5.0, 40.0, 5.0]) == [3]  # the one that has neighbours is still judged


def test_a_missing_hour_leaves_the_readings_around_it_unjudged_and_a_shorter_interval_is_judged() -> None:
    """A pair further apart than the step is not judged; a pair closer than it is, with the limit of the step."""
    hour = dt.timedelta(hours=1)
    stamps = [START + hour * i for i in (0, 1, 2, 4, 5, 6)]  # the hour 3 is not in the series
    assert _flagged(*AIR, [5.0, 5.0, 5.0, 40.0, 40.0, 40.0], stamps=stamps) == []
    # a reading 30 minutes after the one before it: the change is judged with the limit of an hour
    stamps = [START, START + hour, START + hour * 2, START + hour * 2 + dt.timedelta(minutes=30), START + hour * 3]
    assert _flagged(*AIR, [5.0, 5.0, 5.0, 40.0, 40.0], stamps=stamps) == [3]


def test_the_daily_step_is_a_day() -> None:
    """A series of days is judged with the limit of the day; a missing day leaves a spike unjudged."""
    daily = ("dwd/observation", "daily", "climate_summary", "temperature_air_mean_2m")
    assert _flagged(*daily, [5.0, 5.0, 30.0, 5.0, 5.0]) == []  # 25 K is the limit
    assert _flagged(*daily, [5.0, 5.0, 30.1, 5.0, 5.0]) == [2]
    assert _flagged(*daily, [5.0, 5.0, 5.0, 40.0, 40.0, 40.0]) == []  # no step at a day
    day = dt.timedelta(days=1)
    stamps = [START + day * i for i in (0, 1, 2, 4, 5)]
    assert _flagged(*daily, [5.0, 5.0, 31.0, 5.0, 5.0], stamps=stamps) == []


# --- what counts as a neighbour -----------------------------------------------------------------------------------


def test_a_reading_the_range_rejects_is_no_neighbour_and_is_not_flagged_for_a_step() -> None:
    """61.5 degrees is outside the range: `range` judges it, and the good reading after it is not a step."""
    values = [5.0, 5.0, 61.5, 5.0, 5.0]
    assert _flagged(*AIR, values) == []
    ds = _dataset(*AIR[:3])
    out = judged(_frame(_name(ds, AIR[3]), values, STEPS["hourly"]), network=AIR[0], dataset=ds, modes=Plausibility())
    assert out.get_column("quality_flags").to_list() == [None, None, "rejected:range,raw:61.5", None, None]
    # two of them are no spike, and were a neighbour the 5.0 after them would be a step: it has none, and stands aside
    held = [5.0, 5.0, 61.5, 61.5, 5.0, 5.0]
    out = judged(_frame(_name(ds, AIR[3]), held, STEPS["hourly"]), network=AIR[0], dataset=ds, modes=Plausibility())
    assert out.get_column("quality_flags").to_list() == [None, None, *["rejected:range,raw:61.5"] * 2, None, None]
    # 14 K is in the range and a spike: judged
    assert _flagged(*AIR, [5.0, 5.0, 14.0, 5.0, 5.0]) == [2]


def test_a_reading_written_as_a_code_is_no_neighbour_and_not_judged() -> None:
    """A reading that carries the text of a source's code (`raw:-999`) is decided by the code, not by this check."""
    ds = _dataset(*AIR[:3])
    # two of them: a spike is the one case the code would not be told apart from, and the 5.0 after them is no step
    df = _frame(_name(ds, AIR[3]), [5.0, 5.0, 40.0, 40.0, 5.0, 5.0], STEPS["hourly"]).with_columns(
        quality_flags=pl.when(pl.col("value") > 30.0).then(pl.lit("raw:-999")).otherwise(None)
    )
    out = judged(df, network=AIR[0], dataset=ds)
    assert out.get_column("quality_flags").to_list() == [None, None, "raw:-999", "raw:-999", None, None]


def test_a_station_pressure_the_elevation_rejects_is_no_neighbour() -> None:
    """The check `elevation` judges 1093.3 hPa at 48 m; the step stands aside, and so for the reading after it."""
    ds = _dataset("dwd/observation", "hourly", "pressure")
    name = _name(ds, "pressure_air_site")
    df = _frame(name, [1010.0, 1010.0, 1093.3, 1010.0, 1010.0], STEPS["hourly"])
    out = judged(df, network="dwd/observation", dataset=ds, elevation=48.0)
    assert out.get_column("quality_flags").to_list() == [None, None, "rejected:elevation,raw:1093.3", None, None]
    # two of them are no spike: the 1010.0 after them is no step either, as they are no neighbour
    held = _frame(name, [1010.0, 1010.0, 1093.3, 1093.3, 1010.0, 1010.0], STEPS["hourly"])
    out = judged(held, network="dwd/observation", dataset=ds, elevation=48.0)
    assert out.get_column("quality_flags").to_list() == [None, None, *["rejected:elevation,raw:1093.3"] * 2, None, None]
    # a slip that is inside what the elevation allows (909.5 hPa at 48 m) is a spike the step finds
    slip = _frame(name, [1010.0, 1010.0, 909.5, 1010.0, 1010.0], STEPS["hourly"])
    out = judged(slip, network="dwd/observation", dataset=ds, elevation=48.0)
    assert out.get_column("quality_flags").to_list() == [None, None, "suspect:step", None, None]


def test_two_parameters_of_one_frame_are_judged_apart() -> None:
    """The last reading of the air and the first of the dew point are not neighbours."""
    ds = _dataset("dwd/observation", "hourly", "moisture")
    air, dew = _name(ds, "temperature_air_2m"), _name(ds, "temperature_dew_point_2m")
    # the dew point starts the hour after the air ends: next to each other in time, and still two series
    later = [START + dt.timedelta(hours=4 + i) for i in range(4)]
    frame = pl.concat([_frame(air, [5.0] * 4, STEPS["hourly"]), _frame(dew, [40.0] * 4, STEPS["hourly"], later)])
    out = judged(frame, network="dwd/observation", dataset=ds)
    assert out.get_column("quality_flags").null_count() == 8
    # a spike of the dew point is the dew point's (the air is above it, as the check `relations` wants)
    frame = pl.concat(
        [_frame(air, [15.0] * 5, STEPS["hourly"]), _frame(dew, [3.0, 3.0, 13.0, 3.0, 3.0], STEPS["hourly"])]
    )
    out = judged(frame, network="dwd/observation", dataset=ds)
    assert out.get_column("quality_flags").to_list() == [None] * 7 + ["suspect:step", None, None]


def test_the_order_of_the_frame_does_not_matter() -> None:
    """The check sorts the series by time: a frame in any order is judged as the series it is."""
    ds = _dataset(*AIR[:3])
    frame = _frame(_name(ds, AIR[3]), [5.0, 5.0, 40.0, 5.0, 5.0], STEPS["hourly"])
    shuffled = frame.sample(fraction=1.0, shuffle=True, seed=3)
    out = judged(shuffled, network=AIR[0], dataset=ds)
    flagged = out.filter(pl.col("quality_flags").is_not_null())
    assert flagged.get_column("timestamp").to_list() == [START + dt.timedelta(hours=2)]


# --- the modes ----------------------------------------------------------------------------------------------------


def test_a_jump_is_flagged_soft_and_rejected_hard_with_the_number_the_source_wrote() -> None:
    """Soft keeps the value and says `suspect:step`; hard nulls it and keeps the number as `rejected:step,raw:`."""
    ds = _dataset(*AIR[:3])
    df = _frame(_name(ds, AIR[3]), [5.0, 5.0, 14.2, 5.0, 5.0], STEPS["hourly"])
    soft = judged(df, network=AIR[0], dataset=ds, modes=SOFT)
    assert soft.get_column("quality_flags").to_list() == [None, None, "suspect:step", None, None]
    assert soft.get_column("value").to_list() == [5.0, 5.0, 14.2, 5.0, 5.0]
    hard = judged(df, network=AIR[0], dataset=ds, modes=HARD)
    assert hard.get_column("quality_flags").to_list() == [None, None, "rejected:step,raw:14.2", None, None]
    assert hard.get_column("value").to_list() == [5.0, 5.0, None, 5.0, 5.0]
    # soft is the default of the check, and the bare modes cover it
    assert Plausibility().mode("step") == "soft"
    assert Plausibility.model_validate("hard").mode("step") == "hard"
    assert Plausibility.model_validate("soft").mode("step") == "soft"


def test_a_stuck_run_is_judged_by_stuck_alone_and_the_reading_after_it_is_no_step() -> None:
    """A thermometer stuck at -40 for 30 hours is `stuck`'s: the 5.0 after it is no step of 45 K, bare hard or not."""
    ds = _dataset(*AIR[:3])
    values = [*[5.0 + 0.1 * (i % 7) for i in range(30)], *[-40.0] * 30, 5.0, 5.1, 5.2]
    df = _frame(_name(ds, AIR[3]), values, STEPS["hourly"])
    for modes in (Plausibility.model_validate("soft"), Plausibility.model_validate("hard"), SOFT):
        out = judged(df, network=AIR[0], dataset=ds, modes=modes)
        flags = out.get_column("quality_flags").to_list()
        assert flags[:30] == [None] * 30
        assert all(flag is not None and "stuck" in flag for flag in flags[30:60])
        assert "step" not in " ".join(flag for flag in flags if flag)
        assert flags[60:] == [None] * 3, modes
    # where the run is shorter than the limit it is no run: the jump into it is a step and the jump out of it another
    short = _frame(_name(ds, AIR[3]), [*values[:30], *[-40.0] * 5, 5.0, 5.1, 5.2], STEPS["hourly"])
    assert judged(short, network=AIR[0], dataset=ds).get_column("quality_flags").to_list()[30:36] == [
        "suspect:step",
        *[None] * 4,
        "suspect:step",
    ]


GHCN = ("noaa/ghcn", "hourly", "data", "temperature_air_2m")
#: the file's own flags of a value that the check `source` takes for erroneous, as GHCNh writes them (source 220)
ERRONEOUS = "3,source:220"


def _ghcn(values: list[float], flags: list[str | None]) -> tuple[pl.DataFrame, object]:
    ds = _dataset(*GHCN[:3])
    df = _frame(_name(ds, GHCN[3]), values, STEPS["hourly"]).with_columns(
        quality_flags=pl.Series(flags, dtype=pl.String)
    )
    return df, ds


@pytest.mark.parametrize("mode", ["soft", "hard"])
def test_a_reading_the_source_flags_is_no_neighbour_whatever_the_mode_of_that_check(mode: str) -> None:
    """GHCN hourly 5, 5, 40, 41, 5, 5 with 40 and 41 flagged erroneous: the good 5.0 after them is no step of 36 K."""
    df, ds = _ghcn([5.0, 5.0, 40.0, 41.0, 5.0, 5.0], [None, None, ERRONEOUS, ERRONEOUS, None, None])
    for modes in (Plausibility(source=mode), Plausibility.model_validate(mode)):
        out = judged(df, network=GHCN[0], dataset=ds, modes=modes)
        flags = out.get_column("quality_flags").to_list()
        assert flags[:2] == [None, None], (mode, flags)
        assert flags[4:] == [None, None], (mode, flags)
        assert "step" not in " ".join(flag for flag in flags if flag), (mode, flags)
        assert all("source" in flag for flag in flags[2:4]), (mode, flags)


def test_a_reading_a_bound_of_your_own_rejects_is_no_neighbour() -> None:
    """The check `limits` (the caller's bounds), soft or hard: 40 and 41 are out, the 5.0 after is no step."""
    ds = _dataset(*AIR[:3])
    df = _frame(_name(ds, AIR[3]), [5.0, 5.0, 40.0, 41.0, 5.0, 5.0], STEPS["hourly"])
    for modes in (Plausibility(limits="soft"), Plausibility(limits="hard"), Plausibility.model_validate("hard")):
        out = judged(df, network=AIR[0], dataset=ds, modes=modes, limits={"temperature_air_2m": (None, 30.0)})
        flags = out.get_column("quality_flags").to_list()
        assert flags[4:] == [None, None], flags
        assert "step" not in " ".join(flag for flag in flags if flag), flags


def test_a_reading_a_provider_rule_rejects_is_no_neighbour() -> None:
    """A `Beside` rule (`consistency`) and a `Bound` (`range`) judge 40 and 41: the 5.0 after is no step."""
    ds = _dataset("dwd/observation", "hourly", "moisture")
    air, dew = _name(ds, "temperature_air_2m"), _name(ds, "temperature_dew_point_2m")
    stamps = [START + dt.timedelta(hours=i) for i in range(6)]
    frame = pl.concat(
        [
            _frame(air, [5.0, 5.0, 40.0, 41.0, 5.0, 5.0], STEPS["hourly"], stamps),
            _frame(dew, [4.0, 4.0, 4.0, 4.0, 4.0, 4.0], STEPS["hourly"], stamps),
        ]
    )
    # the air that is more than 20 K above its own dew point is no reading, and says so: `consistency`
    rule = Beside("temperature_air_2m", "temperature_dew_point_2m", lambda target, partner: target - partner > 20.0)
    for modes in (SOFT, Plausibility.model_validate("hard"), Plausibility(consistency="soft")):
        out = judged(frame, network="dwd/observation", dataset=ds, modes=modes, rules=[rule])
        flags = out.filter(pl.col("parameter") == air).get_column("quality_flags").to_list()
        assert flags[4:] == [None, None], (modes, flags)
        assert all("consistency" in flag for flag in flags[2:4]), (modes, flags)
        assert "step" not in " ".join(flag for flag in flags if flag)
    bound = Bound(high=30.0, names=("temperature_air_2m",))
    out = judged(frame, network="dwd/observation", dataset=ds, rules=[bound])
    flags = out.filter(pl.col("parameter") == air).get_column("quality_flags").to_list()
    assert flags[4:] == [None, None], flags


def test_a_forecast_is_not_judged_for_jumps() -> None:
    """A model's output is no reading: the forecasts have no jump rule."""
    ds = _dataset("dwd/mosmix", "hourly", "large")
    df = _frame(_name(ds, "temperature_air_2m"), [278.15, 278.15, 308.15, 278.15, 278.15], STEPS["hourly"])
    out = judged(df, network="dwd/mosmix", dataset=ds)
    assert out.get_column("quality_flags").to_list() == [None] * 5


@pytest.mark.parametrize(
    ("network", "resolution", "dataset", "canonical"),
    [
        # no source gives a limit for these
        ("dwd/observation", "hourly", "temperature_air", "humidity_relative"),
        ("dwd/observation", "hourly", "wind", "wind_direction_mean"),
        ("dwd/observation", "hourly", "wind_extreme", "wind_gust_max"),
        ("dwd/observation", "10_minutes", "wind_extreme", "wind_gust_max"),
        ("dwd/observation", "hourly", "precipitation", "precipitation_amount"),
        ("dwd/observation", "hourly", "temperature_soil", "temperature_soil_0_05m"),
        ("dwd/observation", "daily", "climate_summary", "precipitation_amount"),
        # the extremes of an interval shorter than a day
        ("dwd/observation", "10_minutes", "temperature_extreme", "temperature_air_max_2m"),
        # a resolution the table has no limit for
        ("smhi/observation", "1_minute", "data", "temperature_air_2m"),
    ],
)
def test_what_no_source_gives_a_limit_for_is_not_judged(
    network: str, resolution: str, dataset: str, canonical: str
) -> None:
    """A quantity or a resolution that is not in the table has no jump, whatever the size."""
    assert rule_for(canonical, resolution) is None
    ds = _dataset(network, resolution, dataset)
    step = dt.timedelta(minutes=1) if resolution == "1_minute" else STEPS[resolution]
    df = _frame(_name(ds, canonical), [1.0, 1.0, 400.0, 1.0, 1.0, 1.0], step)
    out = judged(df, network=network, dataset=ds, modes=Plausibility.model_validate("hard"))
    assert "step" not in " ".join(out.get_column("quality_flags").drop_nulls().to_list())


@pytest.mark.parametrize(
    ("network", "resolution", "dataset", "canonical", "quiet", "jump", "step"),
    [
        # the road's quarter hour, the SYNOP reports of three hours (in kelvin) and the months of DWD
        ("dwd/road", "15_minutes", "data", "temperature_air", 5.0, 45.0, dt.timedelta(minutes=15)),
        ("meteofrance/synop", "subdaily", "data", "temperature_air_2m", 278.15, 318.15, dt.timedelta(hours=3)),
        ("dwd/observation", "monthly", "climate_summary", "temperature_air_mean_2m", 5.0, 45.0, dt.timedelta(days=30)),
    ],
)
def test_the_air_temperature_of_a_resolution_with_no_limit_is_not_judged_for_jumps_on_a_frame(
    network: str, resolution: str, dataset: str, canonical: str, quiet: float, jump: float, step: dt.timedelta
) -> None:
    """The air temperature at 15 minutes, in reports of 3 hours and by the month has a jump of 40 K and no verdict."""
    assert rule_for(canonical, resolution) is None
    ds = _dataset(network, resolution, dataset)
    df = _frame(_name(ds, canonical), [quiet, quiet, jump, quiet, quiet], step)
    out = judged(df, network=network, dataset=ds, modes=Plausibility.model_validate("hard"))
    flags = out.get_column("quality_flags").drop_nulls().to_list()
    assert "step" not in " ".join(flags), flags


@pytest.mark.parametrize(
    ("pressure", "wind", "flagged"),
    [
        # kPa and km/h, as ECCC writes them: 6.1 kPa are 61 hPa, 37 km/h are 10.3 m/s; 5.9 kPa and 35 km/h are under
        ([101.0, 101.0, 107.1, 101.0, 101.0], [20, 20, 57, 20, 20], True),
        ([101.0, 101.0, 106.9, 101.0, 101.0], [20, 20, 55, 20, 20], False),
    ],
)
def test_the_limits_hold_in_the_canonical_unit_whatever_the_unit_of_the_file_and_the_unit_asked_for(
    monkeypatch: pytest.MonkeyPatch,
    pressure: list[float],
    wind: list[int],
    flagged: bool,  # noqa: FBT001
) -> None:
    """ECCC writes the station pressure in kPa and the wind in km/h, and the caller asks for hPa and m/s: end to end."""
    import json  # noqa: PLC0415

    from tests.provider.value_stubs import _day, _settings, serve, stations_result  # noqa: PLC0415
    from wetterdienst import Options  # noqa: PLC0415
    from wetterdienst.provider.eccc.observation import EcccObservationRequest  # noqa: PLC0415
    from wetterdienst.provider.eccc.observation import api as eccc_api  # noqa: PLC0415

    rows = [
        {"UTC_DATE": f"2019-01-01T{hour:02d}:00:00", "STATION_PRESSURE": pressure[hour], "WIND_SPEED": wind[hour]}
        for hour in range(5)
    ]
    body = json.dumps({"features": [{"type": "Feature", "properties": row} for row in rows]}).encode()
    serve(monkeypatch, eccc_api, {"climate-hourly": body})
    request = EcccObservationRequest(
        parameters=[("hourly", "data", "pressure_air_site"), ("hourly", "data", "wind_speed")],
        start=_day(2019, 1, 1),
        end=_day(2019, 1, 2),
        settings=_settings(),
        options=Options(unit_targets={"pressure": "hectopascal", "speed": "meter_per_second"}),
    )
    result = stations_result(request, "hourly", "data", "51459", elevation=None)
    df = result.values().all().df.sort("parameter", "timestamp")
    expected = {
        "pressure_air_site": [1010.0, 1010.0, pressure[2] * 10, 1010.0, 1010.0],
        "wind_speed": [speed / 3.6 for speed in wind],
    }
    for name, values in expected.items():
        part = df.filter(pl.col("parameter") == name)
        assert part.get_column("value").to_list() == pytest.approx(values, abs=0.01), name
        marked = part.get_column("quality_flags").str.contains("suspect:step").fill_null(value=False).to_list()
        assert marked == [False, False, flagged, False, False], (name, marked)


def test_hurricane_irma_is_kept_at_the_limit_of_the_table_and_flagged_at_the_limit_of_dmi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """St-Barthelemy, 2017-09-06: 977.1, 936.0, 917.4, 960.4 hPa in four hours are good: the limit is 60 hPa.

    The minimum is 18.6 hPa below the hour before and 43.0 below the one after (no more than 41.1 hPa in an hour): the
    limit of the table keeps it, and DMI's certain error of 5 hPa would flag it, which is the reason it is not taken.
    """
    network, dataset = "meteofrance/observation", _dataset("meteofrance/observation", "hourly", "others")
    frame = _frame(_name(dataset, "pressure_air_site"), [990.9, 977.1, 936.0, 917.4, 960.4], STEPS["hourly"])
    out = judged(frame, network=network, dataset=dataset, elevation=3.0)
    assert out.get_column("quality_flags").to_list() == [None] * 5
    dmi = StepRule(5.0, 60.0, "DMI (Vejen et al. 2002, table 3.1)", "hPa")
    monkeypatch.setitem(RULES["pressure_air_site"], "hourly", dmi)
    monkeypatch.setattr(judge, "_PLANS", {})
    out = judged(frame, network=network, dataset=dataset, elevation=3.0)
    assert out.get_column("quality_flags").to_list() == [None, None, None, "suspect:step", None]


def _reference(
    readings: list[tuple[dt.datetime, float | None]], spike: float, step: float, interval: dt.timedelta
) -> set[int]:
    """Judge a series by the definition, reading by reading: the positions of the readings a step or a spike flags."""
    kept = sorted((stamp, value, i) for i, (stamp, value) in enumerate(readings) if value is not None)

    def close(earlier: int, later: int) -> bool:
        return dt.timedelta(0) < kept[later][0] - kept[earlier][0] <= interval

    def change(earlier: int, later: int) -> float:
        return round(kept[later][1] - kept[earlier][1], 6)

    spiked = set()
    for k in range(1, len(kept) - 1):
        if close(k - 1, k) and close(k, k + 1):
            down, up = change(k - 1, k), change(k, k + 1)
            if abs(down) > spike and abs(up) > spike and (down > 0) != (up > 0):
                spiked.add(k)
    flagged = {kept[k][2] for k in spiked}
    for k in range(1, len(kept)):
        if not close(k - 1, k):
            continue
        # a reading is judged against the last reading before it that is no spike (the one before it, or, past one
        # spike or several in a row, the one before them): a spike is the mistake, and the series is where it was
        before = k - 1
        while before in spiked:
            before -= 1
        if abs(change(before, k)) > step:
            flagged.add(kept[k][2])
    return flagged


@pytest.mark.parametrize("seed", range(12))
def test_the_check_is_the_definition_on_random_series_with_nulls_and_gaps(seed: int) -> None:
    """The vectorised check flags what a reading-by-reading judge of the definition flags, nulls and gaps included."""
    import random  # noqa: PLC0415

    rng = random.Random(seed)  # noqa: S311
    hour = dt.timedelta(hours=1)
    stamp, value = START, 5.0
    readings: list[tuple[dt.datetime, float | None]] = []
    for _ in range(400):
        # mostly the next hour, now and then a missing hour or a reading half an hour after the one before
        roll = rng.random()
        stamp += hour * 2 if roll < 0.05 else hour / 2 if roll > 0.95 else hour
        value = max(-30.0, min(40.0, value + rng.gauss(0, 0.3)))
        shown: float | None = value
        roll = rng.random()
        if roll < 0.06:
            shown = value + rng.choice([-1, 1]) * rng.uniform(5.0, 30.0)
        elif roll < 0.1:
            shown = None
        readings.append((stamp, None if shown is None else round(max(-40.0, min(50.0, shown)), 1)))
    # a level shift that holds, to have steps as well as spikes
    shift = rng.uniform(21.0, 25.0)
    readings = [
        (when, what if what is None or i <= 300 or what + shift > 55 else round(what + shift, 1))
        for i, (when, what) in enumerate(readings)
    ]
    ds = _dataset(*AIR[:3])
    df = _frame(_name(ds, AIR[3]), [what for _, what in readings], STEPS["hourly"], [when for when, _ in readings])
    out = judged(df, network=AIR[0], dataset=ds)
    found = {i for i, flag in enumerate(out.get_column("quality_flags").str.contains("step").to_list()) if flag}
    assert found == _reference(readings, 8.0, 20.0, hour)


def test_a_change_of_exactly_the_limit_is_none_whatever_the_noise_of_the_numbers() -> None:
    """16.1 minus 8.1 is 8.000000000000002 in floating point, and a spike of 8 K is no spike (the limit is exceeded)."""
    assert _flagged(*AIR, [8.1, 8.1, 16.1, 8.1, 8.1]) == []
    assert _flagged(*AIR, [12.2, 12.2, 32.2, 32.2]) == []
    assert _flagged(*AIR, [8.1, 8.1, 16.2, 8.1, 8.1]) == [2]
