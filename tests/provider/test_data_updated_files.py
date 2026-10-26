# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`data_updated_at` of the networks that date a file: when the source last wrote what the answer was read from.

The date is the `Last-Modified` the download kept (`File.last_modified`), the newest of the files that gave the station
readings; for a forecast it is the model run. A file that failed, or that gave no reading, adds none (GH-2567).
"""

from __future__ import annotations

import bz2
import datetime as dt
import gzip
import logging
import zipfile
from io import BytesIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.provider.dwd.mosmix.test_api_data import _stub_mosmix_stations
from tests.provider.value_stubs import stations_result
from wetterdienst import Options, Settings
from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.observation import api as dwd_observation_api
from wetterdienst.provider.dwd.observation import download as dwd_observation_download
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest, DwdObservationValues
from wetterdienst.provider.dwd.observation.download import (
    _unpack_climate_observations_data,
    download_climate_observations_data,
)
from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest
from wetterdienst.provider.dwd.swsmos import api as swsmos_api
from wetterdienst.provider.ipma.observation import IpmaObservationRequest
from wetterdienst.provider.ipma.observation import api as ipma_api
from wetterdienst.provider.meteofrance.synop import MeteoFranceSynopRequest
from wetterdienst.provider.meteofrance.synop import api as synop_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from datetime import datetime

UTC = ZoneInfo("UTC")

OLD = dt.datetime(2026, 10, 20, 9, 0, 7, tzinfo=UTC)
NEW = dt.datetime(2026, 10, 25, 6, 30, 0, tzinfo=UTC)
NEWER = dt.datetime(2026, 10, 26, 6, 0, 0, tzinfo=UTC)

# the two files of the seam of the year 2000 of one station, as DWD writes them
_BEFORE = (
    "STATIONS_ID;MESS_DATUM;QN;PP_10;TT_10;TM5_10;RF_10;TD_10\n"
    "       1048;199912312330;    1;  996.2;  -0.6;  -2.3;  92.0;  -1.8\n"
    "       1048;199912312340;    1;  996.3;  -0.6;  -2.2;  92.0;  -1.8\n"
)
_AFTER = (
    "STATIONS_ID;MESS_DATUM;  QN;PP_10;TT_10;TM5_10;RF_10;TD_10;eor\n"
    "       1048;200001010000;    1;  996.4;  -1.0;  -1.4;  94.0;  -1.7;eor\n"
)


def _dwd_10_minute_values(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    files: dict[str, tuple[str, datetime | None]],
) -> object:
    """Read the values of station 01048 from the product files served, each with the date DWD wrote it."""
    monkeypatch.setattr(DwdObservationValues, "_get_historical_date_ranges", lambda *_, **__: None)
    monkeypatch.setattr(
        dwd_observation_api,
        "create_file_list_for_climate_observations",
        lambda *_, **__: pl.Series([f"https://example.invalid/{name}" for name in files]),
    )
    monkeypatch.setattr(
        dwd_observation_api,
        "download_climate_observations_data",
        lambda *_, **__: [
            File(
                url=f"https://example.invalid/{name}",
                content=BytesIO(product.encode("latin-1")),
                status=200,
                last_modified=written,
            )
            for name, (product, written) in files.items()
        ],
    )
    request = DwdObservationRequest(
        parameters=[("10_minutes", "air_temperature", "temperature_air_2m")],
        periods={Period.HISTORICAL},
        start=dt.datetime(1999, 12, 31, 20, tzinfo=UTC),
        end=dt.datetime(2000, 1, 1, 2, tzinfo=UTC),
        settings=settings,
        options=Options(drop_nulls=False),
    )
    return stations_result(request, "10_minutes", "air_temperature", "01048").values().all()


def test_dwd_observation_is_dated_by_the_newest_of_the_files_it_read(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Two archives, written on two days: the answer says the later, in whichever order they were read."""
    for files in (
        {"before.zip": (_BEFORE, OLD), "after.zip": (_AFTER, NEW)},
        {"after.zip": (_AFTER, NEW), "before.zip": (_BEFORE, OLD)},
    ):
        result = _dwd_10_minute_values(monkeypatch, default_settings, files)

        assert not result.df.is_empty()
        assert result.data_updated_at == NEW


