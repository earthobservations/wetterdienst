# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from datetime import datetime

import pandas as pd
import pytest
import pytz
from pandas._testing import assert_frame_equal

from wetterdienst.dwd.observations import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationResolution,
)
from wetterdienst.dwd.observations.api import DwdObservationRequest
from wetterdienst.metadata.columns import Columns


@pytest.mark.remote
def test_dwd_observations_stations_success():

    # Existing combination of parameters
    request = DwdObservationRequest(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL,
    )

    df = request.all().df

    assert not df.empty

    assert_frame_equal(
        df.loc[df[Columns.STATION_ID.value] == "00001", :].reset_index(drop=True),
        pd.DataFrame(
            {
                "station_id": ["00001"],
                "from_date": [datetime(1937, 1, 1, tzinfo=pytz.UTC)],
                "to_date": [datetime(1986, 6, 30, tzinfo=pytz.UTC)],
                "height": [478.0],
                "latitude": [47.8413],
                "longitude": [8.8493],
                "station_name": ["Aach"],
                "state": ["Baden-Württemberg"],
            }
        ),
    )

    # assert df.loc[
    #     df[Columns.STATION_ID.value] == "00001", :
    # ].values.tolist() == [
    #     [
    #         "00001",
    #         datetime(1937, 1, 1, tzinfo=pytz.UTC),
    #         datetime(1986, 6, 30, tzinfo=pytz.UTC),
    #         478.0,
    #         47.8413,
    #         8.8493,
    #         "Aach",
    #         "Baden-Württemberg",
    #     ]
    # ]


@pytest.mark.remote
def test_dwd_observations_stations_geojson():

    # Existing combination of parameters
    request = DwdObservationRequest(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL,
    )

    df = request.all().df

    assert not df.empty

    df = df[df[Columns.STATION_ID.value] == "00001"]

    geojson = df.dwd.to_geojson()

    properties = geojson["features"][0]["properties"]
    geometry = geojson["features"][0]["geometry"]

    assert properties["name"] == "Aach"
    assert properties["state"] == "Baden-Württemberg"

    assert geometry == {
        "type": "Point",
        "coordinates": [8.8493, 47.8413, 478.0],
    }
