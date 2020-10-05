import logging
from pathlib import Path
from typing import Union

import pandas as pd

from wetterdienst import Parameter, TimeResolution, PeriodType
from wetterdienst.dwd.metadata.constants import DWD_FOLDER_MAIN, DataFormat


log = logging.getLogger(__name__)


class StorageAdapter:
    def __init__(
        self,
        persist: bool = False,
        invalidate: bool = False,
        folder: Union[str, Path] = DWD_FOLDER_MAIN,
    ):
        self.persist = persist
        self.invalidate = invalidate
        self.folder = folder

    def hdf5(self, parameter, time_resolution, period_type):
        return LocalHDF5Store(
            parameter=parameter,
            time_resolution=time_resolution,
            period_type=period_type,
            folder=self.folder,
        )


class LocalHDF5Store:
    def __init__(
        self,
        parameter: Union[Parameter, str],
        time_resolution: Union[TimeResolution, str],
        period_type: Union[PeriodType, str],
        folder: Union[str, Path] = DWD_FOLDER_MAIN,
    ):
        self.parameter = parameter
        self.time_resolution = time_resolution
        self.period_type = period_type
        self.folder = folder

    @property
    def filename(self) -> str:
        return f"{self.parameter.value}-{self.time_resolution.value}-{self.period_type.value}.{DataFormat.H5.value}"

    @property
    def filepath(self) -> Path:
        return Path(self.folder, self.filename).absolute()

    def hdf5_key(self, station_id: int) -> str:
        """
        Builds a HDF5 key string from defined parameters including a single station id.

        :param station_id:  Station id of data

        :return:            Key for storing data into HDF5 file.
        """
        key = (
            f"{self.parameter.value}/{self.time_resolution.value}/"
            f"{self.period_type.value}/station_id_{int(station_id)}"
        )

        return key

    def invalidate(self):
        """
        Purge all HDF5 files for the current constraints.
        """
        self.filepath.unlink(missing_ok=True)

    def store(self, station_id: int, df: pd.DataFrame) -> None:
        """
        Store data in a local HDF5 file. The function takes the
        station identifier and a Pandas DataFrame.

        :param station_id:  The station id of the station to store
        :param df:          DataFrame to store

        :return:            None
        """

        log.info("+++++++++++++++++ STORE +++++++++++++++++")

        # Make sure that there is data that can be stored
        if df.empty:
            return

        log.info(f"Storing HDF5 data to {self.filepath}")
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        df.to_hdf(path_or_buf=self.filepath, key=self.hdf5_key(station_id))

    def restore(self, station_id: int) -> pd.DataFrame:
        """
        Restore data from a local HDF5 file.

        :param station_id:              Station id of which data should be restored
        :return:                        The restored DataFrame.
        """

        log.info(f"Restoring HDF5 data from {self.filepath}")

        try:
            # typing required as pandas.read_hdf returns an object by typing
            df = pd.read_hdf(path_or_buf=self.filepath, key=self.hdf5_key(station_id))
        except (FileNotFoundError, KeyError):
            return pd.DataFrame()

        # Cast to pandas DataFrame
        data = pd.DataFrame(df)

        return data
