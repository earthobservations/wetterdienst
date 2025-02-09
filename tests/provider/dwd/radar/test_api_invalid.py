# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for invalid radar API requests."""

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from wetterdienst import Settings
from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.provider.dwd.radar import DwdRadarParameter, DwdRadarValues
from wetterdienst.provider.dwd.radar.metadata import (
    DwdRadarDataFormat,
    DwdRadarDate,
    DwdRadarPeriod,
    DwdRadarResolution,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite


def test_radar_request_site_historic_pe_wrong_parameters(default_settings: Settings) -> None:
    """Verify acquisition of radar/site/PE_ECHO_TOP data croaks when omitting RadarDataFormat."""
    request = DwdRadarValues(
        parameter=DwdRadarParameter.PE_ECHO_TOP,
        site=DwdRadarSite.BOO,
        start_date=dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None),
        settings=default_settings,
    )
    with pytest.raises(ValueError, match="Argument 'format' is missing"):
        next(request.query())


def test_radar_request_site_historic_pe_future(
    default_settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that ``DWDRadarRequest`` will properly emit log messages when hitting empty results.

    This time for PE_ECHO_TOP data.
    """
    request = DwdRadarValues(
        parameter=DwdRadarParameter.PE_ECHO_TOP,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.BUFR,
        start_date="2099-01-01 00:00:00",
        settings=default_settings,
    )
    results = list(request.query())
    assert results == []

    assert "WARNING" in caplog.text
    assert "No radar file found" in caplog.text


def test_radar_request_site_latest_sweep_pcp_v_hdf5(default_settings: Settings) -> None:
    """Verify requesting latest HDF5 data croaks."""
    with pytest.raises(ValueError, match="HDF5 data has no '-latest-' files"):
        DwdRadarValues(
            parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
            site=DwdRadarSite.BOO,
            fmt=DwdRadarDataFormat.HDF5,
            start_date=DwdRadarDate.LATEST,
            settings=default_settings,
        )


def test_radar_request_site_latest_sweep_pcp_v_hdf5_wrong_parameters(default_settings: Settings) -> None:
    """Verify requesting HDF5 data without RadarDataFormat croaks."""
    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        site=DwdRadarSite.BOO,
        start_date=DwdRadarDate.CURRENT,
        settings=default_settings,
    )
    with pytest.raises(ValueError, match="Argument 'format' is missing"):
        list(request.query())


def test_radar_request_site_without_site(default_settings: Settings) -> None:
    """Verify requesting site data without site croaks."""
    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=DwdRadarDate.LATEST,
        settings=default_settings,
    )
    with pytest.raises(ValueError, match="Argument 'site' is missing"):
        list(request.query())


def test_radar_request_hdf5_without_subset(default_settings: Settings) -> None:
    """Verify requesting HDF5 data without "subset" croaks."""
    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        start_date=DwdRadarDate.MOST_RECENT,
        settings=default_settings,
    )
    with pytest.raises(ValueError, match="Argument 'subset' is missing"):
        list(request.query())


@pytest.mark.remote
@pytest.mark.parametrize(
    "time_resolution",
    [
        DwdRadarResolution.DAILY,
        DwdRadarResolution.HOURLY,
    ],
)
def test_radar_request_radolan_cdc_latest(time_resolution: DwdRadarResolution, default_settings: Settings) -> None:
    """Verify requesting latest RADOLAN_CDC croaks."""
    with pytest.raises(ValueError, match="RADOLAN_CDC data has no '-latest-' files"):
        DwdRadarValues(
            parameter=DwdRadarParameter.RADOLAN_CDC,
            resolution=time_resolution,
            start_date=DwdRadarDate.LATEST,
            settings=default_settings,
        )


def test_radar_request_radolan_cdc_invalid_time_resolution(default_settings: Settings) -> None:
    """Verify requesting 1-minute RADOLAN_CDC croaks."""
    with pytest.raises(InvalidEnumerationError):
        DwdRadarValues(
            parameter=DwdRadarParameter.RADOLAN_CDC,
            resolution="minute_1",
            period=DwdRadarPeriod.RECENT,
            start_date="2019-08-08 00:50:00",
            settings=default_settings,
        )


@pytest.mark.remote
def test_radar_request_radolan_cdc_future(default_settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    """Verify that ``DWDRadarRequest`` will properly emit log messages when hitting empty results.

    This time for RADOLAN_CDC data.
    """
    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution="daily",
        period=DwdRadarPeriod.RECENT,
        start_date="2099-01-01 00:50:00",
        settings=default_settings,
    )

    results = list(request.query())
    assert results == []

    assert "WARNING" in caplog.text
    assert "No radar file found" in caplog.text
