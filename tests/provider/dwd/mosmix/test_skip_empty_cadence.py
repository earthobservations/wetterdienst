# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for `skip_empty` over the elements MOSMIX gives at some steps only: the cadence is the file's (GH-4093).

The run of MOSMIX-SNOW beside `test_snow.py` gives `SnCv` at every 3rd of 48 steps (16) at all of its 15 stations; a
share measured against every hour would skip each station at 0.33.
"""

from __future__ import annotations

import datetime as dt
import re
import zipfile
from io import BytesIO
from typing import TYPE_CHECKING

import polars as pl

from tests.provider.dwd.mosmix.test_products import LARGE, RUNS, SMALL, _kml, parses
from tests.provider.dwd.mosmix.test_snow import LISTING, RUN, run_of_the_14th
from tests.provider.value_stubs import _settings, stations_result
from wetterdienst import Options
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, api
from wetterdienst.provider.dwd.mosmix.access import KMLReader
from wetterdienst.provider.dwd.mosmix.metadata import DwdMosmixMetadata

if TYPE_CHECKING:
    import pytest

__all__ = ["parses", "run_of_the_14th"]  # the fixtures, used by name

UTC = dt.UTC

SKIP_EMPTY = Options(skip_empty=True, skip_threshold=0.95)


def _snow(
    station_id: str,
    options: Options = SKIP_EMPTY,
    parameters: tuple[str, ...] = ("snow_depth",),
    window: tuple[dt.datetime, dt.datetime] | None = None,
) -> list[pl.DataFrame]:
    """Give the frames of the stations answered for the parameters of the snow dataset at one station."""
    request = DwdMosmixRequest(
        parameters=[("hourly", "snow", parameter) for parameter in parameters],
        start=window[0] if window else None,
        end=window[1] if window else None,
        settings=_settings(),
        options=options,
    )
    return [result.df for result in stations_result(request, "hourly", "snow", station_id).values().query()]


def _run_edited(edit: dict[tuple[str, str], str]) -> bytes:
    """Give the run of the 14th with the values of an element at a station replaced: `{(station, element): values}`."""
    with zipfile.ZipFile(RUN) as archive:
        name = archive.namelist()[0]
        kml = archive.read(name).decode("latin-1")
    for (station_id, element), values in edit.items():
        start = kml.index(f"<kml:name>{station_id}</kml:name>")
        value = re.compile(rf'(elementName="{element}">\s*<dwd:value>)[^<]*(</dwd:value>)')
        match = value.search(kml, start)
        assert match is not None
        kml = kml[: match.start()] + match.group(1) + values + match.group(2) + kml[match.end() :]
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, kml.encode("latin-1"))
    return out.getvalue()


def _tokens(station_id: str, element: str) -> list[str]:
    """Give the values of an element at a station of the run, as the file writes them."""
    with zipfile.ZipFile(RUN) as archive:
        kml = archive.read(archive.namelist()[0]).decode("latin-1")
    start = kml.index(f"<kml:name>{station_id}</kml:name>")
    match = re.compile(rf'elementName="{element}">\s*<dwd:value>([^<]*)</dwd:value>').search(kml, start)
    assert match is not None
    return match.group(1).split()


def test_reader_collects_the_steps_of_the_elements_asked_for_at_every_station(
    run_of_the_14th: list[str],  # noqa: ARG001
) -> None:
    """The steps come from the 15 stations of the file though one is asked for, of the elements named only."""
    reader = KMLReader(station_ids=["Z914"], settings=_settings())
    reader.read(LISTING[1], steps_of=["SnCv", "TTT", "nosuchelement"])

    assert sorted(reader.data) == ["Z914"]
    sncv = reader.given_timesteps(LISTING[1], "SnCv")
    assert sncv == reader.timesteps[1::3]
    assert len(sncv) == 16
    # an element given at every step, and one no station has
    assert reader.given_timesteps(LISTING[1], "TTT") == reader.timesteps
    assert reader.given_timesteps(LISTING[1], "nosuchelement") == []
    # an element not named is not noted, though the file has it
    assert reader.given_timesteps(LISTING[1], "FF") == []
    # a file never read is not held
    assert reader.given_timesteps("https://example.invalid/other.kmz", "SnCv") is None

    default = KMLReader(station_ids=["Z914"], settings=_settings())
    default.read(LISTING[1])
    assert default.given_timesteps(LISTING[1], "SnCv") is None
    assert default.data == reader.data


def test_reader_looks_at_no_other_station_once_every_step_of_the_elements_is_seen(
    monkeypatch: pytest.MonkeyPatch,
    run_of_the_14th: list[str],  # noqa: ARG001
) -> None:
    """`TTT` is complete at the first station of the file: the placemarks after it are not looked into for it."""
    looked: list[str] = []
    original = KMLReader._elements_of  # noqa: SLF001

    def counting(station_forecast: object, nsmap: dict[str, str]) -> object:
        looked.append("looked")
        return original(station_forecast, nsmap)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(KMLReader, "_elements_of", staticmethod(counting))
    reader = KMLReader(station_ids=["Z946"], settings=_settings())
    reader.read(LISTING[1], steps_of=["TTT"])
    # the first station completes the element, and the last, asked for, is read as always
    assert len(looked) == 2
    assert reader.given_timesteps(LISTING[1], "TTT") == reader.timesteps

    looked.clear()
    reader = KMLReader(station_ids=["Z946"], settings=_settings())
    reader.read(LISTING[1], steps_of=["SnCv"])
    # every station is looked into for an element given at some steps only, until all of its steps were seen
    assert len(looked) > 2


def test_station_that_has_every_step_its_file_gives_is_not_skipped(run_of_the_14th: list[str]) -> None:  # noqa: ARG001
    """`Z914` has `SnCv` at 16 of 48 steps, as every station of the file does: 0.33 of the grid, 1.0 of the steps."""
    frames = _snow("Z914")

    assert [frame["station_id"].unique().to_list() for frame in frames] == [["Z914"]]
    assert frames[0]["value"].is_not_null().sum() == 16


def test_the_threshold_still_judges_what_the_file_gives(
    monkeypatch: pytest.MonkeyPatch,
    run_of_the_14th: list[str],  # noqa: ARG001
) -> None:
    """A station lacking half of the steps its file gives is skipped, and is kept under a threshold of one half."""
    tokens = _tokens("Z914", "SnCv")
    given = [index for index, value in enumerate(tokens) if value != "-"]
    assert len(given) == 16
    # Z914 loses 8 of the 16 steps that the other stations still have
    lost = dict.fromkeys(given[::2], "-")
    halved = " ".join(lost.get(index, value) for index, value in enumerate(tokens))
    run = _run_edited({("Z914", "SnCv"): halved})
    monkeypatch.setattr(api.KMLReader, "download", lambda _self, _url: BytesIO(run))

    assert _snow("Z914") == []
    assert len(_snow("Z914", Options(skip_empty=True, skip_threshold=0.5))) == 1


def test_the_steps_are_those_of_every_station_of_the_file_and_not_of_the_ones_asked_for(
    monkeypatch: pytest.MonkeyPatch,
    run_of_the_14th: list[str],  # noqa: ARG001
) -> None:
    """A step that only another station of the file has a value at counts for `Z914` too: 16 of 17 steps are 0.94."""
    tokens = _tokens("Z901", "SnCv")
    assert tokens[0] == "-"
    extra = " ".join(["0.14", *tokens[1:]])
    run = _run_edited({("Z901", "SnCv"): extra})
    monkeypatch.setattr(api.KMLReader, "download", lambda _self, _url: BytesIO(run))

    assert _snow("Z914") == []
    # the station that has it is complete, and `Z914` under a threshold that lets one step in seventeen go
    assert len(_snow("Z901")) == 1
    assert len(_snow("Z914", Options(skip_empty=True, skip_threshold=0.9))) == 1


def test_an_element_no_station_has_a_value_of_is_a_station_without_it(
    monkeypatch: pytest.MonkeyPatch,
    run_of_the_14th: list[str],  # noqa: ARG001
) -> None:
    """The file gives no step of an element that is `-` at every station of it: nothing is measured, and zero is.

    A no-regression check: the station was skipped for this before the cadence was read from the file and still is.
    """
    blank = " ".join(["-"] * 48)
    stations = ("Z901", "Z905", "Z908", "Z912", "Z914", "Z916", "Z917", "Z919", "Z928", "Z932", "Z934", "Z936")
    stations += ("Z943", "Z944", "Z946")
    run = _run_edited({(station_id, "SnCv"): blank for station_id in stations})
    monkeypatch.setattr(api.KMLReader, "download", lambda _self, _url: BytesIO(run))

    # with the nulls kept the station has the element, all null: the share is 0, and it is skipped
    assert _snow("Z914", Options(drop_nulls=False, skip_empty=True, skip_threshold=0.95)) == []


def test_skip_empty_off_is_the_answer_it_was(run_of_the_14th: list[str]) -> None:  # noqa: ARG001
    """Without `skip_empty` the reader collects nothing and the answer is the same station's values."""
    request = DwdMosmixRequest(parameters=[("hourly", "snow", "snow_depth")], settings=_settings(), options=Options())
    values = stations_result(request, "hourly", "snow", "Z914").values()
    kept = [result.df for result in values.query()]
    skipping = _snow("Z914")

    assert len(kept) == 1
    assert kept[0].equals(skipping[0])
    # nothing was noted of the file's steps, and nothing is asked of the reader for them
    assert values.kml._parsed[LISTING[1]].given is None  # noqa: SLF001
    assert values._steps_of(DwdMosmixMetadata.hourly.snow) is None  # noqa: SLF001


