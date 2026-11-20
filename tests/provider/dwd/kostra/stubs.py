# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
r"""Real rows of the KOSTRA-DWD-2020 tables of DWD, and what serves them in place of the download.

`files/StatRR_KOSTRA-DWD-2020_D<minutes>.csv` are the 22 tables of
https://opendata.dwd.de/climate_environment/CDC/grids_germany/return_periods/precipitation/KOSTRA/KOSTRA_DWD_2020/tab/
as DWD wrote them in December 2022 (the header and a line of the rows, byte for byte, `;`, a decimal comma, `\\n`), cut
to five of their 90,000 rows, each for every duration:

- `000000`: the north-western corner of the grid, in the North Sea off Scotland, where DWD writes its missing values
  (`-99,9` and, for the uncertainty, `-99`), as it does for 74,011 of the 90,000 cells
- `083144` (Hamburg), `105190` (Berlin), `160126` (Frankfurt am Main, the example of DWD's Anwendungshilfe) and
  `203167` (Munich), cells with values

The Anwendungshilfe works out `160126` for D = 5 min as 11.2 mm for T = 5 a and 20.5 mm for T = 100 a (373.3 and 683.3
l/(s ha), +-10 % and +-12 %), which `test_api.py` holds the stub to.

The tables are zipped here as DWD zips them, one member each.
"""

from __future__ import annotations

import datetime as dt
import io
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from wetterdienst.provider.dwd.kostra.metadata import DURATIONS
from wetterdienst.util.network import File

if TYPE_CHECKING:
    import pytest

_FILES = Path(__file__).parent / "files"

#: where the cells are: the point of DWD's own example (its worksheet gives 160126 for it), Berlin, Hamburg and Munich
FRANKFURT = (50.089149, 8.785514)
BERLIN = (52.52, 13.40)
HAMBURG = (53.55, 9.99)
MUNICH = (48.137, 11.575)
#: the centre of the cell `000000`, as DWD's `KOSTRA-DWD-2020_geog_Bezug.xlsx` gives it: a cell without values
NORTH_SEA = (56.746962447676303, -1.79415711790058)

BASE = "/climate_environment/CDC/grids_germany/return_periods/precipitation/KOSTRA/KOSTRA_DWD_2020/tab/"


def csv_name(duration: int) -> str:
    """Give the name of the table of a duration, as DWD names the member of its archive."""
    return f"StatRR_KOSTRA-DWD-2020_D{duration:05d}.csv"


def csv_of(duration: int) -> bytes:
    """Give the rows of the stub for a duration, as DWD wrote them."""
    return (_FILES / csv_name(duration)).read_bytes()


def zipped(content: bytes, name: str = "table.csv") -> bytes:
    """Zip a body as one member."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, content)
    return buffer.getvalue()


def table(duration: int) -> bytes:
    """Give the zipped table of a duration, as the server sends it."""
    return zipped(csv_of(duration), csv_name(duration))


UPDATED = dt.datetime(2022, 12, 12, 17, 12, 6, tzinfo=dt.UTC)

#: the zipped tables by the name of the file, for the 22 durations
TABLES: dict[str, bytes] = {f"{csv_name(duration)}.zip": table(duration) for duration in DURATIONS}


def serve(monkeypatch: pytest.MonkeyPatch, tables: dict[str, bytes] | None = None) -> list[str]:
    """Make the request download these tables (the name of the file to its zipped body), nothing from the network.

    Gives the URLs asked for, in order. The files carry the `Last-Modified` of DWD's, 2022-12-12 17:12:06 UTC.
    """
    served = tables if tables is not None else TABLES
    asked: list[str] = []

    def file_of(url: str) -> File:
        asked.append(url)
        return File(url=url, content=io.BytesIO(served[url.rsplit("/", 1)[-1]]), status=200, last_modified=UPDATED)

    def fake_download(url: str, *_args: object, **_kwargs: object) -> File:
        return file_of(url)

    def fake_downloads(urls: list[str], *_args: object, **_kwargs: object) -> list[File]:
        return [file_of(url) for url in urls]

    monkeypatch.setattr("wetterdienst.provider.dwd.kostra.api.download_file", fake_download)
    monkeypatch.setattr("wetterdienst.provider.dwd.kostra.api.download_files", fake_downloads)
    return asked
