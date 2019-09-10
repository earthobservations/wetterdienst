"""
A set of more general functions used for the organization
"""
from pathlib import Path
from typing import Tuple

from python_dwd.constants.parameter_mapping import TIME_RESOLUTION_PARAMETER_MAPPING


def correct_folder_path(folder: str) -> str:
    """ checks if given folder ends with "/" cuts that off """
    return folder.rstrip('/')


def remove_old_file(file_type,
                    parameter,
                    time_resolution,
                    period_type,
                    fileformat,
                    folder,
                    subfolder):
    """
        Function to remove old dwd file (metadata)
    Args:
        file_type:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        fileformat:
        folder:
        subfolder:

    Returns:
        Deleted file on local filesystem

    """
    file_to_remove = f"{file_type}_{parameter}_{time_resolution}_{period_type}{fileformat}"

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


def determine_parameters(filename: str) -> Tuple[str, str, str]:
    """
    Function to determine the type of file from the bare filename
    Needed for downloading the file and naming it correctly and understandable

    Args:
        filename: str containing all parameter information

    Returns:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files

    """
    filename = filename.lower()

    # First check for time resolution
    if "1minutenwerte_" in filename:
        time_resolution = "1_minute"
    elif "10minutenwerte_" in filename:
        time_resolution = "10_minutes"
    elif "stundenwerte_" in filename:
        time_resolution = "hourly"
    elif "tageswerte_" in filename:
        time_resolution = "daily"
    elif "monatswerte_" in filename:
        time_resolution = "monthly"
    elif "jahreswerte_" in filename:
        time_resolution = "annual"
    else:
        time_resolution = None

    if time_resolution is None:
        raise NameError(f"Resolution {time_resolution} couldn't be determined.")

    # First determine the variable
    if time_resolution == "1_minute":
        if "_nieder_" in filename:
            parameter = "precipitation"
        else:
            parameter = None
    elif time_resolution == "10_minutes":
        if "_tu_" in filename:
            parameter = "air_temperature"
        elif "_tx_" in filename or "_extrema_temp_" in filename:
            parameter = "extreme_temperature"
        elif "_fx_" in filename or "_extrema_wind_" in filename:
            parameter = "extreme_wind"
        elif "_rr_" in filename or "_nieder_" in filename:
            parameter = "precipitation"
        elif "_solar_" in filename:
            parameter = "solar"
        elif "_ff_" in filename or "_wind_" in filename:
            parameter = "wind"
        else:
            parameter = None
    elif time_resolution == "hourly":
        if "_tu_" in filename:
            parameter = "air_temperature"
        elif "_cs_" in filename:
            parameter = "cloud_type"
        elif "_n_" in filename:
            parameter = "cloudiness"
        elif "_rr_" in filename:
            parameter = "precipitation"
        elif "_p0_" in filename:
            parameter = "pressure"
        elif "_eb_" in filename:
            parameter = "soil_temperature"
        elif "_st_" in filename:
            parameter = "solar"
        elif "_sd_" in filename:
            parameter = "sun"
        elif "_vv_" in filename:
            parameter = "visibility"
        elif "_ff_" in filename:
            parameter = "wind"
        else:
            parameter = None
    elif time_resolution == "daily":
        if "_kl_" in filename:
            parameter = "kl"
        elif "_rr_" in filename:
            parameter = "more_precip"
        elif "_eb_" in filename:
            parameter = "soil_temperature"
        elif "_st_" in filename:
            parameter = "solar"
        elif "_wa_" in filename:
            parameter = "water_equiv"
        else:
            parameter = None
    elif time_resolution == "monthly":
        if "_kl_" in filename:
            parameter = "kl"
        elif "_rr_" in filename:
            parameter = "more_precip"
        else:
            parameter = None
    elif time_resolution == "annual":
        if "_kl_" in filename:
            parameter = "kl"
        elif "_rr_" in filename:
            parameter = "more_precip"
        else:
            parameter = None
    else:
        parameter = None

    if parameter is None:
        raise NameError(f"Variable {parameter} couldn't be determined.")

    if "_hist" in filename:
        period_type = "historical"
    elif "_akt" in filename:
        period_type = "recent"
    elif "_now" in filename:
        period_type = "now"
    elif "_row" in filename:
        period_type = ""
    else:
        period_type = None

    if period_type is None:
        raise NameError(f"Timestamp {period_type} couldn't be determined.")

    return parameter, time_resolution, period_type


def check_parameters(parameter: str,
                     time_resolution: str,
                     period_type: str):
    """
    Function to check for element (alternative name) and if existing return it
    Differs from foldername e.g. air_temperature -> tu

    """
    check = TIME_RESOLUTION_PARAMETER_MAPPING.get(time_resolution, [[], []])

    if parameter not in check[0] or period_type not in check[1]:
        raise NameError(
            f"Combination of time_resolution={time_resolution},parameter={parameter} "
            f"and period_type={period_type} not available.Possible parameters are: "
            f"{TIME_RESOLUTION_PARAMETER_MAPPING}.")

    return None
