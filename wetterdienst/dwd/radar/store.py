from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Tuple, Union

from wetterdienst import TimeResolution
from wetterdienst.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.dwd.radar.metadata import RadarParameter


def store_radar_data(
    parameter: RadarParameter,
    date_time_and_file: Tuple[datetime, BytesIO],
    time_resolution: TimeResolution,
    folder: Union[str, Path],
) -> None:
    """
    Stores a binary file of radar data locally.
    """

    date_time, file = date_time_and_file

    filepath = _build_local_filepath(parameter, date_time, folder, time_resolution)

    filepath.parent.mkdir(parents=True, exist_ok=True)

    with filepath.open("wb") as f:
        f.write(file.read())


def restore_radar_data(
    parameter: RadarParameter,
    date_time: datetime,
    time_resolution: TimeResolution,
    folder: Union[str, Path],
) -> BytesIO:
    """ Opens downloaded radar data into a binary object"""
    filepath = _build_local_filepath(parameter, date_time, folder, time_resolution)

    with filepath.open("rb") as f:
        file_in_bytes = BytesIO(f.read())

    return file_in_bytes


def _build_local_filepath(
    parameter: RadarParameter,
    date_time: datetime,
    folder: Union[str, Path],
    time_resolution: TimeResolution,
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
