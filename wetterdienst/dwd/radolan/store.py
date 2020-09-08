from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Tuple, Union

from wetterdienst import TimeResolution, Parameter
from wetterdienst.dwd.metadata.datetime import DatetimeFormat


def store_radolan_data(
        parameter: Parameter,
        date_time_and_file: Tuple[datetime, BytesIO],
        time_resolution: TimeResolution,
        folder: Union[str, Path],
) -> None:
    """
    Stores a binary file of radolan data locally
    """

    date_time, file = date_time_and_file

    filepath = build_local_filepath_for_radar(parameter, date_time, folder, time_resolution)

    filepath.parent.mkdir(parents=True, exist_ok=True)

    with filepath.open("wb") as f:
        f.write(file.read())


def restore_radolan_data(
        parameter: Parameter,
        date_time: datetime,
        time_resolution: TimeResolution,
        folder: Union[str, Path]
) -> BytesIO:
    """ Opens downloaded radolan data into a binary object"""
    filepath = build_local_filepath_for_radar(parameter, date_time, folder, time_resolution)

    with filepath.open("rb") as f:
        file_in_bytes = BytesIO(f.read())

    return file_in_bytes


def build_local_filepath_for_radar(
        parameter: Parameter,
        date_time: datetime,
        folder: Union[str, Path],
        time_resolution: TimeResolution
) -> Union[str, Path]:
    """

    Args:
        parameter: radar data parameter
        date_time: Timestamp of file
        folder:
        time_resolution:

    Returns:

    """
    local_filepath = Path(
        folder,
        parameter.value,
        time_resolution.value,
        f"{parameter.value}_{time_resolution.value}_"
        f"{date_time.strftime(DatetimeFormat.YMDHM.value)}",
    ).absolute()

    return local_filepath
