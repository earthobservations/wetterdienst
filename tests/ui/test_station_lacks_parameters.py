"""A station that exists and lacks the requested parameters is no unknown station, on every surface (GH-4272)."""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from pathlib import Path

_STATIONS = (
    "AA000000001  50.0000   10.0000   10.0    HAS PRCP                                    \n"
    "AA000000003  52.0000   10.0000   10.0    TMAX ONLY                                   \n"
)
_INVENTORY = "AA000000001  50.0000   10.0000 PRCP 1950 2020\nAA000000003  52.0000   10.0000 TMAX 1900 2010\n"
_PARAMETER = "daily/data/precipitation_amount"
_QUERY = {"provider": "noaa", "network": "ghcn", "parameters": _PARAMETER, "timestamp": "2000"}


@pytest.fixture(autouse=True)
def _serve_ghcn(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Serve NOAA's station list and inventory, one of two stations having the precipitation."""
    import os  # noqa: PLC0415

    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    contents = {"ghcnd-stations.txt": _STATIONS, "ghcnd-inventory.txt": _INVENTORY}
    monkeypatch.setattr(
        "wetterdienst.provider.noaa.ghcn.api.download_file",
        lambda url, **_kwargs: File(
            url=url, content=BytesIO(contents[url.rsplit("/", 1)[-1]].encode("utf8")), status=200
        ),
    )


@pytest.mark.parametrize("endpoint", ["interpolate", "summarize"])
def test_rest_answers_a_station_without_the_parameter_with_a_400_that_names_them(endpoint: str) -> None:
    """A 400 `request-refused`, not the 404 of an id that is wrong."""
    client = TestClient(restapi.app, raise_server_exceptions=False)
    response = client.get(f"/api/v1/{endpoint}", params={**_QUERY, "station": "AA000000003"})
    assert response.status_code == 400, response.text
    assert response.json()["type"] == "urn:wetterdienst:problem:request-refused"
    assert response.json()["detail"] == (
        f"Station AA000000003 exists but has none of the requested parameters ({_PARAMETER}). "
        "Change the parameters, not the station."
    )


@pytest.mark.parametrize("endpoint", ["interpolate", "summarize"])
def test_rest_answers_an_unknown_station_with_a_404(endpoint: str) -> None:
    """The id that no list holds is still not found."""
    client = TestClient(restapi.app, raise_server_exceptions=False)
    response = client.get(f"/api/v1/{endpoint}", params={**_QUERY, "station": "AA000000099"})
    assert response.status_code == 404, response.text
    assert "no station found for AA000000099" in response.json()["detail"]


@pytest.mark.parametrize("command", ["interpolate", "summarize"])
def test_cli_names_the_parameters_for_a_station_without_them(command: str) -> None:
    """The command line refuses as a usage error (exit 2) and says what to change."""
    result = CliRunner().invoke(
        cli,
        [
            command,
            "--provider=noaa",
            "--network=ghcn",
            f"--parameters={_PARAMETER}",
            "--timestamp=2000",
            "--station=AA000000003",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "Change the parameters, not the station" in result.output
    assert _PARAMETER in result.output


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_mcp_tool_names_the_parameters_for_a_station_without_them(tool: str) -> None:
    """The MCP tools answer with the REST detail."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> None:
        async with Client(build_mcp_server(restapi.app)) as client:
            await client.call_tool(tool, {**_QUERY, "station": "AA000000003"})

    with pytest.raises(ToolError, match="exists but has none of the requested parameters"):
        asyncio.run(call())
