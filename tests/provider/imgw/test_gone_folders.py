# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
# IMGW-PIB data (CC BY-NC-ND 4.0), which the MIT licence of this repository does not cover; see
# docs/data/provider/data-use.md. Its credit, § 5 ust. 3 and 4 of its terms:
#   „Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej –  # noqa: RUF003
#   Państwowy Instytut Badawczy"
#   „Dane Instytutu Meteorologii i Gospodarki Wodnej –  # noqa: RUF003
#   Państwowego Instytutu Badawczego zostały przetworzone"
"""A period folder or an archive of IMGW's server that is gone since its listing is told, not a 500 (GH-4205).

The walk of the values lists the dataset directory, then each period folder that overlaps the window, then downloads
the archives. IMGW consolidates its archives, so a folder the listing names may answer a 404 and a listed archive may
be gone at its download. The walk answers with what is left and says so in the answer's `warnings`: `file-skipped`
naming the station, which keeps `parameter-without-rows` ("the source has no values") from saying the opposite. The
server is `tests/nginx_stub.py`, and the walk is the library's own (`begin_response()`, `recorded_warnings()`).
"""

from __future__ import annotations

import datetime as dt
import io
import zipfile
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from tests.nginx_stub import NginxLike, serving
from tests.provider.value_stubs import stations_result
from wetterdienst import Settings
from wetterdienst.provider.imgw.fileindex import list_files_for_interval
from wetterdienst.provider.imgw.hydrology import ImgwHydrologyRequest
from wetterdienst.provider.imgw.hydrology.api import ImgwHydrologyMetadata, ImgwHydrologyValues
from wetterdienst.provider.imgw.meteorology import ImgwMeteorologyRequest
from wetterdienst.provider.imgw.meteorology.api import ImgwMeteorologyMetadata, ImgwMeteorologyValues
from wetterdienst.util.response_warnings import SkipCause, begin_response, collecting, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


UTC = dt.UTC
STATION = "149180010"
POINT = (49.99, 18.29)
_CATALOGUE = (
    "LP.;Kod 9-znakowy;Nazwa stacji;Rzeka;Rok założenia;Szerokość geograficzna;Długość geograficzna;"
    "Rzędna zera wodowskazu;Kilometr biegu rzeki\r\n"
    "1;149180010;Krzyżanowice;Odra (1);1927;49 59 37;18 17 14;184.806;713.04\r\n"
)
_DAILY = ImgwHydrologyMetadata.daily.hydrology
DIRECTORY = f"/{_DAILY.resolution.name_original}/"


def _zip(member: str, csv: str) -> bytes:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(member, csv.encode("latin-1"))
    return archive.getvalue()


def _archive(server: NginxLike, folder: str, name: str, row: str) -> None:
    """Serve the archive `name` in the period `folder`, which lists it, with the daily `row` of the station."""
    server.directories.setdefault(f"{DIRECTORY}{folder}/", []).append(name)
    server.contents[f"{DIRECTORY}{folder}/{name}"] = _zip(name.replace(".zip", ".csv"), row)


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Iterator[NginxLike]:
    """Serve the catalogue and the daily directory with the folders of 2022 and 2023, each with one archive."""
    with serving() as state:
        monkeypatch.setattr(ImgwHydrologyValues, "_endpoint", f"{state.base}/{{resolution}}/")
        monkeypatch.setattr(ImgwHydrologyRequest, "_endpoint", f"{state.base}/kody_stacji.csv")
        monkeypatch.setattr(ImgwMeteorologyValues, "_endpoint", f"{state.base}/{{resolution}}/")
        state.contents["/kody_stacji.csv"] = _CATALOGUE.encode("utf8")
        state.directories[DIRECTORY] = ["2022/", "2023/"]
        _archive(state, "2022", "codz_2022_12.zip", f"{STATION},KRZYZANOWICE,Odra,2022,12,15,141,12.5,9.9\n")
        _archive(state, "2023", "codz_2023_03.zip", f"{STATION},KRZYZANOWICE,Odra,2023,03,15,142,12.6,9.8\n")
        yield state


