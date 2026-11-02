# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The check `source`: the codes of a source's own quality flag that mark a value as wrong or in doubt (GH-3677).

`wetterdienst.model.source_flags.SOURCE_FLAGS` names the codes, each with the wording and the page of the provider's
documentation; the core reads them in `quality_flags` (`model/judge.py`). Held here: how a code is found in the
flag, what the two modes and a forecast make of it, that a reading with a `raw:` token or no value is left alone,
and that the map, the page of the plausibility checks and the pages of the providers say the same.
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl
import pytest

from tests.provider.judging import judged
from wetterdienst import Wetterdienst
from wetterdienst.model.judge import Plan, judge
from wetterdienst.model.plausibility import COVERAGE, Plausibility
from wetterdienst.model.source_flags import (
    SOURCE_FLAGS,
    SourceCode,
    SourceFlags,
    flags_of,
    hits,
    source_coverage,
)

ROOT = Path(__file__).parent.parent.parent
PLAUSIBILITY_PAGE = ROOT / "docs" / "data" / "plausibility.md"
PROVIDER_PAGES = ROOT / "docs" / "data" / "provider"

PLAIN_FLAGS = SourceFlags(datasets=("a/b",), codes=(SourceCode("X", "failed bounds check"),), url="u", quote="q")
KIND_FLAGS = SourceFlags(
    datasets=("a/b",), codes=(SourceCode("false", "invalid"),), url="u", quote="q", kind="validity"
)
BESIDE_FLAGS = SourceFlags(
    datasets=("a/b",),
    codes=(SourceCode("3", "Erroneous"),),
    url="u",
    quote="q",
    beside=("source", ("313", "343")),
)


def _hits(flags: SourceFlags, texts: list[str | None]) -> list[bool]:
    return (
        pl.DataFrame({"quality_flags": texts}, schema={"quality_flags": pl.String})
        .select(flags.hit())
        .to_series()
        .to_list()
    )


def test_a_plain_code_is_the_first_token_of_the_flags_and_no_other() -> None:
    """The ordinary quality flag of a source comes first, without a `kind:`; a kind or the `raw:` text is no code."""
    assert _hits(
        PLAIN_FLAGS,
        ["X", "X,measurement:T,source:0", "G,X", "measurement:T,source:X", "source:X", "raw:X", "", None, "XX", "x"],
    ) == [True, True, False, False, False, False, False, False, False, False]


def test_a_code_of_a_kind_is_the_text_after_its_name() -> None:
    """`validity:false` is read as the code `false` of the kind `validity`, wherever the token stands."""
    assert _hits(
        KIND_FLAGS,
        [
            "manual,validity:false",
            "validity:false",
            "none,validity:true",
            "validity:false,raw:1",
            "false",
            "xvalidity:false",
            None,
        ],
    ) == [True, True, False, True, False, False, False]


def test_a_code_beside_a_source_is_read_in_the_list_of_that_source_alone() -> None:
    """GHCNh's code `3` is `Erroneous` in the lists of some sources; the same code of another source is none."""
    assert _hits(
        BESIDE_FLAGS,
        ["3,source:313", "3,measurement:N,source:343", "3,source:345", "3", "2,source:313", "3,source:3130", None],
    ) == [True, True, False, False, False, False, False]


def _plan(*flags: SourceFlags, forecast: bool = False) -> Plan:
    return Plan("a/b", {}, {}, forecast=forecast, source=flags)


def _frame(flags: list[str | None], values: list[float | None]) -> pl.DataFrame:
    return pl.DataFrame(
        {"parameter": ["p"] * len(flags), "value": values, "quality_flags": flags, "__source": values},
        schema={"parameter": pl.String, "value": pl.Float64, "quality_flags": pl.String, "__source": pl.Float64},
    )


