# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The empty answers of the RMI values, collected through `values().all()` from pages served offline (GH-2627).

The provider hands the core its rows and nothing else: a station without a feature in the window and one whose only
features carry no value both come out as the empty long form.
"""

from __future__ import annotations

import datetime as dt
import json

import polars as pl
import pytest

from tests.provider.value_stubs import _options, _settings, serve, stations_result
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.rmi.observation import RmiObservationRequest
from wetterdienst.provider.rmi.observation import api as rmi_api

_UTC = dt.UTC


def _daily(monkeypatch: pytest.MonkeyPatch, features: list[dict]) -> pl.DataFrame:
    """Collect the daily data of 6414 for 2003-08-05, the WFS answering with `features`."""
    body = json.dumps({"numberMatched": len(features), "features": features}).encode()
    serve(monkeypatch, rmi_api, {"aws:aws_1day": body})
    request = RmiObservationRequest(
        parameters=[("daily", "data")],
        start=dt.datetime(2003, 8, 5, tzinfo=_UTC),
        end=dt.datetime(2003, 8, 5, tzinfo=_UTC),
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    return stations_result(request, "daily", "data", "6414").values().all().df


@pytest.mark.parametrize(
    "features",
    [
        pytest.param([], id="no feature"),
        pytest.param(
            [{"properties": {"timestamp": "2003-08-05T00:00:00Z", "qc_flags": json.dumps({"validated": {}})}}],
            id="a feature without a value",
        ),
    ],
)
def test_a_station_without_rows_is_the_empty_long_form(monkeypatch: pytest.MonkeyPatch, features: list[dict]) -> None:
    """Whatever the provider hands over of a window without a value, the core makes the empty long form."""
    df = _daily(monkeypatch, features)
    assert df.is_empty()
    assert df.schema == pl.Schema(LONG_SCHEMA)


def test_a_station_with_rows_comes_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rows the provider hands over are given the station, resolution and dataset by the core."""
    feature = {
        "properties": {
            "timestamp": "2003-08-05T00:00:00Z",
            "temp_avg": 24.03,
            "qc_flags": json.dumps({"validated": {"TEMP_AVG": True}}),
        }
    }
    df = _daily(monkeypatch, [feature])
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df["station_id"].unique().to_list() == ["6414"]
    assert df["resolution"].unique().to_list() == ["daily"]
    assert df["dataset"].unique().to_list() == ["data"]
    assert df["parameter"].unique().to_list() == ["temperature_air_mean_2m"]
    assert df["value"].to_list() == [24.03]
    assert df["quality_flags"].to_list() == ["1"]
