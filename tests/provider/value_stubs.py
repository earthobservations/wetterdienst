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

To hold another provider to this, add a stub to `STUBS`: serve what the source answers, write the missing value as the
source does, and name the parameter and value that must arrive. A network that has no stub is named in `NO_STUB` with
the reason, and `test_every_network_has_a_stub_or_a_reason` fails for one that is in neither.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

import polars as pl

from wetterdienst import Settings
from wetterdienst.metadata.period import Period
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation import api as dwd_observation_api
from wetterdienst.provider.geosphere.observation import GeosphereObservationRequest
from wetterdienst.provider.geosphere.observation import api as geosphere_api
from wetterdienst.provider.ipma.observation import IpmaObservationRequest
from wetterdienst.provider.ipma.observation import api as ipma_api
from wetterdienst.provider.meteofrance.synop import MeteoFranceSynopRequest
from wetterdienst.provider.meteofrance.synop import api as synop_api
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest
from wetterdienst.provider.noaa.ghcn import api as ghcn_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest

_UTC = dt.timezone.utc


@dataclass(frozen=True)
class ValueStub:
    """The values a provider's reader gives for a stub of its source, and what they must and must not hold."""

    provider: str
    build: Callable[[pytest.MonkeyPatch], pl.DataFrame]
    # a (canonical parameter, value) that has to arrive, so that the stub is no empty frame
    reading: tuple[str, float]
    # the numbers the source writes for a missing value, as the output would carry them; (parameter, value) where the
    # number is a sentinel for one parameter and a reading for another
    sentinels: tuple[tuple[str, float], ...]
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


def _day(year: int, month: int, day: int, hour: int = 0) -> dt.datetime:
    return dt.datetime(year, month, day, hour, tzinfo=_UTC)


def _ipma(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
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
        settings=Settings(cache_disable=True),
    )
    return request.filter_by_station_id("1200579").values.all().df


def _dwd_observation(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    dataset: str,
    product: str,
    station_id: str = "00044",
    year: int = 2025,
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
        settings=Settings(cache_disable=True),
    )
    return stations_result(request, resolution, dataset, station_id).values.all().df


