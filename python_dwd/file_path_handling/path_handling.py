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
                    subfolder: str):
    """
    Function to remove old dwd file (metadata)


    Returns:
        Deleted file on local filesystem

    """
    file_to_remove = f"{file_type}_{parameter.value}_" \
                     f"{time_resolution.value}_" \
                     f"{period_type.value}{file_postfix}"

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