import logging
from pathlib import Path
from typing import List, Union, Generator

import pandas as pd
from pandas import Timestamp
import dateparser

from wetterdienst.dwd.observations.access import collect_climate_observations_data
from wetterdienst.dwd.metadata.parameter import (
    TIME_RESOLUTION_PARAMETER_MAPPING,
)
from wetterdienst import (
    TimeResolution,
    Parameter,
    PeriodType,
)
from wetterdienst.dwd.observations.stations import (
    metadata_for_climate_observations,
    get_nearby_stations_by_number,
    get_nearby_stations_by_distance,
)
from wetterdienst.dwd.util import parse_enumeration_from_template, parse_enumeration
from wetterdienst.exceptions import InvalidParameterCombination, StartDateEndDateError
from wetterdienst.dwd.metadata.constants import DWD_FOLDER_MAIN
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns

log = logging.getLogger(__name__)


class DWDObservationData:
    """
    The DWDObservationData class represents a request for
    observation data as provided by the DWD service.
    """

    def __init__(
        self,
        station_ids: Union[str, int, List[Union[int, str]]],
        parameter: Union[str, Parameter, List[Union[str, Parameter]]],
        time_resolution: Union[str, TimeResolution],
        period_type: Union[
            Union[None, str, PeriodType], List[Union[str, PeriodType]]
        ] = None,
        start_date: Union[None, str, Timestamp] = None,
        end_date: Union[None, str, Timestamp] = None,
        prefer_local: bool = False,
        write_file: bool = False,
        folder: Union[str, Path] = DWD_FOLDER_MAIN,
        tidy_data: bool = True,
        humanize_column_names: bool = False,
    ) -> None:
        """
        Class with mostly flexible arguments to define a request regarding DWD data.
        Special handling for period type. If start_date/end_date are given all period
        types are considered and merged together and the data is filtered for the given
        dates afterwards.

        :param station_ids: definition of stations by str, int or list of str/int,
                            will be parsed to list of int
        :param parameter:           Observation measure
        :param time_resolution:     Frequency/granularity of measurement interval
        :param period_type:         Recent or historical files (optional), if None
                                    and start_date and end_date None, all period
                                    types are used
        :param start_date:          Replacement for period type to define exact time
                                    of requested data, if used, period type will be set
                                    to all period types (hist, recent, now)
        :param end_date:            Replacement for period type to define exact time
                                    of requested data, if used, period type will be set
                                    to all period types (hist, recent, now)
        :param prefer_local:        Definition if data should rather be taken from a
                                    local source
        :param write_file:          Should data be written to a local file
        :param folder:              Place where file lists (and station data) are stored
        :param tidy_data:           Reshape DataFrame to a more tidy
                                    and row-based version of data
        :param humanize_column_names: Replace column names by more meaningful ones
        """

        try:
            self.station_ids = pd.Series(station_ids).astype(int).tolist()
        except ValueError:
            raise ValueError("List of station id's can not be parsed to integers.")

        self.parameter = (
            pd.Series(parameter)
            .apply(parse_enumeration_from_template, args=(Parameter,))
            .tolist()
        )

        self.time_resolution = parse_enumeration_from_template(
            time_resolution, TimeResolution
        )

        # If any date is given, use all period types and filter, else if not period type
        # is given use all period types
        if start_date or end_date or not period_type:
            self.period_type = [*PeriodType]
        # Otherwise period types will be parsed
        else:
            # For the case that a period_type is given, parse the period type(s)
            self.period_type = (
                pd.Series(period_type)
                .apply(parse_enumeration_from_template, args=(PeriodType,))
                .sort_values()
                .tolist()
            )

        if start_date or end_date:
            # If only one date given, make the other one equal
            if not start_date:
                start_date = end_date

            if not end_date:
                end_date = start_date

            self.start_date = Timestamp(dateparser.parse(start_date))
            self.end_date = Timestamp(dateparser.parse(end_date))

            if not self.start_date <= self.end_date:
                raise StartDateEndDateError(
                    "Error: 'start_date' must be smaller or equal to 'end_date'."
                )
        else:
            self.start_date = start_date
            self.end_date = end_date

        self.prefer_local = prefer_local
        self.write_file = write_file
        self.folder = folder
        # If more then one parameter requested, automatically tidy data
        self.tidy_data = len(self.parameter) == 2 or tidy_data
        self.humanize_column_names = humanize_column_names

    def __eq__(self, other):
        return [
            self.station_ids,
            self.parameter,
            self.time_resolution,
            self.period_type,
            self.start_date,
            self.end_date,
        ] == other

    def __str__(self):
        station_ids_joined = "& ".join(
            [str(station_id) for station_id in self.station_ids]
        )
        return ", ".join(
            [
                f"station_ids {station_ids_joined}",
                "& ".join([parameter.value for parameter in self.parameter]),
                self.time_resolution.value,
                "& ".join([period_type.value for period_type in self.period_type]),
                self.start_date.value,
                self.end_date.value,
            ]
        )

    def collect_data(self) -> Generator[pd.DataFrame, None, None]:
        """
        Method to collect data for a defined request. The function is build as generator
        in order to not cloak the memory thus if the user wants the data as one pandas
        DataFrame the generator has to be casted to a DataFrame manually via
        pd.concat(list(request.collect_data()).

        :return: A generator yielding a pandas.DataFrame per station.
        """
        for station_id in self.station_ids:
            df_station = pd.DataFrame()

            for parameter in self.parameter:
                df_parameter_period = pd.DataFrame()

                for period_type in self.period_type:
                    try:
                        df_period = collect_climate_observations_data(
                            station_ids=[station_id],
                            parameter=parameter,
                            time_resolution=self.time_resolution,
                            period_type=period_type,
                            folder=self.folder,
                            prefer_local=self.prefer_local,
                            write_file=self.write_file,
                            tidy_data=self.tidy_data,
                            humanize_column_names=self.humanize_column_names,
                        )
                    except InvalidParameterCombination:
                        log.info(
                            f"Combination for "
                            f"{parameter.value}/"
                            f"{self.time_resolution.value}/"
                            f"{period_type} does not exist and is skipped."
                        )

                        continue

                    # Filter out values which already are in the DataFrame
                    try:
                        df_period = df_period[
                            ~df_period[DWDMetaColumns.DATE.value].isin(
                                df_parameter_period[DWDMetaColumns.DATE.value]
                            )
                        ]
                    except KeyError:
                        pass

                    df_parameter_period = df_parameter_period.append(
                        df_period, ignore_index=True
                    )

                df_station = df_station.append(df_parameter_period, ignore_index=True)

            # Filter for dates range if start_date and end_date are defined
            if self.start_date:
                df_station = df_station[
                    (df_station[DWDMetaColumns.DATE.value] >= self.start_date)
                    & (df_station[DWDMetaColumns.DATE.value] <= self.end_date)
                ]

            # Empty dataframe should be skipped
            if df_station.empty:
                continue

            yield df_station

    def collect_safe(self):
        """
        Collect all data from ``DWDObservationData``.
        """

        data = list(self.collect_data())

        if not data:
            raise ValueError("No data available for given constraints")

        return pd.concat(data)


