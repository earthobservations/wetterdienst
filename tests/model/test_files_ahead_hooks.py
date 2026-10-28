"""The files a provider names for the fetch-ahead are the files its own collection downloads (GH-3454).

A hook that names a URL the collection does not ask for fetches it for nothing, and one that leaves a URL out leaves it
to be downloaded at the station's turn: neither is seen in an answer, so each provider's hook is held to its
collection here, with the downloads recorded in place of made.
"""

from __future__ import annotations

import contextlib
import datetime as dt
from io import BytesIO
from typing import TYPE_CHECKING, cast

import polars as pl
import pytest

from tests.provider.value_stubs import stations_result
from wetterdienst import Settings
from wetterdienst.provider.chmi.observation import ChmiObservationRequest
from wetterdienst.provider.chmi.observation import api as chmi_api
from wetterdienst.provider.dwd.derived import DwdDerivedMetadata, DwdDerivedRequest
from wetterdienst.provider.dwd.derived import api as derived_api
from wetterdienst.provider.dwd.derived import download as derived_download
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation import api as observation_api
from wetterdienst.provider.dwd.observation import download as observation_download
from wetterdienst.provider.imgw.meteorology import ImgwMeteorologyRequest
from wetterdienst.provider.imgw.meteorology import api as imgw_api
from wetterdienst.provider.smhi.observation import SmhiObservationRequest
from wetterdienst.provider.smhi.observation import api as smhi_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from wetterdienst.metadata.cache import CacheExpiry
    from wetterdienst.metadata.period import Period
    from wetterdienst.model.values import TimeseriesValues

UTC = dt.UTC
STATION = "00001"


def _settings() -> Settings:
    return Settings(cache_disable=True)


@pytest.mark.parametrize(
    ("resolution", "dataset", "parameter", "periods"),
    [
        ("daily", "climate_summary", "temperature_air_mean_2m", ["historical", "recent"]),
        # the historical files of the fine resolutions are cut to the date ranges the window needs
        ("1_minute", "precipitation", "precipitation_amount", ["historical", "recent"]),
    ],
)
def test_dwd_observation_names_the_archives_it_downloads(
    monkeypatch: pytest.MonkeyPatch, resolution: str, dataset: str, parameter: str, periods: list[str]
) -> None:
    """The archives of every period of the station, with the date ranges the historical period is cut to."""
    downloaded: list[tuple[str, CacheExpiry]] = []

    def file_list(
        station_id: str,
        dataset_: object,
        period: Period,
        settings: Settings,  # noqa: ARG001
        date_ranges: object,
    ) -> pl.Series:
        name = getattr(dataset_, "name", "?")
        return pl.Series([f"https://x/{name}/{station_id}/{period.value}/{date_ranges}.zip"])

    # the download of the archives is the collection's own, which asks `download_files` for them with an expiry
    def download_files(urls: list[str], ttl: CacheExpiry, **_: object) -> list[File]:
        downloaded.extend((url, ttl) for url in urls)
        return []

    monkeypatch.setattr(observation_api, "create_file_list_for_climate_observations", file_list)
    monkeypatch.setattr(observation_download, "download_files", download_files)
    monkeypatch.setattr(
        observation_api.DwdObservationValues, "_get_historical_date_ranges", lambda *_, **__: ["20000101_20091231"]
    )
    request = DwdObservationRequest(
        parameters=[(resolution, dataset, parameter)],
        periods=periods,
        start=dt.datetime(2005, 1, 1, tzinfo=UTC),
        settings=_settings(),
    )
    values = stations_result(request, resolution, dataset, STATION).values()
    model = request.metadata[resolution][dataset]

    values._collect_station_parameter_or_dataset(STATION, model)  # noqa: SLF001
    named = values._files_ahead(STATION, [model])  # noqa: SLF001

    assert downloaded, "the collection downloaded nothing"
    assert list(named.urls) == [url for url, _ in downloaded]
    assert {ttl for _, ttl in downloaded} == {named.ttl}


