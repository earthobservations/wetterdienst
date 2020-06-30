import logging
from pathlib import Path
from typing import List, Union, Generator
import pandas as pd
from pandas import Timestamp

from python_dwd import collect_dwd_data
from python_dwd.additionals.time_handling import parse_date
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.additionals.functions import check_parameters, cast_to_list
from python_dwd.exceptions.start_date_end_date_exception import StartDateEndDateError
from python_dwd.constants.metadata import DWD_FOLDER_MAIN
from python_dwd.enumerations.column_names_enumeration import DWDMetaColumns
from python_dwd.indexing.file_index_creation import reset_file_index_cache

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
                 humanize_column_names: bool = False) -> None:

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

        self.start_date = parse_date(start_date)
        self.end_date = parse_date(end_date)

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

    def collect_data(self,
                     prefer_local: bool = False,
                     write_file: bool = False,
                     folder: Union[str, Path] = DWD_FOLDER_MAIN,
                     parallel_processing: bool = False,
                     create_new_file_index: bool = False) -> Generator[pd.DataFrame, None, None]:
        """
        Method to collect data for a defined request. The function is build as generator in
        order to not cloak the memory thus if the user wants the data as one pandas DataFrame
        the generator has to be casted to a DataFrame manually via
        pd.concat(list(request.collect_data([...])).

        Args:
            prefer_local: definition if data should rather be taken from a local source
            write_file: should data be written to a local file
            folder: place where file lists (and station data) are stored
            parallel_processing: definition if data is downloaded/processed in parallel
            create_new_file_index: definition if the file index should be recreated

        Returns:
            via a generator per station a pandas.DataFrame
        """
        if create_new_file_index:
            reset_file_index_cache()

        for station_id in self.station_ids:
            df_of_station_id = pd.DataFrame()

            for period_type in self.period_type:
                period_df = collect_dwd_data(
                    station_ids=[station_id],
                    parameter=self.parameter,
                    time_resolution=self.time_resolution,
                    period_type=period_type,
                    folder=folder,
                    prefer_local=prefer_local,
                    parallel_processing=parallel_processing,
                    write_file=write_file,
                    create_new_file_index=False,
                    humanize_column_names=self.humanize_column_names
                )

                # Filter out values which already are in the dataframe
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
