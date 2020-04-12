""" function to read data from dwd server """
from pathlib import Path
from typing import List, Tuple, Union, Optional
import re
from io import BytesIO
import pandas as pd

from python_dwd.additionals.functions import retrieve_parameter_from_filename, retrieve_period_type_from_filename, \
    retrieve_time_resolution_from_filename
from python_dwd.additionals.helpers import create_stationdata_dtype_mapping
from python_dwd.constants.column_name_mapping import DATE_NAME, GERMAN_TO_ENGLISH_COLUMNS_MAPPING, \
    STATIONDATA_DTYPE_MAPPING, STATION_ID_NAME
from python_dwd.constants.metadata import DATA_FORMAT, NA_STRING, STATIONDATA_SEP, STATID_REGEX, H5_FORMAT, \
    STATIONDATA_NAME
from python_dwd.constants.access_credentials import MAIN_FOLDER
from python_dwd.file_path_handling.path_handling import create_folder


def parse_dwd_data(files_in_bytes: Optional[List[Tuple[str, BytesIO]]] = None,
                   write_file: bool = False,
                   prefer_local: bool = False,
                   folder: str = MAIN_FOLDER,
                   **kwargs) -> pd.DataFrame:
    """
    This function is used to read the stationdata for which the local zip link is
    provided by the 'download_dwd' function. It checks the zipfile from the link
    for its parameters, opens every zipfile in the list of files and reads in the
    containing product file, and if there's an error or it's wanted the zipfile is
    removed afterwards.

    :param files_in_bytes: list of local stored files that should be read
    :param write_file: If true: The raw zip file will not be deleted, Default is: False.
    :param prefer_local:
    :param folder:
    :returns: DataFrame with requested data

    """
    loaded_locally = False

    # For cases with interaction of a local file, we need those parameters to store the data in a identifiable place
    if write_file or prefer_local:
        try:
            sample_file = files_in_bytes[0][0]

            statid = str(int(re.findall(STATID_REGEX, sample_file).pop(0)))
            time_res = retrieve_time_resolution_from_filename(sample_file)
            parameter = retrieve_parameter_from_filename(sample_file, time_resolution=time_res)
            period = retrieve_period_type_from_filename(sample_file)
        except (IndexError, TypeError):
            try:
                statid = kwargs["statid"]
                parameter = kwargs["parameter"]
                time_res = kwargs["time_resolution"]
                period = kwargs["period_type"]
            except (KeyError, ValueError):
                raise ValueError(f"Error: Could neither parse parameters from filename nor from kwargs (statid, "
                                 f"parameter, time_res, period).")

        # print(statid, parameter, time_res, period)

        request_string = f"{statid[0]}/{parameter.value}/{time_res.value}/{period.value}"

    # If prefered locally try now to read from this data
    if prefer_local:
        try:
            data = pd.read_hdf(Path(folder, STATIONDATA_NAME) / f"{STATIONDATA_NAME}{H5_FORMAT}", key=request_string)

            data = data.astype(create_stationdata_dtype_mapping(data.columns))

            loaded_locally = True
        except (FileNotFoundError, OSError):
            print(f"Error: There seems to be no file "
                  f"{Path(folder, STATIONDATA_NAME) / f'{STATIONDATA_NAME}{H5_FORMAT}'}. Data will be loaded freshly.")
        except KeyError:
            print(f"Error: The requested data for {request_string} does not yet exist in local store. Data will be "
                  f"loaded freshly.")

    if not loaded_locally:
        data = []
        for filename, file_in_bytes in files_in_bytes:
            try:
                data_file = pd.read_csv(
                    filepath_or_buffer=file_in_bytes,
                    sep=STATIONDATA_SEP,
                    na_values=NA_STRING,
                    dtype="str"  # dtypes are mapped manually to ensure expected dtypes
                )

                data.append(data_file)
            except pd.errors.ParserError as e:
                print(f"Error: The file for {filename} could not be parsed to a DataFrame and will be skipped. \n"
                      f"Message: {str(e)}")

        data = pd.concat(data)

        column_names = data.columns

        column_names = [column_name.upper().strip()
                        for column_name in column_names]

        column_names = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(column_name, column_name)
                        for column_name in column_names]

        data.columns = column_names

        data = data.astype(create_stationdata_dtype_mapping(data.columns))

        # data[DATE_NAME] = pd.to_datetime(data[DATE_NAME],
        #                                  DATA_FORMAT)

    if write_file and not loaded_locally:
        try:
            create_folder(STATIONDATA_NAME, folder)

            data.to_hdf(Path(folder, STATIONDATA_NAME) / f"{STATIONDATA_NAME}{H5_FORMAT}", key=request_string)
        except FileNotFoundError:
            print(f"Error: File for station data could not be created at "
                  f"{str(Path(folder, STATIONDATA_NAME, f'{STATIONDATA_NAME}{H5_FORMAT}'))}. "
                  f"Data for {request_string} could not be written.")

    return data
