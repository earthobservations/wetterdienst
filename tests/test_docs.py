# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the documentation."""

import doctest
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


def _prose_lines(path: Path) -> Iterator[str]:
    """Yield the lines of a docs page that sit outside a fenced code block.

    A ``#`` comment inside a fence is not a heading, and reading one as a level-1 heading would close
    the dataset section it sits in -- dropping every row below it out of its dataset, so that the
    descriptions test silently stops comparing them. Which is the skip this module exists to stop,
    and the reason the fence is stripped here rather than in each parser.
    """
    fence: tuple[str, int] | None = None
    for line in path.read_text(encoding="utf8").splitlines():
        marker = re.match(r"\s*(`{3,}|~{3,})", line)
        if marker:
            char, length = marker.group(1)[0], len(marker.group(1))
            if fence is None:
                fence = (char, length)
            elif char == fence[0] and length >= fence[1]:
                # a closing fence has to be at least as long as the one it closes, so a ``` line
                # inside a ````-opened block is content rather than the end of it
                fence = None
            continue
        if fence is None:
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


def _heading_datasets(line: str, current: list[str]) -> list[str]:
    """Name the datasets a heading opens, for the two parsers below.

    ``### <name>`` opens a dataset section, ``#### parameters`` and the like stay inside the one it
    is in, and anything shallower closes it -- a page carries its own resolution-level ``##
    metadata`` table, whose rows belong to no dataset. Shared so that the two parsers cannot answer
    this differently, which is how one of them came to read that table as a dataset.
    """
    level = len(line) - len(line.lstrip("#"))
    if level == 3:
        return [line[4:].strip()]
    if level >= 4:
        return current
    return []


def _documented_descriptions(path: Path) -> dict[tuple[str, str, str], list[str]]:
    """Return {(dataset, canonical name, original name): descriptions} for one provider docs page.

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
    """
    documented: dict[tuple[str, str, str], list[str]] = {}
    datasets: list[str] = []
    header = None
    in_metadata = False
    for line in _prose_lines(path):
        if line.startswith("#"):
            datasets, header, in_metadata = _heading_datasets(line, datasets), None, False
            continue
        if not line.startswith("|"):
            header, in_metadata = None, False
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[:1] == ["property"]:
            in_metadata = bool(datasets)
            continue
        if cells and cells[0] == "name" and "original name" in cells:
            header, in_metadata = (cells if "description" in cells else None), False
            continue
        if in_metadata:
            if cells[:1] == ["name"] and len(cells) >= 2:
                datasets = [name.strip() for name in cells[1].split(",")]
            continue
        if header is None or all(set(cell) <= {"-", ":"} for cell in cells) or len(cells) < len(header):
            continue
        name = re.sub(r"\{term\}`([^`]+)`", r"\1", cells[header.index("name")])
        for dataset in datasets:
            key = (dataset, name, cells[header.index("original name")])
            documented.setdefault(key, []).append(cells[header.index("description")])
    return documented


def _resolution_pages() -> Iterator[tuple[str, str, object, Path]]:
    """Yield (provider, network, resolution model, docs page) for every resolution the model declares.

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
    (`.github/workflows/install.sh testing`) and skips nothing. Only `ModuleNotFoundError` is excused
    -- a `metadata.py` that makes `build_metadata_model` raise, or a typo in a provider's `api.py`,
    has to surface here rather than quietly excusing that provider from all four tests below.
    """
    from wetterdienst import Wetterdienst  # noqa: PLC0415

    for provider, networks in Wetterdienst.registry.items():
        excluded = EXCLUDE_PROVIDER_NETWORKS.get(provider, [])
        if excluded == "*":
            continue
        for network in networks:
            if network in excluded:
                continue
            try:
                api = Wetterdienst(provider, network)
            except ModuleNotFoundError as error:
                warnings.warn(
                    f"{provider}/{network} not checked against its docs: {error}",
                    stacklevel=2,
                )
                continue
            metadata = getattr(api, "metadata", None)
            if metadata is None:
                continue
            for resolution in metadata:
                yield provider, network, resolution, Path(COVERAGE / provider / network / f"{resolution.name}.md")


def _documented_resolutions() -> list[tuple[str, str, object, Path]]:
    """Return the pairs of `_resolution_pages` whose page exists."""
    return [entry for entry in _resolution_pages() if entry[3].exists()]


