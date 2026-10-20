# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frames of the DWD derived datasets that no other offline test reaches, through `values().all()` (GH-2627).

`tests/provider/frames.snapshot.json` records what the core makes of a provider's frame, and is the net under moving
the shaping from the providers into the core. `hourly/radiation_global` is held by the stub of `test_value_stubs.py`
and the monthly degree days, `cooling_degreehours_13` and the climate correction factor by `test_api.py`. These add the
rest: `hourly/sunshine_duration`, `daily/soil`, `monthly/soil` and the cooling degree hours of 16 and 18 degrees, each
written the way DWD serves it (the soil files were read from the `recent` directories on 2026-10-20, cut to a few
columns), so that what each names itself (`resolution`, `dataset`, the stamp, the station) is under the net before the
shaping moves.
"""

from __future__ import annotations

import datetime as dt
from io import BytesIO
from typing import TYPE_CHECKING
from unittest.mock import patch

import polars as pl
import pytest

from tests.provider.value_stubs import _day, _options, _settings, stations_result
from wetterdienst.metadata.period import Period
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.derived import api as dwd_derived_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from collections.abc import Callable

_UTC = dt.UTC
_BASE_URL = "https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly"


def _serve_product(monkeypatch: pytest.MonkeyPatch, product: str) -> None:
    """Make the one file of a station's `produkt` (a radiation, sunshine or soil file) what DWD serves."""
    monkeypatch.setattr(
        dwd_derived_api,
        "create_file_list_for_climate_derived",
        lambda *args, **kwargs: pl.Series(["https://example.invalid/produkt.txt"]),  # noqa: ARG005
    )
    monkeypatch.setattr(
        dwd_derived_api,
        "download_climate_derived_data",
        lambda *args, **kwargs: [  # noqa: ARG005
            File(url="https://example.invalid/produkt.txt", content=BytesIO(product.encode("latin-1")), status=200)
        ],
    )


def _assert_the_long_form(df: pl.DataFrame, *, resolution: str, dataset: str, station_id: str) -> None:
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df["resolution"].unique().to_list() == [resolution]
    assert df["dataset"].unique().to_list() == [dataset]
    assert df["station_id"].unique().to_list() == [station_id]


def test_hourly_sunshine_duration_comes_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sunshine duration is the radiation's sibling: `SD_DUETT` and its uncertainty, `-999` where there is none."""
    # the layout of `stundenwerte_duett_SD_*` as `hourly/sunshine_duration` declares it (QN_952, SD_DUETT, SD_UN_DUETT)
    _serve_product(
        monkeypatch,
        "STATIONS_ID;MESS_DATUM;QN_952;SD_DUETT;SD_UN_DUETT;eor\n"
        "      18001;2025040910;  500;   42;    3;eor\n"
        "      18001;2025040911;  500;   60;    2;eor\n"
        "      18001;2025040912;  500; -999;-999;eor\n",
    )
    request = DwdDerivedRequest(
        parameters=[("hourly", "sunshine_duration")],
        periods={Period.RECENT},
        start=_day(2025, 4, 9),
        end=_day(2025, 4, 9, 23),
        settings=_settings(),
        options=_options(drop_nulls=False),
    )
    df = stations_result(request, "hourly", "sunshine_duration", "18001").values().all().df
    _assert_the_long_form(df, resolution="hourly", dataset="sunshine_duration", station_id="18001")
    assert set(df["parameter"]) == {"sunshine_duration", "sunshine_duration_uncertainty"}
    sunshine = df.filter(pl.col("parameter") == "sunshine_duration").sort("timestamp")
    assert sunshine["timestamp"].to_list() == [_day(2025, 4, 9, hour) for hour in (10, 11, 12)]
    # the unit of the source is the minute, which the core converts to the second
    assert sunshine["value"].to_list() == [42.0 * 60, 60.0 * 60, None]
    assert sunshine["quality_flags"].to_list() == ["500", "500", "500,raw:-999"]


