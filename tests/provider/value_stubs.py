# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Stubs of what a source publishes for a reading it does not have, for `test_value_stubs.py` (GH-2615).

A stub is the response of the source for one station: a reading and, beside it, the way the source writes that it has
none, copied from a real file or worded as the source's own documentation words it. Standing in for the download, it
runs the provider's own reader and the framework's unit conversion, so a sentinel that survives the parser, or is
mapped to null only after the unit converter has had it, shows here without the network. The test checks that the
reading arrives, that the sentinel is nowhere in the values, and holds them to the physical range of their parameter
(`physical_ranges.py`).

A provider that is known to let a sentinel through says so with `leak`, the issue that tracks it. The test then
asserts that the sentinel *is* still in the output, so fixing the provider fails it, and the fix removes the `leak`.

A sentinel a reader maps to null (or to the value the source documents it to mean) is not lost: the value carries the
text the source wrote in `quality_flags`, as a last `raw:<text>` token (GH-2759). `tokens` names, per stub, each
(parameter, text, value) that has to arrive, with `drop_nulls=False` since the default drops the null rows; the test
holds every sentinel of `sentinels` to having one, so a reader that maps a sentinel and keeps no text fails it.

To hold another provider to this, add a stub to `STUBS`: serve what the source answers, write the missing value as the
source does, and name the parameter and value that must arrive. A network that has no stub is named in `NO_STUB` with
the reason, and `test_every_network_has_a_stub_or_a_reason` fails for one that is in neither.
"""

from __future__ import annotations

import bz2
import datetime as dt
import gzip
import json
import tempfile
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

import polars as pl
import pytest

from wetterdienst import Options, Settings
from wetterdienst.metadata.period import Period
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.aemet.observation import AemetObservationRequest
from wetterdienst.provider.aemet.observation import api as aemet_api
from wetterdienst.provider.dmi.observation import DmiObservationRequest
from wetterdienst.provider.dmi.observation import api as dmi_api
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.derived import api as dwd_derived_api
from wetterdienst.provider.dwd.dmo import DwdDmoRequest
from wetterdienst.provider.dwd.dmo import api as dwd_dmo_api
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.mosmix import api as dwd_mosmix_api
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation import api as dwd_observation_api
from wetterdienst.provider.dwd.poi import DwdPoiRequest
from wetterdienst.provider.dwd.poi import api as dwd_poi_api
from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest
from wetterdienst.provider.dwd.swsmos import api as dwd_swsmos_api
from wetterdienst.provider.eccc.observation import EcccObservationRequest
from wetterdienst.provider.eccc.observation import api as eccc_api
from wetterdienst.provider.fmi.observation import FmiObservationRequest
from wetterdienst.provider.fmi.observation import api as fmi_api
from wetterdienst.provider.geosphere.observation import GeosphereObservationRequest
from wetterdienst.provider.geosphere.observation import api as geosphere_api
from wetterdienst.provider.imgw.hydrology import ImgwHydrologyRequest
from wetterdienst.provider.imgw.hydrology import api as imgw_hydrology_api
from wetterdienst.provider.ipma.observation import IpmaObservationRequest
from wetterdienst.provider.ipma.observation import api as ipma_api
from wetterdienst.provider.knmi.observation import KnmiObservationRequest
from wetterdienst.provider.knmi.observation import api as knmi_api
from wetterdienst.provider.meteofrance.observation import MeteoFranceObservationRequest
from wetterdienst.provider.meteofrance.observation import api as observation_api
from wetterdienst.provider.meteofrance.synop import MeteoFranceSynopRequest
from wetterdienst.provider.meteofrance.synop import api as synop_api
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.provider.metoffice.observation import MetOfficeObservationRequest
from wetterdienst.provider.metoffice.observation import api as metoffice_api
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest
from wetterdienst.provider.noaa.ghcn import api as ghcn_api
from wetterdienst.provider.nws.observation import NwsObservationRequest
from wetterdienst.provider.nws.observation import api as nws_api
from wetterdienst.provider.rmi.observation import RmiObservationRequest
from wetterdienst.provider.rmi.observation import api as rmi_api
from wetterdienst.provider.smhi.observation import SmhiObservationRequest
from wetterdienst.provider.smhi.observation import api as smhi_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from collections.abc import Callable

_UTC = dt.UTC


@dataclass(frozen=True)
class ValueStub:
    """The values a provider's reader gives for a stub of its source, and what they must and must not hold."""

    provider: str
    # `build(monkeypatch)` gives the values as a caller gets them, `build(monkeypatch, drop_nulls=False)` with the rows
    # that have no value kept
    build: Callable[..., pl.DataFrame]
    # a (canonical parameter, value) that has to arrive, so that the stub is no empty frame
    reading: tuple[str, float]
    # the numbers the source writes for a missing value, as the output would carry them; (parameter, value) where the
    # number is a sentinel for one parameter and a reading for another. None where the source writes a text that is no
    # number (`-`, `---`), which no unit conversion can turn into one
    sentinels: tuple[tuple[str, float], ...] = ()
    # the `raw:` tokens that have to arrive, as (canonical parameter, the text the source wrote, the value it was mapped
    # to: None for null). The text is verbatim: `-999`, not `-999.0`, wherever the source writes it so
    tokens: tuple[tuple[str, str, float | None], ...] = ()
    # the issue that tracks a sentinel the provider lets through
    leak: str | None = None
    # an instant at which the source has no reading at all, so that the output has no row for it, whatever the unit
    empty_at: dt.datetime | None = None


def serve(monkeypatch: pytest.MonkeyPatch, module: Any, bodies: dict[str, bytes | Callable[[str], bytes]]) -> None:  # noqa: ANN401
    """Make the downloads of a provider module answer with the given bodies, by a part of the url."""

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        url = url or args[0]
        for part, body in bodies.items():
            if part in url:
                content = body(url) if callable(body) else body
                return File(url=url, content=BytesIO(content), status=200)
        msg = f"the stub serves nothing for {url}"
        raise AssertionError(msg)

    monkeypatch.setattr(module, "download_file", download_file)


GHCNH_ATTRIBUTES = ("Measurement_Code", "Quality_Code", "Report_Type", "Source_Code", "Source_Station_ID")


def ghcnh_psv(station: str, columns: list[str], rows: list[tuple[str, dict[str, str]]]) -> bytes:
    """Write a GHCNh by-station file with a column per element and, beside each, its five attribute columns.

    NOAA writes `<element>_Measurement_Code`, `_Quality_Code`, `_Report_Type`, `_Source_Code` and `_Source_Station_ID`
    beside every element, in that order. A cell a row does not name is empty; a row names an attribute as
    `<element>_<attribute>` (`temperature_Quality_Code`), and a name that is in no column is an error, so that a typo
    cannot leave a stub testing nothing.
    """
    header = ["STATION", "DATE"] + [
        name for column in columns for name in (column, *(f"{column}_{attribute}" for attribute in GHCNH_ATTRIBUTES))
    ]
    for _, row in rows:
        unknown = set(row) - set(header)
        assert not unknown, f"the file has no column {sorted(unknown)}"
    lines = ["|".join(header)]
    lines += ["|".join([station, date, *[row.get(name, "") for name in header[2:]]]) for date, row in rows]
    return "\n".join(lines).encode("utf8")


def stations_result(request: Any, resolution: str, dataset: str, station_id: str) -> StationsResult:  # noqa: ANN401
    """Stand a station up rather than look it up, for a provider whose catalogue is not worth serving."""
    df = pl.DataFrame(
        [
            {
                "resolution": resolution,
                "dataset": dataset,
                "station_id": station_id,
                "start_timestamp": None,
                "end_timestamp": None,
                "latitude": 50.0,
                "longitude": 10.0,
                "elevation": 100.0,
                "name": "Stub",
            }
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
        },
    )
    return StationsResult(request=request, df=df, df_all=df, stations_filter=StationsFilter.BY_STATION_ID)


def _settings(**kwargs: Any) -> Settings:  # noqa: ANN401
    """Give the host settings of a stub: no cache, and whatever else the provider needs (a credential)."""
    return Settings(cache_disable=True, **kwargs)


def _options(drop_nulls: bool) -> Options:  # noqa: FBT001
    """Give the options of a stub: the rows without a value are dropped as by default, or kept to see their flags."""
    return Options(drop_nulls=drop_nulls)


def _day(year: int, month: int, day: int, hour: int = 0) -> dt.datetime:
    return dt.datetime(year, month, day, hour, tzinfo=_UTC)


