# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The plausibility checks: a mode for each, and the tokens a soft or a hard verdict writes (GH-3676)."""

from __future__ import annotations

import datetime as dt
import os
from types import SimpleNamespace
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from tests.provider import value_stubs
from wetterdienst import Options
from wetterdienst.core.util import leave_out_suspect
from wetterdienst.model.plausibility import CHECKS, DEFAULTS, Plausibility, active, applying
from wetterdienst.model.quality_flags import (
    Floor,
    NoReading,
    OutOfRange,
    Sentinel,
    clear_sentinels,
    join_quality_flags,
    null_sentinels,
    station_pressure_range,
    unpivot_with_raw,
)
from wetterdienst.options import resolve_options

if TYPE_CHECKING:
    from collections.abc import Iterator

HARD = Plausibility(stuck="hard")
SOFT = Plausibility(range="soft", elevation="soft", stuck="soft", consistency="soft", floor="soft")


def _judge(
    values: list[float | None], *rules: Sentinel | OutOfRange | NoReading | Floor, plausibility: Plausibility
) -> tuple[list[float | None], list[str | None]]:
    """Give the values and the `quality_flags` a column of numbers gets from the rules, in a mode."""
    cleaned, raw = null_sentinels(pl.col("v"), *rules, text=False, plausibility=plausibility)
    out = pl.DataFrame({"v": values}, schema={"v": pl.Float64}).select(cleaned.alias("v"), join_quality_flags(raw=raw))
    return out.get_column("v").to_list(), out.get_column("quality_flags").to_list()


# --- the model and the options ---------------------------------------------------------------------------------------


def test_the_checks_are_the_five_the_issue_names() -> None:
    """The names are the vocabulary of the options, the tokens and the docs."""
    assert set(CHECKS) == {"range", "elevation", "stuck", "consistency", "floor"}
    assert set(Plausibility.model_fields) == set(CHECKS)


def test_every_check_is_hard_but_stuck_by_default() -> None:
    """The defaults reproduce what the library did, except `stuck`, whose verdict depends on the request's window."""
    assert Plausibility().model_dump() == {
        "range": "hard",
        "elevation": "hard",
        "stuck": "soft",
        "consistency": "hard",
        "floor": "hard",
    }
    assert Options().plausibility == Plausibility() == DEFAULTS


def test_a_mode_is_soft_or_hard_and_nothing_else() -> None:
    """There is no `off`: a soft check keeps the value, and the flag keeps the judgement visible."""
    for mode in ("off", "none", "", "SOFT"):
        with pytest.raises(ValidationError, match=r"plausibility\.range"):
            Options(plausibility={"range": mode})
    with pytest.raises(ValidationError, match=r"plausibility\.nonsense"):
        Options(plausibility={"nonsense": "soft"})
    with pytest.raises(ValueError, match="no plausibility check"):
        Plausibility().mode("nonsense")


