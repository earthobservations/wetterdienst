import pytest
import pandas as pd

from wetterdienst.api import DWDStationRequest
from wetterdienst.exceptions import StartDateEndDateError
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution


def test_dwd_station_request():
    assert DWDStationRequest(
        station_ids=[1],
        parameter="kl",
        time_resolution="daily",
        period_type="historical",
    ) == [
        [1],
        [Parameter.CLIMATE_SUMMARY],
        TimeResolution.DAILY,
        [PeriodType.HISTORICAL],
        None,
        None,
    ]

    assert DWDStationRequest(
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


def test_station_id():
    with pytest.raises(ValueError):
        DWDStationRequest(
            station_ids="test",
            parameter=Parameter.CLIMATE_SUMMARY,
            period_type=PeriodType.HISTORICAL,
            time_resolution=TimeResolution.DAILY,
        )


def test_time_input():
    assert DWDStationRequest(
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

    assert DWDStationRequest(
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

    assert DWDStationRequest(
        station_ids=[1],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL,
        start_date="1971-01-01",
    ) == [
        [1],
        [Parameter.CLIMATE_SUMMARY],
        TimeResolution.DAILY,
        [PeriodType.HISTORICAL],
        None,
        None,
    ]

    with pytest.raises(StartDateEndDateError):
        DWDStationRequest(
            station_ids=[1],
            parameter=Parameter.CLIMATE_SUMMARY,
            time_resolution=TimeResolution.DAILY,
            start_date="1971-01-01",
            end_date="1951-01-01",
        )
