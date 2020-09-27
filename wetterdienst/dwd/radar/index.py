import re
from typing import Optional
from urllib.parse import urljoin

import pandas as pd
from dateparser import parse

from wetterdienst import TimeResolution, PeriodType
from wetterdienst.dwd.metadata.constants import ArchiveFormat, DWD_SERVER, DWD_CDC_PATH
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.dwd.radar.sites import RadarSites
from wetterdienst.dwd.radar.metadata import (
    RadarParameter,
    RadarDataType,
    RADAR_PARAMETERS_COMPOSITES,
    RADAR_PARAMETERS_SITES,
    RADAR_PARAMETERS_WITH_HDF5,
    RADAR_PARAMETERS_RADOLAN,
)
from wetterdienst.util.cache import fileindex_cache_five_minutes
from wetterdienst.util.network import list_remote_files

RADOLAN_HISTORICAL_DT_REGEX = r"(?<!\d)\d{6}(?!\d)"
RADOLAN_RECENT_DT_REGEX = r"(?<!\d)\d{10}(?!\d)"


@fileindex_cache_five_minutes.cache_on_arguments()
def create_file_index_for_radolan(time_resolution: TimeResolution) -> pd.DataFrame:
    """
    Function used to create a file index for the RADOLAN product. The file index will
    include both recent as well as historical files. A datetime column is created from
    the filenames which contain some datetime formats. This datetime column is required
    for later filtering for the requested file.

    Args:
        time_resolution: time resolution enumeration for the requesed RADOLAN product,
        where two are possible: hourly and daily

    Returns:
        file index as DataFrame
    """
    file_index = pd.concat(
        [
            _create_fileindex_radar(
                RadarParameter.RADOLAN,
                time_resolution,
                period_type,
            )
            for period_type in (PeriodType.HISTORICAL, PeriodType.RECENT)
        ]
    )

    file_index = file_index[
        file_index[DWDMetaColumns.FILENAME.value].str.contains("/bin/")
        & file_index[DWDMetaColumns.FILENAME.value].str.endswith(
            (ArchiveFormat.GZ.value, ArchiveFormat.TAR_GZ.value)
        )
    ]

    r = re.compile(f"{RADOLAN_HISTORICAL_DT_REGEX}|{RADOLAN_RECENT_DT_REGEX}")

    # Require datetime of file for filtering
    file_index[DWDMetaColumns.DATETIME.value] = file_index[
        DWDMetaColumns.FILENAME.value
    ].apply(
        lambda filename: parse(
            r.findall(filename)[0],
            date_formats=[DatetimeFormat.YM.value, DatetimeFormat.ymdhm.value],
        )
    )

    return file_index


def _create_fileindex_radar(
    parameter: RadarParameter,
    time_resolution: Optional[TimeResolution] = None,
    period_type: Optional[PeriodType] = None,
    radar_site: Optional[RadarSites] = None,
    radar_data_type: Optional[RadarDataType] = None,
) -> pd.DataFrame:
    """
    Function to create a file index of the DWD radar data, which is shipped as
    bin bufr or odim-hdf5 data. The file index is created for a single parameter.

    Args:
        parameter: parameter of Parameter enumeration
        time_resolution: time resolution of TimeResolution enumeration
        period_type: period type of PeriodType enumeration
        radar_site: Site of the radar if parameter is one of RADAR_PARAMETERS_SITES
        radar_data_type: Some radar data are available in different data types
    Returns:
        file index in a pandas.DataFrame with sets of parameters and station id
    """
    parameter_path = build_path_to_parameter(
        parameter, time_resolution, period_type, radar_site, radar_data_type
    )

    url = urljoin(DWD_SERVER, parameter_path)

    files_server = list_remote_files(url, recursive=True)

    files_server = pd.DataFrame(
        files_server, columns=[DWDMetaColumns.FILENAME.value], dtype="str"
    )

    # Some directories have both "---bin" and "---bufr" files within the same directory,
    # so we need to filter here by designated RadarDataType. Example:
    # https://opendata.dwd.de/weather/radar/sites/px/boo/
    if radar_data_type is not None:
        if radar_data_type == RadarDataType.BINARY:
            files_server = files_server[
                files_server[DWDMetaColumns.FILENAME.value].str.contains("--bin")
            ]
        elif radar_data_type == RadarDataType.BUFR:
            files_server = files_server[
                files_server[DWDMetaColumns.FILENAME.value].str.contains("--buf")
            ]

    return files_server


def build_path_to_parameter(
    parameter: RadarParameter,
    time_resolution: Optional[TimeResolution] = None,
    period_type: Optional[PeriodType] = None,
    radar_site: Optional[RadarSites] = None,
    radar_data_type: Optional[RadarDataType] = None,
) -> str:
    """
    Function to build a indexing file path.
    Supports composite- and site-based radar data.

    Composites
    ----------
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/5_minutes/radolan/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/hourly/radolan/
    - https://opendata.dwd.de/weather/radar/composit/
    - https://opendata.dwd.de/weather/radar/radolan/

    Sites
    -----
    - https://opendata.dwd.de/weather/radar/sites/


    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        radar_site: Site of the radar if parameter is one of RADAR_PARAMETERS_SITES
        radar_data_type: Some radar data are available in different data types

    Returns:
        indexing file path relative to climate observations path
    """
    if parameter == RadarParameter.RADOLAN_GRID:
        if time_resolution == TimeResolution.MINUTE_5:
            parameter_path = f"{DWD_CDC_PATH}/grids_germany/{time_resolution.value}/radolan/reproc/2017_002/bin"  # noqa:E501,B950
        else:
            parameter_path = f"{DWD_CDC_PATH}/grids_germany/{time_resolution.value}/radolan/{period_type.value}/bin"  # noqa:E501,B950

    elif parameter in RADAR_PARAMETERS_COMPOSITES:
        parameter_path = f"weather/radar/composit/{parameter.value}"

    elif parameter in RADAR_PARAMETERS_RADOLAN:
        parameter_path = f"weather/radar/radolan/{parameter.value}"

    elif parameter in RADAR_PARAMETERS_SITES:
        if radar_site is None:
            raise ValueError("Acquiring radar site data requires a RadarSite")
        else:
            parameter_path = f"weather/radar/sites/{parameter.value}/{radar_site.value}"
            if parameter in RADAR_PARAMETERS_WITH_HDF5:
                if radar_data_type is None:
                    raise ValueError("RadarDataType missing [hdf5 or binary]")
                elif radar_data_type is RadarDataType.HDF5:
                    parameter_path = f"{parameter_path}/{radar_data_type.value}"

    else:
        raise KeyError("Failed to compute path to RADAR data")

    return parameter_path
