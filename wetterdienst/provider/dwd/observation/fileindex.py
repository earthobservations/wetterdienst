# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from typing import List, Optional

import pandas as pd
from pytz import timezone

from wetterdienst.metadata.extension import Extension
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.index import _create_file_index_for_dwd_server
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns
from wetterdienst.provider.dwd.metadata.constants import DWDCDCBase
from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.provider.dwd.observation.metadata.dataset import (
    DWD_URBAN_DATASETS,
    DwdObservationDataset,
)
from wetterdienst.provider.dwd.observation.metadata.resolution import HIGH_RESOLUTIONS

STATION_ID_REGEX = r"(?<!\d)\d{3,5}(?!\d)"
DATE_RANGE_REGEX = r"(?<!\d)\d{8}_\d{8}(?!\d)"


def create_file_list_for_climate_observations(
    station_id: str,
    dataset: DwdObservationDataset,
    resolution: Resolution,
    period: Period,
    date_range: Optional[str] = None,
) -> List[str]:
    """
    Function for selecting datafiles (links to archives) for given
    station_ids, parameter, time_resolution and period_type under consideration of a
    created list of files that are
    available online.
    Args:
        station_id: station id for the weather station to ask for data
        dataset: observation measure
        resolution: frequency/granularity of measurement interval
        period: recent or historical files
        date_range:
    Returns:
        List of path's to file
    """
    file_index = create_file_index_for_climate_observations(dataset, resolution, period)

    file_index = file_index[file_index[DwdColumns.STATION_ID.value] == station_id]

    if date_range:
        file_index = file_index[file_index[DwdColumns.DATE_RANGE.value] == date_range]

    return file_index[DwdColumns.FILENAME.value].values.tolist()


def create_file_index_for_climate_observations(
    dataset: DwdObservationDataset,
    resolution: Resolution,
    period: Period,
) -> pd.DataFrame:
    """
    Function (cached) to create a file index of the DWD station data. The file index
    is created for an individual set of parameters.
    Args:
        dataset: parameter of Parameter enumeration
        resolution: time resolution of TimeResolution enumeration
        period: period type of PeriodType enumeration
    Returns:
        file index in a pandas.DataFrame with sets of parameters and station id
    """
    timezone_germany = timezone("Europe/Berlin")

    if dataset in DWD_URBAN_DATASETS:
        file_index = _create_file_index_for_dwd_server(
            dataset, resolution, Period.RECENT, DWDCDCBase.CLIMATE_URBAN_OBSERVATIONS
        )
    else:
        file_index = _create_file_index_for_dwd_server(dataset, resolution, period, DWDCDCBase.CLIMATE_OBSERVATIONS)

    file_index = file_index.loc[file_index[DwdColumns.FILENAME.value].str.endswith(Extension.ZIP.value), :]

    file_index[DwdColumns.STATION_ID.value] = file_index[DwdColumns.FILENAME.value].str.findall(STATION_ID_REGEX).str[0]

    file_index = file_index.dropna().reset_index(drop=True)

    file_index[DwdColumns.STATION_ID.value] = (
        file_index[DwdColumns.STATION_ID.value].astype(str).str.pad(5, "left", "0")
    )

    if resolution in HIGH_RESOLUTIONS and period == Period.HISTORICAL:
        # Date range string for additional filtering of historical files
        file_index[DwdColumns.DATE_RANGE.value] = (
            file_index[DwdColumns.FILENAME.value].str.findall(DATE_RANGE_REGEX).str[0]
        )

        file_index[[DwdColumns.FROM_DATE.value, DwdColumns.TO_DATE.value]] = (
            file_index[DwdColumns.DATE_RANGE.value].str.split("_", expand=True).values
        )

        file_index[DwdColumns.FROM_DATE.value] = pd.to_datetime(
            file_index[DwdColumns.FROM_DATE.value],
            format=DatetimeFormat.YMD.value,
        )
        file_index[DwdColumns.FROM_DATE.value] = file_index.loc[:, DwdColumns.FROM_DATE.value].dt.tz_localize(
            timezone_germany
        )

        file_index[DwdColumns.TO_DATE.value] = pd.to_datetime(
            file_index[DwdColumns.TO_DATE.value],
            format=DatetimeFormat.YMD.value,
        ) + pd.Timedelta(days=1)
        file_index[DwdColumns.TO_DATE.value] = file_index.loc[:, DwdColumns.TO_DATE.value].dt.tz_localize(
            timezone_germany
        )

        # Temporary fix for filenames with wrong ordered/faulty dates
        # Fill those cases with minimum/maximum date to ensure that they are loaded as
        # we don't know what exact date range the included data has
        wrong_date_order_index = file_index[DwdColumns.FROM_DATE.value] > file_index[DwdColumns.TO_DATE.value]

        file_index.loc[wrong_date_order_index, DwdColumns.FROM_DATE.value] = file_index[
            DwdColumns.FROM_DATE.value
        ].min()
        file_index.loc[wrong_date_order_index, DwdColumns.TO_DATE.value] = file_index[DwdColumns.TO_DATE.value].max()

        file_index.loc[:, DwdColumns.INTERVAL.value] = file_index.apply(
            lambda x: pd.Interval(
                left=x[DwdColumns.FROM_DATE.value],
                right=x[DwdColumns.TO_DATE.value],
                closed="both",
            ),
            axis=1,
        )

    return file_index.sort_values(by=[DwdColumns.STATION_ID.value, DwdColumns.FILENAME.value])
