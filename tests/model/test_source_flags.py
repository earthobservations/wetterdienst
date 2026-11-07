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
from wetterdienst.model import source_flags
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
DIGIT_FLAGS = SourceFlags(datasets=("a/b",), codes=(SourceCode("1", "suspect"),), url="u", quote="q", digit=3)
PARAMETER_FLAGS = SourceFlags(
    datasets=("a/b",),
    codes=(SourceCode("3", "Error"),),
    url="u",
    quote="q",
    beside=("source", ("345",)),
    parameters=("humidity_relative", "wind_speed"),
)


def _hits(flags: SourceFlags, texts: list[str | None], parameters: list[str] | None = None) -> list[bool]:
    frame = pl.DataFrame({"quality_flags": texts}, schema={"quality_flags": pl.String})
    if parameters is not None:
        frame = frame.with_columns(pl.Series("parameter", parameters, dtype=pl.String))
    return frame.select(flags.hit()).to_series().to_list()


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


def test_a_digit_is_counted_from_the_right_in_the_code_as_the_file_writes_it() -> None:
    """MIDAS writes `02576` as `2576`: the status is the third digit from the right, and a short code has none."""
    assert _hits(
        DIGIT_FLAGS,
        ["100", "2176", "02176", "20101", "20001", "1", "11", "0100", "100,raw:1", "1.00", "x100", "", None, "-1100"],
    ) == [True, True, True, True, False, False, False, True, True, False, False, False, False, True]


def test_a_code_limited_to_parameters_is_read_for_those_parameters_alone() -> None:
    """Source 345's `3` is "for relative humidity and wind speed only", so the temperature of the source is no hit."""
    texts = ["3,source:345"] * 4 + ["3,source:313", None]
    parameters = [
        "humidity_relative",
        "wind_speed",
        "temperature_air_2m",
        "relative_humidity",
        "wind_speed",
        "wind_speed",
    ]
    assert _hits(PARAMETER_FLAGS, texts, parameters) == [True, True, False, False, False, False]
    # the canonical names are resolved to the names the frame holds, the source's own
    flags = pl.DataFrame({"quality_flags": texts, "parameter": parameters})
    names = {"humidity_relative": "relative_humidity"}
    erroneous, suspect = hits(flags, [PARAMETER_FLAGS], names)
    assert erroneous.to_list() == [False, True, False, True, False, False]
    assert not suspect.any()


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
    codes=(SourceCode("1", "Suspect", "suspect"), SourceCode("2", "Poor"), SourceCode("4", "Missing-is-no-code")),
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
    """A forecast is soft whatever is set: the worse level is flagged, not nulled, and so is the milder one."""
    out = judge(_frame(["1", "2"], [10.0, 20.0]), _plan(TWO_LEVELS, forecast=True), Plausibility(source="hard"))
    assert out["quality_flags"].to_list() == ["1,suspect:source", "2,suspect:source"]
    assert out["value"].to_list() == [10.0, 20.0]


def test_the_levels_of_the_map_are_those_the_documentation_words() -> None:
    """Only a source with two levels has a suspect level.

    GHCNh `Suspect`, 382 `R` and `f` of a derived humidity or wet bulb, CHMI `Suspect`, MADIS `Questioned`.
    """
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
        ("noaa/ghcn", "R"),
        ("noaa/ghcn", "f"),
        ("chmi/observation", "1"),
        ("nws/observation", "Q"),
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
    code = code + "0" * ((flags.digit or 1) - 1)
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
                # a rule limited to parameters is judged on the first of them, as the dataset names it
                parameter = next(
                    (
                        parameter.name_original
                        for parameter in model.parameters
                        if flags.parameters is not None and parameter.name == flags.parameters[0]
                    ),
                    "p",
                )
                for code in flags.codes:
                    text = _flags_with(flags, code.code)
                    frame = _frame([text, "unflagged"], [1.0, 1.0]).with_columns(
                        pl.lit(parameter).alias("parameter"),
                        pl.datetime(2026, 1, 1, time_zone="UTC").alias("timestamp"),
                    )
                    out = judged(frame, network=network, dataset=model)
                    assert out["quality_flags"].to_list() == [f"{text},suspect:source", "unflagged"], (
                        network,
                        dataset_name,
                        code.code,
                    )


