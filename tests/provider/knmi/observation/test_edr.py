# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The reading of the EDR API's answers, and the arithmetic of its chunks (GH-3928).

The answers are real ones: `files/edr_<resolution>.json` hold what the API answered on 2026-11-11 and 2026-11-12 for De
Bilt (06260) and Schiphol (06240), cut down to the variables the provider maps (see `edr_stub`).
"""

from __future__ import annotations

import datetime as dt
import json
import math

import pytest

from tests.provider.knmi.observation.edr_stub import FILES, PARAMETERS, RESOLUTION_OF_NAME
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.knmi.observation import api, edr
from wetterdienst.provider.knmi.observation.edr import Chunk, UnusableAnswerError, parse_coverage_json
from wetterdienst.provider.knmi.observation.grid import advance

h5netcdf = pytest.importorskip("h5netcdf", reason="h5netcdf not installed")

UTC = dt.UTC
NOW = dt.datetime(2026, 11, 12, 12, 30, tzinfo=UTC)


def _at(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=UTC)


def _answer(name: str) -> bytes:
    return (FILES / f"edr_{name}.json").read_bytes()


def _rows(name: str, station: str = "06260") -> dict[tuple[dt.datetime, str], float]:
    frames = parse_coverage_json(_answer(name), PARAMETERS[RESOLUTION_OF_NAME[name]], RESOLUTION_OF_NAME[name])
    return {(row["timestamp"], row["parameter"]): row["value"] for row in frames[station].iter_rows(named=True)}


def test_the_day_that_the_api_stamps_with_its_end_is_stamped_with_its_start() -> None:
    """De Bilt, 2020-01-01: TG 0.8, TN -0.2, TX 1.8, RH 0.0, stamped `2020-01-02T00:00Z` by the API (2026-11-11)."""
    rows = _rows("daily")
    day = _at(2020, 1, 1)
    assert [rows[(day, name)] for name in ("TG", "TN", "TX", "RH")] == [0.8, -0.2, 1.8, 0.0]
    stamps = sorted({stamp for stamp, _ in rows})
    assert stamps[0] == _at(2019, 12, 29)
    assert stamps[-1] == _at(2020, 1, 4)


def test_a_month_and_a_year_are_stamped_with_their_first_day() -> None:
    """The monthly and the annual API stamp the end of the period too (read 2026-11-12): January 2020 is 2020-02-01."""
    monthly = _rows("monthly")
    assert sorted({stamp for stamp, _ in monthly}) == [
        _at(2019, 12, 1),
        _at(2020, 1, 1),
        _at(2020, 2, 1),
        _at(2020, 3, 1),
    ]
    assert monthly[(_at(2020, 1, 1), "TG")] == 6.2
    annual = _rows("annual")
    assert sorted({stamp for stamp, _ in annual}) == [
        _at(2017, 1, 1),
        _at(2018, 1, 1),
        _at(2019, 1, 1),
        _at(2020, 1, 1),
    ]
    assert annual[(_at(2018, 1, 1), "TG")] == 11.3  # 2018, the hot year of De Bilt


@pytest.mark.parametrize("name", ["10_minutes", "hourly"])
def test_the_10_minute_and_hourly_stamps_stay_as_they_are(name: str) -> None:
    """The end of the interval is what the provider stamps these with: the first stamp of the answer is a row."""
    document = json.loads(_answer(name))
    first = document["coverages"][0]["domain"]["axes"]["t"]["values"][0]
    stamps = {stamp for stamp, _ in _rows(name)}
    assert min(stamps) == dt.datetime.strptime(first, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def test_a_parameter_that_a_station_has_no_sensor_for_is_a_nan_and_a_null_is_a_nan() -> None:
    """The API leaves `vv` out for De Bilt (the file holds it as a NaN) and writes null for a NaN: both are NaN here."""
    rows = _rows("10_minutes")
    assert all(math.isnan(value) for (_, name), value in rows.items() if name == "vv")
    assert len([1 for (_, name) in rows if name == "vv"]) == 18
    # and a null of the answer, which the real hourly answer holds for T10N and WW (not mapped), is the same
    document = json.loads(_answer("hourly"))
    document["coverages"][0]["ranges"]["T"]["values"][3] = None
    frames = parse_coverage_json(json.dumps(document).encode(), ["T"], Resolution.HOURLY)
    assert [math.isnan(value) for value in frames["06260"].get_column("value")][:5] == [
        False,
        False,
        False,
        True,
        False,
    ]
    # every requested parameter has a row at every time of the station, as every variable of a file has a cell
    assert {name for _, name in rows} == set(PARAMETERS[Resolution.MINUTE_10])


def test_the_stations_are_read_by_their_number() -> None:
    """The coverages hold the WIGOS identifier; the station is its tail, as everywhere in the provider."""
    frames = parse_coverage_json(_answer("daily"), PARAMETERS[Resolution.DAILY], Resolution.DAILY)
    assert set(frames) == {"06260", "06240"}


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b"<html>maintenance</html>", id="a page"),
        pytest.param(b"", id="nothing"),
        pytest.param(b"[]", id="a list"),
        pytest.param(b'{"type": "Feature"}', id="another document"),
        pytest.param(b'{"type": "CoverageCollection"}', id="no coverages"),
        pytest.param(
            b'{"type": "CoverageCollection", "coverages": [{"type": "Coverage"}]}', id="a coverage with no domain"
        ),
        pytest.param(
            b'{"type":"Coverage","eumetnet:locationId":"0-20000-0-06260","domain":{"axes":{"t":{"values":["2020-01-02"]}}},'
            b'"ranges":{}}',
            id="a time that is no stamp",
        ),
        pytest.param(
            b'{"type":"Coverage","eumetnet:locationId":"0-20000-0-06260","domain":{"axes":{"t":{"values":'
            b'["2020-01-02T00:00:00Z"]}}},"ranges":{"TG":{"values":[1.0,2.0]}}}',
            id="a range of another length than the times",
        ),
        pytest.param(
            b'{"type":"Coverage","eumetnet:locationId":"0-20000-0-06260","domain":{"axes":{"t":{"values":'
            b'["2020-01-02T00:00:00Z"]}}},"ranges":{"TG":{"values":["warm"]}}}',
            id="a value that is no number",
        ),
    ],
)
def test_an_answer_that_is_no_coverage_json_is_refused(payload: bytes) -> None:
    """A 200 that is not what was asked for (a page of the gateway, a changed API) is an `UnusableAnswerError`."""
    with pytest.raises(UnusableAnswerError):
        parse_coverage_json(payload, ["TG"], Resolution.DAILY)


def test_a_single_coverage_is_read_as_a_collection_of_one() -> None:
    """A `position` query answers one `Coverage`, not a collection of them."""
    document = json.loads(_answer("daily"))
    single = json.dumps(document["coverages"][0]).encode()
    assert set(parse_coverage_json(single, ["TG"], Resolution.DAILY)) == {"06260"}


@pytest.mark.parametrize("resolution", list(PARAMETERS))
def test_the_stamp_of_the_api_and_the_stamp_of_the_provider_are_each_others_inverse(resolution: Resolution) -> None:
    """The API stamps the end of an interval, the provider the start of a day, a month, a year."""
    stamp = _at(2020, 1, 1)
    assert edr.to_stamp(edr.to_edr_stamp(stamp, resolution), resolution) == stamp
    shifted = {Resolution.MINUTE_10: stamp, Resolution.HOURLY: stamp}.get(resolution)
    if shifted is not None:
        assert edr.to_edr_stamp(stamp, resolution) == stamp
    else:
        assert edr.to_edr_stamp(stamp, resolution) == advance(stamp, resolution)


@pytest.mark.parametrize(
    ("resolution", "start", "end"),
    [
        pytest.param(
            Resolution.MINUTE_10, _at(2026, 11, 9, 6, 5), _at(2026, 11, 9, 9, 0), id="10 minutes, an unaligned start"
        ),
        pytest.param(
            Resolution.MINUTE_10, _at(2026, 11, 12, 11, 0), _at(2026, 11, 13), id="10 minutes, into the future"
        ),
        pytest.param(Resolution.HOURLY, _at(2020, 1, 1, 0, 30), _at(2020, 1, 4, 12, 45), id="hourly, unaligned"),
        pytest.param(Resolution.HOURLY, _at(2026, 11, 10), _at(2026, 11, 20), id="hourly, into the future"),
        pytest.param(Resolution.DAILY, _at(2019, 12, 1), _at(2020, 2, 29, 17), id="daily, an unaligned end"),
        pytest.param(Resolution.DAILY, _at(2026, 10, 1), _at(2026, 12, 31), id="daily, into the future"),
        pytest.param(Resolution.MONTHLY, _at(2018, 5, 1), _at(2022, 12, 15), id="monthly"),
        pytest.param(
            Resolution.MONTHLY, _at(2025, 11, 20), _at(2027, 3, 1), id="monthly, an unaligned start, the future"
        ),
        pytest.param(Resolution.ANNUAL, _at(1960, 1, 1), _at(2030, 1, 1), id="annual, into the future"),
        pytest.param(Resolution.ANNUAL, _at(1960, 3, 1), _at(1999, 6, 1), id="annual, unaligned"),
    ],
)
def test_the_stamps_of_a_range_are_those_of_the_files_that_the_file_route_reads(
    monkeypatch: pytest.MonkeyPatch, resolution: Resolution, start: dt.datetime, end: dt.datetime
) -> None:
    """`stamp_bounds` and `count_stamps` agree with `_moments`, the files' route, on the stamps that are read."""
    monkeypatch.setattr(api, "_now", lambda: NOW)
    stamps = [api._stamp(moment, resolution) for moment in api._moments(start, end, resolution)]  # noqa: SLF001
    bounds = edr.stamp_bounds(start, end, resolution, NOW)
    if not stamps:
        assert bounds is None
        return
    assert bounds == (stamps[0], stamps[-1])
    assert edr.count_stamps(*bounds, resolution) == len(stamps)


