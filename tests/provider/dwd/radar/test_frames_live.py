# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frames of DWD's RV composite, read from opendata.dwd.de (needs the internet), GH-3788."""

from __future__ import annotations

import datetime as dt

import pytest

from wetterdienst import Settings
from wetterdienst.provider.dwd.radar import rv
from wetterdienst.provider.dwd.radar.frames import DwdRadarFrames, forget_everything
from wetterdienst.util.response_warnings import begin_response


@pytest.fixture
def service(tmp_path_factory: pytest.TempPathFactory) -> DwdRadarFrames:
    """Give the service, with nothing held of an earlier test."""
    forget_everything()
    begin_response()
    return DwdRadarFrames(Settings(cache_dir=tmp_path_factory.mktemp("cache"), cache_disable=True))


@pytest.mark.remote
def test_the_loop_of_the_last_hour_and_the_forecast_are_frames_of_the_grid_dwd_serves(service: DwdRadarFrames) -> None:
    """The newest run is minutes old, its analysis and a forecast frame decode on the grid the bounds are announced for.

    Whether it rains over Germany is the weather's: the frames are checked for what they are, not for rain.
    """
    listing = service.frames(history_minutes=30, forecast=True)

    assert dt.datetime.now(dt.UTC) - listing.run < dt.timedelta(hours=1)
    assert [f.kind for f in listing.frames].count("forecast") == 24
    assert listing.image == rv.image_frame()
    observed = [f for f in listing.frames if f.kind == "observation"]
    assert 2 <= len(observed) <= 7

    newest = service.frame(listing.run, listing.run)
    forecast = service.frame(listing.run + dt.timedelta(minutes=60), listing.run)

    for image in (newest, forecast):
        assert image.png.startswith(b"\x89PNG")
        assert 1_000 < len(image.png) < 200_000
        assert image.image == listing.image
    assert (newest.frame.lead_minutes, forecast.frame.lead_minutes) == (0, 60)
    # a frame drawn is the frame of the file: the time the file ends at is the time the frame is named for (`_draw`
    # raises where it is not)
    older = service.frame(observed[0].time, observed[0].run)
    assert older.frame.time == observed[0].time