def test_a_window_between_the_steps_of_an_element_does_not_skip_the_station(
    run_of_the_14th: list[str],  # noqa: ARG001
) -> None:
    """`SnCv` is given at 21:00 and 00:00: a window of 22:00 to 23:00 has no step of it, so it is not measured."""
    window = (dt.datetime(2026, 11, 14, 22, tzinfo=UTC), dt.datetime(2026, 11, 14, 23, tzinfo=UTC))

    # alone, with the nulls kept (the frame of nulls is the station's answer: nothing is said of it by the share)
    alone = _snow("Z914", Options(drop_nulls=False, skip_empty=True, skip_threshold=0.95), window=window)
    assert len(alone) == 1
    assert alone[0]["value"].is_null().all()
    # beside a dense element, which is measured and complete
    both = _snow("Z914", parameters=("snow_depth", "temperature_air_2m"), window=window)
    assert len(both) == 1
    assert set(both[0]["parameter"]) == {"temperature_air_2m"}


def test_steps_past_the_horizon_of_the_run_do_not_count_against_the_station(
    run_of_the_14th: list[str],  # noqa: ARG001
) -> None:
    """A dense element over 96 hours of a run of 48 hours: its 48 steps are all the file gives, and all are there."""
    window = (dt.datetime(2026, 11, 14, 20, tzinfo=UTC), dt.datetime(2026, 11, 18, 20, tzinfo=UTC))

    frames = _snow("Z914", parameters=("temperature_air_2m",), window=window)

    assert len(frames) == 1
    assert frames[0]["value"].is_not_null().sum() == 48


