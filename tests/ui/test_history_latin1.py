# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The history of a DWD station whose name has an umlaut is read, over the command line and REST (GH-4021).

DWD writes the metadata files of an archive in latin-1, so `Hamburg-Fuhlsbüttel` (01975) is the bytes
`Hamburg-Fuhlsb` + 0xFC + `ttel` there. `read_name_history` opened its file in text mode and decoded it as
UTF-8: `wetterdienst history` for the station died with a `UnicodeDecodeError`, and `/api/v1/history`
answered a 500, while a station with no umlaut worked.

The listing and the downloads are replaced, the archive is made of the real bytes of the files of 01975, and
everything between (the lookup of the station, the readers, the serialisation) is the real one. Nothing here
reaches the network.
"""

from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from starlette.testclient import TestClient

from tests.provider.dwd.observation.test_api_history import _station_01975_zip
from wetterdienst.provider.dwd.observation import api, fileindex, metaindex
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from pathlib import Path

    from wetterdienst import Settings

_DWD = "https://opendata.dwd.de"
_DESCRIPTION = (
    b"Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland Abgabe\r\n"
    b"----------- --------- --------- ------------- --------- --------- ----------------------------------------- "
    b"---------- ------\r\n"
    b"01975 19340801 20261110            11     53.6332    9.9881 Hamburg-Fuhlsb\xfcttel                    "
    b"Hamburg                                  Frei\r\n"
)
_FILES = ["tageswerte_KL_01975_19360101_20251231_hist.zip", "KL_Tageswerte_Beschreibung_Stationen.txt"]
_PARAMS = {
    "provider": "dwd",
    "network": "observation",
    "parameters": "daily/climate_summary",
    "stations": "01975",
    "sections": "name,geography",
}


@pytest.fixture(autouse=True)
def dwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Stand in for DWD's server: every directory lists station 01975, whose description and archive are served."""

    def listing(url: str, settings: Settings, cache_expiry: object = None) -> list[str]:  # noqa: ARG001
        return [f"{url}{name}" for name in _FILES]

    def download_file(url: str, **_: object) -> File:
        return File(url=url, content=io.BytesIO(_DESCRIPTION), status=200)

    monkeypatch.setattr(fileindex, "list_remote_files_fsspec", listing)
    monkeypatch.setattr(metaindex, "download_file", download_file)
    monkeypatch.setattr(api, "download_file", lambda url, **_: File(url=url, content=_station_01975_zip(), status=200))
    monkeypatch.setenv("WD_CACHE_DIR", str(tmp_path / "cache"))


def _assert_the_umlaut_reads(history: dict) -> None:
    assert (history["station_id"], history["resolution"], history["dataset"]) == ("01975", "daily", "climate_summary")
    assert [record["station_name"] for record in history["name"]["station"]] == ["Hamburg-Fuhlsbüttel"]
    assert [record["station_name"] for record in history["geography"]] == ["Hamburg-Fuhlsbüttel"] * 2


def test_cli_history_of_a_station_with_an_umlaut() -> None:
    """The command of the issue answered a `UnicodeDecodeError`; now the name, as DWD wrote it."""
    args = ["history", *(arg for key, value in _PARAMS.items() for arg in (f"--{key}", value))]

    result = CliRunner().invoke(cli, args)

    assert result.exit_code == 0, result.output
    (history,) = json.loads(result.output)["histories"]
    _assert_the_umlaut_reads(history)


def test_rest_history_of_a_station_with_an_umlaut() -> None:
    """`/api/v1/history` answered a 500 for it; now the name, as DWD wrote it."""
    client = TestClient(restapi.app, raise_server_exceptions=False)

    response = client.get("/api/v1/history", params=_PARAMS)

    assert response.status_code == 200, response.text
    (history,) = response.json()["histories"]
    _assert_the_umlaut_reads(history)