def test_dwd_observation_a_file_without_a_date_adds_none_and_none_at_all_is_null(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """The date of the file that has one is the answer's; no file with one is no date, never a made-up one."""
    one = _dwd_10_minute_values(
        monkeypatch, default_settings, {"before.zip": (_BEFORE, None), "after.zip": (_AFTER, OLD)}
    )
    none = _dwd_10_minute_values(
        monkeypatch, default_settings, {"before.zip": (_BEFORE, None), "after.zip": (_AFTER, None)}
    )

    assert one.data_updated_at == OLD
    assert none.data_updated_at is None
    assert not none.df.is_empty()


def _archive(content: str, written: datetime | None, name: str = "a.zip") -> File:
    """Give an archive of one product file, as a download of it that DWD wrote on the given day."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("produkt_zehn_min_tu_19911119_19991231_01048.txt", content)
    return File(
        url=f"https://example.invalid/{name}", content=BytesIO(buffer.getvalue()), status=200, last_modified=written
    )


def test_dwd_observation_a_file_that_is_not_there_is_not_counted(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """A 404 is dropped before the readings are made, so the date of what is left is the answer's."""
    missing = File(url="https://example.invalid/missing.zip", content=FileNotFoundError("404"), status=404)
    monkeypatch.setattr(
        dwd_observation_download,
        "download_files",
        lambda **_kwargs: [_archive(_BEFORE, OLD), missing],
    )

    files = download_climate_observations_data(pl.Series(["unused", "unused"]), default_settings)

    assert [file.last_modified for file in files] == [OLD]


def test_dwd_observation_unpacking_an_archive_keeps_its_date() -> None:
    """The product file taken out of the archive has the date of the archive, which the answer is dated by."""
    unpacked = _unpack_climate_observations_data(_archive(_BEFORE, OLD))

    assert unpacked.last_modified == OLD


def test_swsmos_is_dated_by_its_run_and_not_by_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A forecast is dated by the run it is of, which its file name states, whenever the file was written."""
    body = "".join(f"A006;54.889156;8.908735;20261026{hour:02d}00;1{hour}.0\n" for hour in (8, 9))
    content = bz2.compress(b"ID;Lat;Lon;YYYYMMDDHHmm;TL\n202610260700\n" + body.encode("latin-1"))
    name = "swsmos_20261026070000_opendata.csv.bz2"
    monkeypatch.setattr(swsmos_api, "list_remote_files_fsspec", lambda *_a, **_k: [f"{swsmos_api._BASE_URL}/{name}"])  # noqa: SLF001
    monkeypatch.setattr(
        swsmos_api,
        "download_file",
        # written two days after the run it holds
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(content), status=200, last_modified=NEWER),
    )
    request = DwdSwsmosRequest(
        parameters=[("hourly", "data", "temperature_air")], settings=Settings(cache_disable=True)
    )

    result = stations_result(request, "hourly", "data", "A006").values().all()

    assert not result.df.is_empty()
    assert result.data_updated_at == dt.datetime(2026, 10, 26, 7, tzinfo=UTC)


def test_mosmix_is_dated_by_the_run_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A MOSMIX forecast says when its run was issued, the `IssueTime` of the file that was read."""
    values = _stub_mosmix_stations().values()
    monkeypatch.setattr(values, "get_url_for_date", lambda *_a, **_k: "https://example.invalid/MOSMIX_L_2026102606.kmz")
    monkeypatch.setattr(values.kml, "read", lambda _url: None)
    values.kml.metadata = {"issue_time": dt.datetime(2026, 10, 26, 6, tzinfo=UTC)}
    monkeypatch.setattr(
        values.kml,
        "get_station_forecast",
        lambda _station: pl.DataFrame({"timestamp": ["2026-10-26T07:00:00.000Z"], "ttt": [280.1]}),
    )

    result = values.all()

    assert not result.df.is_empty()
    assert result.data_updated_at == dt.datetime(2026, 10, 26, 6, tzinfo=UTC)


_IPMA_STATIONS = (
    b'[{"geometry": {"type": "Point", "coordinates": [-9.1, 38.7]}, "type": "Feature", '
    b'"properties": {"idEstacao": 1200579, "localEstacao": "Lisboa"}}]'
)
_IPMA_FEED = b'{"2026-10-10T12:00": {"1200579": {"temperatura": 20.0}}}'


def _ipma_values(monkeypatch: pytest.MonkeyPatch, *, feed_written: datetime | None) -> object:
    """Read a station of the feed, whose file and whose catalogue were written on different days."""

    def download_file(url: str, **_: object) -> File:
        if url.endswith("observations.json"):
            return File(url=url, content=BytesIO(_IPMA_FEED), status=200, last_modified=feed_written)
        return File(url=url, content=BytesIO(_IPMA_STATIONS), status=200, last_modified=NEWER)

    monkeypatch.setattr(ipma_api, "download_file", download_file)
    return (
        IpmaObservationRequest(
            parameters=[("hourly", "data")],
            start=dt.datetime(2026, 10, 10, 11, tzinfo=UTC),
            end=dt.datetime(2026, 10, 10, 14, tzinfo=UTC),
            settings=Settings(cache_disable=True),
        )
        .filter_by_station_id("1200579")
        .values()
        .all()
    )


def test_ipma_is_dated_by_the_feed_and_not_by_the_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    """The station list is written on another day than the feed, and the readings are the feed's."""
    result = _ipma_values(monkeypatch, feed_written=OLD)

    assert not result.df.is_empty()
    assert result.data_updated_at == OLD


def test_ipma_without_a_date_for_the_feed_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """A feed that states no date is dated by nothing, whatever the catalogue says."""
    assert _ipma_values(monkeypatch, feed_written=None).data_updated_at is None


def _synop_file(*rows: tuple[str, str]) -> bytes:
    """Write the file of a year: a row of the given station and time each, in the columns of the source."""
    schema = list(synop_api._SYNOP_CSV_SCHEMA)  # noqa: SLF001
    lines = [";".join(schema)]
    lines += [
        ";".join({"geo_id_wmo": station, "validity_time": stamp, "t": "280.0"}.get(column, "") for column in schema)
        for station, stamp in rows
    ]
    return gzip.compress("\n".join(lines).encode("utf8"))


def _synop_values(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the year files of a station, written on three days, the newest of them holding another station only."""
    files = {
        "synop_2023": (_synop_file(("07005", "2023-12-31T18:00:00Z")), OLD),
        "synop_2024": (_synop_file(("07005", "2024-01-01T18:00:00Z")), NEW),
        # another station only, written last of all
        "synop_2025": (_synop_file(("07015", "2025-01-01T18:00:00Z")), NEWER),
    }

    def download_file(*, url: str, **_: object) -> File:
        content, written = next(entry for part, entry in files.items() if part in url)
        return File(url=url, content=BytesIO(content), status=200, last_modified=written)

    monkeypatch.setattr(synop_api, "download_file", download_file)
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", "temperature_air_2m")],
        start=dt.datetime(2023, 12, 31, tzinfo=UTC),
        end=dt.datetime(2025, 1, 2, tzinfo=UTC),
        settings=Settings(cache_disable=True),
    )
    return stations_result(request, "subdaily", "data", "07005").values().all()


def test_meteofrance_synop_is_dated_by_the_newest_of_the_year_files_that_gave_readings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Licence Ouverte asks for the date of the update: the newest of the files read that held the station."""
    result = _synop_values(monkeypatch)

    assert not result.df.is_empty()
    assert result.data_updated_at == NEW


def _dwd_periods(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    files: dict[Period, tuple[str, datetime]],
    window: tuple[datetime, datetime],
) -> object:
    """Read station 01048 from an archive of each period, served as DWD writes them, for a window."""
    monkeypatch.setattr(DwdObservationValues, "_get_historical_date_ranges", lambda *_, **__: None)
    monkeypatch.setattr(
        dwd_observation_api,
        "create_file_list_for_climate_observations",
        lambda _station, _dataset, period, *_, **__: pl.Series([f"https://example.invalid/{period.value}.zip"]),
    )
    monkeypatch.setattr(
        dwd_observation_api,
        "download_climate_observations_data",
        lambda remote_files, *_, **__: [
            File(
                url=url,
                content=BytesIO(files[Period(url.rsplit("/", 1)[-1].removesuffix(".zip"))][0].encode("latin-1")),
                status=200,
                last_modified=files[Period(url.rsplit("/", 1)[-1].removesuffix(".zip"))][1],
            )
            for url in remote_files.to_list()
        ],
    )
    request = DwdObservationRequest(
        parameters=[("10_minutes", "air_temperature", "temperature_air_2m")],
        periods=set(files),
        start=window[0],
        end=window[1],
        settings=settings,
        options=Options(drop_nulls=False),
    )
    return stations_result(request, "10_minutes", "air_temperature", "01048").values().all()


def test_dwd_observation_a_period_whose_rows_the_other_settled_does_not_date_the_answer(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """The historical row is the answer's where both archives hold a stamp, and so is its date.

    The recent archive was read but gave the answer no row.
    """
    window = (dt.datetime(1999, 12, 31, 20, tzinfo=UTC), dt.datetime(2000, 1, 1, 2, tzinfo=UTC))

    result = _dwd_periods(
        monkeypatch, default_settings, {Period.HISTORICAL: (_AFTER, OLD), Period.RECENT: (_AFTER, NEWER)}, window
    )

    assert not result.df.is_empty()
    assert result.data_updated_at == OLD


def test_dwd_observation_a_period_whose_rows_are_outside_the_window_does_not_date_the_answer(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """An archive is read because its period is selected: one whose rows all lie before the window adds no date."""
    window = (dt.datetime(2000, 1, 1, tzinfo=UTC), dt.datetime(2000, 1, 1, 2, tzinfo=UTC))

    result = _dwd_periods(
        monkeypatch, default_settings, {Period.HISTORICAL: (_BEFORE, NEWER), Period.RECENT: (_AFTER, OLD)}, window
    )

    assert not result.df.is_empty()
    assert result.data_updated_at == OLD


def _derived_periods(
    monkeypatch: pytest.MonkeyPatch,
    files: dict[Period, tuple[str, datetime]],
) -> object:
    """Read the daily soil of station 01001 for 1 and 2 January from a file of each period, written on given days."""
    from tests.provider.value_stubs import _day  # noqa: PLC0415
    from wetterdienst.provider.dwd.derived import DwdDerivedRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.derived import api as derived_api  # noqa: PLC0415

    monkeypatch.setattr(
        derived_api,
        "create_file_list_for_climate_derived",
        lambda _station, _dataset, period, *_, **__: pl.Series([f"https://example.invalid/{period.value}.txt"]),
    )
    monkeypatch.setattr(
        derived_api,
        "download_climate_derived_data",
        lambda remote_files, *_, **__: [
            File(
                url=url,
                content=BytesIO(files[Period(url.rsplit("/", 1)[-1].removesuffix(".txt"))][0].encode("latin-1")),
                status=200,
                last_modified=files[Period(url.rsplit("/", 1)[-1].removesuffix(".txt"))][1],
            )
            for url in remote_files.to_list()
        ],
    )
    request = DwdDerivedRequest(
        parameters=[("daily", "soil", "temperature_soil_mean_0_05m")],
        periods=set(files),
        start=_day(2026, 1, 1),
        end=_day(2026, 1, 2),
        settings=Settings(cache_disable=True),
    )
    return stations_result(request, "daily", "soil", "01001").values().all()


_SOIL_JANUARY = "Stationsindex;Datum;TS05;eor\n         1001;20260101;    0.0;eor\n         1001;20260102;    0.1;eor\n"
_SOIL_MARCH = "Stationsindex;Datum;TS05;eor\n         1001;20260301;    4.0;eor\n"


def test_dwd_derived_a_period_with_no_row_in_the_answer_does_not_date_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """The newer file of the recent period holds a March day, and the request is for January: it adds no date."""
    result = _derived_periods(
        monkeypatch, {Period.HISTORICAL: (_SOIL_JANUARY, OLD), Period.RECENT: (_SOIL_MARCH, NEWER)}
    )

    assert not result.df.is_empty()
    assert result.data_updated_at == OLD


def test_dwd_derived_the_period_that_has_the_rows_dates_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the January rows in the newer file the answer has its date, and the older file's is not the answer's."""
    result = _derived_periods(
        monkeypatch, {Period.HISTORICAL: (_SOIL_MARCH, OLD), Period.RECENT: (_SOIL_JANUARY, NEWER)}
    )

    assert result.data_updated_at == NEWER


def _synop_year_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    held: bool,
    once_more: File | None = None,
) -> list[tuple[str, int, bool]]:
    """Stand in for the downloads of the years and the cache, and give the calls made: file, attempts, undated."""
    calls: list[tuple[str, int, bool]] = []
    year = dt.datetime.now(UTC).year - 1

    def download_file(*, url: str, attempts: int = 2, refetch_undated: bool = False, **_: object) -> File:
        calls.append((url.rsplit("/", 1)[-1], attempts, refetch_undated))
        if refetch_undated and once_more is not None:
            return once_more
        content = BytesIO(_synop_file(("07005", f"{url[-11:-7]}-01-01T18:00:00Z")))
        return File(url=url, content=content, status=200, last_modified=OLD if not refetch_undated else NEW)

    monkeypatch.setattr(synop_api, "download_file", download_file)
    monkeypatch.setattr(synop_api, "cached_copy_is_held", lambda *_a, **_k: held)
    assert year > 1996
    return calls


def _synop_values_of_the_year_before(*, current: bool = False) -> object:
    year = dt.datetime.now(UTC).year - (0 if current else 1)
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", "temperature_air_2m")],
        start=dt.datetime(year, 1, 1, tzinfo=UTC),
        end=dt.datetime(year, 1, 2, tzinfo=UTC),
        settings=Settings(cache_disable=True),
    )
    return stations_result(request, "subdaily", "data", "07005").values().all()


def test_meteofrance_synop_a_finished_year_held_is_fetched_once_more_in_one_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A copy held may have been made before dates were kept: the one more fetch dates it, and asks once."""
    year = dt.datetime.now(UTC).year - 1
    calls = _synop_year_stub(monkeypatch, held=True)

    result = _synop_values_of_the_year_before()

    assert calls == [(f"synop_{year}.csv.gz", 1, True)]
    assert result.data_updated_at == NEW


def test_meteofrance_synop_the_current_year_and_a_year_not_held_are_downloaded_as_any(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """There is nothing to fetch once more where no copy is held, and the current year is held for 5 minutes only."""
    year = dt.datetime.now(UTC).year
    calls = _synop_year_stub(monkeypatch, held=True)
    _synop_values_of_the_year_before(current=True)
    assert calls == [(f"synop_{year}.csv.gz", 2, False)]

    calls = _synop_year_stub(monkeypatch, held=False)
    _synop_values_of_the_year_before()
    assert calls == [(f"synop_{year - 1}.csv.gz", 2, False)]


@pytest.mark.parametrize("status", [404, 503])
def test_meteofrance_synop_a_year_held_that_cannot_be_fetched_again_is_read_undated_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, status: int
) -> None:
    """Whatever the one more fetch is answered, a 404 too, the held copy is read, with no date and a warning."""
    year = dt.datetime.now(UTC).year - 1
    failed = File(url="https://example.invalid/x", content=ConnectionError("down"), status=status)
    calls = _synop_year_stub(monkeypatch, held=True, once_more=failed)
    original = synop_api.download_file

    def download_file(**kwargs: object) -> File:
        file = original(**kwargs)
        # the held copy, read from the cache with no date
        if not kwargs.get("refetch_undated") and not isinstance(file.content, Exception):
            file.last_modified = None
        return file

    monkeypatch.setattr(synop_api, "download_file", download_file)

    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.meteofrance.synop.api"):
        result = _synop_values_of_the_year_before()

    assert not result.df.is_empty()
    assert result.data_updated_at is None
    assert calls == [(f"synop_{year}.csv.gz", 1, True), (f"synop_{year}.csv.gz", 2, False)]
    assert "the copy held is read, with no date" in caplog.text


def test_meteofrance_synop_a_year_not_held_that_cannot_be_downloaded_is_asked_for_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no copy held a 503 is not asked for a second time through the one more fetch: the error is the answer."""
    year = dt.datetime.now(UTC).year - 1
    calls: list[int] = []

    def download_file(*, url: str, attempts: int = 2, **_: object) -> File:
        calls.append(attempts)
        return File(url=url, content=ConnectionError("down"), status=503)

    monkeypatch.setattr(synop_api, "download_file", download_file)
    monkeypatch.setattr(synop_api, "cached_copy_is_held", lambda *_a, **_k: False)

    with pytest.raises(DownloadError):
        _synop_values_of_the_year_before()

    assert calls == [2]
    assert year


# --- one offline read of every network that dates what it reads: the registry of `tests/ui` runs them ---------


def _dated(monkeypatch: pytest.MonkeyPatch, module: object, name: str, written: datetime | None = NEW) -> None:
    """Make the files a stubbed download of a provider returns the ones the source wrote on a day."""
    original = getattr(module, name)

    def download(*args: object, **kwargs: object) -> object:
        answer = original(*args, **kwargs)
        for file in answer if isinstance(answer, list) else [answer]:
            file.last_modified = written
        return answer

    monkeypatch.setattr(module, name, download)


def _read_dwd_observation(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read two archives that DWD wrote on two days."""
    files = {"before.zip": (_BEFORE, OLD), "after.zip": (_AFTER, NEW)}
    return _dwd_10_minute_values(monkeypatch, Settings(cache_disable=True), files)


def _read_dwd_derived(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the daily soil file of a station."""
    from tests.provider.dwd.derived.test_derived_frames import _serve_product  # noqa: PLC0415
    from tests.provider.value_stubs import _day  # noqa: PLC0415
    from wetterdienst.provider.dwd.derived import DwdDerivedRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.derived import api as derived_api  # noqa: PLC0415

    _serve_product(
        monkeypatch,
        "Stationsindex;Datum;TS05;eor\n         1001;20260101;    0.0;eor\n         1001;20260102;    0.1;eor\n",
    )
    _dated(monkeypatch, derived_api, "download_climate_derived_data")
    request = DwdDerivedRequest(
        parameters=[("daily", "soil", "temperature_soil_mean_0_05m")],
        periods={Period.RECENT},
        start=_day(2026, 1, 1),
        end=_day(2026, 1, 2),
        settings=Settings(cache_disable=True),
    )
    return stations_result(request, "daily", "soil", "01001").values().all()


def _read_dwd_phenology(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the historical release and the recent file of a plant, written on two days."""
    from tests.provider.dwd.phenology.test_values_frame import _HISTORICAL, _RECENT, _URL  # noqa: PLC0415
    from wetterdienst.provider.dwd.phenology import DwdPhenologyRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.phenology import api as phenology_api  # noqa: PLC0415

    historical = f"{_URL}/historical/PH_Jahresmelder_Wildwachsende_Pflanze_Hasel_1979_2024_hist.txt"
    recent = f"{_URL}/recent/PH_Jahresmelder_Wildwachsende_Pflanze_Hasel_akt.txt"
    files = {historical: (_HISTORICAL, OLD), recent: (_RECENT, NEW)}
    monkeypatch.setattr(
        phenology_api,
        "download_file",
        lambda *, url, **_: File(url=url, content=BytesIO(files[url][0]), status=200, last_modified=files[url][1]),
    )
    monkeypatch.setattr(phenology_api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [historical])
    request = DwdPhenologyRequest(parameters=[("annual", "annual_common_hazel")], settings=Settings(cache_disable=True))
    return stations_result(request, "annual", "annual_common_hazel", "07521").values().all()


def _read_dwd_poi(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the report file of a station."""
    from tests.provider.value_stubs import serve  # noqa: PLC0415
    from wetterdienst.provider.dwd.poi import DwdPoiRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.poi import api as poi_api  # noqa: PLC0415

    wind = "mean_wind_direction_during_last_10 min_at_10_meters_above_ground"
    csv = (
        f"surface observations;Parameter description;{wind}\n"
        "10147;Unit;Grad\n"
        "Datum;Uhrzeit (UTC);Windrichtung\n"
        "12.10.26;06:00;360\n"
    ).encode("latin-1")
    serve(monkeypatch, poi_api, {"10147-BEOB.csv": csv})
    _dated(monkeypatch, poi_api, "download_file")
    request = DwdPoiRequest(
        parameters=[("hourly", "data", "wind_direction_mean_last_10min")],
        start=dt.datetime(2026, 10, 11, tzinfo=UTC),
        end=dt.datetime(2026, 10, 13, tzinfo=UTC),
        settings=Settings(cache_disable=True),
    )
    return stations_result(request, "hourly", "data", "10147").values().all()


def _read_dwd_road(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the two files a station group published, written on two days."""
    from tests.conftest import BUFR_AVAILABLE  # noqa: PLC0415
    from tests.provider.dwd.road.test_api import _flat, _stub_downloads, _stub_stations  # noqa: PLC0415
    from wetterdienst.provider.dwd.road import api as road_api  # noqa: PLC0415

    if not BUFR_AVAILABLE:
        pytest.skip("eccodes and pdbufr required")
    reading = _flat({"#1#shortStationName": "A006", "#1#airTemperature": 285.0})
    monkeypatch.setattr("pdbufr.read_bufr", lambda *_args, **_kwargs: reading)
    _stub_downloads(monkeypatch, [BytesIO(b"x" * 500), BytesIO(b"x" * 500)])
    original = road_api.download_files

    def download_files(**kwargs: object) -> list[File]:
        files = original(**kwargs)
        for file, written in zip(files, (OLD, NEW), strict=True):
            file.last_modified = written
        return files

    monkeypatch.setattr(road_api, "download_files", download_files)
    return _stub_stations().values().all()


def _forecast_of_the_run_of_the_26th(monkeypatch: pytest.MonkeyPatch, values: object) -> object:
    """Serve one run, issued at 06:00 on the 26th, to a MOSMIX or DMO values object, whatever the listing says."""
    monkeypatch.setattr(values, "get_url_for_date", lambda *_a, **_k: "https://example.invalid/run.kmz")
    monkeypatch.setattr(values.kml, "read", lambda _url: None)
    values.kml.metadata = {"issue_time": dt.datetime(2026, 10, 26, 6, tzinfo=UTC)}
    monkeypatch.setattr(
        values.kml,
        "get_station_forecast",
        lambda _station: pl.DataFrame({"timestamp": ["2026-10-26T07:00:00.000Z"], "ttt": [280.1]}),
    )
    return values.all()


def _read_dwd_mosmix(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the run of a MOSMIX forecast."""
    return _forecast_of_the_run_of_the_26th(monkeypatch, _stub_mosmix_stations().values())


def _read_dwd_dmo(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the run of a DMO forecast."""
    from tests.provider.dwd.dmo.test_api import _stub_dmo_values  # noqa: PLC0415

    return _forecast_of_the_run_of_the_26th(monkeypatch, _stub_dmo_values())


def _read_dwd_swsmos(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the run of a road weather forecast, written two days after it was issued."""
    body = "".join(f"A006;54.889156;8.908735;20261026{hour:02d}00;1{hour}.0\n" for hour in (8, 9))
    content = bz2.compress(b"ID;Lat;Lon;YYYYMMDDHHmm;TL\n202610260700\n" + body.encode("latin-1"))
    name = "swsmos_20261026070000_opendata.csv.bz2"
    monkeypatch.setattr(swsmos_api, "list_remote_files_fsspec", lambda *_a, **_k: [f"{swsmos_api._BASE_URL}/{name}"])  # noqa: SLF001
    monkeypatch.setattr(
        swsmos_api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(content), status=200, last_modified=NEWER),
    )
    request = DwdSwsmosRequest(
        parameters=[("hourly", "data", "temperature_air")], settings=Settings(cache_disable=True)
    )
    return stations_result(request, "hourly", "data", "A006").values().all()


def _read_chmi(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the daily file of a station."""
    from tests.provider.chmi.observation.test_values_frames import _DAILY_T, CHEB  # noqa: PLC0415
    from wetterdienst.provider.chmi.observation import ChmiObservationRequest  # noqa: PLC0415
    from wetterdienst.provider.chmi.observation import api as chmi_api  # noqa: PLC0415

    monkeypatch.setattr(
        chmi_api,
        "download_file",
        lambda *, url, **_: (
            File(url=url, content=BytesIO(_DAILY_T.encode()), status=200, last_modified=NEW)
            if url.endswith("-T.csv")
            else File(url=url, content=FileNotFoundError(url), status=404)
        ),
    )
    request = ChmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=True),
    )
    return stations_result(request, "daily", "data", CHEB).values().all()


def _read_imgw_hydrology(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the monthly archive of a station."""
    from tests.provider.imgw.hydrology.test_values_frames import STATION, _serve  # noqa: PLC0415
    from tests.provider.value_stubs import _day  # noqa: PLC0415
    from wetterdienst.provider.imgw.hydrology import ImgwHydrologyRequest  # noqa: PLC0415
    from wetterdienst.provider.imgw.hydrology import api as imgw_api  # noqa: PLC0415

    _serve(monkeypatch, "mies_2023.zip", "mies_2023_03.csv", "149180020,CHALUPKI,Odra,2023,03,2,141,12.5,9.9\n")
    _dated(monkeypatch, imgw_api, "download_files")
    request = ImgwHydrologyRequest(
        parameters=[("monthly", "hydrology")],
        start=_day(2023, 1, 1),
        end=_day(2023, 1, 31),
        settings=Settings(cache_disable=True),
    )
    return stations_result(request, "monthly", "hydrology", STATION).values().all()


def _read_imgw_meteorology(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the daily archive of a station."""
    from tests.provider.imgw.meteorology.test_values_frames import _K_D, _K_D_T, _serve  # noqa: PLC0415
    from tests.provider.value_stubs import _day  # noqa: PLC0415
    from wetterdienst.provider.imgw.meteorology import ImgwMeteorologyRequest  # noqa: PLC0415
    from wetterdienst.provider.imgw.meteorology import api as imgw_api  # noqa: PLC0415

    _serve(monkeypatch, "2024_04_k.zip", {"k_d_04_2024.csv": _K_D, "k_d_t_04_2024.csv": _K_D_T})
    _dated(monkeypatch, imgw_api, "download_files")
    request = ImgwMeteorologyRequest(
        parameters=[("daily", "climate", "temperature_air_mean_2m")],
        start=_day(2024, 4, 1),
        end=_day(2024, 4, 2),
        settings=Settings(cache_disable=True),
    )
    return stations_result(request, "daily", "climate", "250190390").values().all()


def _read_ipma(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read a station of the feed."""
    return _ipma_values(monkeypatch, feed_written=OLD)


def _read_meteofrance_synop(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the year files of a station, written on three days."""
    return _synop_values(monkeypatch)


def _read_meteoswiss(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the daily files of a station."""
    from tests.provider.meteoswiss.observation.test_api import _serve_station_files  # noqa: PLC0415
    from wetterdienst.provider.meteoswiss.observation import MeteoswissObservationRequest  # noqa: PLC0415
    from wetterdienst.provider.meteoswiss.observation import api as meteoswiss_api  # noqa: PLC0415

    _serve_station_files(
        monkeypatch,
        {
            "ogd-smn_ber_d_historical.csv": "station_abbr;reference_timestamp;tre200d0\nBER;01.01.2020 00:00;1.5\n",
            "ogd-smn_ber_d_recent.csv": "station_abbr;reference_timestamp;tre200d0\nBER;02.01.2020 00:00;-0.4\n",
        },
    )
    _dated(monkeypatch, meteoswiss_api, "download_file")
    return (
        MeteoswissObservationRequest(
            parameters=[("daily", "data", "temperature_air_mean_2m")],
            start="2020-01-01T00:00:00+00:00",
            end="2020-01-03T00:00:00+00:00",
            settings=Settings(cache_disable=True),
        )
        .filter_by_station_id("BER")
        .values()
        .all()
    )


def _read_noaa_ghcn(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the hourly file of a station."""
    from tests.provider.value_stubs import ghcnh_psv  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn import api as ghcn_api  # noqa: PLC0415

    stations = (
        b"GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        b"ACM00078861,17.1167,-61.7833,10.0,,COOLIDGE FIELD ANTIGUA,,,78861,,AG\n"
    )
    settings = Settings(cache_disable=True)
    metadata = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=settings).metadata
    columns = [parameter.name_original for parameter in metadata["hourly"]["data"]]
    body = ghcnh_psv("ACM00078861", columns, [("1942-01-17T02:00:00", {"wind_speed": "3.0"})])

    def download_file(*, url: str, **_: object) -> File:
        content = stations if "ghcnh-station-list" in url else body
        return File(url=url, content=BytesIO(content), status=200, last_modified=NEW)

    monkeypatch.setattr(ghcn_api, "download_file", download_file)
    return (
        NoaaGhcnRequest(
            parameters=[("hourly", "data", "wind_speed")],
            start=dt.datetime(1942, 1, 17, tzinfo=UTC),
            end=dt.datetime(1942, 1, 18, tzinfo=UTC),
            settings=settings,
        )
        .filter_by_station_id("ACM00078861")
        .values()
        .all()
    )


#: an offline read of each network that dates what it reads, which the registry of `tests/ui` runs
READERS = {
    ("chmi", "observation"): _read_chmi,
    ("dwd", "derived"): _read_dwd_derived,
    ("dwd", "dmo"): _read_dwd_dmo,
    ("dwd", "mosmix"): _read_dwd_mosmix,
    ("dwd", "observation"): _read_dwd_observation,
    ("dwd", "phenology"): _read_dwd_phenology,
    ("dwd", "poi"): _read_dwd_poi,
    ("dwd", "road"): _read_dwd_road,
    ("dwd", "swsmos"): _read_dwd_swsmos,
    ("imgw", "hydrology"): _read_imgw_hydrology,
    ("imgw", "meteorology"): _read_imgw_meteorology,
    ("ipma", "observation"): _read_ipma,
    ("meteofrance", "synop"): _read_meteofrance_synop,
    ("meteoswiss", "observation"): _read_meteoswiss,
    ("noaa", "ghcn"): _read_noaa_ghcn,
}


def _values_for_window(start: datetime | None, end: datetime | None, *, drop_nulls: bool = True) -> object:
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start=start,
        end=end,
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=drop_nulls),
    )
    return stations_result(request, "daily", "climate_summary", "00001").values()


_UTC_STAMP = pl.Datetime(time_zone="UTC")


@pytest.mark.parametrize(
    ("frame", "expected"),
    [
        pytest.param(pl.DataFrame({"timestamp": [dt.datetime(2020, 1, 2, tzinfo=UTC)]}), True, id="aware-inside"),
        pytest.param(pl.DataFrame({"timestamp": [dt.datetime(2020, 1, 5, tzinfo=UTC)]}), False, id="aware-outside"),
        pytest.param(pl.DataFrame({"timestamp": [dt.datetime(2020, 1, 2)]}), True, id="naive-is-utc"),  # noqa: DTZ001
        pytest.param(pl.DataFrame({"timestamp": [dt.datetime(2020, 1, 5)]}), False, id="naive-outside"),  # noqa: DTZ001
        pytest.param(pl.DataFrame({"timestamp": [dt.date(2020, 1, 2)]}), True, id="date-inside"),
        pytest.param(pl.DataFrame({"timestamp": [dt.date(2021, 1, 2)]}), False, id="date-outside"),
        pytest.param(pl.DataFrame({"timestamp": ["2021-01-01"]}), True, id="text-cannot-be-told"),
        pytest.param(pl.DataFrame({"other": [1]}), True, id="no-column"),
        pytest.param(pl.DataFrame({"timestamp": []}, schema={"timestamp": _UTC_STAMP}), False, id="empty"),
    ],
)
def test_a_frame_has_rows_in_the_window_as_the_core_cuts_it(frame: pl.DataFrame, *, expected: bool) -> None:
    """A date, a stamp with or without a zone and a column that cannot be read, against the 1st to the 3rd."""
    values = _values_for_window(dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 1, 3, tzinfo=UTC))

    assert values._has_rows_in_window(frame) is expected  # noqa: SLF001


def test_a_frame_without_a_window_has_rows_where_it_has_any() -> None:
    """With no window every row is in, and a frame with none is not."""
    values = _values_for_window(None, None)

    assert values._has_rows_in_window(pl.DataFrame({"timestamp": [dt.datetime(1900, 1, 1, tzinfo=UTC)]}))  # noqa: SLF001
    assert not values._has_rows_in_window(pl.DataFrame({"timestamp": []}, schema={"timestamp": _UTC_STAMP}))  # noqa: SLF001


@pytest.mark.parametrize(("drop_nulls", "expected"), [(True, False), (False, True)])
def test_a_frame_of_nulls_has_rows_only_where_the_nulls_are_kept(*, drop_nulls: bool, expected: bool) -> None:
    """A row the core drops with `drop_nulls` does not count for the answer, one it keeps does."""
    values = _values_for_window(None, None, drop_nulls=drop_nulls)
    frame = pl.DataFrame(
        {"timestamp": [dt.datetime(2020, 1, 2, tzinfo=UTC)], "value": [None]}, schema_overrides={"value": pl.Float64}
    )

    assert values._has_rows_in_window(frame, value="value") is expected  # noqa: SLF001


def test_meteofrance_synop_a_file_with_only_a_parameter_that_was_not_asked_for_does_not_date_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The newest file holds a value of the station, but of a parameter the request did not name: it is cut later."""
    schema = list(synop_api._SYNOP_CSV_SCHEMA)  # noqa: SLF001

    def file(stamp: str, **values: str) -> bytes:
        row = {"geo_id_wmo": "07005", "validity_time": stamp, **values}
        lines = [";".join(schema), ";".join(row.get(column, "") for column in schema)]
        return gzip.compress("\n".join(lines).encode("utf8"))

    files = {
        "synop_2023": (file("2023-12-31T18:00:00Z", t="280.0"), OLD),
        "synop_2024": (file("2024-01-01T18:00:00Z", ff="3.0"), NEWER),
    }

    def download_file(*, url: str, **_: object) -> File:
        content, written = next(entry for part, entry in files.items() if part in url)
        return File(url=url, content=BytesIO(content), status=200, last_modified=written)

    monkeypatch.setattr(synop_api, "download_file", download_file)
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", "temperature_air_2m")],
        start=dt.datetime(2023, 12, 31, tzinfo=UTC),
        end=dt.datetime(2024, 1, 2, tzinfo=UTC),
        settings=Settings(cache_disable=True),
    )

    result = stations_result(request, "subdaily", "data", "07005").values().all()

    assert not result.df.is_empty()
    assert result.data_updated_at == OLD


def test_ipma_a_feed_without_a_row_of_a_requested_parameter_does_not_date_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The feed holds a temperature of the station only, and the request asks for the humidity: no row, no date."""

    def download_file(url: str, **_: object) -> File:
        if url.endswith("observations.json"):
            return File(url=url, content=BytesIO(_IPMA_FEED), status=200, last_modified=OLD)
        return File(url=url, content=BytesIO(_IPMA_STATIONS), status=200, last_modified=NEWER)

    monkeypatch.setattr(ipma_api, "download_file", download_file)
    result = (
        IpmaObservationRequest(
            parameters=[("hourly", "data", "humidity_relative_mean")],
            start=dt.datetime(2026, 10, 10, 11, tzinfo=UTC),
            end=dt.datetime(2026, 10, 10, 14, tzinfo=UTC),
            settings=Settings(cache_disable=True),
        )
        .filter_by_station_id("1200579")
        .values()
        .all()
    )

    assert result.df.is_empty()
    assert result.data_updated_at is None
