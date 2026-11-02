# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The values core judges in canonical units, and holds what the readers held before (GH-3676)."""

from __future__ import annotations

import datetime as dt
from dataclasses import replace

import polars as pl
import pytest

from tests.provider.judging import judged
from wetterdienst import Wetterdienst
from wetterdienst.model.judge import SOURCE, Beside, Bound, StuckPeriod, judge, plan_for, to_canonical
from wetterdienst.model.plausibility import Plausibility

UTC = dt.UTC


def _datasets(network: str) -> dict[tuple[str, str], object]:
    provider, name = network.split("/")
    return {
        (resolution.name, dataset.name): dataset
        for resolution in Wetterdienst.resolve(provider, name).metadata
        for dataset in resolution
    }


def _frame(
    rows: list[tuple[str, float | None]],
    flags: list[str | None] | None = None,
    step: dt.timedelta = dt.timedelta(hours=1),
) -> pl.DataFrame:
    stamps = [dt.datetime(2024, 1, 1, tzinfo=UTC) + step * hour for hour in range(len(rows))]
    return pl.DataFrame(
        {
            "parameter": [name for name, _ in rows],
            "timestamp": stamps,
            "value": [value for _, value in rows],
            "quality_flags": flags or [None] * len(rows),
        },
        schema_overrides={"value": pl.Float64, "quality_flags": pl.String},
    )


def test_a_value_is_judged_in_the_canonical_unit_and_written_as_the_source_wrote_it() -> None:
    """183.0 K is below the bound of the SYNOP air temperature (-90 degrees); its token is the kelvin the file wrote."""
    dataset = _datasets("meteofrance/synop")[("subdaily", "data")]
    df = _frame([("t", 183.0), ("t", 183.15), ("t", 290.0)])
    out = judged(df, network="meteofrance/synop", dataset=dataset)
    assert out.get_column("quality_flags").to_list() == ["rejected:range,raw:183", None, None]
    assert out.get_column("value").to_list() == [None, 183.15, 290.0]


def test_the_checks_have_their_modes_and_a_rejected_value_carries_only_the_hard_checks() -> None:
    """A pressure that the range and the elevation both reject: hard says both, soft keeps it and says both."""
    dataset = _datasets("dwd/observation")[("hourly", "pressure")]
    plan = plan_for("dwd/observation", dataset)
    p0 = next(name for name, c in plan.parameters.items() if c.name == "pressure_air_site")
    df = _frame([(p0, 1150.0), (p0, 1010.0)])
    hard = judged(df, network="dwd/observation", dataset=dataset, elevation=48.0, modes=Plausibility())
    assert hard.get_column("quality_flags").to_list() == ["rejected:elevation+range,raw:1150", None]
    soft = judged(df, network="dwd/observation", dataset=dataset, elevation=48.0, modes=Plausibility(range="soft"))
    assert soft.get_column("quality_flags").to_list() == ["rejected:elevation,raw:1150", None]
    every = judged(
        df, network="dwd/observation", dataset=dataset, elevation=48.0, modes=Plausibility.model_validate("soft")
    )
    assert every.get_column("quality_flags").to_list() == ["suspect:elevation+range", None]
    assert every.get_column("value").to_list() == [1150.0, 1010.0]


def test_a_value_a_source_code_decided_is_judged_by_nobody() -> None:
    """A reading that carries a `raw:` token already is the source's code, which decides first."""
    dataset = _datasets("dmi/observation")[("daily", "data")]
    df = _frame([("acc_precip", 0.0), ("acc_precip", 2000.0)], ["manual,raw:-0.1", "manual"])
    out = judged(df, network="dmi/observation", dataset=dataset)
    assert out.get_column("quality_flags").to_list() == ["manual,raw:-0.1", "manual,rejected:range,raw:2000"]


