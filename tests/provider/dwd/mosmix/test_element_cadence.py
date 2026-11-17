# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The windows and the steps of the MOSMIX elements, held to two runs of DWD's files (GH-4176).

`docs/_ext/mosmix_cadence.py` is the table behind `docs/data/provider/dwd/mosmix/elements/index.md`: for each element its
window, the UTC hours at which its steps fall and its first and last step. It was measured on 2026-11-17 (MOSMIX-L of
four stations, MOSMIX-S of all 5,648), and these tests hold it to the part of those runs kept beside this file:

- `MOSMIX_L_2026111703_2_stations.kmz`: the run of 2026-11-17 03 UTC of MOSMIX-L for `10382` (Berlin-Tegel) and `10961`
  (Zugspitze), the two placemarks as DWD wrote them, in one file (32 KB).
- `MOSMIX_S_2026111703_240_6_stations.kmz`: the run of 03 UTC of MOSMIX-S, the placemarks of `10382`, `10961`, `01025`
  and of `08515`, `22820` and `16325`, which lack the last 3 or 9 hours of `RR1c`, and one of them a block of a day
  (36 MB for the 5,648 stations, so 37 KB for six).

Neither is a stub in the sense of invented rows: what a test reads is what DWD gave.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import re
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

import pytest

from tests.provider.value_stubs import _settings, stations_result
from wetterdienst import Options
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, api
from wetterdienst.provider.dwd.mosmix.metadata import DwdMosmixMetadata

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.model.result import ValuesResult

UTC = dt.UTC

_EXT = Path(__file__).resolve().parents[4] / "docs" / "_ext" / "mosmix_cadence.py"
_SPEC = importlib.util.spec_from_file_location("mosmix_cadence", _EXT)
assert _SPEC is not None
assert _SPEC.loader is not None
mosmix_cadence = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = mosmix_cadence  # a NamedTuple looks its module up
_SPEC.loader.exec_module(mosmix_cadence)

L_RUN = Path(__file__).with_name("MOSMIX_L_2026111703_2_stations.kmz")
S_RUN = Path(__file__).with_name("MOSMIX_S_2026111703_240_6_stations.kmz")
ISSUE = dt.datetime(2026, 11, 17, 3, tzinfo=UTC)

_NS = {
    "kml": "http://www.opengis.net/kml/2.2",
    "dwd": "https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd",
}

#: station -> element -> the (hours after the issue, value as the file writes it) of every step of the run
Run = dict[str, dict[str, list[tuple[int, str]]]]


