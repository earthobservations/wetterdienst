# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The bounds a caller sets per parameter are a plausibility check of their own, in the unit of the answer (GH-3687)."""

from __future__ import annotations

import datetime as dt
import os

import polars as pl
import pytest
from pydantic import ValidationError

from tests.provider import value_stubs
from tests.provider.judging import judged
from wetterdienst import Options, Wetterdienst
from wetterdienst.exceptions import InvalidParameterError
from wetterdienst.model.judge import limits_in_canonical, plan_for
from wetterdienst.model.limits import read_limit_text
from wetterdienst.model.plausibility import Plausibility
from wetterdienst.model.unit import UnitConverter
from wetterdienst.ui.core import overlay_options

UTC = dt.UTC
DAILY = "daily/climate_summary"
TMK, RSK = "tmk", "rsk"


def _dataset(network: str, resolution: str, name: str) -> object:
    provider, api = network.split("/")
    return next(
        dataset
        for res in Wetterdienst.resolve(provider, api).metadata
        for dataset in res
        if (res.name, dataset.name) == (resolution, name)
    )


def _frame(rows: list[tuple[str, float | None]], flags: list[str | None] | None = None) -> pl.DataFrame:
    stamps = [dt.datetime(2024, 1, 1, tzinfo=UTC) + dt.timedelta(days=day) for day in range(len(rows))]
    return pl.DataFrame(
        {
            "parameter": [name for name, _ in rows],
            "timestamp": stamps,
            "value": [value for _, value in rows],
            "quality_flags": flags or [None] * len(rows),
        },
        schema_overrides={"value": pl.Float64, "quality_flags": pl.String},
    )


def _judge(
    rows: list[tuple[str, float | None]], flags: list[str | None] | None = None, **kwargs: object
) -> pl.DataFrame:
    dataset = _dataset("dwd/observation", "daily", "climate_summary")
    return judged(_frame(rows, flags), network="dwd/observation", dataset=dataset, **kwargs)  # ty: ignore[invalid-argument-type]


def test_limits_are_a_check_with_a_mode_hard_by_default() -> None:
    """The mode is the one of every check, in the options, the shorthand and the environment."""
    assert Plausibility().limits == "hard"
    assert Plausibility.model_validate("soft").limits == "soft"
    assert Options(plausibility={"limits": "soft"}).plausibility.limits == "soft"


def test_a_value_outside_the_bounds_is_rejected_and_keeps_the_number() -> None:
    """Hard: null, `rejected:limits,raw:<number>`. The bounds are included in what is plausible."""
    rows = [(TMK, -35.0), (TMK, -30.0), (TMK, 20.0), (TMK, 45.0), (TMK, 45.5)]
    out = _judge(rows, limits={"temperature_air_mean_2m": (-30, 45)})
    assert out.get_column("value").to_list() == [None, -30.0, 20.0, 45.0, None]
    assert out.get_column("quality_flags").to_list() == [
        "rejected:limits,raw:-35",
        None,
        None,
        None,
        "rejected:limits,raw:45.5",
    ]


def test_soft_keeps_the_value_and_flags_it() -> None:
    """Soft: the value stays, `suspect:limits`."""
    out = _judge(
        [(TMK, -35.0), (TMK, 20.0)],
        limits={"temperature_air_mean_2m": (-30, 45)},
        modes=Plausibility(limits="soft"),
    )
    assert out.get_column("value").to_list() == [-35.0, 20.0]
    assert out.get_column("quality_flags").to_list() == ["suspect:limits", None]


def test_either_end_may_be_left_out() -> None:
    """`None` is no bound at that end."""
    rows = [(RSK, 150.0), (RSK, 250.0), (RSK, 0.0)]
    out = _judge(rows, limits={"precipitation_amount": (None, 200)})
    assert out.get_column("quality_flags").to_list() == [None, "rejected:limits,raw:250", None]
    out = _judge(rows, limits={"precipitation_amount": (100, None)})
    assert out.get_column("quality_flags").to_list() == [None, None, "rejected:limits,raw:0"]


