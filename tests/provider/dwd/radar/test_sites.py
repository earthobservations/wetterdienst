# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.provider.dwd.radar.api import DwdRadarSites
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite


def test_radar_sites_enum():
    assert len(DwdRadarSite) == 17
    assert DwdRadarSite.ASB.value == "asb"
    assert DwdRadarSite.UMD.value == "umd"


def test_radar_sites_data_all():
    dwd_radar_sites = DwdRadarSites().all()

    assert len(dwd_radar_sites) == 20


def test_radar_sites_data_single():
    site_asb = DwdRadarSites().by_odim_code("ASB")

    assert site_asb["location"] == "Isle of Borkum"
