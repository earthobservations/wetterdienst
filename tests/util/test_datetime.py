from datetime import datetime

from wetterdienst.util.datetime import raster_minutes, round_minutes


def test_raster_50min_regular():

    tm = datetime(2010, 1, 1, 0, 56, 56)
    tm_aligned = raster_minutes(tm, 50)

    assert tm_aligned == datetime(2010, 1, 1, 0, 50)


def test_raster_50min_wrap():

    tm = datetime(2010, 1, 1, 0, 42, 42)
    tm_aligned = raster_minutes(tm, 50)

    assert tm_aligned == datetime(2009, 12, 31, 23, 50)


def test_round_5min():

    tm = datetime(2010, 1, 1, 0, 4, 42)
    tm_aligned = round_minutes(tm, 5)

    assert tm_aligned == datetime(2010, 1, 1, 0, 0)