def test_soft_keeps_the_value_and_flags_it_and_hard_nulls_it_and_keeps_the_number() -> None:
    """Soft writes `suspect:source` after the source's own flags, hard `rejected:source,raw:<number>` and a null."""
    df = _frame(["X,source:0", "source:0", None], [12.5, 3.0, 4.0])
    soft = judge(df, _plan(PLAIN_FLAGS), Plausibility(source="soft"))
    assert soft["quality_flags"].to_list() == ["X,source:0,suspect:source", "source:0", None]
    assert soft["value"].to_list() == [12.5, 3.0, 4.0]
    hard = judge(df, _plan(PLAIN_FLAGS), Plausibility(source="hard"))
    assert hard["quality_flags"].to_list() == ["X,source:0,rejected:source,raw:12.5", "source:0", None]
    assert hard["value"].to_list() == [None, 3.0, 4.0]
    # soft is the default of the check
    assert judge(df, _plan(PLAIN_FLAGS), Plausibility()).equals(soft)


TWO_LEVELS = SourceFlags(
    datasets=("a/b",),
    codes=(SourceCode("1", "Suspect", "suspect"), SourceCode("2", "Poor"), SourceCode("3", "Estimated-not-a-code")),
    url="u",
    quote="q",
)


def test_hard_nulls_the_erroneous_level_and_only_flags_the_suspect_level() -> None:
    """A source with two levels: soft flags both, hard nulls the worse and keeps the milder flagged, never nulled."""
    df = _frame(["1", "2", "0", "1,raw:-999"], [10.0, 20.0, 30.0, None])
    plan = _plan(TWO_LEVELS)
    soft = judge(df, plan, Plausibility(source="soft"))
    assert soft["quality_flags"].to_list() == ["1,suspect:source", "2,suspect:source", "0", "1,raw:-999"]
    assert soft["value"].to_list() == [10.0, 20.0, 30.0, None]
    hard = judge(df, plan, Plausibility(source="hard"))
    assert hard["quality_flags"].to_list() == ["1,suspect:source", "2,rejected:source,raw:20", "0", "1,raw:-999"]
    assert hard["value"].to_list() == [10.0, None, 30.0, None]


def test_the_suspect_level_joins_the_other_checks_under_the_name_source() -> None:
    """In hard mode the milder level is `source` among the soft checks, and a hard check that nulls the value wins."""
    flags = SourceFlags(datasets=("a/b",), codes=(SourceCode("1", "Suspect", "suspect"),), url="u", quote="q")
    plan = Plan("a/b", {}, {"p": (0.0, 10.0)}, source=(flags,))
    df = _frame(["1", "1"], [50.0, 5.0])
    out = judge(df, plan, Plausibility(range="soft", source="hard"))
    assert out["quality_flags"].to_list() == ["1,suspect:range+source", "1,suspect:source"]
    out = judge(df, plan, Plausibility(range="hard", source="hard"))
    assert out["quality_flags"].to_list() == ["1,rejected:range,raw:50", "1,suspect:source"]
    assert out["value"].to_list() == [None, 5.0]


def test_a_forecast_flags_both_levels_in_hard_mode_too() -> None:
    """A forecast is soft whatever is set: the worse level is flagged, not nulled."""
    out = judge(_frame(["2"], [20.0]), _plan(TWO_LEVELS, forecast=True), Plausibility(source="hard"))
    assert out["quality_flags"].to_list() == ["2,suspect:source"]
    assert out["value"].to_list() == [20.0]


def test_the_levels_of_the_map_are_those_the_documentation_words() -> None:
    """Only a source with two levels has a suspect level: GHCNh `Suspect`, CHMI `Suspect`; the rest is erroneous."""
    levels = {
        (network, code.code): code.level
        for network, rules in SOURCE_FLAGS.items()
        for flags in rules
        for code in flags.codes
        if code.level == "suspect"
    }
    assert set(levels) == {
        ("noaa/ghcn", "2"),
        ("noaa/ghcn", "6"),
        ("chmi/observation", "1"),
    }


def test_a_reading_with_a_raw_token_or_without_a_value_is_not_judged() -> None:
    """A value that is a code of the source already (`raw:`), and a reading that has no value, are left alone."""
    df = _frame(["X,raw:-999", "X", "X"], [None, None, 1.0])
    out = judge(df, _plan(PLAIN_FLAGS), Plausibility(source="hard"))
    assert out["quality_flags"].to_list() == ["X,raw:-999", "X", "X,rejected:source,raw:1"]


