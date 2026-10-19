# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The comparison of the parameters of every dataset with the last release, tested with datasets made here (GH-3131).

`tests/baselines/test_baselines.py` holds the real metadata to its baseline; these are the differ's own tests: each
kind of break is found, and each kind of addition passes, among them the renames that keep a name from failing.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from tests.baselines.common import unaccepted
from tests.baselines.parameters import ACCEPTED_BREAKS, breaking_changes, build_surface
from wetterdienst.metadata.renamed import RENAMED_PARAMETERS, RENAMED_PARAMETERS_IN_DATASET, RENAMED_RESOLUTIONS


def _surface() -> dict[str, Any]:
    return {
        "networks": ["a/obs", "a/fc", "b/obs"],
        "parameters": {
            "a/obs": {
                "daily": {"kl": ["precipitation_amount", "wind_speed"], "more": ["x"]},
                "6_hours": {"kl": ["y"]},
            },
            "a/fc": {"hourly": {"small": ["temperature_air_2m"]}},
        },
        "renamed": {
            "parameters": {"precipitation_height": "precipitation_amount"},
            "in_dataset": {"a/obs": {"daily/kl": {"wind": "wind_speed"}}},
            "resolutions": {"6_hour": "6_hours"},
        },
    }


def _changed(edit: Any) -> list[str]:  # noqa: ANN401
    """Edit a copy of the metadata and say what the edit breaks."""
    current = copy.deepcopy(_surface())
    edit(current)
    return breaking_changes(_surface(), current)


def _kl(surface: dict[str, Any]) -> list[str]:
    return surface["parameters"]["a/obs"]["daily"]["kl"]


def test_metadata_is_not_a_break_of_itself() -> None:
    """The differ finds nothing where nothing changed."""
    assert breaking_changes(_surface(), _surface()) == []


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        pytest.param(lambda s: _kl(s).remove("wind_speed"), "a/obs/daily/kl/wind_speed was removed", id="parameter"),
        pytest.param(
            lambda s: _kl(s).__setitem__(1, "wind_speed_mean"),
            "a/obs/daily/kl/wind_speed was removed",
            id="parameter-renamed-without-a-rename-entry",
        ),
        pytest.param(
            lambda s: (
                _kl(s).__setitem__(1, "wind_speed_mean"),
                s["renamed"]["in_dataset"]["a/obs"]["daily/kl"].update(wind="wind_speed_mean"),
            ),
            "a/obs/daily/kl/wind_speed was removed",
            id="renamed-in-a-dataset-but-the-entry-does-not-lead-to-the-name",
        ),
        pytest.param(
            lambda s: (_kl(s).remove("precipitation_amount"), s["renamed"]["parameters"].clear()),
            "rename of precipitation_height was removed",
            id="rename-entry-dropped",
        ),
        pytest.param(
            lambda s: s["renamed"]["in_dataset"]["a/obs"]["daily/kl"].clear(),
            "rename of wind in a/obs/daily/kl was removed",
            id="rename-in-dataset-dropped",
        ),
        pytest.param(
            lambda s: s["renamed"]["in_dataset"].pop("a/obs"),
            "rename of wind in a/obs/daily/kl was removed",
            id="all-renames-of-a-network-dropped",
        ),
        pytest.param(
            lambda s: s["renamed"]["resolutions"].clear(),
            "rename of resolution 6_hour was removed",
            id="resolution-rename-dropped",
        ),
        pytest.param(
            lambda s: s["parameters"]["a/obs"]["daily"].pop("more"), "a/obs/daily/more was removed", id="dataset"
        ),
        pytest.param(lambda s: s["parameters"]["a/obs"].pop("daily"), "a/obs/daily was removed", id="resolution"),
        pytest.param(
            lambda s: s["parameters"]["a/obs"].update({"6_hr": s["parameters"]["a/obs"].pop("6_hours")}),
            "a/obs/6_hours was removed",
            id="resolution-renamed-without-an-entry",
        ),
        pytest.param(
            lambda s: (s["parameters"].pop("a/fc"), s["networks"].remove("a/fc")), "a/fc was removed", id="network"
        ),
    ],
)
def test_a_break_is_found(edit: Any, expected: str) -> None:  # noqa: ANN401
    """Each name the last release offered is found gone when it is neither there nor renamed."""
    found = _changed(edit)

    assert any(expected in finding for finding in found), found


