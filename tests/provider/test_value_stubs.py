# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A source's way of writing a missing value leaves no sentinel in the values a provider returns (GH-2615).

What the source wrote is not lost with it: the value carries the text as a `raw:` token in `quality_flags` (GH-2759).
"""

import re
from pathlib import Path

import polars as pl
import pytest

import wetterdienst
from tests.provider.physical_ranges import out_of_range
from tests.provider.value_stubs import NO_STUB, STUBS, ValueStub
from wetterdienst import Wetterdienst
from wetterdienst.metadata.parameter_table import PARAMETERS

PROVIDER_DIR = Path(wetterdienst.__file__).parent / "provider"

# the speed of a wind direction's own reading, by canonical name: the first of them a stub's output holds (GH-3222)
SPEED_OF_DIRECTION = {
    "wind_direction": ("wind_speed", "wind_speed_mean_last_10min", "wind_force_beaufort"),
    "wind_direction_mean": ("wind_speed_mean",),
    "wind_direction_mean_last_10min": ("wind_speed_mean_last_10min",),
    "wind_direction_mean_last_2min": ("wind_speed_mean_last_2min", "wind_speed"),
    "wind_direction_gust_max": ("wind_gust_max",),
}
# the rule of a no-direction code (`no_direction_code`, GH-3222): the stubs whose wind direction 0 is no bearing,
# and is null whatever the speed, with what makes it one. The source names it a code, or its data rules out a bearing.
# Every other direction follows the rule of a calm (`calm`).
NO_DIRECTION_CODE = {
    "dwd/observation hourly/wind_synop": 'a code: the sheet\'s "Windrichtung uml.,windstill DD=00", a variable or calm',
    "dwd/observation hourly/urban_wind": "no bearing: neither a calm nor north, the six 10 minutes spread (GH-2809)",
    "ipma/observation hourly/data": 'a code: the point 0 of eight, "no direction", where north is 1 or 9',
}


def _carried(df: pl.DataFrame, stub: ValueStub) -> list[tuple[str, float]]:
    """Give the sentinels of the stub that the output holds, as (parameter, value)."""
    parameter = df.get_column("parameter")
    return [
        (name, value)
        for name, value in stub.sentinels
        if not df.filter((parameter == name) & (pl.col("value") == value)).is_empty()
    ]


@pytest.mark.parametrize("stub", STUBS, ids=lambda stub: stub.provider)
def test_a_stub_source_leaves_no_sentinel_in_the_values(
    stub: ValueStub,
    monkeypatch: pytest.MonkeyPatch,
    physical_range_findings: list[str],
) -> None:
    """Serve the way a source writes a missing value through the provider's reader, and look for it in the output.

    A provider that is known to let it through is held to that: the sentinel has to be there, so that a fix fails
    this test and takes the `leak` out of the stub with it.
    """
    df = stub.build(monkeypatch)

    parameter, value = stub.reading
    arrived = df.filter(pl.col("parameter") == parameter).get_column("value").to_list()
    assert value in arrived, f"{stub.provider}: the reading {parameter}={value} did not arrive, got {arrived}"
    if stub.empty_at:
        at = df.filter(pl.col("timestamp") == stub.empty_at)
        assert at.is_empty(), f"{stub.provider}: {at.height} values at {stub.empty_at}, where the source has none"
    carried = _carried(df, stub)
    # what is outside the range of its parameter, less the sentinels the stub names: a number that is neither
    # a reading nor one of them is a sentinel the stub does not know of yet
    outside = out_of_range(df)
    unnamed = [
        (str(row["parameter"]), row["value"])
        for row in outside.to_dicts()
        if (str(row["parameter"]), row["value"]) not in stub.sentinels
    ]
    assert unnamed == [], f"{stub.provider}: values outside the range of their parameter, not named: {unnamed[:5]}"
    if stub.leak:
        # all of them: a fix that is only partial changes what the stub holds, and the stub is to say so
        assert carried == list(stub.sentinels), (
            f"{stub.provider}: {stub.leak} is fixed for {sorted(set(stub.sentinels) - set(carried))}, "
            "remove it from `sentinels`, and `leak` when none is left"
        )
        # the hook has recorded whatever of the leak lies outside a range, and the stub has accounted for it above
        physical_range_findings.clear()
        return
    assert carried == [], f"{stub.provider}: the sentinel {carried} reached the output"


@pytest.mark.parametrize("stub", STUBS, ids=lambda stub: stub.provider)
def test_a_sentinel_mapped_away_keeps_the_text_the_source_wrote(
    stub: ValueStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Serve the sentinels again with the null rows kept, and find each one as a `raw:` token on its value.

    The default drops the rows without a value, and with them their flags: a caller sees the text with
    `drop_nulls=False` or in the wide shape.
    """
    assert stub.tokens, f"{stub.provider}: a stub of a reader that maps a sentinel names the tokens it must carry"
    df = stub.build(monkeypatch, drop_nulls=False)
    # a sentinel the stub says the source writes has its text named, or the reader maps it and forgets it
    without_text = {name for name, _ in stub.sentinels} - {parameter for parameter, _, _ in stub.tokens}
    assert without_text == set(), f"{stub.provider}: no `raw:` token is named for {sorted(without_text)}"
    flags = pl.col("quality_flags").str.split(",")
    df = df.with_columns(
        pl.col("parameter"),
        flags.list.last().alias("last"),
        flags.list.eval(pl.element().str.starts_with("raw:")).list.sum().alias("raws"),
    )
    for name, text, value in stub.tokens:
        mapped = df.filter(
            (pl.col("parameter") == name)
            & (pl.col("last") == f"raw:{text}")
            & (pl.col("value").is_null() if value is None else (pl.col("value") == value))
        )
        assert not mapped.is_empty(), (
            f"{stub.provider}: no {name} read as {value} with `raw:{text}`, got "
            f"{df.filter(pl.col('parameter') == name).select('value', 'quality_flags').unique().to_dicts()}"
        )
    if stub.provider in NO_DIRECTION_CODE:
        _assert_the_rule_of_a_no_direction_code(df, stub)
    else:
        _assert_the_rule_of_a_calm(df, stub)
    # the token is the last kind and there is one: a caller reads `split(",")[-1]`
    assert df.filter(pl.col("raws") > 1).is_empty()
    assert df.filter((pl.col("raws") == 1) & ~pl.col("last").str.starts_with("raw:")).is_empty()
    if stub.empty_at:
        at = df.filter(pl.col("timestamp") == stub.empty_at)
        assert not at.is_empty(), f"{stub.provider}: no values at {stub.empty_at}"
        silent = at.filter(pl.col("raws").fill_null(0) == 0)
        assert silent.is_empty(), f"{stub.provider}: {silent.height} values at {stub.empty_at} carry no `raw:` token"


