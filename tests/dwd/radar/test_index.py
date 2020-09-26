from wetterdienst import Parameter, TimeResolution
from wetterdienst.dwd.radar.metadata import RadarDataTypes
from wetterdienst.dwd.radar.sites import RadarSites
from wetterdienst.dwd.radar.index import _create_fileindex_radar


def test_radar_fileindex_sweep():

    file_index = _create_fileindex_radar(
        parameter=Parameter.SWEEP_VOL_VELOCITY_V,
        time_resolution=TimeResolution.MINUTE_5,
        radar_site=RadarSites.BOO,
        radar_data_type=RadarDataTypes.HDF5,
    )

    assert "sweep_vol_v/boo/hdf5" in file_index.iloc[0]["FILENAME"]


def test_radar_fileindex_reflectivity():

    file_index = _create_fileindex_radar(
        parameter=Parameter.PX250_REFLECTIVITY,
        time_resolution=TimeResolution.MINUTE_5,
        radar_site=RadarSites.BOO,
    )

    assert "px250/boo" in file_index.iloc[0]["FILENAME"]
