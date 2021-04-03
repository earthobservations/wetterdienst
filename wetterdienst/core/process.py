# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import dateutil
import pandas as pd
import pytz

from wetterdienst.exceptions import InvalidTimeInterval
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.util.datetime import mktimerange

POSSIBLE_ID_VARS = (
    Columns.STATION_ID.value,
    Columns.DATE.value,
    Columns.FROM_DATE.value,
    Columns.TO_DATE.value,
)

POSSIBLE_DATE_VARS = (
    Columns.DATE.value,
    Columns.FROM_DATE.value,
    Columns.TO_DATE.value,
)


def tidy_up_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a tidy DataFrame by reshaping it, putting quality in a separate column,
    so that for each timestamp there is a tuple of parameter, value and quality.

    :return:            The tidied DataFrame
    """
    id_vars = []
    date_vars = []

    # Add id Columns based on metadata Columns
    for column in POSSIBLE_ID_VARS:
        if column in df:
            id_vars.append(column)
            if column in POSSIBLE_DATE_VARS:
                date_vars.append(column)

    # Extract quality
    # Set empty quality for first Columns until first QN column
    quality = pd.Series(dtype=pd.Int64Dtype())
    column_quality = pd.Series(dtype=pd.Int64Dtype())

    for column in df:
        # If is quality column, overwrite current "column quality"
        if column.startswith(Columns.QUALITY_PREFIX.value):
            column_quality = df.pop(column)
        else:
            quality = quality.append(column_quality)

    df_tidy = df.melt(
        id_vars=id_vars,
        var_name=Columns.PARAMETER.value,
        value_name=Columns.VALUE.value,
    )

    if Columns.STATION_ID.value not in df_tidy:
        df_tidy[Columns.STATION_ID.value] = pd.NA

    df_tidy[Columns.QUALITY.value] = (
        quality.reset_index(drop=True).astype(float).astype(pd.Int64Dtype())
    )

    # TODO: move into coercing field types function after OOP refactoring
    # Convert other Columns to categorical
    df_tidy = df_tidy.astype(
        {
            Columns.STATION_ID.value: "category",
            Columns.PARAMETER.value: "category",
            Columns.QUALITY.value: "category",
        }
    )

    df_tidy.loc[df_tidy[Columns.VALUE.value].isna(), Columns.QUALITY.value] = pd.NA

    # Store metadata information within dataframe.
    df_tidy.attrs["tidy"] = True

    return df_tidy


def filter_by_date_and_resolution(
    df: pd.DataFrame, date: str, resolution: Resolution
) -> pd.DataFrame:
    """
    Filter Pandas DataFrame by date or date interval.

    Accepts different kinds of date formats, like:

    - 2020-05-01
    - 2020-06-15T12
    - 2020-05
    - 2019
    - 2020-05-01/2020-05-05
    - 2017-01/2019-12
    - 2010/2020

    :param df:
    :param date:
    :param resolution:
    :return: Filtered DataFrame
    """

    # TODO: datetimes should be aware of tz
    # TODO: resolution is not necessarily available and ideally filtering does not
    #  depend on it
    # Filter by date interval.
    if "/" in date:
        if date.count("/") >= 2:
            raise InvalidTimeInterval("Invalid ISO 8601 time interval")

        date_from, date_to = date.split("/")
        date_from = dateutil.parser.isoparse(date_from)
        if not date_from.tzinfo:
            date_from = date_from.replace(tzinfo=pytz.UTC)

        date_to = dateutil.parser.isoparse(date_to)
        if not date_to.tzinfo:
            date_to = date_to.replace(tzinfo=pytz.UTC)

        if resolution in (
            Resolution.ANNUAL,
            Resolution.MONTHLY,
        ):
            date_from, date_to = mktimerange(resolution, date_from, date_to)
            expression = (date_from <= df[Columns.FROM_DATE.value]) & (
                df[Columns.TO_DATE.value] <= date_to
            )
        else:
            expression = (date_from <= df[Columns.DATE.value]) & (
                df[Columns.DATE.value] <= date_to
            )
        df = df[expression]

    # Filter by specific date.
    else:
        date = dateutil.parser.isoparse(date)
        if not date.tzinfo:
            date = date.replace(tzinfo=pytz.UTC)

        if resolution in (
            Resolution.ANNUAL,
            Resolution.MONTHLY,
        ):
            date_from, date_to = mktimerange(resolution, date)
            expression = (date_from <= df[Columns.FROM_DATE.value]) & (
                df[Columns.TO_DATE.value] <= date_to
            )
        else:
            expression = date == df[Columns.DATE.value]
        df = df[expression]

    return df
