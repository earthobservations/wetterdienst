import logging
from typing import List, Union, Generator, Dict, Optional, Type

import pandas as pd
from pandas import Timestamp
import dateparser

from wetterdienst.core.data import WDDataCore
from wetterdienst.core.sites import WDSitesCore
from wetterdienst.dwd.index import _create_file_index_for_dwd_server
from wetterdienst.dwd.metadata.column_map import create_humanized_column_names_mapping
from wetterdienst.dwd.observations.access import collect_climate_observations_data
from wetterdienst.dwd.observations.metadata.parameter_set import (
    TIME_RESOLUTION_PARAMETER_MAPPING,
)
from wetterdienst.dwd.observations.metadata import (
    DWDObservationPeriodType,
    DWDObservationParameter,
    DWDParameterSet,
    DWDObservationTimeResolution
)
from wetterdienst.dwd.observations.stations import metadata_for_climate_observations
from wetterdienst.dwd.observations.store import StorageAdapter
from wetterdienst.dwd.observations.util.parameter import (
    create_parameter_to_parameter_set_combination,
)
from wetterdienst.dwd.util import (
    parse_enumeration_from_template,
    parse_enumeration,
    build_parameter_set_identifier,
    check_parameters,
)
from wetterdienst.exceptions import (
    InvalidParameterCombination,
    StartDateEndDateError,
    InvalidParameter,
    NoParametersFound,
)
from wetterdienst.dwd.metadata.constants import DWDCDCBase
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns

log = logging.getLogger(__name__)