def test_a_parameter_without_a_bound_is_left_alone() -> None:
    """A bound for the temperature judges the rain of the same dataset by the table alone."""
    out = _judge([(RSK, 5000.0), (TMK, 80.0)], limits={"temperature_air_mean_2m": (-30, 45)})
    assert out.get_column("quality_flags").to_list() == ["rejected:range,raw:5000", "rejected:limits+range,raw:80"]


def test_limits_are_a_check_beside_the_range_and_both_verdicts_are_kept() -> None:
    """A value outside both carries both, joined with `+`; the mode of each check is its own."""
    rows = [(TMK, 80.0), (TMK, 50.0)]
    limits = {"temperature_air_mean_2m": (-30, 45)}
    both_hard = _judge(rows, limits=limits)
    assert both_hard.get_column("quality_flags").to_list() == ["rejected:limits+range,raw:80", "rejected:limits,raw:50"]
    limits_soft = _judge(rows, limits=limits, modes=Plausibility(limits="soft"))
    assert limits_soft.get_column("quality_flags").to_list() == ["rejected:range,raw:80", "suspect:limits"]
    both_soft = _judge(rows, limits=limits, modes=Plausibility.model_validate("soft"))
    assert both_soft.get_column("quality_flags").to_list() == ["suspect:limits+range", "suspect:limits"]
    range_soft = _judge(rows, limits=limits, modes=Plausibility(range="soft"))
    assert range_soft.get_column("quality_flags").to_list() == ["rejected:limits,raw:80", "rejected:limits,raw:50"]


def test_the_range_is_not_narrowed_or_widened_by_limits() -> None:
    """A bound wider than the table (100 degrees) does not let a value through that the range rejects."""
    out = _judge([(TMK, 80.0)], limits={"temperature_air_mean_2m": (-200, 200)})
    assert out.get_column("quality_flags").to_list() == ["rejected:range,raw:80"]


def test_a_code_of_the_source_decides_before_the_limits() -> None:
    """A reading that carries a `raw:` token is the source's code and is judged by nobody."""
    out = _judge([(TMK, 80.0)], ["raw:80"], limits={"temperature_air_mean_2m": (-30, 45)})
    assert out.get_column("quality_flags").to_list() == ["raw:80"]


def test_a_null_value_is_not_judged() -> None:
    """A missing reading is no number outside the bounds."""
    out = _judge([(TMK, None), (TMK, 20.0)], limits={"temperature_air_mean_2m": (-30, 45)})
    assert out.get_column("quality_flags").to_list() == [None, None]


@pytest.mark.parametrize(
    ("unit_targets", "limits"),
    [
        (None, (-30, 45)),
        ({"temperature": "degree_kelvin"}, (243.15, 318.15)),
        ({"temperature": "degree_fahrenheit"}, (-22, 113)),
    ],
)
def test_a_bound_is_in_the_unit_the_values_come_back_in(unit_targets: dict[str, str] | None, limits: tuple) -> None:
    """The same bounds, written in the unit of the request: 318.15 K is the 45 degrees the source wrote."""
    rows = [(TMK, -35.0), (TMK, -30.0), (TMK, 45.0), (TMK, 46.0)]
    out = _judge(rows, limits={"temperature_air_mean_2m": limits}, unit_targets=unit_targets)
    assert out.get_column("quality_flags").to_list() == [
        "rejected:limits,raw:-35",
        None,
        None,
        "rejected:limits,raw:46",
    ]


