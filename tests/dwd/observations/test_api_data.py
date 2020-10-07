from io import StringIO
from pathlib import Path

import pytest
import pandas as pd
from pandas._testing import assert_frame_equal

from wetterdienst.dwd.metadata import (
    TimeResolution,
    Parameter,
    PeriodType,
)
from wetterdienst.dwd.metadata.column_map import create_humanized_column_names_mapping
from wetterdienst.dwd.observations.api import DWDObservationData
from wetterdienst.dwd.observations.store import StorageAdapter
from wetterdienst.exceptions import StartDateEndDateError


HERE = Path(__file__).parent

# Set filename for mock
filename = "tageswerte_KL_00001_19370101_19860630_hist.zip"

# Loading test data
TEST_FILE = pd.read_json(HERE / "FIXED_STATIONDATA.JSON")

# Prepare csv for regular "downloading" test
CSV_FILE = StringIO()
TEST_FILE.to_csv(CSV_FILE, sep=";", index=False)
CSV_FILE.seek(0)


def test_dwd_observation_data():
    assert DWDObservationData(
        station_ids=[1],
        parameter="kl",
        time_resolution="daily",
        period_type=["recent", "historical"],
    ) == [
        [1],
        [Parameter.CLIMATE_SUMMARY],
        TimeResolution.DAILY,
        [PeriodType.HISTORICAL, PeriodType.RECENT],
        None,
        None,
    ]

    assert DWDObservationData(
        station_ids=[1],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL,
    ) == [
        [1],
        [Parameter.CLIMATE_SUMMARY],
        TimeResolution.DAILY,
        [PeriodType.HISTORICAL],
        None,
        None,
    ]

    # station id
    with pytest.raises(ValueError):
        DWDObservationData(
            station_ids="test",
            parameter=Parameter.CLIMATE_SUMMARY,
            period_type=PeriodType.HISTORICAL,
            time_resolution=TimeResolution.DAILY,
        )

    # time input
    assert DWDObservationData(
        station_ids=[1],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        start_date="1971-01-01",
    ) == [
        [1],
        [Parameter.CLIMATE_SUMMARY],
        TimeResolution.DAILY,
        [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
        pd.Timestamp("1971-01-01"),
        pd.Timestamp("1971-01-01"),
    ]

    assert DWDObservationData(
        station_ids=[1],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        end_date="1971-01-01",
    ) == [
        [1],
        [Parameter.CLIMATE_SUMMARY],
        TimeResolution.DAILY,
        [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
        pd.Timestamp("1971-01-01"),
        pd.Timestamp("1971-01-01"),
    ]

    assert DWDObservationData(
        station_ids=[1],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL,
        start_date="1971-01-01",
    ) == [
        [1],
        [Parameter.CLIMATE_SUMMARY],
        TimeResolution.DAILY,
        [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
        pd.Timestamp("1971-01-01"),
        pd.Timestamp("1971-01-01"),
    ]

    with pytest.raises(StartDateEndDateError):
        DWDObservationData(
            station_ids=[1],
            parameter=Parameter.CLIMATE_SUMMARY,
            time_resolution=TimeResolution.DAILY,
            start_date="1971-01-01",
            end_date="1951-01-01",
        )


def test_observation_data_storing():
    """
    1. Scenario
    This scenario makes sure we take fresh data and write it to the given folder, thus
    we can run just another test afterwards as no old data is used
    """
    storage = StorageAdapter(persist=True).hdf5(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL
    )

    storage.invalidate()

    dwd_obs_data = DWDObservationData(
        station_ids=1,
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL,
        storage=StorageAdapter(persist=True),
    )
    df = dwd_obs_data.collect_safe()

    df_stored = dwd_obs_data.collect_safe()

    assert_frame_equal(df, df_stored, check_column_type=False)

    storage.invalidate()

    assert True


def test_create_humanized_column_names_mapping():
    """ Test for function to create a mapping to humanized column names """
    hcnm = create_humanized_column_names_mapping(
        TimeResolution.DAILY, Parameter.CLIMATE_SUMMARY
    )

    assert hcnm == {
        "QN_3": "QUALITY_WIND",
        "FX": "WIND_GUST_MAX",
        "FM": "WIND_VELOCITY",
        "QN_4": "QUALITY_GENERAL",
        "RSK": "PRECIPITATION_HEIGHT",
        "RSKF": "PRECIPITATION_FORM",
        "SDK": "SUNSHINE_DURATION",
        "SHK_TAG": "SNOW_DEPTH",
        "NM": "CLOUD_COVERAGE_TOTAL",
        "VPM": "PRESSURE_VAPOR",
        "PM": "PRESSURE_AIR",
        "TMK": "TEMPERATURE_AIR_200",
        "UPM": "HUMIDITY",
        "TXK": "TEMPERATURE_AIR_MAX_200",
        "TNK": "TEMPERATURE_AIR_MIN_200",
        "TGK": "TEMPERATURE_AIR_MIN_005",
    }


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
            "ELEMENT": [
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

    assert_frame_equal(df.dwd.tidy_up_data(), df_tidy)
