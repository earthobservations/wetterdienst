""" Tests for data_collection """
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest
from mock import MagicMock, patch

from wetterdienst.dwd.observations import DWDObservationParameterSet
from wetterdienst.dwd.observations.access import collect_climate_observations_data
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution

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
        station_id="01048",
        parameter_set=DWDObservationParameterSet.CLIMATE_SUMMARY,
        resolution=Resolution.DAILY,
        period=Period.RECENT,
    ).empty


@pytest.mark.remote
def test_collect_daily_vanilla():
    """ Test for data collection with real data """

    data = collect_climate_observations_data(
        station_id="01048",
        parameter_set=DWDObservationParameterSet.CLIMATE_SUMMARY,
        resolution=Resolution.DAILY,
        period=Period.RECENT,
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
        station_id="01048",
        parameter_set=DWDObservationParameterSet.TEMPERATURE_AIR,
        resolution=Resolution.HOURLY,
        period=Period.RECENT,
    )

    assert list(data.columns.values) == [
        "STATION_ID",
        "DATE",
        "QN_9",
        "TT_TU",
        "RF_TU",
    ]
