# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

from wetterdienst.core.scalar.request import ScalarRequestCore
from wetterdienst.core.scalar.values import ScalarValuesCore
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.provider.dwd.index import _create_file_index_for_dwd_server
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns
from wetterdienst.provider.dwd.metadata.constants import DWDCDCBase
from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.provider.dwd.observation.download import (
    download_climate_observations_data_parallel,
)
from wetterdienst.provider.dwd.observation.fileindex import (
    create_file_index_for_climate_observations,
    create_file_list_for_climate_observations,
)
from wetterdienst.provider.dwd.observation.metadata import (
    DwdObservationDataset,
    DwdObservationParameter,
    DwdObservationResolution,
)
from wetterdienst.provider.dwd.observation.metadata.field_types import (
    DATE_PARAMETERS_IRREGULAR,
    INTEGER_PARAMETERS,
    STRING_PARAMETERS,
)
from wetterdienst.provider.dwd.observation.metadata.parameter import (
    PARAMETER_TO_DATASET_MAPPING,
    DwdObservationDatasetTree,
)
from wetterdienst.provider.dwd.observation.metadata.period import DwdObservationPeriod
from wetterdienst.provider.dwd.observation.metadata.resolution import (
    HIGH_RESOLUTIONS,
    RESOLUTION_TO_DATETIME_FORMAT_MAPPING,
)
from wetterdienst.provider.dwd.observation.metaindex import (
    create_meta_index_for_climate_observations,
)
from wetterdienst.provider.dwd.observation.parser import parse_climate_observations_data
from wetterdienst.provider.dwd.observation.util.parameter import (
    check_dwd_observations_dataset,
)
from wetterdienst.provider.dwd.util import build_parameter_set_identifier
from wetterdienst.util.enumeration import parse_enumeration_from_template

log = logging.getLogger(__name__)