def test_the_source_check_joins_the_other_checks_alphabetically() -> None:
    """`range` and `source` on one value: both soft are `suspect:range+source`; a hard `range` nulls it alone."""
    flags = SourceFlags(datasets=("a/b",), codes=(SourceCode("X", "w"),), url="u", quote="q")
    plan = Plan("a/b", {}, {"p": (0.0, 10.0)}, source=(flags,))
    df = _frame(["X", "X"], [50.0, 5.0])
    soft = judge(df, plan, Plausibility(range="soft"))
    assert soft["quality_flags"].to_list() == ["X,suspect:range+source", "X,suspect:source"]
    hard = judge(df, plan, Plausibility(range="hard"))
    assert hard["quality_flags"].to_list() == ["X,rejected:range,raw:50", "X,suspect:source"]
    assert hard["value"].to_list() == [None, 5.0]
    both = judge(df, plan, Plausibility(range="hard", source="hard"))
    assert both["quality_flags"].to_list() == ["X,rejected:range+source,raw:50", "X,rejected:source,raw:5"]


def test_a_forecast_is_judged_soft_whatever_the_mode() -> None:
    """On a forecast network every built-in check but `floor` and `limits` is soft, so `source` is too (GH-3676)."""
    df = _frame(["X"], [12.5])
    out = judge(df, _plan(PLAIN_FLAGS, forecast=True), Plausibility(source="hard"))
    assert out["quality_flags"].to_list() == ["X,suspect:source"]
    assert out["value"].to_list() == [12.5]


def test_no_forecast_network_has_a_flag_of_its_own_to_read() -> None:
    """The forecast networks (the metadata `kind`) have no entry in the map: none of their sources flags a value."""
    forecasts = {
        f"{provider}/{network}"
        for provider, networks in Wetterdienst.registry.items()
        for network in networks
        if not Wetterdienst.is_standalone(provider, network)
        and Wetterdienst.resolve(provider, network).metadata.kind == "forecast"
    }
    assert forecasts
    assert forecasts.isdisjoint(SOURCE_FLAGS)


def _flags_with(flags: SourceFlags, code: str) -> str:
    """Write the `quality_flags` a reader writes for a reading of a rule that carries a code of it."""
    plain = f"{code}" if flags.kind is None else f"{flags.kind}:{code}"
    if flags.beside is None:
        return plain
    beside, values = flags.beside
    return f"{plain},{beside}:{values[0]}"


def test_the_core_judges_every_code_of_the_map_in_every_dataset_that_carries_it() -> None:
    """Through the plan of the core, a reading with any code of the map is flagged, whatever else the dataset checks."""
    for network, rules in SOURCE_FLAGS.items():
        provider, name = network.split("/")
        metadata = Wetterdienst.resolve(provider, name).metadata
        for flags in rules:
            for dataset_name in flags.datasets:
                resolution, dataset = dataset_name.split("/")
                model = metadata[resolution][dataset]
                for code in flags.codes:
                    text = _flags_with(flags, code.code)
                    frame = _frame([text, "unflagged"], [1.0, 1.0]).with_columns(pl.lit("p").alias("parameter"))
                    out = judged(frame, network=network, dataset=model)
                    assert out["quality_flags"].to_list() == [f"{text},suspect:source", "unflagged"], (
                        network,
                        dataset_name,
                        code.code,
                    )


def test_the_codes_of_several_rules_are_extracted_once_and_judged_as_each_rule_alone() -> None:
    """`hits` over a frame is the any of the rules' own expressions, whichever kinds they read."""
    rules = [*SOURCE_FLAGS["noaa/ghcn"]]
    texts = ["3,source:313", "3,source:345", "3,source:220", "X,source:382", "X,source:313", "7,source:220", "1", None]
    df = pl.DataFrame({"quality_flags": texts}, schema={"quality_flags": pl.String})
    hourly = [rule for rule in rules if "hourly/data" in rule.datasets]
    alone = df.select(pl.any_horizontal(rule.hit() for rule in hourly).alias("hit")).to_series().to_list()
    erroneous, suspect = hits(df, hourly)
    assert (erroneous | suspect).to_list() == alone == [True, True, True, True, False, False, False, False]
    assert suspect.to_list() == [False] * 8