def test_a_chunk_is_cut_in_two_at_the_middle_of_its_stamps() -> None:
    """A 413 is answered with the halves of the chunk."""
    chunk = Chunk(_at(2020, 1, 1), _at(2020, 1, 5))
    first, second = chunk.halves(Resolution.DAILY)
    assert (first.first, first.last, second.first, second.last) == (
        _at(2020, 1, 1),
        _at(2020, 1, 2),
        _at(2020, 1, 3),
        _at(2020, 1, 5),
    )
    assert Chunk(_at(2020, 1, 1), _at(2020, 1, 1)).halves(Resolution.DAILY) is None
    months = Chunk(_at(2020, 1, 1), _at(2020, 3, 1)).halves(Resolution.MONTHLY)
    assert [(c.first, c.last) for c in months] == [
        (_at(2020, 1, 1), _at(2020, 1, 1)),
        (_at(2020, 2, 1), _at(2020, 3, 1)),
    ]


@pytest.mark.parametrize(
    ("wsi", "valid"),
    [
        ("0-20000-0-06260", True),
        ("0-528-0-06233", True),
        ("0-20000-0-78990", True),
        ("0-20000-0-06260,0-20000-0-06240", False),
        ("0-20000-0-06260&x=1", False),
        ("../0-20000-0-06260", False),
        ("", False),
        (None, False),
    ],
)
def test_only_a_wigos_identifier_goes_into_a_url(wsi: object, *, valid: bool) -> None:
    """The identifiers come from a file of the catalogue: one that holds a `,` or a `&` is not put into a request."""
    assert edr.is_wsi(wsi) is valid


def test_the_url_of_a_request_is_its_cache_key_and_holds_the_chunk_and_no_key() -> None:
    """The URL names the collection, the stations, the stamps of the API and the parameters; it is the key."""
    url = edr.request_url(
        "daily-in-situ-meteorological-observations-validated",
        ["0-20000-0-06260", "0-20000-0-06240"],
        ["TG", "RH"],
        Chunk(_at(2020, 1, 1), _at(2020, 12, 31)),
        Resolution.DAILY,
    )
    assert url == (
        f"{edr.EDR_BASE_URL}/collections/daily-in-situ-meteorological-observations-validated/locations/"
        "0-20000-0-06260,0-20000-0-06240?datetime=2020-01-02T00:00:00Z/2021-01-01T00:00:00Z&parameter-name=TG,RH"
    )
