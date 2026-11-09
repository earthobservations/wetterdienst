"""A file that is final by its name is kept longer than one that is still written to (GH-3929).

Each provider downloads a file with an expiry that follows what the file is: a settled one (the `historical` period
of DWD, SMHI's `corrected-archive`, a MeteoSwiss `_historical` asset, a Met Office release's station-year file) for a
week, one that is still written to (`recent`, `now`, `latest-months`) for five minutes; a day of LHMT and a year of
Météo-France's SYNOP for five minutes until a grace period after they ended, and then for good; and Hub'Eau asks for
URLs that do not change within the five minutes its answers are kept for. The downloads are recorded in place of
made, with the expiry each was asked with.
"""

from __future__ import annotations

import datetime as dt
import json
from io import BytesIO
from itertools import pairwise
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlsplit

import polars as pl
import pytest

from tests.provider.value_stubs import stations_result
from wetterdienst import Settings
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.derived import api as derived_api
from wetterdienst.provider.dwd.derived import download as derived_download
from wetterdienst.provider.dwd.observation import download as observation_download
from wetterdienst.provider.dwd.observation.download import download_climate_observations_data
from wetterdienst.provider.dwd.phenology import DwdPhenologyMetadata, DwdPhenologyRequest
from wetterdienst.provider.dwd.phenology import api as phenology_api
from wetterdienst.provider.eaufrance.hubeau import HubeauRequest
from wetterdienst.provider.eaufrance.hubeau import api as hubeau_api
from wetterdienst.provider.lhmt.observation import LhmtObservationRequest
from wetterdienst.provider.lhmt.observation import api as lhmt_api
from wetterdienst.provider.meteofrance.synop import api as synop_api
from wetterdienst.provider.meteoswiss.observation import MeteoswissObservationRequest
from wetterdienst.provider.meteoswiss.observation import api as meteoswiss_api
from wetterdienst.provider.metoffice.observation import MetOfficeObservationRequest
from wetterdienst.provider.metoffice.observation import api as metoffice_api
from wetterdienst.provider.smhi.observation import api as smhi_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from types import ModuleType

UTC = dt.UTC
FIVE = CacheExpiry.FIVE_MINUTES
WEEK = CacheExpiry.ONE_WEEK
FOREVER = CacheExpiry.INFINITE


def _settings() -> Settings:
    return Settings(cache_disable=True)


def _not_found(url: str) -> File:
    return File(url=url, content=FileNotFoundError(url), status=404)


# DWD: the historical period is final by name, recent and now are appended to


@pytest.mark.parametrize(
    ("period", "expiry"),
    [(Period.HISTORICAL, WEEK), (Period.RECENT, FIVE), (Period.NOW, FIVE), (None, FIVE)],
)
@pytest.mark.parametrize("network", ["observation", "derived"])
def test_dwd_downloads_the_files_of_a_period_with_its_expiry(
    monkeypatch: pytest.MonkeyPatch, network: str, period: Period | None, expiry: CacheExpiry
) -> None:
    """The expiry follows the period of the files, for the observations and for the derived data alike."""
    asked: list[CacheExpiry] = []

    def download_files(urls: list[str], ttl: CacheExpiry, **_: object) -> list[File]:  # noqa: ARG001
        asked.append(ttl)
        return []

    monkeypatch.setattr(observation_download, "download_files", download_files)
    monkeypatch.setattr(derived_download, "download_files", download_files)
    download = (
        observation_download.download_climate_observations_data
        if network == "observation"
        else derived_download.download_climate_derived_data
    )
    download(pl.Series(["https://x/a.zip"]), _settings(), period=period)

    assert asked == [expiry]


