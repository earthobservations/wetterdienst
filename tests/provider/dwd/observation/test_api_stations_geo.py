# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from datetime import datetime

import numpy as np
import pandas as pd
import pytest
import pytz
from pandas._libs.tslibs.timestamps import Timestamp
from pandas._testing import assert_frame_equal

from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)
from wetterdienst.util.geo import Coordinates, derive_nearest_neighbours

EXPECTED_STATIONS_DF = pd.DataFrame.from_records(
    [
        (
            "02480",
            Timestamp("2004-09-01 00:00:00", tzinfo=pytz.UTC),
            108.0,
            50.0643,
            8.993,
            "Kahl/Main",
            "Bayern",
            9.759384982994229,
        ),
        (
            "04411",
            Timestamp("2002-01-24 00:00:00", tzinfo=pytz.UTC),
            155.0,
            49.9195,
            8.9671,
            "Schaafheim-Schlierbach",
            "Hessen",
            10.156943448624304,
        ),
        (
            "07341",
            Timestamp("2005-07-16 00:00:00", tzinfo=pytz.UTC),
            119.0,
            50.0900,
            8.7862,
            "Offenbach-Wetterpark",
            "Hessen",
            12.891318342515483,
        ),
    ],
    columns=["station_id", "from_date", "height", "latitude", "longitude", "name", "state", "distance"],
)


@pytest.mark.remote
def test_dwd_observation_stations_filter_by_rank_single(default_settings):
    # Test for one nearest station
    stations = DwdObservationRequest(
        DwdObservationDataset.TEMPERATURE_AIR,
        DwdObservationResolution.HOURLY,
        DwdObservationPeriod.HISTORICAL,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20),
        settings=default_settings,
    ).filter_by_rank(
        latlon=(50.0, 8.9),
        rank=1,
    )
    df = stations.df.drop(columns="to_date")
    assert_frame_equal(df.iloc[[0], :], EXPECTED_STATIONS_DF.iloc[[0], :])
    values = stations.values.all()
    assert_frame_equal(values.df_stations.iloc[[0], :].drop(columns="to_date"), EXPECTED_STATIONS_DF.iloc[[0], :])


@pytest.mark.remote
def test_dwd_observation_stations_filter_by_rank_multiple(default_settings):
    stations = DwdObservationRequest(
        DwdObservationDataset.TEMPERATURE_AIR,
        DwdObservationResolution.HOURLY,
        DwdObservationPeriod.HISTORICAL,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20),
        settings=default_settings,
    ).filter_by_rank(
        latlon=(50.0, 8.9),
        rank=3,
    )
    df = stations.df.drop("to_date", axis="columns")
    assert_frame_equal(
        df.iloc[
            :3,
        ],
        EXPECTED_STATIONS_DF,
    )
    values = stations.values.all()
    assert_frame_equal(values.df_stations.drop(columns="to_date"), EXPECTED_STATIONS_DF)


@pytest.mark.remote
def test_dwd_observation_stations_nearby_distance(default_settings):
    request = DwdObservationRequest(
        DwdObservationDataset.TEMPERATURE_AIR,
        DwdObservationResolution.HOURLY,
        DwdObservationPeriod.HISTORICAL,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20),
        settings=default_settings,
    )
    # Kilometers
    nearby_station = request.filter_by_distance(latlon=(50.0, 8.9), distance=16.13, unit="km")
    nearby_station = nearby_station.df.drop("to_date", axis="columns")

    assert_frame_equal(nearby_station, EXPECTED_STATIONS_DF)

    # Miles
    nearby_station = request.filter_by_distance(latlon=(50.0, 8.9), distance=10.03, unit="mi")
    nearby_station = nearby_station.df.drop(columns="to_date")

    assert_frame_equal(nearby_station, EXPECTED_STATIONS_DF)


@pytest.mark.remote
def test_dwd_observation_stations_bbox(default_settings):
    request = DwdObservationRequest(
        DwdObservationDataset.TEMPERATURE_AIR,
        DwdObservationResolution.HOURLY,
        DwdObservationPeriod.HISTORICAL,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20),
        settings=default_settings,
    )
    nearby_station = request.filter_by_bbox(left=8.7862, bottom=49.9195, right=8.993, top=50.0900)
    nearby_station = nearby_station.df.drop("to_date", axis="columns")

    assert_frame_equal(nearby_station, EXPECTED_STATIONS_DF.drop(columns=["distance"]))


@pytest.mark.remote
def test_dwd_observation_stations_empty(default_settings):
    request = DwdObservationRequest(
        DwdObservationDataset.TEMPERATURE_AIR,
        DwdObservationResolution.HOURLY,
        DwdObservationPeriod.HISTORICAL,
        datetime(2020, 1, 1),
        datetime(2020, 1, 20),
        settings=default_settings,
    )

    # Bbox
    assert request.filter_by_bbox(
        left=-100,
        bottom=-20,
        right=-90,
        top=-10,
    ).df.empty


@pytest.mark.remote
def test_dwd_observation_stations_fail(default_settings):
    # Number
    with pytest.raises(ValueError):
        DwdObservationRequest(
            DwdObservationDataset.TEMPERATURE_AIR,
            DwdObservationResolution.HOURLY,
            DwdObservationPeriod.HISTORICAL,
            datetime(2020, 1, 1),
            datetime(2020, 1, 20),
            settings=default_settings,
        ).filter_by_rank(
            latlon=(51.4, 9.3),
            rank=0,
        )
    # Distance
    with pytest.raises(ValueError):
        DwdObservationRequest(
            DwdObservationDataset.TEMPERATURE_AIR,
            DwdObservationResolution.HOURLY,
            DwdObservationPeriod.HISTORICAL,
            datetime(2020, 1, 1),
            datetime(2020, 1, 20),
            settings=default_settings,
        ).filter_by_distance(
            latlon=(51.4, 9.3),
            distance=-1,
        )
    # Bbox
    with pytest.raises(ValueError):
        DwdObservationRequest(
            DwdObservationDataset.TEMPERATURE_AIR,
            DwdObservationResolution.HOURLY,
            DwdObservationPeriod.HISTORICAL,
            datetime(2020, 1, 1),
            datetime(2020, 1, 20),
            settings=default_settings,
        ).filter_by_bbox(left=10, bottom=10, right=5, top=5)


def test_derive_nearest_neighbours():
    coords = Coordinates(np.array([50.0, 51.4]), np.array([8.9, 9.3]))

    metadata = pd.DataFrame(
        {
            "station_id": [4371, 4373, 4411, 13904, 13965, 15207],
            "latitude": [52.1042, 52.8568, 49.9195, 55.0, 48.2639, 51.2835],
            "longitude": [8.7521, 11.1319, 8.9671, 6.3333, 8.8134, 9.359],
        }
    )

    distances, indices_nearest_neighbours = derive_nearest_neighbours(
        latitudes=metadata["latitude"].values,
        longitudes=metadata["longitude"].values,
        coordinates=coords,
        number_nearby=1,
    )

    np.testing.assert_array_almost_equal(distances, np.array([[0.001594], [0.002133]]))

    np.testing.assert_array_almost_equal(indices_nearest_neighbours, np.array([[2], [5]]))
