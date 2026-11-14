# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD MOSMIX-SNOW, the `snow` dataset of `dwd/mosmix` (GH-4091).

`MOSMIX-SNOW_S_2026111419_48.kmz` beside this file is the run of 2026-11-14 19 UTC as DWD published it (9.7 KB, 15
stations, 48 hourly steps), unchanged. DWD publishes the product from November to April only.
"""

from __future__ import annotations

import datetime as dt
from io import BytesIO
from pathlib import Path

import polars as pl
import pytest

from tests.provider.value_stubs import _options, _settings, stations_result
from wetterdienst import Options, Settings
from wetterdienst.exceptions import DownloadError, IssueNotFoundError
from wetterdienst.provider.dwd import catalogue
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, api
from wetterdienst.provider.dwd.mosmix.api import MOSMIX_SNOW_STATION_IDS, DwdMosmixMetadata
from wetterdienst.util.network import File

UTC = dt.UTC

RUN = Path(__file__).with_name("MOSMIX-SNOW_S_2026111419_48.kmz")

#: the elements of the run, as the file writes them (`Sa605`, not `sa605`; the reader lower-cases them)
ELEMENTS = {
    "Sa3",
    "Sa6",
    "Sah",
    "Sad",
    "Sa605",
    "Sa610",
    "Sa620",
    "Sah05",
    "Sah10",
    "Sah30",
    "Sad10",
    "Sad30",
    "Sad50",
    "SnCv",
    "TTT",
    "Td",
    "DD",
    "FF",
    "FX1",
    "RR1c",
}

#: the listing of the directory of the run of 19 UTC, as DWD's server writes it: two runs and the alias beside them
LISTING = [
    "https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX-SNOW_S/all_stations/kml/MOSMIX-SNOW_S_2026111418_48.kmz",
    "https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX-SNOW_S/all_stations/kml/MOSMIX-SNOW_S_2026111419_48.kmz",
    "https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX-SNOW_S/all_stations/kml/MOSMIX-SNOW_S_aktuell_48.kmz",
]


@pytest.fixture
def run_of_the_14th(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve the run of 2026-11-14 19 UTC from its listing, and the urls asked for, rather than from DWD's server."""
    asked: list[str] = []

    def download(_self: api.KMLReader, url: str) -> BytesIO:
        asked.append(url)
        return BytesIO(RUN.read_bytes())

    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: LISTING)
    monkeypatch.setattr(api.KMLReader, "download", download)
    return asked


def _snow_values(station_id: str, options: Options, parameters: list[tuple[str, ...]] | None = None) -> pl.DataFrame:
    request = DwdMosmixRequest(
        parameters=parameters or [("hourly", "snow")],
        settings=_settings(),
        options=options,
    )
    return (
        stations_result(request, "hourly", "snow", station_id, position=(47.4, 10.98), elevation=2420.0)
        .values()
        .all()
        .df
    )


def test_mosmix_snow_declares_the_elements_the_run_delivers(run_of_the_14th: list[str]) -> None:
    """The dataset has the 20 elements of the file, matched as the reader lower-cases them, and the 15 stations."""
    declared = {parameter.name_original for parameter in DwdMosmixMetadata.hourly.snow.parameters}
    assert declared == {element.lower() for element in ELEMENTS}
    reader = api.KMLReader(station_ids=["Z914", "01001", *MOSMIX_SNOW_STATION_IDS], settings=_settings())
    reader.read(LISTING[1])
    assert run_of_the_14th == [LISTING[1]]
    # every station of the file is one of the 15 and the other way round; `01001` is no station of the run
    assert sorted(reader.data) == sorted(MOSMIX_SNOW_STATION_IDS)
    for station_id, elements in reader.data.items():
        assert set(elements) == declared, station_id
        assert {len(values) for values in elements.values()} == {48}, station_id


def test_mosmix_snow_reads_the_newest_run_and_not_the_alias(run_of_the_14th: list[str]) -> None:
    """`LATEST` is the run of 19 UTC by name: the `aktuell` alias beside it is not read."""
    df = _snow_values("Z914", _options(drop_nulls=True))
    assert run_of_the_14th == [LISTING[1]]
    assert df["station_id"].unique().to_list() == ["Z914"]
    assert df["dataset"].unique().to_list() == ["snow"]
    # a forecast is dated by the run, which is what `UPDATED` carries; the first step is the hour after it
    assert df["timestamp"].min() == dt.datetime(2026, 11, 14, 20, tzinfo=UTC)
    assert df["timestamp"].max() == dt.datetime(2026, 11, 16, 19, tzinfo=UTC)


