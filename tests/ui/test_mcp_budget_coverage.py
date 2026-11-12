# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The `coverage` tool's answer is cut to the size budget in steps, with a note; no other surface is (GH-4024).

`coverage` is not rows but nested (resolutions, datasets, parameters, each with a description), and the biggest networks
are far over what a client takes: dwd/phenology 139,000 characters, dwd/observation 89,000, noaa/ghcn 59,000. The tool
answers, each step only where the one before is still over the budget: the answer as it is; the `description` of every
parameter null; whole datasets in the order of the network, the note naming those left out; the first of the parameters
of a dataset that alone is over the budget. The shape is that of the REST answer, so the note is in the `description`
of its first resolution (it has no `metadata` block, and its schema takes no other key) and in the
`X-Wetterdienst-Truncated` header. The REST API, the command line and the library answer all of it.

Offline: the metadata of the providers is the library's own, so the networks are the real ones.
"""

from __future__ import annotations

import copy
import json
from typing import Any
from urllib.parse import unquote

import pytest

from tests.ui.test_mcp_budget import _client_sees, _rest_client, _tool_client
from tests.ui.test_operations import _no_ambient_settings  # noqa: F401
from wetterdienst.ui import restapi
from wetterdienst.ui.budget import ANSWER_BUDGET, coverage_size, fit_coverage
from wetterdienst.ui.core import resolve_network

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")


def _discover(provider: str, network: str, **filters: str) -> dict[str, Any]:
    return resolve_network(provider, network).discover(**filters)  # ty: ignore[unresolved-attribute]


def _params(provider: str, network: str, **kwargs: str) -> dict[str, str]:
    return {"provider": provider, "network": network, **kwargs}


def _datasets(coverage: dict[str, Any]) -> list[str]:
    return [f"{resolution}/{name}" for resolution, body in coverage.items() for name in body["datasets"]]


def _shape(coverage: dict[str, Any]) -> Any:  # noqa: ANN401
    """Give the keys of an answer at each level, with the parameters' keys, to compare the shape of two answers."""
    return {
        resolution: (
            sorted(body),
            {
                name: (sorted(dataset), [sorted(parameter) for parameter in dataset["parameters"]])
                for name, dataset in body["datasets"].items()
            },
        )
        for resolution, body in coverage.items()
    }


def _note_of(coverage: dict[str, Any]) -> str:
    """Read the note out of the first resolution's `description`, where the answer carries it."""
    description = coverage[next(iter(coverage))]["description"]
    assert description.startswith("The answer was cut to stay within 40,000 characters: ")
    return description.split("\n\n")[0]


def _descriptions(coverage: dict[str, Any]) -> list[str | None]:
    return [
        parameter["description"]
        for body in coverage.values()
        for dataset in body["datasets"].values()
        for parameter in dataset["parameters"]
    ]


# --- step 1: the answer as it is ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "selection",
    [
        _params("ipma", "observation"),
        _params("dwd", "observation", datasets="climate_summary"),
        _params("dwd", "observation", resolutions="daily"),
    ],
)
def test_an_answer_within_the_budget_is_the_rest_answer(selection: dict[str, str]) -> None:
    """A small network, or a filter that leaves a few datasets, is not cut or noted: the same bytes as the REST API."""
    tool = _tool_client().get("/api/coverage", params=selection)
    rest = _rest_client().get("/api/coverage", params=selection)

    assert tool.status_code == 200
    assert tool.text == rest.text
    assert len(tool.text) <= ANSWER_BUDGET
    assert "x-wetterdienst-truncated" not in tool.headers
    assert "x-wetterdienst-warnings" not in tool.headers
    assert any(description is not None for description in _descriptions(tool.json()))


# --- step 2: the description of each parameter is left out --------------------------------------------------------


