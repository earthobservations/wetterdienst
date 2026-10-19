# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The command line, the Python surface, the MCP tools and the parameters offer all the last release offered (GH-3131).

See `tests/baselines/common.py` for what a baseline is and the command that refreshes them. Each surface has its
module under `tests/baselines`, with the baseline, the comparison and the `ACCEPTED_BREAKS` of that surface. The
OpenAPI document is held the same way in `tests/ui/test_openapi_baseline.py`. Here: the live check of each surface,
that the baselines are those of the release in `pyproject.toml`, that an accepted break says why and is not stale,
and the helpers they share. The comparisons themselves are tested beside, in `test_cli_baseline.py` and the others.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tests.baselines import cli, mcp, parameters, surface
from tests.baselines.common import RELEASE, project_version, signature_breaks, stale, unaccepted, without_reason
from tests.ui.openapi_diff import ACCEPTED_BREAKS as OPENAPI_ACCEPTED_BREAKS
from tests.ui.openapi_snapshot import installed_versions, locked_versions

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

_BREAK = (
    "The {name} no longer offers what the last release did ({baseline}). A caller written against that release "
    "breaks on it: restore it, or, for a change that is meant, name it in ACCEPTED_BREAKS of {module} with the "
    "reason, add a **Breaking** entry to the changelog, and say what to do instead. The baseline itself is "
    "refreshed only in a release commit (`uv run poe contracts:baseline`)."
)

#: the surfaces, by the name a failure gives them
_SURFACES = {
    "command line": cli,
    "Python surface": surface,
    "MCP tools": mcp,
    "parameters of the datasets": parameters,
}


def _skip_unless_locked(module: ModuleType) -> None:
    """Skip where the versions that shape a surface are not the ones the baseline was written with."""
    shaped_by = getattr(module, "SHAPED_BY", ())
    if shaped_by:
        pytest.importorskip("fastmcp")
        if installed_versions(shaped_by) != locked_versions(shaped_by):
            pytest.skip(f"the baseline is compared with the versions {locked_versions(shaped_by)} of {shaped_by}")


def _findings(module: ModuleType) -> list[str]:
    _skip_unless_locked(module)
    return module.breaking_changes(module.read_baseline(), module.build_surface())


@pytest.mark.parametrize("name", _SURFACES)
def test_the_surface_offers_all_the_last_release_offered(name: str) -> None:
    """A command, an option, a name, a signature, a tool, an argument or a parameter of the release is still there."""
    module = _SURFACES[name]

    found = unaccepted(_findings(module), module.ACCEPTED_BREAKS)

    message = _BREAK.format(
        name=name, baseline=module.BASELINE.relative_to(module.BASELINE.parents[2]), module=module.__name__
    )
    assert not found, f"{message}\n" + "\n".join(found[:40])


@pytest.mark.parametrize("name", _SURFACES)
def test_no_accepted_break_is_stale(name: str) -> None:
    """An entry of `ACCEPTED_BREAKS` is a break that is there: undone or refreshed away, the entry goes too."""
    module = _SURFACES[name]

    assert not stale(_findings(module), module.ACCEPTED_BREAKS)


def test_no_accepted_break_of_the_openapi_document_is_stale() -> None:
    """The same for the OpenAPI document, where the comparison is `tests/ui/test_openapi_baseline.py`'s."""
    from tests.ui.openapi_baseline import read_baseline  # noqa: PLC0415
    from tests.ui.openapi_diff import breaking_changes  # noqa: PLC0415
    from tests.ui.openapi_snapshot import build_document  # noqa: PLC0415

    if installed_versions() != locked_versions():
        pytest.skip("the document is compared with the locked versions of FastAPI and pydantic")

    assert not stale(breaking_changes(read_baseline(), build_document()), OPENAPI_ACCEPTED_BREAKS)


@pytest.mark.parametrize("name", _SURFACES)
def test_the_baseline_is_the_surface_of_the_release_in_pyproject(name: str) -> None:
    """The release commit refreshes the baselines: `x-release` is the version `pyproject.toml` has when it is made."""
    assert _SURFACES[name].read_baseline()[RELEASE] == project_version(), (
        "run `uv run poe contracts:baseline` in the release commit, see .github/RELEASE_STRATEGY.md"
    )


