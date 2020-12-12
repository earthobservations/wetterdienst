from io import StringIO
from pathlib import Path
from datetime import datetime

import pytest
import pandas as pd
from pandas._testing import assert_frame_equal

from wetterdienst.dwd.observations import (
    DWDObservationResolution,
    DWDObservationParameterSet,
    DWDObservationPeriod,
)
from wetterdienst.dwd.observations.api import DWDObservationData
from wetterdienst.dwd.observations.metadata.parameter import (
    DWDObservationParameter,
    DWDObservationParameterSetStructure,
)
from wetterdienst.dwd.observations.store import StorageAdapter
from wetterdienst.exceptions import StartDateEndDateError, NoParametersFound

HERE = Path(__file__).parent

# Set filename for mock
filename = "tageswerte_KL_00001_19370101_19860630_hist.zip"

# Loading test data
TEST_FILE = pd.read_json(HERE / "FIXED_STATIONDATA.JSON")

# Prepare csv for regular "downloading" test
CSV_FILE = StringIO()
TEST_FILE.to_csv(CSV_FILE, sep=";", index=False)
CSV_FILE.seek(0)


def test_dwd_observation_data_parameter_set():
    request = DWDObservationData(
        station_ids=[1],
        parameters=["kl"],
        resolution="daily",
        periods=["recent", "historical"],
    )

    assert request == DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DWDObservationResolution.DAILY,
        periods=[DWDObservationPeriod.HISTORICAL, DWDObservationPeriod.RECENT],
        start_date=None,
        end_date=None,
    )

    assert request.parameters == [
        (
            DWDObservationParameterSet.CLIMATE_SUMMARY,
            DWDObservationParameterSet.CLIMATE_SUMMARY,
        )
    ]

    request = DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DWDObservationResolution.DAILY,
        periods=[DWDObservationPeriod.HISTORICAL, DWDObservationPeriod.RECENT],
    )

    assert request == DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DWDObservationResolution.DAILY,
        periods=[DWDObservationPeriod.HISTORICAL, DWDObservationPeriod.RECENT],
        start_date=None,
        end_date=None,
    )

    # station id
    with pytest.raises(ValueError):
        DWDObservationData(
            station_ids=["test"],
            parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
            periods=[DWDObservationPeriod.HISTORICAL],
            resolution=DWDObservationResolution.DAILY,
        )


def test_dwd_observation_data_parameter():
    request = DWDObservationData(
        station_ids=[1],
        parameters=["precipitation_height"],
        resolution="daily",
        periods=["recent", "historical"],
    )

    assert request == DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameter.DAILY.PRECIPITATION_HEIGHT],
        resolution=DWDObservationResolution.DAILY,
        periods=[DWDObservationPeriod.HISTORICAL, DWDObservationPeriod.RECENT],
        start_date=None,
        end_date=None,
    )

    assert request.parameters == [
        (
            DWDObservationParameterSetStructure.DAILY.CLIMATE_SUMMARY.PRECIPITATION_HEIGHT,  # Noqa: E501, B950
            DWDObservationParameterSet.CLIMATE_SUMMARY,
        )
    ]

    with pytest.raises(NoParametersFound):
        DWDObservationData(
            station_ids=[1],
            parameters=["abc"],
            resolution=DWDObservationResolution.DAILY,
            start_date="1971-01-01",
            end_date="1951-01-01",
        )


def test_dwd_observation_data_time_input():
    # time input
    request = DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DWDObservationResolution.DAILY,
        start_date="1971-01-01",
    )

    assert request == DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DWDObservationResolution.DAILY,
        periods=[
            DWDObservationPeriod.HISTORICAL,
        ],
        start_date=pd.Timestamp("1971-01-01"),
        end_date=pd.Timestamp("1971-01-01"),
    )

    request = DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DWDObservationResolution.DAILY,
        periods=[DWDObservationPeriod.HISTORICAL],
        end_date="1971-01-01",
    )

    assert request == DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DWDObservationResolution.DAILY,
        periods=[
            DWDObservationPeriod.HISTORICAL,
        ],
        start_date=pd.Timestamp("1971-01-01"),
        end_date=pd.Timestamp("1971-01-01"),
    )

    with pytest.raises(StartDateEndDateError):
        DWDObservationData(
            station_ids=[1],
            parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
            resolution=DWDObservationResolution.DAILY,
            start_date="1971-01-01",
            end_date="1951-01-01",
        )