def _dwd_daily_climate_summary(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
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
    return _dwd_observation(monkeypatch, "daily", "climate_summary", "\n".join(lines) + "\n")


def _dwd_hourly_moisture(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # the description says `missing value = -999`; the files write -99.9 (station 14006, 2025-01-05 01:00)
    product = (
        "STATIONS_ID;MESS_DATUM;QN_8;ABSF_STD;VP_STD;TF_STD;P_STD;TT_STD;RF_STD;TD_STD;eor\n"
        "   14006;2025010500;    3;   3.2;   4.8;  -1.6;  995.9;  -0.7;  95.0;  -1.2;eor\n"
        "   14006;2025010501;    3; -99.9; -99.9; -99.9;  995.9;  -0.7; -99.9; -99.9;eor\n"
    )
    return _dwd_observation(monkeypatch, "hourly", "moisture", product, "14006")


def _dwd_hourly_wind(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # historical/stundenwerte_FF_00003_19370101_20110331_hist.zip: the description says `missing value=-999`, the files
    # of 1975 to 1994 write 990 for a direction there is none of
    product = (
        "STATIONS_ID;MESS_DATUM;QN_3;   F;   D;eor\n"
        "          3;1975101607;    5;   2.1;  250;eor\n"
        "          3;1975101608;    5;   1.3;  990;eor\n"
    )
    return _dwd_observation(monkeypatch, "hourly", "wind", product, "00003", year=1975)


def _dwd_hourly_weather_phenomena(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # station 01869: `WW_Text` says "Wetter wurde nicht gemeldet" for the -1
    product = (
        "STATIONS_ID;MESS_DATUM;QN_8;  WW;WW_Text;eor\n"
        "       1869;2025040800;    3;  -1;Wetter wurde nicht gemeldet;eor\n"
        "       1869;2025040801;    3;  61;Regen;eor\n"
    )
    return _dwd_observation(monkeypatch, "hourly", "weather_phenomena", product, "01869")


def _geosphere_daily(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    stations = (
        "id,Stationsname,Länge [°E],Breite [°N],Höhe [m],Startdatum,Enddatum,Bundesland,Sonnenschein,Globalstrahlung\n"
        "1,Aflenz,15.24069,47.54594,783.2,1983-05-01 00:00:00+00:00,2100-12-31 00:00:00+00:00,Steiermark,True,True\n"
    ).encode()
    # klima-v2-1d: "-1=kein Niederschlag, 0=weniger als 1/10 mm" for rr, "-1=kein Schnee" for sh_manu
    series = {"rr": [0.3, -1.0, 0.0], "sh_manu": [4.0, -1.0, 2.0]}

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
        settings=Settings(cache_disable=True),
    )
    return request.filter_by_station_id("1").values.all().df


def _ghcn_hourly(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # GHCNh_ACM00078861_por.psv, 1942-01-17 02:00: the direction reads 999 with the measurement code C (calm) and a wind
    # speed of 0.0; the documentation gives "000" for calm
    stations = (
        b"GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        b"ACM00078861,17.1167,-61.7833,10.0,,COOLIDGE FIELD ANTIGUA,,,78861,,AG\n"
    )
    hourly = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=Settings(cache_disable=True))
    columns = [parameter.name_original for parameter in hourly.metadata["hourly"]["data"]]
    rows = [
        {"temperature": "23.5", "wind_direction": "999", "wind_speed": "0.0"},
        {"temperature": "23.0", "wind_direction": "90", "wind_speed": "3.1"},
    ]
    lines = ["|".join(["STATION", "DATE", *columns])]
    for hour, row in zip((2, 3), rows, strict=True):
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
        settings=Settings(cache_disable=True),
    )
    return request.filter_by_station_id("ACM00078861").values.all().df


def _meteofrance_synop(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
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
        settings=Settings(cache_disable=True),
    )
    return stations_result(request, "subdaily", "data", "07005").values.all().df


STUBS = [
    ValueStub(
        "ipma/observation hourly/data",
        _ipma,
        reading=("temperature_air_mean_2m", 21.5),
        # the humidity is converted from percent to a decimal on its way
        sentinels=(("temperature_air_mean_2m", -99.0), ("humidity_relative", -0.99), ("precipitation_amount", -99.0)),
        empty_at=_day(2026, 10, 10, 13),
    ),
    ValueStub(
        "dwd/observation daily/climate_summary",
        _dwd_daily_climate_summary,
        reading=("temperature_air_mean_2m", 2.9),
        sentinels=(("temperature_air_mean_2m", -999.0), ("precipitation_amount", -999.0)),
        empty_at=_day(2025, 1, 2),
    ),
    ValueStub(
        "dwd/observation hourly/moisture",
        _dwd_hourly_moisture,
        reading=("temperature_air_2m", -0.7),
        sentinels=(
            ("humidity_absolute", -99.9),
            ("humidity_relative", -0.999),
            ("pressure_vapor", -99.9),
            ("temperature_dew_point_2m", -99.9),
            ("temperature_wet_2m", -99.9),
        ),
        leak="#2669",
    ),
    ValueStub(
        "dwd/observation hourly/wind",
        _dwd_hourly_wind,
        reading=("wind_direction", 250.0),
        sentinels=(("wind_direction", 990.0),),
        leak="#2686",
    ),
    ValueStub(
        "dwd/observation hourly/weather_phenomena",
        _dwd_hourly_weather_phenomena,
        reading=("weather", 61.0),
        sentinels=(("weather", -1.0),),
        leak="#2670",
    ),
    ValueStub(
        "geosphere/observation daily/data",
        _geosphere_daily,
        reading=("precipitation_amount", 0.3),
        sentinels=(("precipitation_amount", -1.0), ("snow_depth_manual", -1.0)),
        leak="#2671",
    ),
    ValueStub(
        "noaa/ghcn hourly/data",
        _ghcn_hourly,
        reading=("wind_direction", 90.0),
        sentinels=(("wind_direction", 999.0),),
        leak="#2672",
    ),
    ValueStub(
        "meteofrance/synop subdaily/data",
        _meteofrance_synop,
        reading=("precipitation_amount_last_1h", 0.4),
        sentinels=(("precipitation_amount_last_6h", -0.1), ("cloud_cover_total", 1.01)),
        leak="#2674",
    ),
]

# the networks no stub holds yet, with the reason; `test_every_network_has_a_stub_or_a_reason` keeps the list honest
NO_STUB = {
    "aemet/observation": "needs an API key; no offline test pins its `dir == 99` rule",
    "chmi/observation": "no stub yet",
    "dmi/observation": "no stub yet",
    "dwd/alerts": "no timeseries",
    "dwd/derived": "no stub yet; its parser maps -999 and -9999",
    "dwd/dmo": "no stub yet; the KML marks a missing value with `-`",
    "dwd/mosmix": "no stub yet; the KML marks a missing value with `-`",
    "dwd/phenology": "no stub yet",
    "dwd/poi": "no stub yet; the file marks a missing value with `---`",
    "dwd/radar": "no timeseries",
    "dwd/road": "no stub yet; BUFR decodes a missing value itself",
    "dwd/swsmos": "no stub yet; the file marks a missing value with `---`",
    "ea/hydrology": "no stub yet",
    "eaufrance/hubeau": "no stub yet",
    "eccc/observation": "no stub yet",
    "fmi/observation": "no stub yet; its parser maps -1 to 0.0 for four parameters",
    "imgw/hydrology": "no stub yet; its reader nulls 9999, 99999.999 and 99.9",
    "imgw/meteorology": "no stub yet; its reader reads the status columns 8 and 9",
    "knmi/observation": "needs an API key; the NaN and -1 rules are pinned by tests/provider/knmi",
    "lhmt/observation": "no sentinel: the source writes null",
    "meteofrance/observation": "no stub yet",
    "meteoswiss/observation": "no stub yet",
    "metno/frost": "needs an API key; the -1 and -3 rules are pinned by tests/provider/metno, which run with a key",
    "metoffice/observation": "needs an API key; no offline test pins its NA rule",
    "nws/observation": "no stub yet",
    "rmi/observation": "no stub yet",
    "smhi/observation": "no stub yet",
    "wsv/pegel": "no stub yet",
}
