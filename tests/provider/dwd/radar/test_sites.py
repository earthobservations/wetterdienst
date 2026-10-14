# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for radar sites."""

import polars as pl

from wetterdienst.provider.dwd.radar.api import DwdRadarSites
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite, DwdRadarSitesGenerator


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


def test_radar_sites_generator_shape_table() -> None:
    """Test the generator turns the table as tabula reads the DWD PDF into one row per site."""
    n = None
    # the PDF's 8 header lines, then per site: latitude line, name/ids/elevation line, longitude line;
    # every column is text (the header lines sit in them), and the decimal sign is a comma or a dot
    rows = [
        (n, n, n, n, n, "Gauss-Krüger", n),
        (n, n, n, "geographische", "geographische", "(Ellipsoid Bessel,", "Antennenhöhe"),
        ("Name des", n, n, n, n, n, n),
        (n, "Kürzel", "WMO-Nr.", "Koordinaten", "Koordinaten", "Datum Potsdam,", "(gerundet)"),
        ("Radarstandortes", n, n, n, n, n, n),
        (n, n, n, "WGS 84 (B/L)", "WGS 84 (B/L)", "Zentralpunkt", "[müNN]"),
        (n, n, n, n, n, "Rauenberg;", n),
        (n, n, n, n, n, "R/H-Wert)", n),
        (n, n, n, "53° 33‘ 50,44‘‘N", "53,564011N", "2549620,01", n),  # noqa: RUF001 (as the PDF prints it)
        ("ASR Borkum", "ASB", "10103", n, n, n, "36"),
        (n, n, n, "6° 44’ 53,85‘‘E", "6.748292E", "5937210,01", n),  # noqa: RUF001
        (n, n, n, "54° 00' 15,8''N", "54,004381N", "3568712,16", n),
        ("Boostedt", "BOO", "10132", n, n, n, "125"),
        (n, n, n, "10° 02' 48,8''E", "10,046899E", "5986471,67", n),
    ]
    raw = pl.DataFrame(
        rows,
        schema={
            "a": pl.String,
            "b": pl.String,
            "c": pl.String,
            "d": pl.String,
            "e": pl.String,
            "f": pl.String,
            "g": pl.String,
        },
        orient="row",
    )

    sites = DwdRadarSitesGenerator.shape_table(raw)

    assert sites.to_dicts() == [
        {
            "name": "ASR Borkum",
            "dwd_id": "ASB",
            "wmo_id": 10103,
            "latitude": 53.564011,
            "elevation": 36,
            "longitude": 6.748292,
        },
        {
            "name": "Boostedt",
            "dwd_id": "BOO",
            "wmo_id": 10132,
            "latitude": 54.004381,
            "elevation": 125,
            "longitude": 10.046899,
        },
    ]
