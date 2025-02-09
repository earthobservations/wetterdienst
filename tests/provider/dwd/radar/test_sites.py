# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for radar sites."""

from wetterdienst.provider.dwd.radar.api import DwdRadarSites
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite


def test_radar_sites_enum() -> None:
    """Test radar sites enumeration."""
    assert len(DwdRadarSite) == 17
    assert DwdRadarSite.ASB.value == "asb"
    assert DwdRadarSite.UMD.value == "umd"


def test_radar_sites_data_all() -> None:
    """Test radar sites number."""
    dwd_radar_sites = DwdRadarSites().all()

    assert len(dwd_radar_sites) == 20


def test_radar_sites_data_single() -> None:
    """Test radar sites by ODIM code."""
    site_asb = DwdRadarSites().by_odim_code("ASB")

    assert site_asb["location"] == "Isle of Borkum"