@pytest.mark.parametrize("name", _SURFACES)
def test_the_baseline_is_not_empty(name: str) -> None:
    """A baseline that was cut short holds nothing: the entry points of each surface are in it."""
    baseline = _SURFACES[name].read_baseline()
    expected: dict[str, Callable[[dict[str, Any]], bool]] = {
        "command line": lambda b: (
            {"wetterdienst stations", "wetterdienst values"} <= set(b["commands"])
            and "--provider" in b["commands"]["wetterdienst values"]["options"]
            and b["exit_codes"] == [0, 1, 2]
        ),
        "Python surface": lambda b: (
            "Wetterdienst" in b["__all__"]
            and "dwd/observation" in b["requests"]
            and b["request_exports"]["dwd/observation"] == "wetterdienst.provider.dwd.observation.DwdObservationRequest"
        ),
        "MCP tools": lambda b: (
            {"stations", "values"} <= set(b["tools"]) and "provider" in b["tools"]["values"]["properties"]
        ),
        "parameters of the datasets": lambda b: (
            "temperature_air_mean_2m" in b["parameters"]["dwd/observation"]["daily"]["climate_summary"]
            and b["renamed"]["parameters"]
        ),
    }

    assert expected[name](baseline), name


@pytest.mark.parametrize("name", _SURFACES)
def test_every_approved_break_says_why(name: str) -> None:
    """An entry of an `ACCEPTED_BREAKS` has a reason a reviewer can read."""
    assert not without_reason(_SURFACES[name].ACCEPTED_BREAKS)


# --- the helpers ---------------------------------------------------------------------------------


def test_a_finding_is_accepted_by_its_exact_words() -> None:
    """Only the finding named is left out, and an entry of no finding is stale."""
    accepted = {"a was removed": "a reason that is long enough", "b was removed": "a reason that is long enough"}

    assert unaccepted(["a was removed", "c was removed"], accepted) == ["c was removed"]
    assert stale(["a was removed", "c was removed"], accepted) == ["b was removed"]
    assert without_reason({"a was removed": "no"}) == ["a was removed"]


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        pytest.param("(a, b=None)", "(a, b=None, c=1)", [], id="optional-after"),
        pytest.param("(a, *, b=None)", "(a, *, b=None, c=1)", [], id="optional-keyword-only"),
        pytest.param("(a, *, b)", "(a, b)", [], id="keyword-only-becomes-positional"),
        pytest.param("(a, /, b)", "(a, b)", [], id="positional-only-accepts-the-keyword"),
        pytest.param("(a, b=...)", "(a, b=...)", [], id="the-same"),
        pytest.param("(a, b=...)", "(a, b=Ellipsis)", [], id="a-default-that-is-not-printed"),
        pytest.param("(a, b=1)", "(a, b=None)", ["default of b changed from 1 to None"], id="default"),
        pytest.param("(a, b=None)", "(a)", ["parameter b was removed"], id="removed"),
        pytest.param("(a, b=None)", "(a, c=None)", ["parameter b was removed"], id="renamed"),
        pytest.param("(a, b=None)", "(a, b)", ["parameter b became required"], id="required"),
        pytest.param("(a)", "(a, b)", ["parameter b was added and is required"], id="new-required"),
        pytest.param("(a)", "(a, *, b)", ["parameter b was added and is required"], id="new-required-keyword-only"),
        pytest.param(
            "(a, b)", "(a, *, b)", ["parameter b changed from positional_or_keyword to keyword_only"], id="kw"
        ),
        pytest.param(
            "(a, b)", "(a, /, b)", ["parameter a changed from positional_or_keyword to positional_only"], id="po"
        ),
        pytest.param("(a, b)", "(b, a)", ["the positional parameters were reordered"], id="reordered"),
        pytest.param("(a, b=None)", "(a, c=None, b=None)", ["inserted before b"], id="inserted"),
        pytest.param("(a, *args)", "(a)", ["*args was removed"], id="args"),
        pytest.param("(a, **kwargs)", "(a)", ["**kwargs was removed"], id="kwargs"),
        pytest.param("(a)", "(a, *args, **kwargs)", [], id="args-and-kwargs-added"),
    ],
)
def test_a_signature_break_is_found_and_an_addition_is_not(old: str, new: str, expected: list[str]) -> None:
    """A call written against the old signature breaks as the rules of `signature_breaks` say, and not otherwise."""
    found = signature_breaks("f", old, new)

    assert len(found) == len(expected), found
    for finding, part in zip(found, expected, strict=True):
        assert part in finding
