import re
from pathlib import PurePosixPath
from typing import Optional, Union

import pandas as pd
from dateparser import parse

from wetterdienst import TimeResolution, Parameter, PeriodType
from wetterdienst.dwd.metadata.constants import DWDCDCBase, ArchiveFormat, DWDWeatherBase
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.dwd.index import _create_file_index_for_dwd_server
from wetterdienst.dwd.metadata.radar_data_types import RadarDataTypes
from wetterdienst.dwd.metadata.radar_sites import RadarSites
from wetterdienst.file_path_handling.path_handling import RADAR_PARAMETERS_COMPOSITES, RADAR_PARAMETERS_SITES, \
    RADAR_PARAMETERS_WITH_HDF5
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
            _create_file_index_radolan(
                Parameter.RADOLAN,
                time_resolution,
                period_type,
                DWDCDCBase.GRIDS_GERMANY,
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


def _create_file_index_radolan(
    parameter: Parameter,
    time_resolution: TimeResolution,
    dwd_base: Union[DWDCDCBase, DWDWeatherBase],
    period_type: Optional[PeriodType] = None,
    radar_site: Optional[RadarSites] = None,
    radar_data_type: Optional[RadarDataTypes] = None
) -> pd.DataFrame:
    """
    Function to create a file index of the DWD station data, which usually is shipped as
    zipped/archived data. The file index is created for an individual set of parameters.
    Args:
        parameter: parameter of Parameter enumeration
        time_resolution: time resolution of TimeResolution enumeration
        dwd_base: base path e.g. climate_observations/germany or weather
        period_type: period type of PeriodType enumeration
        radar_site: Site of the radar if parameter is one of RADAR_PARAMETERS_SITES
        radar_data_type: Some radar data are available in different data types
    Returns:
        file index in a pandas.DataFrame with sets of parameters and station id
    """
    parameter_path = build_path_to_parameter(parameter,
                                             time_resolution,
                                             period_type,
                                             radar_site,
                                             radar_data_type)

    files_server = list_remote_files(parameter_path, dwd_base, recursive=True)

    files_server = pd.DataFrame(
        files_server, columns=[DWDMetaColumns.FILENAME.value], dtype="str"
    )

    data_directory = DWDCDCBase.PATH.value \
        if isinstance(dwd_base, DWDCDCBase) else DWDWeatherBase.PATH.value

    files_server[DWDMetaColumns.FILENAME.value] = files_server[
        DWDMetaColumns.FILENAME.value
    ].str.replace(f"{data_directory}/{dwd_base.value}/", "")

    return files_server


def build_path_to_parameter(
        parameter: Parameter,
        radar_site: Optional[RadarSites] = None,
        radar_data_type: Optional[RadarDataTypes] = None
) -> PurePosixPath:
    """
    Function to build a indexing file path
    Args:
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        radar_site: Site of the radar if parameter is one of RADAR_PARAMETERS_SITES
        radar_data_type: Some radar data are available in different data types

    Returns:
        indexing file path relative to climate observations path
    """
    if parameter in RADAR_PARAMETERS_COMPOSITES:
        parameter_path = PurePosixPath(parameter.value)

    elif parameter in RADAR_PARAMETERS_SITES:
        if radar_site is None:
            raise ValueError("You have choosen radar site data which "
                             "requires to pass a RadarSite")
        else:
            parameter_path = PurePosixPath(parameter.value,
                                           radar_site.value)
            if parameter in RADAR_PARAMETERS_WITH_HDF5:
                if radar_data_type is None:
                    raise ValueError("You have to define a RadarDataType [hdf5 or binary]")
                elif radar_data_type is RadarDataTypes.HDF5:
                    parameter_path = PurePosixPath.joinpath(parameter_path, radar_data_type.value)

    else:
        raise KeyError("Unknown parameter for RADAR")

    return parameter_path
