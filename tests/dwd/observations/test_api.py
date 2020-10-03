import json

import pytest
import pandas as pd

from wetterdienst import (
    discover_climate_observations,
    TimeResolution,
    Parameter,
    PeriodType,
)
from wetterdienst.dwd.observations.api import DWDObservationData
from wetterdienst.exceptions import StartDateEndDateError


def test_dwd_station_request():
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


def test_discover_climate_observations():
    assert discover_climate_observations(
        TimeResolution.DAILY, Parameter.CLIMATE_SUMMARY
    ) == json.dumps(
        {
            str(TimeResolution.DAILY): {
                str(Parameter.CLIMATE_SUMMARY): [
                    str(PeriodType.HISTORICAL),
                    str(PeriodType.RECENT),
                ]
            }
        },
        indent=4,
    )
