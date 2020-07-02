""" helping functions for downloading german weather service data """
from io import BytesIO
from pathlib import PurePosixPath
from typing import Union

from wetterdienst.download.https_handling import create_dwd_session
from wetterdienst.file_path_handling.path_handling import build_climate_observations_path


def download_file_from_climate_observations(filepath: Union[PurePosixPath, str]) -> BytesIO:
    """
    A function used to download a specified file from the server

    Args:
        filepath: the path that defines the file
        base_url: the base_url representing the part of the server which is worked with

    Returns:
        bytes of the file
    """
    dwd_session = create_dwd_session()

    r = dwd_session.get(build_climate_observations_path(filepath))
    r.raise_for_status()

    return BytesIO(r.content)
