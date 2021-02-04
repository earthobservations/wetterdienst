# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
from pandas import Timestamp

from wetterdienst.core.scalar import ScalarStationsCore, ScalarValuesCore
from wetterdienst.dwd.index import _create_file_index_for_dwd_server
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.metadata.constants import DWDCDCBase
from wetterdienst.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.dwd.observations.download import (
    download_climate_observations_data_parallel,
)
from wetterdienst.dwd.observations.fileindex import (
    create_file_index_for_climate_observations,
    create_file_list_for_climate_observations,
)
from wetterdienst.dwd.observations.metadata import (
    DWDObservationParameter,
    DWDObservationParameterSet,
    DWDObservationResolution,
)
from wetterdienst.dwd.observations.metadata.column_types import (
    DATE_PARAMETERS_IRREGULAR,
    INTEGER_PARAMETERS,
    STRING_PARAMETERS,
)
from wetterdienst.dwd.observations.metadata.parameter import (
    DWDObservationParameterSetStructure,
)
from wetterdienst.dwd.observations.metadata.parameter_set import (
    RESOLUTION_PARAMETER_MAPPING,
)
from wetterdienst.dwd.observations.metadata.period import DWDObservationPeriod
from wetterdienst.dwd.observations.metadata.resolution import (
    HIGH_RESOLUTIONS,
    RESOLUTION_TO_DATETIME_FORMAT_MAPPING,
)
from wetterdienst.dwd.observations.metaindex import (
    create_meta_index_for_climate_observations,
)
from wetterdienst.dwd.observations.parser import parse_climate_observations_data
from wetterdienst.dwd.observations.util.parameter import (
    check_dwd_observations_parameter_set,
    create_parameter_to_parameter_set_combination,
)
from wetterdienst.dwd.util import build_parameter_set_identifier
from wetterdienst.exceptions import InvalidParameter
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.source import Source
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.util.enumeration import (
    parse_enumeration,
    parse_enumeration_from_template,
)

log = logging.getLogger(__name__)


