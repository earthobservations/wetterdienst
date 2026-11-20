# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""KOSTRA-DWD-2020 read from opendata.dwd.de (needs the internet)."""

from __future__ import annotations

import datetime as dt

import pytest

from wetterdienst.exceptions import LocationOutOfRangeError
from wetterdienst.provider.dwd.kostra import DURATIONS, RETURN_PERIODS, DwdKostraRequest

from .stubs import BERLIN, FRANKFURT, NORTH_SEA


@pytest.mark.remote
def test_the_example_of_dwds_anwendungshilfe() -> None:
    """DWD's description works out cell 160126 at 5 minutes as 11.2 mm (5 a) and 20.5 mm (100 a), +-10 % and +-12 %."""
    result = DwdKostraRequest(latitude=FRANKFURT[0], longitude=FRANKFURT[1], duration=5).query()

    rows = {row["return_period_years"]: row for row in result.df.to_dicts()}
    assert result.cell.index_rc == "160126"
    assert (rows[5]["depth_mm"], rows[5]["intensity_l_s_ha"], rows[5]["uncertainty_percent"]) == (11.2, 373.3, 10.0)
    assert (rows[100]["depth_mm"], rows[100]["intensity_l_s_ha"], rows[100]["uncertainty_percent"]) == (
        20.5,
        683.3,
        12.0,
    )
    # DWD wrote the files in December 2022 and keeps them
    assert result.data_updated_at is not None
    assert result.data_updated_at < dt.datetime(2024, 1, 1, tzinfo=dt.UTC)


@pytest.mark.remote
def test_a_cell_of_berlin_has_the_whole_table() -> None:
    """All 22 durations and 9 return periods, no value missing, the depth growing with both."""
    result = DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1]).query()

    assert result.df.height == len(DURATIONS) * len(RETURN_PERIODS)
    assert result.df.null_count().row(0) == (0, 0, 0, 0, 0)
    one_hour = result.df.filter(result.df["duration_minutes"] == 60)
    assert one_hour.filter(one_hour["return_period_years"] == 100)["depth_mm"].item() == 48.9
    assert one_hour["depth_mm"].is_sorted()
    hundred_years = result.df.filter(result.df["return_period_years"] == 100)
    assert hundred_years["depth_mm"].is_sorted()


@pytest.mark.remote
def test_a_cell_in_the_north_sea_has_no_values() -> None:
    """DWD's grid reaches beyond Germany and its border of about 10 km, where it writes its missing values."""
    with pytest.raises(LocationOutOfRangeError, match="no KOSTRA-DWD-2020 values"):
        DwdKostraRequest(latitude=NORTH_SEA[0], longitude=NORTH_SEA[1], duration=60).query()
