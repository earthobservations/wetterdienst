# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the documentation."""

import doctest
import os.path
import re
import warnings
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

from wetterdienst.metadata.parameter_table import PARAMETERS

ROOT = Path(__file__).parent.parent
PROVIDER = Path(ROOT / "src" / "wetterdienst" / "provider")
COVERAGE = Path(ROOT / "docs" / "data" / "provider")

EXCLUDE_PROVIDER_NETWORKS_FILES_STARTSWITH = ["_", ".", "metadata"]

# Networks that expose no `metadata` attribute, and so declare no resolutions for the docs tests to
# compare. Named rather than merely skipped: the skip is keyed on an attribute, so a rename would drop
# a provider out of all four comparisons *and*, because it lands in `skipped`, exempt its published
# pages from the page side of `test_docs_cover_every_resolution` -- all 88 pages could go to none
# checked with every test still passing. `dwd/alerts` is a CAP warnings feed with no timeseries model.
NETWORKS_WITHOUT_A_METADATA_MODEL = {("dwd", "alerts")}

# Networks whose request class needs a package outside the base install, and which therefore go
# unchecked when it is absent. Bounded for the same reason as the set above: landing in `skipped`
# exempts a network's pages from both directions of `test_docs_cover_every_resolution`, and the skip is
# only a warning, which nothing escalates. `dwd/derived` reaches pandas through
# `provider/dwd/derived/metaindex.py`, which the `export` extra supplies; CI installs it
# (`.github/workflows/install.sh testing`) and so skips nothing, while a bare `uv sync` leaves those
# three resolutions unverified -- including description changes made to them. Any other network
# skipped this way is unexpected and fails.
NETWORKS_NEEDING_AN_EXTRA = {("dwd", "derived")}

# Providers that are excluded from the docs. "*" is a wildcard.
EXCLUDE_PROVIDER_NETWORKS = {
    "eumetnet": "*",
    "dwd": ["radar"],
}


@pytest.mark.remote
def test_readme() -> None:
    """Test to make sure that the wetterdienst example code in the README works."""
    readme_file = Path(__file__).parent.parent / "README.md"
    failures, _ = doctest.testfile(
        filename=str(readme_file),
        module_relative=False,
        optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS,
    )
    assert failures == 0


def test_data_coverage() -> None:
    """Test to make sure that the docs correctly cover provider data."""

    def _check_startswith(name: str, startswith: list[str]) -> bool:
        return any(name.startswith(sw) for sw in startswith)

    for provider in PROVIDER.glob("*"):
        if (
            not provider.is_dir()
            or _check_startswith(provider.name, EXCLUDE_PROVIDER_NETWORKS_FILES_STARTSWITH)
            or EXCLUDE_PROVIDER_NETWORKS.get(provider.name) == "*"
        ):
            continue
        assert Path(COVERAGE / provider.name).is_dir()
        provider_readme = Path(COVERAGE / provider.name / "index.md")
        assert provider_readme.exists()
        provider_readme_content = provider_readme.read_text(encoding="utf8")
        for network in provider.glob("*"):
            if (
                not network.is_dir()
                or _check_startswith(network.name, EXCLUDE_PROVIDER_NETWORKS_FILES_STARTSWITH)
                or network.name in EXCLUDE_PROVIDER_NETWORKS.get(provider.name, [])
            ):
                continue
            assert f"{network.name}/index.md" in provider_readme_content
            assert Path(COVERAGE / provider.name / network.name).is_dir()
            network_readme = Path(COVERAGE / provider.name / network.name / "index.md")
            assert network_readme.exists()
            network_readme_content = network_readme.read_text(encoding="utf8")
            # check docs consistency
            for resolution in Path(COVERAGE, provider.name, network.name).glob("*"):
                if resolution.name == "index.md":
                    continue
                assert f"{resolution.stem}{resolution.suffix}" in network_readme_content


# The MyST directives whose body is markdown, so a table inside one is documentation: admonitions,
# layout containers, and the table wrappers -- `{table}` exists only to give a markdown table a
# caption, so wrapping a `#### parameters` table in one is the likeliest next step on these pages.
# `_prose_lines` explains why anything unlisted is read as code instead.
_MARKUP_DIRECTIVES = frozenset(
    [
        "admonition",
        "csv-table",
        "figure",
        "list-table",
        "table",
        "toggle",
        "attention",
        "caution",
        "danger",
        "error",
        "hint",
        "important",
        "note",
        "seealso",
        "tip",
        "warning",
        "card",
        "container",
        "div",
        "dropdown",
        "grid",
        "grid-item",
        "grid-item-card",
        "margin",
        "sidebar",
        "tab-item",
        "tab-set",
    ],
)