def test_dwd_observation_download_without_a_period_is_as_it_was(monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller that names no period (the positional form of before) gets the five minutes it always had."""
    asked: list[CacheExpiry] = []
    monkeypatch.setattr(
        observation_download,
        "download_files",
        lambda urls, ttl, **_: asked.append(ttl) or [],  # noqa: ARG005
    )

    download_climate_observations_data(pl.Series(["https://x/a.zip"]), _settings())

    assert asked == [FIVE]


@pytest.mark.parametrize(
    ("dataset", "periods"),
    [("heating_degreedays", ["historical", "recent"])],
)
def test_dwd_derived_technical_files_follow_their_period(
    monkeypatch: pytest.MonkeyPatch, dataset: str, periods: list[str]
) -> None:
    """The monthly files of the technical datasets are downloaded one by one, each with the expiry of its period."""
    asked: dict[str, CacheExpiry] = {}

    def download_file(*, url: str, ttl: CacheExpiry, **_: object) -> File:
        asked[url] = ttl
        return _not_found(url)

    def listing(url: str, **_: object) -> list[str]:
        return [f"{url}/gradtage_{month}.csv" for month in ("202401", "202402", "202403")]

    monkeypatch.setattr(derived_api, "download_file", download_file)
    monkeypatch.setattr(derived_api, "list_remote_files_fsspec", listing)
    request = DwdDerivedRequest(
        parameters=[("monthly", dataset)],
        periods=periods,
        start=dt.datetime(2024, 1, 1, tzinfo=UTC),
        end=dt.datetime(2024, 3, 1, tzinfo=UTC),
        settings=_settings(),
    )
    values = stations_result(request, "monthly", dataset, "00001").values()
    parameter = request.parameters[0]

    values._collect_station_param_technical_dataset("00001", parameter)  # noqa: SLF001

    assert asked
    assert {ttl for url, ttl in asked.items() if "/historical/" in url} == {WEEK}
    assert {ttl for url, ttl in asked.items() if "/recent/" in url} == {FIVE}
    assert all("/historical/" in url or "/recent/" in url for url in asked)


# SMHI: the corrected archive is final, the latest months are still under quality control


def test_smhi_downloads_the_corrected_archive_for_a_week_and_the_latest_months_for_five_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One series for each period of the resolution: the archive is kept a week, the rolling one five minutes."""
    asked: dict[str, CacheExpiry] = {}

    def download_file(*, url: str, ttl: CacheExpiry, **_: object) -> File:
        asked[url] = ttl
        return _not_found(url)

    monkeypatch.setattr(smhi_api, "download_file", download_file)

    smhi_api.SmhiObservationValues._read_series("188790", "2", Resolution.HOURLY, _settings())  # noqa: SLF001
    smhi_api.SmhiObservationValues._read_series("188790", "2", Resolution.MINUTE_1, _settings())  # noqa: SLF001

    by_period = {url.split("/period/")[1].split("/")[0]: ttl for url, ttl in asked.items()}
    assert by_period == {"corrected-archive": WEEK, "latest-months": FIVE, "latest-day": FIVE}


# MeteoSwiss: the `_historical` assets are final, `_recent` and `_now` are written to

_BASE = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn"
_STATIONS = (
    "station_abbr;station_name;station_canton;station_data_since;station_height_masl;"
    "station_coordinates_wgs84_lat;station_coordinates_wgs84_lon\n"
    "BER;Bern / Zollikofen;BE;01.01.1864;553.0;46.990744;7.464061\n"
)


@pytest.mark.parametrize(
    ("asset", "expiry"),
    [
        ("ogd-smn_ber_h_historical_2000-2009.csv", WEEK),
        ("ogd-smn_ber_h_historical_2010-2019.csv", WEEK),
        ("ogd-smn_ber_h_recent.csv", FIVE),
        ("ogd-smn_ber_h_now.csv", FIVE),
    ],
)
def test_meteoswiss_downloads_a_historical_asset_for_a_week_and_the_others_for_five_minutes(
    monkeypatch: pytest.MonkeyPatch, asset: str, expiry: CacheExpiry
) -> None:
    """The asset is kept by what its name says it is, the decades of the historical file included."""
    names = [
        "ogd-smn_ber_h_historical_2000-2009.csv",
        "ogd-smn_ber_h_historical_2010-2019.csv",
        "ogd-smn_ber_h_recent.csv",
        "ogd-smn_ber_h_now.csv",
    ]
    item = json.dumps({"assets": {name: {"href": f"{_BASE}/ber/{name}"} for name in names}}).encode()
    asked: dict[str, CacheExpiry] = {}

    def download_file(url: str, ttl: CacheExpiry, **_: object) -> File:
        if "ogd-smn_meta_stations.csv" in url:
            return File(url=url, content=BytesIO(_STATIONS.encode("windows-1252")), status=200)
        if "/items/ber" in url:
            return File(url=url, content=BytesIO(item), status=200)
        asked[url.rsplit("/", 1)[-1]] = ttl
        body = "station_abbr;reference_timestamp;tre200h0\nBER;01.01.2010 00:00;4.9\n"
        return File(url=url, content=BytesIO(body.encode("windows-1252")), status=200)

    monkeypatch.setattr(meteoswiss_api, "download_file", download_file)
    request = MeteoswissObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
        start="2005-01-01T00:00:00+00:00",
        end="2015-01-01T00:00:00+00:00",
        settings=_settings(),
    )
    model = request.metadata["hourly"]["data"]

    request.filter_by_station_id("BER").values()._collect_station_parameter_or_dataset("BER", model)  # noqa: SLF001

    assert sorted(asked) == sorted(names)
    assert asked[asset] == expiry