def test_the_checks_of_a_provider_are_rules_the_core_applies_across_parameters() -> None:
    """A station without frost: no air below 0 degrees, and no humidity beside a dew point below it."""
    dataset = _datasets("meteofrance/observation")[("hourly", "others")]
    names = {parameter.name: parameter.name_original for parameter in dataset}
    humidity, dew_point = names["humidity_relative"], names["temperature_dew_point_2m"]
    rules = (
        Bound(low=0.0, unit_type="temperature"),
        Beside("humidity_relative", "temperature_dew_point_2m", lambda _, dew: dew.lt(0.0)),
    )
    df = _frame([(humidity, 4.0), (dew_point, -3.0)])
    df = df.with_columns(pl.lit(dt.datetime(2024, 1, 1, tzinfo=UTC)).alias("timestamp"))
    out = judged(df, network="meteofrance/observation", dataset=dataset, rules=rules)
    assert out.get_column("quality_flags").to_list() == ["rejected:consistency,raw:4", "rejected:range,raw:-3"]


def test_a_sensor_that_did_not_work_in_a_period_is_stuck() -> None:
    """The dated periods of a station are rules of the provider: soft by default, hard where asked."""
    dataset = _datasets("rmi/observation")[("daily", "data")]
    names = {parameter.name: parameter.name_original for parameter in dataset}
    sun = names["sunshine_duration"]
    rules = (StuckPeriod("sunshine_duration", dt.date(2024, 1, 1), dt.date(2024, 1, 1)),)
    df = _frame([(sun, 500.0), (sun, 300.0)]).with_columns(
        pl.Series("timestamp", [dt.datetime(2024, 1, 1, 12, tzinfo=UTC), dt.datetime(2024, 1, 3, tzinfo=UTC)])
    )
    soft = judged(df, network="rmi/observation", dataset=dataset, rules=rules)
    assert soft.get_column("quality_flags").to_list() == ["suspect:stuck", None]
    assert soft.get_column("value").to_list() == [500.0, 300.0]
    hard = judged(df, network="rmi/observation", dataset=dataset, rules=rules, modes=Plausibility(stuck="hard"))
    assert hard.get_column("quality_flags").to_list() == ["rejected:stuck,raw:500", None]
    assert hard.get_column("value").to_list() == [None, 300.0]


def test_a_floor_sets_the_value_to_zero_and_keeps_the_number() -> None:
    """The precipitation of a model a little below nothing is 0, `rejected:floor,raw:-0.02`; soft keeps it."""
    dataset = _datasets("dwd/dmo")[("hourly", "icon")]
    plan = plan_for("dwd/dmo", dataset)
    rr1 = next(name for name, c in plan.parameters.items() if c.name == "precipitation_amount_last_1h")
    df = _frame([(rr1, -0.02), (rr1, 0.3)])
    hard = judged(df, network="dwd/dmo", dataset=dataset)
    assert hard.get_column("value").to_list() == [0.0, 0.3]
    assert hard.get_column("quality_flags").to_list() == ["rejected:floor,raw:-0.02", None]
    soft = judged(df, network="dwd/dmo", dataset=dataset, modes=Plausibility(floor="soft"))
    assert soft.get_column("value").to_list() == [-0.02, 0.3]
    assert soft.get_column("quality_flags").to_list() == ["suspect:floor", None]


def test_a_frame_without_a_verdict_is_handed_back_as_it_is() -> None:
    """The common case does no work beyond the conversion: no token, no change, and the source's number is kept."""
    dataset = _datasets("meteofrance/synop")[("subdaily", "data")]
    plan = plan_for("meteofrance/synop", dataset)
    df = _frame([("t", 290.0), ("t", 291.0)]).with_columns(pl.col("value").alias(SOURCE))
    expr = to_canonical(plan)
    assert expr is not None
    out = judge(df.with_columns(expr.alias("value")), plan, Plausibility())
    assert out.get_column("quality_flags").to_list() == [None, None]
    assert out.get_column("value").to_list() == pytest.approx([16.85, 17.85])
    assert out.get_column(SOURCE).to_list() == [290.0, 291.0]


def test_a_judged_value_keeps_the_text_the_source_wrote() -> None:
    """`raw:` is the cell as the source wrote it (`-0.80`), not the number as short as it goes (`-0.8`)."""
    dataset = _datasets("dwd/observation")[("hourly", "urban_wind")]
    plan = plan_for("dwd/observation", dataset)
    speed = next(name for name, c in plan.parameters.items() if c.name == "wind_speed_mean")
    df = _frame([(speed, -0.8), (speed, 8.3)]).with_columns(pl.Series("source_text", [" -0.80", "8.30"]))
    out = judged(df, network="dwd/observation", dataset=dataset)
    assert out.get_column("quality_flags").to_list() == ["rejected:range,raw:-0.80", None]
    # a provider that gives no text has the number written as short as it goes
    assert judged(df.drop("source_text"), network="dwd/observation", dataset=dataset).get_column(
        "quality_flags"
    ).to_list() == ["rejected:range,raw:-0.8", None]