def _prose_lines(path: Path) -> Iterator[str]:
    """Yield the lines of a docs page that sit outside a fenced code block.

    A ``#`` comment inside a fence is not a heading, and reading one as a level-1 heading would close
    the dataset section it sits in -- dropping every row below it out of its dataset, so that the
    descriptions test silently stops comparing them. Which is the skip this module exists to stop,
    and the reason the fence is stripped here rather than in each parser.

    A fence hides its contents unless it opens one of the markdown containers in
    `_MARKUP_DIRECTIVES`. A table inside a ``:::{note}`` or a `````{note}`` -- both legal -- is
    published documentation and has to be parsed; skipping it dropped the table and reported the
    absence as a missing row somewhere else entirely, which is the authoring trap this guard exists to
    remove rather than add. The backtick spelling is the one this tree writes, four times, in
    `docs/usage` and on `dwd/phenology`'s index; the colon spelling it writes once, in the warning on
    `dwd/road` 15_minutes.

    The list decides the default rather than the exception, because the two mistakes do not cost the
    same. A code body read as markdown puts a ``#`` comment where a level-1 heading goes, which
    closes the dataset section and makes the descriptions test compare *nothing* -- silent, and this
    module exists to stop that. A markdown container left off the list drops its tables instead,
    which the presence tests report. So an unrecognised directive is read as code: ``{code-block}``,
    ``{literalinclude}``, ``{doctest}``, ``{eval-rst}`` and the ``{code-cell}`` this repo
    opens 57 times all hold code, and a name nobody here has used yet is likelier to be another of
    those than another admonition.

    The open fences are a stack, so a code block nested in a directive still hides its own contents,
    and a closing fence is a bare marker at least as long as the one it closes: a three-backtick line
    inside a four-backtick block is content rather than the end of it.
    """
    fences: list[tuple[str, int, bool]] = []
    for line in path.read_text(encoding="utf8").splitlines():
        marker = re.match(r"\s*(`{3,}|~{3,}|:{3,})\s*(\S*)", line)
        # a backtick fence's info string may hold no backtick, so a line that merely *starts* with a
        # long inline code span is prose, and falls through to be yielded as such. Reading it as a fence
        # pushed one that the run closing that span could not close -- its own info string is not empty
        # -- and swallowed the rest of the page: loud on a resolution page, silent on a network index,
        # where only the glossary test runs. This module's own changelog entries are written that way
        inline_span = marker is not None and marker.group(1)[0] == "`" and "`" in line[marker.end(1) :]
        if marker and not inline_span:
            char, length, info = marker.group(1)[0], len(marker.group(1)), marker.group(2)
            closes = not info and bool(fences) and char == fences[-1][0] and length >= fences[-1][1]
            if closes:
                fences.pop()
            elif not fences or fences[-1][2]:
                name = info[1:].removesuffix("}").casefold() if info.startswith("{") else ""
                directive = name in _MARKUP_DIRECTIVES
                fences.append((char, length, directive))
            # else: a marker inside a code fence is literal content, not a fence of its own. Reading
            # it as one left the stack permanently open and dropped every line below it -- a whole page
            # for a ```text block showing a ~~~ or an unclosed :::{note}
            continue
        if not any(not directive for _, _, directive in fences):
            yield line


def _parameter_rows(path: Path) -> list[list[str]]:
    """Extract the rows of every parameter table in a provider docs page."""
    lines = _prose_lines(path)
    rows = []
    in_table = False
    for line in lines:
        if not line.startswith("|"):
            in_table = False
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] == "name" and "original name" in cells:
            in_table = True
            continue
        if in_table and not all(set(cell) <= {"-", ":"} for cell in cells):
            rows.append(cells)
    return rows


def test_docs_parameters_link_to_glossary() -> None:
    """Test that every documented parameter is canonical and links to the glossary.

    This is what keeps the provider tables honest: a parameter renamed in a provider's metadata
    but not in its docs page shows up here rather than silently documenting a name that no longer
    exists.
    """
    errors = []
    for path in sorted(COVERAGE.glob("**/*.md")):
        page = str(path.relative_to(COVERAGE))
        for cells in _parameter_rows(path):
            match = re.fullmatch(r"\{term\}`([a-z0-9_]+)`", cells[0])
            if not match:
                errors.append(f"{page}: {cells[0]!r} does not link to the glossary")
            elif match.group(1) not in PARAMETERS:
                errors.append(f"{page}: {match.group(1)!r} is not a canonical parameter")
    assert not errors, "\n".join(errors)


# the dataset a row is filed under when no `###` section is open. `_heading_datasets` closes the
# section on any heading of level 1 or 2, and this tree has `## Notes` and the like, so a parameter
# table placed after one used to be dropped on the floor -- the last silent skip of the class this
# module is about. Filed under a name the model can never declare, so the orphan check reports it.
_NO_SECTION = "<no dataset section>"


def _is_metadata_heading(line: str) -> bool:
    """Say whether a heading opens a ``metadata`` table, at whatever level and in whatever case.

    `dwd/mosmix` hourly writes ``#### Metadata`` where every other page writes ``#### metadata``, and
    `_heading_datasets` already tolerates that page's capitalisation, so both readers below do too.
    """
    return line.lstrip("#").strip().strip("#").strip().casefold() == "metadata"


def _heading_datasets(line: str, current: list[str]) -> list[str]:
    """Name the datasets a heading opens, for the two parsers below.

    ``### <name>`` opens a dataset section, ``#### parameters`` and the like stay inside the one it
    is in, and anything shallower closes it -- a page carries its own resolution-level ``##
    metadata`` table, whose rows belong to no dataset. Shared so that the two parsers cannot answer
    this differently, which is how one of them came to read that table as a dataset.

    The name is taken by stripping the hashes rather than by slicing past ``### ``, because a closing
    ATX sequence -- ``### data ###`` -- is valid and renders identically, and ``###data`` is too. The
    31 sections that carry no ``#### metadata`` table to name their dataset are the ones that would
    have paid for it.
    """
    level = len(line) - len(line.lstrip("#"))
    if level == 3:
        return [line.lstrip("#").strip().strip("#").strip()]
    if level >= 4:
        return current
    return []


