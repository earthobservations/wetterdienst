# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The check `stuck` for every provider, in both modes (GH-3681).

The runs of one value that the table of `model/persistence.py` takes for a stopped sensor.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from pathlib import Path

import polars as pl
import pytest

from tests.provider.judging import judged
from wetterdienst import Wetterdienst
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.model.persistence import RULES, RunRule, exemption, rule_for
from wetterdienst.model.plausibility import Plausibility

UTC = dt.UTC
PAGE = Path(__file__).parent.parent.parent / "docs" / "data" / "plausibility.md"
SOFT = Plausibility()
HARD = Plausibility(stuck="hard")
STEPS = {"10_minutes": dt.timedelta(minutes=10), "hourly": dt.timedelta(hours=1), "daily": dt.timedelta(days=1)}
START = dt.datetime(2024, 1, 1, tzinfo=UTC)


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
    name: str,
    values: list[float | None],
    step: dt.timedelta,
    stamps: list[dt.datetime] | None = None,
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
) -> list[bool]:
    ds = _dataset(network, resolution, dataset)
    df = _frame(_name(ds, canonical), values, STEPS[resolution], stamps)
    out = judged(df, network=network, dataset=ds, modes=modes)
    return out.get_column("quality_flags").str.contains("stuck").fill_null(value=False).to_list()


def _runs_of(flags: list[bool]) -> list[int]:
    """Give the lengths of the stretches of flagged readings."""
    lengths, current = [], 0
    for flag in [*flags, False]:
        if flag:
            current += 1
        elif current:
            lengths.append(current)
            current = 0
    return lengths


def _varied(count: int, base: float, step: float = 0.1) -> list[float]:
    """Give readings that change at every reading, in steps of tenths unless said (a series that is no run)."""
    return [round(base + step * (i % 7), 4) for i in range(count)]


# --- the table is a table of sources ------------------------------------------------------------------------------


def test_the_table_names_canonical_parameters_and_the_resolutions_with_a_source() -> None:
    """Every rule is for a canonical parameter, at a resolution with a fixed step, and names its source."""
    resolutions = {resolution for by_resolution in RULES.values() for resolution in by_resolution}
    assert resolutions == {"10_minutes", "hourly", "daily"}
    for name, by_resolution in RULES.items():
        assert name in PARAMETERS, name
        for resolution, rule in by_resolution.items():
            assert rule.source.startswith(("HadISD", "ECA&D", "Durre et al.", "own derivation")), (name, resolution)
            assert rule.bands, (name, resolution)
            floors = [band.floors[0] for band in rule.bands]
            assert floors == sorted(floors), f"{name} {resolution}: the bands go from the lowest floor up"
            for band in rule.bands:
                for count in band.counts:
                    assert count is None or count >= 2, (name, resolution)
                counts = [count for count in band.counts if count is not None]
                assert counts == sorted(counts), f"{name} {resolution}: a coarser step is not judged more strictly"
                # the floor is in a unit, which the page names
                if not math.isinf(band.floors[0]):
                    assert rule.unit, (name, resolution)


def test_no_parameter_of_a_forecast_or_an_amount_of_an_interval_is_in_the_table() -> None:
    """The names are readings of an instant or a day, not the extremes of an interval or the sums of one."""
    assert not [name for name in RULES if re.search(r"(_last_\d+h|_yesterday|_multiday|_normal|_night|_day)$", name)]
    assert "precipitation_amount_last_1h" not in RULES
    assert "humidity_relative" not in RULES  # no source gives a limit for it
    assert "wind_direction_mean" not in RULES
    assert set(RULES["precipitation_amount"]) == {"daily"}


def _page_table() -> dict[tuple[str, str, int], tuple[tuple[str, str, str], str, str, str]]:
    """Read the table of limits of the page: `{(parameters, resolution): [(counts, readings that count, source)]}`."""
    text = PAGE.read_text(encoding="utf-8")
    block = text.split("<!-- persistence:start -->")[1].split("<!-- persistence:end -->")[0]
    rows = {}
    for line in block.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7 or cells[0] in {"parameters", "---"}:
            continue
        names, resolution, fine, half, whole, counts, source = cells
        rows.setdefault((names, resolution), []).append(((fine, half, whole), counts, source))
    return rows


