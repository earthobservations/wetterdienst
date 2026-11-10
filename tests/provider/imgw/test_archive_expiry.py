# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""How long the IMGW archives are kept in the cache: 12 hours once their period has ended (GH-3931).

The clock is pinned (`fileindex._now`) to 2026-11-10: November 2026 and the year 2026 are under way. The names are
those of the archives of IMGW's file server, the periods are those `_get_archives` reads from them.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from wetterdienst import Settings
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.imgw import fileindex
from wetterdienst.provider.imgw.fileindex import archive_expiry, download_archives
from wetterdienst.provider.imgw.hydrology import api as hydrology_api
from wetterdienst.provider.imgw.hydrology.api import ImgwHydrologyMetadata, ImgwHydrologyValues
from wetterdienst.provider.imgw.meteorology import api as meteorology_api
from wetterdienst.provider.imgw.meteorology.api import ImgwMeteorologyMetadata, ImgwMeteorologyValues
from wetterdienst.util.network import File

UTC = dt.UTC
FIVE = CacheExpiry.FIVE_MINUTES
TWELVE = CacheExpiry.TWELVE_HOURS
NOW = dt.datetime(2026, 11, 10, 7, 42, tzinfo=UTC)
WINDOW = (dt.datetime(1950, 1, 1, tzinfo=UTC), dt.datetime(2030, 1, 1, tzinfo=UTC))
STATION = "249180010"


@pytest.fixture(autouse=True)
def _pinned_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fileindex, "_now", lambda: NOW)


def _hydrology(
    monkeypatch: pytest.MonkeyPatch, resolution: str, names: list[str], window: tuple[dt.datetime, dt.datetime] | None
) -> dict[str, CacheExpiry]:
    """Give the expiry of each file name of a listing, as `_get_archives` of the hydrology values has it."""
    files = [f"https://example.invalid/{name}" for name in names]
    values = ImgwHydrologyValues.__new__(ImgwHydrologyValues)
    values.sr = SimpleNamespace(  # ty: ignore[invalid-assignment]
        start=window[0] if window else None,
        end=window[1] if window else None,
        settings=Settings(cache_disable=True),
    )
    monkeypatch.setattr(hydrology_api, "list_files_for_interval", lambda *_, **__: files)
    archives = values._get_archives(getattr(ImgwHydrologyMetadata, resolution).hydrology)  # noqa: SLF001
    return {url.rsplit("/", 1)[-1]: ttl for url, ttl in archives.items()}


def _meteorology(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    dataset: str,
    names: list[str],
    window: tuple[dt.datetime, dt.datetime] | None,
) -> dict[str, CacheExpiry]:
    """Give the expiry of each file name of a listing, as `_get_archives` of the meteorology values has it."""
    files = [f"https://example.invalid/{name}" for name in names]
    values = ImgwMeteorologyValues.__new__(ImgwMeteorologyValues)
    values.sr = SimpleNamespace(  # ty: ignore[invalid-assignment]
        start=window[0] if window else None,
        end=window[1] if window else None,
        settings=Settings(cache_disable=True),
    )
    monkeypatch.setattr(meteorology_api, "list_files_for_interval", lambda *_, **__: files)
    archives = values._get_archives(getattr(getattr(ImgwMeteorologyMetadata, resolution), dataset), STATION)  # noqa: SLF001
    return {url.rsplit("/", 1)[-1]: ttl for url, ttl in archives.items()}


def test_an_archive_is_kept_12_hours_from_the_instant_its_period_ended() -> None:
    """The period of a file ends at 00:00 UTC of the day after its last: a microsecond before it is under way."""
    last_day = dt.datetime(2026, 10, 31, tzinfo=UTC)
    end = dt.datetime(2026, 11, 1, tzinfo=UTC)
    micro = dt.timedelta(microseconds=1)
    assert archive_expiry(last_day, end - micro) is FIVE
    assert archive_expiry(last_day, end) is TWELVE
    assert archive_expiry(last_day, end + micro) is TWELVE


