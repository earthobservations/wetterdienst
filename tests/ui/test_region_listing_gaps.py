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

# ruff: noqa: ANN001, ARG001, F811
# the fixtures `dwd` and `client` of `test_empty_listing.py` are imported by name and taken as arguments
from __future__ import annotations

import asyncio

import polars as pl
import pytest
from click.testing import CliRunner

from tests.ui.test_empty_listing import (  # noqa: F401
    _MONTHLY,
    _MONTHLY_HISTORICAL,
    _MONTHLY_RECENT,
    _request,
    _without_description,
    client,
    dwd,
)
from wetterdienst.exceptions import (
    RegionListingIncompleteError,
    StationListingIncompleteError,
    UnknownRegionError,
    UpstreamError,
)
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui.cli import cli
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

_PARAMS = {"provider": "dwd", "network": "observation", "parameters": _MONTHLY}
_HISTORICAL = f"`{_MONTHLY_HISTORICAL}`"
_REASON = "its listing came back empty or missing"


def test_a_region_that_is_found_is_answered_with_the_warning_of_the_skipped_directory(dwd, client) -> None:
    """Station 00044 is listed by `recent`: the skipped `historical` costs nothing, and the answer says so."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    response = client.get("/api/stations", params={**_PARAMS, "region": "niedersachsen"})

    assert response.status_code == 200, response.text
    assert [station["station_id"] for station in response.json()["stations"]] == ["00044"]
    assert "file-skipped" in {warning["code"] for warning in response.json()["metadata"]["warnings"]}


def test_a_region_that_is_not_found_after_a_skipped_directory_is_a_502_that_names_it(dwd, client) -> None:
    """Not the 400 of an unknown region: the directory may have listed it."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    response = client.get("/api/stations", params={**_PARAMS, "region": "Bayern,Hesse"})

    assert response.status_code == 502, response.text
    detail = response.json()["detail"]
    assert detail.startswith("No station found for the regions 'Bayern', 'Hesse'.")
    assert f"{_HISTORICAL} ({_REASON})" in detail
    assert "Try again later." in detail


def test_a_list_that_came_back_empty_after_skipped_directories_is_a_502_too(dwd, client) -> None:
    """Both periods skipped: the list is empty because of them, so no region is known to be missing, or there."""
    dwd.set(empty=(_MONTHLY_HISTORICAL, _MONTHLY_RECENT))

    response = client.get("/api/stations", params={**_PARAMS, "region": "Niedersachsen"})

    assert response.status_code == 502, response.text
    assert response.json()["detail"].startswith("No station found for any region.")


def test_without_a_skipped_directory_an_unknown_region_is_the_400_it_was(dwd, client) -> None:
    """The control: the lookup went without nothing, so the region is known to be unknown, and the list is offered."""
    del dwd

    response = client.get("/api/stations", params={**_PARAMS, "region": "Bayern"})

    assert response.status_code == 400, response.text
    assert "has no station in the region 'Bayern'" in response.json()["detail"]
    assert "The regions there are: Niedersachsen." in response.json()["detail"]


def test_the_values_of_a_region_not_found_after_a_skipped_directory_are_a_502_too(dwd, client) -> None:
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
    dwd,
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


def test_the_mcp_tool_answers_the_502_and_its_text(dwd) -> None:
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


def test_python_raises_an_upstream_error_that_keeps_the_regions_and_the_directories(dwd) -> None:
    """An `UpstreamError` and a `StationListingIncompleteError`, not an `UnknownRegionError`."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    with pytest.raises(RegionListingIncompleteError) as error:
        _request().filter_by_region(["Bayern", "Hesse"])

    assert isinstance(error.value, StationListingIncompleteError)
    assert isinstance(error.value, UpstreamError)
    assert not isinstance(error.value, UnknownRegionError)
    assert error.value.regions == ["Bayern", "Hesse"]
    assert error.value.gaps == {_HISTORICAL: _REASON}


def test_python_a_region_that_is_found_is_selected_and_the_skip_is_warned_of(dwd) -> None:
    """The library answers the region, with the warning the lookup recorded."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    begin_response()

    stations = _request().filter_by_region("Niedersachsen")

    assert stations.df.get_column("station_id").to_list() == ["00044"]
    assert "file-skipped" in {warning["code"] for warning in recorded_warnings()}