class DWDObservationData(WDDataCore):
    """
    The DWDObservationData class represents a request for
    observation data as provided by the DWD service.
    """

    def __init__(
        self,
        station_ids: List[Union[int, str]],
        parameters: List[Union[str, DWDObservationParameter, DWDParameterSet]],
        time_resolution: Union[str, DWDObservationTimeResolution],
        period_types: Optional[List[Union[str, DWDObservationPeriodType]]] = None,
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
        :param parameters:           Observation measure
        :param time_resolution:     Frequency/granularity of measurement interval
        :param period_types:         Recent or historical files (optional), if None
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

        self.time_resolution = parse_enumeration_from_template(
            time_resolution, DWDObservationTimeResolution
        )

        self.parameters = []

        for parameter in pd.Series(parameters):
            try:
                (
                    parameter,
                    parameter_set,
                ) = create_parameter_to_parameter_set_combination(
                    parameter, self.time_resolution
                )
                self.parameters.append((parameter, parameter_set))
            except InvalidParameter as e:
                log.info(str(e))

        if not self.parameters:
            raise NoParametersFound(f"No parameters could be parsed from {parameters}")

        # If any date is given, use all period types and filter, else if not period type
        # is given use all period types
        if start_date or end_date or not period_types:
            self.period_types = [*DWDObservationPeriodType]
        # Otherwise period types will be parsed
        else:
            # For the case that a period_type is given, parse the period type(s)
            self.period_types = (
                pd.Series(period_types)
                .apply(parse_enumeration_from_template, args=(DWDObservationPeriodType,))
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
        self.tidy_data = (
            len(self.parameters) > 1
            or any(
                [
                    not isinstance(parameter, DWDParameterSet)
                    for parameter, parameter_set in self.parameters
                ]
            )
            or tidy_data
        )
        self.humanize_column_names = humanize_column_names

    def __eq__(self, other):
        return (
            self.station_ids == other.station_ids and
            self.parameters == other.parameters and
            self.time_resolution == other.time_resolution and
            self.period_types == other.period_types and
            self.start_date == other.start_date and
            self.end_date == other.end_date
        )

    def __str__(self):
        station_ids_joined = "& ".join(
            [str(station_id) for station_id in self.station_ids]
        )
        return ", ".join(
            [
                f"station_ids {station_ids_joined}",
                "& ".join([parameter.value
                           for parameter, parameter_set in self.parameters]),
                self.time_resolution.value,
                "& ".join([period_type.value for period_type in self.period_types]),
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

            for parameter, parameter_set in self.parameters:
                df_parameter = self._collect_data(station_id, parameter_set)

                if not isinstance(parameter, DWDParameterSet):
                    df_parameter = df_parameter[
                        df_parameter[DWDMetaColumns.ELEMENT.value] == parameter.value
                    ]

                df_station.append(df_parameter)

            df_station = pd.concat(df_station)

            # Filter for dates range if start_date and end_date are defined
            if self.start_date:
                # df_station may be empty depending on if station has data for given
                # constraints
                try:
                    df_station = df_station[
                        (df_station[DWDMetaColumns.DATE.value] >= self.start_date)
                        & (df_station[DWDMetaColumns.DATE.value] <= self.end_date)
                    ]
                except KeyError:
                    pass

            # Empty dataframe should be skipped
            if df_station.empty:
                continue

            yield df_station

    def _collect_data(
        self, station_id: int, parameter_set: DWDParameterSet
    ) -> pd.DataFrame:
        """
        Method to collect data for one specified parameter. Manages restoring,
        collection and storing of data, transformation and combination of different
        periods.

        Args:
            station_id: station id for which parameter is collected
            parameter_set: chosen parameter that is collected

        Returns:
            pandas.DataFrame for given parameter of station
        """
        df_parameter = pd.DataFrame()

        for period_type in self.period_types:
            parameter_identifier = build_parameter_set_identifier(
                parameter_set, self.time_resolution, period_type, station_id
            )

            storage = None
            if self.storage:
                storage = self.storage.hdf5(
                    parameter=parameter_set,
                    time_resolution=self.time_resolution,
                    period_type=period_type,
                )

                df_period = storage.restore(station_id)

                if not df_period.empty:
                    df_parameter = df_parameter.append(df_period)
                    continue

            log.info(f"Acquiring observations data for {parameter_identifier}.")

            try:
                df_period = collect_climate_observations_data(
                    station_id, parameter_set, self.time_resolution, period_type
                )
            except InvalidParameterCombination:
                log.info(
                    f"Invalid combination {parameter_set.value}/"
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
            df_parameter = df_parameter.dwd.tidy_up_data()

            df_parameter.insert(2, DWDMetaColumns.PARAMETER.value, parameter_set.name)

        # Assign meaningful column names (humanized).
        if self.humanize_column_names:
            hcnm = self._create_humanized_column_names_mapping(
                self.time_resolution, parameter_set
            )

            if self.tidy_data:
                df_parameter[DWDMetaColumns.ELEMENT.value] = df_parameter[
                    DWDMetaColumns.ELEMENT.value
                ].apply(lambda x: hcnm[x])
            else:
                df_parameter = df_parameter.rename(columns=hcnm)

        return df_parameter

    def collect_safe(self) -> pd.DataFrame:
        """
        Collect all data from ``DWDObservationData``.
        """

        data = list(self.collect_data())

        if not data:
            raise ValueError("No data available for given constraints")

        return pd.concat(data)

    def _invalidate_storage(self) -> None:
        """
        Wrapper for storage invalidation for all kinds of defined parameters and
        periods. Used before gathering of data as it has no relation to any specific
        station id.

        Returns:
            None
        """
        for parameter in self.parameters:
            for period_type in self.period_types:
                storage = self.storage.hdf5(
                    parameter=parameter,
                    time_resolution=self.time_resolution,
                    period_type=period_type,
                )

                storage.invalidate()

    @staticmethod
    def _create_humanized_column_names_mapping(
        time_resolution: DWDObservationTimeResolution, parameter: DWDParameterSet
    ) -> Dict[str, str]:
        return create_humanized_column_names_mapping(
            time_resolution, parameter, DWDObservationParameter
        )


class DWDObservationSites(WDSitesCore):
    """
    The DWDObservationSites class represents a request for
    station data as provided by the DWD service.
    """

    @staticmethod
    def _check_parameters(**kwargs):
        parameter = kwargs.get("parameter")
        time_resolution = kwargs.get("time_resolution")
        period_type = kwargs.get("period_type")

        if not check_parameters(parameter, time_resolution, period_type):
            raise InvalidParameterCombination(
                f"The combination of {parameter.value}, {time_resolution.value}, "
                f"{period_type.value} is invalid."
            )

    def _all(self) -> pd.DataFrame:
        metadata = metadata_for_climate_observations(
            parameter=self.parameter,
            time_resolution=self.time_resolution,
            period_type=self.period_type,
        )

        # Filter only for stations that have a file
        metadata = metadata[metadata[DWDMetaColumns.HAS_FILE.value].values]

        metadata = metadata.drop(columns=[DWDMetaColumns.HAS_FILE.value])

        return metadata


class DWDObservationMetadata:
    """
    Inquire metadata about weather observations on the
    public DWD data repository.
    """

    def __init__(
        self,
        parameter_set: Union[
            None, str, DWDParameterSet, List[Union[str, DWDParameterSet]]
        ] = None,
        time_resolution: Union[
            None, str, DWDObservationTimeResolution, List[Union[str, DWDObservationTimeResolution]]
        ] = None,
        period_type: Union[None, str, DWDObservationPeriodType, List[Union[str, DWDObservationPeriodType]]] = None,
    ):
        self.parameter_set = parameter_set
        self.time_resolution = time_resolution
        self.period_type = period_type

    def discover_parameters(self) -> dict:
        """
        Function to print/discover available time_resolution/parameter/period_type
        combinations.

        :return:                        Available parameter combinations.
        """

        parameter_set = self.parameter_set
        time_resolution = self.time_resolution
        period_type = self.period_type

        if not parameter_set:
            parameter_set = [*DWDParameterSet]
        if not time_resolution:
            time_resolution = [*DWDObservationTimeResolution]
        if not period_type:
            period_type = [*DWDObservationPeriodType]

        time_resolution = parse_enumeration(DWDObservationTimeResolution, time_resolution)
        parameter_set = parse_enumeration(DWDParameterSet, parameter_set)
        period_type = parse_enumeration(DWDObservationPeriodType, period_type)

        trp_mapping_filtered = {
            ts: {
                par: [p for p in pt if p in period_type]
                for par, pt in parameters_and_period_types.items()
                if par in parameter_set
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

    def describe_fields(self) -> dict:

        file_index = _create_file_index_for_dwd_server(
            parameter_set=self.parameter_set,
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