@pytest.mark.parametrize(
    ("resolution", "dataset_name", "limit"),
    [("hourly", "moisture", 72), ("daily", "climate_summary", 5), ("10_minutes", "temperature_air", 36)],
)
def test_a_barometer_that_holds_one_value_for_a_run_is_stuck(resolution: str, dataset_name: str, limit: int) -> None:
    """The limit is a resolution's: 72 hourly readings, 5 daily, 36 at 10 minutes; one reading short is no run."""
    dataset = _datasets("dwd/observation")[(resolution, dataset_name)]
    plan = plan_for("dwd/observation", dataset)
    name = next(n for n, c in plan.parameters.items() if c.name in {"pressure_air_site", "pressure_air_site_mean"})
    for length, flagged in ((limit - 1, False), (limit, True)):
        values = [1000.0] * length + [1000.1 + 0.1 * i for i in range(10)] + [990.0] * (limit - 1)
        step = {"10_minutes": dt.timedelta(minutes=10), "hourly": dt.timedelta(hours=1), "daily": dt.timedelta(days=1)}
        df = _frame([(name, value) for value in values], step=step[resolution])
        out = judged(df, network="dwd/observation", dataset=dataset)
        marked = out.get_column("quality_flags").to_list()
        assert marked[:length] == (["suspect:stuck"] * length if flagged else [None] * length)
        # the stretch that is one short of the limit later in the series is no run, and a varying one is none
        assert marked[length:] == [None] * (len(values) - length)


def test_a_constant_historical_file_is_flagged_beside_a_recent_one_that_varies(monkeypatch: pytest.MonkeyPatch) -> None:
    """The periods are one series when the core judges: the constant stretch of the historical archive is a run."""
    from io import BytesIO  # noqa: PLC0415

    from tests.provider import value_stubs  # noqa: PLC0415
    from wetterdienst import Options, Settings  # noqa: PLC0415
    from wetterdienst.metadata.period import Period  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import api as dwd_api  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    header = "STATIONS_ID;MESS_DATUM;QN_8;ABSF_STD;VP_STD;TF_STD;P_STD;TT_STD;RF_STD;TD_STD;eor\n"

    def product(start: dt.datetime, pressures: list[float]) -> bytes:
        rows = [
            f"   14006;{start + dt.timedelta(hours=hour):%Y%m%d%H};    3;   4.0;   5.0;  -0.5;"
            f"  {p:.1f};  -0.2;  90.0;  -0.9;eor"
            for hour, p in enumerate(pressures)
        ]
        return (header + "\n".join(rows) + "\n").encode("latin-1")

    files = {
        "historical": product(dt.datetime(2024, 1, 1, tzinfo=UTC), [995.9] * 200),
        "recent": product(dt.datetime(2024, 3, 1, tzinfo=UTC), [995.0 + 0.1 * (hour % 37) for hour in range(200)]),
    }
    monkeypatch.setattr(
        dwd_api,
        "create_file_list_for_climate_observations",
        lambda _station, _dataset, period, *_a, **_k: pl.Series([f"https://example.invalid/{period.value}"]),
    )
    monkeypatch.setattr(
        dwd_api,
        "download_climate_observations_data",
        lambda remote_files, *_a, **_k: [
            File(
                url="https://example.invalid/produkt.txt",
                content=BytesIO(files[remote_files[0].rsplit("/", 1)[1]]),
                status=200,
            )
        ],
    )
    request = DwdObservationRequest(
        parameters=[("hourly", "moisture", "pressure_air_site")],
        periods={Period.HISTORICAL, Period.RECENT},
        start=dt.datetime(2024, 1, 1, tzinfo=UTC),
        end=dt.datetime(2024, 12, 31, tzinfo=UTC),
        settings=Settings(cache_disable=True),
        options=Options(),
    )
    df = value_stubs.stations_result(request, "hourly", "moisture", "14006", elevation=133.0).values().all().df
    flagged = df.filter(pl.col("quality_flags").str.contains("suspect:stuck"))
    assert flagged.height == 200
    assert flagged.get_column("timestamp").max() < dt.datetime(2024, 3, 1, tzinfo=UTC)
    assert df.height == 400