def test_mosmix_snow_values_of_zugspitzplatt(run_of_the_14th: list[str]) -> None:  # noqa: ARG001
    """The snow depth is returned in cm, the probabilities in percent and the temperature in degrees Celsius.

    The file writes the depth in m (`SnCv` 0.46), the probabilities as 0..100 and the temperature in K. The values are
    those of the run: Zugspitzplatt (2420 m) had a snow depth of 46 cm at 21 UTC.
    """
    df = _snow_values("Z914", _options(drop_nulls=True))
    assert set(df["parameter"]) == {
        "snow_depth_new_last_3h",
        "snow_depth_new_last_6h",
        "snow_depth_new_last_12h",
        "snow_depth_new_last_24h",
        "snow_depth",
        "probability_snow_depth_new_gt_5cm_last_6h",
        "probability_snow_depth_new_gt_10cm_last_6h",
        "probability_snow_depth_new_gt_20cm_last_6h",
        "probability_snow_depth_new_gt_5cm_last_12h",
        "probability_snow_depth_new_gt_10cm_last_12h",
        "probability_snow_depth_new_gt_30cm_last_12h",
        "probability_snow_depth_new_gt_10cm_last_24h",
        "probability_snow_depth_new_gt_30cm_last_24h",
        "probability_snow_depth_new_gt_50cm_last_24h",
        "precipitation_amount_significant_weather_last_1h",
        "temperature_air_2m",
        "temperature_dew_point_2m",
        "wind_direction",
        "wind_gust_max_last_1h",
        "wind_speed",
    }

    def value(parameter: str, hour: tuple[int, int, int, int]) -> float:
        return df.filter(pl.col("parameter") == parameter, pl.col("timestamp") == dt.datetime(*hour, tzinfo=UTC)).item(
            0, "value"
        )

    assert value("snow_depth", (2026, 11, 14, 21)) == pytest.approx(46.0)
    assert value("snow_depth", (2026, 11, 15, 6)) == pytest.approx(45.0)
    assert value("snow_depth_new_last_24h", (2026, 11, 15, 3)) == pytest.approx(1.0)
    assert value("probability_snow_depth_new_gt_10cm_last_24h", (2026, 11, 15, 3)) == pytest.approx(3.0)
    assert value("temperature_air_2m", (2026, 11, 14, 20)) == pytest.approx(-1.0)
    assert value("wind_speed", (2026, 11, 14, 20)) == pytest.approx(2.57)
    # the new snow and its probabilities are given at the 3-hourly steps for this station, the rest at every hour
    for parameter in ("snow_depth", "snow_depth_new_last_3h", "probability_snow_depth_new_gt_10cm_last_24h"):
        steps = df.filter(pl.col("parameter") == parameter)["timestamp"].dt.hour().unique().sort().to_list()
        assert steps == [0, 3, 6, 9, 12, 15, 18, 21], parameter
    assert df.filter(pl.col("parameter") == "wind_speed").height == 48


def test_mosmix_snow_keeps_what_the_file_does_not_say_as_a_gap(run_of_the_14th: list[str]) -> None:  # noqa: ARG001
    """A `-` of the file is no value and no zero: the first hour has no snow depth, and says what the file wrote."""
    df = _snow_values("Z914", _options(drop_nulls=False))
    first = df.filter(
        pl.col("parameter") == "snow_depth", pl.col("timestamp") == dt.datetime(2026, 11, 14, 20, tzinfo=UTC)
    )
    assert first.item(0, "value") is None
    assert first.item(0, "quality_flags") == "raw:-"
    # the wind of the same hour is given
    wind = df.filter(
        pl.col("parameter") == "wind_speed", pl.col("timestamp") == dt.datetime(2026, 11, 14, 20, tzinfo=UTC)
    )
    assert wind.item(0, "value") is not None


