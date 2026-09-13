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


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_file_with_only_the_first_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    """A file that speaks to one batch of columns and not the other keeps what it did say.

    The columns are read in two batches, and a group of stations reporting temperatures and no
    wind at all answers the first read and not the second. Merging a frame with no columns is a
    join on a key that is not there -- but skipping the file to avoid that throws away every
    temperature in it, so it is the merge that is skipped.
    """
    import pandas as pd  # noqa: PLC0415

    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    parameters = list(DwdRoadRequest.metadata["15_minutes"]["data"])
    first_batch = [parameter.name_original for parameter in parameters][:10]
    keys = {"year": 2026, "month": 9, "day": 13, "hour": 12, "minute": 0, "shortStationName": "A006"}
    populated = pd.DataFrame([{**keys, "airTemperature": 12.0, "roadSurfaceTemperature": 18.0}])

    def read_first_batch_only(_path: object, columns: tuple[str, ...], **_kwargs: object) -> pd.DataFrame:
        return populated if set(first_batch) & set(columns) else pd.DataFrame()

    monkeypatch.setattr("pdbufr.read_bufr", read_first_batch_only)
    file = File(url="", content=BytesIO(b"not a real bufr message"), status=200)
    parse = api.DwdRoadValues._DwdRoadValues__parse_dwd_road_weather_data  # noqa: SLF001
    df = parse(file, parameters)
    readings = dict(df.drop_nulls("value").select("parameter", "value").iter_rows())
    # what the first read returned, not an empty frame standing in for the whole file
    assert readings == {"airTemperature": 12.0, "roadSurfaceTemperature": 18.0}
    # and the second batch's parameters are there as nulls, so the frame keeps its shape
    assert df.get_column("parameter").n_unique() == len(parameters)


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_folds_a_station_reported_in_parts(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station whose reading arrives in parts keeps all of it.

    A road file holds one subset per station carrying the descriptors that station has, and
    `read_bufr` emits an observation only where every column asked for is present. Asking for
    fourteen and keeping the complete ones threw away every reading of anything not universally
    fitted -- against a real file of the DD group the parse returned 105 values where the file held 121,
    the whole of `roadSurfaceTemperature` among the missing, on a road weather network.
    """
    import pandas as pd  # noqa: PLC0415

    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    keys = {"year": 2026, "month": 9, "day": 13, "hour": 12, "minute": 0, "shortStationName": "A006"}
    asked_for: list[object] = []

    def read_in_parts(_path: object, columns: tuple[str, ...], **kwargs: object) -> pd.DataFrame:
        asked_for.append(kwargs.get("required_columns"))
        if "windSpeed" in columns:
            return pd.DataFrame([{**keys, "windSpeed": 3.0}])
        # one station and minute, arriving as two subsets, neither of them whole
        return pd.DataFrame(
            [
                {**keys, "airTemperature": 12.0, "roadSurfaceTemperature": None},
                {**keys, "airTemperature": None, "roadSurfaceTemperature": 18.0},
            ],
        )

    monkeypatch.setattr("pdbufr.read_bufr", read_in_parts)
    parameters = list(DwdRoadRequest.metadata["15_minutes"]["data"])
    file = File(url="", content=BytesIO(b"not a real bufr message"), status=200)
    parse = api.DwdRoadValues._DwdRoadValues__parse_dwd_road_weather_data  # noqa: SLF001
    df = parse(file, parameters)
    readings = dict(df.drop_nulls("value").select("parameter", "value").iter_rows())
    # both halves of the one reading, where keeping only whole subsets would have kept neither
    assert readings["airTemperature"] == 12.0
    assert readings["roadSurfaceTemperature"] == 18.0
    assert readings["windSpeed"] == 3.0
    # folded rather than left side by side: the two subsets are one reading, so each parameter of
    # the dataset comes back once and not once per subset that mentioned it
    assert df.height == len(parameters)
    # and it is the keys the reads are required of, which is what lets a part be a part
    assert asked_for == [api._READING_KEYS, api._READING_KEYS]  # noqa: SLF001


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_parameter_no_subset_carries(monkeypatch: pytest.MonkeyPatch) -> None:
    """A descriptor no subset carries is a null column, not a missing one.

    Required of the keys alone, a column nothing reports is not in the frame at all -- and the
    select that follows asks for every parameter of the dataset by name.
    """
    import pandas as pd  # noqa: PLC0415

    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    keys = {"year": 2026, "month": 9, "day": 13, "hour": 12, "minute": 0, "shortStationName": "A006"}

    def read_one_descriptor(_path: object, columns: tuple[str, ...], **_kwargs: object) -> pd.DataFrame:
        # the two batches ask for disjoint columns, so only the one holding airTemperature has it
        if "airTemperature" not in columns:
            return pd.DataFrame([dict(keys)])
        return pd.DataFrame([{**keys, "airTemperature": 12.0}])

    monkeypatch.setattr("pdbufr.read_bufr", read_one_descriptor)
    parameters = list(DwdRoadRequest.metadata["15_minutes"]["data"])
    file = File(url="", content=BytesIO(b"not a real bufr message"), status=200)
    parse = api.DwdRoadValues._DwdRoadValues__parse_dwd_road_weather_data  # noqa: SLF001
    df = parse(file, parameters)
    assert df.get_column("parameter").n_unique() == len(parameters)
    assert df.drop_nulls("value").get_column("parameter").to_list() == ["airTemperature"]


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.parametrize(
    ("files_upstream_has", "case"),
    [
        ([], "the group published no file"),
        (["a-file-holding-nothing"], "every file it published held nothing"),
    ],
)
def test_dwd_road_weather_empty_is_one_shape(
    monkeypatch: pytest.MonkeyPatch,
    files_upstream_has: list[str],
    case: str,
) -> None:
    """Nothing to answer with comes back in the shape something to answer with comes back in.

    There were three shapes for this: no columns where the group published no file, five where the
    files it published held nothing, and the seven columns a reading has. All three were handed to
    a caller that reads the first as "this station had nothing" and would meet either of the others
    with a width it did not expect or a column that is not there.
    """
    import pandas as pd  # noqa: PLC0415

    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    # big enough to clear the size filter, and holding nothing a reader can use
    file = File(url="a-file-holding-nothing", content=BytesIO(b"x" * 500), status=200)
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: files_upstream_has)
    monkeypatch.setattr(api, "download_files", lambda **_kwargs: [file] if files_upstream_has else [])
    monkeypatch.setattr("pdbufr.read_bufr", lambda *_args, **_kwargs: pd.DataFrame())

    df = _stub_stations().values._collect_station_parameter_or_dataset(  # noqa: SLF001
        station_id="A006",
        parameter_or_dataset=DwdRoadRequest.metadata["15_minutes"]["data"],
    )
    assert df.is_empty(), case
    assert df.columns == ["resolution", "dataset", "parameter", "station_id", "date", "value", "quality"], case