@pytest.mark.parametrize(
    "selection",
    [_params("dwd", "mosmix"), _params("noaa", "ghcn", resolutions="daily"), _params("dmi", "observation")],
)
def test_the_descriptions_of_the_parameters_are_left_out_first(selection: dict[str, str]) -> None:
    """A network that is over the budget by its descriptions keeps every dataset and parameter, with a null each."""
    whole = _discover(**selection)
    assert coverage_size(whole) > ANSWER_BUDGET

    response = _tool_client().get("/api/coverage", params=selection)

    assert response.status_code == 200
    cut = response.json()
    assert coverage_size(cut) <= ANSWER_BUDGET
    # the shape and every name, unit and aggregation as they were; the descriptions are null, the datasets all there
    assert _shape(cut) == _shape(whole)
    assert _datasets(cut) == _datasets(whole)
    assert set(_descriptions(cut)) == {None}
    assert [p["name"] for b in cut.values() for d in b["datasets"].values() for p in d["parameters"]] == [
        p["name"] for b in whole.values() for d in b["datasets"].values() for p in d["parameters"]
    ]
    # a dataset's own description and its extent are what they were
    for resolution, body in whole.items():
        for name, dataset in body["datasets"].items():
            assert cut[resolution]["datasets"][name]["description"] == dataset["description"]
            assert cut[resolution]["datasets"][name]["extent"] == dataset["extent"]
    note = _note_of(cut)
    assert "the `description` of each parameter is left out (null)" in note
    assert "Ask `coverage` with `datasets=<name>` for the full detail of one dataset." in note
    assert "left out are" not in note
    assert unquote(response.headers["x-wetterdienst-truncated"]) == note
    assert response.headers["x-wetterdienst-warnings"] == "answer-truncated"


# --- step 3: whole datasets, in order ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "selection", [_params("dwd", "observation"), _params("dwd", "phenology"), _params("noaa", "ghcn")]
)
def test_whole_datasets_are_kept_in_order_and_the_note_names_the_rest(selection: dict[str, str]) -> None:
    """The first datasets are kept whole, the others are named in the note, and asking for one of them works."""
    whole = _discover(**selection)
    response = _tool_client().get("/api/coverage", params=selection)

    cut = response.json()
    assert coverage_size(cut) <= ANSWER_BUDGET
    # every resolution is there, as the network has them
    assert list(cut) == list(whole)
    kept = _datasets(cut)
    everything = _datasets(whole)
    assert 0 < len(kept) < len(everything)
    assert kept == everything[: len(kept)]
    # the datasets kept are whole: every parameter, with its own fields, in the order it had
    for resolution, body in cut.items():
        for name, dataset in body["datasets"].items():
            assert [p["name"] for p in dataset["parameters"]] == [
                p["name"] for p in whole[resolution]["datasets"][name]["parameters"]
            ]
    note = _note_of(cut)
    left = everything[len(kept) :]
    assert f"{len(kept):,} of {len(everything):,} datasets are returned, whole and in the order of the network" in note
    assert f"The {len(left):,} left out are: {', '.join(left)}." in note
    assert "`datasets=<name>[,<name>]`" in note
    assert "`resolutions=<resolution>`" in note
    # what the note says to do gives the full detail of one of them
    resolution, name = left[0].split("/")
    again = _tool_client().get("/api/coverage", params={**selection, "resolutions": resolution, "datasets": name})
    detail = again.json()
    assert _datasets(detail) == [left[0]]
    assert coverage_size(detail) <= ANSWER_BUDGET
    if "x-wetterdienst-truncated" not in again.headers:
        assert detail == _discover(**selection, resolutions=resolution, datasets=name)


def test_the_size_counts_the_note() -> None:
    """The budget holds for what is sent, the note in the description of the first resolution included."""
    cut = _tool_client().get("/api/coverage", params=_params("dwd", "phenology")).json()

    assert ANSWER_BUDGET - 3_000 < coverage_size(cut) <= ANSWER_BUDGET
    assert _note_of(cut) in cut[next(iter(cut))]["description"]


# --- step 4: the parameters of one dataset --------------------------------------------------------------------------


def _with_a_huge_dataset() -> dict[str, Any]:
    """Give a coverage whose first dataset alone is more than the budget, made of the real parameters of noaa/ghcn."""
    whole = _discover("noaa", "ghcn")
    first = next(iter(whole))
    dataset = whole[first]["datasets"][next(iter(whole[first]["datasets"]))]
    huge = copy.deepcopy(whole)
    parameters = []
    for copy_of in range(30):
        parameters += [{**p, "name": f"{p['name']}_{copy_of}"} for p in dataset["parameters"]]
    huge[first]["datasets"][next(iter(huge[first]["datasets"]))]["parameters"] = parameters
    assert coverage_size(huge[first]) > 2 * ANSWER_BUDGET
    return huge


