# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The empty answers of the DMI values, collected through `values().all()` from pages served offline (GH-2627).

The provider hands the core its rows and nothing else: a station with no record in the window and one whose records
are all of parameters the dataset does not map both come out as the empty long form.
"""

from __future__ import annotations

import datetime as dt
import json

import polars as pl
import pytest

from tests.provider.value_stubs import _options, _settings, serve, stations_result
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.dmi.observation import DmiObservationRequest
from wetterdienst.provider.dmi.observation import api as dmi_api

_UTC = dt.UTC


def _hourly(monkeypatch: pytest.MonkeyPatch, parameters: list[str]) -> pl.DataFrame:
    """Collect the hourly data of 06070 for one day, DMI answering one record of each of `parameters`."""
    features = [
        {
            "properties": {
                "parameterId": parameter,
                "from": "2020-02-14T03:00:00+00:00",
                "to": "2020-02-14T04:00:00+00:00",
                "value": 4.1,
            }
        }
        for parameter in parameters
    ]
    serve(monkeypatch, dmi_api, {"stationValue": json.dumps({"features": features}).encode()})
    request = DmiObservationRequest(
        parameters=[("hourly", "data")],
        start=dt.datetime(2020, 2, 14, tzinfo=_UTC),
        end=dt.datetime(2020, 2, 14, 7, tzinfo=_UTC),
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    return stations_result(request, "hourly", "data", "06070").values().all().df


@pytest.mark.parametrize(
    "parameters",
    [
        pytest.param([], id="no record"),
        pytest.param(["a_parameter_the_dataset_does_not_map"], id="only unmapped parameters"),
    ],
)
def test_a_station_without_rows_is_the_empty_long_form(monkeypatch: pytest.MonkeyPatch, parameters: list[str]) -> None:
    """Whatever the provider hands over of a window without a mapped record, the core makes the empty long form."""
    df = _hourly(monkeypatch, parameters)
    assert df.is_empty()
    assert df.schema == pl.Schema(LONG_SCHEMA)


def test_a_station_with_rows_comes_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rows the provider hands over are given the station, resolution and dataset by the core."""
    df = _hourly(monkeypatch, ["mean_temp"])
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df["station_id"].unique().to_list() == ["06070"]
    assert df["resolution"].unique().to_list() == ["hourly"]
    assert df["dataset"].unique().to_list() == ["data"]
    assert df["parameter"].unique().to_list() == ["temperature_air_mean_2m"]
    assert df["value"].to_list() == [4.1]
