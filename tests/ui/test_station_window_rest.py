# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The size limit counts the stations a window can have data in, and the walk reads those (GH-4426).

Served as `test_surface_parity.py` serves it: eight stations of a small DWD network, whose index and files are stubs.
Seven are open, and `00007` (`Altstadt`) closed in 1920. The rule itself is held in
`tests/model/test_station_window.py`; here is what a caller of the REST API sees.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.ui.test_surface_parity import PARAMETER, _no_ambient_settings, _rest, _serve_dwd  # noqa: F401
from wetterdienst.provider.dwd.observation.api import DwdObservationValues

if TYPE_CHECKING:
    from collections.abc import Callable

    import polars as pl

WINDOW = {"timestamp": "2020-05"}


@pytest.fixture
def read(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the stations the walk collects."""
    collected: list[str] = []
    original: Callable[..., pl.DataFrame] = DwdObservationValues._collect_station_parameter_or_dataset  # noqa: SLF001

    def collect(self: object, station_id: str, parameter_or_dataset: object) -> pl.DataFrame:
        collected.append(station_id)
        df = original(self, station_id, parameter_or_dataset)
        # the station that closed in 1920 holds nothing in 2020
        return df.clear() if station_id == "00007" else df

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    return collected


def test_the_limit_counts_the_stations_of_the_window_and_the_walk_reads_those(
    monkeypatch: pytest.MonkeyPatch, read: list[str]
) -> None:
    """Eight are listed and seven can have data in 2020: a limit of 7 lets `all=true` pass and 6 refuses it with 7."""
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "7")

    response = _rest("/api/values", all="true", **WINDOW)

    assert response.status_code == 200, response.text
    assert sorted(set(read)) == ["00001", "00002", "00003", "00004", "00005", "00006", "00008"]
    assert "00007" not in read

    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "6")
    refused = _rest("/api/values", all="true", **WINDOW)

    assert refused.status_code == 400
    assert (refused.json()["limit"], refused.json()["requested"], refused.json()["maximum"]) == ("stations", 7, 6)
    assert refused.json()["detail"].startswith(
        "This request reads 7 stations that can have data in the window, more than the 6 this server allows"
    )


def test_a_request_without_a_window_counts_every_listed_station(monkeypatch: pytest.MonkeyPatch) -> None:
    """No window, no cut: the eight listed are counted, as they were."""
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "7")

    refused = _rest("/api/values", all="true")

    assert refused.status_code == 400
    assert refused.json()["requested"] == 8
    assert refused.json()["detail"].startswith("This request reads 8 stations, more than the 7")


def test_the_buffer_of_the_request_is_not_the_lag(monkeypatch: pytest.MonkeyPatch, read: list[str]) -> None:
    """`station_window_end_buffer=0` does not make the seven open stations "closed": they are counted and read."""
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "7")

    response = _rest("/api/values", all="true", station_window_end_buffer="0", **WINDOW)

    assert response.status_code == 200, response.text
    assert len(set(read)) == 7


def test_a_station_named_by_id_is_read_closed_or_not_and_is_told_in_the_metadata(
    monkeypatch: pytest.MonkeyPatch, read: list[str]
) -> None:
    """`00007` closed in 1920: it is read, has no row in May 2020, and `warnings` names it. The limit counts it."""
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "2")

    response = _rest("/api/values", stations="00001,00007", **WINDOW)

    assert response.status_code == 200, response.text
    assert sorted(read) == ["00001", "00007"]
    warnings = response.json()["metadata"]["warnings"]
    (warning,) = [w for w in warnings if w["code"] == "station-without-rows"]
    assert warning["stations"] == ["00007"]


def test_ids_over_the_limit_are_refused_whatever_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Named stations are all counted: the window does not shrink a list of ids under the limit."""
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "1")

    response = _rest("/api/values", stations="00001,00007", **WINDOW)

    assert response.status_code == 400
    assert response.json()["requested"] == 2
    # the window cut nothing, so the text does not say it did
    assert response.json()["detail"].startswith("This request reads 2 stations, more than the 1")


def test_a_selection_the_rule_cuts_to_nothing_is_an_answer_with_a_warning(read: list[str]) -> None:
    """The nearest station within 1 km is `00007`, which closed in 1920: no row, and the metadata says why (GH-3539)."""
    response = _rest("/api/values", latitude="51.05", longitude="13.74", distance="1", **WINDOW)

    assert response.status_code == 200, response.text
    assert read == []
    body = response.json()
    assert body["metadata"]["counts"]["stations"] == 0
    (warning,) = [w for w in body["metadata"]["warnings"] if w["code"] == "stations-outside-window"]
    assert warning["stations"] == ["00007"]
    assert "1 of the 1 stations of the selection is not read" in warning["message"]
