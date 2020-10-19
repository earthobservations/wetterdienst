from wetterdienst.dwd.observations.metadata.parameter_set import DWDObsParameterSet
from wetterdienst.dwd.metadata.time_resolution import DWDObsTimeResolution
from wetterdienst.dwd.observations.metadata import DWDObsPeriodType
from wetterdienst.dwd.observations.store import StorageAdapter


def test_storage_adapter():
    storage_adapter = StorageAdapter()

    storage = storage_adapter.hdf5(
        DWDObsParameterSet.CLIMATE_SUMMARY,
        DWDObsTimeResolution.DAILY,
        DWDObsPeriodType.HISTORICAL,
    )

    assert storage.hdf5_key(1) == "kl/daily/historical/station_id_1"

    assert storage.filename == "kl-daily-historical.h5"