# DWD phenology: the historical release is final by its end year in the name, `recent` is written to


@pytest.mark.parametrize(("period", "expiry"), [(Period.HISTORICAL, WEEK), (Period.RECENT, CacheExpiry.TWELVE_HOURS)])
def test_dwd_phenology_downloads_the_historical_file_for_a_week_and_the_recent_one_for_twelve_hours(
    monkeypatch: pytest.MonkeyPatch, period: Period, expiry: CacheExpiry
) -> None:
    """The file of the period is kept as long as the period allows."""
    asked: list[CacheExpiry] = []

    def download_file(*, url: str, ttl: CacheExpiry, **_: object) -> File:
        asked.append(ttl)
        return File(url=url, content=BytesIO(b""), status=200)

    monkeypatch.setattr(phenology_api, "download_file", download_file)
    monkeypatch.setattr(phenology_api, "_file_url", lambda *_args, **_kwargs: "https://x/hazel.txt")
    monkeypatch.setattr(phenology_api, "_parse_values", lambda *_args, **_kwargs: pl.DataFrame())
    request = DwdPhenologyRequest(parameters=[("annual", "annual_common_hazel")], settings=_settings())
    values = stations_result(request, "annual", "annual_common_hazel", "07521").values()

    values._load(DwdPhenologyMetadata["annual"]["annual_common_hazel"], period)  # noqa: SLF001

    assert asked == [expiry]


# Met Office: the station-year file of a release is final by name, the station metadata of the release is a catalogue


