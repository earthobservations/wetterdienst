# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the documentation."""

import doctest
import re
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


def _parameter_rows(path: Path) -> list[list[str]]:
    """Extract the rows of every parameter table in a provider docs page."""
    lines = path.read_text(encoding="utf8").splitlines()
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


def _documented_descriptions(path: Path) -> dict[tuple[str, str, str], str]:
    """Return {(dataset, canonical name, original name): description} for one provider docs page.

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
    documented = {}
    datasets: list[str] = []
    header = None
    in_metadata = False
    for line in path.read_text(encoding="utf8").splitlines():
        if line.startswith("### "):
            datasets, header, in_metadata = [line[4:].strip()], None, False
            continue
        if not line.startswith("|"):
            header, in_metadata = None, False
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[:1] == ["property"]:
            in_metadata = True
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
            documented[dataset, name, cells[header.index("original name")]] = cells[header.index("description")]
    return documented


def _documented_resolutions() -> list[tuple[str, str, object, Path]]:
    """Yield (provider, network, resolution model, docs page) for every documented resolution."""
    from wetterdienst import Wetterdienst  # noqa: PLC0415

    found = []
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            try:
                api = Wetterdienst(provider, network)
            except Exception:  # noqa: BLE001, S112
                continue
            metadata = getattr(api, "metadata", None)
            if metadata is None:
                continue
            for resolution in metadata:
                path = Path(COVERAGE / provider / network / f"{resolution.name}.md")
                if path.exists():
                    found.append((provider, network, resolution, path))
    return found


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
                shown = documented.get((dataset.name, parameter.name, parameter.name_original))
                if shown in (None, "", "-"):
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
    heading = ""
    prop: dict[str, str] | None = None
    for line in path.read_text(encoding="utf8").splitlines():
        if line.startswith("### ") and not line.startswith("#### "):
            heading = line[4:].strip()
        if not line.startswith("|"):
            if prop is not None:
                yield {"name": heading, **prop}
                prop = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[:1] == ["property"]:
            prop = {}
        elif prop is not None and len(cells) >= 2 and not all(set(cell) <= {"-", ":"} for cell in cells):
            prop[cells[0]] = cells[1]
    if prop is not None:
        yield {"name": heading, **prop}


def _documented_dataset_descriptions(path: Path) -> dict[str, str]:
    """Return {dataset: description} from the "#### metadata" tables of one provider docs page."""
    documented = {}
    for table in _metadata_tables(path):
        if not table.get("description"):
            continue
        for dataset in table["name"].split(","):
            documented[dataset.strip()] = table["description"]
    return documented


def test_docs_dataset_descriptions_match_the_model() -> None:
    """Test that the docs dataset metadata tables agree with the model.

    Same reason as the parameter descriptions: the text used to live only in markdown. The docs
    append a "([details](url))" pointer that is page formatting rather than part of the
    description, so it is ignored here.
    """
    mismatches = []
    for provider, network, resolution, path in _documented_resolutions():
        documented = _documented_dataset_descriptions(path)
        for dataset in resolution:
            shown = documented.get(dataset.name)
            if not shown or not dataset.description:
                continue
            shown = re.sub(r"\s*\(\[[^\]]+\]\([^)]*\)\)\s*$", "", shown).strip().rstrip(".")
            if shown != dataset.description.rstrip("."):
                mismatches.append(
                    f"{provider}/{network}/{resolution.name}/{dataset.name}: "
                    f"docs {shown!r} != model {dataset.description!r}",
                )
    assert not mismatches, "\n".join(mismatches[:10])


# `quality` itself is declared by 58 datasets and documented by 25, so presence is not checked for
# it -- that inconsistency is real and it is its own change. The exclusion stops there rather than
# covering every `quality*` name, to match what the descriptions test above skips: the other five
# (`quality_general`, `quality_precipitation`, `quality_wind`, `quality_3`, `quality_6`) are all
# documented, and holding them here is what says so.
def _substantive(keys: Iterable[tuple[str, str, str]]) -> set[tuple[str, str, str]]:
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

    Both directions are asserted here, so neither survives a parameter rename, a dataset split or
    a copied table again.
    """
    errors = []
    for provider, network, resolution, path in _documented_resolutions():
        documented = _documented_descriptions(path)
        tag = f"{provider}/{network}/{resolution.name}"
        if not documented:
            # collected rather than asserted, so one unparseable page does not hide every other
            # page's findings -- and the two comparisons below name each parameter it lost anyway
            errors.append(f"{tag}: {path.name} parses to no parameter row at all")
        declared = _substantive(
            (dataset.name, parameter.name, parameter.name_original)
            for dataset in resolution
            for parameter in dataset.parameters
        )
        sections = {key[0] for key in documented}
        for orphan in sorted(sections - {dataset.name for dataset in resolution}):
            errors.append(f"{tag}: documents a dataset {orphan!r} that the model does not declare")
        for dataset, name, name_original in sorted(_substantive(documented) - declared):
            errors.append(f"{tag}/{dataset}: documents {name}/{name_original!r}, which it does not declare")
        for dataset, name, name_original in sorted(declared - set(documented)):
            errors.append(f"{tag}/{dataset}: declares {name}/{name_original!r}, which it does not document")
    assert not errors, "\n".join(errors[:20])