def test_daily_soil_comes_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The soil of a day is stamped at midnight UTC, and its station is written without the padding DWD gives it."""
    # derived_germany_soil_daily_recent_v2_1001.txt.gz, cut to the columns asked for
    _serve_product(
        monkeypatch,
        "Stationsindex;Datum;TS05;ZFUMI;VPGFAO;eor\n"
        "         1001;20260101;    0.0;   15;      1.1;eor\n"
        "         1001;20260102;    0.1;   12;      1.1;eor\n",
    )
    request = DwdDerivedRequest(
        parameters=[
            ("daily", "soil", "temperature_soil_mean_0_05m"),
            ("daily", "soil", "frozen_ground_layer_thickness"),
            ("daily", "soil", "evapotranspiration_potential_grass_fao"),
        ],
        periods={Period.RECENT},
        start=_day(2026, 1, 1),
        end=_day(2026, 1, 2),
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    df = stations_result(request, "daily", "soil", "01001").values().all().df
    _assert_the_long_form(df, resolution="daily", dataset="soil", station_id="01001")
    assert set(df["parameter"]) == {
        "temperature_soil_mean_0_05m",
        "frozen_ground_layer_thickness",
        "evapotranspiration_potential_grass_fao",
    }
    assert df["timestamp"].unique().sort().to_list() == [_day(2026, 1, 1), _day(2026, 1, 2)]
    assert df.height == 6


def test_monthly_soil_comes_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The soil of a month is stamped at the first of the month, and its file ends in a `;` (an empty column)."""
    # derived_germany_soil_monthly_recent_v2_1048.txt.gz, cut to the columns asked for
    _serve_product(
        monkeypatch,
        "Stationsindex;Monat;Mittel von TS05;Maximum von ZTUMI;Summe von VPGFAO;eor;\n"
        "         1048;202601;   -1.2;   25.0;   18.5;eor;\n"
        "         1048;202602;    1.9;   15.0;   19.6;eor;\n",
    )
    request = DwdDerivedRequest(
        parameters=[
            ("monthly", "soil", "temperature_soil_mean_0_05m"),
            ("monthly", "soil", "thawing_thickness_bare_ground_max_month"),
            ("monthly", "soil", "evapotranspiration_potential_grass_fao"),
        ],
        periods={Period.RECENT},
        start=_day(2026, 1, 1),
        end=_day(2026, 2, 1),
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    df = stations_result(request, "monthly", "soil", "01048").values().all().df
    _assert_the_long_form(df, resolution="monthly", dataset="soil", station_id="01048")
    assert df["timestamp"].unique().sort().to_list() == [_day(2026, 1, 1), _day(2026, 2, 1)]
    assert df.height == 6


_COOLING_HEADER = (
    "#Kuehlgrade, erstellt: 20250103; Programm: kuehlgrade_alle_open_data_08_2.pl\n"
    "#Bezugstemperatur (Grad Celsius): {reference}\n"
    "ID;geogr. Breite;geogr. Laenge;Stationsname;Datum [jjjjmm];Anzahl Stunden;Anzahl Kuehlstunden;"
    "Kuehlgradestunden;Kuehltage\n"
)


def _serve_cooling(reference: int) -> Callable[..., File]:
    """Answer a download the way the DWD server does: the file of a month of the reference, or a 404."""
    files = {
        f"{_BASE_URL}/cooling_degreehours/cdh_{reference}/recent/kuehlgrade_{reference}_0_{month}.csv": (
            _COOLING_HEADER.format(reference=reference)
            + f"00044;52.93; 8.24;        GROSSENKNETEN;{month};{hours};    9;    9.9;1\n"
            + f"01048;51.13;13.75;        DRESDEN-KLOTZSCHE;{month};{hours};{cooling_hours};{value};{days}\n"
        )
        for month, hours, cooling_hours, value, days in [
            ("202502", 672, "    4", "    3.7", 1),
            ("202503", 744, "   78", "  169.2", 13),
        ]
    }

    def download_file(url: str, **_: object) -> File:
        if url in files:
            return File(url=url, content=BytesIO(files[url].encode("latin-1")), status=200)
        return File(url=url, content=Exception("not found"), status=404)

    download_file.urls = list(files)  # ty: ignore[unresolved-attribute]
    return download_file


@pytest.mark.parametrize("reference", [16, 18])
def test_cooling_degreehours_of_16_and_18_come_out_as_the_long_form(reference: int) -> None:
    """The cooling degree hours of each reference temperature are a dataset of their own, read from their own files."""
    serve = _serve_cooling(reference)
    request = DwdDerivedRequest(
        parameters=[("monthly", f"cooling_degreehours_{reference}", "cooling_degree_hour")],
        start="2025-02-01",
        end="2025-03-01",
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    with (
        patch("wetterdienst.provider.dwd.derived.api.download_file", side_effect=serve),
        patch("wetterdienst.provider.dwd.derived.api.list_remote_files_fsspec", return_value=serve.urls),
    ):
        df = (
            stations_result(request, "monthly", f"cooling_degreehours_{reference}", "01048")
            .values()
            .all()
            .df.sort("timestamp")
        )
    _assert_the_long_form(df, resolution="monthly", dataset=f"cooling_degreehours_{reference}", station_id="01048")
    assert df["timestamp"].to_list() == [dt.datetime(2025, 2, 1, tzinfo=_UTC), dt.datetime(2025, 3, 1, tzinfo=_UTC)]
    assert df["value"].to_list() == [3.7, 169.2]