def test_the_limits_on_the_page_are_the_table_of_the_code() -> None:
    """Every row of the page is a rule of the table, and no rule is missing: the page cannot drift from the code.

    A row has the counts, the readings that count and the source of the rule.
    """
    expected: dict[tuple[str, str], list[tuple[tuple[str, str, str], str, str]]] = {}
    grouped: dict[tuple[str, RunRule], list[str]] = {}
    for name, by_resolution in RULES.items():
        for resolution, rule in by_resolution.items():
            grouped.setdefault((resolution, rule), []).append(name)
    for (resolution, rule), names in grouped.items():
        key = (", ".join(f"`{name}`" for name in sorted(names)), resolution)
        for band in rule.bands:
            counts = tuple("-" if count is None else str(count) for count in band.counts)
            expected.setdefault(key, []).append((counts, exemption(band, rule.unit), rule.source))
    assert _page_table() == expected


# --- the limits ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("network", "resolution", "dataset", "canonical", "base", "step", "limit"),
    [
        # the temperature of an hour: 24 values at tenths, 30 at halves, 40 at whole degrees (HadISD)
        ("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", 5.0, 0.1, 24),
        ("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", 5.0, 0.5, 30),
        ("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", 5.0, 1.0, 40),
        # the dew point twice that
        ("dwd/observation", "hourly", "dew_point", "temperature_dew_point_2m", 5.0, 0.1, 48),
        ("dwd/observation", "hourly", "dew_point", "temperature_dew_point_2m", 5.0, 1.0, 80),
        # pressure: 72, 100 and 120 values
        ("dwd/observation", "hourly", "pressure", "pressure_air_sea_level", 1013.3, 0.1, 72),
        ("dwd/observation", "hourly", "pressure", "pressure_air_sea_level", 1013.3, 1.0, 120),
        # a network that is not DWD: the same table
        ("metno/frost", "hourly", "data", "temperature_air_2m", 5.0, 0.1, 24),
        ("noaa/ghcn", "hourly", "data", "pressure_air_sea_level", 1013.3, 0.1, 72),
        # the span of the hourly limit at 10 minutes (own derivation), a pressure's own 36
        ("dwd/observation", "10_minutes", "temperature_air", "temperature_air_2m", 5.0, 0.1, 144),
        ("dwd/observation", "10_minutes", "temperature_air", "pressure_air_site", 1003.3, 0.1, 36),
        # the day: 5 days of a temperature, of a pressure
        ("dwd/observation", "daily", "climate_summary", "temperature_air_mean_2m", 5.0, 0.1, 5),
        ("dwd/observation", "daily", "climate_summary", "temperature_air_max_2m", 5.0, 0.1, 5),
        ("dwd/observation", "daily", "climate_summary", "pressure_air_site_mean", 1003.3, 0.1, 5),
        ("dwd/observation", "daily", "climate_summary", "wind_speed_mean", 3.3, 0.1, 6),
        ("dwd/observation", "daily", "climate_summary", "wind_gust_max", 7.3, 0.1, 5),
        # the halves and wholes of the rows above that the first cases do not reach
        ("dwd/observation", "hourly", "pressure", "pressure_air_sea_level", 1013.3, 0.5, 100),
        ("dwd/observation", "hourly", "wind", "wind_speed_mean", 3.0, 0.1, 24),
        ("dwd/observation", "hourly", "wind", "wind_speed_mean", 3.0, 0.5, 30),
        ("dwd/observation", "10_minutes", "temperature_air", "temperature_air_2m", 5.0, 0.5, 180),
        ("dwd/observation", "10_minutes", "temperature_air", "temperature_air_2m", 5.0, 1.0, 240),
        ("dwd/observation", "10_minutes", "temperature_air", "temperature_dew_point_2m", 5.0, 0.1, 288),
        ("dwd/observation", "10_minutes", "wind", "wind_speed_mean", 3.0, 0.1, 144),
        ("dwd/observation", "daily", "climate_summary", "temperature_air_mean_2m", 5.0, 0.5, 20),
        ("dwd/observation", "daily", "climate_summary", "temperature_air_mean_2m", 5.0, 1.0, 20),
        ("dwd/observation", "daily", "climate_summary", "pressure_air_site_mean", 1003.0, 0.5, 21),
        ("dwd/observation", "daily", "climate_summary", "pressure_air_site_mean", 1003.0, 1.0, 28),
    ],
)
def test_a_run_is_stuck_at_the_limit_of_its_parameter_resolution_and_step(
    network: str, resolution: str, dataset: str, canonical: str, base: float, step: float, limit: int
) -> None:
    """One reading short of the limit is no run, the limit is, and what follows a change of value is none."""
    after = _varied(limit, base + 20.0, step) if step != 1.0 else [base + 20.0 + i for i in range(limit)]
    # the series is written at the step: readings that change by it, before and after, so the step is read from them
    around = [round(base + step * (i % 9), 4) for i in range(30)]
    for length, stuck in ((limit - 1, False), (limit, True)):
        values = [*around, *[base + 10 * step] * length, *around, *after]
        flags = _flagged(network, resolution, dataset, canonical, values)
        assert _runs_of(flags) == ([length] if stuck else []), f"{length} readings of one value"


