import logging
from pathlib import Path
from typing import List, Union, Generator
import pandas as pd
from pandas import Timestamp
import dateparser

from wetterdienst import collect_dwd_data
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.additionals.functions import check_parameters, cast_to_list
from wetterdienst.exceptions.start_date_end_date_exception import StartDateEndDateError
from wetterdienst.constants.metadata import DWD_FOLDER_MAIN
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.indexing.file_index_creation import reset_file_index_cache

log = logging.getLogger(__name__)


class DWDStationRequest:
    """
    The DWDStationRequest class represents a request for station data as provided by the DWD service
    """
    def __init__(self,
                 station_ids: Union[str, int, List[Union[int, str]]],
                 parameter: Union[str, Parameter],
                 time_resolution: Union[str, TimeResolution],
                 period_type: Union[None, str, list, PeriodType] = None,
                 start_date: Union[None, str, Timestamp] = None,
                 end_date: Union[None, str, Timestamp] = None,
                 prefer_local: bool = False,
                 write_file: bool = False,
                 folder: Union[str, Path] = DWD_FOLDER_MAIN,
                 parallel_processing: bool = False,
                 create_new_file_index: bool = False,
                 humanize_column_names: bool = False) -> None:
        """
        Class with mostly flexible arguments to define a request regarding DWD data. Special handling for
        period type. If start_date/end_date are given all period types are considered and merged together
        and the data is filtered for the given dates afterwards.
        Args:
            station_ids: definition of stations by str, int or list of str/int,
            will be parsed to list of int
            parameter: str or parameter enumeration defining the requested parameter
            time_resolution: str or time resolution enumeration defining the requested time resolution
            period_type: str or period type enumeration defining the requested period type
            start_date: replacement for period type to define exact time of requested data
            end_date: replacement for period type to define exact time of requested data
            prefer_local: definition if data should rather be taken from a local source
            write_file: should data be written to a local file
            folder: place where file lists (and station data) are stored
            parallel_processing: definition if data is downloaded/processed in parallel
            create_new_file_index: definition if the file index should be recreated
            humanize_column_names:
        """

        if not (period_type or (start_date and end_date)):
            raise ValueError("Define either a 'time_resolution' or both the 'start_date' and 'end_date' and "
                             "leave the other one empty!")

        try:
            self.station_ids = [int(station_id) for station_id in cast_to_list(station_ids)]
        except ValueError:
            raise ValueError("List of station id's can not be parsed to integers.")

        self.parameter = Parameter(parameter)

        self.time_resolution = TimeResolution(time_resolution)

        self.period_type = []
        for pt in cast_to_list(period_type):
            if pt is None:
                self.period_type.append(None)
                continue

            self.period_type.append(PeriodType(pt))

        # Additional sorting required for self.period_type to ensure that for multiple
        # periods the data is first sourced from historical
        self.period_type = sorted(self.period_type)

        try:
            self.start_date = Timestamp(dateparser.parse(start_date))
        except TypeError:
            self.start_date = None

        try:
            self.end_date = Timestamp(dateparser.parse(end_date))
        except TypeError:
            self.end_date = None

        if self.start_date:
            # working with ranges of data means expecting data to be laying between periods, thus including all
            self.period_type = [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW]

            if not self.start_date <= self.end_date:
                raise StartDateEndDateError("Error: 'start_date' must be smaller or equal to 'end_date'.")

        for period_type in self.period_type.copy():
            if not check_parameters(
                    self.parameter, self.time_resolution, period_type):
                log.info(f"Combination of: parameter {self.parameter.value}, "
                         f"time_resolution {self.time_resolution.value}, "
                         f"period_type {period_type} not available and removed.")
                self.period_type.remove(period_type)

        # Use the clean up of self.period_type to identify if there's any data with those parameters
        if not self.period_type:
            raise ValueError("No combination for parameter, time_resolution "
                             "and period_type could be found.")

        self.prefer_local = prefer_local
        self.write_file = write_file
        self.folder = folder
        self.parallel_processing = parallel_processing
        self.create_new_file_index = create_new_file_index
        self.humanize_column_names = humanize_column_names

    def __eq__(self, other):
        return [self.station_ids,
                self.parameter,
                self.time_resolution,
                self.period_type,
                self.start_date,
                self.end_date] == other

    def __str__(self):
        return ", ".join([f"station_ids {'& '.join([str(station_id) for station_id in self.station_ids])}",
                          self.parameter.value,
                          self.time_resolution.value,
                          "& ".join([period_type.value for period_type in self.period_type]),
                          self.start_date.value,
                          self.end_date.value])

    def collect_data(self) -> Generator[pd.DataFrame, None, None]:
        """
        Method to collect data for a defined request. The function is build as generator in
        order to not cloak the memory thus if the user wants the data as one pandas DataFrame
        the generator has to be casted to a DataFrame manually via
        pd.concat(list(request.collect_data([...])).

        Args:
            same as init

        Returns:
            via a generator per station a pandas.DataFrame
        """
        if self.create_new_file_index:
            reset_file_index_cache()

        for station_id in self.station_ids:
            df_of_station_id = pd.DataFrame()

            for period_type in self.period_type:
                period_df = collect_dwd_data(
                    station_ids=[station_id],
                    parameter=self.parameter,
                    time_resolution=self.time_resolution,
                    period_type=period_type,
                    folder=self.folder,
                    prefer_local=self.prefer_local,
                    parallel_processing=self.parallel_processing,
                    write_file=self.write_file,
                    create_new_file_index=False,
                    humanize_column_names=self.humanize_column_names
                )

                # Filter out values which already are in the DataFrame
                try:
                    period_df = period_df[
                        ~period_df[DWDMetaColumns.DATE.value].isin(df_of_station_id[DWDMetaColumns.DATE.value])]
                except KeyError:
                    pass

                df_of_station_id = df_of_station_id.append(period_df)

            # Filter for dates range if start_date and end_date are defined
            if self.start_date:
                df_of_station_id = df_of_station_id[
                    (df_of_station_id[DWDMetaColumns.DATE.value] >= self.start_date) &
                    (df_of_station_id[DWDMetaColumns.DATE.value] <= self.end_date)
                    ]

            # Empty dataframe should be skipped
            if df_of_station_id.empty:
                continue

            yield df_of_station_id
