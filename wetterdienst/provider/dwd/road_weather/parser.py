# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
import os
import pandas as pd
import pdbufr
from io import BytesIO
from pathlib import Path
from typing import List, Tuple, Dict

from wetterdienst.provider.dwd.road_weather.metadata.dataset import DwdObservationRoadWeatherDataset

os.environ['ECCODES_DIR'] = '/usr/local/share/eccodes'
time_columns = ('year', 'month', 'day', 'hour', 'minute')
TMP_BUFR_FILE_PATH = Path('/', 'tmp', 'bufr_temp.bufr')

log = logging.getLogger(__name__)
COLUMNS_FILTER_MAPPING = \
    {
        DwdObservationRoadWeatherDataset.ROAD_SURFACE_TEMPERATURE:
            {
                'filters': {'depthBelowLandSurface': [0.05, 0.15, 0.3]},
                'columns': ('shortStationName', 'positionOfRoadSensors')
            },
        DwdObservationRoadWeatherDataset.ROAD_SURFACE_CONDITION: {
            'filters': {}, 'columns': ('shortStationName', 'timePeriod', 'positionOfRoadSensors')},
        DwdObservationRoadWeatherDataset.WATER_FILM_THICKNESS: {'filters': {},
                                                                'columns': ('shortStationName', 'timePeriod')},
        DwdObservationRoadWeatherDataset.TEMPERATURE_AIR: {'filters': {},
                                                           'columns': ('shortStationName',
                                                                       'heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform')},
        DwdObservationRoadWeatherDataset.DEW_POINT: {'filters': {},
                                                     'columns': ('shortStationName',
                                                                 'heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform')},
        DwdObservationRoadWeatherDataset.RELATIVE_HUMIDITY: {'filters': {},
                                                             'columns': ('shortStationName',
                                                                         'heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform')},
        DwdObservationRoadWeatherDataset.WIND_DIRECTION: {'filters': {},
                                                          'columns': ('shortStationName',
                                                                      'heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform')},
        DwdObservationRoadWeatherDataset.WIND: {'filters': {},
                                                'columns': ('shortStationName',
                                                            'heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform')},
        DwdObservationRoadWeatherDataset.WIND_EXTREME: {'filters': {}, 'columns': (
            'shortStationName', 'timePeriod', 'heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform')},
        DwdObservationRoadWeatherDataset.WIND_EXTREME_DIRECTION: {'filters': {}, 'columns': (
            'shortStationName', 'timePeriod', 'heightOfSensorAboveLocalGroundOrDeckOfMarinePlatform')},
        DwdObservationRoadWeatherDataset.PRECIPITATION_TYPE: {'filters': {},
                                                              'columns': ('shortStationName', 'timePeriod')},
        DwdObservationRoadWeatherDataset.TOTAL_PRECIPITATION: {'filters': {},
                                                               'columns': ('shortStationName', 'timePeriod')},
        DwdObservationRoadWeatherDataset.INTENSITY_OF_PRECIPITATION: {'filters': {},
                                                                      'columns': ('shortStationName', 'timePeriod')},
        DwdObservationRoadWeatherDataset.INTENSITY_OF_PHENOMENA: {'filters': {},
                                                                  'columns': ('shortStationName', 'timePeriod')},
        DwdObservationRoadWeatherDataset.HORIZONTAL_VISIBILITY: {'filters': {}, 'columns': ('shortStationName',)},
    }
metadata_columns = ('stationOrSiteName',
                    'shortStationName',
                    'stateOrFederalStateIdentifier',
                    'latitude',
                    'longitude',
                    'heightOfStationGroundAboveMeanSeaLevel',
                    'typeOfRoad',
                    'typeOfConstruction')


def parse_dwd_road_weather_data(
        filenames_and_files: List[Tuple[str, bytes]],
) -> Tuple[List[Dict[str, pd.DataFrame]], pd.DataFrame]:
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
    data_and_metadata = [
        _parse_dwd_road_weather_data(filename_and_file)
        for filename_and_file in filenames_and_files
    ]
    data = [data_tuple[0] for data_tuple in data_and_metadata]
    metadata = pd.concat([data_tuple[1] for data_tuple in data_and_metadata])
    metadata.drop_duplicates(inplace=True)

    return data, metadata


def _parse_dwd_road_weather_data(
        filename_and_file: Tuple[str, BytesIO],
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
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

    metadata = pdbufr.read_bufr(TMP_BUFR_FILE_PATH, columns=metadata_columns)
    data = {}
    for key, item in COLUMNS_FILTER_MAPPING.items():
        if item['filters']:
            for filter, arguments in item['filters'].items():
                for arg in arguments:
                    data[f"{key.value}_{filter}_{arg}"] = \
                        pdbufr.read_bufr(
                            TMP_BUFR_FILE_PATH,
                            columns=item['columns'] + time_columns + (key.value,),
                            filters={filter: arg}
                        )
        else:
            data[key.value] = pdbufr.read_bufr(TMP_BUFR_FILE_PATH,
                                               columns=item['columns'] + time_columns + (key.value,))

    TMP_BUFR_FILE_PATH.unlink()

    return data, metadata