def test_a_run_is_flagged_soft_and_rejected_hard_with_the_number_the_source_wrote() -> None:
    """Soft keeps the value and says `suspect:stuck`; hard nulls it and keeps the number as `rejected:stuck,raw:`."""
    ds = _dataset("dwd/observation", "hourly", "temperature_air")
    name = _name(ds, "temperature_air_2m")
    values = [*_varied(30, 1.0), *[7.3] * 24, *_varied(30, 1.0)]
    df = _frame(name, values, STEPS["hourly"])
    soft = judged(df, network="dwd/observation", dataset=ds, modes=SOFT)
    stuck = soft.slice(30, 24)
    assert stuck.get_column("quality_flags").to_list() == ["suspect:stuck"] * 24
    assert stuck.get_column("value").to_list() == [7.3] * 24
    assert soft.slice(0, 30).get_column("quality_flags").to_list() == [None] * 30
    hard = judged(df, network="dwd/observation", dataset=ds, modes=HARD)
    assert hard.slice(30, 24).get_column("quality_flags").to_list() == ["rejected:stuck,raw:7.3"] * 24
    assert hard.slice(30, 24).get_column("value").to_list() == [None] * 24
    assert hard.slice(0, 30).get_column("value").null_count() == 0
    # soft is the default of the check
    assert Plausibility().mode("stuck") == "soft"


def test_a_stuck_value_that_range_also_finds_carries_both_checks() -> None:
    """A run of 61 degrees is outside the range and stuck: both are told, in alphabetical order, by the soft mode."""
    ds = _dataset("dwd/observation", "hourly", "temperature_air")
    name = _name(ds, "temperature_air_2m")
    df = _frame(name, [*_varied(30, 1.0), *[61.5] * 24, *_varied(30, 1.0)], STEPS["hourly"])
    soft = judged(df, network="dwd/observation", dataset=ds, modes=Plausibility.model_validate("soft"))
    assert soft.slice(30, 24).get_column("quality_flags").to_list() == ["suspect:range+stuck"] * 24
    hard = judged(df, network="dwd/observation", dataset=ds, modes=Plausibility.model_validate("hard"))
    assert hard.slice(30, 24).get_column("quality_flags").to_list() == ["rejected:range+stuck,raw:61.5"] * 24