def _read(path: Path) -> Run:
    """Read a run as DWD wrote it: every step of every element of every station, `-` kept as it is."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read(archive.namelist()[0]))  # noqa: S314 - DWD's file, kept in the repo
    steps = [
        int(
            (
                dt.datetime.strptime(step.text.strip(), "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC) - ISSUE
            ).total_seconds()
            // 3600
        )
        for step in root.iterfind(".//dwd:TimeStep", _NS)
    ]
    run: Run = {}
    for placemark in root.iterfind(".//kml:Placemark", _NS):
        station = placemark.findtext("kml:name", namespaces=_NS)
        elements = {}
        for forecast in placemark.iterfind(".//dwd:Forecast", _NS):
            values = forecast.findtext("dwd:value", namespaces=_NS).split()
            assert len(values) == len(steps)
            elements[forecast.get(f"{{{_NS['dwd']}}}elementName")] = list(zip(steps, values, strict=True))
        run[station] = elements
    return run


@pytest.fixture(scope="module")
def large() -> Run:
    """MOSMIX-L, run of 2026-11-17 03 UTC: `10382` and `10961`."""
    return _read(L_RUN)


@pytest.fixture(scope="module")
def small() -> Run:
    """MOSMIX-S, run of 2026-11-17 03 UTC: six stations."""
    return _read(S_RUN)


def _given(steps: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return [(step, value) for step, value in steps if value != "-"]


def _hours(steps: list[tuple[int, str]]) -> set[int]:
    """Give the UTC clock hours of the steps."""
    return {(ISSUE.hour + step) % 24 for step, _ in steps}


def _numbers(steps: list[tuple[int, str]]) -> list[tuple[int, float]]:
    return [(step, float(value)) for step, value in _given(steps)]


# --- the table against the metadata --------------------------------------------------------------------------------


def test_the_table_has_the_elements_of_large_and_those_of_small_have_a_range() -> None:
    """Each of the 114 elements of MOSMIX-L is in the table, once; MOSMIX-S has a range for the 40 it carries."""
    large = {parameter.name_original for parameter in DwdMosmixMetadata.hourly.large.parameters}
    small = {parameter.name_original for parameter in DwdMosmixMetadata.hourly.small.parameters}

    table = mosmix_cadence.ELEMENTS
    assert {element.lower() for element in table} == large
    assert len(table) == len(large) == 114
    assert {element.lower() for element, cadence in table.items() if cadence.s_range is not None} == small
    assert len(small) == 40


def test_the_window_of_a_parameter_that_names_one_is_the_window_of_the_table() -> None:
    """`..._last_6h` is the 6 hours of `W1W2`'s neighbours: the name and the table say the same window."""
    named = {}
    for dataset in (DwdMosmixMetadata.hourly.large, DwdMosmixMetadata.hourly.small):
        for parameter in dataset.parameters:
            match = re.search(r"_last_(\d+)h$", parameter.name)
            if match:
                named[parameter.name_original] = int(match.group(1))

    by_lower = {element.lower(): cadence for element, cadence in mosmix_cadence.ELEMENTS.items()}
    assert len(named) > 20
    wrong = {name: (hours, by_lower[name].window) for name, hours in named.items() if by_lower[name].window != hours}
    assert not wrong


def test_the_table_is_ordered_by_window_and_every_range_lies_in_the_run() -> None:
    """The directive prints the rows in the order of the table: by window, and no step is past the run's end."""
    rows = list(mosmix_cadence.ELEMENTS.values())

    windows = [row.window or 0 for row in rows]
    assert windows == sorted(windows)
    for row in rows:
        assert 1 <= row.l_range[0] <= row.l_range[1] <= mosmix_cadence.HORIZON["L"]
        if row.s_range is not None:
            assert 1 <= row.s_range[0] <= row.s_range[1] <= mosmix_cadence.HORIZON["S"]


def _given_at(description: str) -> tuple[int, ...] | None:
    """Read the UTC hours a description says an element is given at: `given at the 06 and 18 UTC steps`."""
    match = re.search(r"[Gg]iven at (?:the )?([\d, .and]+?) UTC", description)
    if match is None:
        return None
    numbers = [int(number) for number in re.findall(r"\d+", match.group(1))]
    if "..." in match.group(1):
        return tuple(range(numbers[0], numbers[-1] + 1, numbers[1] - numbers[0]))
    return tuple(numbers)


def test_the_hours_a_description_gives_are_the_hours_of_the_table() -> None:
    """A parameter that says "given at 06 and 18 UTC" is given at the hours the table says, in both products."""
    by_lower = {element.lower(): cadence for element, cadence in mosmix_cadence.ELEMENTS.items()}
    checked = []
    wrong = {}
    for dataset in (DwdMosmixMetadata.hourly.large, DwdMosmixMetadata.hourly.small):
        for parameter in dataset.parameters:
            said = _given_at(parameter.description or "")
            if said is None:
                continue
            checked.append(parameter.name_original)
            if said != by_lower[parameter.name_original].hours:
                wrong[f"{dataset.name}/{parameter.name_original}"] = (said, by_lower[parameter.name_original].hours)

    assert not wrong
    # the elements whose steps are not all hours say so, among them the ones this page is about
    assert {"rr3c", "rr6c", "rrhc", "rrdc", "tx", "tn", "tm", "w1w2", "wpcd1", "wwmd"} <= set(checked)


