from wetterdienst import Parameter, TimeResolution, PeriodType
from wetterdienst.dwd.metadata.constants import DWDWeatherBase, DWDCDCBase
from wetterdienst.dwd.metadata.radar_data_types import RadarDataTypes
from wetterdienst.dwd.metadata.radar_sites import RadarSites
from wetterdienst.dwd.radolan.index import _create_file_index_radolan


def test_radolan_fileindex():

    file_index = _create_file_index_radolan(
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

    file_index = _create_file_index_radolan(
        Parameter.PX250_REFLECTIVITY,
        TimeResolution.MINUTE_5,
        DWDWeatherBase.RADAR_SITES,
        radar_site=RadarSites.BOO)
    test_split = file_index.iat[0, 0].split('/')
    assert test_split[0] == 'px250'
    assert test_split[1] == 'boo'