class DWDObservationValues(ScalarValuesCore):
    """
    The DWDObservationData class represents a request for
    observation data as provided by the DWD service.
    """

    # TODO: change to DWDObservationValues

    @property
    def _source(self) -> Source:
        return Source.DWD

    @property
    def _tz(self) -> Timezone:
        return Timezone.GERMANY

    @property
    def _data_tz(self) -> Timezone:
        return Timezone.UTC

    @property
    def _has_quality(self) -> bool:
        return True

    @property
    def _integer_parameters(self) -> Tuple[str]:
        return INTEGER_PARAMETERS

    @property
    def _string_parameters(self) -> Tuple[str]:
        return STRING_PARAMETERS

    @property
    def _irregular_parameters(self) -> Tuple[str]:
        return DATE_PARAMETERS_IRREGULAR

    @property
    def _parameter_base(self) -> Enum:
        return DWDObservationParameter

    _resolution_type = ResolutionType.MULTI
    _resolution_base = DWDObservationResolution
    _period_type = PeriodType.MULTI
    _period_base = DWDObservationPeriod

    @property
    def _datetime_format(self):
        return RESOLUTION_TO_DATETIME_FORMAT_MAPPING.get(self.resolution)

    # TODO: change arguments to singular
    def __init__(
        self,
        station_id: List[Union[int, str]],
        parameter: List[
            Union[str, DWDObservationParameter, DWDObservationParameterSet]
        ],
        resolution: Union[str, Resolution, DWDObservationResolution],
        period: Optional[List[Union[str, Period, DWDObservationPeriod]]] = None,
        start_date: Optional[Union[str, Timestamp, datetime]] = None,
        end_date: Optional[Union[str, Timestamp, datetime]] = None,
        tidy_data: bool = True,
        humanize_parameters: bool = True,
    ) -> None:
        """
        Class with mostly flexible arguments to define a request regarding DWD data.
        Special handling for period type. If start_date/end_date are given all period
        types are considered and merged together and the data is filtered for the given
        dates afterwards.

        :param station_id: definition of stations by str, int or list of str/int,
                            will be parsed to list of int
        :param parameter:           Observation measure
        :param resolution:     Frequency/granularity of measurement interval
        :param period:         Recent or historical files (optional), if None
                                    and start_date and end_date None, all period
                                    types are used
        :param start_date:          Replacement for period type to define exact time
                                    of requested data, if used, period type will be set
                                    to all period types (hist, recent, now)
        :param end_date:            Replacement for period type to define exact time
                                    of requested data, if used, period type will be set
                                    to all period types (hist, recent, now)
        :param tidy_data:           Reshape DataFrame to a more tidy
                                    and row-based version of data
        :param humanize_parameters: Replace column names by more meaningful ones
        """
        station_id = pd.Series(station_id).astype(str).str.pad(5, "left", "0")

        if not station_id.str.isdigit().all():
            raise ValueError("station identifiers of DWD only contain digits")

        super(DWDObservationValues, self).__init__(
            station_id=station_id,
            parameter=parameter,
            resolution=resolution,
            period=period,
            start_date=start_date,
            end_date=end_date,
            humanize_parameters=humanize_parameters,
            tidy_data=tidy_data,
        )

        # If any date is given, use all period types and filter, else if not period type
        # is given use all period types
        if not self.period:
            if self.start_date:
                self.period = self._get_periods()
            else:
                self.period = [*self._period_base]

        if self.start_date and self.period:
            log.warning(
                f"start_date and end_date filtering limited to defined "
                f"periods {self.period}"
            )

        # For requests with start date and end date set in the future, we wont expect
        # any periods to be selected
        if not self.period:
            log.warning("start date and end date are out of range of any period.")

        # If more then one parameter requested, automatically tidy data
        # - has to be overwritten here only after parsing parameters and getting the
        # correct format (list) plus parameters could be a parameter set for which we
        # always want tidy data
        self.tidy_data = (
            tidy_data
            or len(self.parameters) > 1
            or any(
                [
                    not isinstance(parameter, DWDObservationParameterSet)
                    for parameter, parameter_set in self.parameters
                ]
            )
        )

    # TODO: move create_parameter_to_parameter_set_combination to class
    def _parse_parameters(self, parameter) -> List[Tuple[Enum, Enum]]:
        """
        Parsing of parameter will create tuples of parameter and parameter_set e.g.
        if the parameter that is parsed is daily precipitation, this parameter is taken
        from a particular parameter_set.
        Example:
            (precipitation_height, precipitation)
        If instead a parameter set is requested the tuple will consist of two times the
        same parameter set.
        Example:
            (precipitation, precipitation)

        :param parameter: list of parameter strings or enumerations
        :return: list of tuples of parameter/parameter set to parameter set combination
        """
        parameters_parsed = []

        for parameter in pd.Series(parameter):
            try:
                (
                    parameter,
                    parameter_set,
                ) = create_parameter_to_parameter_set_combination(
                    parameter, self.resolution
                )
                parameters_parsed.append((parameter, parameter_set))
            except InvalidParameter as e:
                log.info(str(e))

        return parameters_parsed

    def __eq__(self, other):
        """ Add resolution and periods """
        return super(DWDObservationValues, self).__eq__(other) and (
            self.resolution == other.resolution and self.period == other.period
        )

    def __str__(self):
        """ Add resolution and periods """
        periods_joined = "& ".join([period_type.value for period_type in self.period])

        return ", ".join(
            [
                super(DWDObservationValues, self).__str__(),
                f"resolution {self.resolution.value}",
                f"periods {periods_joined}",
            ]
        )

    @property
    def _interval(self) -> Optional[pd.Interval]:
        """ Interval of the request if date given """
        if self.start_date:
            return pd.Interval(
                pd.Timestamp(self.start_date), pd.Timestamp(self.end_date), "both"
            )

        return None

    @property
    def _historical_interval(self) -> pd.Interval:
        """Interval of historical data release schedule. Historical data is typically
        release once in a year somewhere in the first few months with updated quality
        """
        start_date = Timestamp(self.start_date)

        historical_end = pd.Timestamp(self._now_local.replace(month=1, day=1))

        if start_date < historical_end:
            historical_begin = start_date.tz_convert(historical_end.tz)
        else:
            historical_begin = historical_end + pd.tseries.offsets.DateOffset(years=-1)

        historical_interval = pd.Interval(historical_begin, historical_end, "both")

        return historical_interval

    @property
    def _recent_interval(self) -> pd.Interval:
        """Interval of recent data release schedule. Recent data is released every day
        somewhere after midnight with data reaching back 500 days."""
        recent_end = pd.Timestamp(self._now_local.replace(hour=0, minute=0, second=0))
        recent_begin = recent_end - pd.Timedelta(days=500)

        recent_interval = pd.Interval(recent_begin, recent_end, "both")

        return recent_interval

    @property
    def _now_interval(self) -> pd.Interval:
        """Interval of now data release schedule. Now data is released every hour (near
        real time) reaching back to beginning of the previous day."""
        now_end = pd.Timestamp(self._now_local)
        now_begin = pd.Timestamp(
            now_end.replace(hour=0, minute=0, second=0)
        ) - pd.Timedelta(days=1)

        now_interval = pd.Interval(now_begin, now_end, "both")

        return now_interval

    def _get_periods(self) -> List[Period]:
        """Set periods automatically depending on the given start date and end date.
        Overlapping of historical and recent interval will cause both periods to appear
        if values from last year are queried within the 500 day range of recent. This is
        okay as we'd prefer historical values with quality checks, but may encounter
        that in the beginning of a new year historical data is not yet updated and only
        recent periods cover this data."""
        periods = []

        interval = self._interval

        if interval.overlaps(self._historical_interval):
            periods.append(Period.HISTORICAL)
        if interval.overlaps(self._recent_interval):
            periods.append(Period.RECENT)
        if interval.overlaps(self._now_interval):
            periods.append(Period.NOW)

        return periods

    def _get_empty_station_parameter_df(
        self, station_id: str, parameter: Enum
    ) -> pd.DataFrame:
        parameter, parameter_set = parameter

        if parameter != parameter_set:
            # parameter = [*DWDObservationParameterSetStructure[self.resolution.name]
            # [parameter_set.name]]
            df = super(DWDObservationValues, self)._get_empty_station_parameter_df(
                station_id, parameter
            )

            df[Columns.PARAMETER_SET.value] = parameter_set.name

            return df

        # Get parameters from enum
        parameter = [
            *DWDObservationParameterSetStructure[self.resolution.name][
                parameter_set.name
            ]
        ]

        if self.tidy_data:
            data = []
            for par in parameter:
                if not par.value.startswith("QN"):
                    data.append(
                        super(
                            DWDObservationValues, self
                        )._get_empty_station_parameter_df(station_id, par)
                    )

            df = pd.concat(data)

            df[Columns.PARAMETER_SET.value] = parameter_set.name

            return df
        else:
            df = super(DWDObservationValues, self)._get_empty_station_parameter_df(
                station_id, parameter
            )

            df[Columns.PARAMETER_SET.value] = parameter_set.name

            return df

    def _build_complete_df(
        self, df: pd.DataFrame, station_id: str, parameter: Enum
    ) -> pd.DataFrame:
        parameter, parameter_set = parameter

        if parameter != parameter_set or not self.tidy_data:
            df = super(DWDObservationValues, self)._build_complete_df(
                df, station_id, parameter
            )
        else:

            data = []
            for parameter, group in df.groupby(Columns.PARAMETER.value, sort=False):
                parameter = parse_enumeration_from_template(
                    parameter,
                    DWDObservationParameterSetStructure[self.resolution.name][
                        parameter_set.name
                    ],
                )

                data.append(
                    super(DWDObservationValues, self)._build_complete_df(
                        group, station_id, parameter
                    )
                )

            df = pd.concat(data)

        if self.tidy_data:
            df[Columns.PARAMETER_SET.value] = parameter_set.name
            df[Columns.PARAMETER_SET.value] = pd.Categorical(
                df[Columns.PARAMETER_SET.value]
            )

        return df

    def _collect_station_parameter(
        self,
        station_id: str,
        parameter: Tuple[
            Union[DWDObservationParameter, DWDObservationParameterSet],
            DWDObservationParameterSet,
        ],
    ) -> pd.DataFrame:
        """
        Method to collect data for one specified parameter. Manages restoring,
        collection and storing of data, transformation and combination of different
        periods.

        Args:
            station_id: station id for which parameter is collected
            parameter: chosen parameter-parameter_set combination that is collected

        Returns:
            pandas.DataFrame for given parameter of station
        """
        parameter, parameter_set = parameter

        periods_and_date_ranges = []
        for period in self.period:
            if self.resolution in HIGH_RESOLUTIONS and period == Period.HISTORICAL:
                date_ranges = self._get_historical_date_ranges(
                    station_id, parameter_set
                )

                for date_range in date_ranges:
                    periods_and_date_ranges.append((period, date_range))
            else:
                periods_and_date_ranges.append((period, None))

        parameter_df = pd.DataFrame()

        for period, date_range in periods_and_date_ranges:
            parameter_identifier = build_parameter_set_identifier(
                parameter_set, self.resolution, period, station_id, date_range
            )

            log.info(f"Acquiring observations data for {parameter_identifier}.")

            if not check_dwd_observations_parameter_set(
                parameter_set, self.resolution, period
            ):
                log.info(
                    f"Invalid combination {parameter_set.value}/"
                    f"{self.resolution.value}/{period} is skipped."
                )

                return pd.DataFrame()

            remote_files = create_file_list_for_climate_observations(
                station_id, parameter_set, self.resolution, period, date_range
            )

            if len(remote_files) == 0:
                parameter_identifier = build_parameter_set_identifier(
                    parameter_set, self.resolution, period, station_id, date_range
                )
                log.info(
                    f"No files found for {parameter_identifier}. Station will be skipped."
                )
                return pd.DataFrame()

            # TODO: replace with FSSPEC caching
            filenames_and_files = download_climate_observations_data_parallel(
                remote_files
            )

            period_df = parse_climate_observations_data(
                filenames_and_files, parameter_set, self.resolution, period
            )

            # Filter out values which already are in the DataFrame
            try:
                period_df = period_df[
                    ~period_df[DWDMetaColumns.DATE.value].isin(
                        parameter_df[DWDMetaColumns.DATE.value]
                    )
                ]
            except KeyError:
                pass

            parameter_df = parameter_df.append(period_df)

        if self.tidy_data:
            parameter_df = parameter_df.dwd.tidy_up_data()

            # TODO: remove this column and rather move it into metadata of resulting
            #  data model
            parameter_df.insert(
                2, DWDMetaColumns.PARAMETER_SET.value, parameter_set.name
            )
            parameter_df[DWDMetaColumns.PARAMETER_SET.value] = parameter_df[
                DWDMetaColumns.PARAMETER_SET.value
            ].astype("category")

        if parameter not in DWDObservationParameterSet:
            parameter_df = parameter_df[
                parameter_df[DWDMetaColumns.PARAMETER.value] == parameter.value
            ]

        return parameter_df

    def _parse_station_ids(self, series: pd.Series) -> pd.Series:
        series = series.str.pad(5, "left", "0")

        return super(DWDObservationValues, self)._parse_station_ids(series)

    def _parse_dates(self, series: pd.Series) -> pd.Series:
        """Use predefined datetime format for given resolution to reduce processing
        time."""
        return pd.to_datetime(series, format=self._datetime_format).dt.tz_localize(
            self.data_tz
        )

    def _parse_irregular_parameter(self, series: pd.Series) -> pd.Series:
        """Only one particular parameter is irregular which is the related to some
        datetime found in solar."""
        return pd.to_datetime(series, format=DatetimeFormat.YMDH_COLUMN_M.value)

    def _create_humanized_parameters_mapping(self) -> Dict[str, str]:
        """Reduce the creation of parameter mapping of the massive amount of parameters
        by specifying the resolution."""
        hcnm = {
            parameter.value: parameter.name
            for parameter in DWDObservationParameter[self.resolution.name]
        }

        return hcnm

    def _get_historical_date_ranges(
        self, station_id: str, parameter_set: DWDObservationParameterSet
    ) -> List[str]:
        """Get particular files for historical data which for high resolution is
        released in data chunks e.g. decades or monthly chunks"""
        file_index = create_file_index_for_climate_observations(
            parameter_set, self.resolution, Period.HISTORICAL
        )

        # Filter for from date and end date
        file_index_filtered = file_index[
            (file_index[DWDMetaColumns.STATION_ID.value] == station_id)
            & file_index[DWDMetaColumns.INTERVAL.value].array.overlaps(self._interval)
        ]

        return file_index_filtered[DWDMetaColumns.DATE_RANGE.value].tolist()


