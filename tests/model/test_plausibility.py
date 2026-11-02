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

from tests.provider import value_stubs
from wetterdienst import Options
from wetterdienst.model.plausibility import CHECKS, Plausibility, leave_out_suspect
from wetterdienst.options import resolve_options

if TYPE_CHECKING:
    from collections.abc import Iterator

HARD = Plausibility(stuck="hard")
SOFT = Plausibility(range="soft", elevation="soft", stuck="soft", consistency="soft", floor="soft", limits="soft")


# --- the model and the options ---------------------------------------------------------------------------------------


def test_the_checks_are_the_vocabulary_of_the_options() -> None:
    """The names are the vocabulary of the options, the tokens and the docs; `limits` is the caller's own (GH-3687)."""
    assert set(CHECKS) == {"range", "elevation", "stuck", "consistency", "floor", "limits"}
    assert set(Plausibility.model_fields) == set(CHECKS)


def test_every_check_is_hard_but_stuck_by_default() -> None:
    """Every check is hard but `stuck`, whose verdict depends on the request's window."""
    assert Plausibility().model_dump() == {
        "range": "hard",
        "elevation": "hard",
        "stuck": "soft",
        "consistency": "hard",
        "floor": "hard",
        "limits": "hard",
    }
    assert Options().plausibility == Plausibility() == Plausibility()


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
    # a text that is neither a mode nor a mapping is refused with the model's own message, naming the two modes
    for bad in ("off", "Soft", "none"):
        monkeypatch.setenv("WD_TS_PLAUSIBILITY", bad)
        with pytest.raises(ValidationError, match="one of soft, hard"):
            Options()


def test_the_all_key_is_no_part_of_a_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    """`__all__` is no check: a mapping given as options is refused and points to the bare-string shorthand."""
    for name in list(os.environ):
        if name.startswith("WD_TS_"):
            monkeypatch.delenv(name)
    mapping = {"__all__": "soft", "range": "hard"}
    for build in (
        lambda: Options(plausibility=mapping),
        lambda: Options().replace(plausibility=mapping),
        lambda: resolve_options({"plausibility": mapping}),
        lambda: Plausibility.model_validate(mapping),
    ):
        with pytest.raises(ValidationError, match="bare `soft` or `hard`"):
            build()


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


# --- every check, in both modes --------------------------------------------------------------------------------------


# --- the tokens ------------------------------------------------------------------------------------------------------


# --- a column cleaned by several calls -------------------------------------------------------------------------------


# --- what reaches the readers from the request -----------------------------------------------------------------------


def _monthly_rain(monkeypatch: pytest.MonkeyPatch, **options: object) -> pl.DataFrame:
    """Read the stub monthly rain of DMI, which holds 17,802 mm (no gauge reads it), with these options."""
    monkeypatch.setattr(value_stubs, "_options", lambda drop_nulls: Options(drop_nulls=drop_nulls, **options))
    return value_stubs._dmi_monthly_rain(monkeypatch, drop_nulls=False)  # noqa: SLF001


def test_the_options_of_a_request_reach_its_readers(monkeypatch: pytest.MonkeyPatch) -> None:
    """With `plausibility={"range": "soft"}` a request keeps the sum no gauge produced and flags it."""
    for name in list(os.environ):
        if name.startswith("WD_TS_"):
            monkeypatch.delenv(name)
    hard = _monthly_rain(monkeypatch)
    soft = _monthly_rain(monkeypatch, plausibility={"range": "soft"})
    for df in (hard, soft):
        assert df.filter(pl.col("quality_flags").str.contains("validity:true")).height > 0
    rejected = hard.filter(pl.col("value").is_null()).get_column("quality_flags").to_list()
    assert sorted(flags.split(",", 1)[1].split(",", 1)[1] for flags in rejected) == ["rejected:range,raw:17802"]
    kept = soft.filter(pl.col("quality_flags").str.contains("suspect:range"))
    assert sorted(kept.get_column("value").to_list()) == [17802.0]
    assert soft.filter(pl.col("value").is_null()).is_empty()


def test_drop_nulls_drops_a_rejected_value_and_keeps_a_suspect_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hard verdict is a null row, which `drop_nulls` drops as ever; a soft one has a value, so its row stays."""
    for name in list(os.environ):
        if name.startswith("WD_TS_"):
            monkeypatch.delenv(name)
    monkeypatch.setattr(value_stubs, "_options", lambda _: Options(drop_nulls=True))
    assert (
        not value_stubs._dmi_monthly_rain(monkeypatch, drop_nulls=True)  # noqa: SLF001
        .get_column("quality_flags")
        .str.contains("rejected:")
        .any()
    )
    monkeypatch.setattr(value_stubs, "_options", lambda _: Options(drop_nulls=True, plausibility={"range": "soft"}))
    kept = value_stubs._dmi_monthly_rain(monkeypatch, drop_nulls=True)  # noqa: SLF001
    assert sorted(kept.filter(pl.col("quality_flags").str.contains("suspect:range")).get_column("value").to_list()) == [
        17802.0
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