def test_a_fraction_is_judged_in_the_unit_the_request_asks_for() -> None:
    """The source writes percent; the answer is a decimal unless asked otherwise, and the bound is in that unit."""
    dataset = _dataset("dwd/observation", "hourly", "moisture")
    rows = [("rf_std", 55.0), ("rf_std", 95.0)]
    for unit_targets, limits in (
        (None, (0, 0.9)),
        ({"fraction": "decimal"}, (0, 0.9)),
        ({"fraction": "percent"}, (0, 90)),
    ):
        out = judged(
            _frame(rows),
            network="dwd/observation",
            dataset=dataset,
            limits={"humidity_relative": limits},
            unit_targets=unit_targets,
        )
        assert out.get_column("quality_flags").to_list() == [None, "rejected:limits,raw:95"], unit_targets


def test_without_unit_conversion_the_bounds_are_in_the_unit_of_the_source() -> None:
    """SYNOP writes the air in kelvin: with `convert_units` off a bound is in kelvin, and on it is in degrees."""
    dataset = _dataset("meteofrance/synop", "subdaily", "data")
    rows = [("t", 263.15), ("t", 293.15), ("t", 320.0)]

    def run(limits: tuple[float, float], *, convert_units: bool) -> list[str | None]:
        out = judged(
            _frame(rows),
            network="meteofrance/synop",
            dataset=dataset,
            limits={"temperature_air_2m": limits},
            convert_units=convert_units,
        )
        return out.get_column("quality_flags").to_list()

    assert run((270.0, 310.0), convert_units=False) == ["rejected:limits,raw:263.15", None, "rejected:limits,raw:320"]
    assert run((-3.0, 37.0), convert_units=True) == ["rejected:limits,raw:263.15", None, "rejected:limits,raw:320"]


def test_the_bound_of_a_dataset_beats_the_one_of_the_name_as_a_whole() -> None:
    """`resolution/dataset/parameter` holds for that dataset only, and wins over the name where both name it."""
    plan = plan_for("dwd/observation", _dataset("dwd/observation", "daily", "climate_summary"))
    monthly = _dataset("dwd/observation", "monthly", "climate_summary")
    converter = UnitConverter()
    limits = {"temperature_air_mean_2m": (-30, 45), "daily/climate_summary/temperature_air_mean_2m": (0, 10)}
    daily = _dataset("dwd/observation", "daily", "climate_summary")
    assert limits_in_canonical(plan, daily, limits, converter, convert_units=True)[TMK] == pytest.approx(
        (0.0, 10.0), abs=1e-6
    )
    assert limits_in_canonical(
        plan_for("dwd/observation", monthly), monthly, limits, converter, convert_units=True
    ) == {"mo_tt": pytest.approx((-30.0, 45.0), abs=1e-6)}
    # neither end of the name's pair is combined with the dataset's: its high end is not 45 where the dataset's is open
    open_ended = {"temperature_air_mean_2m": (-30, 45), "daily/climate_summary/temperature_air_mean_2m": (0, None)}
    daily_bounds = limits_in_canonical(plan, daily, open_ended, converter, convert_units=True)[TMK]
    assert daily_bounds == pytest.approx((0.0, float("inf")), abs=1e-6)


def test_a_dataset_is_named_as_a_request_names_it() -> None:
    """The source's own name of the dataset (`kl`), any casing and the separators of a request work."""
    daily = _dataset("dwd/observation", "daily", "climate_summary")
    plan = plan_for("dwd/observation", daily)
    for key in ("daily/kl/temperature_air_mean_2m", "Daily/KL/Temperature_Air_Mean_2m", "daily.kl.tmk"):
        bounds = limits_in_canonical(plan, daily, {key: (0, 10)}, UnitConverter(), convert_units=True)
        assert bounds == {TMK: pytest.approx((0.0, 10.0), abs=1e-6)}, key


def test_a_dataset_none_of_the_names_reaches_is_not_judged() -> None:
    """The limits of the options are for every request: a dataset without the parameter has none."""
    daily = _dataset("dwd/observation", "daily", "climate_summary")
    plan = plan_for("dwd/observation", daily)
    assert limits_in_canonical(plan, daily, {"wind_speed": (0, 10)}, UnitConverter(), convert_units=True) == {}
    assert limits_in_canonical(plan, daily, {}, UnitConverter(), convert_units=True) == {}
    assert (
        limits_in_canonical(
            plan,
            daily,
            {"monthly/climate_summary/temperature_air_mean_2m": (0, 1)},
            UnitConverter(),
            convert_units=True,
        )
        == {}
    )


