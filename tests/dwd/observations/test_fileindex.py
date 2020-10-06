""" tests for file index creation """
import pytest
import requests

from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.observations.fileindex import (
    create_file_index_for_climate_observations,
    create_file_list_for_climate_observations,
)
from wetterdienst import TimeResolution, Parameter, PeriodType


@pytest.mark.remote
def test_file_index_creation():

    # Existing combination of parameters
    file_index = create_file_index_for_climate_observations(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.RECENT
    )

    assert not file_index.empty

    assert file_index.loc[
        file_index[DWDMetaColumns.STATION_ID.value] == 1048,
        DWDMetaColumns.FILENAME.value,
    ].values.tolist() == [
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
        "climate/daily/kl/recent/tageswerte_KL_01048_akt.zip"
    ]

    with pytest.raises(requests.exceptions.HTTPError):
        create_file_index_for_climate_observations(
            Parameter.CLIMATE_SUMMARY, TimeResolution.MINUTE_1, PeriodType.HISTORICAL
        )


def test_create_file_list_for_dwd_server():
    remote_file_path = create_file_list_for_climate_observations(
        station_id=1048,
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.RECENT,
    )
    assert remote_file_path == [
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "daily/kl/recent/tageswerte_KL_01048_akt.zip"
    ]
