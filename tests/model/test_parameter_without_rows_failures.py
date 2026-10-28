# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A file the provider let go is no evidence that the source holds nothing (GH-3539).

Providers log a file they gave up on and answer with the others: a refused download, an AEMET chunk, the road weather
files withdrawn since the listing, a KNMI timestamp that is not there, an SMHI parameter file that was refused, an FMI
exception report with HTTP 200. The station whose file was let go is not counted by `parameter-without-rows`
(`note_skipped_download`), and the other stations are. An answer that says there is nothing (a 404 for a station that
does not report the parameter, Frost's 412, an AEMET `estado` of 404), and a download that failed and was made again
with success, are the source's answer and are still told. One test per family of providers, with the control that is
the answer of the source.
"""

from __future__ import annotations

import json
from io import BytesIO
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientResponseError

from tests.conftest import BUFR_AVAILABLE
from tests.provider.aemet.observation.test_api import BARCELONA, MADRID_RETIRO, _values
from tests.provider.dwd.road.test_api import _stub_downloads, _stub_stations
from tests.provider.fmi.observation.test_values_frames import _EXCEPTION_REPORT, _collection
from tests.provider.fmi.observation.test_values_frames import _serve as _serve_fmi
from tests.provider.fmi.observation.test_values_frames import _values as _fmi_values
from tests.provider.knmi.observation.test_api import _daily_values, _serve_knmi
from tests.provider.metno.frost.test_values_failures import _failed as _frost_answer
from tests.provider.metno.frost.test_values_failures import _values as _frost_values
from tests.provider.smhi.observation.test_api_download_failure import _STATION
from tests.provider.smhi.observation.test_api_download_failure import _request as _smhi_request
from tests.provider.value_stubs import stations_result
from wetterdienst.provider.aemet.observation import api as aemet_api
from wetterdienst.provider.smhi.observation import api as smhi_api
from wetterdienst.util.network import File, _failed_file
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from wetterdienst import Settings

CODE = "parameter-without-rows"


def _road_stations(station_ids: tuple[str, ...] = ("A006",)) -> Any:  # noqa: ANN401
    """Stand road stations up with the window the dataset needs, as the REST API and the command line demand."""
    import datetime as dt  # noqa: PLC0415

    stations = _stub_stations(station_ids)
    stations.request.start = dt.datetime(2026, 9, 13, tzinfo=dt.UTC)
    stations.request.end = dt.datetime(2026, 9, 13, 23, tzinfo=dt.UTC)
    return stations


def _told() -> list[dict[str, Any]]:
    """Give the warnings of `parameter-without-rows` that the request being served has recorded."""
    return [warning for warning in recorded_warnings() if warning["code"] == CODE]


def _refused(url: str, status: int = 429) -> File:
    """Give a download the source refused, as the network layer hands it back."""
    error = ClientResponseError(request_info=MagicMock(), history=(), status=status, message="refused")
    file = _failed_file(url, error)
    assert file is not None
    return file


# met.no Frost: a 412 is Frost's answer for none, a refusal is a file let go


@pytest.mark.parametrize(
    ("status", "told"),
    [(412, True), (404, True), (429, False), (500, False)],
    ids=["412 is no data", "404 is no data", "429 refused", "500 failed"],
)
def test_frost_values_say_nothing_of_a_discovery_that_failed(
    monkeypatch: pytest.MonkeyPatch, status: int, *, told: bool
) -> None:
    """Frost answers 412 or 404 for the available time series when there are none; anything else is let go."""

    def observations(url: str) -> File:
        return _frost_answer(url, status) if "availableTimeSeries" in url else _frost_answer(url, 404)

    values, _seen = _frost_values(monkeypatch, observations)
    begin_response()
    assert values.all().df.is_empty()
    assert [warning["stations"] for warning in _told()] == ([["SN18700"]] if told else [])


# AEMET: a chunk that failed is skipped; one that AEMET answered for with "no data" is the answer


def _aemet_serving(monkeypatch: pytest.MonkeyPatch, answer: Callable[[str], File]) -> None:
    """Serve the station list as two stations, and every request for values as `answer` says."""
    stations = json.dumps(
        [
            {
                "indicativo": MADRID_RETIRO,
                "nombre": "MADRID, RETIRO",
                "provincia": "MADRID",
                "altitud": "667",
                "latitud": "402941N",
                "longitud": "34041W",
            },
            {
                "indicativo": BARCELONA,
                "nombre": "BARCELONA AEROPUERTO",
                "provincia": "BARCELONA",
                "altitud": "4",
                "latitud": "412258N",
                "longitud": "020412E",
            },
        ]
    ).encode("latin-1")
    fetch = aemet_api._fetch_datos  # noqa: SLF001
    retry = aemet_api._download_with_rate_limit_retry  # noqa: SLF001

    def fetching(url: str, settings: Settings, ttl: object) -> bytes | Exception:
        return stations if "todasestaciones" in url else fetch(url, settings, ttl)  # ty: ignore[invalid-argument-type]

    def downloading(url: str, settings: Settings, ttl: object, **_kwargs: object) -> File:
        # the retry is the provider's own, with no time to wait between attempts
        return retry(url, settings, ttl, wait_initial=0.001, wait_max=0.001, max_retries=2)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(aemet_api, "_fetch_datos", fetching)
    monkeypatch.setattr(aemet_api, "_download_with_rate_limit_retry", downloading)
    monkeypatch.setattr(aemet_api, "download_file", lambda url, **_kwargs: answer(url))


def _envelope(url: str, estado: int, **extra: str) -> File:
    body = json.dumps({"estado": estado, "descripcion": "the answer", **extra}).encode()
    return File(url=url, content=BytesIO(body), status=200)


_AEMET_KINDS = [
    pytest.param(lambda url: _refused(url, 400), False, id="400"),
    pytest.param(lambda url: File(url=url, content=BytesIO(b"<html>maintenance</html>"), status=200), False, id="html"),
    pytest.param(lambda url: _envelope(url, 400), False, id="estado 400 in a 200"),
    pytest.param(lambda url: _envelope(url, 404), True, id="estado 404 is no data"),
    pytest.param(lambda url: _failed_file(url, FileNotFoundError(url)), True, id="404 is no data"),
]


@pytest.mark.parametrize(("answer", "told"), _AEMET_KINDS)
def test_aemet_values_say_nothing_of_a_chunk_that_was_let_go(
    monkeypatch: pytest.MonkeyPatch, answer: Callable[[str], File], *, told: bool
) -> None:
    """A chunk that failed, or whose body is no answer (a page, an `estado` that is an error), is let go."""
    _aemet_serving(monkeypatch, answer)
    begin_response()
    assert _values("daily", years=1).is_empty()
    assert len(_told()) == (1 if told else 0)


def test_aemet_values_tell_of_a_chunk_that_failed_and_then_came_without_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """A download that failed and was made again with success is no file let go: its answer is the source's."""
    calls: list[str] = []

    def answer(url: str) -> File:
        calls.append(url)
        # the first try of each request fails, the second is AEMET's answer that it has no data
        return _refused(url, 503) if calls.count(url) == 1 else _envelope(url, 404)

    _aemet_serving(monkeypatch, answer)
    begin_response()
    assert _values("daily", years=1).is_empty()
    assert len(_told()) == 1
    assert any(calls.count(url) == 2 for url in calls)


def test_aemet_values_name_the_station_that_was_not_let_go(monkeypatch: pytest.MonkeyPatch) -> None:
    """One station's chunk fails and the other's is AEMET's answer of no data: the warning names the other."""
    _aemet_serving(
        monkeypatch,
        lambda url: _refused(url, 400) if f"/{MADRID_RETIRO}" in url else _envelope(url, 404),
    )
    begin_response()
    assert _values("daily", years=1, station_ids=(MADRID_RETIRO, BARCELONA)).is_empty()
    assert [warning["stations"] for warning in _told()] == [[BARCELONA]]


# dwd/road: the files withdrawn since the listing


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_road_weather_says_nothing_of_files_withdrawn_since_the_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 404 there is a gap in the window (DWD removed the file), which the provider logs and answers around."""
    _stub_downloads(monkeypatch, [FileNotFoundError("x"), FileNotFoundError("x")], status=404)
    begin_response()
    assert _road_stations().values().all().df.is_empty()
    assert _told() == []


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_road_weather_tells_of_files_that_hold_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Files that arrived and hold no reading are no file let go: the station has none of the parameter."""
    _stub_downloads(monkeypatch, [BytesIO(b"x" * 142), BytesIO(b"x" * 142)])
    begin_response()
    assert _road_stations().values().all().df.is_empty()
    assert [warning["stations"] for warning in _told()] == [["A006"]]


# KNMI: a timestamp that is not there


def test_knmi_values_say_nothing_of_a_timestamp_that_is_not_there(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A file KNMI answers for with a 404 is a moment it does not have, which the provider skips and warns of."""
    _serve_knmi(monkeypatch, tmp_path, FileNotFoundError("not published"))
    begin_response()
    assert _daily_values(days=2).is_empty()
    assert _told() == []


# SMHI: a parameter file that was refused


@pytest.mark.parametrize(
    ("serving", "told"),
    [
        pytest.param(lambda url: _failed_file(url, FileNotFoundError("not found")), True, id="not reported"),
        pytest.param(lambda url: _refused(url, 403), False, id="refused"),
    ],
)
def test_smhi_values_say_nothing_of_a_file_that_was_refused(
    monkeypatch: pytest.MonkeyPatch, serving: Callable[[str], File], *, told: bool
) -> None:
    """A 404 is SMHI answering that the station does not report the parameter; a refusal is a file let go."""

    def download_files(urls: list[str], **_: object) -> list[File]:
        body = json.dumps({"station": [_STATION]}).encode()
        return [File(url=url, content=BytesIO(body), status=200) for url in urls]

    monkeypatch.setattr(smhi_api, "download_files", download_files)
    monkeypatch.setattr(smhi_api, "download_file", lambda url, **_: serving(url))
    begin_response()
    assert _smhi_request().values().all().df.is_empty()
    assert len(_told()) == (1 if told else 0)


# FMI: an exception report is answered with HTTP 200


@pytest.mark.parametrize(
    ("answer", "told"),
    [
        pytest.param(_EXCEPTION_REPORT, False, id="exception report"),
        pytest.param(_collection(), True, id="empty collection"),
    ],
)
def test_fmi_values_say_nothing_of_an_exception_report(
    monkeypatch: pytest.MonkeyPatch, answer: bytes, *, told: bool
) -> None:
    """FMI answers 200 for an error as well as for a station that reports nothing; only the second is told."""
    import datetime as dt  # noqa: PLC0415

    _serve_fmi(monkeypatch, answer)
    begin_response()
    start = dt.datetime(2024, 1, 1, tzinfo=dt.UTC)
    assert _fmi_values("hourly", start, start + dt.timedelta(hours=1)).is_empty()
    assert len(_told()) == (1 if told else 0)


# the sites that a provider gives up on a file at, one test each: a note removed must fail one of them


def _frost_kind(url: str) -> str:
    """Tell which of the requests of Frost's values a URL is: the batch, one parameter, the listing, a series."""
    if "availableTimeSeries" in url:
        return "available"
    if "timeseriesids=" in url:
        return "series"
    return "batch" if "," in url.split("elements=")[1].split("&", maxsplit=1)[0] else "single"


def _empty_body(url: str) -> File:
    return File(url=url, content=BytesIO(b""), status=200)


_FROST_ANSWERS = {
    "batch empty": {"batch": _empty_body},
    "single empty": {"single": _empty_body},
    "available empty": {"available": _empty_body},
    "series empty": {"series": _empty_body},
    "batch failed": {"batch": lambda url: _frost_answer(url, 500)},
    "single failed": {"single": lambda url: _frost_answer(url, 500)},
    "series failed": {"series": lambda url: _frost_answer(url, 500)},
}


def _frost_listing(url: str) -> File:
    from tests.provider.metno.frost.test_values_failures import AVAILABLE  # noqa: PLC0415
    from tests.provider.metno.frost.test_values_failures import _ok as frost_ok  # noqa: PLC0415

    return frost_ok(url, AVAILABLE)


@pytest.mark.parametrize("case", _FROST_ANSWERS)
def test_frost_values_say_nothing_of_a_body_that_is_empty(monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    """A 200 with no body, and a series the listing just named that is not there, are files let go."""
    answers = {
        "batch": lambda url: _frost_answer(url, 404),
        "single": lambda url: _frost_answer(url, 404),
        "available": _frost_listing,
        "series": lambda url: _frost_answer(url, 404),
        **_FROST_ANSWERS[case],
    }

    values, _seen = _frost_values(monkeypatch, lambda url: answers[_frost_kind(url)](url))
    begin_response()
    assert values.all().df.is_empty()
    assert _told() == []


@pytest.mark.parametrize("status", [404, 412])
def test_frost_values_tell_of_a_series_that_frost_answers_has_no_data(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """Frost's 404 and 412 are its answer for none, and are told.

    The 404 is "No data was found for the query parameters" (a listed series may have a gap in the window), the 412 "No
    available time series for the query parameters" (Frost's swagger of `/observations/v0`).
    """

    def observations(url: str) -> File:
        kind = _frost_kind(url)
        if kind == "available":
            return _frost_listing(url)
        return _frost_answer(url, status if kind == "series" else 404)

    values, _seen = _frost_values(monkeypatch, observations)
    begin_response()
    assert values.all().df.is_empty()
    assert len(_told()) == 1


# AEMET: the link of the data that an envelope of 200 named is not there


def test_aemet_values_say_nothing_of_a_link_of_the_data_that_is_not_there(monkeypatch: pytest.MonkeyPatch) -> None:
    """An envelope that says 200 and a link that answers 404: the chunk is let go, not AEMET's answer of no data."""
    link = "https://opendata.aemet.es/opendata/sh/0123abc"

    def answer(url: str) -> File:
        return _failed_file(url, FileNotFoundError(url)) if url == link else _envelope(url, 200, datos=link)

    _aemet_serving(monkeypatch, answer)
    begin_response()
    assert _values("daily", years=1).is_empty()
    assert _told() == []


# dwd/road: a group of stations is read from one set of files, and each of its stations is told


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.parametrize(
    "contents",
    [
        pytest.param([FileNotFoundError("x"), FileNotFoundError("x")], id="both withdrawn"),
        pytest.param([FileNotFoundError("x"), BytesIO(b"x" * 142)], id="one withdrawn and one empty"),
    ],
)
def test_road_weather_names_none_of_the_stations_of_a_group_a_file_of_which_was_withdrawn(
    monkeypatch: pytest.MonkeyPatch, contents: list[Any]
) -> None:
    """The group is read once and cached for the stations after the first: it is let go for each of them."""
    _stub_downloads(monkeypatch, contents, status=404)
    begin_response()
    assert _road_stations(("A006", "A007")).values().all().df.is_empty()
    assert _told() == []


# dwd/observation and dwd/derived: a file the index listed that is not there


@pytest.mark.parametrize("family", ["observation", "derived"])
@pytest.mark.parametrize(("status", "raises"), [(404, False), (503, True)])
def test_dwd_downloads_let_go_a_file_the_index_listed_that_is_not_there(
    monkeypatch: pytest.MonkeyPatch, family: str, status: int, *, raises: bool
) -> None:
    """A 404 for a listed file is one withdrawn since; any other failure is an outage and raises, as it did."""
    import polars as pl  # noqa: PLC0415

    from wetterdienst import Settings  # noqa: PLC0415
    from wetterdienst.exceptions import DownloadError  # noqa: PLC0415
    from wetterdienst.provider.dwd.derived import download as derived_download  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import download as observation_download  # noqa: PLC0415
    from wetterdienst.util.response_warnings import collecting  # noqa: PLC0415

    module = observation_download if family == "observation" else derived_download
    function = (
        observation_download.download_climate_observations_data
        if family == "observation"
        else derived_download.download_climate_derived_data
    )
    url = "https://opendata.dwd.de/climate_environment/CDC/x/produkt.zip"
    content: Exception = DownloadError(url, "down") if raises else FileNotFoundError(url)
    monkeypatch.setattr(module, "download_files", lambda **_kwargs: [File(url=url, content=content, status=status)])
    letting_go: list[bool] = []

    with collecting(letting_go.append):
        if raises:
            with pytest.raises(DownloadError):
                function(pl.Series([url]), Settings(cache_disable=True))
        else:
            assert function(pl.Series([url]), Settings(cache_disable=True)) == []

    assert bool(letting_go) is not raises


# the parsers of dwd/observation and dwd/derived: a file that would not parse


@pytest.mark.parametrize("family", ["observation", "derived"])
@pytest.mark.parametrize("error", ["schema", "value"])
def test_dwd_parsers_let_go_a_file_that_would_not_parse(
    monkeypatch: pytest.MonkeyPatch, family: str, error: str
) -> None:
    """A file polars cannot read is skipped by the parser, which says so."""
    import polars as pl  # noqa: PLC0415

    from wetterdienst.metadata.period import Period  # noqa: PLC0415
    from wetterdienst.provider.dwd.derived import parser as derived_parser  # noqa: PLC0415
    from wetterdienst.provider.dwd.derived.metadata import DwdDerivedMetadata  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import parser as observation_parser  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata  # noqa: PLC0415
    from wetterdienst.util.response_warnings import collecting  # noqa: PLC0415

    def broken(**_kwargs: object) -> None:
        raise pl.exceptions.SchemaError("x") if error == "schema" else ValueError("x")

    monkeypatch.setattr(pl, "scan_csv", broken)
    file = File(url="https://example.org/produkt.txt", content=BytesIO(b"a;b\n1;2\n"), status=200)
    letting_go: list[bool] = []

    with collecting(letting_go.append):
        if family == "observation":
            observation_parser._parse_climate_observations_data(  # noqa: SLF001
                file, DwdObservationMetadata.daily.climate_summary, Period.RECENT
            )
        else:
            derived_parser._parse_climate_derived_data(file, next(iter(DwdDerivedMetadata["daily"])))  # noqa: SLF001

    assert letting_go == [False]


# the rest of the sites: SMHI's CSV, POI, Météo-France, SWSMOS, WSV


def test_smhi_values_say_nothing_of_a_file_that_would_not_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    """A CSV block the parser raises on is skipped by the provider, which says so."""

    def download_files(urls: list[str], **_: object) -> list[File]:
        body = json.dumps({"station": [_STATION]}).encode()
        return [File(url=url, content=BytesIO(body), status=200) for url in urls]

    def boom(_text: str) -> None:
        msg = "malformed"
        raise ValueError(msg)

    monkeypatch.setattr(smhi_api, "download_files", download_files)
    monkeypatch.setattr(smhi_api, "download_file", lambda url, **_: File(url=url, content=BytesIO(b"x"), status=200))
    monkeypatch.setattr(smhi_api, "parse_smhi_csv", boom)
    begin_response()
    assert _smhi_request().values().all().df.is_empty()
    assert _told() == []


_POI_NO_ROWS = (
    "surface observations;Parameter description;wind_speed_mean_last_10min\n"
    "10147;Unit;km/h\n"
    "Datum;Uhrzeit (UTC);Windgeschwindigkeit\n"
).encode("latin-1")


@pytest.mark.parametrize(
    ("file", "told"),
    [
        pytest.param(lambda url: File(url=url, content=FileNotFoundError(url), status=404), False, id="withdrawn"),
        pytest.param(lambda url: File(url=url, content=BytesIO(b""), status=200), False, id="empty while rewritten"),
        pytest.param(lambda url: File(url=url, content=BytesIO(_POI_NO_ROWS), status=200), True, id="no report"),
    ],
)
def test_poi_values_say_nothing_of_a_report_that_was_withdrawn_or_empty(
    monkeypatch: pytest.MonkeyPatch, file: Callable[[str], File], *, told: bool
) -> None:
    """A report DWD withdrew since the catalogue was read, or is rewriting, is let go; one without a row is not."""
    import datetime as dt  # noqa: PLC0415

    from wetterdienst import Options, Settings  # noqa: PLC0415
    from wetterdienst.provider.dwd.poi import DwdPoiRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.poi import api as poi_api  # noqa: PLC0415

    monkeypatch.setattr(poi_api, "download_file", lambda *_a, url="u", **_k: file(url))
    request = DwdPoiRequest(
        parameters=[("hourly", "data", "wind_speed_mean_last_10min")],
        start=dt.datetime(2026, 10, 11, tzinfo=dt.UTC),
        end=dt.datetime(2026, 10, 13, tzinfo=dt.UTC),
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    )
    begin_response()
    assert stations_result(request, "hourly", "data", "10147").values().all().df.is_empty()
    assert len(_told()) == (1 if told else 0)


def test_meteofrance_observation_says_nothing_of_a_period_file_the_portal_no_longer_has(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A period file the listing names and the portal answers 404 for is let go."""
    from tests.provider.meteofrance.observation.test_api import _utc  # noqa: PLC0415
    from tests.provider.meteofrance.observation.test_api import _values as mf_values  # noqa: PLC0415
    from wetterdienst.provider.meteofrance.observation import api as mf_api  # noqa: PLC0415

    title = "HOR_departement_31_periode_2020-2024"
    resources = [{"title": title, "url": f"https://static.data.gouv.fr/{title}.csv.gz"}]

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        url = url or args[0]
        return File(url=url, content=BytesIO(json.dumps({"resources": resources}).encode("utf8")), status=200)

    def download_files(urls: list[str], **_: object) -> list[File]:
        return [File(url=url, content=FileNotFoundError(url), status=404) for url in urls]

    monkeypatch.setattr(mf_api, "download_file", download_file)
    monkeypatch.setattr(mf_api, "download_files", download_files)
    begin_response()
    assert mf_values("hourly", "core", "temperature_air_2m", "31069001", _utc(2021, 1, 1), _utc(2021, 1, 2)).is_empty()
    assert _told() == []


def test_meteofrance_synop_says_nothing_of_the_year_that_is_not_published(monkeypatch: pytest.MonkeyPatch) -> None:
    """The current year's file, not yet published in early January (a 404), is let go."""
    import datetime as dt  # noqa: PLC0415

    from wetterdienst import Settings  # noqa: PLC0415
    from wetterdienst.provider.meteofrance.synop import MeteoFranceSynopRequest  # noqa: PLC0415
    from wetterdienst.provider.meteofrance.synop import api as synop_api  # noqa: PLC0415

    year = dt.datetime.now(dt.UTC).year

    def download_file(*_args: object, url: str = "u", **_kwargs: object) -> File:
        return File(url=url, content=FileNotFoundError(url), status=404)

    monkeypatch.setattr(synop_api, "download_file", download_file)
    monkeypatch.setattr(synop_api, "cached_copy_is_held", lambda *_a, **_k: False)
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", "temperature_air_2m")],
        start=dt.datetime(year, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(year, 1, 2, tzinfo=dt.UTC),
        settings=Settings(cache_disable=True),
    )
    begin_response()
    assert stations_result(request, "subdaily", "data", "07005").values().all().df.is_empty()
    assert _told() == []


def test_swsmos_says_nothing_of_a_run_that_could_not_be_fetched_for_any_station(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The run is every station's file: a station read after the first, from the frame kept, is not named either."""
    from tests.provider.dwd.swsmos.test_api import _stub_stations as swsmos_stations  # noqa: PLC0415
    from wetterdienst.provider.dwd.swsmos import api as sws_api  # noqa: PLC0415

    listed = [f"{sws_api._BASE_URL}/{sws_api._LATEST_FILE}"]  # noqa: SLF001
    monkeypatch.setattr(sws_api, "list_remote_files_fsspec", lambda *_a, **_k: listed)
    monkeypatch.setattr(
        sws_api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=FileNotFoundError("404"), status=404),
    )
    begin_response()
    assert swsmos_stations(("A006", "B999")).values().all().df.is_empty()
    assert _told() == []


@pytest.mark.parametrize(("unit", "let_go"), [(None, True), ("furlong", True), ("cm", False)])
def test_wsv_values_say_nothing_of_a_series_with_no_unit_or_an_unhandled_one(
    monkeypatch: pytest.MonkeyPatch, unit: str | None, *, let_go: bool
) -> None:
    """A series skipped because its unit is not known is let go; one in a handled unit is read."""
    from types import SimpleNamespace  # noqa: PLC0415

    from wetterdienst import Settings  # noqa: PLC0415
    from wetterdienst.provider.wsv.pegel import api as wsv_api  # noqa: PLC0415
    from wetterdienst.util.response_warnings import collecting  # noqa: PLC0415

    parameter, resolution = next(
        (p, r.name)
        for r in wsv_api.WsvPegelRequest.metadata
        for dataset in r
        for p in dataset
        if p.name_original == "W"
    )
    equidistance = next(e for e, name in wsv_api._EQUIDISTANCE_TO_RESOLUTION.items() if name == resolution)  # noqa: SLF001
    meta = wsv_api.TimeseriesMeta(unit=unit, equidistance=equidistance)
    body = b'[{"timestamp": "2020-01-01T00:00:00+01:00", "value": 1.0}]'

    def download_file(**kwargs: str) -> File:
        return File(url=kwargs["url"], content=BytesIO(body), status=200)

    monkeypatch.setattr(wsv_api, "download_file", download_file)
    values = SimpleNamespace(
        sr=SimpleNamespace(request=SimpleNamespace(settings=Settings(cache_disable=True))),
        _timeseries_meta=lambda _settings: {("0001", "W"): meta},
        _endpoint=wsv_api.WsvPegelValues._endpoint,  # noqa: SLF001
    )
    letting_go: list[bool] = []

    with collecting(letting_go.append):
        df = wsv_api.WsvPegelValues._collect_station_parameter_or_dataset(values, "0001", parameter)  # noqa: SLF001

    assert bool(letting_go) is let_go
    assert df.is_empty() is let_go


@pytest.mark.parametrize("resolution", ["daily", "monthly", "annual", "hourly"])
def test_aemet_values_say_nothing_of_a_chunk_that_failed_at_any_resolution(
    monkeypatch: pytest.MonkeyPatch, resolution: str
) -> None:
    """Each of the places AEMET's values skip a chunk at lets it go: the daily, the yearly and the real-time one."""
    _aemet_serving(monkeypatch, lambda url: _refused(url, 400))
    begin_response()
    assert _values(resolution, years=1).is_empty()
    assert _told() == []


def test_wsv_values_tell_of_a_series_that_pegelonline_says_does_not_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pegelonline answers a series it has not with 404 "Timeseries does not exist.": its answer, not a file let go."""
    from types import SimpleNamespace  # noqa: PLC0415

    from wetterdienst import Settings  # noqa: PLC0415
    from wetterdienst.provider.wsv.pegel import api as wsv_api  # noqa: PLC0415
    from wetterdienst.util.response_warnings import collecting  # noqa: PLC0415

    parameter, resolution = next(
        (p, r.name)
        for r in wsv_api.WsvPegelRequest.metadata
        for dataset in r
        for p in dataset
        if p.name_original == "W"
    )
    equidistance = next(e for e, name in wsv_api._EQUIDISTANCE_TO_RESOLUTION.items() if name == resolution)  # noqa: SLF001
    meta = wsv_api.TimeseriesMeta(unit="cm", equidistance=equidistance)

    def download_file(**kwargs: str) -> File:
        return File(url=kwargs["url"], content=FileNotFoundError(kwargs["url"]), status=404)

    monkeypatch.setattr(wsv_api, "download_file", download_file)
    values = SimpleNamespace(
        sr=SimpleNamespace(request=SimpleNamespace(settings=Settings(cache_disable=True))),
        _timeseries_meta=lambda _settings: {("0001", "W"): meta},
        _endpoint=wsv_api.WsvPegelValues._endpoint,  # noqa: SLF001
    )
    letting_go: list[bool] = []

    with collecting(letting_go.append):
        df = wsv_api.WsvPegelValues._collect_station_parameter_or_dataset(values, "0001", parameter)  # noqa: SLF001

    assert df.is_empty()
    assert letting_go == []


def test_a_request_without_a_window_for_a_dataset_that_needs_one_is_not_told_of(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Python lets a request without a window through, and a provider answers nothing: nothing of the source."""
    _aemet_serving(monkeypatch, lambda url: _refused(url, 400))
    from wetterdienst import Settings  # noqa: PLC0415
    from wetterdienst.provider.aemet.observation import AemetObservationRequest  # noqa: PLC0415

    request = AemetObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        settings=Settings(auth={"aemet": "dummy-key-for-test"}),
    )
    begin_response()
    assert request.filter_by_station_id(MADRID_RETIRO).values().all().df.is_empty()
    assert _told() == []


def test_fmi_values_say_nothing_of_a_fetch_that_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """FMI's 400 (a station it does not know, a stored query it no longer has) is a fetch that failed, and is let go."""
    import datetime as dt  # noqa: PLC0415

    _serve_fmi(monkeypatch, OSError("Unknown 'fmisid' value!"), status=400)
    begin_response()
    start = dt.datetime(2024, 1, 1, tzinfo=dt.UTC)
    assert _fmi_values("hourly", start, start + dt.timedelta(hours=1)).is_empty()
    assert _told() == []
