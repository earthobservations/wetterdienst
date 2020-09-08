import pytest

from wetterdienst.dwd.metadata.constants import DWDCDCBase
from wetterdienst.dwd.metadata.parameter import Parameter
from wetterdienst.dwd.metadata.period_type import PeriodType
from wetterdienst import TimeResolution
from wetterdienst.util.network import list_remote_files
from wetterdienst.dwd.index import build_path_to_parameter, _create_file_index_for_dwd_server


def test_build_index_path():
    path = build_path_to_parameter(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL
    )
    assert path == "daily/kl/historical/"


@pytest.mark.remote
def test_list_files_of_climate_observations():
    files_server = list_remote_files(
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "annual/kl/recent",
        recursive=False,
    )

    assert (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "annual/kl/recent/jahreswerte_KL_01048_akt.zip" in files_server
    )


def test_fileindex():

    file_index = _create_file_index_for_dwd_server(
        Parameter.CLIMATE_SUMMARY,
        TimeResolution.DAILY,
        DWDCDCBase.CLIMATE_OBSERVATIONS,
        period_type=PeriodType.RECENT)

    test_split = file_index.iat[0, 0].split('/')
    assert test_split[0] == 'daily'
    assert test_split[1] == 'kl'
    assert test_split[2] == 'recent'