def test_a_bound_that_is_no_value_of_the_unit_is_refused() -> None:
    """A negative Beaufort number has no speed in m/s (`x ** 1.5` is complex)."""
    dataset = _dataset("dwd/dmo", "hourly", "icon")
    plan = plan_for("dwd/dmo", dataset)
    converter = UnitConverter()
    converter.update_targets({"speed": "beaufort"})
    with pytest.raises(InvalidParameterError, match="no value of beaufort"):
        limits_in_canonical(plan, dataset, {"wind_speed": (-1, 5)}, converter, convert_units=True)


def test_such_a_bound_is_the_requests_error_before_anything_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A request with it is refused as it is built (a 400 for REST), not as a failure in the middle of a station."""
    monkeypatch.setattr(
        value_stubs,
        "_options",
        lambda drop_nulls: Options(
            drop_nulls=drop_nulls,
            unit_targets={"speed": "beaufort"},
            limits={"wind_speed_mean_last_10min": (-1, 5)},
        ),
    )
    read: list[object] = []
    monkeypatch.setattr(
        "wetterdienst.model.values.TimeseriesValues._collect_station_data",
        lambda *args, **_: read.append(args) or pytest.fail("a station was read"),
    )
    with pytest.raises(InvalidParameterError, match="no value of beaufort"):
        value_stubs._meteofrance_synop(monkeypatch)  # noqa: SLF001
    assert not read


@pytest.mark.parametrize("unit_targets", [None, {"fraction": "percent"}, {"fraction": "decimal"}])
def test_a_reading_on_a_bound_stays_in_any_unit(unit_targets: dict[str, str] | None) -> None:
    """Every tenth of a percent, as a low and as a high bound: the conversion adds no digit to be rejected."""
    dataset = _dataset("dwd/observation", "hourly", "moisture")
    scale = 1.0 if unit_targets == {"fraction": "percent"} else 0.01
    values = [tenth / 10 for tenth in range(0, 1001, 3)]
    for end in (0, 1):
        edges = [(value * scale, None) if end == 0 else (None, value * scale) for value in values]
        for value, edge in zip(values, edges, strict=True):
            out = judged(
                _frame([("rf_std", value)]),
                network="dwd/observation",
                dataset=dataset,
                limits={"humidity_relative": edge},
                unit_targets=unit_targets,
            )
            assert out.get_column("quality_flags").to_list() == [None], (unit_targets, value, edge)


def test_a_reading_on_a_bound_stays_in_the_unit_of_the_source() -> None:
    """SYNOP writes kelvin: with `convert_units` off a reading equal to its bound is not rejected."""
    dataset = _dataset("meteofrance/synop", "subdaily", "data")
    for hundredth in range(23315, 31311, 37):
        value = hundredth / 100
        for limits in ((value, None), (None, value)):
            out = judged(
                _frame([("t", value)]),
                network="meteofrance/synop",
                dataset=dataset,
                limits={"temperature_air_2m": limits},
                convert_units=False,
            )
            assert out.get_column("quality_flags").to_list() == [None], (value, limits)


def test_a_key_is_spelled_one_way_so_that_a_request_replaces_the_hosts_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    """`daily/kl/tmk`, any casing and the canonical triple are one key: the later replaces the earlier."""
    spelled = "daily/climate_summary/temperature_air_mean_2m"
    assert Options(limits={"DAILY/KL/TMK": (0, 1)}).limits == {spelled: (0.0, 1.0)}
    assert Options(limits={" Temperature_Air_Mean_2m ": (0, 1)}).limits == {"temperature_air_mean_2m": (0.0, 1.0)}
    assert Options(limits={"daily/kl/tmk": (0, 1), spelled: (2, 3)}).limits == {spelled: (2.0, 3.0)}
    monkeypatch.setenv("WD_TS_LIMITS", '{"daily/kl/tmk": [0, 10]}')
    assert Options(limits={spelled: (-5, 5)}).limits == {spelled: (-5.0, 5.0)}
    host = Options(limits={spelled: (0, 10), "humidity_relative": (0, 1)})
    laid = overlay_options(host, {"limits": {"Daily/KL/Tmk": (-1, 1)}})
    assert laid.limits == {"humidity_relative": (0.0, 1.0), spelled: (-1.0, 1.0)}


def test_a_key_keeps_the_scope_it_names() -> None:
    """A key of one network's own names is not rewritten to the canonical triple of thirteen networks (GH-3687)."""
    key = "hourly/ogd-smn/rre150h0"
    kept = next(iter(Options(limits={key: (0, 1)}).limits))
    assert kept == key
    plan_dataset = _dataset("aemet/observation", "hourly", "data")
    plan = plan_for("aemet/observation", plan_dataset)
    assert limits_in_canonical(plan, plan_dataset, {kept: (0, 1)}, UnitConverter(), convert_units=True) == {}


