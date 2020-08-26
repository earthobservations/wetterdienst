import pytest
from io import StringIO
from pathlib import Path
import pandas as pd
import mock
from shutil import rmtree

from wetterdienst.additionals.functions import coerce_field_types
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.period_type_enumeration import PeriodType

from wetterdienst.data_storing import (
    store_climate_observations,
    restore_climate_observations,
    _build_local_store_key,
)

# Create folder for storage test
test_folder = Path(Path(__file__).parent.absolute() / "dwd_data")
test_folder.mkdir(parents=True, exist_ok=True)

fixtures_dir = Path(__file__, "../").resolve().absolute() / "fixtures"

# Setting parameters for tests
station_id = 1
parameter = Parameter.CLIMATE_SUMMARY
time_resolution = TimeResolution.DAILY
period_type = PeriodType.HISTORICAL
parallel_download = False
create_new_file_index = False

# Set filename for mock
filename = "tageswerte_KL_00001_19370101_19860630_hist.zip"

# Loading test data
file = pd.read_json(fixtures_dir / "FIXED_STATIONDATA.JSON")
file = coerce_field_types(file, time_resolution)

# Prepare csv for regular "downloading" test
csv_file = StringIO()
file.to_csv(csv_file, sep=";")
csv_file.seek(0)


def test_build_local_store_key():
    """ Tests for function _build_local_store_key """
    assert (
        _build_local_store_key(
            station_id=1,
            parameter=Parameter.CLIMATE_SUMMARY,
            time_resolution=TimeResolution.DAILY,
            period_type=PeriodType.HISTORICAL,
        )
        == "kl/daily/historical/station_id_1"
    )

    assert (
        _build_local_store_key(
            station_id="00001",
            parameter=Parameter.CLIMATE_SUMMARY,
            time_resolution=TimeResolution.DAILY,
            period_type=PeriodType.HISTORICAL,
        )
        == "kl/daily/historical/station_id_1"
    )

    with pytest.raises(ValueError):
        _build_local_store_key(
            station_id="abc",
            parameter=Parameter.CLIMATE_SUMMARY,
            time_resolution=TimeResolution.DAILY,
            period_type=PeriodType.HISTORICAL,
        )

    with pytest.raises(AttributeError):
        _build_local_store_key(
            station_id=1,
            parameter=Parameter.NO_REAL_PARAMETER,
            time_resolution=TimeResolution.DAILY,
            period_type=PeriodType.HISTORICAL,
        )


@mock.patch("pandas.read_hdf", mock.MagicMock(return_value=file))
def test_store_dwd_data():
    """ Tests for restore_dwd_data """
    store_climate_observations(
        station_data=file,
        station_id=station_id,
        parameter=parameter,
        time_resolution=time_resolution,
        period_type=period_type,
        folder=test_folder,
    )

    station_data = restore_climate_observations(
        station_id=station_id,
        parameter=parameter,
        time_resolution=time_resolution,
        period_type=period_type,
        folder=test_folder,
    )

    assert station_data.equals(file)

    # Remove storage folder
    rmtree(test_folder)

    # Have to place an assert afterwards to ensure that above function is executed
    assert True