def test_a_check_not_named_keeps_its_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Naming one check says nothing about the rest: not for a mapping given, `replace` or the environment."""
    for name in list(os.environ):
        if name.startswith("WD_TS_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("WD_TS_PLAUSIBILITY__FLOOR", "soft")
    assert Options().plausibility == Plausibility(floor="soft")
    options = resolve_options({"plausibility": {"range": "soft"}})
    assert options.plausibility == Plausibility(range="soft", floor="soft")
    assert options.replace(plausibility={"stuck": "hard"}).plausibility == Plausibility(
        range="soft", stuck="hard", floor="soft"
    )
    # and the options round-trip through their dump
    assert Options(**options.model_dump()) == options


@pytest.mark.parametrize("mode", ["soft", "hard"])
def test_a_bare_mode_is_that_mode_for_every_check(mode: str) -> None:
    """`Options(plausibility="soft")` is the same as listing all five checks (GH-3676)."""
    every = dict.fromkeys(CHECKS, mode)
    assert Options(plausibility=mode).plausibility == Plausibility(**every)
    assert Options(plausibility=mode) == Options(plausibility=every)
    assert Plausibility.model_validate(mode) == Plausibility(**every)
    assert resolve_options({"plausibility": mode}).plausibility == Plausibility(**every)
    assert Options().replace(plausibility=mode).plausibility == Plausibility(**every)
    # the shorthand sets `stuck` too, whatever it was
    assert Options(plausibility="hard").replace(plausibility="soft").plausibility.stuck == "soft"


def test_a_bare_mode_is_refused_when_it_is_none() -> None:
    """Only `soft` and `hard`: `off`, a blank and a wrong case are refused, naming the option."""
    for bad in ("off", "", "Soft", "none"):
        with pytest.raises(ValidationError, match="plausibility"):
            Options(plausibility=bad)
    with pytest.raises(ValidationError, match="plausibility"):
        resolve_options({"plausibility": "off"})
    with pytest.raises(ValidationError, match="plausibility"):
        Options().replace(plausibility="off")
    with pytest.raises(ValidationError, match="plausibility"):
        Options(plausibility=5)


def test_the_environment_takes_a_bare_mode_and_a_check_beside_it_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """`WD_TS_PLAUSIBILITY=soft` sets every check, and `WD_TS_PLAUSIBILITY__RANGE=hard` keeps that one hard."""
    for name in list(os.environ):
        if name.startswith("WD_TS_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("WD_TS_PLAUSIBILITY", "soft")
    assert Options().plausibility == Plausibility(**dict.fromkeys(CHECKS, "soft"))
    monkeypatch.setenv("WD_TS_PLAUSIBILITY__RANGE", "hard")
    assert Options().plausibility == Plausibility(**{**dict.fromkeys(CHECKS, "soft"), "range": "hard"})
    # an argument outranks the environment, as for every option
    assert Options(plausibility="hard").plausibility == Plausibility(**dict.fromkeys(CHECKS, "hard"))
    # a mapping given for the options is laid over the environment's modes, a check not named keeping its own
    options = resolve_options({"plausibility": {"floor": "hard"}})
    assert options.plausibility == Plausibility(**{**dict.fromkeys(CHECKS, "soft"), "range": "hard", "floor": "hard"})
    # a text that is neither a mode nor JSON is refused by the name of the option, as a malformed mapping is
    monkeypatch.setenv("WD_TS_PLAUSIBILITY", "off")
    with pytest.raises(SettingsError, match="plausibility"):
        Options()


def test_the_environment_takes_json_as_before(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mapping as JSON in `WD_TS_PLAUSIBILITY` still works beside the shorthand."""
    for name in list(os.environ):
        if name.startswith("WD_TS_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("WD_TS_PLAUSIBILITY", '{"range": "soft"}')
    assert Options().plausibility == Plausibility(range="soft")


def test_the_environment_names_a_check_by_its_nested_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """`WD_TS_PLAUSIBILITY__<CHECK>` sets one check, and a bad value is refused by the name of the option."""
    monkeypatch.setenv("WD_TS_PLAUSIBILITY__STUCK", "hard")
    assert Options().plausibility.stuck == "hard"
    monkeypatch.setenv("WD_TS_PLAUSIBILITY__STUCK", "off")
    with pytest.raises(ValidationError, match=r"plausibility\.stuck"):
        Options()


def test_the_plausibility_in_effect_is_the_requests_while_its_readers_run() -> None:
    """A reader called on its own applies the defaults, one called by a request the request's modes."""
    assert active() == DEFAULTS
    with applying(SOFT):
        assert active() == SOFT
        with applying(HARD):
            assert active() == HARD
        assert active() == SOFT
    assert active() == DEFAULTS


def test_null_sentinels_applies_the_plausibility_in_effect() -> None:
    """The readers pass no mode: `null_sentinels` reads it, as it builds its expressions, from the request in effect."""
    frame = pl.DataFrame({"v": [4021.0]})
    cleaned, _ = null_sentinels(pl.col("v"), OutOfRange(0.0, 10.0), text=False)
    assert frame.select(cleaned.alias("v")).get_column("v").to_list() == [None]
    with applying(SOFT):
        cleaned, _ = null_sentinels(pl.col("v"), OutOfRange(0.0, 10.0), text=False)
    assert frame.select(cleaned.alias("v")).get_column("v").to_list() == [4021.0]


# --- every check, in both modes --------------------------------------------------------------------------------------


def test_range_hard_nulls_the_value_and_soft_keeps_it() -> None:
    """4021 degrees is `rejected:range,raw:4021` and null, or `suspect:range` and 4021."""
    rule = OutOfRange(-90.0, 60.0)
    assert _judge([4021.0, 12.0], rule, plausibility=HARD) == ([None, 12.0], ["rejected:range,raw:4021", None])
    assert _judge([4021.0, 12.0], rule, plausibility=SOFT) == ([4021.0, 12.0], ["suspect:range", None])


def test_elevation_hard_nulls_the_value_and_soft_keeps_it() -> None:
    """909.5 hPa at a station at 48 m is `rejected:elevation,raw:909.5` and null, or `suspect:elevation` and kept."""
    rule = station_pressure_range(48.0)
    assert rule is not None
    assert _judge([909.5, 1009.6], rule, plausibility=HARD) == ([None, 1009.6], ["rejected:elevation,raw:909.5", None])
    assert _judge([909.5, 1009.6], rule, plausibility=SOFT) == ([909.5, 1009.6], ["suspect:elevation", None])


def test_stuck_hard_nulls_the_value_and_soft_keeps_it() -> None:
    """A sensor that held -25.00 is `rejected:stuck,raw:-25` and null, or `suspect:stuck` and kept; no blank is."""
    rule = NoReading(pl.col("v").lt(0) | pl.col("v").is_null())
    assert _judge([-25.0, 3.0, None], rule, plausibility=HARD) == (
        [None, 3.0, None],
        ["rejected:stuck,raw:-25", None, None],
    )
    assert _judge([-25.0, 3.0, None], rule, plausibility=SOFT) == ([-25.0, 3.0, None], ["suspect:stuck", None, None])


def test_consistency_hard_nulls_the_value_and_soft_keeps_it() -> None:
    """A road surface 30 K above the air is `rejected:consistency,raw:` and null, or `suspect:consistency` and kept."""
    rule = NoReading(pl.col("v").gt(300.0), check="consistency")
    assert _judge([338.75, 285.0], rule, plausibility=HARD) == (
        [None, 285.0],
        ["rejected:consistency,raw:338.75", None],
    )
    assert _judge([338.75, 285.0], rule, plausibility=SOFT) == ([338.75, 285.0], ["suspect:consistency", None])


def test_floor_hard_sets_the_floor_and_soft_keeps_the_value() -> None:
    """-0.1 mm is `rejected:floor,raw:-0.1` and 0.0 (not null), or `suspect:floor` and -0.1."""
    rule = Floor(0.0)
    assert _judge([-0.1, 0.4], rule, plausibility=HARD) == ([0.0, 0.4], ["rejected:floor,raw:-0.1", None])
    assert _judge([-0.1, 0.4], rule, plausibility=SOFT) == ([-0.1, 0.4], ["suspect:floor", None])


def test_one_mode_for_a_check_whatever_rule_belongs_to_it() -> None:
    """The mode is the check's: the `range` rules of every parameter and the `elevation` rule follow their own."""
    modes = Plausibility(range="soft", elevation="hard")
    pressure = station_pressure_range(48.0, where=pl.col("v") < 1000)
    assert pressure is not None
    values, flags = _judge([909.5, 4021.0], OutOfRange(0.0, 2000.0), pressure, plausibility=modes)
    assert flags == ["rejected:elevation,raw:909.5", "suspect:range"]
    assert values == [None, 4021.0]


def test_a_rule_refuses_a_name_that_is_no_check() -> None:
    """A rule names its check, and a name outside the five is a defect of the reader."""
    with pytest.raises(ValueError, match="no plausibility check"):
        OutOfRange(0.0, 1.0, check="nonsense")
    with pytest.raises(ValueError, match="no plausibility check"):
        NoReading(pl.lit(value=True), check="nonsense")


# --- the tokens ------------------------------------------------------------------------------------------------------


def test_the_verdict_stands_after_the_sources_flags_and_before_raw() -> None:
    """`3,zone:mez,suspect:range` for a kept value and `3,zone:mez,rejected:range,raw:4021` for a rejected one."""
    cleaned, raw = null_sentinels(pl.col("v"), OutOfRange(0.0, 10.0), text=False, plausibility=SOFT)
    soft = pl.DataFrame({"v": [4021.0]}).select(join_quality_flags(pl.lit("3"), zone=pl.lit("mez"), raw=raw))
    assert soft.get_column("quality_flags").to_list() == ["3,zone:mez,suspect:range"]
    cleaned, raw = null_sentinels(pl.col("v"), OutOfRange(0.0, 10.0), text=False, plausibility=HARD)
    hard = pl.DataFrame({"v": [4021.0]}).select(join_quality_flags(pl.lit("3"), zone=pl.lit("mez"), raw=raw))
    assert hard.get_column("quality_flags").to_list() == ["3,zone:mez,rejected:range,raw:4021"]
    del cleaned


def test_a_sentinel_keeps_only_raw_and_decides_before_any_judgement() -> None:
    """-999 is the source's code: `raw:-999` in both modes, though it is outside every range, and never `suspect`."""
    rules = (Sentinel("-999"), OutOfRange(-90.0, 60.0), NoReading(pl.lit(value=True)))
    for modes in (HARD, SOFT):
        values, flags = _judge([-999.0, 4021.0], *rules, plausibility=modes)
        assert values[0] is None
        assert flags[0] == "raw:-999"
    # the source's code, however it is listed against the judgements
    values, flags = _judge([-999.0], OutOfRange(-90.0, 60.0), Sentinel("-999"), plausibility=SOFT)
    assert (values, flags) == ([None], ["raw:-999"])


def test_a_documented_code_that_maps_to_a_value_has_no_mode() -> None:
    """A trace of -0.1 that the source means as 0.0 is a code: `raw:-0.1` in both modes, not a `floor` verdict."""
    for modes in (HARD, SOFT):
        values, flags = _judge(
            [-0.1, -0.5], Sentinel("-0.1", to=0.0), Floor(-1.0), OutOfRange(0.0, 10.0), plausibility=modes
        )
        assert values[0] == 0.0
        assert flags[0] == "raw:-0.1"


def test_several_checks_that_find_a_value_suspect_are_joined_with_a_plus() -> None:
    """`suspect:range+stuck`, in alphabetical order whatever the order of the rules."""
    rules = (NoReading(pl.lit(value=True)), OutOfRange(0.0, 10.0))
    assert _judge([4021.0], *rules, plausibility=SOFT) == ([4021.0], ["suspect:range+stuck"])
    assert _judge([4021.0], *reversed(rules), plausibility=SOFT) == ([4021.0], ["suspect:range+stuck"])


def test_several_checks_that_reject_a_value_are_joined_and_the_number_is_kept_once() -> None:
    """`rejected:range+stuck,raw:4021`."""
    rules = (NoReading(pl.lit(value=True)), OutOfRange(0.0, 10.0))
    assert _judge([4021.0], *rules, plausibility=HARD) == ([None], ["rejected:range+stuck,raw:4021"])


def test_a_rejected_value_carries_the_verdict_of_the_hard_checks_alone() -> None:
    """Where one check rejects and another finds suspect, the value is null and says why: `rejected:range,raw:`."""
    rules = (NoReading(pl.lit(value=True)), OutOfRange(0.0, 10.0))
    modes = Plausibility(range="hard", stuck="soft")
    assert _judge([4021.0], *rules, plausibility=modes) == ([None], ["rejected:range,raw:4021"])


def test_a_nan_outside_a_range_is_a_code_and_not_a_verdict() -> None:
    """A NaN is no number: null with its text in both modes, with no `suspect:` or `rejected:` token."""
    for modes in (HARD, SOFT):
        values, flags = _judge([float("nan"), 4021.0], OutOfRange(0.0, 10.0), plausibility=modes)
        assert values[0] is None
        assert flags[0] == "raw:NaN"


def test_a_text_column_is_judged_as_the_text_the_source_wrote() -> None:
    """A cell read as text keeps its text: `suspect:range` keeps `4021.0`, `rejected:range,raw:4021.0` nulls it."""
    for modes, expected in (
        (SOFT, (["4021.0", "12"], ["suspect:range", None])),
        (HARD, ([None, "12"], ["rejected:range,raw:4021.0", None])),
    ):
        cleaned, raw = null_sentinels(pl.col("v"), OutOfRange(-90.0, 60.0), plausibility=modes)
        out = pl.DataFrame({"v": [" 4021.0", "12"]}).select(cleaned.alias("v"), join_quality_flags(raw=raw))
        assert (out.get_column("v").to_list(), out.get_column("quality_flags").to_list()) == expected


# --- a column cleaned by several calls -------------------------------------------------------------------------------


def _wide(modes: Plausibility) -> pl.DataFrame:
    """Clean a wide column of text in two calls, as a reader does, and write its flags."""
    df = pl.DataFrame({"v": ["4021", "5", "5", "99", "-999"], "stuck": [True, True, False, False, False]})
    with applying(modes):
        df = clear_sentinels(df, ["v"], Sentinel("-999"))
        df = clear_sentinels(df, ["v"], OutOfRange(0.0, 50.0))
        df = clear_sentinels(df, ["v"], NoReading(pl.col("stuck")))
    return unpivot_with_raw(df.drop("stuck"), index=[]).select("value", join_quality_flags(raw=pl.col("raw")))


def test_later_calls_add_their_checks_to_a_soft_verdict() -> None:
    """A value found suspect by two calls is `suspect:range+stuck`, one by a single call has that call's check."""
    out = _wide(SOFT)
    assert out.get_column("value").to_list() == ["4021", "5", "5", "99", None]
    assert out.get_column("quality_flags").to_list() == [
        "suspect:range+stuck",
        "suspect:stuck",
        None,
        "suspect:range",
        "raw:-999",
    ]


def test_a_later_hard_check_replaces_the_suspicion_before_it() -> None:
    """A value a later call rejects is null and carries the rejection and its text: the suspicion is moot."""
    out = _wide(Plausibility(range="soft", stuck="hard"))
    assert out.get_column("value").to_list() == [None, None, "5", "99", None]
    assert out.get_column("quality_flags").to_list() == [
        "rejected:stuck,raw:4021",
        "rejected:stuck,raw:5",
        None,
        "suspect:range",
        "raw:-999",
    ]


def test_a_value_a_hard_check_nulled_is_not_judged_again() -> None:
    """A value null after the first call is no reading for the next, so it keeps the first verdict."""
    out = _wide(HARD)
    assert out.get_column("value").to_list() == [None, None, "5", None, None]
    assert out.get_column("quality_flags").to_list() == [
        "rejected:range,raw:4021",
        "rejected:stuck,raw:5",
        None,
        "rejected:range,raw:99",
        "raw:-999",
    ]


# --- what reaches the readers from the request -----------------------------------------------------------------------


def _annual_rain(monkeypatch: pytest.MonkeyPatch, **options: object) -> pl.DataFrame:
    """Read the stub annual rain of DMI, which holds 9574.3 and 6026.5 mm (no gauge reads them), with these options."""
    monkeypatch.setattr(value_stubs, "_options", lambda drop_nulls: Options(drop_nulls=drop_nulls, **options))
    return value_stubs._dmi_annual(monkeypatch, drop_nulls=False)  # noqa: SLF001


def test_the_options_of_a_request_reach_its_readers(monkeypatch: pytest.MonkeyPatch) -> None:
    """With `plausibility={"range": "soft"}` a request keeps the sum no gauge produced and flags it."""
    for name in list(os.environ):
        if name.startswith("WD_TS_"):
            monkeypatch.delenv(name)
    hard = _annual_rain(monkeypatch)
    soft = _annual_rain(monkeypatch, plausibility={"range": "soft"})
    for df in (hard, soft):
        assert df.filter(pl.col("quality_flags").str.contains("validity:true")).height > 0
    rejected = hard.filter(pl.col("value").is_null()).get_column("quality_flags").to_list()
    assert sorted(flags.split(",", 1)[1].split(",", 1)[1] for flags in rejected) == [
        "rejected:range,raw:6026.5",
        "rejected:range,raw:9574.3",
    ]
    kept = soft.filter(pl.col("quality_flags").str.contains("suspect:range"))
    assert sorted(kept.get_column("value").to_list()) == [6026.5, 9574.3]
    assert soft.filter(pl.col("value").is_null()).is_empty()


def test_drop_nulls_drops_a_rejected_value_and_keeps_a_suspect_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hard verdict is a null row, which `drop_nulls` drops as ever; a soft one has a value, so its row stays."""
    for name in list(os.environ):
        if name.startswith("WD_TS_"):
            monkeypatch.delenv(name)
    monkeypatch.setattr(value_stubs, "_options", lambda _: Options(drop_nulls=True))
    assert (
        not value_stubs._dmi_annual(monkeypatch, drop_nulls=True)  # noqa: SLF001
        .get_column("quality_flags")
        .str.contains("rejected:")
        .any()
    )
    monkeypatch.setattr(value_stubs, "_options", lambda _: Options(drop_nulls=True, plausibility={"range": "soft"}))
    kept = value_stubs._dmi_annual(monkeypatch, drop_nulls=True)  # noqa: SLF001
    assert sorted(kept.filter(pl.col("quality_flags").str.contains("suspect:range")).get_column("value").to_list()) == [
        6026.5,
        9574.3,
    ]


# --- interpolation and summary ---------------------------------------------------------------------------------------


def test_leave_out_suspect_nulls_the_value_of_a_suspect_reading_and_nothing_else() -> None:
    """The row stays, as a rejected one does; a `raw:` or a source's flag does not make a value suspect."""
    df = pl.DataFrame(
        {
            "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "quality_flags": [
                None,
                "3,suspect:range",
                "suspect:range+stuck",
                "3,raw:-999",
                "suspect",
                "3,rejected:range,raw:1",
            ],
        }
    )
    assert leave_out_suspect(df).get_column("value").to_list() == [1.0, None, None, 4.0, 5.0, 6.0]
    assert leave_out_suspect(df.drop("quality_flags")).equals(df.drop("quality_flags"))


