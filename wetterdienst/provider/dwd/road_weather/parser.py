# -*- coding: utf-8 -*-
# Copyright (c) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import pdbufr

from wetterdienst.provider.dwd.road_weather.metadata.dataset import (
    DwdObservationRoadWeatherDataset,
)

os.environ["ECCODES_DIR"] = "/usr/local/share/eccodes"
time_columns = ("year", "month", "day", "hour", "minute")
TMP_BUFR_FILE_PATH = Path("/", "tmp", "bufr_temp.bufr")

DEFAULT_TIME_PERIOD = -1
DEFAULT_SENSOR_HEIGHT = 0
DEFAULT_SENSOR_POSITION = 99

log = logging.getLogger(__name__)
COLUMNS_FILTER_MAPPING = {
    DwdObservationRoadWeatherDataset.ROAD_SURFACE_TEMPERATURE: {
        "filters": {},
        "columns": ("shortStationName", "positionOfRoadSensors"),
    },
    DwdObservationRoadWeatherDataset.ROAD_SURFACE_CONDITION: {
        "filters": {},
        "columns": ("shortStationName", "timePeriod", "positionOfRoadSensors"),
    },
    DwdObservationRoadWeatherDataset.WATER_FILM_THICKNESS: {
        "filters": {},
        "columns": ("shortStationName", "timePeriod"),
    },
    DwdObservationRoadWeatherDataset.TEMPERATURE_AIR: {
        "filters": {},
        "columns": (
            "shortStationName",
            "heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform",
        ),
    },
    DwdObservationRoadWeatherDataset.DEW_POINT: {
        "filters": {},
        "columns": (
            "shortStationName",
            "heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform",
        ),
    },
    DwdObservationRoadWeatherDataset.RELATIVE_HUMIDITY: {
        "filters": {},
        "columns": (
            "shortStationName",
            "heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform",
        ),
    },
    DwdObservationRoadWeatherDataset.WIND_DIRECTION: {
        "filters": {},
        "columns": (
            "shortStationName",
            "heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform",
        ),
    },
    DwdObservationRoadWeatherDataset.WIND: {
        "filters": {},
        "columns": (
            "shortStationName",
            "heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform",
        ),
    },
    DwdObservationRoadWeatherDataset.WIND_EXTREME: {
        "filters": {},
        "columns": (
            "shortStationName",
            "timePeriod",
            "heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform",
        ),
    },
    DwdObservationRoadWeatherDataset.WIND_EXTREME_DIRECTION: {
        "filters": {},
        "columns": (
            "shortStationName",
            "timePeriod",
            "heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform",
        ),
    },
    DwdObservationRoadWeatherDataset.PRECIPITATION_TYPE: {
        "filters": {},
        "columns": ("shortStationName", "timePeriod"),
    },
    DwdObservationRoadWeatherDataset.TOTAL_PRECIPITATION: {
        "filters": {},
        "columns": ("shortStationName", "timePeriod"),
    },
    DwdObservationRoadWeatherDataset.INTENSITY_OF_PRECIPITATION: {
        "filters": {},
        "columns": ("shortStationName", "timePeriod"),
    },
    DwdObservationRoadWeatherDataset.INTENSITY_OF_PHENOMENA: {
        "filters": {},
        "columns": ("shortStationName", "timePeriod"),
    },
    DwdObservationRoadWeatherDataset.HORIZONTAL_VISIBILITY: {
        "filters": {},
        "columns": ("shortStationName",),
    },
}
metadata_columns = (
    "stationOrSiteName",
    "shortStationName",
    "stateOrFederalStateIdentifier",
    "latitude",
    "longitude",
    "heightOfStationGroundAboveMeanSeaLevel",
    "typeOfRoad",
    "typeOfConstruction",
)


def parse_dwd_road_weather_data(
    filenames_and_files: List[Tuple[str, bytes]],
) -> pd.DataFrame:
    """
    This function is used to read the road weather station data from given bytes object.
    The filename is required to defined if and where an error happened.

    Args:
        filenames_and_files: list of tuples of a filename and its local stored file
        that should be read

    Returns:
        pandas.DataFrame with requested data, for different station ids the data is
        still put into one DataFrame
    """
    return pd.concat([_parse_dwd_road_weather_data(filename_and_file) for filename_and_file in filenames_and_files])


def _parse_dwd_road_weather_data(
    filename_and_file: Tuple[str, BytesIO],
) -> pd.DataFrame:
    """
    A wrapping function that only handles data for one station id. The files passed to
    it are thus related to this id. This is important for storing the data locally as
    the DataFrame that is stored should obviously only handle one station at a time.
    Args:
        filename_and_file: the files belonging to one station
        resolution: enumeration of time resolution used to correctly parse the
        date field
    Returns:
        pandas.DataFrame with data from that station, acn be empty if no data is
        provided or local file is not found or has no data in it
    """
    _, bytes_file = filename_and_file

    with open(TMP_BUFR_FILE_PATH, "wb") as file:
        file.write(bytes_file)

    data = {}
    for key, item in COLUMNS_FILTER_MAPPING.items():
        if item["filters"]:
            for filter_for_arg, arguments in item["filters"].items():
                for arg in arguments:
                    data[f"{key.value}_{filter_for_arg}_{arg}"] = pdbufr.read_bufr(
                        TMP_BUFR_FILE_PATH,
                        columns=item["columns"] + time_columns + (key.value,),
                        filters={filter_for_arg: arg},
                    )
        else:
            data[key.value] = pdbufr.read_bufr(
                TMP_BUFR_FILE_PATH,
                columns=item["columns"] + time_columns + (key.value,),
            )

    TMP_BUFR_FILE_PATH.unlink()
    return pd.concat(
        [_adding_multiindex_and_drop_unused_columns(item) for _, item in data.items() if not item.empty],
        axis=1,
    )


def _adding_multiindex_and_drop_unused_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """helping function to restructure data from bufr files"""

    dataframe.index = pd.MultiIndex.from_tuples(
        [
            (
                datetime(row["year"], row["month"], row["day"], row["hour"], row["minute"]),
                row["shortStationName"],
                row["timePeriod"]
                if "timePeriod" in row.index and row["timePeriod"] is not None
                else DEFAULT_TIME_PERIOD,
                row["heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform"]
                if "heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform" in row.index
                and row["heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform"] is not None
                else DEFAULT_SENSOR_HEIGHT,
                row["positionOfRoadSensors"]
                if "positionOfRoadSensors" in row.index and row["positionOfRoadSensors"] is not None
                else DEFAULT_SENSOR_POSITION,
            )
            for idx, row in dataframe.iterrows()
        ],
        names=[
            "timestamp",
            "shortStationName",
            "timePeriod",
            "sensorHeight",
            "sensorPosition",
        ],
    )
    dataframe.sort_index(inplace=True)
    dataframe.drop(
        ["year", "month", "day", "hour", "minute", "shortStationName"],
        axis=1,
        inplace=True,
    )
    if "timePeriod" in dataframe.columns:
        dataframe.drop(["timePeriod"], axis=1, inplace=True)
    if "heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform" in dataframe.columns:
        dataframe.drop(
            ["heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform"],
            axis=1,
            inplace=True,
        )
    if "positionOfRoadSensors" in dataframe.columns:
        dataframe.drop(["positionOfRoadSensors"], axis=1, inplace=True)
    return dataframe.loc[~dataframe.index.duplicated(keep="first")]
