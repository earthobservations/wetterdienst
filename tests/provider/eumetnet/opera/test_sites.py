# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites


def test_radar_sites_sizes():

    ors = OperaRadarSites()

    assert len(ors.all()) == 205

    assert len(ors.asdict()) == 197


def test_radar_sites_by_odimcode():

    ors = OperaRadarSites()

    assert ors.by_odimcode("ukdea")["location"] == "Dean Hill"

    assert ors.by_odimcode("ASB")["location"] == "Isle of Borkum"
    assert ors.by_odimcode("EMD")["location"] == "Emden"
    assert ors.by_odimcode("UMD")["location"] == "Ummendorf"

    with pytest.raises(ValueError) as ex:
        ors.by_odimcode("foobar")
    assert ex.errisinstance(ValueError)
    assert ex.match("ODIM code must be three or five letters")

    with pytest.raises(KeyError) as ex:
        ors.by_odimcode("foo")
    assert ex.errisinstance(KeyError)
    assert ex.match("'Radar site not found'")


def test_radar_sites_by_wmocode():

    ors = OperaRadarSites()

    assert ors.by_wmocode(3859)["location"] == "Dean Hill"
    assert ors.by_wmocode(10103)["location"] == "Isle of Borkum"


def test_radar_sites_by_countryname():

    ors = OperaRadarSites()

    sites_uk = ors.by_countryname(name="United Kingdom")
    assert len(sites_uk) == 16

    with pytest.raises(KeyError) as ex:
        ors.by_countryname(name="foo")
    assert ex.errisinstance(KeyError)
    assert ex.match("'No radar sites for this country'")
