from io import BytesIO
from datetime import datetime
from pathlib import Path

import pytest

from wetterdienst.data_collection import _collect_radolan_data
from wetterdienst.api import DWDRadolanRequest
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_collect_radolan_data():
    with Path(FIXTURES_DIR, "radolan_hourly_201908080050").open("rb") as f:
        radolan_hourly = BytesIO(f.read())

    radolan_hourly_test = _collect_radolan_data(
        date_times=[datetime(year=2019, month=8, day=8, hour=0, minute=50)],
        time_resolution=TimeResolution.HOURLY,
    )[0][1]

    assert radolan_hourly.getvalue() == radolan_hourly_test.getvalue()

    with Path(FIXTURES_DIR, "radolan_daily_201908080050").open("rb") as f:
        radolan_daily = BytesIO(f.read())

    radolan_daily_test = _collect_radolan_data(
        date_times=[datetime(year=2019, month=8, day=8, hour=0, minute=50)],
        time_resolution=TimeResolution.DAILY,
    )[0][1]

    assert radolan_daily.getvalue() == radolan_daily_test.getvalue()


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

    print(request.date_times)

    with Path(FIXTURES_DIR, "radolan_hourly_201908080050").open("rb") as f:
        radolan_hourly = BytesIO(f.read())

    radolan_hourly_test = next(request.collect_data())[1]

    assert radolan_hourly.getvalue() == radolan_hourly_test.getvalue()