def test_the_step_of_a_series_is_read_from_its_year_not_from_a_few_finer_readings() -> None:
    """DWD's hourly temperature is in whole degrees until 1981 and in tenths after it.

    30 values of one is a run in the second era (24) and none in the first (40), and a few tenths among whole degrees
    do not make the first fine.
    """
    ds = _dataset("dwd/observation", "hourly", "moisture")
    name = _name(ds, "temperature_air_2m")
    whole = [float(i % 5) for i in range(200)]
    # 3 of 200 readings of a finer step among whole degrees
    whole[10], whole[50], whole[90] = 2.3, 3.7, 1.1
    old = [dt.datetime(1980, 1, 1, tzinfo=UTC) + dt.timedelta(hours=i) for i in range(200 + 30)]
    values = [*whole[:100], *[4.0] * 30, *whole[100:]]
    flags = _flagged("dwd/observation", "hourly", "moisture", "temperature_air_2m", values, stamps=old)
    assert _runs_of(flags) == []
    # the same readings in tenths, two years later
    new = [dt.datetime(1982, 1, 1, tzinfo=UTC) + dt.timedelta(hours=i) for i in range(200 + 30)]
    tenths = [round(i % 17 * 0.1, 1) for i in range(200)]
    values = [*tenths[:100], *[4.4] * 30, *tenths[100:]]
    assert _runs_of(_flagged("dwd/observation", "hourly", "moisture", "temperature_air_2m", values, stamps=new)) == [30]
    assert name  # the parameter is the dataset's own


def test_a_stuck_stretch_does_not_decide_the_step_of_the_series() -> None:
    """A whole number held for many hours is no evidence that the sensor writes whole numbers: it counts once."""
    values = [*_varied(40, 1.0), *[5.0] * 300, *_varied(40, 1.0)]
    assert _runs_of(_flagged("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", values)) == [300]
    # 24 hours of 5.0 in a series of tenths is a run, though 24 of 87 readings are whole numbers
    values = [*_varied(30, 1.0), *[5.0] * 24, *_varied(30, 1.0)]
    assert _runs_of(_flagged("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", values)) == [24]


def test_a_series_of_one_value_is_read_as_its_value_allows_unless_it_is_long() -> None:
    """One value that is no whole number cannot be whole degrees (24); a whole number is the lenient 40."""
    air = ("dwd/observation", "hourly", "temperature_air", "temperature_air_2m")
    assert _runs_of(_flagged(*air, [5.3] * 23)) == []
    assert _runs_of(_flagged(*air, [5.3] * 24)) == [24]
    assert _runs_of(_flagged(*air, [5.0] * 39)) == []
    assert _runs_of(_flagged(*air, [5.0] * 40)) == [40]