def _ipma(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    stations = [
        {
            "geometry": {"type": "Point", "coordinates": [-9.1333, 38.7667]},
            "type": "Feature",
            "properties": {"idEstacao": 1200579, "localEstacao": "Lisboa (Geofísico)"},
        }
    ]
    # `(valor "-99.0" = nodata)` in every numeric field, and wind direction is a code of eight points
    reading = {
        "temperatura": 21.5,
        "humidade": 64.0,
        "pressao": 1015.2,
        "intensidadeVento": 3.1,
        "idDireccVento": 4,
        "precAcumulada": 0.0,
        "radiacao": 410.0,
    }
    feed = {
        "2026-10-10T12:00": {"1200579": reading},
        "2026-10-10T13:00": {"1200579": dict.fromkeys(reading, -99.0)},
        # code 0 is "no direction (calm)", which the feed writes as the integer 0 (checked on the live feed)
        "2026-10-10T14:00": {"1200579": {**reading, "idDireccVento": 0}},
    }
    serve(
        monkeypatch,
        ipma_api,
        {"stations.json": json.dumps(stations).encode("utf8"), "observations.json": json.dumps(feed).encode("utf8")},
    )
    request = IpmaObservationRequest(
        parameters=[("hourly", "data")],
        start=_day(2026, 10, 10, 11),
        end=_day(2026, 10, 10, 14),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return request.filter_by_station_id("1200579").values().all().df


def _dwd_observation(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    dataset: str,
    product: str,
    station_id: str = "00044",
    year: int = 2025,
    *,
    drop_nulls: bool = True,
) -> pl.DataFrame:
    """Give the values of one station from a product file of DWD, as the parser and the framework make them."""
    monkeypatch.setattr(
        dwd_observation_api,
        "create_file_list_for_climate_observations",
        lambda *args, **kwargs: pl.Series(["https://example.invalid/produkt.zip"]),  # noqa: ARG005
    )
    monkeypatch.setattr(
        dwd_observation_api,
        "download_climate_observations_data",
        lambda *args, **kwargs: [  # noqa: ARG005
            File(url="https://example.invalid/produkt.txt", content=BytesIO(product.encode("latin-1")), status=200)
        ],
    )
    request = DwdObservationRequest(
        parameters=[(resolution, dataset)],
        periods={Period.RECENT},
        start=_day(year, 1, 1),
        end=_day(year, 12, 31),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, resolution, dataset, station_id).values().all().df


def _dwd_daily_climate_summary(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # `missing_value=-999` in the description of every DWD dataset that states one, in every column
    columns = [
        "STATIONS_ID",
        "MESS_DATUM",
        "QN_3",
        "FX",
        "FM",
        "QN_4",
        "RSK",
        "RSKF",
        "SDK",
        "SHK_TAG",
        "NM",
        "VPM",
        "PM",
        "TMK",
        "UPM",
        "TXK",
        "TNK",
        "TGK",
    ]
    reading = [
        "44",
        "20250101",
        "10",
        "8.3",
        "3.2",
        "3",
        "0.0",
        "0",
        "0.0",
        "0",
        "7.3",
        "6.6",
        "1008.7",
        "2.9",
        "86.0",
        "4.0",
        "1.2",
        "0.8",
    ]
    missing = ["44", "20250102", "10", "-999", "-999", "3", *["-999"] * 12]
    # DWD pads every field, which is what makes a column text for the reader
    lines = [";".join(f"{cell:>8}" for cell in row) + ";eor" for row in (columns, reading, missing)]
    return _dwd_observation(monkeypatch, "daily", "climate_summary", "\n".join(lines) + "\n", drop_nulls=drop_nulls)


def _dwd_hourly_moisture(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # the description says `missing value = -999`; the files write -99.9
    # (stundenwerte_TF_03735_19490101_19511231_hist.zip, 1949-01-28 06:00; station 14006, 2025-01-05 01:00,
    # in stundenwerte_TF_14006_20201104_20251231_hist.zip). That file holds 995.9 in P_STD in all of its 44531 rows, the
    # pressure of a station without a barometer: the sheet ("Stundenwerte Luftdruck") says nothing of it, the reader
    # nulls a constant from 500 readings on (GH-2699), so the file is served with 500 rows
    rows = [
        "   14006;2025010500;    3;   4.6;   5.8;  -0.3;  995.9;  -0.1;  95.7;  -0.7;eor",
        "   14006;2025010501;    3; -99.9; -99.9; -99.9;  995.9;  -0.7; -99.9; -99.9;eor",
    ]
    start = dt.datetime(2025, 1, 5, 2, tzinfo=_UTC)
    rows += [
        f"   14006;{start + dt.timedelta(hours=hour):%Y%m%d%H};    3;   4.0;   5.0;  -0.5;  995.9;"
        "  -0.2;  90.0;  -0.9;eor"
        for hour in range(498)
    ]
    product = (
        "STATIONS_ID;MESS_DATUM;QN_8;ABSF_STD;VP_STD;TF_STD;P_STD;TT_STD;RF_STD;TD_STD;eor\n" + "\n".join(rows) + "\n"
    )
    return _dwd_observation(monkeypatch, "hourly", "moisture", product, "14006", drop_nulls=drop_nulls)


def _dwd_hourly_wind(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # historical/stundenwerte_FF_00003_19370101_20110331_hist.zip: the description says `missing value=-999`, the files
    # of 1975 to 1994 write 990 for a direction there is none of, and 0 for a calm (a speed of 0.0) beside 360 for north
    # of a "36-teilige Windrose", which has no point 0 (GH-2805)
    product = (
        "STATIONS_ID;MESS_DATUM;QN_3;   F;   D;eor\n"
        "          3;1975101607;    5;   2.1;  250;eor\n"
        "          3;1975101608;    5;   1.3;  990;eor\n"
        "          3;1975020807;    5;   0.0;    0;eor\n"
        "          3;1975010215;    5;   1.2;  360;eor\n"
    )
    return _dwd_observation(monkeypatch, "hourly", "wind", product, "00003", year=1975, drop_nulls=drop_nulls)


def _dwd_hourly_wind_synop(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # historical/stundenwerte_F_00003_19500401_20110401_hist.zip: "Windrichtung uml.,windstill DD=00" (DWD), so the 0 of
    # 1954-02-19 15:00 (beside 1.0 m/s) is no direction; 360 is north, as at 1954-01-04 00:00 (GH-2805)
    product = (
        "STATIONS_ID;MESS_DATUM;QN_8;  FF;  DD;eor\n"
        "          3;1954021915;    1;   1.0;   0;eor\n"
        "          3;1954010400;    1;   2.6; 360;eor\n"
    )
    return _dwd_observation(monkeypatch, "hourly", "wind_synop", product, "00003", year=1954, drop_nulls=drop_nulls)


def _dwd_subdaily_wind(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # historical/terminwerte_FK_00001_19370101_19860630_hist.zip: "Terminwerte der Windrichtung (32-teilige Windrose)",
    # whose 0 is a calm (Beaufort 0) and whose north is 32 (GH-2805, GH-2808): 24 is a west wind, 270 degrees
    product = (
        "STATIONS_ID;MESS_DATUM;QN_4;DK_TER;FK_TER;eor\n"
        "          1;1937010107;    5;   0;   0;eor\n"
        "          1;1937010114;    5;  24;   3;eor\n"
    )
    return _dwd_observation(monkeypatch, "subdaily", "wind", product, "00001", year=1937, drop_nulls=drop_nulls)


def _dwd_10_minutes_wind(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # historical/10minutenwerte_wind_01691_19931110_19991231_hist.zip, read 2026-10-12: station 01691 writes north as
    # 360 and as 0 (22:00 and 22:10 of 1993-11-15, at 5.0 and 6.1 m/s), so only the 0 beside a speed of 0.0 (1993-11-17
    # 04:20) is a calm (GH-2805)
    product = (
        "STATIONS_ID;MESS_DATUM;  QN;FF_10;DD_10;eor\n"
        "       1691;199311152200;    1;   5.0; 360;eor\n"
        "       1691;199311152210;    1;   6.1;   0;eor\n"
        "       1691;199311170420;    1;   0.0;   0;eor\n"
    )
    return _dwd_observation(monkeypatch, "10_minutes", "wind", product, "01691", year=1993, drop_nulls=drop_nulls)


def _dwd_10_minutes_urban_wind(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # climate_urban/10_minutes/wind/recent/10minutenwerte_FF_STADT_15818_akt.zip, read 2026-10-13: the sheet of the
    # dataset answers 404; all 20 zeros of the recent files and 51 of the historical ones come beside a speed of 0.00
    # (2025-04-28 18:30), and north is 360 (2025-04-12 06:20) (GH-2809)
    product = (
        "STATIONS_ID;MESS_DATUM;  QN;FF_ST_10;DD_ST_10;eor\n"
        "      15818;202504281830;    3;   0.00;   0;eor\n"
        "      15818;202504281820;    3;   0.10; 220;eor\n"
        "      15818;202504120620;    3;   0.50; 360;eor\n"
    )
    return _dwd_observation(monkeypatch, "10_minutes", "urban_wind", product, "15818", year=2025, drop_nulls=drop_nulls)


def _dwd_hourly_urban_wind(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # climate_urban/hourly/wind/recent/stundenwerte_wind_13667_akt.zip, read 2026-10-12 (the Berlin television tower,
    # 368 m): 1,288 zeros in 295,005 hours, none beside a speed of 0 and, in the 410 hours with the six 10 minute
    # values at hand, no sign of a calm or of north: the six directions are spread over the compass (13667, 2025-04-12
    # 04:00 UTC: 50, 110, 250, 260, 100 and 80 degrees). North is 360 (2018-09-23 01:00) (GH-2809)
    product = (
        "STATIONS_ID; MESS_DATUM; QUALITAETS_NIVEAU; STRUKTUR_VERSION; WINDGESCHWINDIGKEIT; WINDRICHTUNG; eor\n"
        "     13667;   2018061722;    2;0;  0.50;  0;eor\n"
        "     13667;   2018092301;    2;0;  0.40;360;eor\n"
    )
    return _dwd_observation(monkeypatch, "hourly", "urban_wind", product, "13667", year=2018, drop_nulls=drop_nulls)


def _dwd_10_minutes_urban_solar(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # climate_urban/10_minutes/solar/recent/10minutenwerte_SD_STADT_00399_akt.zip, read 2026-10-14: the sheet of the
    # parameter says "Minute", the values are fractions of an hour -- 0.17 (10/60 rounded) in 1257 rows, never more,
    # and 0.02 one minute -- so that a full-sun interval is 612 s, not 10.2 s (GH-2698); both columns write -999
    product = (
        "STATIONS_ID;MESS_DATUM;  QN;FG_ST_10;SD_ST_10;eor\n"
        "        399;202504120000;    3;     -999;  0.00;eor\n"
        "        399;202504121050;    3;     -999;  0.02;eor\n"
        "        399;202504121200;    3;     -999;  0.17;eor\n"
        "        399;202506182350;    3;     -999;-999;eor\n"
    )
    return _dwd_observation(
        monkeypatch, "10_minutes", "urban_solar", product, "00399", year=2025, drop_nulls=drop_nulls
    )


def _dwd_10_minutes_extreme_wind(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # historical/10minutenwerte_extrema_wind_00003_19930429_19991231_hist.zip: the direction of the gust is 0 beside a
    # gust of 0.0 (1993-04-28 12:30), a calm, and beside one of 4.1 m/s (1993-06-15 15:30), a north (GH-2805)
    product = (
        "STATIONS_ID;MESS_DATUM;  QN;FX_10;FNX_10;FMX_10;DX_10\n"
        "          3;199304281230;    1;   0.0;  -999;  -999;   0\n"
        "          3;199306151530;    1;   4.1;  -999;  -999;   0\n"
    )
    return _dwd_observation(
        monkeypatch, "10_minutes", "wind_extreme", product, "00003", year=1993, drop_nulls=drop_nulls
    )


def _dwd_hourly_weather_phenomena(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # station 01048, stundenwerte_WW_01048_19750701_20251231_hist.zip, 2022-08-01 05:00 to 09:00 (read 2026-10-15): the
    # station reports from the 0-99 table (21, 61) and from the 100-199 table (123, 100) within these five hours,
    # and `WW_Text` says "Wetter wurde nicht gemeldet" for the -1
    product = (
        "STATIONS_ID;MESS_DATUM;QN_8;  WW;WW_Text;eor\n"
        "       1048;2022080105;    3;  -1;Wetter wurde nicht gemeldet;eor\n"
        "       1048;2022080106;    3;  21;Regen, nicht gefrierend (nicht zur Zeit der Beobachtung): an der Station in "
        "der letzen Stunde, kein Schauercharakter;eor\n"
        "       1048;2022080107;    3;  61;Regen ohne Unterbrechungen: leicht;eor\n"
        "       1048;2022080108;    3; 123;Regen, nicht gefrierend (nicht zum Beobachtungszeitpunkt): an der "
        "Station in der letzten Stunde;eor\n"
        "       1048;2022080109;    3; 100;bei Bewölkung (> 0/8) zum Beobachtungstermin: keine signifikanten "
        "Wettererscheinungen beobachtet;eor\n"
    )
    return _dwd_observation(
        monkeypatch, "hourly", "weather_phenomena", product, "01048", year=2022, drop_nulls=drop_nulls
    )


def _dwd_hourly_precipitation(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # station 01048, stundenwerte_RR_01048_19950901_20251231_hist.zip (read 2026-10-16): the 9 of `WRTR` is DWD's
    # "Missing value, Type of precipitation unascertainable" (the English sheet), written 2021-07-09 17:00 beside a
    # height of 0.0 and, in the files read, mostly beside R1 = -999 (261 of 270 rows). A 6 is a liquid precipitation
    product = (
        "STATIONS_ID;MESS_DATUM;QN_8;  R1;RS_IND;WRTR;eor\n"
        "       1048;2021070915;    3;   0.4;   1;   6;eor\n"
        "       1048;2021070916;    3;   0.0;   0;   0;eor\n"
        "       1048;2021070917;    3;   0.0;   1;   9;eor\n"
    )
    return _dwd_observation(monkeypatch, "hourly", "precipitation", product, "01048", year=2021, drop_nulls=drop_nulls)


def _dwd_hourly_cloudiness(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # the -1 where the sky could not be seen, as the hourly cloud_type file of station 00003 writes it (43 times in
    # 2005, read 2026-10-12); the cloudiness file is worded after it
    product = (
        "STATIONS_ID;MESS_DATUM;QN_8;V_N_I;V_N;eor\n"
        "          3;2025040800;    3;    I;   4;eor\n"
        "          3;2025040801;    3;    I;  -1;eor\n"
    )
    return _dwd_observation(monkeypatch, "hourly", "cloudiness", product, "00003", drop_nulls=drop_nulls)


# the first row of klima-v2-1d/metadata/stations with the list's header, as Geosphere publishes it (read 2026-10-14)
_GEOSPHERE_STATIONS = (
    "id,Synopstationsnummer,Stationsname,Länge [°E],Breite [°N],Höhe [m],Startdatum,Enddatum,Bundesland,"
    "Sonnenschein,Globalstrahlung,Synop,Verknüpfungsnummer,Startdatum Teilzeitreihe,Enddatum Teilzeitreihe,"
    "zusammengesetzt\n"
    "1,,Aflenz,15.24069,47.54594,783.2,1983-05-01 00:00:00+00:00,2100-12-31 00:00:00+00:00,Steiermark,"
    "True,True,,,,,ja\n"
)


def _geosphere_daily(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    stations = _GEOSPHERE_STATIONS.encode()
    # klima-v2-1d: "-1=kein Niederschlag, 0=weniger als 1/10 mm" for rr, "-1=kein Schnee" for sh_manu
    # (checked on the live API for station 5904: rr is written -1.0, the whole-number sh_manu -1)
    series = {"rr": [0.3, -1.0, 0.0], "sh_manu": [4, -1, 2]}

    def data(url: str) -> bytes:
        names = parse_qs(urlparse(url).query)["parameters"][0].split(",")
        timestamps = ["2024-01-08T00:00+00:00", "2024-01-09T00:00+00:00", "2024-01-10T00:00+00:00"]
        parameters = {name: {"data": series[name]} for name in sorted(names)}
        body = {"timestamps": timestamps, "features": [{"properties": {"parameters": parameters}}]}
        return json.dumps(body).encode()

    serve(monkeypatch, geosphere_api, {"/metadata/stations": stations, "klima-v2-1d": data})
    request = GeosphereObservationRequest(
        parameters=[("daily", "data", "precipitation_amount"), ("daily", "data", "snow_depth_manual")],
        start=_day(2024, 1, 8),
        end=_day(2024, 1, 10),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return request.filter_by_station_id("1").values().all().df


def _geosphere_hourly(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    stations = _GEOSPHERE_STATIONS.encode()
    # klima-v2-1h for Aflenz, 2024-01-02 18:00 to 20:00 (read 2026-10-12): "Windrichtung [360°]" dd is [9, 0, 38] beside
    # the speed ff [0.3, 0.0, 0.5], the calm at 19:00 written 0; north is 360 (GH-2794)
    series = {"dd": [9, 0, 38], "ff": [0.3, 0.0, 0.5]}

    def data(url: str) -> bytes:
        names = parse_qs(urlparse(url).query)["parameters"][0].split(",")
        timestamps = ["2024-01-02T18:00+00:00", "2024-01-02T19:00+00:00", "2024-01-02T20:00+00:00"]
        parameters = {name: {"data": series[name]} for name in sorted(names)}
        body = {"timestamps": timestamps, "features": [{"properties": {"parameters": parameters}}]}
        return json.dumps(body).encode()

    serve(monkeypatch, geosphere_api, {"/metadata/stations": stations, "klima-v2-1h": data})
    request = GeosphereObservationRequest(
        parameters=[("hourly", "data", "wind_direction"), ("hourly", "data", "wind_speed")],
        start=_day(2024, 1, 2, 18),
        end=_day(2024, 1, 2, 20),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return request.filter_by_station_id("1").values().all().df


def _ghcn_hourly(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # GHCNh_ACM00078861_por.psv, 1942-01-17 02:00: the direction reads 999 with the measurement code C (calm) and a
    # wind speed of 0.0; the documentation gives "000" for calm. 1942-01-28 14:00 reads 999 too, with no code and a
    # wind speed of 4.1 (the stub puts it on the 17th): no direction given. The documentation: "the most consistent
    # way to identify hours of missing data across the entire dataset is to test if the precipitation value is equal
    # to the special missing value of -9999"; the precipitation columns of the Antigua file are empty, so that row is
    # worded after the documentation
    stations = (
        b"GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        b"ACM00078861,17.1167,-61.7833,10.0,,COOLIDGE FIELD ANTIGUA,,,78861,,AG\n"
    )
    hourly = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=_settings(), options=_options(drop_nulls))
    columns = [parameter.name_original for parameter in hourly.metadata["hourly"]["data"]]
    # `<element>_Quality_Code` beside each value (GH-2754): 1942-01-17 02:00 reads 1 for the temperature and for the
    # direction 999, so that the text of the sentinel follows the code. The file gives the direction the measurement
    # code C and source 220 too (GH-2925), which come between the two (`1,measurement:C,source:220,raw:999`)
    rows = [
        {
            "temperature": "23.5",
            "temperature_Quality_Code": "1",
            "wind_direction": "999",
            "wind_direction_Measurement_Code": "C",
            "wind_direction_Quality_Code": "1",
            "wind_direction_Source_Code": "220",
            "wind_speed": "0.0",
            "precipitation": "-9999",
        },
        {"temperature": "23.0", "wind_direction": "90", "wind_speed": "3.1", "precipitation": "0.2"},
        {"temperature": "24.0", "wind_direction": "999", "wind_speed": "4.1", "precipitation": "-9999"},
        # the reader maps `-None` to null in every column; this row pins that
        {"temperature": "-None", "wind_direction": "90", "wind_speed": "3.1", "precipitation": "0.2"},
        # "A direction of "000" is given for calm winds" (the documentation), which the files write 0 (GH-2794)
        {"temperature": "24.0", "wind_direction": "0", "wind_speed": "0.0", "precipitation": "0.0"},
    ]
    body = ghcnh_psv(
        "ACM00078861",
        columns,
        [(f"1942-01-17T{hour:02d}:00:00", row) for hour, row in zip((2, 3, 14, 15, 16), rows, strict=True)],
    )
    serve(monkeypatch, ghcn_api, {"ghcnh-station-list": stations, "GHCNh_ACM00078861": body})
    request = NoaaGhcnRequest(
        parameters=[("hourly", "data")],
        start=_day(1942, 1, 17),
        end=_day(1942, 1, 18),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return request.filter_by_station_id("ACM00078861").values().all().df


def _serve_meteofrance(
    monkeypatch: pytest.MonkeyPatch, resolution: str, dataset: str, title: str, rows: list[dict[str, str]]
) -> None:
    """Serve the one period file of a department, by the title of its resource, with these rows."""
    schema = list(observation_api._CLIMATE_SCHEMAS[resolution, dataset])  # noqa: SLF001
    lines = [";".join(schema)] + [";".join(row.get(column, "") for column in schema) for row in rows]
    body = gzip.compress("\n".join(lines).encode("utf8"))

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        url = url or args[0]
        listing = {"resources": [{"title": title, "url": f"https://example.invalid/{title}.csv.gz"}]}
        return File(url=url, content=BytesIO(json.dumps(listing).encode("utf8")), status=200)

    def download_files(urls: list[str], **_: object) -> list[File]:
        return [File(url=url, content=BytesIO(body), status=200) for url in urls]

    monkeypatch.setattr(observation_api, "download_file", download_file)
    monkeypatch.setattr(observation_api, "download_files", download_files)


def _meteofrance_observation_hourly(
    monkeypatch: pytest.MonkeyPatch,
    dataset: str,
    parameters: list[str],
    *,
    drop_nulls: bool,
) -> pl.DataFrame:
    # HOR_departement_07_periode_2020-2024 of data.gouv.fr: the descriptions of the hourly dataset give N = 9 for a sky
    # that could not be seen, and the audit of GH-2720 found a wind direction of 0 where there is none (and 999 in six
    # rows of 1965 to 1967); the rows are worded by the stub, with the validation code beside each value
    rows = [
        {"NUM_POSTE": "07005001", "AAAAMMJJHH": "2024010100", "T": "2.1", "N": "4", "DD": "250", "QN": "1", "QDD": "1"},
        {"NUM_POSTE": "07005001", "AAAAMMJJHH": "2024010101", "T": "2.0", "N": "9", "DD": "0", "QN": "1", "QDD": "1"},
        {"NUM_POSTE": "07005001", "AAAAMMJJHH": "2024010102", "T": "1.9", "N": "5", "DD": "999", "QN": "1", "QDD": "1"},
    ]
    _serve_meteofrance(monkeypatch, "hourly", dataset, "HOR_departement_07_periode_2020-2024", rows)
    request = MeteoFranceObservationRequest(
        parameters=[("hourly", dataset, parameter) for parameter in parameters],
        start=_day(2024, 1, 1),
        end=_day(2024, 1, 1, 3),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "hourly", dataset, "07005001").values().all().df


def _meteofrance_observation_daily(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # QUOT_departement_07_periode_2020-2024_RR-T-Vent: the daily DXI holds the code 0 (GH-2720), and the reader applies
    # 0 and 999 to it as to the hourly DD, so the stub adds the 999; the 400 is that of QUOT_departement_31 (31299001,
    # 2007-09-05: DXI = 400, FXI = 8.0, QDXI = 1, GH-2728), moved here; worded by the stub,
    # with the validation code beside each value
    rows = [
        {"NUM_POSTE": "07005001", "AAAAMMJJ": "20240101", "TN": "-1.0", "DXI": "250", "QDXI": "1"},
        {"NUM_POSTE": "07005001", "AAAAMMJJ": "20240102", "TN": "-0.5", "DXI": "0", "QDXI": "1"},
        {"NUM_POSTE": "07005001", "AAAAMMJJ": "20240103", "TN": "0.5", "DXI": "999", "QDXI": "1"},
        {"NUM_POSTE": "07005001", "AAAAMMJJ": "20240104", "TN": "1.5", "DXI": "400", "QDXI": "1"},
    ]
    _serve_meteofrance(monkeypatch, "daily", "core", "QUOT_departement_07_periode_2020-2024_RR-T-Vent", rows)
    request = MeteoFranceObservationRequest(
        parameters=[("daily", "core", "temperature_air_min_2m"), ("daily", "core", "wind_direction_gust_max")],
        start=_day(2024, 1, 1),
        end=_day(2024, 1, 4),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "daily", "core", "07005001").values().all().df


def _meteofrance_observation_hourly_core(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    return _meteofrance_observation_hourly(
        monkeypatch, "core", ["temperature_air_2m", "wind_direction_last_10min"], drop_nulls=drop_nulls
    )


def _meteofrance_observation_hourly_others(
    monkeypatch: pytest.MonkeyPatch,
    drop_nulls: bool = True,  # noqa: FBT001, FBT002
) -> pl.DataFrame:
    return _meteofrance_observation_hourly(monkeypatch, "others", ["cloud_cover_total"], drop_nulls=drop_nulls)


def _meteofrance_synop(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # synop_2024.csv.gz: ABBEVILLE 2024-01-01T18:00Z has rr6=-0.1 beside rr1=0.0, CHASSIRON 2024-01-03T06:00Z has n=101;
    # a calm is dd=0 beside ff=0 (3495 rows, all with ff=0) and north is dd=360 (3230 rows), as the WMO table has it;
    # the 400 is the file of 1996's own (14 rows, DUMONT D'URVILLE and EUROPA, dd=400 beside ff=1 or 2, GH-2873), here
    # moved to 07005 at 2024-01-01T23:00Z
    schema = list(synop_api._SYNOP_CSV_SCHEMA)  # noqa: SLF001
    rows = [
        {
            "geo_id_wmo": "07005",
            "validity_time": "2024-01-01T18:00:00Z",
            "rr1": "0.0",
            "rr6": "-0.1",
            "n": "90",
            "dd": "0",
            "ff": "0",
        },
        {
            "geo_id_wmo": "07005",
            "validity_time": "2024-01-01T21:00:00Z",
            "rr1": "0.4",
            "rr6": "1.2",
            "n": "101",
            "dd": "360",
            "ff": "2",
        },
        {
            "geo_id_wmo": "07005",
            "validity_time": "2024-01-01T23:00:00Z",
            "dd": "400",
            "ff": "1",
        },
    ]
    lines = [";".join(schema)] + [";".join(row.get(column, "") for column in schema) for row in rows]
    serve(monkeypatch, synop_api, {"synop_2024": gzip.compress("\n".join(lines).encode("utf8"))})
    request = MeteoFranceSynopRequest(
        parameters=[
            ("subdaily", "data", "precipitation_amount_last_1h"),
            ("subdaily", "data", "precipitation_amount_last_6h"),
            ("subdaily", "data", "cloud_cover_total"),
            ("subdaily", "data", "wind_direction_last_10min"),
        ],
        start=_day(2024, 1, 1),
        end=_day(2024, 1, 2),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "subdaily", "data", "07005").values().all().df


def _dwd_derived_radiation(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # stundenwerte_duett_FG_18001_akt.zip (the 2025-04-09 to 2026-10-10 release, read 2026-10-12): the hours
    # without a reading write `-999` in both columns, e.g. 2025-04-17 18:00 `18001;2025041718;  500; -999;-999;eor`
    product = (
        "STATIONS_ID;MESS_DATUM;QN_952;FG_DUETT;FG_UN_DUETT;eor\n"
        "      18001;2025040900;  500;  103;   10;eor\n"
        "      18001;2025040901;  500; -999;-999;eor\n"
        # the derived datasets add -9999 to the -999 of the descriptions
        "      18001;2025040902;  500;-9999;-9999;eor\n"
    )
    monkeypatch.setattr(
        dwd_derived_api,
        "create_file_list_for_climate_derived",
        lambda *args, **kwargs: pl.Series(["https://example.invalid/produkt.zip"]),  # noqa: ARG005
    )
    monkeypatch.setattr(
        dwd_derived_api,
        "download_climate_derived_data",
        lambda *args, **kwargs: [  # noqa: ARG005
            File(url="https://example.invalid/produkt.txt", content=BytesIO(product.encode("latin-1")), status=200)
        ],
    )
    request = DwdDerivedRequest(
        parameters=[("hourly", "radiation_global")],
        periods={Period.RECENT},
        start=_day(2025, 4, 9),
        end=_day(2025, 4, 9, 23),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "hourly", "radiation_global", "18001").values().all().df


_KML = "http://www.opengis.net/kml/2.2"
_DWD_KML = "https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd"


def _forecast_kml(station_id: str, elements: dict[str, str]) -> bytes:
    """Build the document `KMLReader.fetch` hands back: three hours of a run and one station's elements.

    Each element is the text of its `dwd:value`: the values separated by blanks, `-` for one the run does not have.
    """
    steps = "".join(f"<dwd:TimeStep>2026-10-10T{hour}:00:00.000Z</dwd:TimeStep>" for hour in (10, 11, 12))
    forecasts = "".join(
        f'<dwd:Forecast dwd:elementName="{name}"><dwd:value>{values}</dwd:value></dwd:Forecast>'
        for name, values in elements.items()
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<kml:kml xmlns:kml="{_KML}" xmlns:dwd="{_DWD_KML}"><kml:Document>'
        "<kml:ExtendedData><dwd:ProductDefinition><dwd:Issuer>DWD</dwd:Issuer><dwd:ProductID>MOSMIX</dwd:ProductID>"
        "<dwd:GeneratingProcess>L</dwd:GeneratingProcess><dwd:IssueTime>2026-10-10T09:00:00.000Z</dwd:IssueTime>"
        f"<dwd:ForecastTimeSteps>{steps}</dwd:ForecastTimeSteps></dwd:ProductDefinition></kml:ExtendedData>"
        f"<kml:Placemark><kml:name>{station_id}</kml:name><kml:ExtendedData>{forecasts}</kml:ExtendedData>"
        "</kml:Placemark></kml:Document></kml:kml>"
    ).encode()


def _dwd_mosmix(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # the file writes `-` for a value the run does not have, in the blank-separated list of an element; the
    # temperature is in Kelvin, and the second hour of it and the third of the dew point are missing
    kml = _forecast_kml("01001", {"TTT": "275.15 - 276.15", "Td": "273.15 274.15 -"})
    monkeypatch.setattr(
        dwd_mosmix_api.DwdMosmixValues,
        "get_url_for_date",
        lambda *args, **kwargs: "https://example.invalid/MOSMIX_S_2026101009_240.kmz",  # noqa: ARG005
    )
    monkeypatch.setattr(dwd_mosmix_api.KMLReader, "fetch", lambda _self, _url: BytesIO(kml))
    request = DwdMosmixRequest(
        parameters=[("hourly", "small", "ttt"), ("hourly", "small", "td")],
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "hourly", "small", "01001").values().all().df


def dwd_dmo_values(
    monkeypatch: pytest.MonkeyPatch,
    elements: dict[str, str],
    parameters: list[tuple[str, str, str]],
    lead_time: str = "short",
    options: Options | None = None,
) -> pl.DataFrame:
    """Give the values of station 01001 from a DMO run that holds the given elements, as a caller gets them."""
    kml = _forecast_kml("01001", elements)
    monkeypatch.setattr(
        dwd_dmo_api.DwdDmoValues,
        "get_url_for_date",
        lambda *args, **kwargs: "https://example.invalid/ptp_gdmog_01001_078_1_100000.kmz",  # noqa: ARG005
    )
    monkeypatch.setattr(dwd_dmo_api.KMLReader, "fetch", lambda _self, _url: BytesIO(kml))
    request = DwdDmoRequest(
        parameters=parameters,
        lead_time=lead_time,
        settings=_settings(),
        options=options or _options(drop_nulls=True),
    )
    return stations_result(request, "hourly", "icon", "01001").values().all().df


def _dwd_dmo(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # the same KML as MOSMIX's, with the same `-`
    return dwd_dmo_values(
        monkeypatch,
        {"TTT": "275.15 - 276.15", "Td": "273.15 274.15 -"},
        [("hourly", "icon", "ttt"), ("hourly", "icon", "td")],
        options=_options(drop_nulls),
    )


def _dwd_poi(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # a station file as DWD serves it (10147-BEOB.csv): English names, units and German descriptions, then the
    # reports, newest first, `,` for a decimal and `---` for a report without the value
    wind = "mean_wind_direction_during_last_10 min_at_10_meters_above_ground"
    temperature = "dry_bulb_temperature_at_2_meter_above_ground"
    csv = (
        f"surface observations;Parameter description;cloud_cover_total;{temperature};{wind}\n"
        "10147;Unit;%;Grad C;Grad\n"
        "Datum;Uhrzeit (UTC);Wolkenbedeckung;Temperatur (2m);Windrichtung\n"
        "10.10.26;20:00;100;15,3;360\n"
        "10.10.26;19:00;---;15,4;250\n"
        # a percent that reads 113 (9 oktas x 12.5, sky obscured) or 126 (03953, 13367, 2026-10-12)
        "10.10.26;18:00;113;15,5;250\n"
        # the direction is 0 for a calm or a variable wind, 360 is north (GH-2794)
        "10.10.26;17:00;126;15,6;0\n"
    ).encode("latin-1")
    serve(monkeypatch, dwd_poi_api, {"10147-BEOB.csv": csv})
    request = DwdPoiRequest(parameters=[("hourly", "data")], settings=_settings(), options=_options(drop_nulls))
    return stations_result(request, "hourly", "data", "10147").values().all().df


def _dwd_swsmos(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # a run file as DWD serves it (swsmos_LATEST_opendata.csv.bz2, read 2026-10-12): the header, the run's own
    # timestamp, then the rows. The file read had no cell that is no number, in any of its 12 columns, so the text
    # of the second row is worded by the stub: the reader takes a text that is no number for none
    raw = (
        b"ID;Lat;Lon;YYYYMMDDHHmm;TL;TS\n"
        b"202610120500\n"
        b"A006;54.889156;8.908735;202610120600;6.2;4.4\n"
        b"A006;54.889156;8.908735;202610120700;---;5.1\n"
    )
    run = dwd_swsmos_api._read_run_csv(bz2.compress(raw))  # noqa: SLF001
    monkeypatch.setattr(dwd_swsmos_api.DwdSwsmosValues, "_run_frame", lambda _self, _settings: run)
    request = DwdSwsmosRequest(parameters=[("hourly", "data")], settings=_settings(), options=_options(drop_nulls))
    return stations_result(request, "hourly", "data", "A006").values().all().df


def _eccc_daily(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # climate-daily as api.weather.gc.ca answers for ALERT (STN_ID=1731, read 2026-10-12): a day below the 31 km/h the
    # stations report from has 0 for the speed and 0 for the direction, no flag (1975-07-01, 1975-07-02), where the
    # bulk CSV of the day writes "<31"; 1975-07-06 is a gust of 60 km/h from 200 degrees (the direction is in tens of
    # degrees)
    rows = [
        {"LOCAL_DATE": "1975-07-01 00:00:00", "MAX_TEMPERATURE": 5, "SPEED_MAX_GUST": 0, "DIRECTION_MAX_GUST": 0},
        {"LOCAL_DATE": "1975-07-02 00:00:00", "MAX_TEMPERATURE": 6.7, "SPEED_MAX_GUST": 0, "DIRECTION_MAX_GUST": 0},
        {"LOCAL_DATE": "1975-07-06 00:00:00", "MAX_TEMPERATURE": 11.1, "SPEED_MAX_GUST": 60, "DIRECTION_MAX_GUST": 20},
    ]
    body = json.dumps({"features": [{"type": "Feature", "properties": row} for row in rows]}).encode()
    serve(monkeypatch, eccc_api, {"climate-daily": body})
    request = EcccObservationRequest(
        parameters=[("daily", "data")],
        start=_day(1975, 7, 1),
        end=_day(1975, 7, 6),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "daily", "data", "1731").values().all().df


def _eccc_hourly(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # climate-hourly as api.weather.gc.ca answers for Toronto Intl A (STN_ID=51459, read 2026-10-12): the direction is
    # in tens of degrees, 31 at 2019-01-01 08:00Z, and 0 beside a speed of 0 at 2019-01-08 22:00Z, which the glossary
    # words "A value of zero (0) denotes a calm wind" (GH-2794)
    rows = [
        {"UTC_DATE": "2019-01-01T08:00:00", "WIND_DIRECTION": 31, "WIND_SPEED": 29},
        {"UTC_DATE": "2019-01-08T22:00:00", "WIND_DIRECTION": 0, "WIND_SPEED": 0},
    ]
    body = json.dumps({"features": [{"type": "Feature", "properties": row} for row in rows]}).encode()
    serve(monkeypatch, eccc_api, {"climate-hourly": body})
    request = EcccObservationRequest(
        parameters=[("hourly", "data", "wind_direction_last_2min"), ("hourly", "data", "wind_speed")],
        start=_day(2019, 1, 1),
        end=_day(2019, 1, 9),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "hourly", "data", "51459").values().all().df


def _aemet_daily(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # worded by the stub, as the API needs a key: the daily endpoint writes its numbers as text with a decimal
    # comma, the wind direction in tens of degrees with 99 for "calm/variable" (the reader's own comment), and the
    # reader takes a text that is no number (the second precipitation) for none
    records = [
        {"fecha": "2024-01-01", "tmed": "5,3", "prec": "0,0", "dir": "23", "velmedia": "3,1"},
        {"fecha": "2024-01-02", "tmed": "6,0", "prec": "Ip", "dir": "99", "velmedia": "2,0"},
    ]
    payload = json.dumps(records).encode("latin-1")
    monkeypatch.setattr(aemet_api, "_fetch_datos", lambda *args, **kwargs: payload)  # noqa: ARG005
    request = AemetObservationRequest(
        parameters=[("daily", "data")],
        start=_day(2024, 1, 1),
        end=_day(2024, 1, 2),
        settings=_settings(auth={"aemet": "stub"}),
        options=_options(drop_nulls),
    )
    return stations_result(request, "daily", "data", "3195").values().all().df


def _metoffice_daily_rain(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # the archive needs a CEDA login, so this is worded after what the reader takes for the files: BADC-CSV, a table
    # between a bare `data` and an `end data` line, and `NA` for a value (and its flag) a report does not have
    def badc(columns: str, rows: str) -> bytes:
        return f"Conventions,G,BADC-CSV,1\ndata\n{columns}\n{rows}end data\n".encode()

    stations = badc(
        "src_id,station_name,station_file_name,historic_county,authority,"
        "station_latitude,station_longitude,station_elevation,first_year,last_year",
        "00001,FOULA,foula,shetland,Met Office,60.154,-2.074,22,1989,2003\n",
    )
    values = badc(
        "ob_date,ob_day_cnt,prcp_amt,prcp_amt_q",
        "2000-01-01 00:00:00,1,3.7,2576\n2000-01-02 00:00:00,1,NA,NA\n",
    )

    def download(_self: object, url: str, *_args: object, **_kwargs: object) -> bytes | None:
        if "station-metadata" in url:
            return stations
        return values if "qcv-1" in url else None

    monkeypatch.setattr(metoffice_api.MetOfficeObservationValues, "_token", lambda _self, _settings: "token")
    monkeypatch.setattr(metoffice_api.MetOfficeObservationValues, "_download", download)
    monkeypatch.setattr(metoffice_api, "latest_release_version", lambda *_args, **_kwargs: "202507")
    request = MetOfficeObservationRequest(
        parameters=[("daily", "rain")],
        start=_day(2000, 1, 1),
        end=_day(2000, 1, 2),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "daily", "rain", "00001").values().all().df


def _metno_frost_hourly(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # the API needs a client id, so this is worded after the element descriptions Frost publishes, which state the codes
    # of the reader: a cloud cover of 9 (and -3) could not be estimated, and a snow thickness of -1 is no snow
    payload = {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": f"2020-01-01T0{hour}:00:00.000Z",
                "observations": [
                    {"elementId": "cloud_area_fraction", "value": cloud, "qualityCode": 0},
                    {"elementId": "surface_snow_thickness", "value": snow, "qualityCode": 0},
                ],
            }
            for hour, (cloud, snow) in enumerate([(4, 12.0), (9, -1.0)])
        ],
    }
    serve(monkeypatch, frost_api, {"observations/v0.jsonld": json.dumps(payload).encode()})
    request = MetnoFrostRequest(
        parameters=[("hourly", "data", "cloud_cover_total"), ("hourly", "data", "snow_depth")],
        start=_day(2020, 1, 1),
        end=_day(2020, 1, 1, 1),
        settings=_settings(auth={"metno_frost": "stub"}),
        options=_options(drop_nulls),
    )
    return stations_result(request, "hourly", "data", "SN18700").values().all().df


def _knmi_netcdf(values: dict[str, float]) -> bytes:
    """Write the file KNMI serves for one timestamp: a variable per name, laid out as (station, time), one station."""
    h5py = pytest.importorskip("h5py")
    h5netcdf = pytest.importorskip("h5netcdf")

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "knmi.nc"
        with h5netcdf.File(path, "w") as file:
            file.dimensions = {"station": 1, "time": 1}
            station = file.create_variable("station", ("station",), dtype=h5py.string_dtype())
            station[:] = ["0-20000-0-06260"]
            for name, value in values.items():
                variable = file.create_variable(name, ("station", "time"), dtype="f8")
                variable[:] = [[value]]
        return path.read_bytes()


def _knmi_serve(monkeypatch: pytest.MonkeyPatch, payloads: dict[str, bytes]) -> None:
    """Serve the file of each timestamp, by the part of its filename that names it."""
    monkeypatch.setattr(
        knmi_api,
        "_fetch_netcdf",
        lambda _dataset, _version, filename, _settings: next(
            payload for moment, payload in payloads.items() if moment in filename
        ),
    )


def _knmi_daily(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # a file per day for the whole network (here one station): a missing observation is the NaN _FillValue and a trace
    # of precipitation a -1 in RH
    _knmi_serve(
        monkeypatch,
        {
            "20240101": _knmi_netcdf({"TG": 3.2, "RH": 1.4}),
            "20240102": _knmi_netcdf({"TG": float("nan"), "RH": -1.0}),
        },
    )
    request = KnmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m"), ("daily", "data", "precipitation_amount")],
        start=_day(2024, 1, 1),
        end=_day(2024, 1, 2),
        settings=_settings(auth={"knmi": "stub"}),
        options=_options(drop_nulls),
    )
    return stations_result(request, "daily", "data", "06260").values().all().df


def _knmi_hourly(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # DD is "360=north, 90=east, 180=south, 270=west, 0=calm, 990=variable" (GH-2850): a bearing at 00 UTC, the code for
    # a variable wind at 01 UTC (hourly-observations-validated-20261012-08.nc has Horst at 990 with FF 1.0 m/s) and the
    # one for a calm at 02 UTC; a missing temperature is the NaN _FillValue
    _knmi_serve(
        monkeypatch,
        {
            "20240101-00": _knmi_netcdf({"T": 3.2, "DD": 250.0}),
            "20240101-01": _knmi_netcdf({"T": float("nan"), "DD": 990.0}),
            "20240101-02": _knmi_netcdf({"T": 3.0, "DD": 0.0}),
        },
    )
    request = KnmiObservationRequest(
        parameters=[("hourly", "data", "temperature_air_2m"), ("hourly", "data", "wind_direction_last_10min")],
        start=_day(2024, 1, 1),
        end=_day(2024, 1, 1, 2),
        settings=_settings(auth={"knmi": "stub"}),
        options=_options(drop_nulls),
    )
    return stations_result(request, "hourly", "data", "06260").values().all().df


def _fmi_hourly(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # the WFS answers a flat list of Time / ParameterName / ParameterValue triples: `NaN` for a reading it does not have
    # and, for the precipitation and the snow depth, `-1.0` for none (the fixture of tests/provider/fmi)
    def element(hour: int, name: str, value: str) -> str:
        return (
            "<wfs:member><BsWfs:BsWfsElement>"
            f"<BsWfs:Time>2024-01-01T{hour:02d}:00:00Z</BsWfs:Time><BsWfs:ParameterName>{name}</BsWfs:ParameterName>"
            f"<BsWfs:ParameterValue>{value}</BsWfs:ParameterValue></BsWfs:BsWfsElement></wfs:member>"
        )

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:BsWfs="http://xml.fmi.fi/schema/wfs/2.0">'
        + element(0, "t2m", "-3.5")
        + element(0, "r_1h", "0.4")
        + element(1, "t2m", "NaN")
        + element(1, "r_1h", "-1.0")
        # the direction is 0.0 for a calm wind and 360.0 for north (checked on 15 stations, 2026-10-12; GH-2794)
        + element(0, "wd_10min", "250.0")
        + element(1, "wd_10min", "0.0")
        + "</wfs:FeatureCollection>"
    ).encode()
    serve(monkeypatch, fmi_api, {"opendata.fmi.fi": body})
    request = FmiObservationRequest(
        parameters=[("hourly", "data")],
        start=_day(2024, 1, 1),
        end=_day(2024, 1, 1, 1),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "hourly", "data", "100971").values().all().df


def _nws_hourly(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # api.weather.gov/stations/KBOS/observations (read 2026-10-12): 12:54Z is the METAR `36005KT`, a direction of 360,
    # and 14:54Z `00000KT`, a calm, which the endpoint gives as a direction of 0 beside a speed of 0 (GH-2794). The
    # METAR carries the `precipitationLastHour` key and a 5-minute ASOS row, which the endpoint serves beside it at the
    # minutes 0, 5, 10, ..., does not; the rows at 12:55 and 15:00 are the 5-minute rows `hourly` leaves out (GH-2857)
    def observation(timestamp: str, direction: int, speed: float, *, report: bool) -> dict[str, Any]:
        properties = {
            "station": "https://api.weather.gov/stations/KBOS",
            "timestamp": f"2026-10-12T{timestamp}:00+00:00",
            "windDirection": {"unitCode": "wmoUnit:degree_(angle)", "value": direction, "qualityControl": "V"},
            "windSpeed": {"unitCode": "wmoUnit:km_h-1", "value": speed, "qualityControl": "V"},
        }
        if report:
            properties["precipitationLastHour"] = {"unitCode": "wmoUnit:mm", "value": None, "qualityControl": "Z"}
        return {"properties": properties}

    features = [
        observation("12:54", 360, 9.36, report=True),
        observation("12:55", 350, 11.1, report=False),
        observation("14:54", 0, 0, report=True),
        observation("15:00", 0, 0, report=False),
    ]
    # the endpoint names a cursor on the oldest row in every page, the last one too (GH-2994); a page of four rows is
    # short, and the walk ends with it
    cursor = "eyJzIjoiMjAyNi0xMC0xMlQxMjo1NDowMCswMDowMCJ9"
    pagination = {"next": f"https://api.weather.gov/stations/KBOS/observations?cursor={cursor}"}
    serve(
        monkeypatch, nws_api, {"/observations": json.dumps({"features": features, "pagination": pagination}).encode()}
    )
    request = NwsObservationRequest(
        parameters=[("hourly", "data")],
        start=_day(2026, 10, 12),
        end=_day(2026, 10, 13),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "hourly", "data", "KBOS").values().all().df


def _smhi_hourly(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # parameter 3 of station 188790 (Abisko Aut) as SMHI writes it (read 2026-10-12), "Vindriktning, medelvärde 10 min":
    # 0 at 2019-01-18 04:00, where the wind speed is 0.0, and 360 for north at 2019-03-15 11:00 (GH-2794)
    csv = (
        "Datum;Tid (UTC);Vindriktning;Kvalitet\n"
        "2019-01-18;03:00:00;208;G\n"
        "2019-01-18;04:00:00;0;G\n"
        "2019-03-15;11:00:00;360;G\n"
    )
    serve(monkeypatch, smhi_api, {"parameter/3/station/188790/period": csv.encode()})
    request = SmhiObservationRequest(
        parameters=[("hourly", "data", "wind_direction_last_10min")],
        start=_day(2019, 1, 18),
        end=_day(2019, 3, 16),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "hourly", "data", "188790").values().all().df


def _dmi_hourly(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # stationValue of 06070 (read 2026-10-12): the mean wind direction of 2020-02-14 03:00 is 0 beside a mean wind speed
    # of 0, which is a calm (GH-2794); the 06:00 hour is made up. The 0 beside a speed above 0, which stays, is pinned
    # by tests/provider/dmi
    rows = [
        ("mean_wind_dir", "2020-02-14T03:00:00+00:00", 0.0),
        ("mean_wind_speed", "2020-02-14T03:00:00+00:00", 0.0),
        ("mean_wind_dir", "2020-02-14T06:00:00+00:00", 250.0),
        ("mean_wind_speed", "2020-02-14T06:00:00+00:00", 4.1),
    ]
    features = [
        {
            "properties": {
                "parameterId": parameter,
                "from": start,
                "to": (dt.datetime.fromisoformat(start) + dt.timedelta(hours=1)).isoformat(),
                "value": value,
            }
        }
        for parameter, start, value in rows
    ]
    serve(monkeypatch, dmi_api, {"stationValue": json.dumps({"features": features}).encode()})
    request = DmiObservationRequest(
        parameters=[("hourly", "data")],
        start=_day(2020, 2, 14),
        end=_day(2020, 2, 14, 7),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "hourly", "data", "06070").values().all().df


def _dmi_annual(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # stationValue of 04339, `acc_precip` of `timeResolution=year` (read 2026-10-15): 1343.1 mm for 2013 is a reading,
    # 9574.3 mm for 2014 and 6026.5 mm for 2015 are sums no gauge produced (DMI validated 3,291.3 mm at most in a
    # year of any station), above the 4,000 mm bound of a year's precipitation (GH-2797). DMI marks both
    # `validity: false`
    rows = [
        ("2013-01-01T06:00:00+00:00", "2014-01-01T06:00:00+00:00", 1343.1, "none"),
        ("2014-01-01T06:00:00+00:00", "2015-01-01T06:00:00+00:00", 9574.3, "manual"),
        ("2015-01-01T06:00:00+00:00", "2016-01-01T06:00:00+00:00", 6026.5, "none"),
    ]
    features = [
        {
            "properties": {
                "parameterId": "acc_precip",
                "from": start,
                "to": end,
                "value": value,
                "qcStatus": qc_status,
                "validity": value < 3_000,
            }
        }
        for start, end, value, qc_status in rows
    ]
    serve(monkeypatch, dmi_api, {"stationValue": json.dumps({"features": features}).encode()})
    request = DmiObservationRequest(
        parameters=[("annual", "data")],
        start=_day(2013, 1, 1),
        end=_day(2015, 1, 1),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "annual", "data", "04339").values().all().df


def _rmi_daily(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # `aws:aws_1day` of station 6414 (read 2026-10-15): 2003-08-05 is a day of readings, on 2003-08-06 the mean is
    # 110.26 and the maximum 4021 degrees, which no thermometer read, and `validated` is false for both (GH-2797). The
    # other attributes are left out, the reader taking what it maps. Station 6477, 2016-12-24 (read 2026-10-17): the
    # sunshine reads 1,440 minutes, a full day in December, inside every range, from a sensor that was stuck from
    # 2016-04-30 to 2017-05-31 (GH-3031), `validated` false; the stub serves it for the station of the rest
    day = {
        "temp_avg": 24.03,
        "temp_max": 31.6,
        "temp_min": 16.14,
        "wind_gusts_speed": 7.65,
        "qc_flags": json.dumps({"validated": {"TEMP_AVG": False, "TEMP_MAX": False, "TEMP_MIN": False}}),
    }
    features = [
        {"properties": {"timestamp": "2003-08-05T00:00:00Z", **day}},
        {
            "properties": {
                "timestamp": "2003-08-06T00:00:00Z",
                **day,
                "temp_avg": 110.26,
                "temp_max": 4021,
                "temp_min": 16.84,
                "wind_gusts_speed": 5.24,
            }
        },
    ]
    features.append(
        {
            "properties": {
                "timestamp": "2016-12-24T00:00:00Z",
                "temp_avg": 7.0,
                "sun_duration": 1440,
                "qc_flags": json.dumps({"validated": {"TEMP_AVG": False, "SUN_DURATION": False}}),
            }
        }
    )
    body = json.dumps({"numberMatched": len(features), "features": features}).encode()
    serve(monkeypatch, rmi_api, {"aws:aws_1day": body})
    request = RmiObservationRequest(
        parameters=[("daily", "data")],
        start=_day(2003, 8, 5),
        end=_day(2016, 12, 25),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "daily", "data", "6477").values().all().df


def _imgw_hydrology(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # codz_2023.zip (read 2026-10-12): `;` separated, a station per row with the stage, the discharge and the water
    # temperature, which reads 99.9 in the first rows of the file (149180020, 2023-01-01 to 2023-01-03). The stage's
    # 9999 and the discharge's 99999.999 are not in those rows: they are worded after the reader, which nulls those
    # three texts
    csv = (
        "149180020;CHALUPKI;Odra (1);2023;01;01;88;14.200;4.1;11\n"
        "149180020;CHALUPKI;Odra (1);2023;01;02;89;13.700;99.9;11\n"
        "149180020;CHALUPKI;Odra (1);2023;01;03;9999;99999.999;99.9;11\n"
        # 99.900 m3/s is a discharge, and 99.9 is the sentinel of the temperature column alone (GH-2759)
        "149180020;CHALUPKI;Odra (1);2023;01;04;90;99.900;9999;11\n"
    )
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("codz_2023.csv", csv.encode("latin-1"))
    monkeypatch.setattr(
        imgw_hydrology_api,
        "list_files_for_interval",
        lambda *args, **kwargs: ["https://example.invalid/codz_2023.zip"],  # noqa: ARG005
    )
    monkeypatch.setattr(
        imgw_hydrology_api,
        "download_files",
        lambda *args, **kwargs: [  # noqa: ARG005
            File(url="https://example.invalid/codz_2023.zip", content=BytesIO(archive.getvalue()), status=200)
        ],
    )
    request = ImgwHydrologyRequest(
        parameters=[("daily", "hydrology")],
        start=_day(2022, 11, 1),
        end=_day(2022, 11, 4),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "daily", "hydrology", "149180020").values().all().df


STUBS = [
    ValueStub(
        "ipma/observation hourly/data",
        _ipma,
        reading=("temperature_air_mean_2m", 21.5),
        # the humidity is converted from percent to a decimal on its way
        sentinels=(("temperature_air_mean_2m", -99.0), ("humidity_relative", -0.99), ("precipitation_amount", -99.0)),
        tokens=(
            ("temperature_air_mean_2m", "-99.0", None),
            ("humidity_relative", "-99.0", None),
            ("precipitation_amount", "-99.0", None),
            ("wind_direction", "-99.0", None),
            # the calm code, which is no direction
            ("wind_direction", "0", None),
        ),
        empty_at=_day(2026, 10, 10, 13),
    ),
    ValueStub(
        "dwd/observation daily/climate_summary",
        _dwd_daily_climate_summary,
        reading=("temperature_air_mean_2m", 2.9),
        sentinels=(("temperature_air_mean_2m", -999.0), ("precipitation_amount", -999.0)),
        tokens=(("temperature_air_mean_2m", "-999", None), ("precipitation_amount", "-999", None)),
        empty_at=_day(2025, 1, 2),
    ),
    ValueStub(
        "dwd/observation hourly/moisture",
        _dwd_hourly_moisture,
        reading=("temperature_air_2m", -0.1),
        sentinels=(
            ("humidity_absolute", -99.9),
            ("humidity_relative", -0.999),
            ("pressure_vapor", -99.9),
            ("temperature_dew_point_2m", -99.9),
            ("temperature_wet_2m", -99.9),
        ),
        tokens=(
            ("humidity_absolute", "-99.9", None),
            ("humidity_relative", "-99.9", None),
            # the pressure of a file that holds one value, null with the text the file wrote (GH-2699)
            ("pressure_air_site", "995.9", None),
            ("pressure_vapor", "-99.9", None),
            ("temperature_dew_point_2m", "-99.9", None),
            ("temperature_wet_2m", "-99.9", None),
        ),
    ),
    ValueStub(
        "dwd/observation hourly/wind",
        _dwd_hourly_wind,
        reading=("wind_direction", 250.0),
        sentinels=(("wind_direction", 990.0), ("wind_direction", 0.0)),
        tokens=(("wind_direction", "990", None), ("wind_direction", "0", None)),
    ),
    ValueStub(
        "dwd/observation hourly/wind_synop",
        _dwd_hourly_wind_synop,
        reading=("wind_direction", 360.0),
        sentinels=(("wind_direction", 0.0),),
        tokens=(("wind_direction", "0", None),),
    ),
    ValueStub(
        "dwd/observation subdaily/wind",
        _dwd_subdaily_wind,
        # 24 of the 32-point rose is a west wind, 270 degrees (GH-2808)
        reading=("wind_direction", 270.0),
        sentinels=(("wind_direction", 0.0),),
        tokens=(("wind_direction", "0", None),),
    ),
    ValueStub(
        "dwd/observation 10_minutes/wind",
        _dwd_10_minutes_wind,
        # no sentinel: a 0 beside a wind that blows is a bearing here
        reading=("wind_direction", 360.0),
        tokens=(("wind_direction", "0", None),),
    ),
    ValueStub(
        "dwd/observation 10_minutes/urban_wind",
        _dwd_10_minutes_urban_wind,
        reading=("wind_direction", 360.0),
        sentinels=(("wind_direction", 0.0),),
        tokens=(("wind_direction", "0", None),),
    ),
    ValueStub(
        "dwd/observation hourly/urban_wind",
        _dwd_hourly_urban_wind,
        reading=("wind_direction", 360.0),
        sentinels=(("wind_direction", 0.0),),
        tokens=(("wind_direction", "0", None),),
    ),
    ValueStub(
        "dwd/observation 10_minutes/urban_solar",
        _dwd_10_minutes_urban_solar,
        # hours in the file, seconds in the output: 0.17 h
        reading=("sunshine_duration", 612.0),
        sentinels=(("radiation_global", -999.0), ("sunshine_duration", -999.0)),
        tokens=(("radiation_global", "-999", None), ("sunshine_duration", "-999", None)),
    ),
    ValueStub(
        "dwd/observation 10_minutes/wind_extreme",
        _dwd_10_minutes_extreme_wind,
        reading=("wind_gust_max", 4.1),
        tokens=(("wind_direction_gust_max", "0", None),),
    ),
    ValueStub(
        "dwd/observation hourly/weather_phenomena",
        _dwd_hourly_weather_phenomena,
        reading=("weather", 61.0),
        sentinels=(("weather", -1.0),),
        tokens=(("weather", "-1", None),),
    ),
    ValueStub(
        "dwd/observation hourly/precipitation",
        _dwd_hourly_precipitation,
        reading=("precipitation_amount", 0.4),
        sentinels=(("precipitation_form", 9.0),),
        tokens=(("precipitation_form", "9", None),),
    ),
    ValueStub(
        "dwd/observation hourly/cloudiness",
        _dwd_hourly_cloudiness,
        reading=("cloud_cover_total", 0.5),
        # in eighths the -1 converts to -0.125 of the sky
        sentinels=(("cloud_cover_total", -0.125),),
        tokens=(("cloud_cover_total", "-1", None),),
    ),
    ValueStub(
        "geosphere/observation daily/data",
        _geosphere_daily,
        reading=("precipitation_amount", 0.3),
        sentinels=(("precipitation_amount", -1.0), ("snow_depth_manual", -1.0)),
        # a day without precipitation or snow reads 0.0, and the code stays beside it as the source writes it
        tokens=(("precipitation_amount", "-1.0", 0.0), ("snow_depth_manual", "-1", 0.0)),
    ),
    ValueStub(
        "geosphere/observation hourly/data",
        _geosphere_hourly,
        reading=("wind_direction", 38.0),
        sentinels=(("wind_direction", 0.0),),
        tokens=(("wind_direction", "0", None),),
    ),
    ValueStub(
        "noaa/ghcn hourly/data",
        _ghcn_hourly,
        reading=("wind_direction", 90.0),
        sentinels=(
            ("wind_direction", 999.0),
            ("wind_direction", 0.0),
            ("precipitation_amount_since_last_routine_report", -9999.0),
        ),
        tokens=(
            ("wind_direction", "999", None),
            ("wind_direction", "0", None),
            ("precipitation_amount_since_last_routine_report", "-9999", None),
            ("temperature_air_2m", "-None", None),
        ),
    ),
    ValueStub(
        "metoffice/observation daily/rain",
        _metoffice_daily_rain,
        reading=("precipitation_amount", 3.7),
        tokens=(("precipitation_amount", "NA", None),),
        empty_at=_day(2000, 1, 2),
    ),
    ValueStub(
        "metno/frost hourly/data",
        _metno_frost_hourly,
        reading=("cloud_cover_total", 0.5),
        # the cloud cover is converted from eighths to a decimal on its way
        sentinels=(("cloud_cover_total", 1.125), ("snow_depth", -1.0)),
        tokens=(("cloud_cover_total", "9", None), ("snow_depth", "-1", 0.0)),
    ),
    ValueStub(
        "knmi/observation daily/data",
        _knmi_daily,
        reading=("temperature_air_mean_2m", 3.2),
        sentinels=(("precipitation_amount", -1.0),),
        tokens=(("temperature_air_mean_2m", "NaN", None), ("precipitation_amount", "-1", 0.0)),
    ),
    ValueStub(
        "knmi/observation hourly/data",
        _knmi_hourly,
        reading=("wind_direction_last_10min", 250.0),
        # 0 is a calm and 990 a variable wind, neither a bearing (GH-2850)
        sentinels=(("wind_direction_last_10min", 0.0), ("wind_direction_last_10min", 990.0)),
        tokens=(
            ("temperature_air_2m", "NaN", None),
            ("wind_direction_last_10min", "0", None),
            ("wind_direction_last_10min", "990", None),
        ),
    ),
    ValueStub(
        "fmi/observation hourly/data",
        _fmi_hourly,
        reading=("temperature_air_2m", -3.5),
        sentinels=(("precipitation_amount", -1.0), ("wind_direction_last_10min", 0.0)),
        tokens=(
            ("temperature_air_2m", "NaN", None),
            ("precipitation_amount", "-1.0", 0.0),
            ("wind_direction_last_10min", "0.0", None),
        ),
    ),
    ValueStub(
        "nws/observation hourly/data",
        _nws_hourly,
        reading=("wind_direction_last_2min", 360.0),
        sentinels=(("wind_direction_last_2min", 0.0),),
        # a calm is no direction; the speed of 0 is a reading
        tokens=(("wind_direction_last_2min", "0", None),),
    ),
    ValueStub(
        "smhi/observation hourly/data",
        _smhi_hourly,
        reading=("wind_direction_last_10min", 360.0),
        sentinels=(("wind_direction_last_10min", 0.0),),
        tokens=(("wind_direction_last_10min", "0", None),),
    ),
    ValueStub(
        "dmi/observation hourly/data",
        _dmi_hourly,
        reading=("wind_direction", 250.0),
        sentinels=(("wind_direction", 0.0),),
        tokens=(("wind_direction", "0", None),),
    ),
    ValueStub(
        "dmi/observation annual/data",
        _dmi_annual,
        reading=("precipitation_amount", 1343.1),
        # a sum no gauge produced is no sentinel: it is outside the range of its parameter
        sentinels=(("precipitation_amount", 9574.3), ("precipitation_amount", 6026.5)),
        tokens=(("precipitation_amount", "9574.3", None), ("precipitation_amount", "6026.5", None)),
    ),
    ValueStub(
        "rmi/observation daily/data",
        _rmi_daily,
        reading=("temperature_air_min_2m", 16.84),
        sentinels=(("temperature_air_mean_2m", 110.26), ("temperature_air_max_2m", 4021.0)),
        tokens=(
            ("temperature_air_mean_2m", "110.26", None),
            ("temperature_air_max_2m", "4021", None),
            ("sunshine_duration", "1440", None),
        ),
    ),
    ValueStub(
        "imgw/hydrology daily/hydrology",
        _imgw_hydrology,
        reading=("discharge", 99.9),
        tokens=(
            ("stage", "9999", None),
            ("discharge", "99999.999", None),
            ("temperature_water", "99.9", None),
            ("temperature_water", "9999", None),
        ),
    ),
    ValueStub(
        "eccc/observation daily/data",
        _eccc_daily,
        reading=("wind_gust_max", 16.6667),
        # the gust is converted from km/h to m/s on its way
        sentinels=(("wind_gust_max", 0.0), ("wind_direction_gust_max", 0.0)),
        tokens=(("wind_gust_max", "0", None), ("wind_direction_gust_max", "0", None)),
    ),
    ValueStub(
        "eccc/observation hourly/data",
        _eccc_hourly,
        reading=("wind_direction_last_2min", 310.0),
        # a calm has no direction; the speed of 0 is a reading
        sentinels=(("wind_direction_last_2min", 0.0),),
        tokens=(("wind_direction_last_2min", "0", None),),
    ),
    ValueStub(
        "aemet/observation daily/data",
        _aemet_daily,
        reading=("temperature_air_mean_2m", 5.3),
        sentinels=(("wind_direction_gust_max", 990.0),),
        tokens=(("wind_direction_gust_max", "99", None), ("precipitation_amount", "Ip", None)),
    ),
    ValueStub(
        "dwd/derived hourly/radiation_global",
        _dwd_derived_radiation,
        reading=("radiation_global", 103.0),
        sentinels=(("radiation_global", -999.0), ("radiation_global", -9999.0)),
        tokens=(
            ("radiation_global", "-999", None),
            ("radiation_global_uncertainty", "-999", None),
            ("radiation_global", "-9999", None),
        ),
        empty_at=_day(2025, 4, 9, 1),
    ),
    ValueStub(
        "dwd/mosmix hourly/small",
        _dwd_mosmix,
        reading=("temperature_air_2m", 2.0),
        tokens=(("temperature_air_2m", "-", None), ("temperature_dew_point_2m", "-", None)),
    ),
    ValueStub(
        "dwd/dmo hourly/icon",
        _dwd_dmo,
        reading=("temperature_air_2m", 2.0),
        tokens=(("temperature_air_2m", "-", None), ("temperature_dew_point_2m", "-", None)),
    ),
    ValueStub(
        "dwd/poi hourly/data",
        _dwd_poi,
        reading=("temperature_air_2m", 15.3),
        # the percent is converted to a decimal on its way
        sentinels=(("cloud_cover_total", 1.13), ("cloud_cover_total", 1.26), ("wind_direction_last_10min", 0.0)),
        tokens=(
            ("cloud_cover_total", "---", None),
            ("cloud_cover_total", "113", None),
            ("cloud_cover_total", "126", None),
            ("wind_direction_last_10min", "0", None),
        ),
    ),
    ValueStub(
        "dwd/swsmos hourly/data",
        _dwd_swsmos,
        reading=("temperature_air_2m", 6.2),
        tokens=(("temperature_air_2m", "---", None),),
    ),
    # Météo-France's climatological files, as audited in GH-2719 and GH-2720. RR (6 minutes, daily, monthly) and RR1
    # (hourly) hold no code: the descriptions (the descriptif_champs files and the climatologie-*-descriptif PDFs)
    # define none, and 1.9 billion rows of 2158 raw files (the daily RR-T-Vent and the monthly files of every
    # department; the hourly ones of every department up to 1999 and from 2020, and of the overseas and a few mainland
    # ones for 2000 to 2019; the 6 minute ones likewise from 2020 and for 2000 to 2019) have a minimum of 0.0, no
    # negative value and nothing that is not a number. A trace is a 0.0: RR1 = 0.0 comes with a precipitation duration
    # DRR1 > 0 in 414,235 hourly rows of 2020 to 2024. DD and DXY (hourly) and DXI (daily) hold a code 0, and DD a code
    # 999, neither in the descriptions: 0, which has no place on a compass 'en rose de 360' where 360 is the north,
    # mostly next to FF, FXY or FXI = 0 (99.97 %, 99.9 % and 98.8 %), and 999, as the swell direction DIRHOULE writes
    # for 'variable', in six rows of Kerguelen and Nouvelle-Amsterdam, 1965 to 1967. One row lies outside 0 to 360
    # without a description, with a quality code of 1: daily DXI = 400 (31299001, 2007-09-05, GH-2728), which the
    # daily reader takes for a third code.
    ValueStub(
        "meteofrance/observation hourly/core",
        _meteofrance_observation_hourly_core,
        reading=("temperature_air_2m", 2.1),
        sentinels=(("wind_direction_last_10min", 0.0), ("wind_direction_last_10min", 999.0)),
        tokens=(("wind_direction_last_10min", "0", None), ("wind_direction_last_10min", "999", None)),
    ),
    ValueStub(
        "meteofrance/observation daily/core",
        _meteofrance_observation_daily,
        reading=("temperature_air_min_2m", -1.0),
        sentinels=(
            ("wind_direction_gust_max", 0.0),
            ("wind_direction_gust_max", 999.0),
            ("wind_direction_gust_max", 400.0),
        ),
        tokens=(
            ("wind_direction_gust_max", "0", None),
            ("wind_direction_gust_max", "999", None),
            ("wind_direction_gust_max", "400", None),
        ),
    ),
    ValueStub(
        "meteofrance/observation hourly/others",
        _meteofrance_observation_hourly_others,
        reading=("cloud_cover_total", 0.5),
        # the octas are converted to a fraction on their way
        sentinels=(("cloud_cover_total", 1.125),),
        tokens=(("cloud_cover_total", "9", None),),
    ),
    ValueStub(
        "meteofrance/synop subdaily/data",
        _meteofrance_synop,
        reading=("precipitation_amount_last_1h", 0.4),
        sentinels=(
            ("precipitation_amount_last_6h", -0.1),
            ("cloud_cover_total", 1.01),
            ("wind_direction_last_10min", 0.0),
            ("wind_direction_last_10min", 400.0),
        ),
        # a trace is 0.0 with the code beside it; an obscured sky has no amount; a calm and a 400 are no direction,
        # and north is 360
        tokens=(
            ("precipitation_amount_last_6h", "-0.1", 0.0),
            ("cloud_cover_total", "101", None),
            ("wind_direction_last_10min", "0", None),
            ("wind_direction_last_10min", "400", None),
        ),
    ),
]

# the networks no stub holds, with the reason: a network that is no timeseries, or whose reader maps no sentinel to
# null. A reader that does is given a stub and its `tokens` (GH-2759); `test_every_network_has_a_stub_or_a_reason`
# keeps the list honest, and `test_a_reader_that_maps_a_sentinel_has_a_stub` finds a reader of this list that has
# taken up the helper
NO_STUB = {
    "chmi/observation": (
        "the files write an empty VALUE for a missing one, with the QUALITY 4 (meta4.csv: `Missing`): the daily T "
        "files of 14 stations (0-20000-0-11406, 11433, 11457, 11502, 11519, 11546, 11609, 11636, 11653, 11679, "
        "11693, 11723, 11766, 11787) have 41,993 of 1,410,190 rows empty, all of them with QUALITY 4, and no cell "
        "holds text that is no number. The extremes of every daily, monthly, yearly, 10 minute and hourly element "
        "sampled (station 0-20000-0-11414, 2026-10-12) are readings (daily H tops at 100, SRA at 238.5 mm)"
    ),
    "dwd/alerts": "no timeseries",
    "dwd/phenology": (
        "the value is DWD's JULTAG, which is the day of the year only for a date in the reference year (negative "
        "for a date before it, past 365 for one after it) and the reader maps no sentinel: no -999 or other "
        "sentinel in the 424 files of annual and immediate reporters (crops, farming, fruit, vine, wild; recent and "
        "historical, 2026-10-14), whose lowest JULTAG is -130 and highest 443"
    ),
    "dwd/radar": (
        "no timeseries: the files are handed over as DWD wrote them, and the BUFR path (`read_radar_bufr`) turns the "
        "NaN of a missing pixel into null"
    ),
    "dwd/road": "BUFR: ecCodes decodes a missing value itself, there is no text of it to keep",
    "ea/hydrology": (
        "no reader maps a sentinel; a reading without a value is a JSON null with the quality `Missing`, and the "
        "daily (2015) and 15 minute (2024) discharge of the first six stations by id has no value that is no reading "
        "(2026-10-12); nor has the groundwater logger (`gw-logged-i-subdaily`) of eight stations in 2024, 2 to 63 "
        "mAOD (2026-10-15)"
    ),
    "eaufrance/hubeau": (
        "no reader maps a sentinel of a value; -999 is a site altitude of the referential. The 15 minute discharge "
        "and stage of twelve stations spread over the list (5061000101 to Y500202001), the last seven days, hold no "
        "value that is no reading (2026-10-12)"
    ),
    "imgw/meteorology": (
        "the null is decided by the status column beside the value (`8` no measurement, `9` no phenomenon), which "
        "`quality_flags` carries verbatim: the cell of the value holds `.0` or nothing, no sentinel. The daily "
        "climate, synop and precipitation files (249180010, 252190030, 249190090, 349190600, 249180020; "
        "2010 to 2011) and the monthly climate and synop files (1990 to 2020) have no value that is no reading "
        "(2026-10-12)"
    ),
    "lhmt/observation": (
        "no sentinel: the source writes null, and the hourly values of vilniaus-ams, kauno-ams and klaipedos-ams "
        "(2017-01, 2023-06) hold no value that is no reading (2026-10-12)"
    ),
    "meteoswiss/observation": (
        "the files write an empty field for a missing value: no cell that is no number in the d, h, t, m and y files "
        "of ber, jun and sma (152,308 daily rows, hourly 1990 to 1999 and recent, 10 minute 2010 to 2019), 2026-10-12. "
        "The wind direction 0 has speeds up to 13 m/s beside it, so it is north"
    ),
    "wsv/pegel": (
        "no reader maps a sentinel; its values are JSON numbers, and the current measurement of its 1,168 timeseries "
        "holds no value that is no reading (2026-10-12)"
    ),
}