def test_of_two_keys_naming_one_parameter_the_later_wins() -> None:
    """Whatever the spelling: `hourly/data/p` after the canonical key replaces its bound."""
    dataset = _dataset("chmi/observation", "hourly", "data")
    plan = plan_for("chmi/observation", dataset)
    limits = {"hourly/data/pressure_air_site": (900, 1100), "hourly/data/p": (0, 1)}
    bounds = limits_in_canonical(plan, dataset, limits, UnitConverter(), convert_units=True)
    assert bounds["P"] == pytest.approx((0.0, 1.0), abs=1e-6)


def test_a_forecast_is_judged_soft_whatever_the_mode() -> None:
    """The rule of every check but `floor` (`Plausibility.for_forecast`): flagged, never nulled."""
    dataset = _dataset("dwd/dmo", "hourly", "icon")
    plan = plan_for("dwd/dmo", dataset)
    rr1 = next(name for name, c in plan.parameters.items() if c.name == "precipitation_amount_last_1h")
    df = _frame([(rr1, 5.0), (rr1, 0.3)])
    for modes in (None, Plausibility(limits="hard"), Plausibility.model_validate("hard")):
        out = judged(
            df, network="dwd/dmo", dataset=dataset, modes=modes, limits={"precipitation_amount_last_1h": (0, 1)}
        )
        assert out.get_column("value").to_list() == [5.0, 0.3]
        assert out.get_column("quality_flags").to_list() == ["suspect:limits", None]


# --- the options -----------------------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_ambient_options(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("WD_TS_"):
            monkeypatch.delenv(name)


def test_the_options_take_a_pair_as_a_tuple_a_list_or_json() -> None:
    """Either end may be null; the pairs are what Python, JSON and the environment write."""
    expected = {"temperature_air_mean_2m": (-30.0, 45.0), "precipitation_amount": (None, 200.0)}
    assert (
        Options(limits={"temperature_air_mean_2m": (-30, 45), "precipitation_amount": (None, 200)}).limits == expected
    )
    assert (
        Options(limits={"temperature_air_mean_2m": [-30, 45], "precipitation_amount": [None, 200]}).limits == expected
    )
    assert Options.model_validate_json(Options(limits=expected).model_dump_json()).limits == expected
    assert Options(limits=None).limits == {} == Options().limits


