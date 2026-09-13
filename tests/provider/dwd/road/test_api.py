# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD road weather API."""

from io import BytesIO

import polars as pl
import pytest

from tests.conftest import BUFR_AVAILABLE, IS_CI, IS_WINDOWS
from wetterdienst import Settings
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.road.api import DwdRoadRequest, DwdRoadStationGroup
from wetterdienst.util.network import File, list_remote_files_fsspec


@pytest.mark.skipif(IS_CI and IS_WINDOWS, reason="permission with storage in CI on Windows")
@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.remote
def test_dwd_road_weather() -> None:
    """Test fetching of DWD road weather data."""
    request = DwdRoadRequest(parameters=[("15_minutes", "data", "temperature_air_mean_2m")]).filter_by_station_id(
        "A006",
    )
    item = request.to_dict()["stations"][0]
    assert item == {
        "resolution": "15_minutes",
        "dataset": "data",
        "station_id": "A006",
        "start_date": None,
        "end_date": None,
        "latitude": 54.8892,
        "longitude": 8.9087,
        "height": 2.0,
        "name": "Boeglum",
        "state": "SH",
        "road_name": "L5S",
        "road_sector": "2",
        "road_surface_type": 1,
        "road_surroundings_type": 2,
        "road_type": 1,
        "station_group": "KK",
    }
    values = request.values.all().df.drop_nulls(subset="value")
    assert -40 <= values.get_column("value").min() <= 40  # approx. -+40 K


@pytest.mark.xfail(reason="number of station groups may change")
def test_dwd_road_weather_station_groups() -> None:
    """Test fetching of DWD road weather station groups."""
    url = "https://opendata.dwd.de/weather/weather_reports/road_weather_stations/"
    files = list_remote_files_fsspec(
        url=url,
        settings=Settings(),
        cache_expiry=CacheExpiry.METAINDEX,
    )
    files = {file[len(url) :].split("/")[0] for file in files}
    if "quality-assured" in files:
        files.remove("quality-assured")
    assert files == {group.value for group in DwdRoadStationGroup}


def _stub_stations() -> StationsResult:
    """Stand a road station up rather than look one up.

    Asked of the real index, a test about frame handling would find no station the day A006 leaves
    the network, walk no stations, and pass on an empty frame having exercised nothing.
    """
    request = DwdRoadRequest(parameters=[("15_minutes", "data", "temperature_air_mean_2m")])
    df_stations = pl.DataFrame(
        [
            {
                "resolution": "15_minutes",
                "dataset": "data",
                "station_id": "A006",
                "start_date": None,
                "end_date": None,
                "latitude": 54.8892,
                "longitude": 8.9087,
                "height": 2.0,
                "name": "Boeglum",
                "state": "SH",
                "station_group": "DD",
            },
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "end_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "height": pl.Float64,
            "name": pl.String,
            "state": pl.String,
            "station_group": pl.String,
        },
        orient="row",
    )
    return StationsResult(
        stations=request,
        df=df_stations,
        df_all=df_stations,
        stations_filter=StationsFilter.BY_STATION_ID,
    )


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_group_with_nothing_published(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station group with no usable file is an empty result, not a broken frame.

    The road stations report in fifteen-minute batches and four of the groups are already known to
    go quiet, so a window with no file behind it -- or one holding only the 142-byte empty files of
    GH-1526 -- is an ordinary outcome. It used to raise `ColumnNotFoundError: unable to find column
    "station_id"; valid columns: []` out of the middle of the collection walk, because the frame
    standing for "nothing here" was filtered before anyone asked whether it held anything.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    # the group publishes nothing for the window, which is the whole of what upstream has to say
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [])
    df = _stub_stations().values.all().df
    assert df.is_empty()
    # and it is an answer rather than a hole: the columns a caller asks the result for are there
    assert set(df.columns) == {"station_id", "resolution", "dataset", "parameter", "date", "value", "quality"}


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_file_that_decodes_to_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A file that survives the size filter and decodes to nothing is nothing, not a broken frame.

    The size filter turns the empty files away by their exact length, which is a guess at a shape
    rather than a reading of one. A file holding no subsets at some other length reaches the parse,
    where an empty read took the select into a column that was not there.
    """
    import pandas as pd  # noqa: PLC0415

    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    monkeypatch.setattr("pdbufr.read_bufr", lambda *_args, **_kwargs: pd.DataFrame())
    parameters = list(DwdRoadRequest.metadata["15_minutes"]["data"])
    file = File(url="", content=BytesIO(b"not a real bufr message"), status=200)
    parse = api.DwdRoadValues._DwdRoadValues__parse_dwd_road_weather_data  # noqa: SLF001
    df = parse(file, parameters)
    assert df.is_empty()
    # in the shape the files that do hold something come back in, so the two concatenate
    assert set(df.columns) == {"station_id", "date", "parameter", "value", "quality"}
    assert df.schema["date"] == pl.Datetime(time_zone="UTC")


def test_dwd_road_weather_file_with_only_the_first_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    """The columns are read in two batches, and the second comes back empty on its own terms.

    A station reporting temperatures and no wind at all answers the first read and not the second,
    and `merge` on a frame with no columns is a join on a key that is not there -- `KeyError:
    'year'`, out of the middle of the collection walk.
    """
    import pandas as pd  # noqa: PLC0415

    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    parameters = list(DwdRoadRequest.metadata["15_minutes"]["data"])
    first_batch = [parameter.name_original for parameter in parameters][:10]
    populated = pd.DataFrame(
        [
            {"year": 2026, "month": 9, "day": 13, "hour": 12, "minute": 0, "shortStationName": "A006"}
            | dict.fromkeys(first_batch, 1.0)
        ],
    )

    def read_first_batch_only(_path: object, columns: tuple[str, ...], **_kwargs: object) -> pd.DataFrame:
        return populated if set(first_batch) & set(columns) else pd.DataFrame()

    monkeypatch.setattr("pdbufr.read_bufr", read_first_batch_only)
    file = File(url="", content=BytesIO(b"not a real bufr message"), status=200)
    parse = api.DwdRoadValues._DwdRoadValues__parse_dwd_road_weather_data  # noqa: SLF001
    df = parse(file, parameters)
    assert df.is_empty()
    assert set(df.columns) == {"station_id", "date", "parameter", "value", "quality"}


def test_require_bufr_says_what_to_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Road data without the reader is refused with the remedy, not with a loader error.

    `bufr_is_available` is cached, so absence is simulated where `require_bufr` looks the answer up
    rather than at the two halves behind it.
    """
    from wetterdienst.util import eccodes  # noqa: PLC0415

    monkeypatch.setattr(eccodes, "bufr_is_available", lambda: False)
    with pytest.raises(ImportError, match=r"pip install wetterdienst\[bufr\]"):
        _ = _stub_stations().values