def _request(
    tmp_path: Path, start: dt.datetime, end: dt.datetime, parameter: str = "stage", cache: str = "cache"
) -> ImgwHydrologyRequest:
    return ImgwHydrologyRequest(
        parameters=[("daily", "hydrology", parameter)],
        start=start,
        end=end,
        settings=Settings(cache_dir=str(tmp_path / cache)),
    )


def _values(request: ImgwHydrologyRequest) -> pl.DataFrame:
    begin_response()
    return request.filter_by_station_id(STATION).values().all().df


def _told() -> dict[str, list[dict[str, Any]]]:
    told: dict[str, list[dict[str, Any]]] = {}
    for warning in recorded_warnings():
        told.setdefault(warning["code"], []).append(warning)
    return told


_BOTH_YEARS = (dt.datetime(2022, 10, 1, tzinfo=UTC), dt.datetime(2023, 1, 31, tzinfo=UTC))
_THIS_YEAR = (dt.datetime(2023, 1, 1, tzinfo=UTC), dt.datetime(2023, 1, 31, tzinfo=UTC))


def test_the_control_both_folders_are_read(server: NginxLike, tmp_path: Path) -> None:  # noqa: ARG001
    """With every folder there, both readings are in the answer and nothing is told."""
    df = _values(_request(tmp_path, *_BOTH_YEARS))

    assert sorted(df["value"].to_list()) == [1.41, 1.42]
    assert not _told()


def test_a_period_folder_that_is_gone_is_a_partial_answer_that_names_the_station(
    server: NginxLike, tmp_path: Path
) -> None:
    """The folder of 2023 answers a 404: the reading of 2022 is the answer, `file-skipped` names the station."""
    server.missing.add(f"{DIRECTORY}2023/")

    df = _values(_request(tmp_path, *_BOTH_YEARS))

    assert df["value"].to_list() == [1.41]
    told = _told()
    (skipped,) = told["file-skipped"]
    assert skipped["stations"] == [STATION]
    assert "the directory was found empty" in skipped["message"]
    # the answer does not also say the source has no values
    assert "parameter-without-rows" not in told


def test_a_window_whose_only_folder_is_gone_is_told_and_no_500(server: NginxLike, tmp_path: Path) -> None:
    """No file is left to read: the empty answer, which names the skip, not a polars `SchemaError`."""
    server.directories[DIRECTORY] = ["2023/"]
    server.missing.add(f"{DIRECTORY}2023/")

    df = _values(_request(tmp_path, *_THIS_YEAR))

    assert df.is_empty()
    told = _told()
    (skipped,) = told["file-skipped"]
    assert skipped["stations"] == [STATION]
    assert "parameter-without-rows" not in told


def test_an_empty_period_folder_is_no_500(server: NginxLike, tmp_path: Path) -> None:
    """A folder with no file reads as no file, as it did not for a window that held only it (a `SchemaError`)."""
    server.directories[DIRECTORY] = ["2023/"]
    server.directories[f"{DIRECTORY}2023/"] = []

    df = _values(_request(tmp_path, *_THIS_YEAR))

    assert df.is_empty()
    assert "file-skipped" not in _told()


def test_a_window_that_overlaps_no_folder_is_no_500(server: NginxLike, tmp_path: Path) -> None:  # noqa: ARG001
    """The folders are of 2022 and 2023 and the window is of 2010: no folder is read, no file, no 500."""
    df = _values(_request(tmp_path, dt.datetime(2010, 1, 1, tzinfo=UTC), dt.datetime(2010, 1, 31, tzinfo=UTC)))

    assert df.is_empty()


def test_an_archive_that_is_gone_at_its_download_is_told(server: NginxLike, tmp_path: Path) -> None:
    """The listing names the archive of 2023 and the server has none: 404, dropped, and told with the station."""
    del server.contents[f"{DIRECTORY}2023/codz_2023_03.zip"]

    df = _values(_request(tmp_path, *_BOTH_YEARS))

    assert df["value"].to_list() == [1.41]
    told = _told()
    (skipped,) = told["file-skipped"]
    assert skipped["stations"] == [STATION]
    assert "the file was gone" in skipped["message"]
    assert "parameter-without-rows" not in told