def test_the_codes_of_several_rules_are_extracted_once_and_judged_as_each_rule_alone() -> None:
    """`hits` over a frame is the any of the rules' own expressions, whichever kinds they read."""
    rules = [*SOURCE_FLAGS["noaa/ghcn"]]
    texts = [
        "3,source:313",
        "3,source:220",
        "3,source:345",
        "X,source:382",
        "X,source:313",
        "7,source:220",
        "1",
        None,
        "2,source:313",
        "6,source:335",
        "R,source:382",
        "R,source:313",
        "6,source:220",
    ]
    df = pl.DataFrame(
        {"quality_flags": texts, "parameter": ["p"] * len(texts)},
        schema=dict.fromkeys(["quality_flags", "parameter"], pl.String),
    )
    hourly = [rule for rule in rules if "hourly/data" in rule.datasets]
    alone = df.select(pl.any_horizontal(rule.hit() for rule in hourly).alias("hit")).to_series().to_list()
    erroneous, suspect = hits(df, hourly)
    mild = df.select(pl.any_horizontal(rule.hit(level="suspect") for rule in hourly).alias("hit")).to_series()
    assert (erroneous | suspect).to_list() == alone
    assert alone == [True, True, False, True, False, False, False, False, True, True, True, False, False]
    assert suspect.to_list() == mild.to_list() == [False] * 8 + [True] * 3 + [False] * 2
    assert not (erroneous & suspect).any()


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


def test_the_datasets_of_the_map_exist_and_the_coverage_follows_them() -> None:
    """The datasets are `resolution/dataset` of their network, and a dataset has the rules `flags_of` finds."""
    for network, rules in SOURCE_FLAGS.items():
        provider, name = network.split("/")
        metadata = Wetterdienst.resolve(provider, name).metadata
        existing = {f"{resolution.name}/{dataset.name}" for resolution in metadata for dataset in resolution}
        for flags in rules:
            assert set(flags.datasets) <= existing, (network, sorted(set(flags.datasets) - existing))
    assert len(flags_of("noaa/ghcn", "hourly/data")) == 6
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
            _assert_levels_in_cells(rows, flags, network)


def _assert_levels_in_cells(rows: str, flags: SourceFlags, network: str) -> None:
    """Assert the two levels of a rule are told apart in the table cell of its codes, each code under its level."""
    suspect = [code.code for code in flags.codes if code.level == "suspect"]
    erroneous = [code.code for code in flags.codes if code.level == "erroneous"]
    # the cell of this rule's codes: the one whose backticked codes are exactly the rule's
    wanted = {code.code for code in flags.codes}
    cell = next(
        part for part in rows.split(" | ") if "suspect level:" in part and set(re.findall(r"`([^`]+)`", part)) == wanted
    )
    before, _, after = cell.partition("erroneous level:")
    assert all(f"`{code}`" in before for code in suspect), (network, wanted)
    # a rule may have a suspect level only (`f` of a derived wet bulb temperature)
    assert bool(erroneous) == ("erroneous level:" in cell), (network, wanted)
    assert all(f"`{code}`" in after for code in erroneous), (network, wanted)


@pytest.mark.parametrize("network", sorted(SOURCE_FLAGS))
def test_the_page_of_the_provider_cites_every_code_of_the_map(network: str) -> None:
    """The page of the network says each code with the words of the documentation, and links the page they are on."""
    text = _flat((PROVIDER_PAGES / network / "index.md").read_text(encoding="utf-8"))
    for flags in SOURCE_FLAGS[network]:
        assert flags.url in text, (network, flags.url)
        for code in flags.codes:
            assert code.wording in text, (network, code.code, code.wording)
            assert f"`{code.code}`" in text, (network, code.code)


#: how every text names a suspect-level code of the map (the milder level of a source that has two), by network and code
SUSPECT_NAMES = {
    ("noaa/ghcn", "2"): "GHCNh `Suspect`",
    ("noaa/ghcn", "6"): "GHCNh `Suspect`",
    ("noaa/ghcn", "R"): "382 `R`",
    ("noaa/ghcn", "f"): "GHCNh `f`",
    ("chmi/observation", "1"): "CHMI `Suspect`",
    ("nws/observation", "Q"): "MADIS `Questioned`",
}
#: the list of them that the CLI help, the OpenAPI document and the pages give, in the order they all give it: the
#: plain flag of GHCNh, the letter of source 382, then the others, each named with its provider (`Hub'Eau `12``,
#: `NWS/MADIS `X`` and `Météo-France `2`` would be read as more of the list), the last one after a comma or an `and`
_SUSPECT_LIST = re.compile(r"GHCNh `Suspect` and (?:source )?382 `R`(?P<rest>(?:(?:, | and )[A-Z][^,`()]*? `[^`]+`)*)")
#: the files that name the suspect level, with the number of lists each holds: the pages, the Python strings that make
#: the CLI help and the OpenAPI document, the snapshots of both (any number: one for every route that has the field),
#: and the legend of the token `suspect:`. A list written in another form is not found by the expression above, and the
#: count of the lists is what tells
_LISTING_FILES: dict[str, int | None] = {
    "docs/data/plausibility.md": 2,
    "docs/data/quality-flags.md": 1,
    "docs/data/special_values.md": 1,
    "docs/usage/cli.md": 1,
    "docs/usage/python-api.md": 1,
    "src/wetterdienst/model/plausibility.py": 1,
    "src/wetterdienst/model/plausibility_modes.py": 1,
    "src/wetterdienst/model/quality_legend.py": 1,
    "tests/ui/cli/help.snapshot.txt": 1,
    "tests/ui/openapi.snapshot.json": None,
}
#: the files a list of them is looked for in: not the changelog and the migration guide, which tell a release as it
#: was, and not the baselines, which are the last release's contract
_HISTORIC = {"changelog.md", "migrating.md"}
_SCANNED = (
    *(path for path in sorted((ROOT / "docs").rglob("*.md")) if path.name not in _HISTORIC),
    *sorted((ROOT / "src" / "wetterdienst").rglob("*.py")),
    ROOT / "tests" / "ui" / "cli" / "help.snapshot.txt",
    ROOT / "tests" / "ui" / "openapi.snapshot.json",
)