class DwdObservationValues(ScalarValuesCore):
    """
    The DWDObservationData class represents a request for
    observation data as provided by the DWD service.
    """

    _provider = Provider.DWD
    _tz = Timezone.GERMANY
    _data_tz = Timezone.UTC
    _has_quality = True

    _integer_parameters = INTEGER_PARAMETERS
    _string_parameters = STRING_PARAMETERS
    _irregular_parameters = DATE_PARAMETERS_IRREGULAR

    _resolution_type = ResolutionType.MULTI
    _resolution_base = DwdObservationResolution
    _period_type = PeriodType.MULTI
    _period_base = DwdObservationPeriod

    @property
    def _datetime_format(self):
        return RESOLUTION_TO_DATETIME_FORMAT_MAPPING.get(
            self.stations.stations.resolution
        )

    def __eq__(self, other):
        """ Add resolution and periods """
        return super(DwdObservationValues, self).__eq__(other) and (
            self.stations.resolution == other.stations.resolution
            and self.stations.period == other.stations.period
        )

    def __str__(self):
        """ Add resolution and periods """
        periods_joined = "& ".join(
            [period_type.value for period_type in self.stations.period]
        )

        return ", ".join(
            [
                super(DwdObservationValues, self).__str__(),
                f"resolution {self.stations.resolution.value}",
                f"periods {periods_joined}",
            ]
        )

    def _collect_station_parameter(
        self,
        station_id: str,
        parameter: Tuple[
            Union[DwdObservationParameter, DwdObservationDataset],
            DwdObservationDataset,
        ],
    ) -> pd.DataFrame:
        """
        Method to collect data for one specified parameter. Manages restoring,
        collection and storing of data, transformation and combination of different
        periods.

        Args:
            station_id: station id for which parameter is collected
            parameter: chosen parameter-dataset combination that is collected

        Returns:
            pandas.DataFrame for given parameter of station
        """
        parameter, dataset = parameter

        periods_and_date_ranges = []

        for period in self.stations.period:
            if (
                self.stations.resolution in HIGH_RESOLUTIONS
                and period == Period.HISTORICAL
            ):
                date_ranges = self._get_historical_date_ranges(station_id, dataset)

                for date_range in date_ranges:
                    periods_and_date_ranges.append((period, date_range))
            else:
                periods_and_date_ranges.append((period, None))

        parameter_df = pd.DataFrame()

        for period, date_range in periods_and_date_ranges:
            parameter_identifier = build_parameter_set_identifier(
                dataset, self.stations.resolution, period, station_id, date_range
            )

            log.info(f"Acquiring observations data for {parameter_identifier}.")

            if not check_dwd_observations_dataset(
                dataset, self.stations.resolution, period
            ):
                log.info(
                    f"Invalid combination {dataset.value}/"
                    f"{self.stations.resolution.value}/{period} is skipped."
                )

                continue

            remote_files = create_file_list_for_climate_observations(
                station_id, dataset, self.stations.resolution, period, date_range
            )

            if len(remote_files) == 0:
                parameter_identifier = build_parameter_set_identifier(
                    dataset,
                    self.stations.resolution,
                    period,
                    station_id,
                    date_range,
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
                filenames_and_files, dataset, self.stations.resolution, period
            )

            # Filter out values which already are in the DataFrame
            try:
                period_df = period_df[
                    ~period_df[DwdColumns.DATE.value].isin(
                        parameter_df[DwdColumns.DATE.value]
                    )
                ]
            except KeyError:
                pass

            parameter_df = parameter_df.append(period_df)

        if self.stations.tidy:
            parameter_df = parameter_df.dwd.tidy_up_data()

            # TODO: remove this column and rather move it into metadata of resulting
            #  data model
            parameter_df.insert(2, Columns.DATASET.value, dataset.name.lower())
            parameter_df[Columns.DATASET.value] = parameter_df[
                Columns.DATASET.value
            ].astype("category")

        if parameter not in DwdObservationDataset:
            parameter_df = parameter_df[
                parameter_df[DwdColumns.PARAMETER.value] == parameter.value.lower()
            ]

        return parameter_df

    def _coerce_dates(self, series: pd.Series) -> pd.Series:
        """Use predefined datetime format for given resolution to reduce processing
        time."""
        return pd.to_datetime(series, format=self._datetime_format).dt.tz_localize(
            self.data_tz
        )

    def _coerce_irregular_parameter(self, series: pd.Series) -> pd.Series:
        """Only one particular parameter is irregular which is the related to some
        datetime found in solar."""
        return pd.to_datetime(series, format=DatetimeFormat.YMDH_COLUMN_M.value)

    def _create_humanized_parameters_mapping(self) -> Dict[str, str]:
        """Reduce the creation of parameter mapping of the massive amount of parameters
        by specifying the resolution."""
        hcnm = {
            parameter.value: parameter.name.lower()
            for parameter in DwdObservationParameter[self.stations.resolution.name]
        }

        return hcnm

    def _get_historical_date_ranges(
        self, station_id: str, dataset: DwdObservationDataset
    ) -> List[str]:
        """Get particular files for historical data which for high resolution is
        released in data chunks e.g. decades or monthly chunks"""
        file_index = create_file_index_for_climate_observations(
            dataset, self.stations.resolution, Period.HISTORICAL
        )

        # Filter for from date and end date
        file_index_filtered = file_index[
            (file_index[Columns.STATION_ID.value] == station_id)
            & file_index[Columns.INTERVAL.value].array.overlaps(
                self.stations.stations._interval
            )
        ]

        return file_index_filtered[Columns.DATE_RANGE.value].tolist()


