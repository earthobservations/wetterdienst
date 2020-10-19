""" Tests for parse_dwd_data function """
from typing import Union
from io import StringIO, BytesIO
from pathlib import Path
import pandas as pd

from wetterdienst.dwd.observations.metadata.parameter_set import (
    DWDObsParameterSet,
    DWDObsTimeResolution,
)
from wetterdienst.dwd.observations.parser import (
    parse_climate_observations_data,
)

HERE = Path(__file__).parent


def test_parse_dwd_data():
    filename = "tageswerte_KL_00001_19370101_19860630_hist.zip"

    station_data_original = pd.read_json(HERE / "FIXED_STATIONDATA.JSON")
    file_in_bytes: Union[StringIO, BytesIO] = StringIO()
    station_data_original.to_csv(file_in_bytes, sep=";")
    file_in_bytes.seek(0)

    station_data = parse_climate_observations_data(
        filenames_and_files=[(filename, BytesIO(file_in_bytes.read().encode()))],
        parameter=DWDObsParameterSet.CLIMATE_SUMMARY,
        time_resolution=DWDObsTimeResolution.DAILY,
    )

    station_data.equals(station_data_original)