def _rename_chain(surface: dict[str, Any]) -> None:
    """Rename `precipitation_height` twice: it became `precipitation_amount`, which became `precipitation`."""
    _kl(surface)[0] = "precipitation"
    surface["renamed"]["parameters"]["precipitation_amount"] = "precipitation"


def _rename_in_dataset(surface: dict[str, Any]) -> None:
    _kl(surface)[1] = "wind_speed_mean"
    surface["renamed"]["in_dataset"]["a/obs"]["daily/kl"]["wind_speed"] = "wind_speed_mean"


def _rename_resolution(surface: dict[str, Any]) -> None:
    surface["parameters"]["a/obs"]["six_hours"] = surface["parameters"]["a/obs"].pop("6_hours")
    surface["renamed"]["resolutions"]["6_hours"] = "six_hours"


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(lambda s: _kl(s).append("new"), id="parameter"),
        pytest.param(lambda s: s["parameters"]["a/obs"]["daily"].update(new=["z"]), id="dataset"),
        pytest.param(lambda s: s["parameters"]["a/obs"].update(monthly={"kl": ["z"]}), id="resolution"),
        pytest.param(lambda s: s["parameters"].update({"b/new": {"daily": {"d": ["z"]}}}), id="network"),
        pytest.param(lambda s: s["renamed"]["parameters"].update(new_old="new_new"), id="rename"),
        pytest.param(_rename_in_dataset, id="renamed-in-a-dataset"),
        pytest.param(_rename_chain, id="renamed-twice"),
        pytest.param(
            lambda s: (
                _kl(s).__setitem__(0, "precipitation_amount_x"),
                s["renamed"]["parameters"].update(precipitation_amount="precipitation_amount_x"),
            ),
            id="renamed-again-with-the-first-entry-kept",
        ),
        pytest.param(_rename_resolution, id="resolution-renamed"),
        pytest.param(
            lambda s: (s["parameters"].pop("b/obs", None), s["networks"].append("b/obs")),
            id="network-without-its-extra",
        ),
    ],
)
def test_an_addition_or_a_rename_is_not_a_break(edit: Any) -> None:  # noqa: ANN401
    """New names pass, and so does a name that is renamed, even more than once, to one the dataset has."""
    assert _changed(edit) == []


def test_a_sub_daily_mean_temperature_that_became_a_spot_name_is_a_rename() -> None:
    """`temperature_air_mean_2m` is `temperature_air_2m` where a source states no mean: no table lists it."""
    baseline = _surface()
    baseline["parameters"]["a/fc"]["hourly"]["small"] = ["temperature_air_mean_2m"]

    assert breaking_changes(baseline, _surface()) == []


def test_a_dataset_that_is_gone_is_a_break_whatever_its_parameters_became() -> None:
    """A dataset is removed with all its names, and the rename tables do not say where they went."""
    found = _changed(lambda s: s["parameters"]["a/obs"]["daily"].pop("kl"))

    assert found == ["a/obs/daily/kl was removed"]


def test_an_approved_break_is_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """A finding named in `ACCEPTED_BREAKS` does not fail the check, and any other still does."""
    finding = "a/obs/daily/kl/wind_speed was removed"
    monkeypatch.setitem(ACCEPTED_BREAKS, finding, "a reason that is long enough")

    assert unaccepted([finding, "a/obs/daily/more was removed"], ACCEPTED_BREAKS) == ["a/obs/daily/more was removed"]


def test_the_real_metadata_is_listed_with_its_renames() -> None:
    """The listing has the networks, their datasets' parameters and each rename table as the code has them."""
    surface = build_surface()

    assert "dwd/observation" in surface["networks"]
    assert "dwd/radar" not in surface["networks"]
    assert set(surface["parameters"]) <= set(surface["networks"])
    assert surface["renamed"]["parameters"] == dict(sorted(RENAMED_PARAMETERS.items()))
    assert surface["renamed"]["resolutions"] == RENAMED_RESOLUTIONS
    # the renames of a dataset are keyed by the network, not by the name of its metadata
    renames = surface["renamed"]["in_dataset"]
    assert set(renames) <= set(surface["networks"])
    assert sum(len(datasets) for datasets in renames.values()) == sum(
        len(datasets) for datasets in RENAMED_PARAMETERS_IN_DATASET.values()
    )
