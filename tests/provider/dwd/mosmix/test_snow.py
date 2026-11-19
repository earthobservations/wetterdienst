# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD MOSMIX-SNOW, the `snow` dataset of `dwd/mosmix` (GH-4091).

`MOSMIX-SNOW_S_2026111419_48.kmz` beside this file is the run of 2026-11-14 19 UTC as DWD published it (9.7 KB, 15
stations, 48 hourly steps), unchanged. DWD publishes the product from November to April only.
"""

from __future__ import annotations

import datetime as dt
import zipfile
from io import BytesIO
from pathlib import Path

import polars as pl
import pytest

from tests.provider.value_stubs import _options, _settings, dwd_mosmix_values, stations_result
from wetterdienst import Options, Settings
from wetterdienst.exceptions import DownloadError, IssueNotFoundError, ProductOutOfSeasonError
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


CATALOGUE = (
    "ID    ICAO NAME                 LAT    LON     ELEV\n"
    "----- ---- -------------------- -----  ------- -----\n"
    "01001 ENJA JAN MAYEN             70.56   -8.40    10\n"
    " Z901 ---- HOERMOOS              47.30   10.00  1280\n"
    " Z902 ---- HOCHGRATBAHN          47.30   10.04  1720\n"
    " Z914 ---- ZUGSPITZPLATT         47.24   10.59  2420\n"
)


def _serve_catalogue(monkeypatch: pytest.MonkeyPatch, body: str = CATALOGUE) -> None:
    """Serve `mosmix_stationskatalog.cfg` with these rows, as DWD writes it."""
    monkeypatch.setattr(
        catalogue,
        "download_file",
        lambda *, url, **_: File(url=url, content=BytesIO(body.encode("latin-1")), status=200),
    )


def _snow_stations() -> list[str]:
    request = DwdMosmixRequest(parameters=[("hourly", "snow")], settings=_settings())
    return request.all().df["station_id"].to_list()


def test_mosmix_snow_has_the_stations_of_the_run_and_the_other_datasets_all_of_them(
    monkeypatch: pytest.MonkeyPatch,
    run_of_the_14th: list[str],
) -> None:
    """The stations of `snow` are those the newest run names, not the 37 `Z9xx` of the catalogue or all of it.

    The rows are those of `mosmix_stationskatalog.cfg`: `Z902` is a station of the catalogue that the run does not
    name. `large` keeps every station of the catalogue, and a request for both datasets lists each as it is.
    """
    _serve_catalogue(monkeypatch)
    settings = _settings()

    snow = DwdMosmixRequest(parameters=[("hourly", "snow")], settings=settings).all().df
    assert run_of_the_14th == [LISTING[1]]
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
    # a station the run does not name is none of the dataset, whichever way it is asked for
    assert (
        DwdMosmixRequest(parameters=[("hourly", "snow")], settings=settings).filter_by_station_id("Z902").df.is_empty()
    )


def _run_with_a_station_more() -> bytes:
    """Give the run of the 14th with a copy of the placemark of `Z914` named `Z999`, as DWD would add a station."""
    with zipfile.ZipFile(RUN) as archive:
        name = archive.namelist()[0]
        kml = archive.read(name).decode("latin-1")
    start = kml.index("<kml:Placemark>\n            <kml:name>Z914")
    end = kml.index("</kml:Placemark>", start) + len("</kml:Placemark>")
    added = kml[start:end].replace("Z914", "Z999").replace("ZUGSPITZPLATT", "NEUE STATION")
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, (kml[:end] + "\n        " + added + kml[end:]).encode("latin-1"))
    return out.getvalue()


def test_mosmix_snow_a_station_dwd_adds_to_the_run_is_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station the newest run names and the catalogue lists is a station of the dataset, with its values.

    `Z999` stands for a station DWD adds: the catalogue lists it and the run names it, and it is not one of the 15 the
    constant holds. `Z903` is in the catalogue and not in the run.
    """
    body = (
        CATALOGUE
        + " Z999 ---- NEUE STATION          47.20   10.50  1500\n"
        + " Z903 ---- ANDERE STATION        47.10   10.40  1400\n"
    )
    _serve_catalogue(monkeypatch, body)
    run = _run_with_a_station_more()
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: LISTING)
    monkeypatch.setattr(api.KMLReader, "download", lambda _self, _url: BytesIO(run))
    assert "Z999" not in MOSMIX_SNOW_STATION_IDS

    request = DwdMosmixRequest(parameters=[("hourly", "snow")], settings=_settings(), options=_options(drop_nulls=True))
    assert request.all().df["station_id"].to_list() == ["Z901", "Z914", "Z999"]
    values = request.filter_by_station_id("Z999").values().all().df
    assert values["station_id"].unique().to_list() == ["Z999"]
    assert values.filter(pl.col("parameter") == "snow_depth").sort("timestamp")["value"][0] == pytest.approx(46.0)


