# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A station column a provider builds but its `_base_columns` leave out is found, not dropped in silence (GH-2019)."""

import re
from io import BytesIO
from pathlib import Path

import pytest

from wetterdienst import Settings, Wetterdienst
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest
from wetterdienst.ui.core import resolve_network
from wetterdienst.util.network import File

PYTHON_API = Path(__file__).parents[2] / "docs" / "usage" / "python-api.md"


def _serve_ghcn_daily(monkeypatch: pytest.MonkeyPatch) -> None:
    contents = {
        "ghcnd-stations.txt": "GM000010147  53.6350    9.9900   11.0    HAMBURG FUHLSBUETTEL           GSN     10147\n",
        "ghcnd-inventory.txt": "GM000010147  53.6350    9.9900 TMAX 1891 2026\n",
    }
    monkeypatch.setattr(
        "wetterdienst.provider.noaa.ghcn.api.download_file",
        lambda url, **_: File(url=url, content=BytesIO(contents[url.rsplit("/", 1)[-1]].encode()), status=200),
    )


def test_a_built_column_the_request_does_not_declare_is_found(
    monkeypatch: pytest.MonkeyPatch,
    station_column_findings: list[str],
) -> None:
    """GHCN's reader builds `wmo_id`; left out of `_base_columns`, it is named by the check and dropped by `all()`."""
    _serve_ghcn_daily(monkeypatch)
    monkeypatch.setattr(NoaaGhcnRequest, "_base_columns", TimeseriesRequest._base_columns)  # noqa: SLF001

    df = NoaaGhcnRequest(parameters=[("daily", "data")], settings=Settings(cache_disable=True)).all().df

    assert "wmo_id" not in df.columns
    assert station_column_findings == ["NoaaGhcnRequest builds ['wmo_id'] but declares no such station column"]
    station_column_findings.clear()


def test_a_declared_column_is_not_found(monkeypatch: pytest.MonkeyPatch, station_column_findings: list[str]) -> None:
    """With `wmo_id` declared, as `NoaaGhcnRequest` does, the same stations raise nothing and keep the column."""
    _serve_ghcn_daily(monkeypatch)

    df = NoaaGhcnRequest(parameters=[("daily", "data")], settings=Settings(cache_disable=True)).all().df

    assert df["wmo_id"].to_list() == ["10147"]
    assert station_column_findings == []


def _documented_station_columns() -> set[tuple[str, str]]:
    """Read the `(provider/network, column)` pairs of the table of station columns in the Python API page."""
    text = PYTHON_API.read_text(encoding="utf8")
    section = text.split("#### Station columns of a provider", 1)[1].split("\n### ", 1)[0]
    pairs = set()
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        networks, columns, _ = (cell.strip() for cell in line.strip("|").split("|", 2))
        pairs |= {
            (network, column)
            for network in re.findall(r"`([^`]+)`", networks)
            for column in re.findall(r"`([^`]+)`", columns)
        }
    return pairs


def test_every_station_column_a_provider_adds_is_in_the_docs() -> None:
    """The table of station columns lists each column a request declares besides `STATIONS_SCHEMA`, and no other."""
    declared = set()
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            api = resolve_network(provider, network)
            declared |= {
                (f"{provider}/{network}", column)
                for column in getattr(api, "_base_columns", ())
                if column not in TimeseriesRequest._base_columns  # noqa: SLF001
            }
    documented = _documented_station_columns()
    assert declared - documented == set(), "declared by a provider and not in the table of python-api.md"
    assert documented - declared == set(), "in the table of python-api.md and declared by no provider"