class DwdObservationRequest(ScalarRequestCore):
    """
    The DWDObservationStations class represents a request for
    a station list as provided by the DWD service.
    """

    _values = DwdObservationValues
    _parameter_base = DwdObservationParameter
    _provider = Provider.DWD
    _tz = Timezone.GERMANY

    _resolution_type = ResolutionType.MULTI
    _resolution_base = DwdObservationResolution
    _period_type = PeriodType.MULTI
    _period_base = DwdObservationPeriod

    _has_datasets = True
    _unique_dataset = False
    _dataset_base = DwdObservationDataset
    _dataset_tree = DwdObservationDatasetTree
    _parameter_to_dataset_mapping = PARAMETER_TO_DATASET_MAPPING

    @property
    def _interval(self) -> Optional[pd.Interval]:
        """ Interval of the request if date given """
        if self.start_date:
            return pd.Interval(self.start_date, self.end_date, "both")

        return None

    @property
    def _historical_interval(self) -> pd.Interval:
        """Interval of historical data release schedule. Historical data is typically
        release once in a year somewhere in the first few months with updated quality
        """

        historical_end = self._now_local.replace(month=1, day=1)

        if self.start_date < historical_end:
            historical_begin = self.start_date.tz_convert(historical_end.tz)
        else:
            historical_begin = historical_end + pd.tseries.offsets.DateOffset(years=-1)

        historical_interval = pd.Interval(
            left=historical_begin, right=historical_end, closed="both"
        )

        return historical_interval

    @property
    def _recent_interval(self) -> pd.Interval:
        """Interval of recent data release schedule. Recent data is released every day
        somewhere after midnight with data reaching back 500 days."""
        recent_end = self._now_local.replace(hour=0, minute=0, second=0)
        recent_begin = recent_end - pd.Timedelta(days=500)

        recent_interval = pd.Interval(
            left=recent_begin, right=recent_end, closed="both"
        )

        return recent_interval

    @property
    def _now_interval(self) -> pd.Interval:
        """Interval of now data release schedule. Now data is released every hour (near
        real time) reaching back to beginning of the previous day."""
        now_end = self._now_local
        now_begin = now_end.replace(hour=0, minute=0, second=0) - pd.Timedelta(days=1)

        now_interval = pd.Interval(left=now_begin, right=now_end, closed="both")

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

    def _parse_station_id(self, series: pd.Series) -> pd.Series:
        series = super(DwdObservationRequest, self)._parse_station_id(series)

        series = series.str.pad(5, "left", "0")

        return series

    def __init__(
        self,
        parameter: Union[str, DwdObservationDataset],
        resolution: Union[str, Resolution, DwdObservationResolution],
        period: Optional[Union[str, Period, DwdObservationPeriod]] = None,
        start_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
        end_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
        humanize: bool = True,
        tidy: bool = True,
    ):
        """

        :param parameter: parameter set str/enumeration
        :param resolution: resolution str/enumeration
        :param period: period str/enumeration
        :param start_date: start date to limit the stations
        :param end_date: end date to limit the stations
        """
        super().__init__(
            parameter=parameter,
            resolution=resolution,
            period=period,
            start_date=start_date,
            end_date=end_date,
            humanize=humanize,
            tidy=tidy,
        )

        # Has to follow the super call as start date and end date are required for getting
        # automated periods from overlapping intervals
        if not self.period:
            if self.start_date:
                self.period = self._get_periods()
            else:
                self.period = self._parse_period([*self._period_base])

        if self.start_date and self.period:
            log.warning(
                f"start_date and end_date filtering limited to defined "
                f"periods {self.period}"
            )

    @classmethod
    def describe_fields(cls, dataset, resolution, period, language: str = "en") -> dict:
        dataset = parse_enumeration_from_template(dataset, DwdObservationDataset)
        resolution = parse_enumeration_from_template(
            resolution, cls._resolution_base, Resolution
        )
        period = parse_enumeration_from_template(period, cls._period_base, Period)

        file_index = _create_file_index_for_dwd_server(
            dataset=dataset,
            resolution=resolution,
            period=period,
            cdc_base=DWDCDCBase.CLIMATE_OBSERVATIONS,
        )

        if language == "en":
            file_prefix = "DESCRIPTION_"
        elif language == "de":
            file_prefix = "BESCHREIBUNG_"
        else:
            raise ValueError("Only language 'en' or 'de' supported")

        file_index = file_index[
            file_index[DwdColumns.FILENAME.value].str.contains(file_prefix)
        ]

        description_file_url = str(file_index[DwdColumns.FILENAME.value].tolist()[0])
        log.info(f"Acquiring field information from {description_file_url}")

        from wetterdienst.provider.dwd.observation.fields import read_description

        document = read_description(description_file_url, language=language)

        return document

    def _all(self) -> pd.DataFrame:
        datasets = pd.Series(self.parameter).map(lambda x: x[1]).unique()

        stations_df = pd.DataFrame()

        for dataset in datasets:
            # First "now" period as it has more updated end date up to the last "now"
            # values
            for period in reversed(self.period):
                # TODO: move to _all and replace error with logging + empty dataframe
                if not check_dwd_observations_dataset(dataset, self.resolution, period):
                    log.warning(
                        f"The combination of {dataset.value}, "
                        f"{self.resolution.value}, {period.value} is invalid."
                    )

                    continue

                df = create_meta_index_for_climate_observations(
                    dataset, self.resolution, period
                )

                file_index = create_file_index_for_climate_observations(
                    dataset, self.resolution, period
                )

                df = df[
                    df.loc[:, Columns.STATION_ID.value].isin(
                        file_index[Columns.STATION_ID.value]
                    )
                ]

                if not stations_df.empty:
                    df = df[
                        ~df[Columns.STATION_ID.value].isin(
                            stations_df[Columns.STATION_ID.value]
                        )
                    ]

                stations_df = stations_df.append(df)

        if not stations_df.empty:
            stations_df = stations_df.sort_values(
                [Columns.STATION_ID.value], key=lambda x: x.astype(int)
            )

        return stations_df
