# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.dwd.radar import DWDRadarData
from wetterdienst.dwd.radar.sites import DWDRadarSite


def test_radar_sites_data():

    sites = DWDRadarData.get_sites()

    assert len(sites) == 18
    assert sites["ASB"]["name"] == "ASR Borkum"
    assert sites["EMD"]["name"] == "Emden"
    assert sites["UMD"]["name"] == "Ummendorf"


def test_radar_sites_enum():

    assert len(DWDRadarSite) == 18
    assert DWDRadarSite.ASB.value == "asb"
    assert DWDRadarSite.EMD.value == "emd"
    assert DWDRadarSite.UMD.value == "umd"
