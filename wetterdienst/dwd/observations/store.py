import logging
from pathlib import Path
from typing import Union

import pandas as pd

from wetterdienst.dwd.observations.metadata import (
    DWDObservationParameterSet,
    DWDObservationResolution,
    DWDObservationPeriod,
)
from wetterdienst.dwd.observations.metadata.column_types import (
    QUALITY_FIELDS,
    INTEGER_FIELDS,
)
from wetterdienst.dwd.metadata.constants import DWD_FOLDER_MAIN, DataFormat
from wetterdienst.dwd.util import build_parameter_set_identifier

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

    def hdf5(self, parameter, resolution, period):
        return LocalHDF5Store(
            parameter_set=parameter,
            resolution=resolution,
            period=period,
            folder=self.folder,
        )


class LocalHDF5Store:
    def __init__(
        self,
        parameter_set: DWDObservationParameterSet,
        resolution: DWDObservationResolution,
        period: DWDObservationPeriod,
        folder: Union[str, Path] = DWD_FOLDER_MAIN,
    ):
        self.parameter_set = parameter_set
        self.resolution = resolution
        self.period = period
        self.folder = folder

    @property
    def filename(self) -> str:
        return (
            f"{self.parameter_set.value}-{self.resolution.value}-"
            f"{self.period.value}.{DataFormat.H5.value}"
        )

    @property
    def filepath(self) -> Path:
        return Path(self.folder, self.filename).absolute()

    def hdf5_key(self, station_id: int) -> str:
        """
        Builds a HDF5 key string from defined parameters including a single station id.

        :param station_id:  Station id of data

        :return:            Key for storing data into HDF5 file.
        """

        return build_parameter_set_identifier(
            self.parameter_set, self.resolution, self.period, station_id
        )

    def invalidate(self):
        """
        Purge all HDF5 files for the current constraints.
        """
        try:
            self.filepath.unlink()
        except FileNotFoundError:
            pass

    def store(self, station_id: int, df: pd.DataFrame) -> None:
        """
        Store data in a local HDF5 file. The function takes the
        station identifier and a Pandas DataFrame.

        :param station_id:  The station id of the station to store
        :param df:          DataFrame to store

        :return:            None
        """

        # Make sure that there is data that can be stored
        if df.empty:
            return

        # Replace IntegerArrays by float64
        for column in df:
            if column in QUALITY_FIELDS or column in INTEGER_FIELDS:
                df[column] = df[column].astype("float64")

        log.info(f"Storing HDF5 data to {self.filepath}")
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        df.to_hdf(path_or_buf=self.filepath, key=self.hdf5_key(station_id))

    def restore(self, station_id: int) -> pd.DataFrame:
        """
        Restore data from a local HDF5 file.

        :param station_id:              Station id of which data should be restored
        :return:                        The restored DataFrame.
        """

        try:
            # Typing required as pandas.read_hdf returns an object by typing.
            df = pd.read_hdf(path_or_buf=self.filepath, key=self.hdf5_key(station_id))
            log.info(f"Restored HDF5 data from {self.filepath}")
        except (FileNotFoundError, KeyError):
            return pd.DataFrame()

        # Cast to pandas DataFrame
        df = pd.DataFrame(df)

        for column in df:
            if column in QUALITY_FIELDS or column in INTEGER_FIELDS:
                df[column] = df[column].astype(pd.Int64Dtype())

        return df