def test_dwd_observation_data_dynamic_period():
    # Historical period expected
    request = DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DWDObservationResolution.DAILY,
        start_date="1971-01-01",
    )

    assert request.periods == [
        DWDObservationPeriod.HISTORICAL,
    ]

    # Historical and recent period expected
    request = DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DWDObservationResolution.DAILY,
        start_date="1971-01-01",
        end_date=pd.Timestamp(datetime.utcnow()) - pd.Timedelta(days=400),
    )

    assert request.periods == [
        DWDObservationPeriod.HISTORICAL,
        DWDObservationPeriod.RECENT,
    ]

    # Historical, recent and now period expected
    request = DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DWDObservationResolution.DAILY,
        start_date="1971-01-01",
        end_date=pd.Timestamp(datetime.utcnow()),
    )

    assert request.periods == [
        DWDObservationPeriod.HISTORICAL,
        DWDObservationPeriod.RECENT,
        DWDObservationPeriod.NOW,
    ]

    # !!!Recent and now period cant be tested dynamically
    # TODO: add test with mocked datetime here

    # Now period
    request = DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DWDObservationResolution.DAILY,
        start_date=pd.Timestamp(datetime.utcnow()) - pd.Timedelta(hours=2),
    )
    assert DWDObservationPeriod.NOW in request.periods

    # No period (for example in future)
    request = DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DWDObservationResolution.DAILY,
        start_date=pd.Timestamp(datetime.utcnow()) + pd.Timedelta(days=720),
    )

    assert request.periods == []


def test_observation_data_storing():
    """
    1. Scenario
    This scenario makes sure we take fresh data and write it to the given folder, thus
    we can run just another test afterwards as no old data is used
    """
    storage = StorageAdapter(persist=True).hdf5(
        DWDObservationParameterSet.CLIMATE_SUMMARY,
        DWDObservationResolution.DAILY,
        DWDObservationPeriod.HISTORICAL,
    )

    storage.invalidate()

    dwd_obs_data = DWDObservationData(
        station_ids=[1],
        parameters=[DWDObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DWDObservationResolution.DAILY,
        periods=[DWDObservationPeriod.HISTORICAL],
        storage=StorageAdapter(persist=True),
    )
    df = dwd_obs_data.collect_safe()

    df_stored = dwd_obs_data.collect_safe()

    assert_frame_equal(df, df_stored, check_column_type=False)

    storage.invalidate()

    assert True


def test_create_humanized_column_names_mapping():
    """ Test for function to create a mapping to humanized column names """
    kl_daily_hcnm = {
        # "QN_3": "QUALITY_WIND",
        "FX": "WIND_GUST_MAX",
        "FM": "WIND_SPEED",
        # "QN_4": "QUALITY_GENERAL",
        "RSK": "PRECIPITATION_HEIGHT",
        "RSKF": "PRECIPITATION_FORM",
        "SDK": "SUNSHINE_DURATION",
        "SHK_TAG": "SNOW_DEPTH",
        "NM": "CLOUD_COVER_TOTAL",
        "VPM": "PRESSURE_VAPOR",
        "PM": "PRESSURE_AIR",
        "TMK": "TEMPERATURE_AIR_200",
        "UPM": "HUMIDITY",
        "TXK": "TEMPERATURE_AIR_MAX_200",
        "TNK": "TEMPERATURE_AIR_MIN_200",
        "TGK": "TEMPERATURE_AIR_MIN_005",
    }
    hcnm = DWDObservationData(
        [0],
        [DWDObservationParameterSet.CLIMATE_SUMMARY],
        DWDObservationResolution.DAILY,
        [DWDObservationPeriod.RECENT],
    )._create_humanized_parameters_mapping()

    assert set(kl_daily_hcnm.items()).issubset(set(hcnm.items()))


def test_tidy_up_data():
    """ Test for function to tidy data"""
    df = pd.DataFrame(
        {
            "STATION_ID": [1048],
            "DATE": [pd.Timestamp("2019-01-23 00:00:00")],
            "QN_3": [10],
            "FX": [11.8],
            "FM": [5.8],
            "QN_4": [3],
            "RSK": [0.0],
            "RSKF": [0.0],
            "SDK": [7.1],
            "SHK_TAG": [0.0],
            "NM": [2.3],
            "VPM": [3.2],
            "PM": [975.4],
            "TMK": [-5.5],
            "UPM": [79.17],
            "TXK": [-1.7],
            "TNK": [-7.9],
            "TGK": [-11.4],
        }
    )

    df_tidy = pd.DataFrame(
        {
            "STATION_ID": [1048] * 14,
            "DATE": [pd.Timestamp("2019-01-23 00:00:00")] * 14,
            "PARAMETER": [
                "FX",
                "FM",
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
            ],
            "VALUE": [
                11.8,
                5.8,
                0.0,
                0.0,
                7.1,
                0.0,
                2.3,
                3.2,
                975.4,
                -5.5,
                79.17,
                -1.7,
                -7.9,
                -11.4,
            ],
            "QUALITY": pd.Series(
                [10, 10, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], dtype=pd.Int64Dtype()
            ),
        }
    )

    df_tidy = df_tidy.astype(
        {
            "STATION_ID": "category",
            "PARAMETER": "category",
            "QUALITY": "category",
        }
    )

    assert_frame_equal(df.dwd.tidy_up_data(), df_tidy)