def test_an_archive_whose_period_is_unknown_is_kept_five_minutes() -> None:
    """A period that could not be read fails safe."""
    assert archive_expiry(None, NOW) is FIVE


@pytest.mark.parametrize(
    ("resolution", "names", "expected"),
    [
        (
            # the month of the name is a hydrological month: 2027/01 is November 2026, 2026/12 is October 2026
            "daily",
            ["codz_2022_05.zip", "codz_2026_12.zip", "codz_2027_01.zip", "codz_2027_02.zip"],
            [TWELVE, TWELVE, FIVE, FIVE],
        ),
        # a year file ends with the November of its year in the file index; the years before it are final
        ("daily", ["codz_2022.zip", "codz_2025.zip", "codz_2026.zip", "codz_2027.zip"], [TWELVE, TWELVE, FIVE, FIVE]),
        ("monthly", ["mies_2022.zip", "mies_2025.zip", "mies_2026.zip", "mies_2027.zip"], [TWELVE, TWELVE, FIVE, FIVE]),
    ],
)
def test_hydrology_keeps_the_archives_of_a_finished_period_12_hours(
    monkeypatch: pytest.MonkeyPatch, resolution: str, names: list[str], expected: list[CacheExpiry]
) -> None:
    """A closed month or year is 12 hours, the one that is under way 5 minutes."""
    assert _hydrology(monkeypatch, resolution, names, WINDOW) == dict(zip(names, expected, strict=True))


@pytest.mark.parametrize("resolution", ["daily", "monthly"])
def test_hydrology_keeps_an_archive_whose_name_has_no_period_five_minutes(
    monkeypatch: pytest.MonkeyPatch, resolution: str
) -> None:
    """Without a window nothing selects by the period, and a name that has none is kept 5 minutes."""
    names = ["codz_abc.zip" if resolution == "daily" else "mies_abc.zip", "codz_2022_05.zip"]
    expiries = _hydrology(monkeypatch, resolution, names, None)
    assert expiries[names[0]] is FIVE


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # the hydrological month 01 of 2027 is November 2026, which ends 2026-12-01 00:00 UTC
        (dt.datetime(2026, 11, 30, 23, 59, 59, 999999, tzinfo=UTC), FIVE),
        (dt.datetime(2026, 12, 1, tzinfo=UTC), TWELVE),
    ],
)
def test_hydrology_changes_the_expiry_at_the_end_of_the_period(
    monkeypatch: pytest.MonkeyPatch, now: dt.datetime, expected: CacheExpiry
) -> None:
    """A microsecond before the period ends its archive is still written to, at the instant it ends it is final."""
    monkeypatch.setattr(fileindex, "_now", lambda: now)
    assert _hydrology(monkeypatch, "daily", ["codz_2027_01.zip"], WINDOW) == {"codz_2027_01.zip": expected}


@pytest.mark.parametrize(
    ("resolution", "dataset", "names", "expected"),
    [
        (
            "daily",
            "climate",
            [
                "1951_k.zip",
                "2025_k.zip",
                "2026_k.zip",
                "2026_09_k.zip",
                "2026_10_k.zip",
                "2026_11_k.zip",
                "2026_12_k.zip",
            ],
            [TWELVE, TWELVE, FIVE, TWELVE, TWELVE, FIVE, FIVE],
        ),
        (
            "monthly",
            "climate",
            ["1951_m_k.zip", "1951_1955_m_k.zip", "2025_m_k.zip", "2026_m_k.zip", "2025_2026_m_k.zip"],
            [TWELVE, TWELVE, TWELVE, FIVE, FIVE],
        ),
        (
            # per station: a year, and the decades of the older data; the files of other stations are not named
            "daily",
            "synop",
            ["1951_1955_010_s.zip", "2024_010_s.zip", "2025_010_s.zip", "2026_010_s.zip", "2026_020_s.zip"],
            [TWELVE, TWELVE, TWELVE, FIVE],
        ),
    ],
)
def test_meteorology_keeps_the_archives_of_a_finished_period_12_hours(
    monkeypatch: pytest.MonkeyPatch, resolution: str, dataset: str, names: list[str], expected: list[CacheExpiry]
) -> None:
    """A closed month or year is 12 hours, the one that is under way 5 minutes, for every pattern of file name."""
    kept = names[:-1] if dataset == "synop" else names
    assert _meteorology(monkeypatch, resolution, dataset, names, WINDOW) == dict(zip(kept, expected, strict=True))


