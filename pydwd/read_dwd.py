import pandas as pd
import zipfile
import datetime as dt

from .additionals.generic_functions import determine_parameters
from .additionals.generic_functions import check_parameters


def read_dwd(files):
    # Check for files
    if len(files) == 0:
        return(None)

    # Determine variables
    var, res, per = determine_parameters(files[0].split("/")[-1])

    # Check for combination
    check_parameters(var=var, res=res, per=per)

    # Create empty dataframe to combine several files
    data = []

    # Read in every single datafile
    for file in files:
        # Try doing everything without know of the existance of file
        try:
            zip_file = zipfile.ZipFile(file)

            file_data = [file.filename
                         for file in zip_file.infolist()
                         if "produkt" in file.filename]

            file_data = file_data[0]

        except Exception:
            # In case something goes wrong file_data is set to None to ensure
            # that there's no old csv being opened
            file_data = None

            print("The zipfile {} couldn't be opened.".format(file))
            # print(e)

        try:
            data_file = pd.read_csv(
                filepath_or_buffer=zip_file.open(file_data),
                sep=";",
                na_values="-999")

            data.append(data_file)
        except Exception:
            print("The data from the zipfile {} couldn't be read.".format(
                file))
            # print(e)

    # Put together several rows of data from different files
    data = pd.concat(data)

    # Strip eventual whitespace around columnnames
    data.columns = [column.strip() for column in data.columns]

    # Date column is transformed from character to datetime
    data["MESS_DATUM"] = [dt.datetime.strptime(str(date), "%Y%m%d")
                          for date in data["MESS_DATUM"]]

    return data
