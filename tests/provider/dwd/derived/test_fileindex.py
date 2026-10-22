# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The ids the file index of `dwd/derived` reads from the names DWD lists (GH-3257)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wetterdienst import Settings
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.derived.fileindex import (
    create_file_index_for_climate_derived,
    create_file_list_for_climate_derived,
)
from wetterdienst.provider.dwd.derived.metadata import DwdDerivedMetadata
from wetterdienst.provider.dwd.observation import fileindex as dwd_fileindex

if TYPE_CHECKING:
    import pytest

_SOIL = "https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/daily/recent/"
_RADIATION = (
    "https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/radiation_global/recent/"
)


def _serve(monkeypatch: pytest.MonkeyPatch, base: str, names: list[str]) -> None:
    listed = [f"{base}{name}" for name in names]
    monkeypatch.setattr(dwd_fileindex, "list_remote_files_fsspec", lambda *_args, **_kwargs: listed)


def test_soil_files_with_an_id_of_one_to_five_digits_are_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pad the id of a soil file as the list of the stations does, however many digits the file name has.

    DWD does not pad the index in `derived_germany_soil_daily_recent_v2_44.txt.gz`, and the pattern asked for three
    digits at least, so the files of the stations 44, 73, 78, 91 and 96 were not in the index and the stations were
    dropped from the catalogue. The names are those of `soil/daily/recent/` as listed on 2026-10-21, with the other
    files of the directory (the description, the list and the map of the stations).
    """
    _serve(
        monkeypatch,
        _SOIL,
        [
            "AMBETI.pdf",
            "BESCHREIBUNG_derived_ermany_soil_daily_recent_de_v2.pdf",
            "derived_germany_soil_daily_recent_stations_list.txt",
            "derived_germany_soil_daily_recent_stations_map.png",
            "derived_germany_soil_daily_recent_v2_44.txt.gz",
            "derived_germany_soil_daily_recent_v2_73.txt.gz",
            "derived_germany_soil_daily_recent_v2_1001.txt.gz",
            "derived_germany_soil_daily_recent_v2_13710.txt.gz",
        ],
    )
    dataset = DwdDerivedMetadata["daily"]["soil"]
    settings = Settings(cache_disable=True)
    index = create_file_index_for_climate_derived(dataset, Period.RECENT, settings).collect()
    assert index["station_id"].to_list() == ["00044", "00073", "01001", "13710"]
    assert index["filename"].to_list() == [
        "derived_germany_soil_daily_recent_v2_44.txt.gz",
        "derived_germany_soil_daily_recent_v2_73.txt.gz",
        "derived_germany_soil_daily_recent_v2_1001.txt.gz",
        "derived_germany_soil_daily_recent_v2_13710.txt.gz",
    ]
    urls = create_file_list_for_climate_derived("00044", dataset, Period.RECENT, settings)
    assert urls.to_list() == [f"{_SOIL}derived_germany_soil_daily_recent_v2_44.txt.gz"]


def test_radiation_files_are_read_by_their_five_digit_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """The zip files of the radiation are padded by DWD, so the id is read from between the underscores."""
    _serve(
        monkeypatch,
        _RADIATION,
        [
            "fg_duett_Beschreibung_Stationen.txt",
            "stundenwerte_duett_FG_18000_akt.zip",
            "stundenwerte_duett_FG_18001_akt.zip",
        ],
    )
    dataset = DwdDerivedMetadata["hourly"]["radiation_global"]
    index = create_file_index_for_climate_derived(dataset, Period.RECENT, Settings(cache_disable=True)).collect()
    assert index["station_id"].to_list() == ["18000", "18001"]
