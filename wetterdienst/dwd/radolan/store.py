from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Tuple, Union

from wetterdienst import TimeResolution
from wetterdienst.dwd.metadata.datetime import DatetimeFormat


def store_radolan_data(
    date_time_and_file: Tuple[datetime, BytesIO],
    time_resolution: TimeResolution,
    folder: Union[str, Path],
) -> None:

    date_time, file = date_time_and_file

    filepath = build_local_filepath_for_radolan(date_time, folder, time_resolution)

    filepath.parent.mkdir(parents=True, exist_ok=True)

    with filepath.open("wb") as f:
        f.write(file.read())

    # When the file has been written, reset seek pointer.
    file.seek(0)


def restore_radolan_data(
    date_time: datetime, time_resolution: TimeResolution, folder: Union[str, Path]
) -> BytesIO:
    filepath = build_local_filepath_for_radolan(date_time, folder, time_resolution)

    with filepath.open("rb") as f:
        file_in_bytes = BytesIO(f.read())

    return file_in_bytes


def build_local_filepath_for_radolan(
    date_time: datetime, folder: Union[str, Path], time_resolution: TimeResolution
) -> Union[str, Path]:
    """

    Args:
        date_time:
        folder:
        time_resolution:

    Returns:

    """
    local_filepath = Path(
        folder,
        "radolan",
        time_resolution.value,
        f"radolan_{time_resolution.value}_"
        f"{date_time.strftime(DatetimeFormat.YMDHM.value)}",
    ).absolute()

    return local_filepath