def test_a_summary_tells_a_folder_that_is_gone_once_as_source_data_left_out(server: NginxLike, tmp_path: Path) -> None:
    """`summarize` folds the station's skip into `source-data-left-out`; the per-station `file-skipped` stays off."""
    server.missing.add(f"{DIRECTORY}2023/")
    request = _request(tmp_path, *_BOTH_YEARS, parameter="stage")
    begin_response()

    request.summarize(POINT)

    told = _told()
    (summary,) = told["source-data-left-out"]
    assert summary["stations"] == [STATION]
    assert "the directory was found empty" in summary["message"]
    assert "file-skipped" not in told
    assert "parameter-without-rows" not in told


def test_the_fetch_ahead_lists_a_gone_folder_without_a_word(server: NginxLike, tmp_path: Path) -> None:
    """The hook of the meteorology values runs outside the station's collection: it skips and tells the walk nothing."""
    server.directories[DIRECTORY] = ["2023/"]
    server.missing.add(f"{DIRECTORY}2023/")
    values = ImgwMeteorologyValues.__new__(ImgwMeteorologyValues)
    values.sr = type("SR", (), {"start": None, "end": None, "settings": Settings(cache_dir=str(tmp_path))})()  # ty: ignore[invalid-assignment]
    begin_response()
    told_to_the_walk: list[SkipCause] = []

    # the hook is called as the walk calls it, with a station's collection set up to be told what is let go
    with collecting(lambda _whole_request, cause: told_to_the_walk.append(cause)):
        ahead = values._files_ahead("249180100", [ImgwMeteorologyMetadata.daily.synop])  # noqa: SLF001

    assert ahead.urls == []
    assert told_to_the_walk == []
    assert not recorded_warnings()


def _requests_for(server: NginxLike, directory: str) -> int:
    """Count the requests the server met for a directory, with or without its `/`."""
    return sum(1 for _, path in server.requests if path.split("?")[0].rstrip("/") == directory.rstrip("/"))


def test_a_folder_that_stays_gone_has_the_parent_read_again_once_not_for_every_station(
    server: NginxLike, tmp_path: Path
) -> None:
    """The first station drops the cached listing of the parent and reads it again; the others take that listing."""
    catalogue = _CATALOGUE + "".join(
        f"{n};14918001{n};Station {n};Odra (1);1927;49 59 37;18 17 14;184.806;713.04\r\n" for n in range(1, 5)
    )
    server.contents["/kody_stacji.csv"] = catalogue.encode("utf8")
    server.missing.add(f"{DIRECTORY}2023/")

    def requests_for_parent(cache: str, stations: list[str]) -> int:
        server.requests.clear()
        begin_response()
        _request(tmp_path, *_BOTH_YEARS, cache=cache).filter_by_station_id(stations).values().all()
        return _requests_for(server, DIRECTORY)

    one = requests_for_parent("one", [STATION])
    five = requests_for_parent("five", [STATION, *(f"14918001{n}" for n in range(1, 5))])

    assert one >= 2  # the listing, and the listing read again
    assert five == one


def test_an_archive_that_was_consolidated_is_followed_by_the_next_request(server: NginxLike, tmp_path: Path) -> None:
    """The cached listings name an archive IMGW has moved: it is told gone once, the next request follows the move."""
    # an earlier request listed the parent and the folders, which the cache keeps (the archives were not read)
    settings = Settings(cache_dir=str(tmp_path / "cache"))
    assert len(list_files_for_interval(f"{server.base}{DIRECTORY}", settings, None)) == 2
    # IMGW consolidates 2023/ into 2021_2023/, while the listings of the parent and of 2023/ are still cached
    server.missing.add(f"{DIRECTORY}2023/")
    del server.contents[f"{DIRECTORY}2023/codz_2023_03.zip"]
    server.directories[DIRECTORY] = ["2022/", "2021_2023/"]
    _archive(server, "2021_2023", "codz_2023_03.zip", f"{STATION},KRZYZANOWICE,Odra,2023,03,15,142,12.6,9.8\n")

    df = _values(_request(tmp_path, *_BOTH_YEARS))

    assert df["value"].to_list() == [1.41]
    assert "the file was gone" in _told()["file-skipped"][0]["message"]
    df = _values(_request(tmp_path, *_BOTH_YEARS))
    assert sorted(df["value"].to_list()) == [1.41, 1.42]
    assert not _told()