def test_the_gaps_are_those_of_the_last_lookup(dwd) -> None:
    """A directory that is filled again no longer makes an unknown region a 502."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    request = _request()
    with pytest.raises(RegionListingIncompleteError):
        request.filter_by_region("Bayern")

    dwd.server.directories[dwd._path(_MONTHLY_HISTORICAL)] = ["KL_Beschreibung_Stationen.txt"]  # noqa: SLF001

    with pytest.raises(UnknownRegionError) as error:
        request.filter_by_region("Bayern")
    assert not isinstance(error.value, RegionListingIncompleteError)


# the text of the 502 is the text of the 400: at most twenty regions, control characters replaced


def test_the_502_names_at_most_twenty_regions_cleans_them_and_keeps_all_on_the_error(dwd, client) -> None:
    """3,000 unknown regions with a newline and an escape among them: a sentence, not 27,000 characters."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    asked = ["Evil\nHeader: x", "\x1b[31mred", *[f"Atlantis {number:04d}" for number in range(2998)]]

    response = client.get("/api/stations", params={**_PARAMS, "region": ",".join(asked)})

    assert response.status_code == 502, response.text
    detail = response.json()["detail"]
    assert "\n" not in detail
    assert "\x1b" not in detail
    assert detail.startswith("No station found for the regions 'Evil�Header: x', '�[31mred', 'Atlantis 0000'")
    assert "and 2980 more." in detail
    assert len(detail) < 1500
    with pytest.raises(RegionListingIncompleteError) as error:
        _request().filter_by_region(asked)
    assert error.value.regions == asked
    assert str(error.value) == detail


# only a skipped directory that may hold a region the list lacks makes the 502


def test_a_directory_whose_files_name_only_stations_the_list_has_cannot_hold_the_region(dwd, client) -> None:
    """`historical` lists files and no description, and the files are 00044's: 00044 is in the list from `recent`."""
    _without_description(dwd)  # one file, of 00044

    response = client.get("/api/stations", params={**_PARAMS, "region": "Bayern"})

    assert response.status_code == 400, response.text
    assert "has no station in the region 'Bayern'" in response.json()["detail"]
    found = client.get("/api/stations", params={**_PARAMS, "region": "Niedersachsen"})
    assert [station["station_id"] for station in found.json()["stations"]] == ["00044"]


def test_a_directory_whose_files_name_a_station_the_list_lacks_may_hold_the_region(dwd, client) -> None:
    """The files are 00045's, and 00045 is not in the list: the directory that lists them may have its region."""
    _without_description(dwd, files=["stundenwerte_KL_00045_19700101_20241231_hist.zip"])

    response = client.get("/api/stations", params={**_PARAMS, "region": "Bayern"})

    assert response.status_code == 502, response.text
    assert f"the directory {_HISTORICAL} (it lists no description of its stations)" in response.json()["detail"]


def test_a_directory_whose_files_name_the_stations_of_the_list_and_another_may_hold_the_region(dwd, client) -> None:
    """The files are 00044's and 00045's: 00045 is not in the list, so the directory may have its region."""
    _without_description(
        dwd,
        files=[
            "stundenwerte_KL_00044_19700101_20241231_hist.zip",
            "stundenwerte_KL_00045_19700101_20241231_hist.zip",
        ],
    )

    response = client.get("/api/stations", params={**_PARAMS, "region": "Bayern"})

    assert response.status_code == 502, response.text


def test_a_directory_that_names_no_station_may_hold_any_region(dwd, client) -> None:
    """An empty or missing directory names none, so any region may be one of its stations'."""
    dwd.set(missing=(_MONTHLY_HISTORICAL,))

    response = client.get("/api/stations", params={**_PARAMS, "region": "Bayern"})

    assert response.status_code == 502, response.text


# a list whose stations have no region is no better than an empty one where a directory may hold it


@pytest.fixture
def without_regions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every station of the lookup have no region, as `dwd/derived monthly/climate_correction_factor` does."""
    original = DwdObservationRequest._all  # noqa: SLF001

    def nulled(self: DwdObservationRequest) -> pl.LazyFrame:
        return original(self).with_columns(pl.lit(None, pl.String).alias("region"))

    monkeypatch.setattr(DwdObservationRequest, "_all", nulled)


def test_stations_without_a_region_after_a_skipped_directory_are_a_502_like_an_empty_list(
    dwd, client, without_regions
) -> None:
    """The directory may hold the regions: no region is said not to exist, and none is named."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    response = client.get("/api/stations", params={**_PARAMS, "region": "Hamburg"})

    assert response.status_code == 502, response.text
    assert response.json()["detail"].startswith("No station found for any region.")
    with pytest.raises(RegionListingIncompleteError) as error:
        _request().filter_by_region("Hamburg")
    assert error.value.regions == []


def test_stations_without_a_region_and_no_skipped_directory_are_refused_for_that_reason(
    dwd, client, without_regions
) -> None:
    """The control: nothing was skipped, so it is the 400 of a network that has no region for these parameters."""
    response = client.get("/api/stations", params={**_PARAMS, "region": "Hamburg"})

    assert response.status_code == 400, response.text
    assert response.json()["detail"].startswith("DwdObservationRequest lists no region for the requested parameters: ")
    assert "their stations have no `region`" in response.json()["detail"]


# dwd/derived keeps the gaps of its lookup too


def test_derived_a_region_not_found_after_a_skipped_directory_is_a_502(dwd, client) -> None:
    """`dwd/derived` shares the lookup of the periods: the empty `historical` directory is named, not a 400."""
    directory = "derived_germany/climate/hourly/duett/radiation_global/historical/"
    dwd.set(empty=(directory,))
    params = {"provider": "dwd", "network": "derived", "parameters": "hourly/radiation_global"}

    response = client.get("/api/stations", params={**params, "region": "Bayern"})

    assert response.status_code == 502, response.text
    assert f"the directory `{directory}` ({_REASON})" in response.json()["detail"]