def _section_datasets(path: Path) -> list[list[str]]:
    """Return the datasets each ``###`` section names, one entry per section, in page order.

    A first pass, so that the row parser below does not depend on the ``#### metadata`` table coming
    before the ``#### parameters`` one. A section naming no dataset falls back to its heading text,
    which is the dataset name on the 31 sections that carry no metadata table at all. A ``###``
    outside the page's ``## datasets`` block gets an empty entry rather than none, so that this walk
    and the row parser's stay in step over the same lines -- and so that rows under a prose heading
    are filed under no dataset and reported, rather than under the heading as though it named one.

    By position rather than by heading text, because two sections can share a heading while naming
    different datasets. Keyed by text, the later one won and the earlier one's rows were filed under
    its datasets -- and `_metadata_tables` reads the same page positionally, so the two parsers came
    out disagreeing, which is what sharing `_heading_datasets` is supposed to prevent.
    """
    sections: list[list[str]] = []
    # tracked separately from `sections` being non-empty: a `## Notes` after the last `###` closes the
    # section, and a metadata table under it was renaming that section's dataset -- while
    # `_metadata_tables` kept the right name, so the two parsers came out disagreeing
    section_open = False
    in_datasets = False
    in_metadata = False
    under_metadata = False
    for line in _prose_lines(path):
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            if level <= 2:
                # all 269 dataset sections in the tree sit under a `## datasets`, so a `###` anywhere
                # else is prose -- `metno/frost` already writes `## Notes` -- and calling it a dataset
                # would report the opposite of what happened
                name = line.lstrip("#").strip().strip("#").strip()
                in_datasets = level == 2 and name.casefold() == "datasets"
            if level == 3:
                # an entry per `###` either way, empty for a prose one, so that this walk and the row
                # parser's stay index for index in step over the same `_prose_lines`
                sections.append(_heading_datasets(line, []) if in_datasets else [])
                section_open = in_datasets
            elif level < 3:
                section_open = False
            under_metadata = _is_metadata_heading(line)
            in_metadata = False
            continue
        if not line.startswith("|"):
            in_metadata = False
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[:1] == ["property"]:
            in_metadata = section_open and under_metadata
            continue
        if in_metadata and cells[:1] == ["name"] and len(cells) >= 2:
            sections[-1] = [name.strip() for name in cells[1].split(",")]
    return sections


def _malformed_parameter_tables(path: Path) -> list[str]:
    """Return a line per parameter table or row that `_documented_descriptions` cannot read.

    It skips a row whose cell count does not match its header -- the column it wants is either absent
    or shifted -- and a table whose header has no ``description`` column at all. Dropping any of them
    silently made the presence test report the opposite of what happened: a row plainly on the page
    came out as "declares X, which it does not document", or a whole table as "parses to no parameter
    row at all". Forgetting a trailing ``constraints`` cell, leaving an unescaped ``|`` in a
    description, or omitting the column are all likelier slips than omitting a row, so the report has
    to name the real one. Every table in the tree has a ``description`` column and every row matches
    its header today.
    """
    malformed = []
    header = None
    for line in _prose_lines(path):
        if line.startswith("#") or not line.startswith("|"):
            header = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and cells[0] == "name" and "original name" in cells:
            header = cells
            # both columns, because `_documented_column` drops every row of a table that lacks the one
            # it is asked for: a table losing `unit` made the units test compare nothing and no other
            # test noticed, which is the hole this check closes for `description`
            missing = [wanted for wanted in ("description", "unit") if wanted not in cells]
            if missing:
                malformed.append(f"a parameter table has no {missing} column: {cells}")
            continue
        if header is None or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if len(cells) != len(header):
            name = re.sub(r"\{term\}`([^`]+)`", r"\1", cells[0])
            malformed.append(f"{name}: {len(cells)} cells against a header of {len(header)}")
    return malformed


def _documented_descriptions(path: Path) -> dict[tuple[str, str, str], list[str]]:
    """Return {(dataset, canonical name, original name): descriptions} for one provider docs page."""
    return _documented_column(path, "description")


def _documented_units(path: Path) -> dict[tuple[str, str, str], list[str]]:
    """Return {(dataset, canonical name, original name): unit cells} for one provider docs page."""
    return _documented_column(path, "unit")


def _documented_column(path: Path, column: str) -> dict[tuple[str, str, str], list[str]]:
    """Return {(dataset, canonical name, original name): cells of `column`} for one docs page.

    A list, not a string: a table can carry the same row twice, which is how `dwd/mosmix` hourly and
    `imgw/meteorology` daily came to hold a stale row beside its replacement. Overwriting would keep
    only the last of them and compare nothing against the rest, so the parser keeps all of them and
    `test_docs_parameter_tables_hold_the_parameters_the_dataset_declares` reports the repeat.

    Keyed by dataset as well: one page can document the same parameter in two datasets with
    different wording, e.g. daily ``snow_depth`` in climate_summary and in water_equivalent.

    The dataset comes from the ``name`` row of the section's own metadata table rather than from
    its ``###`` heading, for two reasons. `dwd/mosmix` heads its sections ``Small`` and ``Large``
    while the datasets are ``small`` and ``large``, so a heading-keyed parse matched nothing on
    that page and every row on it went unchecked. And `dwd/derived` monthly documents
    ``cooling_degreehours_13``, ``_16`` and ``_18`` in one section, saying so in that row, because
    the three carry identical parameters -- keying on it registers the rows under all three rather
    than forcing three copies of the table.

    Resolved in a first pass over the page, by `_section_datasets`, so that a section putting its
    ``#### parameters`` table before its ``#### metadata`` one -- valid, and equally good
    documentation -- is read the same way. A single pass could only use a ``name`` row it had already
    seen, which filed every row of such a section under the raw heading instead: exactly the sort of
    disagreement between the two parsers that sharing `_heading_datasets` was meant to end.
    """
    documented: dict[tuple[str, str, str], list[str]] = {}
    sections = _section_datasets(path)
    index = -1
    datasets: list[str] = []
    header = None
    for line in _prose_lines(path):
        if line.startswith("#"):
            if len(line) - len(line.lstrip("#")) == 3:
                # the section's own answer, by position; `_heading_datasets` still answers for the
                # `####` headings inside it and for anything that closes it
                index += 1
                datasets = sections[index]
            else:
                datasets = _heading_datasets(line, datasets)
            header = None
            continue
        if not line.startswith("|"):
            header = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and cells[0] == "name" and "original name" in cells:
            header = cells if column in cells else None
            continue
        if header is None or all(set(cell) <= {"-", ":"} for cell in cells) or len(cells) != len(header):
            # a row with more cells than its header reads every column shifted, so it is left to
            # `_malformed_parameter_tables` rather than compared as though the cells lined up
            continue
        name = re.sub(r"\{term\}`([^`]+)`", r"\1", cells[header.index("name")])
        for dataset in datasets or [_NO_SECTION]:
            key = (dataset, name, cells[header.index("original name")])
            documented.setdefault(key, []).append(cells[header.index(column)])
    return documented


