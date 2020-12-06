"""
=====
About
=====
Acquire measurement information from DWD and store into HDF5 files.


=====
Setup
=====
::

    pip install wetterdienst

"""
import logging

from wetterdienst.dwd.observations import (
    DWDObservationData,
    DWDObservationResolution,
    DWDObservationParameterSet,
    StorageAdapter,
)

log = logging.getLogger()


def hdf5_example():

    storage = StorageAdapter(persist=True)

    observations = DWDObservationData(
        station_ids=[1048],
        parameters=[DWDObservationParameterSet.TEMPERATURE_AIR],
        resolution=DWDObservationResolution.HOURLY,
        start_date="2019-01-01",
        end_date="2020-01-01",
        tidy_data=True,
        humanize_parameters=True,
        storage=storage,
    )

    df = observations.collect_safe().dwd.lower()
    print(df)


def main():
    logging.basicConfig(level=logging.INFO)
    hdf5_example()


if __name__ == "__main__":
    main()