def test_docs_cover_every_resolution() -> None:
    """Test that every resolution the model declares has a docs page.

    The three tests below pair a resolution with its page and can only check the pages that exist, so
    a resolution added without one would be compared by nothing at all -- the same silent skip as a
    page that parses to nothing, which they do report. Asserting the page here keeps that reported
    once, rather than once per test or not at all.
    """
    missing = [
        f"{provider}/{network}: {path.relative_to(ROOT)} does not exist"
        for provider, network, _, path in _resolution_pages()
        if not path.exists()
    ]
    assert not missing, "\n".join(missing)


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
                if parameter.name == "quality" or not parameter.description:
                    continue
                for shown in documented.get((dataset.name, parameter.name, parameter.name_original), []):
                    if shown in ("", "-"):
                        continue
                    if shown.rstrip(".") != parameter.description.rstrip("."):
                        mismatches.append(
                            f"{provider}/{network}/{resolution.name} {parameter.name}: "
                            f"docs {shown!r} != model {parameter.description!r}",
                        )
    assert not mismatches, "\n".join(mismatches[:10])


def _metadata_tables(path: Path) -> Iterator[dict[str, str]]:
    """Yield the property/value rows of each "#### metadata" table on one provider docs page.

    ``name`` starts as the enclosing ``###`` heading and is replaced by the table's own ``name``
    row where it has one, which is the key the model declares. `dwd/mosmix` heads its sections
    ``Small`` and ``Large`` against datasets ``small`` and ``large``, so keying on the heading
    matched nothing there and left the whole page uncompared.
    """
    datasets: list[str] = []
    prop: dict[str, str] | None = None
    for line in _prose_lines(path):
        if not line.startswith("|"):
            # flushed before the heading moves on, so a table not separated from the next `###` by a
            # blank line is still yielded under the dataset it belongs to
            if prop is not None and datasets:
                yield {"name": datasets[0], **prop}
            prop = None
            if line.startswith("#"):
                datasets = _heading_datasets(line, datasets)
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[:1] == ["property"]:
            prop = {} if datasets else None
        elif prop is not None and len(cells) >= 2 and not all(set(cell) <= {"-", ":"} for cell in cells):
            prop[cells[0]] = cells[1]
    if prop is not None and datasets:
        yield {"name": datasets[0], **prop}


def _documented_dataset_descriptions(path: Path) -> dict[str, list[str]]:
    """Return {dataset: descriptions} from the "#### metadata" tables of one provider docs page.

    A list for the same reason `_documented_descriptions` returns one: a page can carry two sections
    for one dataset, and overwriting would leave only the last of them compared while the other went
    on being rendered. The repeat is reported by the test below.
    """
    documented: dict[str, list[str]] = {}
    for table in _metadata_tables(path):
        if not table.get("description"):
            continue
        for dataset in table["name"].split(","):
            documented.setdefault(dataset.strip(), []).append(table["description"])
    return documented


def test_docs_dataset_descriptions_match_the_model() -> None:
    """Test that the docs dataset metadata tables agree with the model, and are there at all.

    Same reason as the parameter descriptions: the text used to live only in markdown. The docs
    append a "([details](url))" pointer that is page formatting rather than part of the
    description, so it is ignored here.

    A dataset the model describes has to carry a documented description, because comparing only the
    rows that appear on both sides means a deleted `description` row -- or a whole missing `####
    metadata` table -- is answered by comparing nothing, which is the one direction the parameter
    presence test does not reach. All 211 described datasets document it today; the 54 that document
    none describe none in the model either, so nothing is being demanded that does not exist.
    """
    mismatches = []
    for provider, network, resolution, path in _documented_resolutions():
        documented = _documented_dataset_descriptions(path)
        for dataset in resolution:
            tag = f"{provider}/{network}/{resolution.name}/{dataset.name}"
            shown = documented.get(dataset.name, [])
            if not dataset.description:
                continue
            if not shown:
                mismatches.append(f"{tag}: the model describes it, the page does not")
                continue
            if len(shown) > 1:
                mismatches.append(f"{tag}: carries {len(shown)} metadata tables")
            for text in shown:
                text = re.sub(r"\s*\(\[[^\]]+\]\([^)]*\)\)\s*$", "", text).strip().rstrip(".")
                if text != dataset.description.rstrip("."):
                    mismatches.append(f"{tag}: docs {text!r} != model {dataset.description!r}")
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
        if not documented:
            # collected rather than asserted, so one unparseable page does not hide every other
            # page's findings -- and skipped rather than compared, because otherwise it contributes
            # one error per declared parameter and fills the report the same way an abort emptied it
            errors.append(f"{tag}: {path.name} parses to no parameter row at all")
            continue
        declared = {
            (dataset.name, parameter.name, parameter.name_original)
            for dataset in resolution
            for parameter in dataset.parameters
        }
        found = []
        sections = {key[0] for key in documented}
        for orphan in sorted(sections - {dataset.name for dataset in resolution}):
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