def test_the_environment_takes_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """`WD_TS_LIMITS` is a JSON object, and the nested form names one parameter."""
    monkeypatch.setenv("WD_TS_LIMITS", '{"temperature_air_mean_2m": [-30, 45], "precipitation_amount": [null, 200]}')
    assert Options().limits == {"temperature_air_mean_2m": (-30.0, 45.0), "precipitation_amount": (None, 200.0)}
    monkeypatch.delenv("WD_TS_LIMITS")
    monkeypatch.setenv("WD_TS_LIMITS__humidity_relative", "[0, 100]")
    assert Options().limits == {"humidity_relative": (0.0, 100.0)}
    monkeypatch.setenv("WD_TS_PLAUSIBILITY__LIMITS", "soft")
    assert Options().plausibility.limits == "soft"


def test_replace_sets_the_limits_wholesale() -> None:
    """As for the unit targets, `replace` replaces the mapping it is given; the surfaces merge it."""
    options = Options(limits={"temperature_air_mean_2m": (-30, 45)})
    assert options.replace(limits={"humidity_relative": (0, 100)}).limits == {"humidity_relative": (0.0, 100.0)}
    assert options.replace(shape="wide").limits == options.limits


@pytest.mark.parametrize(
    ("limits", "message"),
    [
        ({"temperature": (0, 1)}, "is no canonical parameter"),
        ({"precipitation_height": (0, 1)}, "now 'precipitation_amount'"),
        ({"daily/kl/nonsense": (0, 1)}, "no parameter of any dataset of any network"),
        ({"nonsense/kl/tmk": (0, 1)}, "no parameter of any dataset of any network"),
        ({"daily/kl": (0, 1)}, "not a whole dataset"),
        ({"Precipitation_Height": (0, 1)}, "now 'precipitation_amount'"),
    ],
)
def test_a_name_that_names_no_parameter_is_an_error(limits: dict, message: str) -> None:
    """A typo is not ignored, which would be indistinguishable from having set none."""
    with pytest.raises(ValidationError, match=message):
        Options(limits=limits)


@pytest.mark.parametrize(
    ("pair", "message"),
    [
        ((5, 1), "low .* is above high"),
        ((None, None), "both are null"),
        ((float("nan"), 1), "finite number"),
        ((1, float("inf")), "finite number"),
        ((float("-inf"), 1), "finite number"),
        (("a", 1), "valid number"),
        ((True, 5), "not a truth value"),
        ((1,), "Field required"),
        ((1, 2, 3), "too long|at most 2"),
    ],
)
def test_a_pair_that_is_no_limit_is_an_error(pair: tuple, message: str) -> None:
    """`low` may not exceed `high`, an end may be missing but not both, and a bound is a finite number."""
    with pytest.raises(ValidationError, match=message):
        Options(limits={"temperature_air_mean_2m": pair})


def test_equal_bounds_are_a_limit() -> None:
    """A pair of one value is allowed: it keeps that value alone."""
    assert Options(limits={"temperature_air_mean_2m": (1, 1)}).limits == {"temperature_air_mean_2m": (1.0, 1.0)}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("temperature_air_mean_2m=-30:45", ("temperature_air_mean_2m", (-30.0, 45.0))),
        ("precipitation_amount=:200", ("precipitation_amount", (None, 200.0))),
        ("precipitation_amount=0:", ("precipitation_amount", (0.0, None))),
        ("daily/kl/tmk=-1.5:2e1", ("daily/kl/tmk", (-1.5, 20.0))),
    ],
)
def test_the_command_line_text_is_name_low_high(text: str, expected: tuple) -> None:
    """`name=low:high`, an end left empty for none."""
    assert read_limit_text(text) == expected


@pytest.mark.parametrize("text", ["tmk", "tmk=1", "=1:2", "tmk=a:b", "tmk=nan:1", "tmk=1:inf"])
def test_a_text_that_is_no_name_low_high_is_refused(text: str) -> None:
    """Text without the colon, a name or numbers, and NaN or infinity, is refused."""
    with pytest.raises(ValueError, match=r"name=low:high|finite"):
        read_limit_text(text)


# --- through the values of a provider --------------------------------------------------------------------------------


