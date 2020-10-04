import pytest
import pandas as pd

from wetterdienst import (
    TimeResolution,
    Parameter,
    PeriodType,
)
from wetterdienst.dwd.observations.api import DWDObservationData
from wetterdienst.exceptions import StartDateEndDateError


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
        [PeriodType.HISTORICAL, PeriodType.RECENT],  # check order
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
