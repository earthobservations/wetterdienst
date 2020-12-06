import logging
from abc import abstractmethod
from datetime import datetime
from typing import Union

import numpy as np
import pandas as pd
import pytz
from pandas import Timestamp


from wetterdienst.core.core import Core
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.util import parse_datetime
from wetterdienst.exceptions import StartDateEndDateError
from wetterdienst.metadata.columns import Columns
from wetterdienst.util.geo import Coordinates, derive_nearest_neighbours

logger = logging.getLogger(__name__)

KM_EARTH_RADIUS = 6371


class StationsCore(Core):
    """ Core for stations information of a source """

    # Columns that should be contained within any stations information
    _base_columns = (
        Columns.STATION_ID.value,
        Columns.FROM_DATE.value,
        Columns.TO_DATE.value,
        Columns.STATION_HEIGHT.value,
        Columns.LATITUDE.value,
        Columns.LONGITUDE.value,
        Columns.STATION_NAME.value,
        Columns.STATE.value,
    )
    # TODO: eventually this can be matched with the type coercion of station data to get
    #  similar types of floats and strings
    # Dtype mapping for stations
    _dtype_mapping = {
        Columns.STATION_ID.value: str,
        Columns.STATION_HEIGHT.value: float,
        DWDMetaColumns.LATITUDE.value: float,
        DWDMetaColumns.LONGITUDE.value: float,
        DWDMetaColumns.STATION_NAME.value: str,
        DWDMetaColumns.STATE.value: str,
    }

    def __init__(
        self,
        start_date: Union[None, str, Timestamp] = None,
        end_date: Union[None, str, Timestamp] = None,
    ) -> None:
        """

        :param start_date: start date for filtering stations for their available data
        :param end_date: end date for filtering stations for their available data
        """
        # TODO: make datetimes timezone sensible
        start_date = (
            start_date
            if not start_date or isinstance(start_date, datetime)
            else parse_datetime(start_date)
        )
        end_date = (
            end_date
            if not end_date or isinstance(end_date, datetime)
            else parse_datetime(end_date)
        )

        start_date = start_date.replace(tzinfo=self.tz) if start_date else None
        end_date = end_date.replace(tzinfo=self.tz) if end_date else None

        if start_date and end_date:
            if start_date > end_date:
                raise StartDateEndDateError("'start_date' has to be before 'end_date'")

        self.start_date = start_date
        self.end_date = end_date

    def all(self) -> pd.DataFrame:
        """
        Wraps the _all method and applies date filters.

        :return: pandas.DataFrame with the information of different available stations
        """
        metadata_df = self._all()

        for column in self._base_columns:
            if column not in metadata_df:
                metadata_df[column] = pd.NA

        metadata_df = self._coerce_meta_fields(metadata_df)

        if self.start_date:
            metadata_df = metadata_df[
                metadata_df[DWDMetaColumns.FROM_DATE.value] <= self.start_date
            ]

        if self.end_date:
            metadata_df = metadata_df[
                metadata_df[DWDMetaColumns.TO_DATE.value] >= self.end_date
            ]

        return metadata_df

    def _coerce_meta_fields(self, df) -> pd.DataFrame:
        """ Method for filed coercion. """
        df = df.astype(self._dtype_mapping)

        df[Columns.FROM_DATE.value] = pd.to_datetime(
            df[Columns.FROM_DATE.value], infer_datetime_format=True
        ).dt.tz_localize(pytz.UTC)
        df[Columns.TO_DATE.value] = pd.to_datetime(
            df[Columns.TO_DATE.value], infer_datetime_format=True
        ).dt.tz_localize(pytz.UTC)

        return df

    @abstractmethod
    def _all(self) -> pd.DataFrame:
        """
        Abstract method for gathering of sites information for a given implementation.
        Information consist of a DataFrame with station ids, location, name, etc

        :return: pandas.DataFrame with the information of different available sites
        """
        pass

    def nearby_number(
        self,
        latitude: float,
        longitude: float,
        num_stations_nearby: int,
    ) -> pd.DataFrame:
        """
        Wrapper for get_nearby_stations_by_number using the given parameter set. Returns
        nearest stations defined by number.

        :param latitude: latitude in degrees
        :param longitude: longitude in degrees
        :param num_stations_nearby: number of stations to be returned, greater 0
        :return: pandas.DataFrame with station information for the selected stations
        """
        if num_stations_nearby <= 0:
            raise ValueError("'num_stations_nearby' has to be at least 1.")

        coords = Coordinates(np.array(latitude), np.array(longitude))

        metadata = self.all()

        metadata = metadata.reset_index(drop=True)

        distances, indices_nearest_neighbours = derive_nearest_neighbours(
            metadata.LAT.values, metadata.LON.values, coords, num_stations_nearby
        )

        distances = pd.Series(distances)
        indices_nearest_neighbours = pd.Series(indices_nearest_neighbours)

        # If num_stations_nearby is higher then the actual amount of stations
        # further indices and distances are added which have to be filtered out
        distances = distances[: min(metadata.shape[0], num_stations_nearby)]
        indices_nearest_neighbours = indices_nearest_neighbours[
            : min(metadata.shape[0], num_stations_nearby)
        ]

        distances_km = np.array(distances * KM_EARTH_RADIUS)

        metadata_location = metadata.iloc[indices_nearest_neighbours, :].reset_index(
            drop=True
        )

        metadata_location[DWDMetaColumns.DISTANCE_TO_LOCATION.value] = distances_km

        if metadata_location.empty:
            logger.warning(
                f"No weather stations were found for coordinate "
                f"{latitude}°N and {longitude}°E "
            )

        return metadata_location

    def nearby_radius(
        self,
        latitude: float,
        longitude: float,
        max_distance_in_km: int,
    ) -> pd.DataFrame:
        """
        Wrapper for get_nearby_stations_by_distance using the given parameter set.
        Returns nearest stations defined by distance (km).

        :param latitude: latitude in degrees
        :param longitude: longitude in degrees
        :param max_distance_in_km: distance (km) for which stations will be selected
        :return: pandas.DataFrame with station information for the selected stations
        """
        # Theoretically a distance of 0 km is possible
        if max_distance_in_km < 0:
            raise ValueError("'max_distance_in_km' has to be at least 0.0.")

        metadata = self.all()

        all_nearby_stations = self.nearby_number(latitude, longitude, metadata.shape[0])

        nearby_stations_in_distance = all_nearby_stations[
            all_nearby_stations[DWDMetaColumns.DISTANCE_TO_LOCATION.value]
            <= max_distance_in_km
        ]

        return nearby_stations_in_distance.reset_index(drop=True)
