# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
Extending pandas
- https://pandas.pydata.org/pandas-docs/stable/development/extending.html
"""

import json

import dateutil.parser
import pandas as pd
import pytz

from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.exceptions import InvalidTimeInterval
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.util.datetime import mktimerange

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


@pd.api.extensions.register_dataframe_accessor("dwd")
class PandasDwdExtension:
    def __init__(self, pandas_obj):
        self.df = pandas_obj

    def lower(self) -> pd.DataFrame:
        """
        Make Pandas DataFrame column names and parameters lowercase.

        :return: Mungled DataFrame
        """
        df = self.df.rename(columns=str.lower)

        for attribute in DWDMetaColumns.PARAMETER_SET, DWDMetaColumns.PARAMETER:
            attribute_name = attribute.value.lower()
            if attribute_name in df:
                df[attribute_name] = df[attribute_name].str.lower()

        return df

    def filter_by_date(self, date: str, resolution: Resolution) -> pd.DataFrame:
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
                expression = (date_from <= self.df[DWDMetaColumns.FROM_DATE.value]) & (
                    self.df[DWDMetaColumns.TO_DATE.value] <= date_to
                )
            else:
                expression = (date_from <= self.df[DWDMetaColumns.DATE.value]) & (
                    self.df[DWDMetaColumns.DATE.value] <= date_to
                )
            df = self.df[expression]

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
                expression = (date_from <= self.df[DWDMetaColumns.FROM_DATE.value]) & (
                    self.df[DWDMetaColumns.TO_DATE.value] <= date_to
                )
            else:
                expression = date == self.df[DWDMetaColumns.DATE.value]
            df = self.df[expression]

        return df

    def format(self, fmt: str) -> str:
        """
        Format/render Pandas DataFrame to given output format.

        :param fmt: One of json, geojson, csv, excel.
        :return: Rendered payload.
        """

        # Output as GeoJSON.
        if fmt == "geojson":
            output = json.dumps(self.df.dwd.to_geojson(), indent=4)

        elif fmt in ("json", "csv", "excel"):
            output = self.df.io.format(fmt=fmt)
        else:
            raise KeyError("Unknown output format")

        return output

    # TODO make compatible with forecasts (instead of station_id, use wmo_id)
    def to_geojson(self) -> dict:
        """
        Convert DWD station information into GeoJSON format.

        Args:

        Return:
             Dictionary in GeoJSON FeatureCollection format.
        """
        df = self.df.rename(columns=str.lower)

        features = []
        for _, station in df.iterrows():
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "id": station["station_id"],
                        "name": station["station_name"],
                        "state": station["state"],
                        "from_date": station["from_date"].isoformat(),
                        "to_date": station["to_date"].isoformat(),
                    },
                    "geometry": {
                        # WGS84 is implied and coordinates represent decimal degrees
                        # ordered as "longitude, latitude [,elevation]" with z expressed
                        # as metres above mean sea level per WGS84.
                        # -- http://wiki.geojson.org/RFC-001
                        "type": "Point",
                        "coordinates": [
                            station["longitude"],
                            station["latitude"],
                            station["height"],
                        ],
                    },
                }
            )

        return {
            "type": "FeatureCollection",
            "features": features,
        }

    def tidy_up_data(self) -> pd.DataFrame:
        """
        Create a tidy DataFrame by reshaping it, putting quality in a separate column,
        so that for each timestamp there is a tuple of parameter, value and quality.

        :return:            The tidied DataFrame
        """
        id_vars = []
        date_vars = []

        # Add id columns based on metadata columns
        for column in POSSIBLE_ID_VARS:
            if column in self.df:
                id_vars.append(column)
                if column in POSSIBLE_DATE_VARS:
                    date_vars.append(column)

        # Extract quality
        # Set empty quality for first columns until first QN column
        quality = pd.Series(dtype=pd.Int64Dtype())
        column_quality = pd.Series(dtype=pd.Int64Dtype())

        for column in self.df:
            # If is quality column, overwrite current "column quality"
            if column.startswith("QN"):
                column_quality = self.df.pop(column)
            else:
                quality = quality.append(column_quality)

        df_tidy = self.df.melt(
            id_vars=id_vars,
            var_name=DWDMetaColumns.PARAMETER.value,
            value_name=DWDMetaColumns.VALUE.value,
        )

        if DWDMetaColumns.STATION_ID.value not in df_tidy:
            df_tidy[DWDMetaColumns.STATION_ID.value] = pd.NA

        df_tidy[DWDMetaColumns.QUALITY.value] = (
            quality.reset_index(drop=True).astype(float).astype(pd.Int64Dtype())
        )

        # TODO: move into coercing field types function after OOP refactoring
        # Convert other columns to categorical
        df_tidy = df_tidy.astype(
            {
                DWDMetaColumns.STATION_ID.value: "category",
                DWDMetaColumns.PARAMETER.value: "category",
                DWDMetaColumns.QUALITY.value: "category",
            }
        )

        df_tidy.loc[
            df_tidy[DWDMetaColumns.VALUE.value].isna(), DWDMetaColumns.QUALITY.value
        ] = pd.NA

        # Store metadata information within dataframe.
        df_tidy.attrs["tidy"] = True

        return df_tidy
