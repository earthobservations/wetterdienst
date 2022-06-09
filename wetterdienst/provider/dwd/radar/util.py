# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import re
from io import BytesIO

import dateparser

from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat

# 6-character timestamps are used for data within "RADOLAN_CDC/historical".
# Examples:
# - SF201901.tar.gz
RADAR_DT_REGEX_SHORT = r"(?<!\d)\d{6}(?!\d)"

# 10-character timestamps are used for data within
# "RADOLAN_CDC/recent" and "weather/composit/fx".
# Examples:
# - raa01-sf_10000-2001010050-dwd---bin.gz
# - raa00-dx_10132-2009260240-boo---bin
# - FX2009261820.tar.bz2
RADAR_DT_REGEX_MEDIUM = r"(?<!\d)\d{10}(?!\d)"

# 16-character timestamps are used for data within "weather/site".
# We are just using 12 digits here to cut off the "second" part.
# Examples:
# - sweep_pcp_v_0-20200926143033_10132--buf.bz2
# - rab02-tt_10132-20200926161533-boo---buf
# - ras07-stqual-vol5minng01_sweeph5onem_vradh_00-2020092614305700-boo-10132-hd5
# - ras07-vol5minng01_sweeph5onem_vradh_00-2020092614305700-boo-10132-hd5
RADAR_DT_REGEX_LONG = r"(?<!\d)\d{12}"


RADAR_DT_PATTERN = re.compile(f"{RADAR_DT_REGEX_LONG}|{RADAR_DT_REGEX_MEDIUM}")
RADOLAN_DT_PATTERN = re.compile(f"{RADAR_DT_REGEX_SHORT}|{RADAR_DT_REGEX_MEDIUM}")


def get_date_from_filename(filename):
    try:
        datestr = RADAR_DT_PATTERN.findall(filename)[0]
        return dateparser.parse(
            datestr,
            date_formats=[
                DatetimeFormat.ymdhm.value,
                DatetimeFormat.YMDHM.value,
            ],
        )
    except IndexError:
        pass


def verify_hdf5(buffer: BytesIO):
    import h5py

    buffer.seek(0)
    try:
        nc = h5py.File(buffer, mode="r")
        nc.close()
        buffer.seek(0)
    except Exception:
        buffer.seek(0)
        raise
