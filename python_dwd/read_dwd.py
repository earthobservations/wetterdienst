""" function to read data from dwd server """
from datetime import datetime as dt
from pathlib import Path
from typing import List
from zipfile import ZipFile

import pandas as pd

from python_dwd.constants.column_name_mapping import DATE_NAME, GERMAN_TO_ENGLISH_COLUMNS_MAPPING
from python_dwd.constants.metadata import STATIONDATA_MATCHSTRINGS
from .additionals.functions import check_parameters
from .additionals.functions import determine_parameters


def read_dwd_data(files: List[str],
                  keep_zip=False) -> pd.DataFrame:
    """
    This function is used to read the stationdata for which the local zip link is
    provided by the 'download_dwd' function. It checks the zipfile from the link
    for its parameters, opens every zipfile in the list of files and reads in the
    containing product file, and if there's an error or it's wanted the zipfile is
    removed afterwards.

    Args:
        files:
        keep_zip:

    Returns:
        DataFrame with requested data

    """
    # Test for types of input parameters
    assert isinstance(files, list)
    assert isinstance(keep_zip, bool)

    # Check for files and if empty return empty DataFrame
    if not files:
        return pd.DataFrame()

    # Get first filename
    first_filename = files[0].split("/")[-1]

    # Determine variables (by first filename)
    parameter, time_resolution, period_type = determine_parameters(first_filename)

    # Check for combination
    check_parameters(parameter, time_resolution, period_type)

    # Create empty dataframe to combine several files
    data = []

    # Read in every single datafile
    for file in files:
        # Try doing everything without know of the existance of file
        try:
            with ZipFile(file) as zip_file:
                # List of fileitems in zipfile
                zip_file_files = zip_file.infolist()

                # List of filenames of fileitems
                zip_file_files = [zip_file_file.filename
                                  for zip_file_file in zip_file_files]

                # Filter file with 'produkt' in filename
                file_data = [zip_file_file
                             for zip_file_file in zip_file_files
                             if all([matchstring in zip_file_file.lower()
                                     for matchstring in STATIONDATA_MATCHSTRINGS])]

                # List to filename
                file_data = file_data.pop(0)

                with zip_file.open(file_data) as file_opened:
                    # Read data into a dataframe
                    data_file = pd.read_csv(filepath_or_buffer=file_opened,
                                            sep=";",
                                            na_values="-999")

            # Append dataframe to list of all data read
            data.append(data_file)

        except Exception:
            # In case something goes wrong there's a print
            print(f'''The zipfile
                  {file}
                  couldn't be opened/read and will be removed.''')
            # Data will be removed
            Path(file).unlink()

        finally:
            # If file shouldn't be kept remove it
            if not keep_zip:
                Path(file).unlink()

    # Put together list of files to a DataFrame
    data = pd.concat(data)

    # Extract column names
    column_names = data.columns

    # Strip empty chars from before and after column names
    column_names = [column_name.upper().strip()
                    for column_name in column_names]

    # Replace certain names by conform names
    column_names = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(column_name, column_name)
                    for column_name in column_names]

    # Reassign column names to DataFrame
    data.columns = column_names

    # String to date
    data[DATE_NAME] = data[DATE_NAME].apply(
        lambda date: dt.strptime(str(date), "%Y%m%d"))

    return data
