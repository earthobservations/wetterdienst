""" Meta data handling """
from pathlib import Path

import pandas as pd

from python_dwd.additionals.functions import check_parameters
from python_dwd.additionals.helpers import create_fileindex, check_file_exist
from python_dwd.additionals.helpers import metaindex_for_1minute_data, create_metaindex
from python_dwd.additionals.variables import STRING_STATID_COL
from python_dwd.constants.column_name_mapping import STATIONNAME_NAME, \
    STATE_NAME, HAS_FILE_NAME
from python_dwd.constants.ftp_credentials import MAIN_FOLDER, \
    SUB_FOLDER_METADATA
from python_dwd.constants.metadata import METADATA_NAME, DATA_FORMAT
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.file_path_handling.file_list_creation import \
    create_file_list_for_dwd_server
from python_dwd.file_path_handling.path_handling import correct_folder_path, \
    remove_old_file, create_folder


def add_filepresence(metainfo: pd.DataFrame,
                     parameter: Parameter,
                     time_resolution: TimeResolution,
                     period_type: PeriodType,
                     folder: str,
                     create_new_filelist: bool) -> pd.DataFrame:
    """
    updates the metainfo

    Args:
        metainfo: meta info about the weather data
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        folder: local folder to store meta info file
        create_new_filelist: if true: a new file_list for metadata will
         be created

    Returns:
        updated meta info
    """
    folder = correct_folder_path(folder)

    if create_new_filelist:
        create_fileindex(parameter=parameter,
                         time_resolution=time_resolution,
                         period_type=period_type,
                         folder=folder)

    metainfo[HAS_FILE_NAME] = False

    file_existence = create_file_list_for_dwd_server(
        statid=list(metainfo.iloc[:, 0]),
        parameter=parameter,
        time_resolution=time_resolution,
        period_type=period_type,
        folder=folder)

    file_existence = pd.DataFrame(file_existence)

    file_existence.iloc[:, 0] = file_existence.iloc[:, 0].apply(
        lambda x: x.split('_')[
            STRING_STATID_COL.get(period_type, None)]).astype(int)

    metainfo.loc[metainfo.iloc[:, 0].isin(
        file_existence.iloc[:, 0]), HAS_FILE_NAME] = True

    return metainfo


def metadata_for_dwd_data(parameter: Parameter,
                          time_resolution: TimeResolution,
                          period_type: PeriodType,
                          folder: str = MAIN_FOLDER,
                          write_file: bool = True,
                          create_new_filelist: bool = False):
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
    assert isinstance(parameter, Parameter)
    assert isinstance(time_resolution, TimeResolution)
    assert isinstance(period_type, PeriodType)
    assert isinstance(folder, str)
    assert isinstance(write_file, bool)
    assert isinstance(create_new_filelist, bool)

    check_parameters(parameter=parameter,
                     time_resolution=time_resolution,
                     period_type=period_type)

    file_path = create_metainfo_fpath(folder,
                                      parameter,
                                      period_type,
                                      time_resolution)

    if check_file_exist(file_path) and not create_new_filelist:
        metainfo = pd.read_csv(filepath_or_buffer=file_path)
        return metainfo

    if time_resolution != TimeResolution.MINUTE_1:
        metainfo = create_metaindex(parameter=parameter,
                                    time_resolution=time_resolution,
                                    period_type=period_type)


    else:
        metainfo = metaindex_for_1minute_data(parameter=parameter,
                                              time_resolution=time_resolution,
                                              folder=folder)

    if STATE_NAME not in metainfo.columns:
        mdp = metadata_for_dwd_data(Parameter.PRECIPITATION_MORE,
                                    TimeResolution.DAILY,
                                    PeriodType.HISTORICAL,
                                    folder=folder,
                                    write_file=False,
                                    create_new_filelist=False)

        metainfo = metainfo.merge(
            mdp.loc[:, [STATIONNAME_NAME, STATE_NAME]],
            on=STATIONNAME_NAME).reset_index(drop=True)

    metainfo = add_filepresence(metainfo=metainfo,
                                parameter=parameter,
                                time_resolution=time_resolution,
                                period_type=period_type,
                                folder=folder,
                                create_new_filelist=create_new_filelist)

    if write_file and not check_file_exist(file_path) and not \
            create_new_filelist:
        remove_old_file(file_type=METADATA_NAME,
                        file_postfix=DATA_FORMAT,
                        parameter=parameter,
                        time_resolution=time_resolution,
                        period_type=period_type,
                        folder=folder,
                        subfolder=SUB_FOLDER_METADATA)

        metainfo.to_csv(path_or_buf=file_path,
                        header=True,
                        index=False)

    return metainfo


def create_metainfo_fpath(folder: str,
                          parameter: Parameter,
                          period_type: PeriodType,
                          time_resolution: TimeResolution) -> Path:
    """ checks if the file behind the path exists """
    folder = correct_folder_path(folder)

    create_folder(subfolder=SUB_FOLDER_METADATA,
                  folder=folder)
    return Path(folder,
                SUB_FOLDER_METADATA,
                f"{METADATA_NAME}_{parameter.value}_"
                f"{time_resolution.value}_{period_type.value}"
                f"{DATA_FORMAT}")
