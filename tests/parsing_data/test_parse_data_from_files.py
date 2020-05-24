""" Tests for parse_dwd_data function """
from typing import Union
from io import StringIO, BytesIO
from pathlib import Path
import pandas as pd

from python_dwd.parsing_data.parse_data_from_files import parse_dwd_data

fixtures_dir = Path(__file__, "../..").resolve().absolute() / "fixtures"


def test_parse_dwd_data():
    filename = "tageswerte_KL_00001_19370101_19860630_hist.zip"

    station_data_original = pd.read_json(fixtures_dir / "FIXED_STATIONDATA.JSON")
    file_in_bytes: Union[StringIO, BytesIO] = StringIO()
    station_data_original.to_csv(file_in_bytes, sep=";")
    file_in_bytes.seek(0)

    station_data = parse_dwd_data(
        filenames_and_files=[(filename, file_in_bytes)])

    station_data.equals(station_data_original)
