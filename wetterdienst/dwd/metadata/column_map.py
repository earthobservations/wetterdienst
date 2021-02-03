# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.dwd.metadata.column_names import DWDOrigMetaColumns
from wetterdienst.metadata.columns import Columns

GERMAN_TO_ENGLISH_COLUMNS_MAPPING = {
    DWDOrigMetaColumns.STATION_ID.value: Columns.STATION_ID.value,
    DWDOrigMetaColumns.DATE.value: Columns.DATE.value,
    DWDOrigMetaColumns.FROM_DATE.value: Columns.FROM_DATE.value,
    DWDOrigMetaColumns.TO_DATE.value: Columns.TO_DATE.value,
    DWDOrigMetaColumns.FROM_DATE_ALTERNATIVE.value: Columns.FROM_DATE.value,
    DWDOrigMetaColumns.TO_DATE_ALTERNATIVE.value: Columns.TO_DATE.value,
    DWDOrigMetaColumns.STATION_HEIGHT.value: Columns.HEIGHT.value,
    DWDOrigMetaColumns.LATITUDE.value: Columns.LATITUDE.value,
    DWDOrigMetaColumns.LATITUDE_ALTERNATIVE.value: Columns.LATITUDE.value,
    DWDOrigMetaColumns.LONGITUDE.value: Columns.LONGITUDE.value,
    DWDOrigMetaColumns.LONGITUDE_ALTERNATIVE.value: Columns.LONGITUDE.value,
    DWDOrigMetaColumns.STATION_NAME.value: Columns.STATION_NAME.value,
    DWDOrigMetaColumns.STATE.value: Columns.STATE.value,
}