def test_a_year_of_one_value_in_many_readings_is_a_stopped_sensor_whatever_the_number() -> None:
    """A barometer that writes 1012.0 in blocks split by gaps, in a series of whole hPa, is read as fine (72)."""
    ds = _dataset("dwd/observation", "hourly", "pressure")
    # 20 blocks of 80 readings of 1012.0 (the run limit at whole hPa is 120, at tenths 72), each 6 hours apart
    constant = [START + dt.timedelta(hours=86 * block + i) for block in range(20) for i in range(80)]
    # the next year: whole hPa in short changing blocks
    changing = [dt.datetime(2025, 1, 1, tzinfo=UTC) + dt.timedelta(hours=i) for i in range(400)]
    values = [1012.0] * len(constant) + [float(1000 + (i // 5) % 9) for i in range(400)]
    df = _frame(_name(ds, "pressure_air_sea_level"), values, STEPS["hourly"], [*constant, *changing])
    out = judged(df, network="dwd/observation", dataset=ds)
    flagged = out.get_column("quality_flags").str.contains("stuck").fill_null(value=False).to_list()
    assert sum(flagged[: len(constant)]) == len(constant)
    assert sum(flagged[len(constant) :]) == 0


def test_a_year_with_fewer_than_ten_changes_takes_the_step_of_the_series() -> None:
    """Three changes of whole degrees in 2021 do not make the year whole in a series of tenths: 30 are a run."""
    tenths = [round(0.1 * ((i * 7) % 60), 1) for i in range(300)]
    values = [*tenths, 5.0, 6.0, 7.0, *[6.0] * 30]
    stamps = [
        *_hourly(dt.datetime(2020, 1, 1, tzinfo=UTC), 300),
        *_hourly(dt.datetime(2021, 1, 1, tzinfo=UTC), 33),
    ]
    flags = _flagged("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", values, stamps=stamps)
    assert _runs_of(flags) == [30]


# --- what is exempt and what ends a run ---------------------------------------------------------------------------


def test_a_calm_wind_is_no_run_but_a_wind_that_holds_one_speed_is() -> None:
    """Readings below 0.5 m/s are discounted (1 m/s at whole steps): a calm held for days is the weather."""
    around = _varied(30, 1.0)
    calm = [*around, *[0.0] * 200, *around]
    assert _runs_of(_flagged("dwd/observation", "hourly", "wind", "wind_speed_mean", calm)) == []
    nearly_calm = [*around, *[0.4] * 200, *around]
    assert _runs_of(_flagged("dwd/observation", "hourly", "wind", "wind_speed_mean", nearly_calm)) == []
    jammed = [*around, *[3.1] * 24, *around]
    assert _runs_of(_flagged("dwd/observation", "hourly", "wind", "wind_speed_mean", jammed)) == [24]
    # a series in whole m/s: 1.0 is the lowest that counts, and the count is 40
    whole = [float((i * 3) % 8 + 1) for i in range(60)]
    assert (
        _runs_of(_flagged("dwd/observation", "hourly", "wind", "wind_speed_mean", [*whole, *[5.0] * 39, *whole])) == []
    )
    assert _runs_of(
        _flagged("dwd/observation", "hourly", "wind", "wind_speed_mean", [*whole, *[5.0] * 40, *whole])
    ) == [40]


def test_the_rain_of_a_day_is_judged_from_one_millimetre_and_by_the_size_of_the_value() -> None:
    """10 days of one value above 1.0 mm, 5 days above 5.0 mm (ECA&D); a dry day and a trace are never a run."""
    wet = [0.0, 2.2, 0.0, 7.4, 0.3, 1.5, 12.0, 0.0, 3.1, 0.6] * 3

    def check(value: float, days: int) -> list[int]:
        return _runs_of(
            _flagged(
                "dwd/observation", "daily", "climate_summary", "precipitation_amount", [*wet, *[value] * days, *wet]
            )
        )

    assert check(0.0, 200) == []
    assert check(0.4, 100) == []
    assert check(1.0, 100) == []  # "more than 1.0 mm": 1.0 is exempt
    assert check(1.1, 9) == []
    assert check(1.1, 10) == [10]
    assert check(4.2, 10) == [10]
    assert check(5.0, 9) == []
    assert check(5.1, 4) == []
    assert check(5.1, 5) == [5]
    # a dry day between 7.0 mm falls ends the run
    assert (
        _runs_of(
            _flagged(
                "dwd/observation",
                "daily",
                "climate_summary",
                "precipitation_amount",
                [*wet, 7.0, 7.0, 7.0, 0.0, 7.0, 7.0, *wet],
            )
        )
        == []
    )


def test_the_snow_depth_of_a_day_is_judged_only_where_it_is_not_zero() -> None:
    """No snow is the normal state: 90 identical nonzero depths are a run, any number of zeros are none."""
    around = [0.0, 3.0, 5.0, 4.0, 8.0, 6.0, 2.0, 0.0] * 3
    for count, run in ((200, []), (89, []), (90, [90])):
        depth = 0.0 if count == 200 else 12.0
        flags = _flagged(
            "dwd/observation", "daily", "precipitation_more", "snow_depth", [*around, *[depth] * count, *around]
        )
        assert _runs_of(flags) == run, count
    assert _runs_of(
        _flagged("dwd/observation", "daily", "precipitation_more", "snow_depth_new", [*around, *[3.0] * 10, *around])
    ) == [10]
    assert (
        _runs_of(
            _flagged("dwd/observation", "daily", "precipitation_more", "snow_depth_new", [*around, *[3.0] * 9, *around])
        )
        == []
    )


def test_the_daily_wind_of_whole_metres_per_second_is_not_judged() -> None:
    """ECA&D's limits are for tenths: a gust written in whole m/s holds one value for days."""
    whole = [float(8 + (i * 5) % 9) for i in range(40)]
    flags = _flagged("dwd/observation", "daily", "climate_summary", "wind_gust_max", [*whole, *[13.0] * 8, *whole])
    assert _runs_of(flags) == []
    tenths = [round(8 + 0.1 * ((i * 37) % 90), 1) for i in range(120)]
    flags = _flagged("dwd/observation", "daily", "climate_summary", "wind_gust_max", [*tenths, *[13.3] * 5, *tenths])
    assert _runs_of(flags) == [5]
    # below 4 m/s a gust is a calm
    flags = _flagged("dwd/observation", "daily", "climate_summary", "wind_gust_max", [*tenths, *[3.3] * 50, *tenths])
    assert _runs_of(flags) == []


def test_a_gap_ends_a_run_and_the_nulls_inside_a_short_stretch_are_skipped() -> None:
    """Readings more than four intervals apart are two runs; a null between two equal readings is bridged."""
    values = [*_varied(30, 1.0), *[7.3] * 30, *_varied(30, 1.0)]
    stamps = [START + dt.timedelta(hours=i) for i in range(len(values))]
    # a day without readings in the middle of the stretch: two stretches of 15 readings
    shifted = [stamp + dt.timedelta(hours=24) if i >= 45 else stamp for i, stamp in enumerate(stamps)]
    assert (
        _runs_of(_flagged("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", values, stamps=shifted))
        == []
    )
    # a null reading inside the stretch is skipped, the value on both sides is one run
    holes = list(values)
    holes[40] = None
    flags = _flagged("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", holes)
    assert sum(flags) == 29
    assert flags[30:40] == [True] * 10
    assert flags[41:60] == [True] * 19


def test_a_value_that_ends_a_run_is_exempt_or_not_the_same() -> None:
    """A reading of another value ends a run: 20 and 20 readings of 7.3 around a 7.4 are two runs under the limit."""
    values = [*_varied(30, 1.0), *[7.3] * 20, 7.4, *[7.3] * 20, *_varied(30, 1.0)]
    assert _runs_of(_flagged("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", values)) == []


def _hourly(start: dt.datetime, count: int) -> list[dt.datetime]:
    return [start + dt.timedelta(hours=i) for i in range(count)]


def test_a_run_at_the_start_of_a_year_is_judged_by_the_step_of_the_series_not_of_one_change() -> None:
    """A year with a single change of value (here the start of a run) tells nothing of the step."""
    whole = [float((i * 3) % 7) for i in range(200)]
    values = [*[3.0] * 30, *whole]
    stamps = _hourly(dt.datetime(2020, 12, 31, 20, tzinfo=UTC), len(values))
    # 30 readings of one whole number in a series of whole degrees: under the 40 of that step, as mid-year
    assert (
        _runs_of(_flagged("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", values, stamps=stamps))
        == []
    )
    mid = _hourly(dt.datetime(2021, 6, 1, tzinfo=UTC), len(values))
    assert (
        _runs_of(_flagged("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", values, stamps=mid))
        == []
    )


def test_the_step_is_read_per_year_in_one_frame_that_spans_two_eras() -> None:
    """Whole degrees in 1980, tenths in 1982, one frame: 30 readings of one value are a run in 1982 and none in 1980."""
    whole = [float((i * 3) % 7) for i in range(300)]
    tenths = [round(0.1 * ((i * 7) % 60), 1) for i in range(300)]
    values = [*whole[:150], *[4.0] * 30, *whole[150:], *tenths[:150], *[4.4] * 30, *tenths[150:]]
    stamps = [
        *_hourly(dt.datetime(1980, 1, 1, tzinfo=UTC), 330),
        *_hourly(dt.datetime(1982, 1, 1, tzinfo=UTC), 330),
    ]
    flags = _flagged("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", values, stamps=stamps)
    assert _runs_of(flags) == [30]
    assert flags[:330] == [False] * 330
    assert flags[480:510] == [True] * 30


def test_a_run_across_a_year_boundary_has_the_step_of_the_year_it_starts_in() -> None:
    """18 readings in a year of whole degrees and 12 in a year of tenths are one run, judged by the first (40)."""
    whole = [float((i * 3) % 7) for i in range(150)]
    tenths = [round(0.1 * ((i * 7) % 60), 1) for i in range(150)]
    values = [*whole, *[4.0] * 30, *tenths]
    stamps = _hourly(dt.datetime(1981, 12, 25, tzinfo=UTC), len(values))
    assert stamps[150].year == 1981
    assert stamps[179].year == 1982
    flags = _flagged("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", values, stamps=stamps)
    assert _runs_of(flags) == []


def test_two_parameters_of_one_frame_never_make_one_run() -> None:
    """The last readings of one parameter and the first of the next are two runs under the limit, not one of 24."""
    ds = _dataset("dwd/observation", "hourly", "moisture")
    dew, air = _name(ds, "temperature_dew_point_2m"), _name(ds, "temperature_air_2m")
    stamps = _hourly(START, 100)
    dews = _frame(dew, [*_varied(70, 1.0), *[5.0] * 30], STEPS["hourly"], stamps)
    airs = _frame(air, [*[5.0] * 20, *_varied(80, 1.0)], STEPS["hourly"], stamps)
    out = judged(pl.concat([dews, airs]), network="dwd/observation", dataset=ds)
    # the dew point of 30 readings is under its 48, the air of 20 under its 24: none, and not one run of 50
    assert out.get_column("quality_flags").str.contains("stuck").fill_null(value=False).sum() == 0


def test_the_step_comes_from_where_the_values_change_not_from_every_reading() -> None:
    """Three long whole-number stretches in a series of tenths do not make it whole: a run of 30 is still one."""
    stretches = [reading for value in (5.0, 6.0, 7.0) for reading in (*_varied(30, 1.0), *[value] * 300)]
    values = [*stretches, *_varied(30, 1.0), *[7.3] * 30, *_varied(30, 1.0)]
    flags = _flagged("dwd/observation", "hourly", "temperature_air", "temperature_air_2m", values)
    # the three stretches and the 30 readings of 7.3 (24 < 30 < 40)
    assert _runs_of(flags) == [300, 300, 300, 30]


# --- where it runs ------------------------------------------------------------------------------------------------


def test_a_forecast_is_not_judged_for_runs() -> None:
    """A model holds one value over hours without a sensor failing: the forecasts have no run rule."""
    ds = _dataset("dwd/mosmix", "hourly", "large")
    name = _name(ds, "temperature_air_2m")
    df = _frame(name, [278.15] * 300, STEPS["hourly"])
    out = judged(df, network="dwd/mosmix", dataset=ds)
    assert out.get_column("quality_flags").to_list() == [None] * 300


@pytest.mark.parametrize(
    ("network", "resolution", "dataset", "canonical"),
    [
        # a resolution the table has no limit for
        ("smhi/observation", "1_minute", "data", "temperature_air_2m"),
        # a parameter no source gives a limit for
        ("dwd/observation", "hourly", "temperature_air", "humidity_relative"),
        ("dwd/observation", "hourly", "wind", "wind_direction_mean"),
        ("dwd/observation", "hourly", "precipitation", "precipitation_amount"),
        ("dwd/observation", "hourly", "wind_extreme", "wind_gust_max"),
        # the extremes of an interval shorter than a day
        ("dwd/observation", "10_minutes", "temperature_extreme", "temperature_air_max_2m"),
    ],
)
def test_what_no_source_gives_a_limit_for_is_not_judged(
    network: str, resolution: str, dataset: str, canonical: str
) -> None:
    """A quantity or a resolution that is not in the table has no run, whatever the length."""
    assert rule_for(canonical, resolution) is None
    ds = _dataset(network, resolution, dataset)
    name = _name(ds, canonical)
    df = _frame(
        name,
        [5.0] * 500,
        dt.timedelta(minutes=15) if resolution == "15_minutes" else STEPS.get(resolution, dt.timedelta(minutes=1)),
    )
    out = judged(df, network=network, dataset=ds, modes=Plausibility.model_validate("hard"))
    assert out.get_column("value").null_count() == 0, "nothing is nulled"
    assert "stuck" not in " ".join(out.get_column("quality_flags").drop_nulls().to_list())


def test_the_road_keeps_its_own_run_rule_and_the_table_adds_nothing_at_15_minutes() -> None:
    """The road run rule (24 readings, melting ice excepted) is a provider rule, and 15 minutes is not in the table."""
    from wetterdienst.model.judge import RUNS  # noqa: PLC0415

    assert "dwd/road" in RUNS
    assert all("15_minutes" not in by_resolution for by_resolution in RULES.values())
