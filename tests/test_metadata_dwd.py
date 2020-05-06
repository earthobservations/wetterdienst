from python_dwd.metadata_dwd import create_metainfo_fpath
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.constants.access_credentials import DWD_FOLDER_MAIN

from pathlib import Path


def test_create_metainfo_fpath():
    file_path_to_test = create_metainfo_fpath(
        DWD_FOLDER_MAIN,
        Parameter.SOLAR,
        PeriodType.RECENT,
        TimeResolution.HOURLY
    )
    assert file_path_to_test == Path('dwd_data/metadata/metadata_solar_hourly_recent.csv')

    file_path_to_test = create_metainfo_fpath(
        DWD_FOLDER_MAIN,
        Parameter.PRECIPITATION,
        PeriodType.NOW,
        TimeResolution.MINUTE_1
    )
    assert file_path_to_test == Path('dwd_data/metadata/metadata_precipitation_1_minute_now.csv')
