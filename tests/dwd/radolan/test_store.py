from datetime import datetime
from pathlib import PosixPath

from wetterdienst import Parameter, TimeResolution
from wetterdienst.dwd.metadata.constants import DWD_FOLDER_MAIN
from wetterdienst.dwd.radolan.store import build_local_filepath_for_radar


def test_build_local_filepath_for_radar():
    assert PosixPath('/home/dlassahn/projects/forecast-system/wetterdienst/'
                     'dwd_data/dx/5_minutes/dx_5_minutes_202001011215') == \
           build_local_filepath_for_radar(
               Parameter.DX_REFLECTIVITY,
               datetime(2020, 1, 1, 12, 15),
               DWD_FOLDER_MAIN,
               TimeResolution.MINUTE_5)
