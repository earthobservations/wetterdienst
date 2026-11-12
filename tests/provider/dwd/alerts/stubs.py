# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A real multi-language CAP message of DWD, and the snapshot that serves it, for the tests of GH-3801."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

#: A message of the `mul` product (district basis, one fog warning for Kreis Wittenberg, 2026-11-05) as DWD published
#: it: eight `<info>` blocks, `de-DE` first and then `en`, `fr`, `es`, `ar`, `ru`, `tr`, `pl`, whose times, codes,
#: parameter and area are the same and whose event, headline, description and instruction are each language's. Its
#: wording is DWD's; only the polygon of the one area is cut to 5 of its 124 points (closed), the same in each block.
CAP_MUL: bytes = (Path(__file__).parent / "files" / "cap_mul_fog.xml").read_bytes()

_FILES = Path(__file__).parent / "files"

#: Real messages of the `en` products of 2026-11-12, as DWD published them (a gale warning day on the coast of the North
#: Sea and the Baltic), for the tests of the place filter (GH-4019). Nothing is cut. The warncells and names are the
#: areas a warning is for, the polygons its event area:
#:
#: - the community product, wind gusts for 150 communes, one polygon, `Stadt Kiel` (`801002000`) among them
CAP_COMMUNITY_KIEL: bytes = (_FILES / "cap_community_wind_kiel.xml").read_bytes()
#: - the community product, wind gusts for 27 communes of the Ostfriesland coast, 13 polygons, Norderney in one
CAP_COMMUNITY_NORDERNEY: bytes = (_FILES / "cap_community_wind_norderney.xml").read_bytes()
#: - the community product, a warning for the sea (`Ostfriesische Küste`, `501000001`): one area with a warn cell and no
#:   polygon, so no point is in it
CAP_COMMUNITY_SEA: bytes = (_FILES / "cap_community_sea_near_gale.xml").read_bytes()
#: - the district product, wind gusts for 5 districts, `Stadt Kiel` (`101002000`) among them
CAP_DISTRICT_KIEL: bytes = (_FILES / "cap_district_wind_kiel.xml").read_bytes()
#: - the district product, a warning for the sea around Helgoland: a polygon of the sea of 5 corners with a hole, the
#:   island, in it
CAP_DISTRICT_HELGOLAND: bytes = (_FILES / "cap_district_sea_helgoland.xml").read_bytes()

#: the languages of that message, in the order of its blocks
CAP_MUL_LANGUAGES = ["de-DE", "en", "fr", "es", "ar", "ru", "tr", "pl"]


def make_zip(*documents: bytes) -> io.BytesIO:
    """Pack CAP documents into the zip a snapshot is."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for index, document in enumerate(documents):
            archive.writestr(f"alert_{index}.xml", document)
    buffer.seek(0)
    return buffer


def serve_snapshot(monkeypatch: pytest.MonkeyPatch, *documents: bytes) -> None:
    """Make `DwdWeatherAlertRequest.query` download a snapshot of these documents, and nothing from the network."""
    from wetterdienst.util.network import File  # noqa: PLC0415

    def fake_download(*_args: object, **_kwargs: object) -> File:
        return File(url="http://x", content=make_zip(*documents), status=200)

    monkeypatch.setattr("wetterdienst.provider.dwd.alerts.api.download_file", fake_download)
