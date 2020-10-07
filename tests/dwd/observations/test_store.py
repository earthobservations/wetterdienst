from wetterdienst.dwd.metadata.parameter import Parameter
from wetterdienst.dwd.metadata.time_resolution import TimeResolution
from wetterdienst.dwd.metadata.period_type import PeriodType
from wetterdienst.dwd.observations.store import StorageAdapter


def test_storage_adapter():
    storage_adapter = StorageAdapter()

    storage = storage_adapter.hdf5(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL
    )

    assert storage.hdf5_key(1) == "kl/daily/historical/station_id_1"

    assert storage.filename == "kl-daily-historical.h5"