def test_mosmix_snow_has_the_15_stations_and_the_other_datasets_all_of_them(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stations of `snow` are the 15 the product forecasts for, not the 37 `Z9xx` of the catalogue or all of it.

    The rows are those of `mosmix_stationskatalog.cfg`: `Z902` is a station of the catalogue that MOSMIX-SNOW does not
    forecast for. `large` keeps every station of the catalogue, and a request for both datasets lists each as it is.
    """
    body = (
        "ID    ICAO NAME                 LAT    LON     ELEV\n"
        "----- ---- -------------------- -----  ------- -----\n"
        "01001 ENJA JAN MAYEN             70.56   -8.40    10\n"
        " Z901 ---- HOERMOOS              47.30   10.00  1280\n"
        " Z902 ---- HOCHGRATBAHN          47.30   10.04  1720\n"
        " Z914 ---- ZUGSPITZPLATT         47.24   10.59  2420\n"
    )
    monkeypatch.setattr(
        catalogue,
        "download_file",
        lambda *, url, **_: File(url=url, content=BytesIO(body.encode("latin-1")), status=200),
    )
    settings = Settings(cache_disable=True)

    snow = DwdMosmixRequest(parameters=[("hourly", "snow")], settings=settings).all().df
    assert snow["station_id"].to_list() == ["Z901", "Z914"]
    assert snow["dataset"].unique().to_list() == ["snow"]
    zugspitzplatt = snow.filter(pl.col("station_id") == "Z914").row(0, named=True)
    assert (zugspitzplatt["name"], zugspitzplatt["elevation"]) == ("ZUGSPITZPLATT", 2420.0)

    large = DwdMosmixRequest(parameters=[("hourly", "large")], settings=settings).all().df
    assert large["station_id"].to_list() == ["01001", "Z901", "Z902", "Z914"]

    both = DwdMosmixRequest(parameters=[("hourly", "snow"), ("hourly", "small")], settings=settings).all().df
    assert both.group_by("dataset").agg(pl.col("station_id")).sort("dataset").to_dicts() == [
        {"dataset": "small", "station_id": ["01001", "Z901", "Z902", "Z914"]},
        {"dataset": "snow", "station_id": ["Z901", "Z914"]},
    ]
    # a station the product does not forecast for is none of it, whichever way it is asked for
    assert (
        DwdMosmixRequest(parameters=[("hourly", "snow")], settings=settings).filter_by_station_id("Z902").df.is_empty()
    )


def test_mosmix_snow_out_of_season_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """From May to October the directory is empty, which is no `StopIteration` but a 404 that names the season.

    Raised inside `query()`'s generator, a `StopIteration` surfaced as `RuntimeError: generator raised StopIteration`
    (PEP 479); the answer is an `IssueNotFoundError`, which is a `NotFoundError` (404) and still an `IndexError`.
    """
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [])
    request = DwdMosmixRequest(parameters=[("hourly", "snow")], settings=_settings(), options=_options(drop_nulls=True))
    values = stations_result(request, "hourly", "snow", "Z914").values()

    with pytest.raises(IssueNotFoundError, match=r"No MOSMIX-SNOW run is listed within .*November to April"):
        list(values.query())
    with pytest.raises(IssueNotFoundError, match="November to April"):
        values.all()
    # the season is the snow dataset's: MOSMIX-S answers as it did, with its own message
    with pytest.raises(IndexError, match="a missing directory lists as empty"):
        values.get_url_for_date("https://example.com/kml/", api.DwdForecastDate.LATEST, one_station_only=False)


def test_mosmix_snow_directory_that_is_empty_on_the_server_is_out_of_season_and_an_outage_page_is_not() -> None:
    """DWD's empty directory (an nginx index with no file) is the season; a 200 page that is no index is an outage."""
    from tests.nginx_stub import serving  # noqa: PLC0415

    request = DwdMosmixRequest(parameters=[("hourly", "snow")], settings=_settings())
    values = stations_result(request, "hourly", "snow", "Z914").values()
    with serving() as server:
        server.directories["/empty/"] = []
        server.pages["/outage/"] = ("text/html", b"<html><title>503 - CDN</title><a href='/x'>s</a></html>")
        server.pages["/outage"] = ("text/html", b"<html><title>503 - CDN</title><a href='/x'>s</a></html>")

        with pytest.raises(IssueNotFoundError, match="November to April"):
            values.get_url_for_date(
                f"{server.base}/empty/", api.DwdForecastDate.LATEST, one_station_only=False, seasonal=True
            )
        # an outage must not read as the season: it is a `DownloadError`, a 502, and a request to try again soon
        with pytest.raises(DownloadError, match="not the index page of a directory"):
            values.get_url_for_date(
                f"{server.base}/outage/", api.DwdForecastDate.LATEST, one_station_only=False, seasonal=True
            )


@pytest.mark.remote
def test_dwd_mosmix_snow(options_humanize_false_convert_units_false: Options) -> None:
    """Fetch the latest run of MOSMIX-SNOW from DWD: the 15 stations and their values.

    DWD publishes the product from November to April only, and the directory is empty in the other months: the test
    is skipped then, the answer of the library being the `IssueNotFoundError` that the offline test holds.
    """
    if 5 <= dt.datetime.now(UTC).month <= 10:
        pytest.skip("MOSMIX-SNOW is published from November to April; the directory is empty from May to October")
    request = DwdMosmixRequest(
        parameters=[("hourly", "snow")],
        settings=Settings(cache_disable=True),
        options=options_humanize_false_convert_units_false,
    )
    assert sorted(request.all().df["station_id"]) == sorted(MOSMIX_SNOW_STATION_IDS)
    values = request.filter_by_station_id(list(MOSMIX_SNOW_STATION_IDS)).values().all()
    # the 15 stations of the run are the 15 of the library (`MOSMIX_SNOW_STATION_IDS`), whichever one DWD adds
    assert sorted(values.df["station_id"].unique()) == sorted(MOSMIX_SNOW_STATION_IDS)
    assert set(values.df["parameter"]) == {
        parameter.name_original for parameter in DwdMosmixMetadata.hourly.snow.parameters
    }
    # 48 hourly steps from the hour after the run
    assert values.df.filter(pl.col("station_id") == "Z914")["timestamp"].n_unique() == 48
    # the snow depth is in m for this options object (`convert_units=False`), as the file writes it, and a depth
    depth = values.df.filter(pl.col("parameter") == "sncv").drop_nulls("value")["value"]
    assert not depth.is_empty()
    assert 0.0 <= depth.min() <= depth.max() < 12.0
    # the probabilities are 0..100 and a probability of more is not above that of less
    probability = values.df.filter(pl.col("parameter") == "sad10").drop_nulls("value")["value"]
    assert 0.0 <= probability.min() <= probability.max() <= 100.0