def _moisture_pressure() -> tuple[object, str]:
    dataset = _datasets("dwd/observation")[("hourly", "moisture")]
    plan = plan_for("dwd/observation", dataset)
    return dataset, next(n for n, c in plan.parameters.items() if c.name == "pressure_air_site")


def _at(*hours: int) -> list[dt.datetime]:
    return [dt.datetime(2024, 1, 1, tzinfo=UTC) + dt.timedelta(hours=hour) for hour in hours]


def test_a_gap_of_more_than_four_intervals_ends_a_run_and_a_short_one_does_not() -> None:
    """Equal values either side of a month without readings are two stretches; either side of a short gap, one run."""
    dataset, name = _moisture_pressure()
    # 50 and 50 equal readings, a month of readings missing between them (they are null or not there at all)
    stamps = _at(*range(50), *range(24 * 30, 24 * 30 + 50))
    df = _frame([(name, 997.3)] * 100).with_columns(pl.Series("timestamp", stamps))
    out = judged(df, network="dwd/observation", dataset=dataset)
    assert out.get_column("quality_flags").to_list() == [None] * 100
    # the same month as rows of null (-999) between them: the nulls are skipped, and the gap ends the run all the same
    nulls = _at(*range(50, 24 * 30))
    month = pl.DataFrame({"parameter": name, "timestamp": nulls, "value": None, "quality_flags": "raw:-999"})
    with_nulls = pl.concat(
        [df.slice(0, 50), month.cast(dict(df.schema)), df.slice(50).select(df.columns)], how="vertical"
    )
    out = judged(with_nulls, network="dwd/observation", dataset=dataset)
    assert out.filter(pl.col("quality_flags").str.contains("stuck").fill_null(value=False)).is_empty()
    # three missing hours inside the stretch (a gap of 4 intervals) are bridged: 40 + 40 readings are one run of 80
    stamps = _at(*range(40), *range(43, 83))
    df = _frame([(name, 997.3)] * 80).with_columns(pl.Series("timestamp", stamps))
    out = judged(df, network="dwd/observation", dataset=dataset)
    assert out.get_column("quality_flags").to_list() == ["suspect:stuck"] * 80
    # one hour more (a gap of 5 intervals) ends it: 40 and 40 are two stretches under the limit
    stamps = _at(*range(40), *range(44, 84))
    df = _frame([(name, 997.3)] * 80).with_columns(pl.Series("timestamp", stamps))
    assert judged(df, network="dwd/observation", dataset=dataset).get_column("quality_flags").to_list() == [None] * 80


def test_a_request_class_that_subclasses_a_network_is_judged_as_the_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """`class My(DwdObservationRequest)` is still `dwd/observation`: a pressure of 1093.3 hPa is rejected."""
    from tests.provider import value_stubs  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    class MyRequest(DwdObservationRequest):
        pass

    assert Wetterdienst._network_of(MyRequest) == "dwd/observation"  # noqa: SLF001
    monkeypatch.setattr(value_stubs, "DwdObservationRequest", MyRequest)
    df = value_stubs._dwd_hourly_pressure_typo(monkeypatch, drop_nulls=False)  # noqa: SLF001
    rejected = df.filter(pl.col("quality_flags").str.contains("rejected:"))
    assert rejected.get_column("quality_flags").to_list() == ["1,rejected:elevation,raw:1093.3"]
    assert rejected.get_column("value").to_list() == [None]


def test_the_network_of_every_request_class_is_its_entry_of_the_registry() -> None:
    """The network a class serves is read off the registry by module and name, for every network of it."""
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if Wetterdienst.is_standalone(provider, network):
                continue
            assert Wetterdienst._network_of(Wetterdienst.resolve(provider, network)) == f"{provider}/{network}"  # noqa: SLF001
    assert Wetterdienst._network_of(object) == ""  # noqa: SLF001