@pytest.mark.parametrize(("resolution", "dataset"), [("daily", "climate"), ("monthly", "climate"), ("daily", "synop")])
def test_meteorology_keeps_an_archive_whose_name_has_no_period_five_minutes(
    monkeypatch: pytest.MonkeyPatch, resolution: str, dataset: str
) -> None:
    """Without a window nothing selects by the period, and a name that has none is kept 5 minutes."""
    name = {"climate": "abc_k.zip" if resolution == "daily" else "abc_m_k.zip", "synop": "abc_010_s.zip"}[dataset]
    expiries = _meteorology(monkeypatch, resolution, dataset, [name, "2020_010_s.zip"], None)
    assert expiries[name] is FIVE


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (dt.datetime(2026, 10, 31, 23, 59, 59, 999999, tzinfo=UTC), FIVE),
        (dt.datetime(2026, 11, 1, tzinfo=UTC), TWELVE),
    ],
)
def test_meteorology_changes_the_expiry_at_the_end_of_the_period(
    monkeypatch: pytest.MonkeyPatch, now: dt.datetime, expected: CacheExpiry
) -> None:
    """The month of October 2026 ends 2026-11-01 00:00 UTC."""
    monkeypatch.setattr(fileindex, "_now", lambda: now)
    assert _meteorology(monkeypatch, "daily", "climate", ["2026_10_k.zip"], WINDOW) == {"2026_10_k.zip": expected}


def test_meteorology_changes_the_expiry_of_a_year_at_the_turn_of_the_year(monkeypatch: pytest.MonkeyPatch) -> None:
    """The year 2025 ends 2026-01-01 00:00 UTC, whichever way the file is named."""
    names = ["2025_k.zip", "2025_m_k.zip", "2025_010_s.zip"]
    for now, expected in [
        (dt.datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=UTC), FIVE),
        (dt.datetime(2026, 1, 1, tzinfo=UTC), TWELVE),
    ]:
        monkeypatch.setattr(fileindex, "_now", lambda now=now: now)
        assert _meteorology(monkeypatch, "daily", "climate", names[:1], WINDOW) == {names[0]: expected}
        assert _meteorology(monkeypatch, "monthly", "climate", names[1:2], WINDOW) == {names[1]: expected}
        assert _meteorology(monkeypatch, "daily", "synop", names[2:], WINDOW) == {names[2]: expected}


def test_the_archives_are_downloaded_with_their_own_expiry_and_come_back_in_their_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One download for each expiry, and the files are given back in the order of the archives."""
    calls: list[tuple[list[str], CacheExpiry]] = []

    def download_files(urls: list[str], ttl: CacheExpiry, **_: object) -> list[File]:
        calls.append((urls, ttl))
        return [File(url=url, content=FileNotFoundError(url), status=404) for url in urls]

    monkeypatch.setattr(fileindex, "download_files", download_files)
    archives = {"a": FIVE, "b": TWELVE, "c": FIVE, "d": TWELVE}

    files = download_archives(archives, Settings(cache_disable=True))

    assert [file.url for file in files] == ["a", "b", "c", "d"]
    assert sorted(calls, key=lambda call: call[0]) == [(["a", "c"], FIVE), (["b", "d"], TWELVE)]


def test_no_archive_is_one_download_of_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A listing without a file in the window is not an error here, it is what it always was."""
    calls: list[tuple[list[str], CacheExpiry]] = []
    monkeypatch.setattr(fileindex, "download_files", lambda urls, ttl, **_: calls.append((urls, ttl)) or [])
    assert download_archives({}, Settings(cache_disable=True)) == []
    assert calls == [([], FIVE)]