class DWDObservationStations(ScalarStationsCore):
    """
    The DWDObservationStations class represents a request for
    a station list as provided by the DWD service.
    """

    @property
    def _source(self) -> Source:
        return Source.DWD

    @property
    def _tz(self) -> Timezone:
        return Timezone.GERMANY

    _resolution_type = ResolutionType.MULTI
    _resolution_base = DWDObservationResolution
    _period_type = PeriodType.MULTI
    _period_base = DWDObservationPeriod

    def __init__(
        self,
        parameter: Union[str, DWDObservationParameterSet],
        resolution: Union[str, Resolution, DWDObservationResolution],
        period: Union[str, Period, DWDObservationPeriod],
        start_date: Union[None, str, Timestamp] = None,
        end_date: Union[None, str, Timestamp] = None,
    ):
        """

        :param parameter: parameter set str/enumeration
        :param resolution: resolution str/enumeration
        :param period: period str/enumeration
        :param start_date: start date to limit the stations
        :param end_date: end date to limit the stations
        """
        super().__init__(
            resolution=resolution,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

        # Ensure there's only one period given
        # self.period = pd.Series(self.period).item()

        parameter = parse_enumeration_from_template(
            parameter, DWDObservationParameterSet
        )

        self.parameter = parameter

    def _all(self) -> pd.DataFrame:
        # TODO: move to _all and replace error with logging + empty dataframe
        if not check_dwd_observations_parameter_set(
            self.parameter, self.resolution, self.period
        ):
            log.warning(
                f"The combination of {self.parameter.value}, {self.resolution.value}, "
                f"{self.period.value} is invalid."
            )

            return pd.DataFrame()

        df = create_meta_index_for_climate_observations(
            self.parameter, self.resolution, self.period
        )

        df[Columns.HAS_FILE.value] = False

        file_index = create_file_index_for_climate_observations(
            self.parameter, self.resolution, self.period
        )

        df.loc[
            df.loc[:, Columns.STATION_ID.value].isin(
                file_index[Columns.STATION_ID.value]
            ),
            Columns.HAS_FILE.value,
        ] = True

        # TODO: we may eventually still return those stations which have no file on the
        #  server for the sake of completeness and rather return empty values later on
        #  with a corresponding report e.g. "data not provided"
        # Filter only for stations that have a file
        df = df[df[Columns.HAS_FILE.value].values]

        df = df.drop(columns=[Columns.HAS_FILE.value])

        return df


class DWDObservationMetadata:
    """
    Inquire metadata about weather observations on the
    public DWD data repository.
    """

    def __init__(
        self,
        parameter: Optional[List[Union[str, DWDObservationParameterSet]]] = None,
        resolution: Optional[List[Union[str, DWDObservationResolution]]] = None,
        period: Optional[List[Union[str, DWDObservationPeriod]]] = None,
    ):
        """

        :param parameter: parameter set str/enumeration
        :param resolution: resolution str/enumeration
        :param period: period str/enumeration
        """

        if not parameter:
            parameter = [*DWDObservationParameterSet]
        else:
            parameter = parse_enumeration(parameter, DWDObservationParameterSet)
        if not resolution:
            resolution = [*DWDObservationResolution]
        resolution = parse_enumeration(resolution, DWDObservationResolution, Resolution)
        if not period:
            period = [*DWDObservationPeriod]
        period = parse_enumeration(period, DWDObservationPeriod, Period)

        self.parameter = parameter
        self.resolution = resolution
        self.period = period

    def discover_parameter_sets(self) -> dict:
        """
        Function to print/discover available time_resolution/parameter/period_type
        combinations.

        :return: Available parameter combinations.
        """
        trp_mapping_filtered = {
            ts: {
                par: [p for p in pt if p in self.period]
                for par, pt in parameters_and_period_types.items()
                if par in self.parameter
            }
            for ts, parameters_and_period_types in RESOLUTION_PARAMETER_MAPPING.items()  # noqa:E501,B950
            if ts in self.resolution
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

    def discover_parameters(self) -> Dict[str, List[str]]:
        """Return available parameters for the given time resolution, independent of
        source parameter set"""
        available_parameters = {
            resolution.name: [
                parameter.name for parameter in DWDObservationParameter[resolution.name]
            ]
            for resolution in self.resolution
        }

        return available_parameters

    def describe_fields(self, language: str = "en") -> dict:
        if len(self.parameter) > 1 or len(self.resolution) > 1 or len(self.period) > 1:
            raise NotImplementedError(
                "'describe_fields is only available for a single"
                "parameter, resolution and period"
            )

        file_index = _create_file_index_for_dwd_server(
            parameter_set=self.parameter[0],
            resolution=self.resolution[0],
            period=self.period[0],
            cdc_base=DWDCDCBase.CLIMATE_OBSERVATIONS,
        )

        if language == "en":
            file_prefix = "DESCRIPTION_"
        elif language == "de":
            file_prefix = "BESCHREIBUNG_"
        else:
            raise ValueError("Only language 'en' or 'de' supported")

        file_index = file_index[
            file_index[DWDMetaColumns.FILENAME.value].str.contains(file_prefix)
        ]

        description_file_url = str(
            file_index[DWDMetaColumns.FILENAME.value].tolist()[0]
        )
        log.info(f"Acquiring field information from {description_file_url}")

        from wetterdienst.dwd.observations.fields import read_description

        document = read_description(description_file_url, language=language)

        return document
