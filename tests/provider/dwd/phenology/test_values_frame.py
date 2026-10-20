# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frame of the DWD phenology values, collected through `values().all()` from files served offline (GH-2627).

The tests of `test_api.py` read the parsing and the file choice, and the collection is read only by remote tests, so
no offline frame of this network was in `tests/provider/frames.snapshot.json` to hold what the core hands out while
the shaping moves from the provider into the core. This serves the two files of one plant, as DWD writes them
(blank-padded, `eor` last), and reads the answer for one station.
"""

from __future__ import annotations

import datetime as dt
from io import BytesIO

import polars as pl
import pytest

from tests.provider.value_stubs import _options, _settings, stations_result
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.dwd.phenology import DwdPhenologyRequest
from wetterdienst.provider.dwd.phenology import api as phenology_api
from wetterdienst.util.network import File

_UTC = dt.UTC
_HEADER = (
    "Stations_id; Referenzjahr; Qualitaetsniveau; Objekt_id; Phase_id; Eintrittsdatum;Eintrittsdatum_QB; Jultag;eor;\n"
)


def _file(*rows: tuple[int, ...]) -> bytes:
    """Write rows the way DWD pads them: right-aligned in a column of fixed width, `eor` last."""
    return (_HEADER + "".join(";".join(f"{cell:>12}" for cell in row) + ";eor;\n" for row in rows)).encode("latin-1")


# (Stations_id, Referenzjahr, Qualitaetsniveau, Objekt_id, Phase_id, Eintrittsdatum, Eintrittsdatum_QB, Jultag) of
# hazel (Objekt_id 113); 7521 is Goosefeld, whose 2024 row (27, quality 10) is read from
# `PH_Jahresmelder_Wildwachsende_Pflanze_Hasel_akt` on 2026-10-20. The historical release and the recent file both
# hold 2024, and both hold a station that is not asked for
_HISTORICAL = _file(
    (7521, 2023, 10, 113, 5, 20230105, 1, 5),
    (7521, 2024, 10, 113, 5, 20240127, 1, 27),
    (7650, 2024, 10, 113, 5, 20231229, 1, -3),
)
_RECENT = _file(
    # phase 41 is one the hazel's metadata declares nothing for, and the core drops it
    (7521, 2024, 7, 113, 41, 20240210, 1, 41),
    (7521, 2024, 1, 113, 5, 20240129, 1, 29),
    (7521, 2025, 1, 113, 5, 20250210, 1, 41),
    (7650, 2025, 1, 113, 5, 20250111, 1, 11),
)
_URL = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/phenology/annual_reporters/wild"


def test_phenology_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station's hazel flowering is dated to the 1st of January of its year, and the historical release wins."""
    historical = f"{_URL}/historical/PH_Jahresmelder_Wildwachsende_Pflanze_Hasel_1979_2024_hist.txt"
    files = {historical: _HISTORICAL, f"{_URL}/recent/PH_Jahresmelder_Wildwachsende_Pflanze_Hasel_akt.txt": _RECENT}

    def download_file(*, url: str, **_: object) -> File:
        return File(url=url, content=BytesIO(files[url]), status=200)

    monkeypatch.setattr(phenology_api, "download_file", download_file)
    monkeypatch.setattr(phenology_api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [historical])
    request = DwdPhenologyRequest(
        parameters=[("annual", "annual_common_hazel")],
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    df = stations_result(request, "annual", "annual_common_hazel", "07521").values().all().df.sort("timestamp")
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df["station_id"].unique().to_list() == ["07521"]
    assert df["resolution"].unique().to_list() == ["annual"]
    assert df["dataset"].unique().to_list() == ["annual_common_hazel"]
    assert df["parameter"].unique().to_list() == ["phenology_flowering_beginning"]
    assert df["timestamp"].to_list() == [dt.datetime(year, 1, 1, tzinfo=_UTC) for year in (2023, 2024, 2025)]
    # 2024 is the historical 27 with its flag 10, not the recent 29 with its 1
    assert df["value"].to_list() == [5.0, 27.0, 41.0]
    assert df["quality_flags"].to_list() == ["10", "10", "1"]


@pytest.mark.parametrize(
    "recent",
    [
        pytest.param(_HEADER.encode("latin-1"), id="header-only"),
        pytest.param(b"", id="empty"),
        pytest.param(_file((7650, 2025, 1, 113, 5, 20250111, 1, 11)), id="another-station"),
    ],
)
def test_a_station_with_nothing_in_the_file_is_an_empty_frame_for_the_core_to_skip(
    monkeypatch: pytest.MonkeyPatch, recent: bytes
) -> None:
    """A file that holds nothing for the station is a bare frame, whose columns nobody reads (GH-2627)."""
    monkeypatch.setattr(
        phenology_api, "download_file", lambda *, url, **_: File(url=url, content=BytesIO(recent), status=200)
    )
    request = DwdPhenologyRequest(
        parameters=[("annual", "annual_common_hazel")],
        periods="recent",
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    values = stations_result(request, "annual", "annual_common_hazel", "07521").values()
    dataset = request.parameters[0].dataset
    assert values._collect_station_parameter_or_dataset("07521", dataset).is_empty()  # noqa: SLF001
