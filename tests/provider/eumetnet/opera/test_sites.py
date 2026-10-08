# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for EUMETNET OPERA radar sites."""

import pytest
from fsspec.exceptions import FSTimeoutError

from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.provider.eumetnet.opera import sites
from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites, OperaRadarSitesGenerator
from wetterdienst.util.network import File


def test_radar_sites_sizes() -> None:
    """Test radar sites number."""
    ors = OperaRadarSites()

    assert len(ors.all()) == 205

    assert len(ors.to_dict()) == 197


def test_radar_sites_by_odimcode() -> None:
    """Test radar sites by ODIM code."""
    ors = OperaRadarSites()

    assert ors.by_odim_code("ukdea")["location"] == "Dean Hill"

    assert ors.by_odim_code("ASB")["location"] == "Isle of Borkum"
    assert ors.by_odim_code("EMD")["location"] == "Emden"
    assert ors.by_odim_code("UMD")["location"] == "Ummendorf"

    with pytest.raises(ValueError, match="ODIM code must be three or five letters"):
        ors.by_odim_code("foobar")

    with pytest.raises(KeyError, match="Radar site not found"):
        ors.by_odim_code("foo")


def test_radar_sites_by_wmocode() -> None:
    """Test radar sites by WMO code."""
    ors = OperaRadarSites()

    assert ors.by_wmo_code(3859)["location"] == "Dean Hill"
    assert ors.by_wmo_code(10103)["location"] == "Isle of Borkum"


def test_radar_sites_by_countryname() -> None:
    """Test radar sites by country name."""
    ors = OperaRadarSites()

    sites_uk = ors.by_country_name(country_name="United Kingdom")
    assert len(sites_uk) == 16

    with pytest.raises(KeyError) as exec_info:
        ors.by_country_name(country_name="foo")
    assert exec_info.match("'No radar sites for this country'")


def test_radar_sites_a_failed_listing_download_names_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a listing download that timed out raises an error naming the file (GH-2507)."""
    monkeypatch.setattr(
        sites,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=FSTimeoutError(), status=408),
    )

    with pytest.raises(DownloadError, match=r"Failed to download .*OPERA_RADARS_DB\.json: FSTimeoutError") as caught:
        OperaRadarSitesGenerator().get_opera_radar_sites()
    assert isinstance(caught.value.__cause__, FSTimeoutError)


def test_radar_sites_listing_without_internet_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that being offline gives an empty listing rather than an error."""
    monkeypatch.setattr(
        sites,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=NoInternetError("offline"), status=503),
    )

    assert OperaRadarSitesGenerator().get_opera_radar_sites() == []
