# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The stations of a request for several datasets come in the order of the request, whatever the hash seed (GH-3551).

A loop over a `set` of the requested datasets gives them in the order the hash seed of the interpreter does, which a
test that asks twice in one process cannot see: the seed is fixed when the process starts. So the stubs of the
stations of `eccc`, `dwd/dmo` and `knmi` are read in a process of their own for each of several seeds, each asked for
more than one dataset, and the datasets must come in the order they were named in.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SEEDS = (1, 2, 3, 4)

#: provider -> the datasets asked for, in the order they are named
REQUESTED = {
    "eccc": [("hourly", "data"), ("daily", "data"), ("monthly", "data")],
    "dmo": [("hourly", "icon"), ("hourly", "icon_eu")],
    "knmi": [("daily", "data"), ("hourly", "data"), ("10_minutes", "data")],
}

# The stubs ask for the dataset they were written for, through `_stations` or, for KNMI, the request class; both are
# made to ask for the datasets above instead, and each stub serves its one catalogue for all of them
PROBE = """
import json
import sys

import pytest

from tests.provider import station_catalogue_stubs as stubs
from wetterdienst import Settings

requested = json.loads(sys.argv[1])
current = []


def stations(request_class, *_parameters, **kwargs):
    request = request_class(parameters=current[0], settings=Settings(cache_disable=True), **kwargs)
    return request.all().df


knmi_request = stubs.KnmiObservationRequest
stubs._stations = stations
stubs.KnmiObservationRequest = lambda parameters, **kwargs: knmi_request(parameters=current[0], **kwargs)
stub_of = {"eccc": lambda mp: stubs._eccc(mp, "hourly"), "dmo": stubs._dwd_dmo, "knmi": stubs._knmi}
answers = {}
for name, stub in stub_of.items():
    current[:] = [[tuple(parameter) for parameter in requested[name]]]
    with pytest.MonkeyPatch.context() as monkeypatch:
        try:
            df = stub(monkeypatch)
        except pytest.skip.Exception:
            continue
    answers[name] = df.select("station_id", "resolution", "dataset").rows()
print(json.dumps(answers))
"""


def _read(seed: int) -> subprocess.Popen[str]:
    return subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", PROBE, json.dumps(REQUESTED)],
        cwd=ROOT,
        env={**os.environ, "PYTHONHASHSEED": str(seed)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


@pytest.fixture(scope="module")
def answers() -> dict[int, dict[str, list[list[str]]]]:
    """Read the stations of every stub in a process for each seed, the processes running together."""
    processes = {seed: _read(seed) for seed in SEEDS}
    result = {}
    for seed, process in processes.items():
        out, err = process.communicate(timeout=300)
        assert process.returncode == 0, err
        result[seed] = json.loads(out.strip().splitlines()[-1])
    return result


@pytest.mark.parametrize("provider", list(REQUESTED))
def test_the_datasets_of_the_stations_come_in_request_order_whatever_the_hash_seed(
    answers: dict[int, dict[str, list[list[str]]]], provider: str
) -> None:
    """Hold the stations to the datasets in the order they were named, and to one answer for every seed."""
    if any(provider not in answer for answer in answers.values()):
        pytest.skip(f"the stub of {provider} needs a package that is not installed")
    for seed, answer in answers.items():
        rows = answer[provider]
        assert rows, f"seed {seed}: the stub gave no stations"
        datasets = list(dict.fromkeys((resolution, dataset) for _, resolution, dataset in rows))
        assert datasets == [tuple(requested) for requested in REQUESTED[provider]], f"seed {seed}"
    assert len({json.dumps(answer[provider]) for answer in answers.values()}) == 1