def _resolution_pages() -> tuple[list[tuple[str, str, object, Path]], set[tuple[str, str]]]:
    """Return ([(provider, network, resolution model, docs page)], the networks that were skipped).

    The page is where it belongs, whether or not it is there -- `test_docs_cover_every_resolution`
    below is what says it is, so that the three tests after it can assume the pages exist and report
    mismatches rather than absences. `dwd/radar` and `dwd/alerts` carry no metadata model at all, so
    they declare no resolutions and do not appear here. `EXCLUDE_PROVIDER_NETWORKS` is applied for
    the same reason `test_data_coverage` applies it -- `dwd/radar` is deliberately undocumented, and
    it already has a `metadata/` package, so the day it grows a metadata model the two tests in this
    module would otherwise contradict each other and one of them would have to fail.

    A network whose request class needs a package this environment does not have is skipped, with a
    warning naming it: `dwd/derived` imports pandas, which arrives with the `export` extra, so a bare
    `uv sync` leaves its three resolutions unverifiable. CI installs the extras
    (`.github/workflows/install.sh testing`) and skips nothing. The skipped pairs come back beside the
    pages because a network that was never walked declares nothing here, and the page-side half of
    `test_docs_cover_every_resolution` would otherwise read its published pages as naming resolutions
    the model does not declare -- turning the skip into the very failure it exists to avoid.

    Only a genuinely missing third-party module is excused -- a `metadata.py` that makes
    `build_metadata_model` raise, or a mistyped intra-package import in a provider's `api.py`, has to
    surface here rather than quietly excusing that provider from all four tests below.
    `Wetterdienst.resolve` re-raises the `ModuleNotFoundError` as a plain `ImportError`, so the
    distinction is read off `__cause__` rather than off the type: catching `ModuleNotFoundError`
    catches nothing at all, and the skip this clause documents would have come out as four errors
    instead. `resolve` reports a name it cannot import as a missing dependency whatever it is, so a
    name inside this package is excluded here rather than trusted to its message.
    """
    from wetterdienst import Wetterdienst  # noqa: PLC0415

    pages: list[tuple[str, str, object, Path]] = []
    skipped: set[tuple[str, str]] = set()
    for provider, networks in Wetterdienst.registry.items():
        excluded = EXCLUDE_PROVIDER_NETWORKS.get(provider, [])
        if excluded == "*":
            continue
        for network in networks:
            if network in excluded:
                continue
            try:
                api = Wetterdienst(provider, network)
            except ImportError as error:
                cause = error.__cause__
                if not isinstance(cause, ModuleNotFoundError) or (cause.name or "").startswith("wetterdienst"):
                    raise
                if (provider, network) not in NETWORKS_NEEDING_AN_EXTRA:
                    msg = (
                        f"{provider}/{network} cannot be imported, so none of the docs tests read it: "
                        f"{error}. Add it to NETWORKS_NEEDING_AN_EXTRA if that is intended."
                    )
                    raise AssertionError(msg) from error
                warnings.warn(f"{provider}/{network} not checked against its docs: {error}", stacklevel=2)
                skipped.add((provider, network))
                continue
            metadata = getattr(api, "metadata", None)
            if metadata is None:
                if (provider, network) not in NETWORKS_WITHOUT_A_METADATA_MODEL:
                    msg = (
                        f"{provider}/{network} exposes no `metadata`, so none of the docs tests read it. "
                        f"Add it to NETWORKS_WITHOUT_A_METADATA_MODEL if that is intended."
                    )
                    raise AssertionError(msg)
                skipped.add((provider, network))
                continue
            pages.extend(
                (provider, network, resolution, Path(COVERAGE / provider / network / f"{resolution.name}.md"))
                for resolution in metadata
            )
    return pages, skipped


def _documented_resolutions() -> list[tuple[str, str, object, Path]]:
    """Return the pairs of `_resolution_pages` whose page exists."""
    return [entry for entry in _resolution_pages()[0] if entry[3].exists()]


def test_docs_cover_every_resolution() -> None:
    """Test that every resolution the model declares has a docs page.

    The three tests below pair a resolution with its page and can only check the pages that exist, so
    a resolution added without one would be compared by nothing at all -- the same silent skip as a
    page that parses to nothing, which they do report. Asserting the page here keeps that reported
    once, rather than once per test or not at all. The reverse holds for the same reason: those tests
    walk the model, so a page whose resolution the model no longer declares stays published and unread.
    """
    pages, skipped = _resolution_pages()
    errors = [
        f"{provider}/{network}: {path.relative_to(ROOT)} does not exist"
        for provider, network, _, path in pages
        if not path.exists()
    ]
    # and the other way, because the three tests below iterate the model: a page for a resolution the
    # model no longer declares stays published, stays linked from its network index -- which is all
    # `test_data_coverage` asks of it -- and is read by nothing at all
    declared = {path for _, _, _, path in pages}
    for page in sorted(COVERAGE.glob("*/*/*.md")):
        if page.name == "index.md" or page in declared:
            continue
        provider, network = page.parts[-3], page.parts[-2]
        excluded = EXCLUDE_PROVIDER_NETWORKS.get(provider, [])
        if excluded == "*" or network in excluded or (provider, network) in skipped:
            continue
        errors.append(f"{provider}/{network}: {page.relative_to(ROOT)} names a resolution the model does not declare")
    assert not errors, "\n".join(errors)


