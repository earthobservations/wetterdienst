# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the quality code of SMHI values."""

import polars as pl
import pytest

from tests.provider.smhi.observation import test_api_daily_stamp as stamp
from wetterdienst import Settings
from wetterdienst.provider.smhi.observation import SmhiObservationRequest
from wetterdienst.provider.smhi.observation.parser import parse_smhi_csv

# The head and the tail of station 98230 (Stockholm-Observatoriekullen A), parameter 2, period corrected-archive, as
# opendata-download-metobs.smhi.se writes it (checked 2026-10-11): the code of each reading sits in "Kvalitet", and the
# legend is written into the trailing columns of the first rows.
_FILE = (
    "﻿Stationsnamn;Stationsnummer;Stationsnät;Mäthöjd (meter över marken)\n"
    "Stockholm-Observatoriekullen A;98230;SMHIs stationsnät;2.0\n"
    "\n"
    "Parameternamn;Beskrivning;Enhet\n"
    "Lufttemperatur;medelvärde 1 dygn, 1 gång/dygn, kl 00;celsius\n"
    "\n"
    "Tidsperiod (fr.o.m);Tidsperiod (t.o.m);Höjd (meter över havet);Latitud (decimalgrader);Longitud (decimalgrader)\n"
    "1996-10-01 00:00:00;2026-10-01 19:20:12;43.133;59.3417;18.0549\n"
    "\n"
    "Från Datum Tid (UTC);Till Datum Tid (UTC);Representativt dygn;Lufttemperatur;Kvalitet;;Tidsutsnitt:\n"
    "1996-10-01 00:00:01;1996-10-02 00:00:00;1996-10-01;11.1;Y;;Kvalitetskontrollerade historiska data\n"
    "1996-10-02 00:00:01;1996-10-03 00:00:00;1996-10-02;8.6;G;;Kvalitetskoderna:\n"
    "1996-10-03 00:00:01;1996-10-04 00:00:00;1996-10-03;9.3;Y;;Grön (G) = Kontrollerade och godkända värden.\n"
    "1996-10-04 00:00:01;1996-10-05 00:00:00;1996-10-04;11.5;Y;;Gul (Y) = Misstänkta eller aggregerade värden.\n"
    "1996-10-05 00:00:01;1996-10-06 00:00:00;1996-10-05;9.4;Y\n"
)


def test_smhi_parser_returns_the_quality_code_of_each_reading() -> None:
    """Test that the "Kvalitet" column is returned verbatim as `quality_flag`, beside the value (GH-2018).

    The column was read only to find the value column left of it. SMHI's legend, written into the file:
    "Grön (G) = Kontrollerade och godkända värden." (approved) and "Gul (Y) = Misstänkta eller aggregerade
    värden. Grovt kontrollerade arkivdata och okontrollerade realtidsdata (senaste 2 tim)." (suspect or
    aggregated; roughly checked archive data and unchecked real-time data). Red (R) values are not delivered.
    """
    df = parse_smhi_csv(_FILE.removeprefix("﻿"))
    assert df.get_column("quality_flag").to_list() == ["Y", "G", "Y", "Y", "Y"]
    assert df.get_column("value").to_list() == ["11.1", "8.6", "9.3", "11.5", "9.4"]


def test_smhi_values_carry_the_quality_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the values come back with SMHI's code in `quality_flag` and a null numeric `quality`."""
    stamp._serve(monkeypatch)  # noqa: SLF001
    request = SmhiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start="2025-03-29",
        end="2025-03-31",
        settings=Settings(cache_disable=True),
    ).filter_by_station_id("98230")
    df = request.values.all().df.sort("timestamp")
    assert df.schema["quality_flag"] == pl.String
    assert df.get_column("quality_flag").to_list() == ["Y", "Y", "Y"]
    assert df.get_column("quality").null_count() == df.height
