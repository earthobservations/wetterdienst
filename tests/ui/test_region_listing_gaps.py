# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A region that is not found after a listing was skipped is the provider's gap, not the caller's mistake (GH-4418).

`dwd/observation` looks its stations up in directories and goes on without one that came back empty or missing
(`file-skipped`). A station asked for by id that is then not found is a 502 that names the directory
(`StationListingIncompleteError`): the directory may have listed it. A region is the same: one that is not in the list
the lookup built, or a list that came back empty, may be one a skipped directory holds, so it is a 502 and not the 400
of a region that does not exist. A region that is found is answered, and the warning of the lookup says what was left
out. Served by the stand-in of DWD's server of `test_empty_listing.py`.
"""

from __future__ import annotations

import asyncio

import pytest
from click.testing import CliRunner

from tests.ui.test_empty_listing import (  # noqa: F401
    _MONTHLY,
    _MONTHLY_HISTORICAL,
    _MONTHLY_RECENT,
    _request,
    client,
    dwd,
)
from wetterdienst.exceptions import (
    RegionListingIncompleteError,
    StationListingIncompleteError,
    UnknownRegionError,
    UpstreamError,
)
from wetterdienst.ui.cli import cli
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

_PARAMS = {"provider": "dwd", "network": "observation", "parameters": _MONTHLY}
_HISTORICAL = f"`{_MONTHLY_HISTORICAL}`"
_REASON = "its listing came back empty or missing"


def test_a_region_that_is_found_is_answered_with_the_warning_of_the_skipped_directory(dwd, client) -> None:  # noqa: ANN001, F811
    """Station 00044 is listed by `recent`: the skipped `historical` costs nothing, and the answer says so."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    response = client.get("/api/stations", params={**_PARAMS, "region": "niedersachsen"})

    assert response.status_code == 200, response.text
    assert [station["station_id"] for station in response.json()["stations"]] == ["00044"]
    assert "file-skipped" in {warning["code"] for warning in response.json()["metadata"]["warnings"]}


def test_a_region_that_is_not_found_after_a_skipped_directory_is_a_502_that_names_it(dwd, client) -> None:  # noqa: ANN001, F811
    """Not the 400 of an unknown region: the directory may have listed it."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    response = client.get("/api/stations", params={**_PARAMS, "region": "Bayern,Hesse"})

    assert response.status_code == 502, response.text
    detail = response.json()["detail"]
    assert detail.startswith("No station found for the region 'Bayern', 'Hesse'.")
    assert f"{_HISTORICAL} ({_REASON})" in detail
    assert "Try again later." in detail


def test_a_list_that_came_back_empty_after_skipped_directories_is_a_502_too(dwd, client) -> None:  # noqa: ANN001, F811
    """Both periods skipped: the list is empty because of them, so no region is known to be missing, or there."""
    dwd.set(empty=(_MONTHLY_HISTORICAL, _MONTHLY_RECENT))

    response = client.get("/api/stations", params={**_PARAMS, "region": "Niedersachsen"})

    assert response.status_code == 502, response.text
    assert response.json()["detail"].startswith("No station found for any region.")


def test_without_a_skipped_directory_an_unknown_region_is_the_400_it_was(dwd, client) -> None:  # noqa: ANN001, F811
    """The control: the lookup went without nothing, so the region is known to be unknown, and the list is offered."""
    del dwd

    response = client.get("/api/stations", params={**_PARAMS, "region": "Bayern"})

    assert response.status_code == 400, response.text
    assert "has no station in the region 'Bayern'" in response.json()["detail"]
    assert "The regions there are: Niedersachsen." in response.json()["detail"]


def test_the_values_of_a_region_not_found_after_a_skipped_directory_are_a_502_too(dwd, client) -> None:  # noqa: ANN001, F811
    """`values` selects the same way, and is refused the same way before anything is read."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    response = client.get(
        "/api/values",
        params={**_PARAMS, "parameters": "monthly/climate_summary/temperature_air_mean_2m"}
        | {"region": "Bayern", "timestamp": "2020/2026-06"},
    )

    assert response.status_code == 502, response.text
    assert "No station found for the region 'Bayern'." in response.json()["detail"]


def test_the_command_line_exits_1_with_the_error_not_the_usage_error_of_an_unknown_region(
    dwd,  # noqa: ANN001, F811
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An upstream gap is the provider's: exit 1, as the id of `interpolate` is."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    result = CliRunner().invoke(
        cli,
        ["stations", "--provider=dwd", "--network=observation", f"--parameters={_MONTHLY}", "--region=Bayern"],
    )

    assert result.exit_code == 1, result.output
    assert "RegionListingIncompleteError" in caplog.text
    assert f"the directory {_HISTORICAL} ({_REASON})" in caplog.text


def test_the_mcp_tool_answers_the_502_and_its_text(dwd) -> None:  # noqa: ANN001, F811
    """The agent reads the directory, as it does for a station of `interpolate`."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui import restapi  # noqa: PLC0415
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    async def call() -> None:
        async with Client(build_mcp_server(restapi.app)) as mcp:
            await mcp.call_tool("stations", {**_PARAMS, "region": ["Bayern"]})

    with pytest.raises(ToolError, match="HTTP error 502") as error:
        asyncio.run(call())
    assert f"the directory {_HISTORICAL} ({_REASON})" in str(error.value)


def test_python_raises_an_upstream_error_that_keeps_the_regions_and_the_directories(dwd) -> None:  # noqa: ANN001, F811
    """An `UpstreamError` and a `StationListingIncompleteError`, not an `UnknownRegionError`."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    with pytest.raises(RegionListingIncompleteError) as error:
        _request().filter_by_region(["Bayern", "Hesse"])

    assert isinstance(error.value, StationListingIncompleteError)
    assert isinstance(error.value, UpstreamError)
    assert not isinstance(error.value, UnknownRegionError)
    assert error.value.regions == ["Bayern", "Hesse"]
    assert error.value.gaps == {_HISTORICAL: _REASON}


def test_python_a_region_that_is_found_is_selected_and_the_skip_is_warned_of(dwd) -> None:  # noqa: ANN001, F811
    """The library answers the region, with the warning the lookup recorded."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    begin_response()

    stations = _request().filter_by_region("Niedersachsen")

    assert stations.df.get_column("station_id").to_list() == ["00044"]
    assert "file-skipped" in {warning["code"] for warning in recorded_warnings()}


def test_the_gaps_are_those_of_the_last_lookup(dwd) -> None:  # noqa: ANN001, F811
    """A directory that is filled again no longer makes an unknown region a 502."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    request = _request()
    with pytest.raises(RegionListingIncompleteError):
        request.filter_by_region("Bayern")

    dwd.server.directories[dwd._path(_MONTHLY_HISTORICAL)] = ["KL_Beschreibung_Stationen.txt"]  # noqa: SLF001

    with pytest.raises(UnknownRegionError) as error:
        request.filter_by_region("Bayern")
    assert not isinstance(error.value, RegionListingIncompleteError)
