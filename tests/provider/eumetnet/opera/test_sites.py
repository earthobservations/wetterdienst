# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites


def test_radar_sites_sizes():
    ors = OperaRadarSites()

    assert len(ors.all()) == 205

    assert len(ors.to_dict()) == 197


def test_radar_sites_by_odimcode():
    ors = OperaRadarSites()

    assert ors.by_odim_code("ukdea")["location"] == "Dean Hill"

    assert ors.by_odim_code("ASB")["location"] == "Isle of Borkum"
    assert ors.by_odim_code("EMD")["location"] == "Emden"
    assert ors.by_odim_code("UMD")["location"] == "Ummendorf"

    with pytest.raises(ValueError) as exec_info:
        ors.by_odim_code("foobar")
    assert exec_info.match("ODIM code must be three or five letters")

    with pytest.raises(KeyError) as exec_info:
        ors.by_odim_code("foo")
    assert exec_info.match("'Radar site not found'")


def test_radar_sites_by_wmocode():
    ors = OperaRadarSites()

    assert ors.by_wmo_code(3859)["location"] == "Dean Hill"
    assert ors.by_wmo_code(10103)["location"] == "Isle of Borkum"


def test_radar_sites_by_countryname():
    ors = OperaRadarSites()

    sites_uk = ors.by_country_name(country_name="United Kingdom")
    assert len(sites_uk) == 16

    with pytest.raises(KeyError) as exec_info:
        ors.by_country_name(country_name="foo")
    assert exec_info.match("'No radar sites for this country'")