def _serve_large(monkeypatch: pytest.MonkeyPatch, tx: str) -> None:
    """Serve a MOSMIX-L run of 14 hours (10 to 23 UTC) of one station with the given `TX` and `TTT` at every hour."""
    run = _kml({"01001": {"TX": tx, "TTT": " ".join(["280.15"] * 14)}}, hours=tuple(range(10, 24)))
    monkeypatch.setitem(RUNS, LARGE, run)
    monkeypatch.setattr(api.DwdMosmixValues, "get_url_for_date", lambda *_args, **_kwargs: LARGE)


def test_tx_given_at_two_steps_has_no_say_about_a_window_between_them(
    monkeypatch: pytest.MonkeyPatch,
    parses: list[str],  # noqa: ARG001
) -> None:
    """`TX` is given at 12 and 22 UTC: a window of 13:00 to 21:00 holds none of it, and the station is not skipped."""
    _serve_large(monkeypatch, " ".join("281.15" if hour in {12, 22} else "-" for hour in range(10, 24)))
    window = {"start": dt.datetime(2026, 10, 10, 13, tzinfo=UTC), "end": dt.datetime(2026, 10, 10, 21, tzinfo=UTC)}

    def read(parameters: list[tuple[str, str, str]], options: Options) -> pl.DataFrame:
        request = DwdMosmixRequest(parameters=parameters, settings=_settings(), options=options, **window)
        return stations_result(request, "hourly", "large", "01001").values().all().df

    alone = read([("hourly", "large", "tx")], Options(drop_nulls=False, skip_empty=True, skip_threshold=0.95))
    assert alone["station_id"].unique().to_list() == ["01001"]
    both = read([("hourly", "large", "tx"), ("hourly", "large", "ttt")], Options(skip_empty=True, skip_threshold=0.95))
    assert set(both["parameter"]) == {"temperature_air_2m"}


def test_each_dataset_of_a_mixed_request_is_measured_by_its_own_file(
    monkeypatch: pytest.MonkeyPatch,
    parses: list[str],  # noqa: ARG001
) -> None:
    """`ttt` of the small run and `tx` of the large one, which is given at the last step only at both stations."""
    stations = pl.DataFrame(
        [
            {"resolution": "hourly", "dataset": dataset, "station_id": station_id, "latitude": 50.0, "longitude": 10.0}
            for dataset in ("small", "large")
            for station_id in ("01001", "01002")
        ]
    ).with_columns(
        pl.lit(None, pl.Datetime("us", "UTC")).alias("start_timestamp"),
        pl.lit(None, pl.Datetime("us", "UTC")).alias("end_timestamp"),
        pl.lit(100.0).alias("elevation"),
        pl.lit("Stub").alias("name"),
    )
    request = DwdMosmixRequest(
        parameters=[("hourly", "small", "ttt"), ("hourly", "large", "tx")],
        settings=_settings(),
        options=Options(skip_empty=True, skip_threshold=0.95),
    )
    result = StationsResult(
        request=request, df=stations, _df_all=stations, _stations_filter=StationsFilter.BY_STATION_ID
    )
    monkeypatch.setattr(
        api.DwdMosmixValues, "get_url_for_date", lambda _self, url, *_args, **_kwargs: LARGE if "_L" in url else SMALL
    )
    assert RUNS[LARGE] != RUNS[SMALL]

    df = result.values().all().df

    assert sorted(df["station_id"].unique().to_list()) == ["01001", "01002"]
    assert set(df["parameter"]) == {"temperature_air_2m", "temperature_air_max_2m_last_12h"}