def test_the_zero_tail_is_in_the_description_of_the_elements_the_table_names_it_for() -> None:
    """`RR1c` and `RR3c` say they are real zeros late in the run, in both products, as the table and the page do."""
    named = {element.lower() for element, cadence in mosmix_cadence.ELEMENTS.items() if "0.0" in cadence.note}
    assert named == {"rr1c", "rr3c"}
    for dataset in (DwdMosmixMetadata.hourly.large, DwdMosmixMetadata.hourly.small):
        for parameter in dataset.parameters:
            if parameter.name_original in named:
                assert "real zeros, not missing values" in parameter.description
                assert "+100 to +125 h" in parameter.description


def test_the_description_of_the_duration_of_precipitation_says_which_station_skip_empty_drops() -> None:
    """`DRR1` is given at no step at the Zugspitze, so `skip_empty` drops it: the parameter says so (MOSMIX-L only)."""
    parameter = next(p for p in DwdMosmixMetadata.hourly.large.parameters if p.name_original == "drr1")

    assert "10961" in parameter.description
    assert "skip_empty" in parameter.description
    assert "drr1" not in {p.name_original for p in DwdMosmixMetadata.hourly.small.parameters}


# --- the table against the files -----------------------------------------------------------------------------------


def test_the_steps_of_mosmix_l_fall_at_the_hours_of_the_table(large: Run) -> None:
    """Every element is given at the hours it says: all of them, for one that is not `subset`, and no others."""
    assert sorted(large) == ["10382", "10961"]
    problems = []
    for station, elements in large.items():
        assert {element for element, steps in elements.items() if _given(steps)} <= set(mosmix_cadence.ELEMENTS)
        for element, steps in elements.items():
            given = _given(steps)
            if not given:
                continue
            cadence = mosmix_cadence.ELEMENTS[element]
            seen = _hours(given)
            allowed = set(cadence.hours) | set(cadence.extra)
            if not seen <= allowed:
                problems.append(f"{station} {element}: {sorted(seen)} outside {sorted(allowed)}")
            if not cadence.subset and not set(cadence.hours) <= seen:
                problems.append(f"{station} {element}: {sorted(seen)} lacks {sorted(set(cadence.hours) - seen)}")
    assert not problems, "\n".join(problems)


def test_no_element_of_mosmix_l_ends_before_its_range_does(large: Run) -> None:
    """The first and the last step of an element at a station are the table's, and none is past +247 h.

    No precipitation element stops early: `RR1c` and `RR3c` reach their last step too, though they are 0.0 by then.
    """
    problems = []
    for station, elements in large.items():
        for element, steps in elements.items():
            given = _given(steps)
            if not given:
                continue
            cadence = mosmix_cadence.ELEMENTS[element]
            first, last = given[0][0], given[-1][0]
            assert last <= mosmix_cadence.HORIZON["L"]
            if cadence.subset:
                continue
            # the table is the widest range of the four stations measured, and these are two of them
            if first != cadence.l_range[0]:
                problems.append(f"{station} {element}: first {first}, table {cadence.l_range}")
            # `Rd*` is given at 07 UTC as well at some stations, one step later
            if last not in {cadence.l_range[1], cadence.l_range[1] - 1}:
                problems.append(f"{station} {element}: last {last}, table {cadence.l_range}")
    assert not problems, "\n".join(problems)


def test_the_precipitation_elements_of_mosmix_l_reach_the_end_of_the_run(large: Run) -> None:
    """The last step of every precipitation element is the last of its window: +247, +246 or +243 h at 03 UTC."""
    for element, last in {
        "RR1c": 247,
        "RR3c": 246,
        "RR6c": 243,
        "RRhc": 243,
        "RRdc": 243,
        "R101": 247,
        "R602": 243,
    }.items():
        for station in ("10382", "10961"):
            assert _given(large[station][element])[-1][0] == last, (station, element)