def test_docs_parameter_descriptions_match_the_model() -> None:
    """Test that the docs description column agrees with the model.

    The model is the source: these descriptions used to live only in the markdown tables, where the
    REST API, MCP and CLI could not reach them and where the two copies drifted apart in both
    directions. Editing a description in the docs alone now fails here.
    """
    mismatches = []
    for provider, network, resolution, path in _documented_resolutions():
        documented = _documented_descriptions(path)
        for dataset in resolution:
            for parameter in dataset.parameters:
                # `quality` is compared like anything else: the presence test below requires the 25
                # rows that exist to be keyed right, so leaving their text alone would have been the
                # one thing about them nothing checked
                for shown in documented.get((dataset.name, parameter.name, parameter.name_original), []):
                    tag = f"{provider}/{network}/{resolution.name} {parameter.name}"
                    # a blank cell and a "-" both say "no text here", so they are read the same way --
                    # and either is still compared where the model has a description, which is the
                    # escape this replaced: no row writes either today and no parameter lacks a
                    # description, so waving them through could only have hidden one being dropped
                    if shown in ("", "-") and not parameter.description:
                        continue
                    if not parameter.description:
                        mismatches.append(f"{tag}: the page describes it, the model does not")
                        continue
                    if shown.rstrip(".") != parameter.description.rstrip("."):
                        mismatches.append(f"{tag}: docs {shown!r} != model {parameter.description!r}")
    assert not mismatches, "\n".join(_capped(mismatches, 20, "the report"))


# Spellings a page uses where the model names the unit differently. All four are questions of notation
# rather than of quantity, and GH-1980 is where they are settled: `kg/m²` and `mm` are equal for water
# and `kg/m²` is what DWD's MOSMIX documentation writes; `-` reads as "no unit" for a coded value whose
# model symbol is the unhelpful `sign [0..95]`; the docs write a Greek mu where the model writes a
# micro sign; and the model's Beaufort symbol is lower case. Listed rather than tolerated wholesale so
# that a cell naming a different *quantity* -- `mm/s` where the model says `millimeter_per_hour`, a
# factor of 3600, or `Bft` where it says `meter_per_second` -- fails instead of hiding among them. The
# four cover all 60 cells that disagree; the three just named were the only wrong quantities.
_UNIT_SPELLINGS = frozenset(
    [
        ("kg/m²", "millimeter"),
        ("-", "significant_weather"),
        ("\u03bcS/cm", "microsiemens_per_centimeter"),
        ("Bft", "beaufort"),
    ],
)


def test_docs_parameter_units_name_the_quantity_the_model_declares() -> None:
    """Test that a documented unit is the model's unit, by name or by symbol or by a known spelling.

    The `unit` column was hand-written and compared by nothing, which is how three cells came to name a
    different quantity than the model declares. `dwd/observation` monthly and annual wrote `Bft` for
    `wind_gust_max`, which the model declares `meter_per_second` -- copied, it looks like, from the
    `wind_force_beaufort` row above, and the values are 12 to 28, so the model is right. `dwd/road`
    15_minutes wrote `mm/s` against a declared `millimeter_per_hour`, and there the *model* is the side
    under question: that parser labels the BUFR units of what it decodes, BUFR gives
    `intensityOfPrecipitation` as `kg m-2 s-1`, and the delivered values top out at 0.006, which is
    absurd as mm/h. GH-1984 carries it. This test follows the model either way, so whoever settles it
    changes one declaration and the page follows -- it is not a claim that the page was the defect.

    Accepting `_UNIT_SPELLINGS` alongside the model's own name and symbol is what lets this run without
    reflowing 60 cells first: those four notations are real editorial choices for GH-1980 to settle,
    and holding them in a list keeps the check honest about which disagreements are tolerated. What it
    does not tolerate is a cell naming a different quantity, which is the only kind that misleads a
    reader about the numbers.
    """
    from wetterdienst.model.unit import UnitConverter  # noqa: PLC0415

    converter = UnitConverter()
    wrong = []
    for provider, network, resolution, path in _documented_resolutions():
        documented = _documented_units(path)
        for dataset in resolution:
            for parameter in dataset.parameters:
                key = (dataset.name, parameter.name, parameter.name_original)
                unit = converter.get_unit(parameter.unit, parameter.unit_type)
                for shown in documented.get(key, []):
                    if shown in (unit.name, unit.symbol) or (shown, parameter.unit) in _UNIT_SPELLINGS:
                        continue
                    wrong.append(
                        f"{provider}/{network}/{resolution.name}/{dataset.name} {parameter.name}: "
                        f"docs {shown!r}, model {unit.name!r} ({unit.symbol!r})",
                    )
    assert not wrong, "\n".join(_capped(wrong, 20, "the report"))


def test_docs_descriptions_do_not_misstate_a_parameter_count() -> None:
    """Test that a description naming a parameter count names the number the dataset declares.

    `dwd/mosmix` hourly describes `small` and `large` by how many parameters they carry, and a count
    written into prose is exactly the fact whose drift set this change off: the page said 115 where the
    model declared 122, for long enough that three other pages still say it. Tying the number to
    `len(dataset.parameters)` is what stops the same sentence going stale again -- adding a parameter to
    `large` would otherwise leave `discover`, the REST API, MCP and the page all saying 122 of 123, with
    every other test green. Two descriptions name a count today.
    """
    wrong = []
    # every declared resolution, not only the documented ones: the claim is about the model alone, so
    # gating it on a page existing would let deleting `dwd/mosmix/hourly.md` stop the only two
    # count-bearing descriptions being checked at all
    for provider, network, resolution, _ in _resolution_pages()[0]:
        for dataset in resolution:
            for count in re.findall(r"(\d+) parameters", dataset.description or ""):
                if int(count) != len(dataset.parameters):
                    wrong.append(
                        f"{provider}/{network}/{resolution.name}/{dataset.name}: the description says "
                        f"{count} parameters, the dataset declares {len(dataset.parameters)}",
                    )
    assert not wrong, "\n".join(_capped(wrong, 20, "the report"))


