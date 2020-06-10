from pathlib import Path
from typing import List, Union, Optional, Dict, Generator
import pandas as pd
from pandas import Timestamp

from python_dwd.data_collection import collect_dwd_data
from python_dwd.additionals.time_handling import parse_date
from python_dwd.constants.parameter_mapping import PARAMETER_WORDLIST_MAPPING, TIMERESOLUTION_WORDLIST_MAPPING, \
    PERIODTYPE_WORDLIST_MAPPING
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.additionals.functions import check_parameters, cast_to_list
from python_dwd.exceptions.start_date_end_date_exception import StartDateEndDateError

from python_dwd.constants.access_credentials import DWD_FOLDER_MAIN
from python_dwd.enumerations.column_names_enumeration import DWDColumns


class DWDStationRequest:
    """
    The DWDStationRequest class represents a request for station data as provided by the DWD service
    """
    def __init__(self,
                 station_id: Union[str, int, List[Union[int, str]]],
                 parameter: Union[str, Parameter],
                 time_resolution: Union[str, TimeResolution],
                 period_type: Union[None, str, list, PeriodType] = None,
                 start_date: Union[None, str, Timestamp] = None,
                 end_date: Union[None, str, Timestamp] = None) -> None:

        if not (period_type or (start_date and end_date)):
            raise ValueError("Define either a 'time_resolution' or both the 'start_date' and 'end_date' and "
                             "leave the other one empty!")

        try:
            self.station_id = [int(s) for s in cast_to_list(station_id)]
        except ValueError:
            raise ValueError("List of station id's can not be parsed to integers.")

        self.parameter = parameter if isinstance(parameter, Parameter) \
            else _parse_parameter_from_value(parameter, PARAMETER_WORDLIST_MAPPING)

        self.time_resolution = time_resolution if isinstance(time_resolution, TimeResolution) \
            else _parse_parameter_from_value(time_resolution, TIMERESOLUTION_WORDLIST_MAPPING)

        self.period_type = cast_to_list(period_type) if isinstance(period_type, (PeriodType, type(None))) \
            else [_parse_parameter_from_value(period_type, PERIODTYPE_WORDLIST_MAPPING)
                  for period_type in cast_to_list(period_type)]

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
            if not check_parameters(parameter=self.parameter,
                                    time_resolution=self.time_resolution,
                                    period_type=period_type):
                print(f"Combination of: parameter {self.parameter.value}, "
                      f"time_resolution {self.time_resolution.value}, "
                      f"period_type {period_type} not available and removed.")
                self.period_type.remove(period_type)

        # Use the clean up of self.period_type to identify if there's any data with those parameters
        if not self.period_type:
            raise ValueError("No combination for parameter, time_resolution "
                             "and period_type could be found.")

    def __eq__(self, other):
        return [self.station_id,
                self.parameter,
                self.time_resolution,
                self.period_type,
                self.start_date,
                self.end_date] == other

    def __str__(self):
        return ", ".join([f"station_ids {'& '.join([str(stat_id) for stat_id in self.station_id])}",
                          self.parameter.value,
                          self.time_resolution.value,
                          "& ".join([period_type.value for period_type in self.period_type]),
                          self.start_date.value,
                          self.end_date.value])

    def collect_data(self,
                     prefer_local: bool = False,
                     write_file: bool = False,
                     folder: Union[str, Path] = DWD_FOLDER_MAIN,
                     parallel_download: bool = False,
                     create_new_filelist: bool = False) -> Generator[pd.DataFrame, None, None]:
        """
        Method to collect data for a defined request. The function is build as generator in
        order to not cloak the memory thus if the user wants the data as one pandas DataFrame
        the generator has to be casted to a DataFrame manually via
        pd.concat(list(request.collect_data([...])).

        Args:
            prefer_local: definition if data should rather be taken from a local source
            write_file: should data be written to a local file
            folder: place where filelists (and station data) are stored
            parallel_download: definition if data is downloaded in parallel
            create_new_filelist: definition if the fileindex should be recreated

        Returns:
            via a generator per station a pandas.DataFrame
        """
        for station_id in self.station_id:
            df_of_station_id = pd.DataFrame()

            for period_type in self.period_type:
                period_df = collect_dwd_data(
                    station_ids=[station_id],
                    parameter=self.parameter,
                    time_resolution=self.time_resolution,
                    period_type=period_type,
                    folder=folder,
                    prefer_local=prefer_local,
                    parallel_download=parallel_download,
                    write_file=write_file,
                    create_new_filelist=create_new_filelist,
                )

                # Filter out values which already are in the dataframe
                try:
                    period_df = period_df[
                        ~period_df[DWDColumns.DATE.value].isin(df_of_station_id[DWDColumns.DATE.value])]
                except KeyError:
                    pass

                df_of_station_id = df_of_station_id.append(period_df)

            # Filter for dates range if start_date and end_date are defined
            if self.start_date:
                df_of_station_id = df_of_station_id[
                    (df_of_station_id[DWDColumns.DATE.value] >= self.start_date) &
                    (df_of_station_id[DWDColumns.DATE.value] <= self.end_date)
                ]

            # Empty dataframe should be skipped
            if df_of_station_id.empty:
                continue

            yield df_of_station_id


def _find_any_one_word_from_wordlist(string_list: List[str],
                                     word_list: List[List[str]]) -> bool:
    """
    Function that tries to match a list of strings with a list of words by trying to find any word of each given list of
    words in one of the strings given by string_list.

    Args:
        string_list: list of strings
        word_list: list one or more list of words

    Returns:
        boolean if any of the strings in string list are in the word_list 
    """
    check = all(
        [
            any(
                [
                    any(
                        [(word in string) if not word.isdigit() else word == string
                         for word in wl]
                    )
                    for string in string_list
                ]
            )
            for wl in word_list
        ]
    )

    return check


def _parse_parameter_from_value(
        string: str,
        parameter_to_wordlist_mapping: Dict[Union[TimeResolution, PeriodType, Parameter], List[List[str]]]
) -> Optional[Union[TimeResolution, PeriodType, Parameter]]:
    """
    Function to parse a parameter from a given string based on a list of parameter enumerations and corresponding list
    of words.

    Args:
        string: string containing the circa name of the parameter
        parameter_to_wordlist_mapping: mapping of parameter and list of words

    Returns:
        None or one of the found enumerations
    """
    string_split = string.split("_")

    for parameter, wordlist in parameter_to_wordlist_mapping.items():
        cond1 = len(wordlist) == len(string_split)
        cond2 = _find_any_one_word_from_wordlist(string_split, wordlist)

        if cond1 and cond2:
            return parameter

    return None