def test_rr1c_and_rr3c_are_zero_late_in_the_run_and_the_totals_still_carry_rain(large: Run) -> None:
    """At 10382 the hourly amounts are 0.0 from +112 h, while `RR6c`, `RRhc`, `RRdc` and `R101` carry rain to the end.

    The zeros are values the file writes (`0.0`), not the `-` of a step that is missing.
    """
    steps = large["10382"]
    # the last non-zero step of each element (the table of the page: +111, +123, +231, +243, +243, +247)
    last_nonzero = {
        element: max((step for step, value in _numbers(steps[element]) if value > 0), default=None)
        for element in ("RR1c", "RR3c", "RR6c", "RRhc", "RRdc", "R101")
    }
    assert last_nonzero == {"RR1c": 111, "RR3c": 123, "RR6c": 231, "RRhc": 243, "RRdc": 243, "R101": 247}

    for element in ("RR1c", "RR3c"):
        late = [(step, value) for step, value in _given(steps[element]) if step > 125]
        assert len(late) > 30
        # written `0.00` for `RR1c` and `0.0` for others, never `-`
        assert {float(value) for _, value in late} == {0.0}, element


def test_days_six_to_ten_look_dry_in_rr1c_where_rrdc_has_rain(large: Run) -> None:
    """The 24 h windows of 06 UTC from the 6th day on: `RRdc` has 0.5 mm and more, the 24 hourly amounts sum to 0."""
    steps = large["10382"]
    hourly = dict(_numbers(steps["RR1c"]))
    daily = {step: value for step, value in _numbers(steps["RRdc"]) if step >= 123}

    dry_with_rain = []
    for end, rain in daily.items():
        window = [hourly[step] for step in range(end - 23, end + 1) if step in hourly]
        assert len(window) == 24
        if rain >= 0.5 and sum(window) < 0.1:
            dry_with_rain.append((end, rain))

    assert len(dry_with_rain) >= 3, daily
    # and the 6 and 12 h totals of the same days see it
    assert all(
        sum(value for step, value in _numbers(steps["RRhc"]) if end - 12 < step <= end) > 0 for end, _ in dry_with_rain
    )


def test_the_zugspitze_has_rr1c_to_the_end_of_the_run(large: Run) -> None:
    """The mountain station is the exception the page names: its hourly amounts carry rain to +241 h."""
    last_nonzero = max(step for step, value in _numbers(large["10961"]["RR1c"]) if value > 0)

    assert last_nonzero == 241


def test_drr1_is_zero_for_most_rainy_hours_at_10382_and_not_given_at_10961(large: Run) -> None:
    """At Berlin-Tegel the duration is 0 s at all 247 hours of this run though 75 of the hourly amounts are above 0.

    The run of 09 UTC of the 16th had 10 hours above 0 there; `-` at every step at 10961.
    """
    duration = [value for _, value in _numbers(large["10382"]["DRR1"])]
    rain = [value for _, value in _numbers(large["10382"]["RR1c"])]

    assert len(duration) == 247
    assert sum(value > 0 for value in duration) == 0
    assert sum(value > 0 for value in rain) == 75
    assert _given(large["10961"]["DRR1"]) == []
    assert len(large["10961"]["DRR1"]) == 247


