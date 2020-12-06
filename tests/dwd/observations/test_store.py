from wetterdienst.dwd.observations import (
    DWDObservationParameterSet,
    DWDObservationResolution,
    DWDObservationPeriod,
    StorageAdapter,
)


def test_storage_adapter():
    storage_adapter = StorageAdapter()

    storage = storage_adapter.hdf5(
        DWDObservationParameterSet.CLIMATE_SUMMARY,
        DWDObservationResolution.DAILY,
        DWDObservationPeriod.HISTORICAL,
    )

    assert storage.hdf5_key("00001") == "kl/daily/historical/00001"

    assert storage.filename == "kl-daily-historical.h5"
