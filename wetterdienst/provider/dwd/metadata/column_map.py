# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.metadata.columns import Columns
from wetterdienst.provider.dwd.metadata.column_names import DwdOrigColumns

GERMAN_TO_ENGLISH_COLUMNS_MAPPING = {
    DwdOrigColumns.STATION_ID.value: Columns.STATION_ID.value,
    DwdOrigColumns.DATE.value: Columns.DATE.value,
    DwdOrigColumns.FROM_DATE.value: Columns.FROM_DATE.value,
    DwdOrigColumns.TO_DATE.value: Columns.TO_DATE.value,
    DwdOrigColumns.FROM_DATE_ALTERNATIVE.value: Columns.FROM_DATE.value,
    DwdOrigColumns.TO_DATE_ALTERNATIVE.value: Columns.TO_DATE.value,
    DwdOrigColumns.STATION_HEIGHT.value: Columns.HEIGHT.value,
    DwdOrigColumns.LATITUDE.value: Columns.LATITUDE.value,
    DwdOrigColumns.LATITUDE_ALTERNATIVE.value: Columns.LATITUDE.value,
    DwdOrigColumns.LONGITUDE.value: Columns.LONGITUDE.value,
    DwdOrigColumns.LONGITUDE_ALTERNATIVE.value: Columns.LONGITUDE.value,
    DwdOrigColumns.STATION_NAME.value: Columns.NAME.value,
    DwdOrigColumns.STATE.value: Columns.STATE.value,
}