def _metadata_tables(path: Path) -> Iterator[dict[str, str]]:
    """Yield the property/value rows of each "#### metadata" table on one provider docs page.

    ``name`` starts as the enclosing ``###`` heading and is replaced by the table's own ``name``
    row where it has one, which is the key the model declares. `dwd/mosmix` heads its sections
    ``Small`` and ``Large`` against datasets ``small`` and ``large``, so keying on the heading
    matched nothing there and left the whole page uncompared.

    The table has to sit under the section's own ``metadata`` heading. Taking any property/value table
    inside a ``###`` section made a second one -- a ``#### source file`` or ``#### periods``, both
    plausible -- read as a repeated metadata table, so correct documentation was reported as "carries 2
    metadata tables" and its rows compared against the model besides. All 238 such tables in the tree
    are under that heading today, so nothing is lost by asking.

    Which section a table belongs to is `_section_datasets`' answer, taken by position, rather than this
    walk's own reading of the heading. Reading it here as well is how the two came to disagree: this one
    had no notion of the ``## datasets`` block, so a ``#### metadata`` table under a prose ``###``
    elsewhere on the page was read as a dataset -- reported as one the model does not declare, or, if
    the prose heading reused a real dataset's name, as that dataset carrying two metadata tables. Taking
    the answer from one place is the invariant the rest of this module is built on.
    """
    sections = _section_datasets(path)
    index = -1
    datasets: list[str] = []
    under_metadata = False
    prop: dict[str, str] | None = None
    for line in _prose_lines(path):
        if not line.startswith("|"):
            # flushed before the heading moves on, so a table not separated from the next `###` by a
            # blank line is still yielded under the dataset it belongs to
            if prop is not None:
                # under a sentinel where no dataset section encloses it, so that a `#### metadata`
                # table under a prose `###` is reported rather than dropped -- the parameter rows in
                # that position already are. Its own `name` row still wins, so one naming a real
                # dataset is reported as that dataset's second description rather than as an orphan
                yield {"name": datasets[0] if datasets else _NO_SECTION, **prop}
            prop = None
            if line.startswith("#"):
                if len(line) - len(line.lstrip("#")) == 3:
                    index += 1
                    datasets = sections[index]
                else:
                    datasets = _heading_datasets(line, datasets)
                under_metadata = _is_metadata_heading(line)
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[:1] == ["property"]:
            # `index >= 0` means a `###` has opened, which keeps the page's own resolution-level
            # `## metadata` table out: it sits above them all and belongs to no dataset
            prop = {} if under_metadata and index >= 0 else None
        elif prop is not None and len(cells) >= 2 and not all(set(cell) <= {"-", ":"} for cell in cells):
            prop[cells[0]] = cells[1]
    if prop is not None:
        yield {"name": datasets[0] if datasets else _NO_SECTION, **prop}


def _documented_resolution_description(path: Path) -> str | None:
    """Return the ``## metadata`` description a provider docs page opens with, if it has one.

    The resolution's own table, above the first ``###`` dataset section -- which is why
    `_metadata_tables` skips it, and why nothing compared it until now. `RESOLUTION_DESCRIPTIONS`
    carries the model side, so this is the last of the three description tables to be held in both
    directions; three pages have one today.

    Read from under the page's ``## metadata`` heading rather than from any property table above the
    first section, and reset per table, so that a second one added later -- under a ``## Notes`` or
    ``## periods``, say -- is not compared against the resolution's description and the author sent to
    the wrong table.
    """
    prop: dict[str, str] = {}
    under_metadata = False
    in_table = False
    for line in _prose_lines(path):
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            if level == 3:
                break
            under_metadata = level == 2 and _is_metadata_heading(line)
            in_table = False
            continue
        if not line.startswith("|"):
            in_table = False
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[:1] == ["property"]:
            in_table = under_metadata
            if in_table:
                # reset on entering a table this reads, never on skipping one -- resetting on every
                # property table let a later `## Notes` table wipe the description it must not read
                prop = {}
            continue
        if in_table and len(cells) >= 2 and not all(set(cell) <= {"-", ":"} for cell in cells):
            prop[cells[0]] = cells[1]
    return prop.get("description")


def test_docs_resolution_descriptions_match_the_model() -> None:
    """Test that the ``## metadata`` description a page opens with agrees with the model.

    Same contract as the dataset and parameter tables, for the one description table neither reaches:
    the resolution's own, which sits above the first dataset section. Held in both directions, so the
    text cannot drift and neither side can quietly drop it. Three pages carry one, and the model
    carries the same three.
    """
    mismatches = []
    for provider, network, resolution, path in _documented_resolutions():
        tag = f"{provider}/{network}/{resolution.name}"
        shown = _documented_resolution_description(path)
        model = resolution.description
        # a `-` says "no text here", as on the dataset and parameter sides
        if shown in (None, "", "-") and not model:
            continue
        if not shown:
            mismatches.append(f"{tag}: the model describes the resolution, the page does not")
        elif not model:
            mismatches.append(f"{tag}: the page describes the resolution, the model does not")
        else:
            text = re.sub(r"\s*\(\[[^\]]+\]\([^)]*\)\)\s*$", "", shown).strip().rstrip(".")
            if text != model.rstrip("."):
                mismatches.append(f"{tag}: docs {text!r} != model {model!r}")
    assert not mismatches, "\n".join(_capped(mismatches, 20, "the report"))


def _documented_dataset_sections(path: Path) -> dict[str, int]:
    """Return {dataset: how many "#### metadata" tables name it} for one provider docs page.

    Separate from the descriptions below because a stale section is worth reporting whether or not it
    carries a `description` row, and `dwd/derived` monthly legitimately names three datasets in one
    table, which counts as one section for each of them rather than three for any.
    """
    counts: dict[str, int] = {}
    for table in _metadata_tables(path):
        for dataset in table["name"].split(","):
            counts[dataset.strip()] = counts.get(dataset.strip(), 0) + 1
    return counts


