import pytest

from wetterdienst.dwd.metadata.parameter import Parameter
from wetterdienst.dwd.metadata.period_type import PeriodType
from wetterdienst import TimeResolution
from wetterdienst.util.network import list_remote_files
from wetterdienst.dwd.index import build_path_to_parameter


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