def test_metoffice_downloads_a_station_year_for_a_week_and_the_station_metadata_for_twelve_hours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The file of a station and a year is addressed by the release, the QC version and the year."""
    stations = (
        b"Conventions,G,BADC-CSV,1\ndata\n"
        b"src_id,station_name,station_file_name,historic_county,authority,"
        b"station_latitude,station_longitude,station_elevation,first_year,last_year\n"
        b"00001,FOULA,foula,shetland,Met Office,60.154,-2.074,22,1989,2003\nend data\n"
    )
    asked: dict[str, CacheExpiry] = {}

    def download_file(*, url: str, ttl: CacheExpiry, **_: object) -> File:
        asked[url] = ttl
        if "station-metadata" in url:
            return File(url=url, content=BytesIO(stations), status=200)
        return _not_found(url)

    monkeypatch.setattr(metoffice_api, "download_file", download_file)
    monkeypatch.setattr(metoffice_api.MetOfficeObservationValues, "_token", lambda _self, _settings: "token")
    monkeypatch.setattr(metoffice_api, "latest_release_version", lambda *_args, **_kwargs: "202507")
    request = MetOfficeObservationRequest(
        parameters=[("daily", "rain")],
        start=dt.datetime(2000, 1, 1, tzinfo=UTC),
        end=dt.datetime(2001, 1, 2, tzinfo=UTC),
        settings=_settings(),
    )
    values = stations_result(request, "daily", "rain", "00001").values()

    values._collect_station_parameter_or_dataset("00001", request.metadata["daily"]["rain"])  # noqa: SLF001

    years = {url: ttl for url, ttl in asked.items() if "qcv-" in url}
    assert years, "no station-year file was asked for"
    assert set(years.values()) == {WEEK}
    assert {ttl for url, ttl in asked.items() if "station-metadata" in url} == {CacheExpiry.TWELVE_HOURS}


# LHMT: a day is kept five minutes until six hours after it ended


def _pin(monkeypatch: pytest.MonkeyPatch, module: ModuleType, now: dt.datetime) -> None:
    monkeypatch.setattr(module, "_now", lambda: now)


def _lhmt_expiry(monkeypatch: pytest.MonkeyPatch, day: dt.date, now: dt.datetime) -> CacheExpiry:
    asked: list[CacheExpiry] = []

    def download_file(*, url: str, ttl: CacheExpiry, **_: object) -> File:
        asked.append(ttl)
        return _not_found(url)

    monkeypatch.setattr(lhmt_api, "download_file", download_file)
    _pin(monkeypatch, lhmt_api, now)
    request = LhmtObservationRequest(
        parameters=[("hourly", "data")], start=day.isoformat(), end=day.isoformat(), settings=_settings()
    )
    values = stations_result(request, "hourly", "data", "vilniaus-ams").values()
    values._download_day("vilniaus-ams", day, _settings())  # noqa: SLF001
    (expiry,) = asked
    return expiry


@pytest.mark.parametrize(
    ("now", "expiry"),
    [
        # the day is on, and the day has just ended
        (dt.datetime(2026, 11, 8, 12, tzinfo=UTC), FIVE),
        (dt.datetime(2026, 11, 9, 0, 0, 0, tzinfo=UTC), FIVE),
        # one microsecond short of six hours after the end of the day, and the six hours
        (dt.datetime(2026, 11, 9, 5, 59, 59, 999999, tzinfo=UTC), FIVE),
        (dt.datetime(2026, 11, 9, 6, 0, 0, tzinfo=UTC), FOREVER),
        (dt.datetime(2026, 12, 1, tzinfo=UTC), FOREVER),
    ],
)
def test_lhmt_keeps_a_day_for_good_six_hours_after_it_ended(
    monkeypatch: pytest.MonkeyPatch, now: dt.datetime, expiry: CacheExpiry
) -> None:
    """The day 2026-11-08 ends at 00:00 UTC on the 9th, and is settled 6 hours later."""
    assert _lhmt_expiry(monkeypatch, dt.date(2026, 11, 8), now) is expiry


def test_lhmt_keeps_a_day_to_come_and_a_day_long_past_as_it_did(monkeypatch: pytest.MonkeyPatch) -> None:
    """Today (the day is not over) is short, a day of a year ago is for good."""
    now = dt.datetime(2026, 11, 9, 12, tzinfo=UTC)
    assert _lhmt_expiry(monkeypatch, dt.date(2026, 11, 9), now) is FIVE
    assert _lhmt_expiry(monkeypatch, dt.date(2025, 11, 9), now) is FOREVER


# Météo-France SYNOP: a year is kept five minutes until seven days after it ended


def _synop_download(monkeypatch: pytest.MonkeyPatch, year: int, now: dt.datetime, *, held: bool = False) -> list[dict]:
    calls: list[dict] = []

    def download_file(**kwargs: Any) -> File:  # noqa: ANN401
        calls.append(kwargs)
        return _not_found(kwargs["url"])

    monkeypatch.setattr(synop_api, "download_file", download_file)
    monkeypatch.setattr(synop_api, "cached_copy_is_held", lambda *_args, **_kwargs: held)
    _pin(monkeypatch, synop_api, now)
    synop_api._download_year(year, _settings())  # noqa: SLF001
    return calls


@pytest.mark.parametrize(
    ("year", "now", "expiry"),
    [
        # the year is on
        (2026, dt.datetime(2026, 11, 9, tzinfo=UTC), FIVE),
        # 2025 ended at 00:00 UTC on 2026-01-01: just ended, one microsecond short of 7 days, and the 7 days
        (2025, dt.datetime(2026, 1, 1, tzinfo=UTC), FIVE),
        (2025, dt.datetime(2026, 1, 7, 23, 59, 59, 999999, tzinfo=UTC), FIVE),
        (2025, dt.datetime(2026, 1, 8, tzinfo=UTC), FOREVER),
        (2025, dt.datetime(2026, 11, 9, tzinfo=UTC), FOREVER),
        (1999, dt.datetime(2026, 11, 9, tzinfo=UTC), FOREVER),
    ],
)
def test_synop_keeps_a_year_for_good_seven_days_after_it_ended(
    monkeypatch: pytest.MonkeyPatch, year: int, now: dt.datetime, expiry: CacheExpiry
) -> None:
    """The year 2025 is settled a week after it ended; the year 2026 is on until it is over."""
    (call,) = _synop_download(monkeypatch, year, now)
    assert call["ttl"] is expiry


def test_synop_does_not_date_again_a_year_that_is_not_kept_for_good_yet(monkeypatch: pytest.MonkeyPatch) -> None:
    """A year in its grace is downloaded as the current one is; the second look at a held copy is for settled years."""
    inside = _synop_download(monkeypatch, 2025, dt.datetime(2026, 1, 3, tzinfo=UTC), held=True)
    after = _synop_download(monkeypatch, 2025, dt.datetime(2026, 1, 9, tzinfo=UTC), held=True)

    assert [call["refetch_undated"] for call in inside] == [False]
    assert after[0]["refetch_undated"] is True


# Hub'Eau: the URLs of the last 30 days are the same for as long as the answers are cached


def _hubeau_urls(monkeypatch: pytest.MonkeyPatch, now: dt.datetime) -> list[str]:
    urls: list[str] = []

    def paged_rows(url: str, settings: Settings, *, ttl: CacheExpiry, timeout: int) -> list[dict]:  # noqa: ARG001
        assert ttl is FIVE
        urls.append(url)
        return []

    monkeypatch.setattr(hubeau_api, "_paged_rows", paged_rows)
    # a page of 1000 observations: the 30 days of a 15 minute station are three chunks
    monkeypatch.setattr(hubeau_api, "_VALUES_PAGE_SIZE", 1000)
    _pin(monkeypatch, hubeau_api, now)
    request = HubeauRequest(
        parameters=[("15_minutes", "data", "stage")], start="2026-11-01", end="2026-11-02", settings=_settings()
    )
    values = stations_result(request, "15_minutes", "data", "1011000101").values()
    values._collect_station_parameter_or_dataset("1011000101", request.parameters[0])  # noqa: SLF001
    return urls


def _window(url: str) -> tuple[dt.datetime, dt.datetime]:
    query = parse_qs(urlsplit(url).query)
    return (
        dt.datetime.fromisoformat(query["date_debut_obs"][0]),
        dt.datetime.fromisoformat(query["date_fin_obs"][0]),
    )


def test_hubeau_asks_the_same_urls_within_the_five_minutes_its_answers_are_kept_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The end of the window is rounded down to the start of the five minutes: no microsecond is in a URL."""
    first = _hubeau_urls(monkeypatch, dt.datetime(2026, 11, 9, 12, 5, 0, 1, tzinfo=UTC))
    later = _hubeau_urls(monkeypatch, dt.datetime(2026, 11, 9, 12, 9, 59, 999999, tzinfo=UTC))
    next_window = _hubeau_urls(monkeypatch, dt.datetime(2026, 11, 9, 12, 10, 0, tzinfo=UTC))

    assert len(first) == 3
    assert first == later
    assert first != next_window
    # the same chunks, shifted by the five minutes
    assert len(next_window) == len(first)
    assert [_window(url) for url in next_window] == [
        (start + dt.timedelta(minutes=5), end + dt.timedelta(minutes=5)) for start, end in map(_window, first)
    ]