def _documented_dataset_descriptions(path: Path) -> dict[str, list[tuple[str, bool]]]:
    """Return {dataset: [(description, came from a table naming several datasets)]} for one page.

    A list for the same reason `_documented_descriptions` returns one: a page can carry two sections
    for one dataset, and overwriting would leave only the last of them compared while the other went
    on being rendered. The repeat is reported by the test below.

    The flag rides with each description rather than with the dataset, because the exemption belongs
    to the table. `dwd/derived` monthly documents `cooling_degreehours_13`, `_16` and `_18` in one
    section and says so: the three carry identical parameters and differ only in the reference
    temperature, so one `description` cell cannot equal three model descriptions, and the model is
    right to carry one per dataset since `discover`, the REST API and MCP report them one at a time.
    Exempting the dataset *name* instead would have let a dedicated `### cooling_degreehours_13`
    section go uncompared too, on a page that documented it both ways -- the silent skip this module
    exists to close, let back in by the side door.
    """
    documented: dict[str, list[tuple[str, bool]]] = {}
    for table in _metadata_tables(path):
        if not table.get("description"):
            continue
        names = [dataset.strip() for dataset in table["name"].split(",")]
        for dataset in names:
            documented.setdefault(dataset, []).append((table["description"], len(names) > 1))
    return documented


def _dataset_description_problems(
    resolution: object,
    documented: dict[str, list[tuple[str, bool]]],
    dataset: object,
) -> Iterator[str]:
    """Yield what is wrong between one dataset's model description and the page's, if anything.

    Presence in both directions, then the text of each description the page carries for it -- except
    where that description's table names several datasets, which `_shared_description_repeat` answers
    instead.
    """
    shown = documented.get(dataset.name, [])
    # a `-` cell says "no text here", as it does for a parameter row, so a dataset the model does not
    # describe and the page writes `-` for is not reported as described by the page. Where the model
    # does describe it, the `-` is still compared and still fails, again as on the parameter side
    substantive = [text for text, _ in shown if text not in ("", "-")]
    if not dataset.description and not substantive:
        return
    if not shown:
        yield "the model describes it, the page does not"
        return
    if not dataset.description:
        yield "the page describes it, the model does not"
        return
    for shown_text, from_shared_table in shown:
        if from_shared_table:
            yield from _shared_description_problems(resolution, documented, shown_text, dataset.name)
            continue
        text = re.sub(r"\s*\(\[[^\]]+\]\([^)]*\)\)\s*$", "", shown_text).strip().rstrip(".")
        if text != dataset.description.rstrip("."):
            yield f"docs {text!r} != model {dataset.description!r}"


def _distinguishing_tokens(names: list[str]) -> list[str]:
    """Return what is left of each name once the part they all share is removed.

    `cooling_degreehours_13`, `_16` and `_18` distinguish themselves by `13`, `16` and `18`. Used to
    ask whether a cell documenting several datasets at once names each of them.

    The shared part is cut back to the last `_` before it ends, so that the token is the whole segment
    that differs rather than however many characters happen to be left: those three share the prefix
    `cooling_degreehours_1`, and `3`, `6` and `8` would be matched by almost any prose.
    """
    head = os.path.commonprefix(names)
    head = head[: head.rfind("_") + 1]
    tail = os.path.commonprefix([name[::-1] for name in names])[::-1]
    tail = tail[tail.find("_") :] if "_" in tail else ""
    return [name[len(head) : len(name) - len(tail)] for name in names]


def _shared_description_problems(
    resolution: object,
    documented: dict[str, list[tuple[str, bool]]],
    text: str,
    first_of: str,
) -> Iterator[str]:
    """Yield what is wrong with one description cell that documents several datasets, if anything.

    Its text cannot equal any single one of their model descriptions, so it is not compared against
    them -- but two things are still asked of it. The model's descriptions have to differ from each
    other, a copied entry being the likeliest error the exemption hides. And the cell has to name what
    tells the datasets apart -- `13`, `16` and `18` for the three `cooling_degreehours_*` -- so that a
    blurb saying "13, 16 and 20" is reported rather than read. What stays unchecked is the prose
    between those tokens, which is the price of documenting several datasets in one section and the
    reason this exemption is kept as narrow as it is.

    Reported once, from the first of the datasets, rather than once per dataset.
    """
    sharing = [
        dataset for dataset in resolution if dataset.description and (text, True) in documented.get(dataset.name, [])
    ]
    if not sharing or sharing[0].name != first_of:
        return
    names = [dataset.name for dataset in sharing]
    tokens = _distinguishing_tokens(names)
    described = [dataset.description for dataset in sharing]
    if len(set(described)) != len(described):
        yield f"{names} are documented by one description and the model repeats one of theirs"
    missing = [token for token in tokens if token and token not in text]
    if missing:
        yield f"{names} are documented by one description that does not name {missing}"
    # and each model description has to name its own dataset's token. Without this the exemption asked
    # only that the three differ from each other and that the docs cell list all three, so moving the
    # 18-degree dataset to the 20-degree sentence satisfied both and nothing else reads these
    for dataset, token in zip(sharing, tokens, strict=True):
        if token and token not in dataset.description:
            yield f"{dataset.name} is described as {dataset.description!r}, which does not name {token!r}"


def test_docs_dataset_descriptions_match_the_model() -> None:
    """Test that the docs dataset metadata tables agree with the model, and are there at all.

    Same reason as the parameter descriptions: the text used to live only in markdown. The docs
    append a "([details](url))" pointer that is page formatting rather than part of the
    description, so it is ignored here.

    Presence is asserted in both directions, because comparing only the datasets described on both
    sides means either side alone going unread. A deleted `description` row -- or a whole missing
    `#### metadata` table -- was answered by comparing nothing, and so was text living only in the
    markdown, where the REST API, MCP and CLI never see it: `dwd/mosmix` hourly described `large` as
    "Local forecast of 115 parameters" on a page nothing compared, while the model declares 122. All
    217 described datasets now document it and vice versa; the 54 that document none describe none
    either, so nothing is demanded that does not exist.
    """
    mismatches = []
    for provider, network, resolution, path in _documented_resolutions():
        documented = _documented_dataset_descriptions(path)
        sections = _documented_dataset_sections(path)
        for dataset in resolution:
            tag = f"{provider}/{network}/{resolution.name}/{dataset.name}"
            # counted before the presence branches, so a repeat is reported for the 54 datasets no
            # description names as much as for the 217 that do -- and counted from the sections rather
            # than the descriptions, so a second table with no `description` row, which
            # `_documented_dataset_descriptions` drops, is reported as well
            if sections.get(dataset.name, 0) > 1:
                mismatches.append(f"{tag}: carries {sections[dataset.name]} metadata tables")
            mismatches.extend(
                f"{tag}: {problem}" for problem in _dataset_description_problems(resolution, documented, dataset)
            )
    assert not mismatches, "\n".join(_capped(mismatches, 20, "the report"))


