from io import StringIO
from shutil import rmtree
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd

from python_dwd import parse_dwd_data

fixtures_dir = Path(__file__, "../..").resolve().absolute() / "fixtures"

file = pd.read_json(fixtures_dir / "FIXED_STATIONDATA.JSON")

file_in_bytes = StringIO()
file.to_csv(file_in_bytes, sep=";", )

# @patch(
#     'pandas.read_csv',
#     MagicMock(return_value=file_in_bytes)
# )
def test_parse_dwd_data():
    filename = "tageswerte_KL_00001_19370101_19860630_hist.zip"

    file_in_bytes.seek(0)
    stationdata_online = parse_dwd_data(
        filenames_and_files=[(filename, file_in_bytes)],
        write_file=True,
        folder=Path(__file__).parent.absolute() / "dwd_data"
    )

    stationdata_local = parse_dwd_data(
        filenames_and_files=[(filename, file_in_bytes)],
        prefer_local=True,
        folder=Path(__file__).parent.absolute() / "dwd_data"
    )

    # 1. Compare freshly loaded data with data read from hdf and assure it's identical
    assert stationdata_online.equals(stationdata_local)

    # 2. Check functioning for filename only, that is used for parameter definition to parse data from local hdf file
    assert stationdata_online.equals(
        parse_dwd_data(
            filenames_and_files=[filename],
            prefer_local=True,
            folder=Path(__file__).parent.absolute() / "dwd_data",
            write_file=False
        )
    )

    # 3. Check for only giving filename but no valid filepath
    assert parse_dwd_data(
        filenames_and_files=[filename],
        prefer_local=True,
        folder="wrong/folder/name",
        write_file=False
    ).empty

    rmtree(Path(Path(__file__).parent.absolute() / "dwd_data"))

    # To ensure files are deleted with the above execution
    assert True