def test_a_dataset_that_alone_is_over_the_budget_keeps_its_first_parameters() -> None:
    """Whole datasets cannot fit, so the first dataset keeps the first parameters that do, and the note counts them."""
    huge = _with_a_huge_dataset()
    resolution, name = _datasets(huge)[0].split("/")
    parameters = huge[resolution]["datasets"][name]["parameters"]

    cut, note = fit_coverage(huge)

    assert note is not None
    assert coverage_size(cut) <= ANSWER_BUDGET
    kept = cut[resolution]["datasets"][name]["parameters"]
    assert 0 < len(kept) < len(parameters)
    assert [p["name"] for p in kept] == [p["name"] for p in parameters[: len(kept)]]
    assert set(_descriptions(dict(cut))) == {None}
    assert f"the dataset `{resolution}/{name}` alone is more than that" in note
    assert f"only its first {len(kept):,} of {len(parameters):,} parameters are returned" in note
    # the other datasets are left out and named, as for the step before
    others = _datasets(huge)[1:]
    assert _datasets(dict(cut)) == [f"{resolution}/{name}"]
    assert f"The {len(others):,} left out are: {', '.join(others)}." in note
    assert "still over" not in note
    assert list(cut) == list(huge)


def test_the_tool_cuts_the_parameters_of_a_huge_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Through the tool, the answer of a dataset with thousands of parameters is within the budget."""
    huge = _with_a_huge_dataset()
    api = resolve_network("noaa", "ghcn")
    monkeypatch.setattr(api, "discover", classmethod(lambda _cls, **_kwargs: huge))

    result = _client_sees("coverage", _params("noaa", "ghcn"))

    assert not result.is_error, result.content
    assert len(json.dumps(result.structured_content, separators=(",", ":"), ensure_ascii=False)) <= ANSWER_BUDGET


def test_a_dataset_that_cannot_be_cut_to_the_budget_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """Where one parameter and the note are over the budget, the note says it is still over."""
    monkeypatch.setattr("wetterdienst.ui.budget.ANSWER_BUDGET", 600)

    cut, note = fit_coverage(_discover("noaa", "ghcn", resolutions="daily"))

    assert note is not None
    assert "was cut as far as it goes and is still over 600 characters" in note
    assert len(cut["daily"]["datasets"]["data"]["parameters"]) == 1


# --- what a client receives, and the other surfaces ---------------------------------------------------------------


@pytest.mark.parametrize(
    "selection",
    [
        _params("dwd", "phenology"),
        _params("dwd", "observation"),
        _params("noaa", "ghcn"),
        _params("noaa", "ghcn", resolutions="daily"),
        _params("dwd", "mosmix"),
    ],
)
def test_what_a_client_receives_of_coverage_is_within_the_budget(selection: dict[str, str]) -> None:
    """The structured content of the tool result, which validates against the output schema, is within the budget."""
    result = _client_sees("coverage", selection)

    assert not result.is_error, result.content
    assert len(json.dumps(result.structured_content, separators=(",", ":"), ensure_ascii=False)) <= ANSWER_BUDGET
    assert result.structured_content == json.loads(result.content[0].text)
    assert "answer was cut" in result.structured_content[next(iter(result.structured_content))]["description"]


@pytest.mark.parametrize(
    "selection", [_params("dwd", "phenology"), _params("dwd", "observation"), _params("noaa", "ghcn")]
)
def test_the_rest_api_answers_all_of_coverage(monkeypatch: pytest.MonkeyPatch, selection: dict[str, str]) -> None:
    """Not from a tool, the answer is whole: no note, no header, every description; the budget is not even asked."""

    def never(*_args: object, **_kwargs: object) -> None:
        msg = "the budget is for a tool's request alone"
        raise AssertionError(msg)

    monkeypatch.setattr(restapi, "fit_coverage", never)

    response = _rest_client().get("/api/coverage", params=selection)

    assert response.status_code == 200
    assert len(response.text) > ANSWER_BUDGET
    assert "x-wetterdienst-truncated" not in response.headers
    assert "answer was cut" not in response.text
    assert response.json() == _discover(**selection)


def test_python_answers_all_of_coverage() -> None:
    """`discover()` is whole whatever its size."""
    whole = _discover("dwd", "phenology")

    assert coverage_size(whole) > 100_000
    assert len(_datasets(whole)) > 100
