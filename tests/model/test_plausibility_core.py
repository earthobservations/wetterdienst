# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The values core judges in canonical units, and holds what the readers held before (spike of GH-3676)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl
import pytest

from tests.provider.judging import judged
from wetterdienst import Wetterdienst
from wetterdienst.model.judge import SOURCE, Beside, Bound, StuckPeriod, judge, plan_for, to_canonical
from wetterdienst.model.plausibility import Plausibility
from wetterdienst.model.plausibility_ranges import SCOPE

BEFORE = json.loads((Path(__file__).parent / "data" / "ranges_before_the_move.json").read_text(encoding="utf-8"))
UTC = dt.UTC


def _datasets(network: str) -> dict[tuple[str, str], object]:
    provider, name = network.split("/")
    return {
        (resolution.name, dataset.name): dataset
        for resolution in Wetterdienst.resolve(provider, name).metadata
        for dataset in resolution
    }


def test_the_core_holds_every_network_to_the_bounds_its_reader_declared_and_to_no_more() -> None:
    """The table of the core, converted by the plan of each dataset, is the bounds of the readers before the move.

    `ranges_before_the_move.json` holds them in canonical units, read off the readers before their tables were taken
    out: the network, the dataset, the name of the source and the bounds. The table of the core says the same, per
    dataset, and judges no parameter that no reader judged.
    """
    expected = {(row["net"], row["res"], row["ds"], row["orig"]): (row["low"], row["high"]) for row in BEFORE}
    # the road's range of the humidity and its rule of a humidity under 1 % were two rules of `range`: one bound
    expected["dwd/road", "15_minutes", "data", "relativeHumidity"] = (0.01, 1.3)
    found = {}
    for network in SCOPE:
        for (resolution, name), dataset in _datasets(network).items():
            for original, bounds in plan_for(network, dataset).ranges.items():
                found[network, resolution, name, original] = bounds
    assert set(found) == set(expected)
    for key, (low, high) in expected.items():
        assert found[key] == pytest.approx((low, high), rel=1e-6, abs=1e-6), key


def _frame(rows: list[tuple[str, float | None]], flags: list[str | None] | None = None) -> pl.DataFrame:
    stamps = [dt.datetime(2024, 1, 1, tzinfo=UTC) + dt.timedelta(hours=hour) for hour in range(len(rows))]
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
    df = _frame([(p0, 1093.3), (p0, 1010.0)])
    hard = judged(df, network="dwd/observation", dataset=dataset, elevation=48.0, modes=Plausibility())
    assert hard.get_column("quality_flags").to_list() == ["rejected:elevation+range,raw:1093.3", None]
    soft = judged(df, network="dwd/observation", dataset=dataset, elevation=48.0, modes=Plausibility(range="soft"))
    assert soft.get_column("quality_flags").to_list() == ["rejected:elevation,raw:1093.3", None]
    every = judged(
        df, network="dwd/observation", dataset=dataset, elevation=48.0, modes=Plausibility.model_validate("soft")
    )
    assert every.get_column("quality_flags").to_list() == ["suspect:elevation+range", None]
    assert every.get_column("value").to_list() == [1093.3, 1010.0]


def test_a_value_a_source_code_decided_is_judged_by_nobody() -> None:
    """A reading that carries a `raw:` token already is the source's code, which decides first."""
    dataset = _datasets("dmi/observation")[("daily", "data")]
    df = _frame([("acc_precip", 0.0), ("acc_precip", 900.0)], ["manual,raw:-0.1", "manual"])
    out = judged(df, network="dmi/observation", dataset=dataset)
    assert out.get_column("quality_flags").to_list() == ["manual,raw:-0.1", "manual,rejected:range,raw:900"]


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
        df = _frame([(name, value) for value in values])
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