@pytest.mark.parametrize("method", ["interpolate", "summarize"])
def test_interpolate_and_summarize_leave_out_a_suspect_value_whatever_the_mode(
    monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    """A soft verdict keeps 999.0 in a station's own values, and never lets it into a blend or a summary.

    Four stations around the point report 5.0 for three days, and the nearest of them 999.0 on the second day, flagged
    `suspect:range`. The same readings with no flag are the control: without the exclusion they would come through.
    """
    from wetterdienst.core.interpolate import get_interpolated_df  # noqa: PLC0415
    from wetterdienst.core.summarize import get_summarized_df  # noqa: PLC0415
    from wetterdienst.model.result import StationsFilter, StationsResult  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation.api import DwdObservationValues  # noqa: PLC0415

    latitude, longitude = 50.0, 8.9
    offsets = {"00001": (-0.03, -0.03), "00002": (-0.03, 0.03), "00003": (0.03, 0.03), "00004": (0.03, -0.03)}
    stations = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "station_id": station_id,
                "latitude": latitude + d_lat,
                "longitude": longitude + d_lon,
                "elevation": 100.0,
                "distance": 4.0 + index / 10,
            }
            for index, (station_id, (d_lat, d_lon)) in enumerate(offsets.items())
        ],
    )
    timestamps = [dt.datetime(2021, 2, day, tzinfo=ZoneInfo("UTC")) for day in (1, 2, 3)]
    flag = {"value": "suspect:range"}

    def _filter_by_distance(self: DwdObservationRequest, *_args: object, **_kwargs: object) -> StationsResult:
        return StationsResult(request=self, df=stations, _df_all=stations, _stations_filter=StationsFilter.BY_DISTANCE)

    def _query(_self: DwdObservationValues) -> Iterator[object]:
        for station_id in offsets:
            rows = []
            for timestamp in timestamps:
                outlier = station_id == "00001" and timestamp.day == 2
                rows.append(
                    {
                        "station_id": station_id,
                        "resolution": "daily",
                        "dataset": "climate_summary",
                        "parameter": "temperature_air_mean_2m",
                        "timestamp": timestamp,
                        "value": 999.0 if outlier else 5.0,
                        "quality_flags": flag["value"] if outlier else "10",
                    }
                )
            yield SimpleNamespace(df=pl.DataFrame(rows), data_updated_at=None)

    monkeypatch.setattr(DwdObservationRequest, "filter_by_distance", _filter_by_distance)
    monkeypatch.setattr(DwdObservationValues, "query", _query)
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start=timestamps[0],
        end=timestamps[-1],
        options=Options(plausibility={"range": "soft"}),
    )
    get_df = get_interpolated_df if method == "interpolate" else get_summarized_df
    assert set(get_df(request, latitude, longitude).get_column("value").drop_nulls().round(2)) == {5.0}
    # the control: no flag, no exclusion
    flag["value"] = "10"
    assert set(get_df(request, latitude, longitude).get_column("value").drop_nulls().round(2)) != {5.0}
