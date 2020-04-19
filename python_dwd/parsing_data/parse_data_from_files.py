""" function to read data from dwd server """
from itertools import zip_longest, groupby
from pathlib import Path
from typing import List, Tuple, Optional, Union
import re
from io import BytesIO
import pandas as pd

from python_dwd.additionals.functions import retrieve_parameter_from_filename, retrieve_period_type_from_filename, \
    retrieve_time_resolution_from_filename, cast_to_list
from python_dwd.additionals.helpers import create_stationdata_dtype_mapping
from python_dwd.constants.column_name_mapping import GERMAN_TO_ENGLISH_COLUMNS_MAPPING
from python_dwd.constants.metadata import NA_STRING, STATIONDATA_SEP, STATID_REGEX, H5_FORMAT, STATIONDATA_NAME
from python_dwd.constants.access_credentials import MAIN_FOLDER
from python_dwd.file_path_handling.path_handling import create_folder


def parse_dwd_data(filenames_and_files: Optional[Union[List[str], List[Tuple[str, BytesIO]]]] = None,
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

    :param filenames_and_files: list of local stored files that should be read
    :param write_file: If true, the raw zip file will not be deleted, default is false.
    :param prefer_local: bool to define if preferably data is loaded from local file
    :param folder: the folder where data either should be written to or loaded from
    :returns: DataFrame with requested data

    """
    # Unpack values
    try:
        filenames = []
        files = []

        for filename, file in filenames_and_files:
            filenames.append(filename)
            files.append(file)

    except ValueError:
        filenames = filenames_and_files
        files = None
    except TypeError:
        filenames = None
        files = None
    finally:
        filenames = cast_to_list(filenames)
        files = cast_to_list(files)

    try:
        sample_file = filenames[0]

        statid = [str(int(re.findall(STATID_REGEX, filename).pop(0)))
                  for filename in filenames]

        time_res = retrieve_time_resolution_from_filename(sample_file)
        parameter = retrieve_parameter_from_filename(sample_file, time_resolution=time_res)
        period = retrieve_period_type_from_filename(sample_file)
    except (IndexError, TypeError):
        try:
            statid = cast_to_list(kwargs["statid"])

            time_res = kwargs["time_resolution"]
            parameter = kwargs["parameter"]
            period = kwargs["period_type"]
        except (KeyError, ValueError):
            raise ValueError(f"Error: Could neither parse parameters from filename nor from kwargs (statid, "
                             f"parameter, time_resolution, period_type).")
    finally:
        statid = cast_to_list(statid)

    data = []
    for statid, group in groupby(zip_longest(statid, filenames, files), key=lambda x: x[0]):
        request_string = f"{statid[0]}/{parameter.value}/{time_res.value}/{period.value}"

        data.append(
            _parse_dwd_data(group, prefer_local, folder, write_file, request_string)
        )

    try:
        data = pd.concat(data).reset_index(drop=True)
    except ValueError:
        data = pd.DataFrame()

    return data


def _parse_dwd_data(files_in_bytes: Optional[List[Tuple[str, BytesIO]]],
                    prefer_local: bool,
                    folder: str,
                    write_file: bool,
                    request_string: str):
    """
    Writing the data is not supposed to happen here
    :param files_in_bytes:
    :param prefer_local:
    :param folder:
    :return:
    """
    loaded_locally = False
    data = None

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
        for _statid, filename, file_in_bytes in files_in_bytes:
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
            except ValueError:
                print("Error: file from files_in_bytes is None. No data is parsed.")

        try:
            data = pd.concat(data).reset_index(drop=True)
        except ValueError:
            return pd.DataFrame()

        column_names = data.columns

        column_names = [column_name.upper().strip()
                        for column_name in column_names]

        column_names = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(column_name, column_name)
                        for column_name in column_names]

        data.columns = column_names

        data = data.astype(create_stationdata_dtype_mapping(data.columns))

    if write_file and not loaded_locally:
        try:
            create_folder(STATIONDATA_NAME, folder)

            data.to_hdf(Path(folder, STATIONDATA_NAME) / f"{STATIONDATA_NAME}{H5_FORMAT}", key=request_string)
        except FileNotFoundError:
            print(f"Error: File for station data could not be created at "
                  f"{str(Path(folder, STATIONDATA_NAME, f'{STATIONDATA_NAME}{H5_FORMAT}'))}. "
                  f"Data for {request_string} could not be written.")

    return data
