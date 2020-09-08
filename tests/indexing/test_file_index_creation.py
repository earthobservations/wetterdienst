""" tests for file index creation """
import pytest
import requests

from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.constants.access_credentials import DWDWeatherBase, DWDCDCBase
from wetterdienst.enumerations.radar_data_types import RadarDataTypes
from wetterdienst.enumerations.radar_sites import RadarSites
from wetterdienst.indexing.file_index_creation import (
    create_file_index_for_climate_observations,
    reset_file_index_cache,
    _create_file_index_for_dwd_server
)
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.period_type_enumeration import PeriodType


@pytest.mark.remote
def test_file_index_creation():
    reset_file_index_cache()

    # Existing combination of parameters
    file_index = create_file_index_for_climate_observations(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.RECENT
    )

    assert not file_index.empty

    reset_file_index_cache()

    file_index2 = create_file_index_for_climate_observations(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.RECENT
    )

    assert file_index.equals(file_index2)

    assert (
        file_index.loc[
            file_index[DWDMetaColumns.STATION_ID.value] == 1048,
            DWDMetaColumns.FILENAME.value,
        ].values.tolist()
        == ["daily/kl/recent/tageswerte_KL_01048_akt.zip"]
    )

    with pytest.raises(requests.exceptions.HTTPError):
        create_file_index_for_climate_observations(
            Parameter.CLIMATE_SUMMARY, TimeResolution.MINUTE_1, PeriodType.HISTORICAL
        )


def test__create_file_index_for_dwd_server():
    file_index = _create_file_index_for_dwd_server(
        Parameter.SWEEP_VOL_VELOCITY_V,
        TimeResolution.MINUTE_5,
        DWDWeatherBase.RADAR_SITES,
        radar_site=RadarSites.BOO,
        radar_data_type=RadarDataTypes.HDF5
    )
    test_split = file_index.iat[0, 0].split('/')
    assert test_split[0] == 'sweep_vol_v'
    assert test_split[1] == 'boo'
    assert test_split[2] == 'hdf5'

    file_index = _create_file_index_for_dwd_server(
        Parameter.PX250_REFLECTIVITY,
        TimeResolution.MINUTE_5,
        DWDWeatherBase.RADAR_SITES,
        radar_site=RadarSites.BOO)
    test_split = file_index.iat[0, 0].split('/')
    assert test_split[0] == 'px250'
    assert test_split[1] == 'boo'

    file_index = _create_file_index_for_dwd_server(
        Parameter.CLIMATE_SUMMARY,
        TimeResolution.DAILY,
        DWDCDCBase.CLIMATE_OBSERVATIONS,
        period_type=PeriodType.RECENT)

    test_split = file_index.iat[0, 0].split('/')
    assert test_split[0] == 'daily'
    assert test_split[1] == 'kl'
    assert test_split[2] == 'recent'

