import pytest
from io import StringIO
from pathlib import Path
import pandas as pd
import mock

from python_dwd.additionals.helpers import create_stationdata_dtype_mapping
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.enumerations.period_type_enumeration import PeriodType

from python_dwd.data_storing import store_dwd_data, restore_dwd_data, _build_local_store_key

fixtures_dir = Path(__file__, "../").resolve().absolute() / "fixtures"

# Setting parameters for tests
station_id = 1
parameter = Parameter.CLIMATE_SUMMARY
time_resolution = TimeResolution.DAILY
period_type = PeriodType.HISTORICAL
parallel_download = False
create_new_filelist = False

# Set filename for mock
filename = "tageswerte_KL_00001_19370101_19860630_hist.zip"

# Loading test data
file = pd.read_json(fixtures_dir / "FIXED_STATIONDATA.JSON")
file = file.astype(create_stationdata_dtype_mapping(file.columns))

# Prepare csv for regular "downloading" test
csv_file = StringIO()
file.to_csv(csv_file, sep=";")
csv_file.seek(0)


def test_build_local_store_key():
    """ Tests for function _build_local_store_key """
    assert _build_local_store_key(
        station_id=1,
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL
    ) == "kl/daily/historical/station_id_1"

    assert _build_local_store_key(
        station_id="00001",
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL
    ) == "kl/daily/historical/station_id_1"

    with pytest.raises(ValueError):
        _build_local_store_key(
            station_id="abc",
            parameter=Parameter.CLIMATE_SUMMARY,
            time_resolution=TimeResolution.DAILY,
            period_type=PeriodType.HISTORICAL
        )

    with pytest.raises(AttributeError):
        _build_local_store_key(
            station_id=1,
            parameter=Parameter.NO_REAL_PARAMETER,
            time_resolution=TimeResolution.DAILY,
            period_type=PeriodType.HISTORICAL
        )


@mock.patch(
    "pandas.read_hdf",
    mock.MagicMock(return_value=file)
)
def test_restore_dwd_data():
    """ Tests for restore_dwd_data """
    success, station_data = restore_dwd_data(
        station_id=station_id,
        parameter=parameter,
        time_resolution=time_resolution,
        period_type=period_type,
        folder=""
    )

    assert success and station_data.equals(file)
