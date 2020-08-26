import logging
from io import BytesIO
from pathlib import Path
from typing import List, Union, Generator, Optional, Tuple
from datetime import datetime

import pandas as pd
from pandas import Timestamp
import dateparser

from wetterdienst.data_collection import (
    collect_climate_observations_data,
    collect_radolan_data,
)
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.additionals.functions import (
    cast_to_list,
    parse_enumeration_from_template,
)
from wetterdienst.exceptions import InvalidParameterCombination, StartDateEndDateError
from wetterdienst.constants.metadata import DWD_FOLDER_MAIN
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.indexing.file_index_creation import (
    reset_file_index_cache,
    create_file_index_for_radolan,
)

log = logging.getLogger(__name__)


class DWDStationRequest:
    """
    The DWDStationRequest class represents a request for station data as provided by the
    DWD service
    """

    def __init__(
        self,
        station_ids: Union[str, int, List[Union[int, str]]],
        parameter: Union[str, Parameter, List[Union[str, Parameter]]],
        time_resolution: Union[str, TimeResolution],
        period_type: Union[
            Union[None, str, PeriodType], List[Union[None, str, PeriodType]]
        ] = None,
        start_date: Union[None, str, Timestamp] = None,
        end_date: Union[None, str, Timestamp] = None,
        prefer_local: bool = False,
        write_file: bool = False,
        folder: Union[str, Path] = DWD_FOLDER_MAIN,
        tidy_data: bool = True,
        humanize_column_names: bool = False,
        create_new_file_index: bool = False,
    ) -> None:
        """
        Class with mostly flexible arguments to define a request regarding DWD data.
        Special handling for period type. If start_date/end_date are given all period
        types are considered and merged together and the data is filtered for the given
        dates afterwards.
        Args:
            station_ids: definition of stations by str, int or list of str/int,
            will be parsed to list of int
            parameter: str or parameter enumeration defining the requested parameter
            time_resolution: str or time resolution enumeration defining the requested
            time resolution
            period_type: str or period type enumeration defining the requested
            period type
            start_date: replacement for period type to define exact time of
            requested data
            end_date: replacement for period type to define exact time of requested data
            prefer_local: definition if data should rather be taken from a local source
            write_file: should data be written to a local file
            folder: place where file lists (and station data) are stored
            tidy_data: reshape DataFrame to a more tidy, row based version of data
            humanize_column_names: replace column names by more meaningful ones
            create_new_file_index: definition if the file index should be recreated
        """

        if not (period_type or start_date or end_date):
            raise ValueError(
                "Define either a 'time_resolution' or one of or both 'start_date' and "
                "'end_date' and leave 'time_resolution' empty!"
            )

        try:
            self.station_ids = [
                int(station_id) for station_id in cast_to_list(station_ids)
            ]
        except ValueError:
            raise ValueError("List of station id's can not be parsed to integers.")

        self.parameter = []
        for p in cast_to_list(parameter):
            self.parameter.append(parse_enumeration_from_template(p, Parameter))

        self.time_resolution = parse_enumeration_from_template(
            time_resolution, TimeResolution
        )

        # start date and end date required for collect_data in any case
        self.start_date = None
        self.end_date = None

        if period_type:
            # For the case that a period_type is given, parse the period type(s)
            self.period_type = []
            for pt in cast_to_list(period_type):
                if pt is None:
                    self.period_type.append(None)
                else:
                    self.period_type.append(
                        parse_enumeration_from_template(pt, PeriodType)
                    )

            # Additional sorting required for self.period_type to ensure that for
            # multiple periods the data is first sourced from historical
            self.period_type = sorted(self.period_type)

        else:
            # working with ranges of data means expecting data to be laying between
            # periods, thus including all periods
            self.period_type = [
                PeriodType.HISTORICAL,
                PeriodType.RECENT,
                PeriodType.NOW,
            ]

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

        self.prefer_local = prefer_local
        self.write_file = write_file
        self.folder = folder
        # If more then one parameter requested, automatically tidy data
        self.tidy_data = len(self.parameter) == 2 or tidy_data
        self.humanize_column_names = humanize_column_names
        self.create_new_file_index = create_new_file_index

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
        pd.concat(list(request.collect_data([...])).

        Args:
            same as init

        Returns:
            via a generator per station a pandas.DataFrame
        """
        if self.create_new_file_index:
            reset_file_index_cache()

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
                            create_new_file_index=False,
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


class DWDRadolanRequest:
    """
    API for DWD RADOLAN data requests
    """

    def __init__(
        self,
        time_resolution: Union[str, TimeResolution],
        date_times: Optional[Union[str, List[Union[str, datetime]]]] = None,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        prefer_local: bool = False,
        write_file: bool = False,
        folder: Union[str, Path] = DWD_FOLDER_MAIN,
    ):

        time_resolution = parse_enumeration_from_template(
            time_resolution, TimeResolution
        )

        if time_resolution not in (TimeResolution.HOURLY, TimeResolution.DAILY):
            raise ValueError("RADOLAN only supports hourly and daily resolution.")

        self.time_resolution = time_resolution

        if date_times == "latest":
            file_index_radolan = create_file_index_for_radolan(time_resolution)

            self.date_times = pd.Series(
                file_index_radolan[DWDMetaColumns.DATETIME.value][-1:]
            )
        elif date_times:
            self.date_times = pd.Series(
                pd.to_datetime(date_times, infer_datetime_format=True)
            )
        else:
            self.date_times = pd.Series(
                pd.date_range(
                    pd.to_datetime(start_date, infer_datetime_format=True),
                    pd.to_datetime(end_date, infer_datetime_format=True),
                )
            )

        self.date_times = self.date_times.dt.floor(freq="H") + pd.Timedelta(minutes=50)

        self.date_times = self.date_times.drop_duplicates().sort_values()

        self.prefer_local = prefer_local
        self.write_file = write_file
        self.folder = folder

    def __eq__(self, other):
        return (
            self.time_resolution == other.time_resolution
            and self.date_times.values.tolist() == other.date_times.values.tolist()
        )

    def __str__(self):
        return ", ".join(
            [
                self.time_resolution.value,
                "& ".join([str(date_time) for date_time in self.date_times]),
            ]
        )

    def collect_data(self) -> Generator[Tuple[datetime, BytesIO], None, None]:
        """
        Function used to get the data for the request returned as generator.

        Returns:
            for each datetime the same datetime and file in bytes
        """
        for date_time in self.date_times:
            _, file_in_bytes = collect_radolan_data(
                time_resolution=self.time_resolution,
                date_times=[date_time],
                write_file=self.write_file,
                folder=self.folder,
            )[0]

            yield date_time, file_in_bytes
