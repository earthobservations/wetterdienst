# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The wide CSV of the row options: streamed it has every requested column, chosen it has the delivered ones.

A wide CSV streamed station by station (`filter`, `max_rows`, nothing) has the header of the request (GH-4432). The
CSV of rows chosen by `sort` or `first` is one frame that was held whole and cut: it has the columns the stations
delivered (the union of them, as the plain `all()` frame has), and it is sent in batches of that frame (GH-4411).
"""

from __future__ import annotations

import csv
import io
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.ui.test_wide_csv_columns import (  # noqa: F401
    BOTH,
    FLAGS,
    IDENTITY,
    MAX,
    MIN,
    _no_ambient_settings,
    _query,
    _serve_dwd,
    _stations_that_lack_parameters,
)
from wetterdienst.ui import restapi

EVERY_COLUMN = [*IDENTITY, MIN, f"{MIN}{FLAGS}", MAX, f"{MAX}{FLAGS}"]


def _csv(**options: str) -> tuple[list[str], list[dict[str, Any]]]:
    response = TestClient(restapi.app, raise_server_exceptions=False).get(
        "/api/v1/values", params={**_query(shape="wide"), "format": "csv", **options}
    )
    assert response.status_code == 200, response.text
    reader = csv.DictReader(io.StringIO(response.text))
    return list(reader.fieldnames or []), list(reader)


@pytest.mark.parametrize(
    "options",
    [{"filter": "day=2"}, {"max_rows": "40"}, {"filter": "month=5", "max_rows": "50"}],
    ids=["filter", "max_rows", "both"],
)
def test_a_streamed_wide_csv_with_row_options_has_every_requested_column(options: dict[str, str]) -> None:
    """Stations that deliver different parameters: the header is the request's, what a station lacks is empty."""
    names, rows = _csv(**options)
    assert names == EVERY_COLUMN
    assert rows
    by_station = {row["station_id"]: row for row in rows}
    assert by_station["00001"][MAX] == ""  # the station that lacks the maximum
    assert by_station["00001"][MIN] != ""
    if "00003" in by_station:
        assert by_station["00003"][MIN] == ""
        assert by_station["00003"][MAX] != ""


@pytest.mark.parametrize(
    "options",
    [{"sort": "-month", "first": "1"}, {"sort": "-day", "first": "2", "by": "none"}, {"sort": "day", "max_rows": "20"}],
    ids=["first", "first over stations", "sort and max_rows"],
)
def test_a_wide_csv_of_rows_chosen_by_sort_is_answered_and_has_the_delivered_columns(options: dict[str, str]) -> None:
    """One frame held whole is cut and sent in batches: no `reader` is needed, and no delivered column is lost."""
    names, rows = _csv(**options)
    assert rows
    assert names == EVERY_COLUMN  # the stations between them delivered both parameters
    assert {row["station_id"] for row in rows} <= {"00001", "00002", "00003"}