def test_every_resolution_of_a_constant_run_has_a_step_to_bound_its_gap() -> None:
    """A limit for a resolution with no fixed step (a month, a year, sub-daily) would leave `constant_gap` None.

    The gap rule would then end no run, silently: the comparison with `None` is null. The limit is declared for a
    resolution with a step, or not at all, and the plan of every dataset that has one carries the gap.
    """
    from wetterdienst.metadata.resolution import reading_step  # noqa: PLC0415
    from wetterdienst.model.judge import CONSTANT_RUNS, RUN_GAP_FACTOR  # noqa: PLC0415

    for network, (_, limits) in CONSTANT_RUNS.items():
        provider, name = network.split("/")
        metadata = Wetterdienst.resolve(provider, name).metadata
        for resolution_name in limits:
            resolution = next(r for r in metadata if r.name == resolution_name)
            assert reading_step(resolution.value) is not None, f"{network} {resolution_name}: no fixed step"
            for dataset in resolution:
                plan = plan_for(network, dataset)
                if plan.constants:
                    assert plan.constant_gap == reading_step(resolution.value) * RUN_GAP_FACTOR


# --- a forecast is judged soft only (GH-3681) -------------------------------------------------------------------------


def _all_datasets() -> list[tuple[str, object]]:
    return [
        (f"{provider}/{network}", dataset)
        for provider, networks in Wetterdienst.registry.items()
        for network in networks
        if not Wetterdienst.is_standalone(provider, network)
        for resolution in Wetterdienst.resolve(provider, network).metadata
        for dataset in resolution
    ]


def test_a_network_is_a_forecast_by_the_kind_its_metadata_declares() -> None:
    """No list of networks: the plan of every dataset says `forecast` where, and only where, `kind` does."""
    kinds = {}
    for network, dataset in _all_datasets():
        provider, name = network.split("/")
        kind = Wetterdienst.resolve(provider, name).metadata.kind
        kinds[network] = kind
        assert plan_for(network, dataset).forecast is (kind == "forecast"), network
    assert {network for network, kind in kinds.items() if kind == "forecast"} >= {"dwd/mosmix", "dwd/dmo", "dwd/swsmos"}
    assert kinds["dwd/observation"] == "observation"


def test_a_forecast_is_judged_with_every_check_soft_but_the_one_that_corrects() -> None:
    """`hard`, given or default, is `soft` for a forecast; `floor` corrects and keeps the mode it was given."""
    assert Plausibility.model_validate("hard").for_forecast().model_dump() == {
        "range": "soft",
        "elevation": "soft",
        "stuck": "soft",
        "consistency": "soft",
        "floor": "hard",
    }
    assert Plausibility(floor="soft").for_forecast() == Plausibility.model_validate("soft")
    assert Plausibility().for_forecast().model_dump()["floor"] == "hard"


def test_a_forecast_keeps_the_value_a_hard_range_check_would_null() -> None:
    """ICON's 394.92 mm of rain in an hour (83827, run of 2026-10-31 12Z) is flagged and kept, in any mode."""
    dataset = _datasets("dwd/dmo")[("hourly", "icon")]
    plan = plan_for("dwd/dmo", dataset)
    rr1 = next(name for name, c in plan.parameters.items() if c.name == "precipitation_amount_last_1h")
    df = _frame([(rr1, 394.92), (rr1, 0.3)])
    for modes in (None, Plausibility(range="hard"), Plausibility.model_validate("hard")):
        out = judged(df, network="dwd/dmo", dataset=dataset, modes=modes)
        assert out.get_column("value").to_list() == [394.92, 0.3]
        assert out.get_column("quality_flags").to_list() == ["suspect:range", None]


def test_an_observation_in_hard_mode_still_nulls_the_same_value() -> None:
    """The rule is the network's kind: the same 394.92 mm in an hour at a DWD station is null."""
    dataset = _datasets("dwd/observation")[("hourly", "precipitation")]
    plan = plan_for("dwd/observation", dataset)
    rain = next(name for name, c in plan.parameters.items() if c.name == "precipitation_amount")
    out = judged(_frame([(rain, 394.92), (rain, 0.3)]), network="dwd/observation", dataset=dataset)
    assert out.get_column("value").to_list() == [None, 0.3]
    assert out.get_column("quality_flags").to_list() == ["rejected:range,raw:394.92", None]


