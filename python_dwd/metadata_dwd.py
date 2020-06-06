""" Meta data handling """
from pathlib import Path
import pandas as pd

from python_dwd.additionals.functions import check_parameters
from python_dwd.additionals.helpers import create_fileindex, check_file_exist
from python_dwd.additionals.helpers import metaindex_for_1minute_data, create_metaindex
from python_dwd.enumerations.column_names_enumeration import DWDColumns
from python_dwd.constants.access_credentials import DWD_FOLDER_MAIN, \
    DWD_FOLDER_METADATA
from python_dwd.constants.metadata import METADATA_NAME, DATA_FORMAT
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.file_path_handling.file_list_creation import \
    create_file_list_for_dwd_server
from python_dwd.file_path_handling.path_handling import remove_old_file, create_folder


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
    if not isinstance(metainfo, pd.DataFrame):
        raise TypeError("Error: metainfo is not of type pandas.DataFrame.")

    if create_new_filelist:
        create_fileindex(parameter=parameter,
                         time_resolution=time_resolution,
                         period_type=period_type,
                         folder=folder)

    metainfo[DWDColumns.HAS_FILE.value] = False

    filelist = create_file_list_for_dwd_server(
        station_ids=metainfo.iloc[:, 0].to_list(),
        parameter=parameter,
        time_resolution=time_resolution,
        period_type=period_type,
        folder=folder)

    metainfo.loc[metainfo.iloc[:, 0].isin(
        filelist[DWDColumns.STATION_ID.value]), DWDColumns.HAS_FILE.value] = True

    return metainfo


def metadata_for_dwd_data(parameter: Parameter,
                          time_resolution: TimeResolution,
                          period_type: PeriodType,
                          folder: str = DWD_FOLDER_MAIN,
                          write_file: bool = True,
                          create_new_filelist: bool = False) -> pd.DataFrame:
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

    if not isinstance(parameter, Parameter):
        raise TypeError("Error: 'parameter' is not of type Parameter(Enum).")
    if not isinstance(time_resolution, TimeResolution):
        raise TypeError("Error: 'time_resolution' is not of type TimeResolution(Enum).")
    if not isinstance(period_type, PeriodType):
        raise TypeError("Error: 'period_type' is not of type PeriodType(Enum).")
    if not isinstance(folder, str):
        raise TypeError("Error: 'folder' is not a string.")
    if not isinstance(write_file, bool):
        raise TypeError("Error: 'write_file' is not a bool.")
    if not isinstance(create_new_filelist, bool):
        raise TypeError("Error: 'create_new_filelist' is not a bool.")

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
                                    write_file=False,
                                    create_new_filelist=False)

        stateinfo = pd.merge(metainfo[DWDColumns.STATION_ID],
                             mdp.loc[:, [DWDColumns.STATION_ID.value, DWDColumns.STATE.value]],
                             how="left")

        metainfo[DWDColumns.STATE.value] = stateinfo[DWDColumns.STATE.value]

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
                        subfolder=DWD_FOLDER_METADATA)

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
                f"{METADATA_NAME}_{parameter.value}_"
                f"{time_resolution.value}_{period_type.value}"
                f"{DATA_FORMAT}")
