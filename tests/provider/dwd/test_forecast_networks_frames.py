# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frames of the DWD forecast networks, for the paths the stubs of `test_value_stubs.py` do not reach (GH-2627).

`tests/provider/frames.snapshot.json` records what the core makes of a provider's frame, and is the net under moving
the shaping from the providers into the core. The stubs cover `hourly/small` of MOSMIX and `hourly/icon` of DMO; these
cover the datasets they leave out (`hourly/large`, `hourly/icon_eu`), which are read by the same code but write their
own `resolution` and `dataset`. The empty answers of POI and SWSMOS are checked on the provider's own frame rather than
through the core: the core skips an empty frame, so what a provider's empty frame holds is no one's to read.
"""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import polars as pl
import pytest

from tests.provider.value_stubs import _forecast_kml, _options, _settings, stations_result
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.dwd.dmo import DwdDmoRequest
from wetterdienst.provider.dwd.dmo import api as dwd_dmo_api
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.mosmix import api as dwd_mosmix_api
from wetterdienst.provider.dwd.poi import DwdPoiMetadata, DwdPoiRequest
from wetterdienst.provider.dwd.poi import api as dwd_poi_api
from wetterdienst.provider.dwd.swsmos import DwdSwsmosMetadata, DwdSwsmosRequest
from wetterdienst.provider.dwd.swsmos import api as dwd_swsmos_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from collections.abc import Callable


def _assert_the_long_form(df: pl.DataFrame, *, resolution: str, dataset: str, station_id: str, rows: int) -> None:
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.height == rows
    assert df["resolution"].unique().to_list() == [resolution]
    assert df["dataset"].unique().to_list() == [dataset]
    assert df["station_id"].unique().to_list() == [station_id]


def test_mosmix_large_comes_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The MOSMIX-L dataset is named `large`, and its temperature is converted from Kelvin."""
    kml = _forecast_kml("01001", {"TTT": "275.15 276.15 277.15"})
    monkeypatch.setattr(
        dwd_mosmix_api.DwdMosmixValues,
        "get_url_for_date",
        lambda *args, **kwargs: "https://example.invalid/MOSMIX_L_2026101009_01001.kmz",  # noqa: ARG005
    )
    monkeypatch.setattr(dwd_mosmix_api.KMLReader, "fetch", lambda _self, _url: BytesIO(kml))
    request = DwdMosmixRequest(
        parameters=[("hourly", "large", "ttt")],
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    df = stations_result(request, "hourly", "large", "01001").values().all().df
    _assert_the_long_form(df, resolution="hourly", dataset="large", station_id="01001", rows=3)
    assert df.sort("timestamp")["value"].round(2).to_list() == [2.0, 3.0, 4.0]
    assert df["timestamp"].dtype == pl.Datetime("us", "UTC")


def test_dmo_icon_eu_comes_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The DMO ICON-EU dataset is named `icon_eu`, and its temperature is converted from Kelvin."""
    kml = _forecast_kml("01001", {"TTT": "275.15 276.15 277.15"})
    monkeypatch.setattr(
        dwd_dmo_api.DwdDmoValues,
        "get_url_for_date",
        lambda *args, **kwargs: "https://example.invalid/ptp_gdmog_01001_078_1_100000.kmz",  # noqa: ARG005
    )
    monkeypatch.setattr(dwd_dmo_api.KMLReader, "fetch", lambda _self, _url: BytesIO(kml))
    request = DwdDmoRequest(
        parameters=[("hourly", "icon_eu", "ttt")],
        lead_time="short",
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    df = stations_result(request, "hourly", "icon_eu", "01001").values().all().df
    _assert_the_long_form(df, resolution="hourly", dataset="icon_eu", station_id="01001", rows=3)
    assert df.sort("timestamp")["value"].round(2).to_list() == [2.0, 3.0, 4.0]
    assert df["timestamp"].dtype == pl.Datetime("us", "UTC")


_POI_HEADER = (
    "surface observations;Parameter description;dry_bulb_temperature_at_2_meter_above_ground\n"
    "10147;Unit;Grad C\n"
    "Datum;Uhrzeit (UTC);Temperatur (2m)\n"
)
_POI_NO_PARAMETER_HEADER = "surface observations;Parameter description;unknown\n10147;Unit;x\nDatum;Uhrzeit (UTC);y\n"


def _poi_collect(monkeypatch: pytest.MonkeyPatch, file: File) -> pl.DataFrame:
    monkeypatch.setattr(dwd_poi_api, "download_file", lambda *args, **kwargs: file)  # noqa: ARG005
    request = DwdPoiRequest(parameters=[("hourly", "data")], settings=_settings())
    values = stations_result(request, "hourly", "data", "10147").values()
    return values._collect_station_parameter_or_dataset("10147", DwdPoiMetadata["hourly"]["data"])  # noqa: SLF001


@pytest.mark.parametrize(
    "file",
    [
        pytest.param(File(url="https://example.invalid/10147-BEOB.csv", content=OSError("gone"), status=404), id="404"),
        pytest.param(File(url="https://example.invalid/10147-BEOB.csv", content=BytesIO(b""), status=200), id="empty"),
        pytest.param(
            File(url="https://example.invalid/10147-BEOB.csv", content=BytesIO(_POI_HEADER.encode()), status=200),
            id="no-reports",
        ),
        pytest.param(
            File(
                url="https://example.invalid/10147-BEOB.csv",
                content=BytesIO((_POI_NO_PARAMETER_HEADER + "10.10.26;20:00;1\n").encode()),
                status=200,
            ),
            id="no-known-parameter",
        ),
    ],
)
def test_poi_with_nothing_to_report_hands_the_core_no_rows(monkeypatch: pytest.MonkeyPatch, file: File) -> None:
    """A withdrawn, empty or unreadable station file is an empty frame, which the core skips."""
    assert _poi_collect(monkeypatch, file).is_empty()


def _swsmos_collect(monkeypatch: pytest.MonkeyPatch, run: Callable[[], pl.DataFrame]) -> pl.DataFrame:
    monkeypatch.setattr(dwd_swsmos_api.DwdSwsmosValues, "_run_frame", lambda _self, _settings: run())
    request = DwdSwsmosRequest(parameters=[("hourly", "data")], settings=_settings())
    values = stations_result(request, "hourly", "data", "A006").values()
    return values._collect_station_parameter_or_dataset("A006", DwdSwsmosMetadata["hourly"]["data"])  # noqa: SLF001


@pytest.mark.parametrize(
    "run",
    [
        pytest.param(pl.DataFrame, id="no-run"),
        pytest.param(lambda: pl.DataFrame({"x": ["1"]}), id="no-id-column"),
        pytest.param(
            lambda: pl.DataFrame({"ID": ["B007"], "YYYYMMDDHHmm": ["202610120600"], "TL": ["6.2"]}),
            id="station-not-in-the-run",
        ),
    ],
)
def test_swsmos_with_nothing_to_report_hands_the_core_no_rows(
    monkeypatch: pytest.MonkeyPatch, run: Callable[[], pl.DataFrame]
) -> None:
    """A run that is not there, or holds nothing for the station, is an empty frame, which the core skips."""
    assert _swsmos_collect(monkeypatch, run).is_empty()
