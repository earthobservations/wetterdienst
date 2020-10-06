import logging
from typing import List, Union, Generator

import pandas as pd
from pandas import Timestamp
import dateparser

from wetterdienst.dwd.index import _create_file_index_for_dwd_server
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
from wetterdienst.dwd.observations.store import StorageAdapter
from wetterdienst.dwd.util import (
    parse_enumeration_from_template,
    parse_enumeration,
    build_parameter_identifier,
)
from wetterdienst.exceptions import InvalidParameterCombination, StartDateEndDateError
from wetterdienst.dwd.metadata.constants import DWDCDCBase
from wetterdienst.dwd.metadata.column_names import (
    DWDMetaColumns,
    DWDOrigDataColumns,
    DWDDataColumns,
)

log = logging.getLogger(__name__)

POSSIBLE_ID_VARS = (
    DWDMetaColumns.STATION_ID.value,
    DWDMetaColumns.DATE.value,
    DWDMetaColumns.FROM_DATE.value,
    DWDMetaColumns.TO_DATE.value,
)

POSSIBLE_DATE_VARS = (
    DWDMetaColumns.DATE.value,
    DWDMetaColumns.FROM_DATE.value,
    DWDMetaColumns.TO_DATE.value,
)


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
        storage: StorageAdapter = None,
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
        :param storage:             Storage adapter.
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

        self.storage = storage

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
        # Remove HDF file for given parameters and period_types if defined by storage
        if self.storage and self.storage.invalidate:
            self._invalidate_storage()

        for station_id in self.station_ids:
            df_station = []

            for parameter in self.parameter:
                df_parameter = self._collect_parameter(parameter, station_id)

                df_station.append(df_parameter)

            df_station = pd.concat(df_station)

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

    def _collect_parameter(self, parameter: Parameter, station_id: int) -> pd.DataFrame:
        df_parameter = pd.DataFrame()

        for period_type in self.period_type:
            parameter_identifier = build_parameter_identifier(
                parameter, self.time_resolution, period_type, station_id
            )

            storage = None
            if self.storage:
                storage = self.storage.hdf5(
                    parameter=parameter,
                    time_resolution=self.time_resolution,
                    period_type=period_type,
                )

                df_period = storage.restore(station_id)

                if not df_period.empty:
                    log.info(f"Data for {parameter_identifier} restored from local.")

                    df_parameter = df_parameter.append(df_period)

                    continue

            log.info(f"Acquiring observations data for {parameter_identifier}.")

            try:
                df_period = collect_climate_observations_data(
                    station_id, parameter, self.time_resolution, period_type
                )
            except InvalidParameterCombination:
                log.info(
                    f"Invalid combination {parameter.value}/"
                    f"{self.time_resolution.value}/{period_type} is skipped."
                )

                df_period = pd.DataFrame()

            if self.storage and self.storage.persist:
                storage.store(station_id=station_id, df=df_period)

            # Filter out values which already are in the DataFrame
            try:
                df_period = df_period[
                    ~df_period[DWDMetaColumns.DATE.value].isin(
                        df_parameter[DWDMetaColumns.DATE.value]
                    )
                ]
            except KeyError:
                pass

            df_parameter = df_parameter.append(df_period)

        if self.tidy_data:
            df_parameter = self._tidy_up_data(df_parameter, parameter)

        # Assign meaningful column names (humanized).
        if self.humanize_column_names:
            hcnm = self._create_humanized_column_names_mapping(
                self.time_resolution, parameter
            )

            if self.tidy_data:
                df_parameter[DWDMetaColumns.ELEMENT.value] = df_parameter[
                    DWDMetaColumns.ELEMENT.value
                ].apply(lambda x: hcnm[x])
            else:
                df_parameter = df_parameter.rename(columns=hcnm)

        return df_parameter

    def collect_safe(self):
        """
        Collect all data from ``DWDObservationData``.
        """

        data = list(self.collect_data())

        if not data:
            raise ValueError("No data available for given constraints")

        return pd.concat(data)

    def _invalidate_storage(self):
        for parameter in self.parameter:
            for period_type in self.period_type:
                storage = self.storage.hdf5(
                    parameter=parameter,
                    time_resolution=self.time_resolution,
                    period_type=period_type,
                )

                storage.invalidate()

    @staticmethod
    def _tidy_up_data(df: pd.DataFrame, parameter: Parameter) -> pd.DataFrame:
        """
        Function to create a tidy DataFrame by reshaping it, putting quality in a
        separate column and setting an extra column with the parameter.

        :param df:          DataFrame to be tidied
        :param parameter:   the parameter that is written in a column to identify a set
                            of different parameters amongst each other

        :return:            The tidied DataFrame
        """
        id_vars = []
        date_vars = []

        # Add id columns based on metadata columns
        for column in POSSIBLE_ID_VARS:
            if column in df:
                id_vars.append(column)
                if column in POSSIBLE_DATE_VARS:
                    date_vars.append(column)

        # Extract quality
        # Set empty quality for first columns until first QN column
        quality = pd.Series()
        column_quality = pd.Series()

        for column in df:
            # If is quality column, overwrite current "column quality"
            if column.startswith("QN"):
                column_quality = df.pop(column)
            else:
                quality = quality.append(column_quality)

        df_tidy = df.melt(
            id_vars=id_vars,
            var_name=DWDMetaColumns.ELEMENT.value,
            value_name=DWDMetaColumns.VALUE.value,
        )

        df_tidy[DWDMetaColumns.PARAMETER.value] = parameter.name

        df_tidy[DWDMetaColumns.QUALITY.value] = quality.reset_index(drop=True).astype(
            pd.Int64Dtype()
        )

        # Reorder properly
        df_tidy = df_tidy.reindex(
            columns=[
                DWDMetaColumns.STATION_ID.value,
                DWDMetaColumns.PARAMETER.value,
                DWDMetaColumns.ELEMENT.value,
                *date_vars,
                DWDMetaColumns.VALUE.value,
                DWDMetaColumns.QUALITY.value,
            ]
        )

        return df_tidy

    @staticmethod
    def _create_humanized_column_names_mapping(
        time_resolution: TimeResolution, parameter: Parameter
    ) -> dict:
        """
        Function to create an extend humanized column names mapping. The function
        takes care of the special cases of quality columns. Therefor it requires the
        time resolution and parameter.

        Args:
            time_resolution: time resolution enumeration
            parameter: parameter enumeration

        Returns:
            dictionary with mappings extended by quality columns mappings
        """
        column_name_mapping = {
            orig_column.value: humanized_column.value
            for orig_column, humanized_column in zip(
                DWDOrigDataColumns[time_resolution.name][parameter.name],
                DWDDataColumns[time_resolution.name][parameter.name],
            )
        }

        return column_name_mapping


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

    def describe_fields(self):

        file_index = _create_file_index_for_dwd_server(
            parameter=self.parameter,
            time_resolution=self.time_resolution,
            period_type=self.period_type,
            cdc_base=DWDCDCBase.CLIMATE_OBSERVATIONS,
        )

        file_index = file_index[
            file_index[DWDMetaColumns.FILENAME.value].str.contains("DESCRIPTION_")
        ]

        description_file_url = str(
            file_index[DWDMetaColumns.FILENAME.value].tolist()[0]
        )

        from wetterdienst.dwd.observations.fields import read_description

        document = read_description(description_file_url)

        return document
