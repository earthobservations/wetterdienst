# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The comparison of the Python surface with the last release, tested with a surface made here (GH-3131).

`tests/baselines/test_baselines.py` holds the real surface to its baseline; these are the differ's own tests: each
kind of break is found, and each kind of addition passes. The signatures themselves are tested there.
"""

from __future__ import annotations

import copy
import importlib
from typing import Any

import pytest

from tests.baselines.common import unaccepted
from tests.baselines.surface import ACCEPTED_BREAKS, breaking_changes
from tests.public_surface import build_surface
from wetterdienst import Wetterdienst


def _surface() -> dict[str, Any]:
    return {
        "__all__": ["Options", "Wetterdienst"],
        "Period": {"HISTORICAL": "historical", "RECENT": "recent"},
        "Settings": ["auth", "cache_dir"],
        "Wetterdienst": {"resolve": "(provider, network)", "is_valid": "(api)", "registry": "property"},
        "networks": ["dwd/observation", "eccc/observation"],
        "requests": {
            "dwd/observation": "(parameters, start=None, *, options=None)",
            "eccc/observation": "(parameters)",
        },
        "request_exports": [
            "wetterdienst.provider.dwd.observation.DwdObservationRequest",
            "wetterdienst.provider.eccc.observation.EcccObservationRequest",
        ],
    }


def _changed(edit: Any) -> list[str]:  # noqa: ANN401
    """Edit a copy of the surface and say what the edit breaks."""
    current = copy.deepcopy(_surface())
    edit(current)
    return breaking_changes(_surface(), current)


def test_a_surface_is_not_a_break_of_itself() -> None:
    """The differ finds nothing where nothing changed, and the release marker of a baseline is not compared."""
    assert breaking_changes({**_surface(), "x-release": "0.1.0"}, _surface()) == []


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        pytest.param(lambda s: s.pop("Settings"), "Settings was removed", id="section"),
        pytest.param(lambda s: s["__all__"].remove("Options"), "__all__: Options was removed", id="export"),
        pytest.param(lambda s: s["Settings"].remove("cache_dir"), "Settings: cache_dir was removed", id="setting"),
        pytest.param(lambda s: s["Period"].pop("RECENT"), "Period: RECENT was removed", id="enum-member"),
        pytest.param(
            lambda s: s["Period"].update(RECENT="latest"),
            "Period.RECENT: changed from 'recent' to 'latest'",
            id="value",
        ),
        pytest.param(lambda s: s["Wetterdienst"].pop("is_valid"), "Wetterdienst: is_valid was removed", id="method"),
        pytest.param(
            lambda s: s["Wetterdienst"].update(registry="(x)"),
            "Wetterdienst.registry: changed from 'property' to '(x)'",
            id="property-became-a-method",
        ),
        pytest.param(
            lambda s: s["Wetterdienst"].update(resolve="(provider)"),
            "Wetterdienst.resolve: parameter network was removed",
            id="parameter",
        ),
        pytest.param(
            lambda s: s["Wetterdienst"].update(resolve="(provider, network, extra)"),
            "parameter extra was added and is required",
            id="new-required",
        ),
        pytest.param(
            lambda s: s["networks"].remove("eccc/observation"), "networks: eccc/observation was removed", id="network"
        ),
        pytest.param(
            lambda s: s["requests"].update({"eccc/observation": "(parameters, start)"}),
            "parameter start was added and is required",
            id="request-constructor",
        ),
        pytest.param(
            lambda s: s["requests"].update({"dwd/observation": "(parameters, start=None, *, options)"}),
            "requests.dwd/observation: parameter options became required",
            id="request-option-required",
        ),
        pytest.param(
            lambda s: s["requests"].update({"dwd/observation": "(parameters, start='x', *, options=None)"}),
            "default of start changed from None to 'x'",
            id="request-default",
        ),
        pytest.param(
            lambda s: s["request_exports"].remove("wetterdienst.provider.dwd.observation.DwdObservationRequest"),
            "request_exports: wetterdienst.provider.dwd.observation.DwdObservationRequest was removed",
            id="request-export",
        ),
        pytest.param(
            lambda s: s["request_exports"].__setitem__(
                0, "wetterdienst.provider.dwd.observation.api.DwdObservationRequest"
            ),
            "DwdObservationRequest was removed",
            id="request-export-moved-into-an-internal-module",
        ),
    ],
)
def test_a_break_is_found(edit: Any, expected: str) -> None:  # noqa: ANN401
    """Each name and each signature the last release offered is found missing or different."""
    found = _changed(edit)

    assert any(expected in finding for finding in found), found


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(lambda s: s.update(Extra={"x": "(a)"}), id="section"),
        pytest.param(lambda s: s["__all__"].append("Extra"), id="export"),
        pytest.param(lambda s: s["Settings"].append("extra"), id="setting"),
        pytest.param(lambda s: s["Period"].update(NOW="now"), id="enum-member"),
        pytest.param(lambda s: s["Wetterdienst"].update(discover="(cls)"), id="method"),
        pytest.param(lambda s: s["Wetterdienst"].update(resolve="(provider, network, extra=None)"), id="optional"),
        pytest.param(lambda s: s["networks"].append("x/y"), id="network"),
        pytest.param(lambda s: s["requests"].update({"x/y": "(a)"}), id="request"),
        pytest.param(
            lambda s: s["requests"].update({"dwd/observation": "(parameters, start=None, end=None, *, options=None)"}),
            id="request-optional-parameter",
        ),
        pytest.param(
            lambda s: s["requests"].update({"dwd/observation": "(parameters, start=None, options=None)"}),
            id="keyword-only-becomes-positional",
        ),
        pytest.param(lambda s: s["request_exports"].append("wetterdienst.provider.x.y.Z"), id="request-export"),
        pytest.param(lambda s: s["requests"].pop("eccc/observation"), id="constructor-of-a-network-without-its-extra"),
    ],
)
def test_an_addition_is_not_a_break(edit: Any) -> None:  # noqa: ANN401
    """A new name, section or optional parameter passes, and so does a constructor left out for a missing extra."""
    assert _changed(edit) == []


def test_an_approved_break_is_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """A finding named in `ACCEPTED_BREAKS` does not fail the check, and any other still does."""
    finding = "Settings: cache_dir was removed"
    monkeypatch.setitem(ACCEPTED_BREAKS, finding, "a reason that is long enough")

    assert unaccepted([finding, "__all__: Options was removed"], ACCEPTED_BREAKS) == ["__all__: Options was removed"]


def test_every_request_class_is_exported_by_its_provider_package() -> None:
    """The class of each registry path is a class of that package and listed in its `__all__`, not only of `api`."""
    paths = build_surface()["request_exports"]

    assert len(paths) == sum(len(networks) for networks in Wetterdienst.registry.values())
    for path in paths:
        module_name, name = path.rsplit(".", 1)
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue  # the extra the package needs is not installed here
        assert isinstance(getattr(module, name), type), path
        assert name in module.__all__, f"{module_name} does not list {name} in __all__"
        assert not module_name.endswith((".api", ".values", ".metadata")), path
