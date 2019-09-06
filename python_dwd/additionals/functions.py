"""A set of more general functions used for the organization
"""

from pathlib import Path
from python_dwd.constants.parameter_mapping import TIME_RESOLUTION_PARAMETER_MAPPING


def correct_folder_path(folder: str) -> str:
    """ checks if given folder ends with "/" cuts that off """
    return folder.rstrip('/')


def remove_old_file(file_type,
                    var,
                    res,
                    per,
                    fileformat,
                    folder,
                    subfolder):
    """
        Function to remove old dwd file (metadata)
    Args:
        file_type:
        var:
        res:
        per:
        fileformat:
        folder:
        subfolder:

    Returns:
        Deleted file on local filesystem

    """
    file_to_remove = f"{file_type}_{var}_{res}_{per}{fileformat}"

    filepath_to_remove = Path(folder,
                              subfolder,
                              file_to_remove)

    # Try to remove the file
    try:
        Path.unlink(filepath_to_remove)
    except Exception:
        pass
        # print('No file found to delete in \n{}!'.format(folder))

    return None


def create_folder(subfolder: str,
                  folder: str):
    """
    Function for creating folder structure for saved stationdata
    """
    folder = correct_folder_path(folder)
    path_to_create = Path(folder,
                          subfolder)

    # Try to create folder
    try:
        if not Path(path_to_create).is_dir():
            Path(path_to_create).mkdir(parents=True)
    except Exception:
        raise NameError(f"Folder couldn't be created at \n{path_to_create} !")

    return None


def determine_parameters(filename: str):
    """
    Function to determine the type of file from the bare filename
    Needed for downloading the file and naming it correctly and understandable

    Args:
        filename: str containing all parameter information

    Returns:

    """
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
        raise NameError(f"Resolution {res} couldn't be determined.")

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
        raise NameError(f"Variable {var} couldn't be determined.")

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
        raise NameError(f"Timestamp {per} couldn't be determined.")

    return var, res, per


def check_parameters(parameter,
                     time_resolution,
                     period_type):
    """
    Function to check for element (alternative name) and if existing return it
    Differs from foldername e.g. air_temperature -> tu
    Args:
        parameter:
        time_resolution:
        period_type:

    Returns:

    """
    check = TIME_RESOLUTION_PARAMETER_MAPPING.get(time_resolution, [[], []])

    if parameter not in check[0] or period_type not in check[1]:
        raise NameError(
            f"Combination of time_resolution={time_resolution},parameter={parameter} "
            f"and period_type={period_type} not available.Possible parameters are: "
            f"{TIME_RESOLUTION_PARAMETER_MAPPING}.")

    return None