def test_the_elevation_the_stuck_and_the_consistency_checks_are_soft_on_a_forecast() -> None:
    """The checks no forecast dataset of the library triggers still never null on a forecast plan."""
    dataset = _datasets("dwd/dmo")[("hourly", "icon")]
    plan = plan_for("dwd/dmo", dataset)
    names = {c.name: name for name, c in plan.parameters.items()}
    # the elevation: 1090 hPa at 48 m is 82.5 hPa above the standard atmosphere, which hard would null
    with_pressure = replace(plan, pressure=(names["pressure_air_sea_level"],))
    df = _frame([(names["pressure_air_sea_level"], 1090.0)]).with_columns(pl.col("value").alias(SOURCE))
    out = judge(df, with_pressure, Plausibility.model_validate("hard"), elevation=48.0)
    assert out.get_column("value").to_list() == [1090.0]
    assert out.get_column("quality_flags").to_list() == ["suspect:elevation"]
    # the same plan as an observation's would null it
    out = judge(df, replace(with_pressure, forecast=False), Plausibility.model_validate("hard"), elevation=48.0)
    assert out.get_column("quality_flags").to_list() == ["rejected:elevation,raw:1090"]
    # stuck, from a dated period, and consistency, from a relation of two readings of one timestamp
    air, dew = names["temperature_air_2m"], names["temperature_dew_point_2m"]
    rules = (
        StuckPeriod("temperature_air_2m", dt.date(2024, 1, 1), dt.date(2024, 1, 1)),
        Beside("temperature_dew_point_2m", "temperature_air_2m", lambda dew_point, air_: dew_point.gt(air_)),
    )
    df = _frame([(air, 5.0), (dew, 9.0)]).with_columns(pl.lit(dt.datetime(2024, 1, 1, tzinfo=UTC)).alias("timestamp"))
    df = df.with_columns(pl.col("value").alias(SOURCE))
    out = judge(df, plan, Plausibility.model_validate("hard"), rules)
    assert out.get_column("value").to_list() == [5.0, 9.0]
    assert out.get_column("quality_flags").to_list() == ["suspect:stuck", "suspect:consistency"]


def test_a_forecast_floor_still_sets_the_floor() -> None:
    """`floor` corrects and does not reject, so a forecast keeps its mode: 0.0 and the number as `raw:`."""
    dataset = _datasets("dwd/dmo")[("hourly", "icon")]
    plan = plan_for("dwd/dmo", dataset)
    rr1 = next(name for name, c in plan.parameters.items() if c.name == "precipitation_amount_last_1h")
    out = judged(_frame([(rr1, -0.02)]), network="dwd/dmo", dataset=dataset, modes=Plausibility.model_validate("hard"))
    assert out.get_column("value").to_list() == [0.0]
    assert out.get_column("quality_flags").to_list() == ["rejected:floor,raw:-0.02"]


def test_a_temperature_difference_is_held_to_no_temperature_bound() -> None:
    """The error of a temperature is no temperature, so no range of one catches it (GH-3688).

    An expected error of 0 K or of 40 K lies outside no bound of the air, and the rules that name the unit type
    `temperature` (France's frostless stations, `Bound(low=0.0, unit_type="temperature")`) do not select a difference.
    """
    from wetterdienst.metadata.parameter_table import PARAMETER_TABLE  # noqa: PLC0415
    from wetterdienst.model.plausibility_ranges import bounds_for  # noqa: PLC0415

    differences = {p.name for p in PARAMETER_TABLE if p.unit_type == "temperature_difference"}
    assert differences == {"error_absolute_temperature_air_2m", "error_absolute_temperature_dew_point_2m"}
    assert [name for name in differences if bounds_for(name) is not None] == []
    plan = plan_for("dwd/mosmix", _datasets("dwd/mosmix")[("hourly", "large")])
    assert {c.name for c in plan.parameters.values() if c.name in differences} == differences
    assert not [name for name, c in plan.parameters.items() if c.name in differences and name in plan.ranges]
    # the kelvin of the file is the canonical unit of a difference, so it is judged as written, where a reading is
    # converted to degrees Celsius and loses 273.15
    assert {c.canonical for c in plan.parameters.values() if c.name in differences} == {"degree_kelvin"}
    frame = pl.DataFrame({"parameter": ["e_ttt", "e_td", "ttt"], "value": [2.0, 0.5, 275.15]})
    converted = frame.with_columns(to_canonical(plan).alias("value"))
    assert converted["value"].to_list() == pytest.approx([2.0, 0.5, 2.0])