class DWDObservationSites:
    """
    The DWDObservationSites class represents a request for
    station data as provided by the DWD service.
    """

    def __init__(
        self,
        parameter: Union[str, Parameter, List[Union[str, Parameter]]],
        time_resolution: Union[
            None, str, TimeResolution, List[Union[str, TimeResolution]]
        ] = None,
        period_type: Union[
            Union[None, str, PeriodType], List[Union[str, PeriodType]]
        ] = None,
        start_date: Union[None, str, Timestamp] = None,
        end_date: Union[None, str, Timestamp] = None,
    ) -> None:
        """
        Request list of stations from DWD observation data, related to parameter,
        time_resolution and period_type.

        :param parameter:           Observation measure
        :param time_resolution:     Frequency/granularity of measurement interval
        :param period_type:         Recent or historical files (optional), if None
                                    and start_date and end_date None, all period
                                    types are used
        :param start_date:          Start date of timespan where measurements
                                    should be available
        :param end_date:            End date of timespan where measurements
                                    should be available
        """
        self.parameter = parameter
        self.time_resolution = time_resolution
        self.period_type = period_type
        self.start_date = start_date
        self.end_date = end_date

    def all(self) -> pd.DataFrame:

        return metadata_for_climate_observations(
            parameter=self.parameter,
            time_resolution=self.time_resolution,
            period_type=self.period_type,
        )

    def nearby_radius(
        self,
        latitude: float,
        longitude: float,
        max_distance_in_km: int,
    ) -> pd.DataFrame:
        return get_nearby_stations_by_distance(
            latitude=latitude,
            longitude=longitude,
            max_distance_in_km=max_distance_in_km,
            parameter=self.parameter,
            time_resolution=self.time_resolution,
            period_type=self.period_type,
            minimal_available_date=self.start_date,
            maximal_available_date=self.end_date,
        )

    def nearby_number(
        self,
        latitude: float,
        longitude: float,
        num_stations_nearby: int,
    ) -> pd.DataFrame:

        return get_nearby_stations_by_number(
            latitude=latitude,
            longitude=longitude,
            num_stations_nearby=num_stations_nearby,
            parameter=self.parameter,
            time_resolution=self.time_resolution,
            period_type=self.period_type,
            minimal_available_date=self.start_date,
            maximal_available_date=self.end_date,
        )


class DWDObservationMetadata:
    """
    Inquire metadata about weather observations on the
    public DWD data repository.
    """

    def __init__(
        self,
        parameter: Union[None, str, Parameter, List[Union[str, Parameter]]] = None,
        time_resolution: Union[
            None, str, TimeResolution, List[Union[str, TimeResolution]]
        ] = None,
        period_type: Union[None, str, PeriodType, List[Union[str, PeriodType]]] = None,
    ):
        self.parameter = parameter
        self.time_resolution = time_resolution
        self.period_type = period_type

    def discover_parameters(self) -> dict:
        """
        Function to print/discover available time_resolution/parameter/period_type
        combinations.

        :param parameter:               Observation measure
        :param time_resolution:         Frequency/granularity of measurement interval
        :param period_type:             Recent or historical files

        :return:                        Available parameter combinations.
        """

        parameter = self.parameter
        time_resolution = self.time_resolution
        period_type = self.period_type

        if not parameter:
            parameter = [*Parameter]
        if not time_resolution:
            time_resolution = [*TimeResolution]
        if not period_type:
            period_type = [*PeriodType]

        time_resolution = parse_enumeration(TimeResolution, time_resolution)
        parameter = parse_enumeration(Parameter, parameter)
        period_type = parse_enumeration(PeriodType, period_type)

        trp_mapping_filtered = {
            ts: {
                par: [p for p in pt if p in period_type]
                for par, pt in parameters_and_period_types.items()
                if par in parameter
            }
            for ts, parameters_and_period_types in TIME_RESOLUTION_PARAMETER_MAPPING.items()  # noqa:E501,B950
            if ts in time_resolution
        }

        time_resolution_parameter_mapping = {
            str(time_resolution): {
                str(parameter): [str(period) for period in periods]
                for parameter, periods in parameters_and_periods.items()
                if periods
            }
            for time_resolution, parameters_and_periods in trp_mapping_filtered.items()
            if parameters_and_periods
        }

        return time_resolution_parameter_mapping

