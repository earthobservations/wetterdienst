""" functions to handle paths and file names"""

from pathlib import Path

from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


def correct_folder_path(folder: str) -> str:
    """ checks if given folder ends with "/" cuts that off """
    return folder.rstrip('/')


def remove_old_file(file_type: str,
                    parameter: Parameter,
                    time_resolution: TimeResolution,
                    period_type: PeriodType,
                    file_postfix: str,
                    folder: str,
                    subfolder: str) -> None:
    """
    Function to remove old dwd file (metadata)


    Returns:
        Deleted file on local filesystem

    """
    filepath_to_remove = Path(folder,
                              subfolder,
                              f"{file_type}_{parameter.value}_"
                              f"{time_resolution.value}_"
                              f"{period_type.value}{file_postfix}")

    try:
        Path.unlink(filepath_to_remove)
    except FileNotFoundError:
        pass

    return None


def create_folder(subfolder: str,
                  folder: str):
    """
    Function for creating folder structure for saved stationdata
    """
    path_to_create = Path(correct_folder_path(folder),
                          subfolder)

    try:
        Path(path_to_create).mkdir(parents=True)
    except FileExistsError:
        print(f"Error: Folder at {path_to_create} already exists.")

    return None
