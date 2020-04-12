from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd

from python_dwd import parse_dwd_data

fixtures_dir = Path(__file__, "../..").resolve().absolute() / "fixtures"

file_in_bytes = pd.read_json(fixtures_dir / "FIXED_STATIONDATA.JSON")

@patch(
    'pandas.read_csv',
    MagicMock(return_value=file_in_bytes)
)
def test_parse_dwd_data():
    filename = "tageswerte_KL_00001_19370101_19860630_hist.zip"

    stationdata_1 = parse_dwd_data(
        files_in_bytes=[(filename, file_in_bytes)],
        write_file=True,
        folder=Path(__file__).parent.absolute() / "dwd_data"
    )

    stationdata_2 = parse_dwd_data(
        files_in_bytes=[(filename, file_in_bytes)],
        prefer_local=True,
        folder=Path(__file__).parent.absolute() / "dwd_data"
    )

    assert stationdata_1.equals(stationdata_2)


# @todo removing old files created for test
def test_remove_file():
    Path(Path(__file__).parent.absolute() / "dwd_data").rmdir()

    assert True
