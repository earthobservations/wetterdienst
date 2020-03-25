""" function to read data from dwd server """
from pathlib import Path
from typing import List, Tuple, Union, Optional
import re
from io import BytesIO
import xarray
import pandas as pd

from python_dwd.additionals.functions import retrieve_parameter_from_filename, retrieve_period_type_from_filename, \
    retrieve_time_resolution_from_filename
from python_dwd.constants.column_name_mapping import DATE_NAME, GERMAN_TO_ENGLISH_COLUMNS_MAPPING
from python_dwd.constants.metadata import DATA_FORMAT, NA_STRING, STATIONDATA_SEP, STATID_REGEX, STATION_DATA_NC
from python_dwd.constants.access_credentials import MAIN_FOLDER


def parse_dwd_data(files_in_bytes: Optional[Union[List[Tuple[str, BytesIO]], str]] = None,
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
                statid, parameter, time_res, period = kwargs["request"]
            except (KeyError, ValueError):
                raise ValueError(f"Error: Could neither parse parameters from filename nor from 'request' argument.")
        finally:
            files_in_bytes = None

        request_string = f"{statid}/{parameter.value}/{time_res.value}/{period.value}"

    # If prefered locally try now to read from this data
    if prefer_local:
        try:
            # Try read data and reshape and set loaded_locally
            with xarray.open_dataset(Path(folder, STATION_DATA_NC)) as ds:
                data = ds.sel(space=re).to_dataframe()

            data = data[request_string].unstack()
        except:
            # If not working simply print continue with following path
            pass

    data = []
    for file in files_in_bytes:
        try:
            data_file = pd.read_csv(filepath_or_buffer=file,
                                    sep=STATIONDATA_SEP,
                                    na_values=NA_STRING)

            data.append(data_file)

        except pd.errors.ParserError as e:
            print(f"The file could be parsed to a dataframe."
                  f"Error: {str(e)}")

    data = pd.concat(data)

    column_names = data.columns

    column_names = [column_name.upper().strip()
                    for column_name in column_names]

    column_names = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(column_name, column_name)
                    for column_name in column_names]

    data.columns = column_names

    data[DATE_NAME] = pd.to_datetime(data[DATE_NAME],
                                     DATA_FORMAT)

    if write_file and not loaded_locally:
        ds = xarray.Dataset({request_string: data})

        try:
            ds.to_netcdf(Path(folder, STATION_DATA_NC), mode="a")
        except FileNotFoundError:
            print(f"Error: Path {str(Path(folder, STATION_DATA_NC))} not found. Data for "
                  f"{statid}/{parameter.value}/{time_res.value}/{period.value} could not be written.")

    return data
