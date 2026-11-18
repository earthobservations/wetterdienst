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

import pytest

from tests.nginx_stub import NginxLike, serving
from wetterdienst import Settings
from wetterdienst.provider.imgw.hydrology import ImgwHydrologyRequest
from wetterdienst.provider.imgw.hydrology.api import ImgwHydrologyMetadata, ImgwHydrologyValues
from wetterdienst.provider.imgw.meteorology.api import ImgwMeteorologyMetadata, ImgwMeteorologyValues
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    import polars as pl

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


def _request(tmp_path: Path, start: dt.datetime, end: dt.datetime, parameter: str = "stage") -> ImgwHydrologyRequest:
    return ImgwHydrologyRequest(
        parameters=[("daily", "hydrology", parameter)],
        start=start,
        end=end,
        settings=Settings(cache_dir=str(tmp_path / "cache")),
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
    """The hook of the meteorology values runs outside the station's collection: it skips and tells nothing."""
    server.directories[DIRECTORY] = ["2023/"]
    server.missing.add(f"{DIRECTORY}2023/")
    values = ImgwMeteorologyValues.__new__(ImgwMeteorologyValues)
    values.sr = type("SR", (), {"start": None, "end": None, "settings": Settings(cache_dir=str(tmp_path))})()  # ty: ignore[invalid-assignment]
    begin_response()

    archives = values._get_archives(ImgwMeteorologyMetadata.daily.synop, "249180100")  # noqa: SLF001

    assert archives == {}
    assert not recorded_warnings()