def test_dwd_derived_names_the_archives_it_downloads_and_none_of_a_technical_dataset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The archives of the station for each period; the monthly files of the whole network are left to the first."""
    downloaded: list[tuple[str, CacheExpiry]] = []

    def file_list(station_id: str, dataset: object, period: Period, settings: Settings) -> pl.Series:  # noqa: ARG001
        return pl.Series([f"https://x/{getattr(dataset, 'name', '?')}/{station_id}/{period.value}.zip"])

    def download_files(urls: list[str], ttl: CacheExpiry, **_: object) -> list[File]:
        downloaded.extend((url, ttl) for url in urls)
        return []

    monkeypatch.setattr(derived_api, "create_file_list_for_climate_derived", file_list)
    monkeypatch.setattr(derived_download, "download_files", download_files)
    request = DwdDerivedRequest(parameters=[("hourly", "radiation_global")], settings=_settings())
    values = stations_result(request, "hourly", "radiation_global", STATION).values()
    model = request.metadata["hourly"]["radiation_global"]

    # what is made of the files that were not downloaded is of no interest, the periods are all it goes through
    monkeypatch.setattr(derived_api, "parse_climate_derived_data", lambda *_: pl.LazyFrame({"timestamp": []}))
    with contextlib.suppress(Exception):
        values._collect_station_parameter_or_dataset(STATION, model)  # noqa: SLF001
    named = values._files_ahead(STATION, [model])  # noqa: SLF001
    technical = values._files_ahead(STATION, [DwdDerivedMetadata.monthly.heating_degreedays])  # noqa: SLF001

    assert downloaded, "the collection downloaded nothing"
    assert list(named.urls) == [url for url, _ in downloaded]
    assert {ttl for _, ttl in downloaded} == {named.ttl}
    assert list(technical.urls) == []


@pytest.mark.parametrize(
    ("resolution", "window"),
    [
        ("daily", None),
        ("hourly", (dt.datetime(2024, 12, 30, tzinfo=UTC), dt.datetime(2025, 2, 2, tzinfo=UTC))),
    ],
)
def test_chmi_names_the_files_of_each_element_and_month_it_downloads(
    monkeypatch: pytest.MonkeyPatch, resolution: str, window: tuple[dt.datetime, dt.datetime] | None
) -> None:
    """One file for each element, and for the sub-daily layout one for each month of the window."""
    asked: list[str] = []
    expiries: list[CacheExpiry] = []

    def download_file(*args: str, url: str | None = None, ttl: CacheExpiry | None = None, **_: object) -> File:
        asked.append(url or args[0])
        expiries.append(cast("CacheExpiry", ttl))
        return File(url=asked[-1], content=FileNotFoundError(asked[-1]), status=404)

    monkeypatch.setattr(chmi_api, "download_file", download_file)
    start, end = window or (dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 1, 3, tzinfo=UTC))
    request = ChmiObservationRequest(parameters=[(resolution, "data")], start=start, end=end, settings=_settings())
    values = stations_result(request, resolution, "data", "0-20000-0-11406").values()
    model = request.metadata[resolution]["data"]

    values._collect_station_parameter_or_dataset("0-20000-0-11406", model)  # noqa: SLF001
    named = values._files_ahead("0-20000-0-11406", [model])  # noqa: SLF001

    assert len(asked) > 1
    assert list(named.urls) == asked
    assert set(expiries) == {named.ttl}


def test_chmi_names_only_the_elements_that_were_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    """A request for one parameter of the dataset downloads the file of its element and no other."""
    asked: list[str] = []

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        asked.append(url or args[0])
        return File(url=asked[-1], content=FileNotFoundError(asked[-1]), status=404)

    monkeypatch.setattr(chmi_api, "download_file", download_file)
    request = ChmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start=dt.datetime(2020, 1, 1, tzinfo=UTC),
        end=dt.datetime(2020, 1, 3, tzinfo=UTC),
        settings=_settings(),
    )
    values = stations_result(request, "daily", "data", "0-20000-0-11406").values()
    model = request.metadata["daily"]["data"]

    values._collect_station_parameter_or_dataset("0-20000-0-11406", model)  # noqa: SLF001
    named = values._files_ahead("0-20000-0-11406", [model])  # noqa: SLF001

    assert len(asked) == 1
    assert list(named.urls) == asked


def test_chmi_names_no_sub_daily_file_where_the_window_is_open() -> None:
    """The month files are addressed by the window, and a request without one has none to name."""
    request = ChmiObservationRequest(parameters=[("hourly", "data")], settings=_settings())
    values = stations_result(request, "hourly", "data", "0-20000-0-11406").values()

    assert list(values._files_ahead("0-20000-0-11406", [request.metadata["hourly"]["data"]]).urls) == []  # noqa: SLF001


@pytest.mark.parametrize(
    ("resolution", "dataset", "per_station"), [("daily", "synop", True), ("monthly", "synop", False)]
)
def test_imgw_names_only_the_archives_that_one_station_reads(
    monkeypatch: pytest.MonkeyPatch, resolution: str, dataset: str, *, per_station: bool
) -> None:
    """The daily synop is archived per station; the files of the other datasets are those of every station."""
    downloaded: list[str] = []
    expiries: list[CacheExpiry] = []

    def download_files(urls: list[str], ttl: CacheExpiry, **_: object) -> list[File]:
        downloaded.extend(urls)
        expiries.append(ttl)
        return []

    monkeypatch.setattr(imgw_api, "download_files", download_files)
    monkeypatch.setattr(imgw_api.ImgwMeteorologyValues, "_get_urls", lambda *args: [f"https://x/{args[-1]}.zip"])
    request = ImgwMeteorologyRequest(parameters=[(resolution, dataset)], settings=_settings())
    values: TimeseriesValues = stations_result(request, resolution, dataset, "249180010").values()
    model = request.metadata[resolution][dataset]

    values._collect_station_parameter_or_dataset("249180010", model)  # noqa: SLF001
    named = values._files_ahead("249180010", [model])  # noqa: SLF001

    assert downloaded == ["https://x/249180010.zip"]
    assert list(named.urls) == (downloaded if per_station else [])
    assert expiries == [named.ttl]


@pytest.mark.parametrize(
    ("resolution", "parameters", "per_parameter"),
    [
        # the corrected-archive and the latest-months file of each parameter
        ("hourly", ["temperature_air_2m", "humidity_relative"], 4),
        # a wind direction is read with the speed beside it, asked for or not
        ("hourly", ["wind_direction_mean_last_10min"], 4),
        ("hourly", ["wind_direction_mean_last_10min", "wind_speed_mean_last_10min"], 4),
        # one rolling file for each parameter in the minute resolution, and the speed beside the direction
        ("1_minute", ["wind_direction_mean", "temperature_air_2m"], 3),
        ("monthly", ["temperature_air_mean_2m"], 2),
    ],
)
def test_smhi_names_the_series_of_each_parameter_and_period_it_downloads(
    monkeypatch: pytest.MonkeyPatch, resolution: str, parameters: list[str], per_parameter: int
) -> None:
    """One file for each period of the resolution and each parameter, and the speed beside a direction."""
    asked: list[str] = []
    expiries: list[CacheExpiry] = []
    # a series that is read, so that the speed beside a direction is asked for as well: the collection goes on to it
    # only where the direction file is there
    date = "Representativ månad;" if resolution == "monthly" else "Datum;Tid (UTC);"
    row = "2024-01;" if resolution == "monthly" else "2024-01-01;00:00:00;"
    csv = f"{date}Value;Kvalitet\n{row}1.0;G\n".encode()

    def download_file(*args: str, url: str | None = None, ttl: CacheExpiry | None = None, **_: object) -> File:
        asked.append(url or args[0])
        expiries.append(cast("CacheExpiry", ttl))
        return File(url=asked[-1], content=BytesIO(csv), status=200)

    monkeypatch.setattr(smhi_api, "download_file", download_file)
    request = SmhiObservationRequest(
        parameters=[(resolution, "data", parameter) for parameter in parameters], settings=_settings()
    )
    values = stations_result(request, resolution, "data", "188790").values()
    model = request.metadata[resolution]["data"]

    values._collect_station_data("188790", [model])  # noqa: SLF001
    named = values._files_ahead("188790", [model])  # noqa: SLF001

    assert len(asked) >= per_parameter
    # the collection reads a speed twice when it is asked for beside its direction: the cache holds it once
    assert list(named.urls) == list(dict.fromkeys(asked))
    assert len(named.urls) == per_parameter
    assert set(expiries) == {named.ttl}
    assert all("/station/188790/period/" in url for url in named.urls)


def test_smhi_names_the_files_of_the_datasets_it_is_given_and_no_more() -> None:
    """A dataset the station does not have is not collected, so its files are not named."""
    request = SmhiObservationRequest(
        parameters=[("hourly", "data", "temperature_air_2m"), ("daily", "data", "temperature_air_mean_2m")],
        settings=_settings(),
    )
    values = stations_result(request, "hourly", "data", "188790").values()

    named = values._files_ahead("188790", [request.metadata["daily"]["data"]])  # noqa: SLF001

    assert [url.split("/parameter/")[1] for url in named.urls] == [
        "2/station/188790/period/corrected-archive/data.csv",
        "2/station/188790/period/latest-months/data.csv",
    ]