def test_mosmix_snow_without_a_run_lists_the_stations_known(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Out of season the directory is empty and the stations are the 15 known, those of them the catalogue lists."""
    _serve_catalogue(monkeypatch)
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [])

    assert _snow_stations() == ["Z901", "Z914"]
    assert "Unable to read the stations" not in caplog.text


def test_mosmix_snow_a_run_that_cannot_be_read_lists_the_stations_known_and_says_so(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A run that fails to list or to read is not the reason for no stations at all."""
    _serve_catalogue(monkeypatch)

    def fail(*_args: object, **_kwargs: object) -> list[str]:
        msg = "boom"
        raise OSError(msg)

    monkeypatch.setattr(api, "list_remote_files_fsspec", fail)
    assert _snow_stations() == ["Z901", "Z914"]
    assert "Unable to read the stations the newest MOSMIX-SNOW run names" in caplog.text

    caplog.clear()
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: LISTING)

    def not_a_run(_self: api.KMLReader, _url: str) -> BytesIO:
        return BytesIO(b"not a zip")

    monkeypatch.setattr(api.KMLReader, "download", not_a_run)
    assert _snow_stations() == ["Z901", "Z914"]
    assert "Unable to read the stations the newest MOSMIX-SNOW run names" in caplog.text


def test_mosmix_snow_out_of_season_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no run listed the answer is a `ProductOutOfSeasonError`: a 404, still an `IssueNotFoundError`.

    Raised inside `query()`'s generator, a `StopIteration` surfaced as `RuntimeError: generator raised StopIteration`
    (PEP 479); the answer is an `IssueNotFoundError`, which is a `NotFoundError` (404) and still an `IndexError`.
    """
    from wetterdienst.ui.core import failure_status  # noqa: PLC0415

    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [])
    request = DwdMosmixRequest(parameters=[("hourly", "snow")], settings=_settings(), options=_options(drop_nulls=True))
    values = stations_result(request, "hourly", "snow", "Z914").values()

    with pytest.raises(ProductOutOfSeasonError, match=r"No MOSMIX-SNOW run is listed within") as raised:
        list(values.query())
    assert isinstance(raised.value, IssueNotFoundError)
    assert isinstance(raised.value, IndexError)
    assert failure_status(raised.value) == 404
    with pytest.raises(ProductOutOfSeasonError):
        values.all()
    # the season is the snow dataset's: MOSMIX-S answers as it did, with its own message
    with pytest.raises(IndexError, match="a missing directory lists as empty") as plain:
        values.get_url_for_date("https://example.com/kml/", api.DwdForecastDate.LATEST, one_station_only=False)
    assert not isinstance(plain.value, ProductOutOfSeasonError)


@pytest.mark.parametrize("month", [5, 7, 10])
def test_mosmix_snow_out_of_season_names_the_season_from_may_to_october(month: int) -> None:
    """From May to October the season is the reason, and when to come back."""
    message = api.out_of_season_message("https://example.com/kml/", month)
    assert "from November to April only" in message
    assert "until the winter" in message


@pytest.mark.parametrize("month", [11, 12, 1, 4])
def test_mosmix_snow_with_no_run_in_winter_does_not_name_the_season_as_the_reason(month: int) -> None:
    """From November to April no run is listed, and DWD publishes it while there is snow: no "try again in winter"."""
    message = api.out_of_season_message("https://example.com/kml/", month)
    assert "No MOSMIX-SNOW run is listed within https://example.com/kml/" in message
    assert "only while there is snow" in message
    assert "winter" not in message
    assert "November" not in message


def test_mosmix_snow_directory_that_is_empty_on_the_server_is_out_of_season_and_an_outage_page_is_not() -> None:
    """DWD's empty directory (an nginx index with no file) is the season; a 200 page that is no index is an outage."""
    from tests.nginx_stub import serving  # noqa: PLC0415

    request = DwdMosmixRequest(parameters=[("hourly", "snow")], settings=_settings())
    values = stations_result(request, "hourly", "snow", "Z914").values()
    with serving() as server:
        server.directories["/empty/"] = []
        server.pages["/outage/"] = ("text/html", b"<html><title>503 - CDN</title><a href='/x'>s</a></html>")
        server.pages["/outage"] = ("text/html", b"<html><title>503 - CDN</title><a href='/x'>s</a></html>")

        with pytest.raises(ProductOutOfSeasonError, match="No MOSMIX-SNOW run is listed"):
            values.get_url_for_date(
                f"{server.base}/empty/", api.DwdForecastDate.LATEST, one_station_only=False, seasonal=True
            )
        # an outage must not read as the season: it is a `DownloadError`, a 502, and a request to try again soon
        with pytest.raises(DownloadError, match="not the index page of a directory"):
            values.get_url_for_date(
                f"{server.base}/outage/", api.DwdForecastDate.LATEST, one_station_only=False, seasonal=True
            )


