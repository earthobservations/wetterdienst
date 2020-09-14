from datetime import datetime
from io import BytesIO
from pathlib import Path

import pytest
import pandas as pd

from wetterdienst.api import DWDStationRequest, DWDRadolanRequest
from wetterdienst.exceptions import StartDateEndDateError
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_dwd_station_request():
    assert DWDStationRequest(
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

    # station id
    with pytest.raises(ValueError):
        DWDStationRequest(
            station_ids="test",
            parameter=Parameter.CLIMATE_SUMMARY,
            period_type=PeriodType.HISTORICAL,
            time_resolution=TimeResolution.DAILY,
        )

    # time input
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


@pytest.mark.remote
def test_dwd_radolan_request():
    with pytest.raises(ValueError):
        DWDRadolanRequest(
            time_resolution=TimeResolution.MINUTE_1, date_times=["2019-08-08 00:50:00"]
        )

    request = DWDRadolanRequest(
        time_resolution=TimeResolution.HOURLY, date_times=["2019-08-08 00:50:00"]
    )

    assert request == DWDRadolanRequest(
        TimeResolution.HOURLY,
        [datetime(year=2019, month=8, day=8, hour=0, minute=50, second=0)],
    )

    with Path(FIXTURES_DIR, "radolan_hourly_201908080050").open("rb") as f:
        radolan_hourly = BytesIO(f.read())

    radolan_hourly_test = next(request.collect_data())[1]

    assert radolan_hourly.getvalue() == radolan_hourly_test.getvalue()
