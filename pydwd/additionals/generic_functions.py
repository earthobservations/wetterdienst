# Import modules
from pathlib import Path

"""
######################################
### Function 'correct_folder_path' ###
######################################
- checks if given folder ends with "/" cuts that off
"""


def correct_folder_path(folder):
    if folder[-1] == "/":
        folder = folder[:-1]

    return folder


def determine_statid_col(per):
    if per == "historical":
        statid_col = -4
    elif per == "recent":
        statid_col = -2
    elif per == "now":
        statid_col = -2
    else:
        statid_col = None

    return statid_col


"""
Function to remove old dwd file (metadata)
"""


def remove_old_file(file_type,
                    var,
                    res,
                    per,
                    folder):
    # Correct folder of file
    folder = correct_folder_path(folder)

    metainfo_to_remove = "{}/{}/{}_{}_{}_{}{}".format(
        folder, "metadata", file_type, var, res, per, ".csv")

    # Try to remove the file
    try:
        Path.unlink(metainfo_to_remove)
    except Exception:
        pass
        # print('No file found to delete in \n{}!'.format(folder))

    return None


"""
Function for creating folder structure for saved stationdata
"""


def create_folder(subfolder,
                  folder):
    # Correct folder path to make it work
    folder = correct_folder_path(folder)

    path_to_create = "{}/{}".format(folder, subfolder)

    # Try to create folder
    try:
        if not Path(path_to_create).is_dir():
            Path(path_to_create).mkdir(parents=True)
    except Exception:
        raise NameError(
            "Folder couldn't be created at \n{} !".format(path_to_create))

    return None


"""
Function to determine the type of file from the bare filename
Needed for downloading the file and naming it correctly and understandable
"""


def determine_parameters(filename):
    filename = filename.lower()

    # First check for time resolution
    if "1minutenwerte_" in filename:
        res = "1_minute"
    elif "10minutenwerte_" in filename:
        res = "10_minutes"
    elif "stundenwerte_" in filename:
        res = "hourly"
    elif "tageswerte_" in filename:
        res = "daily"
    elif "monatswerte_" in filename:
        res = "monthly"
    elif "jahreswerte_" in filename:
        res = "annual"
    else:
        res = None

    if res is None:
        raise NameError("Resolution {} couldn't be determined.".format(res))

    # First determine the variable
    if res == "1_minute":
        if "_nieder_" in filename:
            var = "precipitation"
        else:
            var = None
    elif res == "10_minutes":
        if "_tu_" in filename:
            var = "air_temperature"
        elif "_tx_" in filename or "_extrema_temp_" in filename:
            var = "extreme_temperature"
        elif "_fx_" in filename or "_extrema_wind_" in filename:
            var = "extreme_wind"
        elif "_rr_" in filename or "_nieder_" in filename:
            var = "precipitation"
        elif "_solar_" in filename:
            var = "solar"
        elif "_ff_" in filename or "_wind_" in filename:
            var = "wind"
        else:
            var = None
    elif res == "hourly":
        if "_tu_" in filename:
            var = "air_temperature"
        elif "_cs_" in filename:
            var = "cloud_type"
        elif "_n_" in filename:
            var = "cloudiness"
        elif "_rr_" in filename:
            var = "precipitation"
        elif "_p0_" in filename:
            var = "pressure"
        elif "_eb_" in filename:
            var = "soil_temperature"
        elif "_st_" in filename:
            var = "solar"
        elif "_sd_" in filename:
            var = "sun"
        elif "_vv_" in filename:
            var = "visibility"
        elif "_ff_" in filename:
            var = "wind"
        else:
            var = None
    elif res == "daily":
        if "_kl_" in filename:
            var = "kl"
        elif "_rr_" in filename:
            var = "more_precip"
        elif "_eb_" in filename:
            var = "soil_temperature"
        elif "_st_" in filename:
            var = "solar"
        elif "_wa_" in filename:
            var = "water_equiv"
        else:
            var = None
    elif res == "monthly":
        if "_kl_" in filename:
            var = "kl"
        elif "_rr_" in filename:
            var = "more_precip"
        else:
            var = None
    elif res == "annual":
        if "_kl_" in filename:
            var = "kl"
        elif "_rr_" in filename:
            var = "more_precip"
        else:
            var = None
    else:
        var = None

    if var is None:
        raise NameError("Variable {} couldn't be determined.".format(var))

    if "_hist" in filename:
        per = "historical"
    elif "_akt" in filename:
        per = "recent"
    elif "_now" in filename:
        per = "now"
    elif "_row" in filename:
        per = ""
    else:
        per = None

    if per is None:
        raise NameError("Timestamp {} couldn't be determined.".format(per))

    return var, res, per


"""
Function to check for element (alternative name) and if existing return it
Differs from foldername e.g. air_temperature -> tu
"""


def check_parameters(var, res, per):

    param_struct = {
        "1_minute":     [["precipitation"],
                         ["historical",
                          "recent",
                          "now"]],
        "10_minutes":   [["air_temperature",
                          "extreme_temperature",
                          "extreme_wind",
                          "precipitation",
                          "solar",
                          "wind"],
                         ["historical",
                          "recent",
                          "now"]],
        "hourly":       [["air_temperature",
                          "cloud_type",
                          "cloudiness",
                          "precipitation",
                          "pressure",
                          "soil_temperature",
                          "solar",
                          "sun",
                          "visibility",
                          "wind"],
                         ["historical",
                          "recent"]],
        "daily":        [["kl",
                          "more_precip",
                          "soil_temperature",
                          "solar",
                          "water_equiv"],
                         ["historical",
                          "recent"]],
        "monthly":      [["kl",
                          "more_precip"],
                         ["historical",
                          "recent"]],
        "annual":       [["kl",
                          "more_precip"],
                         ["historical",
                          "recent"]]
    }

    check = param_struct.get(res, [[], []])

    if var not in check[0] or per not in check[1]:
        raise NameError(
            "Combination of res='{}', var='{}' and per='{}' not available. Possible parameters are: \n {}.".
            format(res, var, per, param_struct))

    return None