def test_a_snow_depth_a_little_below_zero_is_zero_and_keeps_the_number_written(monkeypatch: pytest.MonkeyPatch) -> None:
    """The last of a melting snow is `SnCv` -0.01 and -0.02 m in the run: 0.0 with `raw:`, as DMO's rain (GH-4182)."""
    elements = {"SnCv": "0.05 -0.01 -0.02", "Sa3": "0.03 0.00 0.01"}
    parameters = [("hourly", "snow", "sncv"), ("hourly", "snow", "sa3")]
    df = dwd_mosmix_values(monkeypatch, elements, parameters, options=Options(drop_nulls=False, convert_units=False))
    depth = df.filter(pl.col("parameter") == "snow_depth").sort("timestamp")
    assert depth["value"].to_list() == [0.05, 0.0, 0.0]
    assert depth["quality_flags"].to_list() == [None, "rejected:floor,raw:-0.01", "rejected:floor,raw:-0.02"]
    # the depth of a snow that stays is untouched, and so is the new snow
    assert df.filter(pl.col("parameter") == "snow_depth_new_last_3h").sort("timestamp")["value"].to_list() == [
        0.03,
        0.0,
        0.01,
    ]
    assert df.filter(pl.col("parameter") == "snow_depth_new_last_3h")["quality_flags"].is_null().all()
    # the check does not reject, so the answer has no null where the model wrote a number
    assert depth["value"].null_count() == 0

    # in the units of the library it is cm, and the range of a depth, which allows -10 cm, does not decide
    df = dwd_mosmix_values(monkeypatch, elements, parameters, options=Options(drop_nulls=False))
    depth = df.filter(pl.col("parameter") == "snow_depth").sort("timestamp")
    assert depth["value"].to_list() == [5.0, 0.0, 0.0]
    assert depth["quality_flags"].to_list() == [None, "rejected:floor,raw:-0.01", "rejected:floor,raw:-0.02"]


