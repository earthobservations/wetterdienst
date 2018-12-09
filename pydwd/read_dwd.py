import pandas as pd
import zipfile
import datetime as dt

import pydwd_functions


def reduce_to_values(data):
    pass


def read_dwd(files):
    # Check for files
    if len(files) == 0:
        return(None)

    # Determine variables
    var, res, per = pydwd_functions.determine_type(files[0].split("/")[-1])

    # Check for combination
    pydwd_functions.check_dwd_structure(var=var, res=res, per=per)

    # Create empty dataframe to combine several files
    data = []

    # Read in every single datafile
    for file in files:
        # Try doing everything without know of the existance of file
        try:
            zip_file = zipfile.ZipFile(file)
            file_with_data = [
                file_in_zip.filename for file_in_zip in zip_file.infolist()
                if "produkt" in file_in_zip.filename]
            data_file = pd.read_csv(
                filepath_or_buffer=zip_file.open(file_with_data[0]),
                sep=";",
                na_values="-999")
            data.append(data_file)
        except Exception as e:
            print("The file {} couldn't be read.".format(file))
            print(e)

    # Put together several rows of data from different files
    data = pd.concat(data)

    # Here the data is cleaned
    data["MESS_DATUM"] = [dt.datetime.strptime(
        str(date), "%Y%m%d") for date in data["MESS_DATUM"]]

    return(data)