# `quality` itself is declared by 58 datasets and documented by 25, so a *declared* `quality` need
# not be documented -- that inconsistency is real and it is its own change. The exclusion stops
# there rather than covering every `quality*` name, to match what the descriptions test above skips:
# the other five (`quality_general`, `quality_precipitation`, `quality_wind`, `quality_3`,
# `quality_6`) are all documented, and holding them here is what says so.
#
# It is applied to the declared side alone, because the gap runs one way: no page carries a `quality`
# row for a dataset that has no quality flag, and exempting the documented side too would let one in
# -- along with a wrong `name_original` on any of those 25 rows, which the descriptions test skips as
# well, so nothing else would check them at all.
def _declared_to_document(keys: Iterable[tuple[str, str, str]]) -> set[tuple[str, str, str]]:
    """Drop the plain `quality` rows from a set of (dataset, name, original name) keys."""
    return {key for key in keys if key[1] != "quality"}


def test_docs_parameter_tables_hold_the_parameters_the_dataset_declares() -> None:
    """Test that a documented parameter exists and a declared parameter is documented.

    The descriptions test compares the *text* of rows that appear on both sides and says nothing
    about a row appearing on one side alone, in either direction. So a table could advertise a
    parameter no request can ask for -- `dwd/dmo` hourly documented `cloud_base_convective` and
    `cloud_cover_below_7km` under `icon_eu`, which the model declares for `icon` alone, and asking
    for either raised `NoParametersFoundError` while the docs said it was there (GH-1971) -- or
    quietly omit one a request can, which is how `imgw/meteorology` monthly `synop` came to
    document none of its four precipitation parameters.

    A row written twice is reported too, because the parse keys on (dataset, name, original name) and
    would otherwise keep only the last of them -- which is exactly the shape of the two defects above,
    a stale row left in place beside the one that replaced it.

    Both directions are asserted here, so neither survives a parameter rename, a dataset split or
    a copied table again.
    """
    errors: list[str] = []
    for provider, network, resolution, path in _documented_resolutions():
        documented = _documented_descriptions(path)
        tag = f"{provider}/{network}/{resolution.name}"
        malformed = [f"{tag}: {problem}" for problem in _malformed_parameter_tables(path)]
        if not documented:
            # collected rather than asserted, so one unparseable page does not hide every other
            # page's findings -- and skipped rather than compared, because otherwise it contributes
            # one error per declared parameter and fills the report the same way an abort emptied it
            # the cause first, where there is one: a page whose only table is the broken one used to
            # report nothing but the symptom, which is the message this check exists to replace. Capped
            # like the path below, since one page with an extra header column reports every row of it
            errors.extend(_capped([*malformed, f"{tag}: {path.name} parses to no parameter row at all"], 10, tag))
            continue
        declared = {
            (dataset.name, parameter.name, parameter.name_original)
            for dataset in resolution
            for parameter in dataset.parameters
        }
        found = []
        # unioned with the metadata tables, because a section left behind when its dataset was dropped
        # from the model need not still carry a `#### parameters` table, and the description test
        # walks the model's datasets so it never reaches one
        sections = (
            {key[0] for key in documented}
            | set(_documented_dataset_sections(path))
            # and the headings, because both of the above are derived from tables: a `###` section
            # carrying neither a `#### metadata` nor a `#### parameters` table named no dataset at all,
            # so a page could advertise one no request can ask for -- the GH-1971 defect this test
            # exists to report -- and be read by nothing
            | {name for entry in _section_datasets(path) for name in entry}
        )
        found.extend(malformed)
        for orphan in sorted(sections - {dataset.name for dataset in resolution}):
            if orphan == _NO_SECTION:
                found.append(f"{tag}: has a table that no `###` dataset section encloses")
            else:
                found.append(f"{tag}: documents a dataset {orphan!r} that the model does not declare")
        for dataset, name, name_original in sorted(set(documented) - declared):
            found.append(f"{tag}/{dataset}: documents {name}/{name_original!r}, which it does not declare")
        for dataset, name, name_original in sorted(_declared_to_document(declared) - set(documented)):
            found.append(f"{tag}/{dataset}: declares {name}/{name_original!r}, which it does not document")
        for (dataset, name, name_original), shown in sorted(documented.items()):
            if len(shown) > 1:
                found.append(f"{tag}/{dataset}: documents {name}/{name_original!r} {len(shown)} times")
        errors.extend(_capped(found, 10, f"{tag}"))
    assert not errors, "\n".join(_capped(errors, 40, "the report"))


def _capped(lines: list[str], limit: int, what: str) -> list[str]:
    """Return at most `limit` of `lines`, saying how many were left out.

    One page can produce an error per parameter on both sides -- a single mistyped dataset `name` row
    does, since nothing then matches -- which is enough to push every page after it past a flat cap
    and report a corpus-wide problem as a local one. So each page is capped before the report is, and
    the count is stated either way: a truncated list that does not say it was truncated reads exactly
    like a complete one.
    """
    if len(lines) <= limit:
        return lines
    return [*lines[:limit], f"{what}: ... and {len(lines) - limit} more"]