def test_a_snow_depth_down_to_10_cm_below_zero_is_zero_and_one_further_below_is_the_ranges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tolerance is the lower bound of the range of a depth, 10 cm: -0.07 m (run of 2026-11-18) is 0.0 (GH-4237).

    A depth of -0.11 m is no round-off: the floor leaves it to the range, whose low end for a forecast's depth is 0. A
    forecast is soft in `range`, so the value is kept and flagged `suspect:range`, as the new snow's tolerance, which is
    the same constant, is held to.
    """
    elements = {"SnCv": "-0.07 -0.10 -0.11", "Sa3": "-0.07 -0.11 0.01"}
    parameters = [("hourly", "snow", "sncv"), ("hourly", "snow", "sa3")]
    df = dwd_mosmix_values(monkeypatch, elements, parameters, options=Options(drop_nulls=False, convert_units=False))
    depth = df.filter(pl.col("parameter") == "snow_depth").sort("timestamp")
    assert depth["value"].to_list() == [0.0, 0.0, -0.11]
    assert depth["quality_flags"].to_list() == ["rejected:floor,raw:-0.07", "rejected:floor,raw:-0.1", "suspect:range"]
    # the sums of new snow share the tolerance
    new = df.filter(pl.col("parameter") == "snow_depth_new_last_3h").sort("timestamp")
    assert new["value"].to_list() == [0.0, -0.11, 0.01]
    assert new["quality_flags"].to_list() == ["rejected:floor,raw:-0.07", "suspect:range", None]


def test_a_snow_depth_below_zero_is_kept_and_flagged_where_the_floor_is_soft(monkeypatch: pytest.MonkeyPatch) -> None:
    """`plausibility={"floor": "soft"}` returns the number as DWD wrote it, flagged `suspect:floor` (GH-4182)."""
    df = dwd_mosmix_values(
        monkeypatch,
        {"SnCv": "0.05 -0.01 -0.02"},
        [("hourly", "snow", "sncv")],
        options=Options(drop_nulls=False, convert_units=False, plausibility={"floor": "soft"}),
    ).sort("timestamp")
    assert df["value"].to_list() == [0.05, -0.01, -0.02]
    assert df["quality_flags"].to_list() == [None, "suspect:floor", "suspect:floor"]


def test_the_amounts_of_mosmix_s_that_cannot_be_negative_are_held_to_the_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    """A round-off below 0 of the precipitation, the radiation and the sunshine of MOSMIX-S is 0.0 with `raw:`."""
    df = dwd_mosmix_values(
        monkeypatch,
        {"RR1c": "-0.02 0.40 0.00", "Rad1h": "-0.16 0.00 142.09", "SunD1": "-0.5 3600.0 0.0"},
        [("hourly", "small", "rr1c"), ("hourly", "small", "rad1h"), ("hourly", "small", "sund1")],
        options=Options(drop_nulls=False, convert_units=False),
    )
    floored = df.filter(pl.col("quality_flags").str.starts_with("rejected:floor"))
    assert sorted(floored["parameter"].to_list()) == [
        "precipitation_amount_significant_weather_last_1h",
        "radiation_global",
        "sunshine_duration",
    ]
    assert floored["value"].to_list() == [0.0, 0.0, 0.0]
    assert sorted(floored["quality_flags"].to_list()) == [
        "rejected:floor,raw:-0.02",
        "rejected:floor,raw:-0.16",
        "rejected:floor,raw:-0.5",
    ]


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
    # the stations are those the live run names, and the values are of those
    stations = sorted(request.all().df["station_id"])
    values = request.filter_by_station_id(stations).values().all()
    assert sorted(values.df["station_id"].unique()) == stations
    # and the 15 of the constant, which only an out-of-season answer is read from: a change in the run is noticed here
    assert stations == sorted(MOSMIX_SNOW_STATION_IDS), (
        "DWD changed the stations of MOSMIX-SNOW: update the constant, and re-check the extent of `hourly/snow` in "
        "`metadata.py` (national DE; an Austrian station makes it regional DE/AT)"
    )
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