def test_hubeau_window_still_covers_the_last_30_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """The window is closed at the start of the five minutes `now` is in, and runs 30 days back from there."""
    now = dt.datetime(2026, 11, 9, 12, 7, 31, 123456, tzinfo=UTC)
    windows = [_window(url) for url in _hubeau_urls(monkeypatch, now)]

    assert len(windows) == 3
    assert windows[0][0] == dt.datetime(2026, 10, 10, 12, 5, tzinfo=None)  # noqa: DTZ001
    assert windows[-1][1] == dt.datetime(2026, 11, 9, 12, 5, tzinfo=None)  # noqa: DTZ001
    # chunks that follow each other without a gap or an overlap
    assert all(earlier[1] == later[0] for earlier, later in pairwise(windows))
    assert now.replace(tzinfo=None) - windows[-1][1] < dt.timedelta(minutes=5)


def test_hubeau_window_end_is_in_utc_whatever_the_zone_of_now() -> None:
    """A `now` given in another zone is the same instant, and the same window."""
    cest = dt.timezone(dt.timedelta(hours=2))
    utc = dt.datetime(2026, 11, 9, 10, 7, 31, tzinfo=UTC)

    window_end = hubeau_api._window_end  # noqa: SLF001
    assert window_end(utc.astimezone(cest)) == window_end(utc) == dt.datetime(2026, 11, 9, 10, 5, tzinfo=None)  # noqa: DTZ001