def _suspect_codes() -> set[tuple[str, str]]:
    """Give the suspect-level codes of the map as (network, code): the milder level of a source that has two."""
    return {
        (network, code.code)
        for network, rules in SOURCE_FLAGS.items()
        for flags in rules
        for code in flags.codes
        if code.level == "suspect"
    }


def _listed(path: Path) -> list[set[str]]:
    """Give the suspect levels each list in a file names, as the names of `SUSPECT_NAMES` (`source 382` is `382`).

    A Python string that the source breaks over several lines is read as the one string it is.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        text = re.sub(r'"\s*\n\s*"', "", text)
    found = []
    for match in _SUSPECT_LIST.finditer(_flat(text)):
        rest = re.split(r", | and ", match["rest"])
        found.append({"GHCNh `Suspect`", "382 `R`", *(item for item in rest if item)})
    return found


def _assert_the_map_is_listed(path: Path) -> None:
    """Assert each list of the suspect level in a file names the codes of the map: none missing, none more."""
    wanted = set(SUSPECT_NAMES.values())
    for listed in _listed(path):
        assert listed == wanted, (str(path), "missing", sorted(wanted - listed), "more", sorted(listed - wanted))


def test_every_suspect_level_code_of_the_map_has_a_name_in_the_texts() -> None:
    """A new suspect-level code, or one that goes, is named in `SUSPECT_NAMES` and so in every list that follows."""
    assert set(SUSPECT_NAMES) == _suspect_codes()


@pytest.mark.parametrize(("name", "count"), _LISTING_FILES.items())
def test_the_texts_that_name_the_suspect_level_list_all_of_it(name: str, count: int | None) -> None:
    """The list of the codes that stay `suspect:source` in the mode `hard` is the map's, in each place it is given.

    The pages, the field descriptions of the CLI help and of the OpenAPI document and the legend of the token
    `suspect:` (GH-3763: the `f` of a derived humidity was in the map and in none of them for a time).
    """
    found = _listed(ROOT / name)
    assert bool(found) if count is None else len(found) == count, (name, "lists found", len(found))
    _assert_the_map_is_listed(ROOT / name)


@pytest.mark.parametrize("path", _SCANNED, ids=lambda path: str(path.relative_to(ROOT)))
def test_no_other_text_lists_the_suspect_level_in_part(path: Path) -> None:
    """A list in a file that the test above does not name is held to the map as well."""
    _assert_the_map_is_listed(path)


@pytest.mark.parametrize("network", sorted({network for network, _ in SUSPECT_NAMES}))
def test_the_page_of_the_provider_has_each_code_under_the_level_the_map_gives_it(network: str) -> None:
    """A table of codes on the pages of a provider that has a suspect level tells it apart from the erroneous one."""
    for page in sorted((PROVIDER_PAGES / network).glob("*.md")):
        text = _flat(page.read_text(encoding="utf-8"))
        for flags in SOURCE_FLAGS[network]:
            if any(code.level == "suspect" for code in flags.codes) and "suspect level:" in text:
                _assert_levels_in_cells(text, flags, network)


#: what the module docstring and the comment of `SourceCode.level` of the map name as the suspect level, in the
#: words they use (the letters and words of the codes, not the providers)
_SUSPECT_WORDS = ("Suspect", "R", "f", "Questioned")


def test_the_docstring_of_the_map_names_every_suspect_level() -> None:
    """The module docstring and the comment of `level` name the suspect level of every source that has one."""
    text = _flat(Path(source_flags.__file__).read_text(encoding="utf-8"))
    docstring = _flat(source_flags.__doc__ or "")
    comment = text[text.index("#: ``erroneous``: the documentation words") :].split("level: Level")[0]
    for word in _SUSPECT_WORDS:
        assert f"``{word}``" in docstring, word
        assert f'"{word}"' in comment, word
