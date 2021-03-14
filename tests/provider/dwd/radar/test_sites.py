# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.provider.dwd.radar import DwdRadarValues
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite


def test_radar_sites_data():

    sites = DwdRadarValues.get_sites()

    assert len(sites) == 18
    assert sites["ASB"]["name"] == "ASR Borkum"
    assert sites["EMD"]["name"] == "Emden"
    assert sites["UMD"]["name"] == "Ummendorf"


def test_radar_sites_enum():

    assert len(DwdRadarSite) == 18
    assert DwdRadarSite.ASB.value == "asb"
    assert DwdRadarSite.EMD.value == "emd"
    assert DwdRadarSite.UMD.value == "umd"