def test_the_steps_of_mosmix_s_fall_at_the_hours_of_the_table(small: Run) -> None:
    """MOSMIX-S gives an element at the table's hours (06 and 18 UTC for `TX`) or, for some stations, at others."""
    problems = []
    for station, elements in small.items():
        for element, steps in elements.items():
            given = _given(steps)
            if not given:
                continue
            cadence = mosmix_cadence.ELEMENTS[element]
            assert cadence.s_range is not None, element
            assert given[-1][0] <= mosmix_cadence.HORIZON["S"]
            seen = _hours(given)
            allowed = set(cadence.hours) | set(cadence.extra)
            # `Rd02` and `Rd50` are hourly at about 600 stations, which the note of the table gives
            if element in {"Rd02", "Rd50"}:
                continue
            if not seen <= allowed:
                problems.append(f"{station} {element}: {sorted(seen)} outside {sorted(allowed)}")
    assert not problems, "\n".join(problems)


def _missing_rr1c(steps: list[tuple[int, str]]) -> list[int]:
    return [step for step, value in steps if value == "-"]


def test_some_stations_of_mosmix_s_lack_the_last_hours_of_rr1c_and_some_a_block_of_a_day(small: Run) -> None:
    """The stub has two complete stations, one without the last 3 h, one without 3 h and a block, one without 9 h."""
    assert _missing_rr1c(small["10382"]["RR1c"]) == []
    assert _missing_rr1c(small["01025"]["RR1c"]) == []
    assert _missing_rr1c(small["16325"]["RR1c"]) == [238, 239, 240]
    assert _missing_rr1c(small["08515"]["RR1c"]) == [22, 23, 24, 238, 239, 240]
    assert _missing_rr1c(small["22820"]["RR1c"]) == [*range(16, 25), *range(232, 241)]
    # a hole is a `-`, no rain: the station that lacks the hours has no 0.0 in their place
    assert {value for step, value in small["16325"]["RR1c"] if step in {238, 239, 240}} == {"-"}


def test_mosmix_s_has_no_precipitation_total_of_6_12_or_24_hours(small: Run) -> None:
    """MOSMIX-S has `RR1c` and `RR3c`, the probabilities and no `RR6c`, `RRhc` or `RRdc`: late days have no totals."""
    elements = {element for station in small.values() for element in station}

    assert {"RR1c", "RR3c", "R602", "Rd02", "Rh00"} <= elements
    assert not elements & {"RR6c", "RRhc", "RRdc", "DRR1"}


# --- what the provider makes of it ---------------------------------------------------------------------------------


@pytest.fixture
def serve_large(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the run of MOSMIX-L from the file beside this one, and name it for every request."""
    url = "https://example.invalid/MOSMIX_L_2026111703_stub.kmz"
    monkeypatch.setattr(api.KMLReader, "download", lambda _self, _url: BytesIO(L_RUN.read_bytes()))
    monkeypatch.setattr(api.DwdMosmixValues, "get_url_for_date", lambda *_args, **_kwargs: url)


def _values(station_id: str, parameter: str, *, skip_empty: bool) -> Iterator[ValuesResult]:
    request = DwdMosmixRequest(
        parameters=[("hourly", "large", parameter)],
        settings=_settings(),
        options=Options(skip_empty=skip_empty, skip_threshold=0.95),
    )
    return stations_result(request, "hourly", "large", station_id).values().query()


@pytest.mark.parametrize(
    ("station_id", "frames"),
    [
        pytest.param("10382", 1, id="berlin-tegel"),
        pytest.param("10961", 0, id="zugspitze"),
    ],
)
def test_skip_empty_drops_the_station_that_has_no_drr1(
    serve_large: None,  # noqa: ARG001
    station_id: str,
    frames: int,
) -> None:
    """`DRR1` is given at no step at 10961: `skip_empty=True` drops the station; Berlin-Tegel's zeros are kept."""
    assert len(list(_values(station_id, "precipitation_duration", skip_empty=True))) == frames


def test_skip_empty_keeps_the_zugspitze_for_a_parameter_it_has(serve_large: None) -> None:  # noqa: ARG001
    """The same station is kept for `RR1c`, which it has at every step: the drop is the element's, not the station's."""
    results = list(_values("10961", "precipitation_amount_significant_weather_last_1h", skip_empty=True))

    assert len(results) == 1