# --- the meteorology values: the same walk, through the monthly climate files ---------------------------------------

_MONTHLY = ImgwMeteorologyMetadata.monthly.climate
_MONTHLY_DIRECTORY = f"/{_MONTHLY.resolution.name_original}/"
_MONTHLY_STATION = "249180010"


def _k_m_d_line() -> str:
    """Give the row of `k_m_d` for January 2010: every pair a value and its status, the day counts carry none."""
    fields = ["0"] * 27
    fields[0] = _MONTHLY_STATION
    fields[1] = "PSZCZYNA"
    fields[2] = "2010"
    fields[3] = "1"
    for position, value in zip((4, 6, 8, 10, 12, 14), ("14.2", "3.1", "-12.4", "-5.0", "-1.2", "-15.0"), strict=True):
        fields[position] = value
        fields[position + 1] = ""
    fields[16] = "31.4"
    fields[17] = ""
    fields[18] = "6.1"
    fields[19] = ""
    fields[22] = "21"
    fields[23] = ""
    return ",".join(fields)


@pytest.fixture
def monthly(server: NginxLike) -> NginxLike:
    """Serve the monthly climate directory with the folder of 2010 and its one archive."""
    server.directories[_MONTHLY_DIRECTORY] = ["2010/"]
    server.directories[f"{_MONTHLY_DIRECTORY}2010/"] = ["2010_m_k.zip"]
    server.contents[f"{_MONTHLY_DIRECTORY}2010/2010_m_k.zip"] = _zip("k_m_d_2010.csv", _k_m_d_line())
    return server


def _monthly_values(tmp_path: Path) -> pl.DataFrame:
    request = ImgwMeteorologyRequest(
        parameters=[("monthly", "climate")],
        start=dt.datetime(2010, 1, 1, tzinfo=UTC),
        end=dt.datetime(2010, 3, 1, tzinfo=UTC),
        settings=Settings(cache_dir=str(tmp_path / "cache")),
    )
    begin_response()
    return stations_result(request, "monthly", "climate", _MONTHLY_STATION).values().all().df


def test_the_control_the_monthly_climate_file_is_read(monthly: NginxLike, tmp_path: Path) -> None:  # noqa: ARG001
    """With the folder there, the rain of January is in the answer and nothing is told."""
    df = _monthly_values(tmp_path)

    assert df.filter(pl.col("parameter").eq("precipitation_amount"))["value"].to_list() == [31.4]
    assert not _told()


def test_meteorology_a_period_folder_that_is_gone_is_told_with_the_station(monthly: NginxLike, tmp_path: Path) -> None:
    """The only folder of the window answers a 404: an empty answer that names the skip, no 500."""
    monthly.missing.add(f"{_MONTHLY_DIRECTORY}2010/")

    df = _monthly_values(tmp_path)

    assert df.is_empty()
    told = _told()
    (skipped,) = told["file-skipped"]
    assert skipped["stations"] == [_MONTHLY_STATION]
    assert "the directory was found empty" in skipped["message"]
    assert "parameter-without-rows" not in told


def test_meteorology_an_archive_that_is_gone_at_its_download_is_told(monthly: NginxLike, tmp_path: Path) -> None:
    """The listing names the archive and the server has none: dropped, and told with the station."""
    del monthly.contents[f"{_MONTHLY_DIRECTORY}2010/2010_m_k.zip"]

    df = _monthly_values(tmp_path)

    assert df.is_empty()
    told = _told()
    (skipped,) = told["file-skipped"]
    assert skipped["stations"] == [_MONTHLY_STATION]
    assert "the file was gone" in skipped["message"]
    assert "parameter-without-rows" not in told