def test_every_code_has_the_wording_and_the_page_of_its_documentation() -> None:
    """A code that is no cited word of the provider is not in the map: wording, URL and quote are all there."""
    for network, rules in SOURCE_FLAGS.items():
        assert rules, network
        for flags in rules:
            assert flags.url.startswith("https://"), (network, flags.url)
            assert flags.quote.strip(), network
            assert flags.codes, network
            for code in flags.codes:
                assert code.code.strip() == code.code
                assert code.wording.strip(), (network, code.code)
            assert len({code.code for code in flags.codes}) == len(flags.codes), network


def test_the_datasets_of_the_map_exist_and_are_one_rule_each() -> None:
    """The datasets are `resolution/dataset` of their network, and none is in two rules with the same codes."""
    for network, rules in SOURCE_FLAGS.items():
        provider, name = network.split("/")
        metadata = Wetterdienst.resolve(provider, name).metadata
        existing = {f"{resolution.name}/{dataset.name}" for resolution in metadata for dataset in resolution}
        for flags in rules:
            assert set(flags.datasets) <= existing, (network, sorted(set(flags.datasets) - existing))
    for dataset in ("hourly/data",):
        assert len(flags_of("noaa/ghcn", dataset)) == 4
    assert source_coverage() == COVERAGE["source"]


def _flat(text: str) -> str:
    """Give a page's text with every run of white space (a line break of the markdown) as one space."""
    return re.sub(r"\s+", " ", text)


def _source_rows(network: str) -> str:
    """Give the rows of the table of the codes that are the network's, as one text."""
    text = PLAUSIBILITY_PAGE.read_text(encoding="utf-8")
    block = text.split("<!-- source:start -->")[1].split("<!-- source:end -->")[0]
    rows = [line for line in block.splitlines() if line.startswith(f"| `{network}` |")]
    assert rows, network
    return _flat(" ".join(rows))


@pytest.mark.parametrize("network", sorted(SOURCE_FLAGS))
def test_the_plausibility_page_cites_every_code_of_the_map(network: str) -> None:
    """Each code, its wording, its datasets and the page it is taken from are in the rows of the page of the checks."""
    rows = _source_rows(network)
    for flags in SOURCE_FLAGS[network]:
        assert flags.url in rows, (network, flags.url)
        for code in flags.codes:
            assert f"`{code.code}`" in rows, (network, code.code)
            assert code.wording in rows, (network, code.code, code.wording)
        for dataset in flags.datasets:
            assert f"`{dataset}`" in rows, (network, dataset)
        if any(code.level == "suspect" for code in flags.codes):
            # the two levels are told apart in the table, each code under the level it is
            suspect = [code.code for code in flags.codes if code.level == "suspect"]
            erroneous = [code.code for code in flags.codes if code.level == "erroneous"]
            cell = next(
                part for part in rows.split("| ") if "suspect level:" in part and flags.codes[0].wording in part
            )
            assert cell.index("suspect level:") < cell.index("erroneous level:")
            before, after = cell.split("erroneous level:")
            assert all(f"`{code}`" in before for code in suspect)
            assert all(f"`{code}`" in after for code in erroneous)


@pytest.mark.parametrize("network", sorted(SOURCE_FLAGS))
def test_the_page_of_the_provider_cites_every_code_of_the_map(network: str) -> None:
    """The page of the network says each code with the words of the documentation, and links the page they are on."""
    text = _flat((PROVIDER_PAGES / network / "index.md").read_text(encoding="utf-8"))
    for flags in SOURCE_FLAGS[network]:
        assert flags.url in text, (network, flags.url)
        for code in flags.codes:
            assert code.wording in text, (network, code.code, code.wording)
            assert f"`{code.code}`" in text, (network, code.code)
