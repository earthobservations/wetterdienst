""" Tests for data_collection """
import pytest
from pathlib import Path
from io import StringIO

import pandas as pd
from mock import MagicMock, patch

from wetterdienst.dwd.observations.access import (
    collect_climate_observations_data,
)
from wetterdienst.dwd.observations.metadata import (
    DWDObsParameterSet,
    DWDObsTimeResolution,
    DWDObsPeriodType,
)

HERE = Path(__file__).parent

# Set filename for mock
filename = "tageswerte_KL_00001_19370101_19860630_hist.zip"

# Loading test data
TEST_FILE = pd.read_json(HERE / "FIXED_STATIONDATA.JSON")

# Prepare csv for regular "downloading" test
CSV_FILE = StringIO()
TEST_FILE.to_csv(CSV_FILE, sep=";", index=False)
CSV_FILE.seek(0)


@patch(
    "wetterdienst.dwd.observations.access.create_file_list_for_climate_observations",
    MagicMock(return_value=[]),
)
def test_collect_dwd_data_empty():
    """ Test for data collection with no available data """

    assert collect_climate_observations_data(
        station_id=1048,
        parameter_set=DWDObsParameterSet.CLIMATE_SUMMARY,
        time_resolution=DWDObsTimeResolution.DAILY,
        period_type=DWDObsPeriodType.RECENT,
    ).empty


@pytest.mark.remote
def test_collect_daily_vanilla():
    """ Test for data collection with real data """

    data = collect_climate_observations_data(
        station_id=1048,
        parameter_set=DWDObsParameterSet.CLIMATE_SUMMARY,
        time_resolution=DWDObsTimeResolution.DAILY,
        period_type=DWDObsPeriodType.RECENT,
    )

    assert list(data.columns.values) == [
        "STATION_ID",
        "DATE",
        "QN_3",
        "FX",
        "FM",
        "QN_4",
        "RSK",
        "RSKF",
        "SDK",
        "SHK_TAG",
        "NM",
        "VPM",
        "PM",
        "TMK",
        "UPM",
        "TXK",
        "TNK",
        "TGK",
    ]


@pytest.mark.remote
def test_collect_hourly_vanilla():
    """ Test for data collection with real data """

    data = collect_climate_observations_data(
        station_id=1048,
        parameter_set=DWDObsParameterSet.TEMPERATURE_AIR,
        time_resolution=DWDObsTimeResolution.HOURLY,
        period_type=DWDObsPeriodType.RECENT,
    )

    assert list(data.columns.values) == [
        "STATION_ID",
        "DATE",
        "QN_9",
        "TT_TU",
        "RF_TU",
    ]
