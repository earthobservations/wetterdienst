""" Meta data handling """
from pathlib import Path
from typing import Union
import pandas as pd

from python_dwd.additionals.helpers import metaindex_for_1minute_data, create_metaindex
from python_dwd.enumerations.column_names_enumeration import DWDColumns
from python_dwd.constants.access_credentials import DWD_FOLDER_MAIN, \
    DWD_FOLDER_METADATA
from python_dwd.constants.metadata import DWD_METADATA_NAME, CSV_FORMAT
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.file_path_handling.file_index_creation import create_file_index_for_dwd_server, _create_file_index_path
from python_dwd.file_path_handling.path_handling import create_folder


def add_filepresence(metainfo: pd.DataFrame,
                     parameter: Parameter,
                     time_resolution: TimeResolution,
                     period_type: PeriodType,
                     folder: str) -> pd.DataFrame:
    """
    updates the metainfo

    Args:
        metainfo: meta info about the weather data
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        folder: local folder to store meta info file

    Returns:
        updated meta info
    """
    metainfo[DWDColumns.HAS_FILE.value] = False

    file_index = pd.read_csv(
        _create_file_index_path(folder)
    )

    file_index = file_index[
        (file_index[DWDColumns.PARAMETER.value] == parameter.value) &
        (file_index[DWDColumns.TIME_RESOLUTION.value] == time_resolution.value) &
        (file_index[DWDColumns.PERIOD_TYPE.value] == period_type.value)
    ]

    metainfo.loc[metainfo.iloc[:, 0].isin(
        file_index[DWDColumns.STATION_ID.value]), DWDColumns.HAS_FILE.value] = True

    return metainfo


def metadata_for_dwd_data(parameter: Union[Parameter, str],
                          time_resolution: Union[TimeResolution, str],
                          period_type: Union[PeriodType, str],
                          folder: str = DWD_FOLDER_MAIN,
                          write_file: bool = True) -> pd.DataFrame:
    """
    A main function to retrieve metadata for a set of parameters that creates a
        corresponding csv.

    STATE information is added to metadata for cases where there's no such named
    column (e.g. STATE) in the dataframe.
    For this purpose we use daily precipitation data. That has two reasons:
     - daily precipitation data has a STATE information combined with a city
     - daily precipitation data is the most common data served by the DWD


    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        folder: local file system folder where files should be stored
        write_file: writes the meta data file to the local file system
        create_new_filelist: if true: a new file_list for metadata will
         be created

    Returns:

    """
    create_file_index_for_dwd_server(folder)

    parameter = Parameter(parameter)
    time_resolution = TimeResolution(time_resolution)
    period_type = PeriodType(period_type)

    file_path = create_metainfo_fpath(folder,
                                      parameter,
                                      period_type,
                                      time_resolution)

    if file_path.is_file():
        metainfo = pd.read_csv(filepath_or_buffer=file_path)
        return metainfo

    if time_resolution == TimeResolution.MINUTE_1:
        metainfo = metaindex_for_1minute_data(parameter=parameter,
                                              time_resolution=time_resolution)
    else:
        metainfo = create_metaindex(parameter=parameter,
                                    time_resolution=time_resolution,
                                    period_type=period_type)

    if all(pd.isnull(metainfo[DWDColumns.STATE.value])):
        # @todo avoid calling function in function -> we have to build a function around to manage missing data
        mdp = metadata_for_dwd_data(Parameter.PRECIPITATION_MORE,
                                    TimeResolution.DAILY,
                                    PeriodType.HISTORICAL,
                                    folder=folder,
                                    write_file=False)

        stateinfo = pd.merge(metainfo[DWDColumns.STATION_ID],
                             mdp.loc[:, [DWDColumns.STATION_ID.value, DWDColumns.STATE.value]],
                             how="left")

        metainfo[DWDColumns.STATE.value] = stateinfo[DWDColumns.STATE.value]

    metainfo = add_filepresence(metainfo=metainfo,
                                parameter=parameter,
                                time_resolution=time_resolution,
                                period_type=period_type,
                                folder=folder)

    if write_file and not file_path.is_file():
        metainfo.to_csv(path_or_buf=file_path,
                        header=True,
                        index=False)

    return metainfo


def create_metainfo_fpath(folder: str,
                          parameter: Parameter,
                          period_type: PeriodType,
                          time_resolution: TimeResolution) -> Path:
    """ checks if the file behind the path exists """
    # folder = correct_folder_path(folder)

    create_folder(subfolder=DWD_FOLDER_METADATA,
                  folder=folder)
    return Path(folder,
                DWD_FOLDER_METADATA,
                f"{DWD_METADATA_NAME}_{parameter.value}_"
                f"{time_resolution.value}_{period_type.value}"
                f"{CSV_FORMAT}")
