from io import BytesIO
from datetime import datetime
from pathlib import Path

from wetterdienst.radolan import collect_radolan_data
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_collect_radolan_data():
    with Path(FIXTURES_DIR, "radolan_hourly_201908080050").open("rb") as f:
        radolan_hourly = BytesIO(f.read())

    radolan_hourly_test = collect_radolan_data(
        date_times=[datetime(year=2019, month=8, day=8, hour=0, minute=50)],
        time_resolution=TimeResolution.HOURLY
    )[0][1]

    assert radolan_hourly.getvalue() == radolan_hourly_test.getvalue()

    with Path(FIXTURES_DIR, "radolan_daily_201908080050").open("rb") as f:
        radolan_daily = BytesIO(f.read())

    radolan_daily_test = collect_radolan_data(
        date_times=[datetime(year=2019, month=8, day=8, hour=0, minute=50)],
        time_resolution=TimeResolution.DAILY
    )[0][1]

    assert radolan_daily.getvalue() == radolan_daily_test.getvalue()
