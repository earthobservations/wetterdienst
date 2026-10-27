"""The files a provider names for the fetch-ahead are the files its own collection downloads (GH-3454).

A hook that names a URL the collection does not ask for fetches it for nothing, and one that leaves a URL out leaves it
to be downloaded at the station's turn: neither is seen in an answer, so each provider's hook is held to its
collection here, with the downloads recorded in place of made.
"""

from __future__ import annotations

import contextlib
import datetime as dt
from typing import TYPE_CHECKING

import polars as pl
import pytest

from tests.provider.value_stubs import stations_result
from wetterdienst import Settings
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.chmi.observation import ChmiObservationRequest
from wetterdienst.provider.chmi.observation import api as chmi_api
from wetterdienst.provider.dwd.derived import DwdDerivedMetadata, DwdDerivedRequest
from wetterdienst.provider.dwd.derived import api as derived_api
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation import api as observation_api
from wetterdienst.provider.imgw.meteorology import ImgwMeteorologyRequest
from wetterdienst.provider.imgw.meteorology import api as imgw_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
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
    downloaded: list[str] = []

    def file_list(
        station_id: str,
        dataset_: object,
        period: Period,
        settings: Settings,  # noqa: ARG001
        date_ranges: object,
    ) -> pl.Series:
        name = getattr(dataset_, "name", "?")
        return pl.Series([f"https://x/{name}/{station_id}/{period.value}/{date_ranges}.zip"])

    def download(remote_files: pl.Series, settings: Settings, dataset_: object = None) -> list[File]:  # noqa: ARG001
        downloaded.extend(remote_files.to_list())
        return []

    monkeypatch.setattr(observation_api, "create_file_list_for_climate_observations", file_list)
    monkeypatch.setattr(observation_api, "download_climate_observations_data", download)
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
    assert list(named.urls) == downloaded
    assert named.ttl is CacheExpiry.FIVE_MINUTES


def test_dwd_derived_names_the_archives_it_downloads_and_none_of_a_technical_dataset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The archives of the station for each period; the monthly files of the whole network are left to the first."""
    downloaded: list[str] = []

    def file_list(station_id: str, dataset: object, period: Period, settings: Settings) -> pl.Series:  # noqa: ARG001
        return pl.Series([f"https://x/{getattr(dataset, 'name', '?')}/{station_id}/{period.value}.zip"])

    def download(remote_files: pl.Series, settings: Settings) -> list[File]:  # noqa: ARG001
        downloaded.extend(remote_files.to_list())
        return []

    monkeypatch.setattr(derived_api, "create_file_list_for_climate_derived", file_list)
    monkeypatch.setattr(derived_api, "download_climate_derived_data", download)
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
    assert list(named.urls) == downloaded
    assert named.ttl is CacheExpiry.FIVE_MINUTES
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

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        asked.append(url or args[0])
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
    assert named.ttl is CacheExpiry.TWELVE_HOURS


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

    def download_files(urls: list[str], **_: object) -> list[File]:
        downloaded.extend(urls)
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