def _monthly_rain(monkeypatch: pytest.MonkeyPatch, **options: object) -> pl.DataFrame:
    """Read the stub monthly rain of DMI (85.4 mm and 17,802 mm) with these options, the nulls kept."""
    monkeypatch.setattr(value_stubs, "_options", lambda drop_nulls: Options(drop_nulls=drop_nulls, **options))
    return value_stubs._dmi_monthly_rain(monkeypatch, drop_nulls=False)  # noqa: SLF001


def _tokens(flags: str | None) -> str:
    """Keep the tokens the library writes (`suspect:`, `rejected:`, `raw:`) of a reading's flags, not the source's."""
    ours = {"suspect", "rejected", "raw"}
    return ",".join(token for token in (flags or "").split(",") if token.split(":")[0] in ours)


def _flags_and_values(df: pl.DataFrame) -> list[tuple[str, float | None]]:
    """Give the plausibility tokens of the flags and the value of each reading in time order."""
    rows = df.sort("timestamp").select("quality_flags", "value").iter_rows()
    return [(_tokens(flags), value) for flags, value in rows]


def test_the_limits_reach_the_values_of_a_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """85.4 mm is above a bound of 50 mm: rejected beside the 17,802 mm the range rejects."""
    out = _monthly_rain(monkeypatch, limits={"precipitation_amount": (None, 50)})
    assert _flags_and_values(out) == [
        ("rejected:limits,raw:85.4", None),
        ("rejected:limits+range,raw:17802", None),
    ]


def test_the_limits_of_a_request_can_be_soft(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the mode of the check soft, 85.4 mm is kept and flagged; the range still rejects the 17,802 mm."""
    out = _monthly_rain(monkeypatch, limits={"precipitation_amount": (None, 80)}, plausibility={"limits": "soft"})
    assert _flags_and_values(out) == [("suspect:limits", 85.4), ("rejected:range,raw:17802", None)]


@pytest.mark.parametrize(
    ("options", "limit"),
    [
        ({}, 20.0),
        ({"unit_targets": {"temperature": "degree_kelvin"}}, 293.15),
        ({"unit_targets": {"temperature": "degree_fahrenheit"}}, 68.0),
        ({"convert_units": False}, 293.15),
    ],
    ids=["celsius", "kelvin", "fahrenheit", "the unit of the source"],
)
def test_the_bound_of_a_request_is_in_the_unit_it_asks_for(
    monkeypatch: pytest.MonkeyPatch, options: dict, limit: float
) -> None:
    """The 12-hour maximum of SYNOP is in kelvin: 303.75 K (30.6 C) is above 20 C in any unit, 287.85 K is not."""
    monkeypatch.setattr(
        value_stubs,
        "_options",
        lambda drop_nulls: Options(
            drop_nulls=drop_nulls, limits={"temperature_air_max_2m_last_12h": (None, limit)}, **options
        ),
    )
    out = value_stubs._meteofrance_synop(monkeypatch, drop_nulls=False)  # noqa: SLF001
    maxima = out.filter(pl.col("parameter") == "temperature_air_max_2m_last_12h").sort("timestamp")
    flagged = maxima.filter(pl.col("quality_flags").str.contains("rejected:limits"))
    assert [_tokens(flags) for flags in flagged.get_column("quality_flags")] == ["rejected:limits,raw:303.75"]
    assert flagged.get_column("value").to_list() == [None]
    # the other two maxima (287.85 K and 289.35 K) are kept, with no token of ours
    kept = maxima.filter(pl.col("value").is_not_null())
    assert kept.height == 2
    assert [_tokens(flags) for flags in kept.get_column("quality_flags")] == ["", ""]


def test_a_request_without_limits_is_judged_as_before(monkeypatch: pytest.MonkeyPatch) -> None:
    """No bounds, no check: the answer is the one of the range alone."""
    out = _monthly_rain(monkeypatch)
    assert _flags_and_values(out) == [("", 85.4), ("rejected:range,raw:17802", None)]
    assert "limits" not in "".join(out.get_column("quality_flags").to_list())
