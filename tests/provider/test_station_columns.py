# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A station column a provider builds but its `_base_columns` leave out is found, not dropped in silence (GH-2019)."""

from io import BytesIO

import pytest

from wetterdienst import Settings
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest
from wetterdienst.util.network import File


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
