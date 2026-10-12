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
    return StationsResult(stations=request, df=df, df_all=df, stations_filter=StationsFilter.BY_STATION_ID)


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
    return request.filter_by_station_id("1200579").values.all().df


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
    return stations_result(request, resolution, dataset, station_id).values.all().df


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
    # in stundenwerte_TF_14006_20201104_20251231_hist.zip)
    product = (
        "STATIONS_ID;MESS_DATUM;QN_8;ABSF_STD;VP_STD;TF_STD;P_STD;TT_STD;RF_STD;TD_STD;eor\n"
        "   14006;2025010500;    3;   4.6;   5.8;  -0.3;  995.9;  -0.1;  95.7;  -0.7;eor\n"
        "   14006;2025010501;    3; -99.9; -99.9; -99.9;  995.9;  -0.7; -99.9; -99.9;eor\n"
    )
    return _dwd_observation(monkeypatch, "hourly", "moisture", product, "14006", drop_nulls=drop_nulls)


def _dwd_hourly_wind(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # historical/stundenwerte_FF_00003_19370101_20110331_hist.zip: the description says `missing value=-999`, the files
    # of 1975 to 1994 write 990 for a direction there is none of
    product = (
        "STATIONS_ID;MESS_DATUM;QN_3;   F;   D;eor\n"
        "          3;1975101607;    5;   2.1;  250;eor\n"
        "          3;1975101608;    5;   1.3;  990;eor\n"
    )
    return _dwd_observation(monkeypatch, "hourly", "wind", product, "00003", year=1975, drop_nulls=drop_nulls)


def _dwd_hourly_weather_phenomena(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # station 01869: `WW_Text` says "Wetter wurde nicht gemeldet" for the -1
    product = (
        "STATIONS_ID;MESS_DATUM;QN_8;  WW;WW_Text;eor\n"
        "       1869;2025040800;    3;  -1;Wetter wurde nicht gemeldet;eor\n"
        "       1869;2025040801;    3;  61;Regen;eor\n"
    )
    return _dwd_observation(monkeypatch, "hourly", "weather_phenomena", product, "01869", drop_nulls=drop_nulls)


def _dwd_hourly_cloudiness(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # the -1 where the sky could not be seen, as the hourly cloud_type file of station 00003 writes it (43 times in
    # 2005, read 2026-10-12); the cloudiness file is worded after it
    product = (
        "STATIONS_ID;MESS_DATUM;QN_8;V_N_I;V_N;eor\n"
        "          3;2025040800;    3;    I;   4;eor\n"
        "          3;2025040801;    3;    I;  -1;eor\n"
    )
    return _dwd_observation(monkeypatch, "hourly", "cloudiness", product, "00003", drop_nulls=drop_nulls)


def _geosphere_daily(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    stations = (
        "id,Stationsname,Länge [°E],Breite [°N],Höhe [m],Startdatum,Enddatum,Bundesland,Sonnenschein,Globalstrahlung\n"
        "1,Aflenz,15.24069,47.54594,783.2,1983-05-01 00:00:00+00:00,2100-12-31 00:00:00+00:00,Steiermark,True,True\n"
    ).encode()
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
    return request.filter_by_station_id("1").values.all().df


def _geosphere_hourly(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    stations = (
        "id,Stationsname,Länge [°E],Breite [°N],Höhe [m],Startdatum,Enddatum,Bundesland,Sonnenschein,Globalstrahlung\n"
        "1,Aflenz,15.24069,47.54594,783.2,1983-05-01 00:00:00+00:00,2100-12-31 00:00:00+00:00,Steiermark,True,True\n"
    ).encode()
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
    return request.filter_by_station_id("1").values.all().df


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
    rows = [
        {"temperature": "23.5", "wind_direction": "999", "wind_speed": "0.0", "precipitation": "-9999"},
        {"temperature": "23.0", "wind_direction": "90", "wind_speed": "3.1", "precipitation": "0.2"},
        {"temperature": "24.0", "wind_direction": "999", "wind_speed": "4.1", "precipitation": "-9999"},
        # the reader maps `-None` to null in every column; this row pins that
        {"temperature": "-None", "wind_direction": "90", "wind_speed": "3.1", "precipitation": "0.2"},
        # "A direction of "000" is given for calm winds" (the documentation), which the files write 0 (GH-2794)
        {"temperature": "24.0", "wind_direction": "0", "wind_speed": "0.0", "precipitation": "0.0"},
    ]
    lines = ["|".join(["STATION", "DATE", *columns])]
    for hour, row in zip((2, 3, 14, 15, 16), rows, strict=True):
        cells = [row.get(column, "") for column in columns]
        lines.append("|".join(["ACM00078861", f"1942-01-17T{hour:02d}:00:00", *cells]))
    serve(
        monkeypatch,
        ghcn_api,
        {"ghcnh-station-list": stations, "GHCNh_ACM00078861": "\n".join(lines).encode("utf8")},
    )
    request = NoaaGhcnRequest(
        parameters=[("hourly", "data")],
        start=_day(1942, 1, 17),
        end=_day(1942, 1, 18),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return request.filter_by_station_id("ACM00078861").values.all().df


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
    return stations_result(request, "hourly", dataset, "07005001").values.all().df


def _meteofrance_observation_daily(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # QUOT_departement_07_periode_2020-2024_RR-T-Vent: the daily DXI holds the code 0 (GH-2720), and the reader applies
    # 0 and 999 to it as to the hourly DD, so the stub adds the 999; worded by the stub, with the validation code
    # beside each value
    rows = [
        {"NUM_POSTE": "07005001", "AAAAMMJJ": "20240101", "TN": "-1.0", "DXI": "250", "QDXI": "1"},
        {"NUM_POSTE": "07005001", "AAAAMMJJ": "20240102", "TN": "-0.5", "DXI": "0", "QDXI": "1"},
        {"NUM_POSTE": "07005001", "AAAAMMJJ": "20240103", "TN": "0.5", "DXI": "999", "QDXI": "1"},
    ]
    _serve_meteofrance(monkeypatch, "daily", "core", "QUOT_departement_07_periode_2020-2024_RR-T-Vent", rows)
    request = MeteoFranceObservationRequest(
        parameters=[("daily", "core", "temperature_air_min_2m"), ("daily", "core", "wind_direction_gust_max")],
        start=_day(2024, 1, 1),
        end=_day(2024, 1, 3),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "daily", "core", "07005001").values.all().df


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
    # synop_2024.csv.gz: ABBEVILLE 2024-01-01T18:00Z has rr6=-0.1 beside rr1=0.0, CHASSIRON 2024-01-03T06:00Z has n=101
    schema = list(synop_api._SYNOP_CSV_SCHEMA)  # noqa: SLF001
    rows = [
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T18:00:00Z", "rr1": "0.0", "rr6": "-0.1", "n": "90"},
        {"geo_id_wmo": "07005", "validity_time": "2024-01-01T21:00:00Z", "rr1": "0.4", "rr6": "1.2", "n": "101"},
    ]
    lines = [";".join(schema)] + [";".join(row.get(column, "") for column in schema) for row in rows]
    serve(monkeypatch, synop_api, {"synop_2024": gzip.compress("\n".join(lines).encode("utf8"))})
    request = MeteoFranceSynopRequest(
        parameters=[
            ("subdaily", "data", "precipitation_amount_last_1h"),
            ("subdaily", "data", "precipitation_amount_last_6h"),
            ("subdaily", "data", "cloud_cover_total"),
        ],
        start=_day(2024, 1, 1),
        end=_day(2024, 1, 2),
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "subdaily", "data", "07005").values.all().df


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
    return stations_result(request, "hourly", "radiation_global", "18001").values.all().df


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
    return stations_result(request, "hourly", "small", "01001").values.all().df


def _dwd_dmo(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    # the same KML as MOSMIX's, with the same `-`
    kml = _forecast_kml("01001", {"TTT": "275.15 - 276.15", "Td": "273.15 274.15 -"})
    monkeypatch.setattr(
        dwd_dmo_api.DwdDmoValues,
        "get_url_for_date",
        lambda *args, **kwargs: "https://example.invalid/ptp_gdmog_01001_078_1_100000.kmz",  # noqa: ARG005
    )
    monkeypatch.setattr(dwd_dmo_api.KMLReader, "fetch", lambda _self, _url: BytesIO(kml))
    request = DwdDmoRequest(
        parameters=[("hourly", "icon", "ttt"), ("hourly", "icon", "td")],
        lead_time="short",
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, "hourly", "icon", "01001").values.all().df


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
    return stations_result(request, "hourly", "data", "10147").values.all().df


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
    return stations_result(request, "hourly", "data", "A006").values.all().df


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
    return stations_result(request, "daily", "data", "3195").values.all().df


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
    return stations_result(request, "daily", "rain", "00001").values.all().df


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
    return stations_result(request, "hourly", "data", "SN18700").values.all().df


def _knmi_daily(monkeypatch: pytest.MonkeyPatch, drop_nulls: bool = True) -> pl.DataFrame:  # noqa: FBT001, FBT002
    h5py = pytest.importorskip("h5py")
    h5netcdf = pytest.importorskip("h5netcdf")

    # a file per day for the whole network (here one station), the variables laid out as (station, time): a missing
    # observation is the NaN _FillValue and a trace of precipitation a -1 in RH
    days = {"20240101": (3.2, 1.4), "20240102": (float("nan"), -1.0)}

    def netcdf(temperature: float, precipitation: float) -> bytes:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "knmi.nc"
            with h5netcdf.File(path, "w") as file:
                file.dimensions = {"station": 1, "time": 1}
                station = file.create_variable("station", ("station",), dtype=h5py.string_dtype())
                station[:] = ["0-20000-0-06260"]
                for name, value in (("TG", temperature), ("RH", precipitation)):
                    variable = file.create_variable(name, ("station", "time"), dtype="f8")
                    variable[:] = [[value]]
            return path.read_bytes()

    payloads = {day: netcdf(*values) for day, values in days.items()}
    monkeypatch.setattr(
        knmi_api,
        "_fetch_netcdf",
        lambda _dataset, _version, filename, _settings: next(
            payload for day, payload in payloads.items() if day in filename
        ),
    )
    request = KnmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m"), ("daily", "data", "precipitation_amount")],
        start=_day(2024, 1, 1),
        end=_day(2024, 1, 2),
        settings=_settings(auth={"knmi": "stub"}),
        options=_options(drop_nulls),
    )
    return stations_result(request, "daily", "data", "06260").values.all().df


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
    return stations_result(request, "hourly", "data", "100971").values.all().df


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
    return stations_result(request, "daily", "hydrology", "149180020").values.all().df


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
            ("pressure_vapor", "-99.9", None),
            ("temperature_dew_point_2m", "-99.9", None),
            ("temperature_wet_2m", "-99.9", None),
        ),
    ),
    ValueStub(
        "dwd/observation hourly/wind",
        _dwd_hourly_wind,
        reading=("wind_direction", 250.0),
        sentinels=(("wind_direction", 990.0),),
        tokens=(("wind_direction", "990", None),),
    ),
    ValueStub(
        "dwd/observation hourly/weather_phenomena",
        _dwd_hourly_weather_phenomena,
        reading=("weather", 61.0),
        sentinels=(("weather", -1.0),),
        tokens=(("weather", "-1", None),),
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
        sentinels=(("wind_direction", 999.0), ("wind_direction", 0.0), ("precipitation_amount", -9999.0)),
        tokens=(
            ("wind_direction", "999", None),
            ("wind_direction", "0", None),
            ("precipitation_amount", "-9999", None),
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
        "fmi/observation hourly/data",
        _fmi_hourly,
        reading=("temperature_air_2m", -3.5),
        sentinels=(("precipitation_amount", -1.0),),
        tokens=(("temperature_air_2m", "NaN", None), ("precipitation_amount", "-1.0", 0.0)),
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
    # without a code, with a quality code of 1: daily DXI = 400 (31299001, 2007-09-05).
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
        sentinels=(("wind_direction_gust_max", 0.0), ("wind_direction_gust_max", 999.0)),
        tokens=(("wind_direction_gust_max", "0", None), ("wind_direction_gust_max", "999", None)),
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
        sentinels=(("precipitation_amount_last_6h", -0.1), ("cloud_cover_total", 1.01)),
        # a trace is 0.0 with the code beside it; an obscured sky has no amount
        tokens=(
            ("precipitation_amount_last_6h", "-0.1", 0.0),
            ("cloud_cover_total", "101", None),
        ),
    ),
]

# the networks no stub holds, with the reason: a network that is no timeseries, or whose reader maps no sentinel to
# null. A reader that does is given a stub and its `tokens` (GH-2759); `test_every_network_has_a_stub_or_a_reason`
# keeps the list honest, and `test_a_reader_that_maps_a_sentinel_has_a_stub` finds a reader of this list that has
# taken up the helper
NO_STUB = {
    "chmi/observation": (
        "the files write an empty VALUE for a missing one: dly-0-20000-0-11406-T.csv (2026-10-12) has 177144 rows, "
        "32136 of them empty, nothing that is no number and a minimum of -27.6"
    ),
    "dmi/observation": "no reader maps a sentinel; its values are JSON numbers",
    "dwd/alerts": "no timeseries",
    "dwd/phenology": (
        "JULTAG is a day of the year and the reader maps no sentinel: no -999 in the 2119 lines of "
        "PH_Jahresmelder_Landwirtschaft_Kulturpflanze_Ruebe_akt.txt (2026-10-12)"
    ),
    "dwd/radar": "no timeseries",
    "dwd/road": "BUFR: ecCodes decodes a missing value itself, there is no text of it to keep",
    "ea/hydrology": "no reader maps a sentinel; a reading without a value is a JSON null with the quality `Missing`",
    "eaufrance/hubeau": "no reader maps a sentinel of a value; -999 is a site altitude of the referential",
    "eccc/observation": "no reader maps a sentinel; the flag `M` marks a missing value",
    "imgw/meteorology": (
        "the null is decided by the status column beside the value (`8` no measurement, `9` no phenomenon), which "
        "`quality_flags` carries verbatim: the cell of the value holds `.0` or nothing, no sentinel"
    ),
    "lhmt/observation": "no sentinel: the source writes null",
    "meteoswiss/observation": (
        "the files write an empty field for a missing value: no cell that is no number in ogd-smn_ber_h_recent.csv "
        "(6816 rows) and ogd-smn_ber_d_historical.csv (59170 rows), 2026-10-12"
    ),
    "nws/observation": "no reader maps a sentinel; a quantity without a value is a JSON null",
    "rmi/observation": "no reader maps a sentinel; its values are JSON numbers",
    "smhi/observation": "no reader maps a sentinel; a blank row is a missing reading and is dropped",
    "wsv/pegel": "no reader maps a sentinel; its values are JSON numbers",
}