def _assert_the_rule_of_a_calm(df: pl.DataFrame, stub: ValueStub) -> None:
    """Hold the wind directions of a stub's output to the one rule of a calm, as the speed beside them says (GH-3222).

    A direction of 0 beside a speed of 0 of the same reading is a calm, and is null with `raw:0`: no provider returns
    the 0. A direction mapped from a 0 is beside a speed of 0, as a 0 beside a wind that blows stays. `df` is the
    output with the null rows kept and the last token of `quality_flags` as `last`.
    """
    present = set(df.get_column("parameter").unique().to_list())
    for direction, speeds in SPEED_OF_DIRECTION.items():
        speed = next((name for name in speeds if name in present), None)
        if direction not in present or speed is None:
            continue
        pairs = (
            df.filter(pl.col("parameter") == direction)
            .select("timestamp", pl.col("value").alias("direction"), pl.col("last"))
            .join(
                df.filter(pl.col("parameter") == speed).select("timestamp", pl.col("value").alias("speed")),
                on="timestamp",
            )
        )
        calm = pairs.filter((pl.col("direction") == 0) & (pl.col("speed") == 0))
        assert calm.is_empty(), f"{stub.provider}: {direction} is 0 beside a {speed} of 0: {calm.to_dicts()}"
        blowing = pairs.filter(pl.col("direction").is_null() & _MAPPED_ZERO & (pl.col("speed") > 0))
        assert blowing.is_empty(), f"{stub.provider}: a 0 of {direction} beside a wind that blows: {blowing.to_dicts()}"


# the 0 as the source wrote it, `0` or `0.0`, mapped away
_MAPPED_ZERO = pl.col("last").str.contains(r"^raw:0(\.0+)?$")


def _assert_the_rule_of_a_no_direction_code(df: pl.DataFrame, stub: ValueStub) -> None:
    """Hold a direction whose 0 is no bearing to the rule of a no-direction code: null with `raw:0`, whatever the speed.

    The stub serves the 0, so the rule is seen to apply (GH-3222); `NO_DIRECTION_CODE` says what makes it one.
    """
    directions = df.filter(pl.col("parameter").is_in(list(SPEED_OF_DIRECTION)))
    returned = directions.filter(pl.col("value") == 0)
    assert returned.is_empty(), f"{stub.provider}: a 0 that is no bearing is returned: {returned.to_dicts()}"
    mapped = directions.filter(pl.col("value").is_null() & _MAPPED_ZERO)
    assert not mapped.is_empty(), f"{stub.provider}: the stub serves no 0 of a direction, so the rule is not seen"


def test_a_reader_that_maps_a_sentinel_has_a_stub() -> None:
    """A network whose reader uses the helper that maps a sentinel is held to its stub, with the tokens it names.

    The test above holds what a stub names to the `raw:` token; this keeps a reader from losing its stub, and a network
    that has taken up the helper from sitting in `NO_STUB` with the reason it had before.
    """
    users = set()
    for path in PROVIDER_DIR.rglob("*.py"):
        parts = path.relative_to(PROVIDER_DIR).parts
        text = path.read_text(encoding="utf-8")
        if len(parts) >= 3 and re.search(r"\b(null_sentinels|clear_sentinels|unpivot_with_raw|raw_column)\(", text):
            users.add(f"{parts[0]}/{parts[1]}")
    stubbed = {stub.provider.split(" ")[0] for stub in STUBS}
    assert users - stubbed == set(), "add a stub with its tokens to STUBS"
    assert users, "the helper is used by no reader, or the search found no provider"


def test_the_parameters_a_stub_names_are_canonical() -> None:
    """A parameter of a stub that is not a canonical name is never found in the output, and its check is dead."""
    for stub in STUBS:
        named = {stub.reading[0], *(name for name, _ in stub.sentinels)}
        assert named <= set(PARAMETERS), f"{stub.provider}: {sorted(named - set(PARAMETERS))}"


def test_every_network_has_a_stub_or_a_reason() -> None:
    """A network added to the library takes a stand: a stub of its source, or the reason it has none yet."""
    registered = {
        f"{provider}/{network}" for provider, networks in Wetterdienst.registry.items() for network in networks
    }
    stubbed = {stub.provider.split(" ")[0] for stub in STUBS}
    assert registered - stubbed - set(NO_STUB) == set(), "add a stub to STUBS, or a reason to NO_STUB"
    assert set(NO_STUB) - registered == set(), "NO_STUB names a network that is not registered"
    assert set(NO_STUB) & stubbed == set(), "NO_STUB names a network that has a stub"
    assert stubbed - registered == set()
