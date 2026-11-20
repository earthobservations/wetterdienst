# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the climate stripes of NOAA GHCN daily, whose years are built from its days (GH-4222).

Every test reads the stub files of `ghcn_stripes_stub`, through the library, the REST API, the command line and MCP.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
from typing import TYPE_CHECKING, Any, Literal

import polars as pl
import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from tests.ui import ghcn_stripes_stub as stub
from wetterdienst.exceptions import NotEnoughDataError, StationNotFoundError
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest
from wetterdienst.ui import core, restapi
from wetterdienst.ui.cli import cli
from wetterdienst.ui.core import (
    StripesImageRequest,
    StripesStationsRequest,
    StripesValuesRequest,
    _get_stripes_data,
    _get_stripes_stations,
)
from wetterdienst.util.response_warnings import _COUNTED, _RECORDED

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi.testclient import TestClient

GHCN = {"provider": "noaa", "network": "ghcn"}
TEMPERATURE = {"kind": "temperature", **GHCN, "station": stub.STATION}
PRECIPITATION = {"kind": "precipitation", **GHCN, "station": stub.STATION}


@pytest.fixture(autouse=True)
def _serve_the_stub_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the settings of whoever runs the tests out, and have the provider read the stub's files."""
    _RECORDED.set(None)
    _COUNTED.set(None)
    for name in list(os.environ):
        if name.upper().startswith("WD_") and name.upper() != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    stub.serve_ghcn(monkeypatch)


@pytest.fixture
def client() -> TestClient:
    """Make a client of the app."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    return TestClient(restapi.app)


def _years(data: core.StripesData) -> dict[int, float | None]:
    return dict(
        zip(data.df.get_column("timestamp").dt.year().to_list(), data.df.get_column("value").to_list(), strict=True)
    )


# --- the library ------------------------------------------------------------------------------


def test_the_temperature_years_are_built_from_the_days_by_the_rules() -> None:
    """Test each year is the mean of its months, a year a rule fails is a gap, and a partial TAVG makes no step."""
    data = _get_stripes_data(StripesValuesRequest(**TEMPERATURE))

    years = _years(data)
    assert list(years) == list(range(stub.FIRST_YEAR, stub.LAST_YEAR + 1))
    # 11 days missing in a month, and 5 in a row: no year
    assert years[2000] is None
    assert years[2005] is None
    # 10 missing days, never more than 4 in a row, is a month that counts
    assert years[2010] == pytest.approx(stub.mean_temperature(2010), abs=1e-3)
    # the one year that has a TAVG, 1 degree under the midrange, is the midrange like the others: no step
    assert years[stub.TAVG_YEAR] == pytest.approx(15.0, abs=1e-3)
    assert years[stub.TAVG_YEAR] == pytest.approx(stub.mean_temperature(stub.TAVG_YEAR), abs=1e-3)
    assert all(
        years[year] == pytest.approx(stub.mean_temperature(year), abs=1e-3) for year in years if years[year] is not None
    )
    assert years[1990] == pytest.approx(10.0)
    assert years[1999] == pytest.approx(11.8, abs=1e-3)
    gaps = {year for year, value in years.items() if value is None}
    assert gaps == {2000, 2005}


def test_the_precipitation_years_are_the_sums_and_a_missing_day_makes_a_gap() -> None:
    """Test a year is the sum of its months, and any missing day fails its month, so 2010 fails as well."""
    data = _get_stripes_data(StripesValuesRequest(**PRECIPITATION))

    years = _years(data)
    assert {year for year, value in years.items() if value is None} == {2000, 2005, 2010}
    # 1 and 3 mm on alternate days: 2 mm a day, with the day a year has one more of in either direction
    assert years[1991] == pytest.approx(stub.rain_of(1991))
    assert years[1992] == pytest.approx(stub.rain_of(1992))
    assert 728 <= years[1991] <= 732


def test_the_rest_is_as_for_dwd_the_reference_its_fallback_and_the_classes() -> None:
    """Test the scale is Hawkins' on the years that have a value, and falls back to the whole record as DWD's does."""
    data = _get_stripes_data(StripesValuesRequest(**TEMPERATURE))

    values = [v for v in _years(data).values() if v is not None]
    # 1990-2020 has 10 years with a value in 1971-2000 (of the 20 needed for the mean) and in 1901-2000 (of the 30 for
    # the spread): both fall back to the whole record, the 29 years that have one
    reference = data.reference
    assert len(values) == 29
    for stat in (reference.centre, reference.spread):
        assert stat.fallback
        assert (stat.first_year, stat.last_year, stat.years) == (1990, 2020, 29)
    assert reference.centre.value == pytest.approx(sum(values) / len(values))
    classes = data.df.get_column("stripe_class").to_list()
    # a gap has no class, and the warmest year has the highest
    gap_years = data.df.filter(pl.col("value").is_null()).get_column("stripe_class").to_list()
    assert gap_years == [None, None]
    assert max(c for c in classes if c is not None) == classes[-1]
    assert data.df.get_column("anomaly").to_list()[0] == pytest.approx(10.0 - reference.centre.value, abs=1e-3)


def test_the_series_names_the_daily_parameter_the_years_are_built_from() -> None:
    """Test the series says whose and what the values are, with the unit of the kind."""
    temperature = _get_stripes_data(StripesValuesRequest(**TEMPERATURE)).series
    assert (temperature.resolution, temperature.dataset) == ("daily", "data")
    assert (temperature.parameter, temperature.unit) == ("temperature_air_mean_2m", "degree_celsius")
    assert temperature.station["station_id"] == stub.STATION
    precipitation = _get_stripes_data(StripesValuesRequest(**PRECIPITATION)).series
    assert (precipitation.parameter, precipitation.unit) == ("precipitation_amount", "millimeter")


def test_the_unit_targets_set_the_unit_of_the_years() -> None:
    """Test a year is in the unit asked for, and its class is the same in any unit."""
    celsius = _get_stripes_data(StripesValuesRequest(**TEMPERATURE))
    fahrenheit = _get_stripes_data(
        StripesValuesRequest(**TEMPERATURE, unit_targets={"temperature": "degree_fahrenheit"})
    )

    assert fahrenheit.series.unit == "degree_fahrenheit"
    assert _years(fahrenheit)[1990] == pytest.approx(50.0, abs=1e-2)
    assert _years(fahrenheit)[2000] is None
    assert fahrenheit.df.get_column("stripe_class").to_list() == celsius.df.get_column("stripe_class").to_list()


def test_a_value_that_failed_a_check_of_the_source_is_a_missing_day(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test 11 days of TMAX that NOAA's quality checks flagged fail their month, as 11 missing days do."""
    flagged = [dt.date(1995, 3, day) for day in range(1, 22, 2)]
    stub.serve_ghcn(monkeypatch, failed=flagged)

    years = _years(_get_stripes_data(StripesValuesRequest(**TEMPERATURE)))

    assert years[1995] is None
    assert years[1994] is not None
    # and its precipitation, flagged on the same days
    assert _years(_get_stripes_data(StripesValuesRequest(**PRECIPITATION)))[1995] is None


def test_a_station_without_tavg_has_its_years_and_no_warning_of_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a station with no TAVG, as most have none, is read from TMAX and TMIN without a `parameter-without-rows`."""
    from wetterdienst.util.response_warnings import begin_response, recorded_warnings  # noqa: PLC0415

    stub.serve_ghcn(monkeypatch, tavg=False)
    begin_response()

    years = _years(_get_stripes_data(StripesValuesRequest(**TEMPERATURE)))

    assert years[stub.TAVG_YEAR] == pytest.approx(15.0, abs=1e-3)
    assert recorded_warnings() == []


def test_a_station_with_only_tavg_has_its_years_from_the_tavg_and_names_it() -> None:
    """Test TAVG makes the days at a station with no TMAX and TMIN, with no warning of the two it has none of."""
    from wetterdienst.util.response_warnings import begin_response, recorded_warnings  # noqa: PLC0415

    begin_response()

    data = _get_stripes_data(StripesValuesRequest(**{**TEMPERATURE, "station": stub.TAVG_ONLY_STATION}))

    years = _years(data)
    assert data.series.method == "tavg"
    # the TAVG swings around the midrange of the stub, a tenth of a degree at most over a month
    assert years[1990] == pytest.approx(10.0, abs=0.1)
    assert years[1999] == pytest.approx(11.8, abs=0.1)
    assert {year for year, value in years.items() if value is None} == {2000, 2005}
    assert recorded_warnings() == []


def test_a_station_with_tmax_and_tmin_names_the_midrange() -> None:
    """Test the series says which method made its days, for the note of the answer."""
    assert _get_stripes_data(StripesValuesRequest(**TEMPERATURE)).series.method == "midrange"
    assert _get_stripes_data(StripesValuesRequest(**PRECIPITATION)).series.method is None


def test_the_environment_cannot_turn_the_names_of_the_parameters_into_the_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test `WD_TS_HUMANIZE=false`, which names the parameters as the source does, leaves the years as they are."""
    monkeypatch.setenv("WD_TS_HUMANIZE", "false")

    temperature = _get_stripes_data(StripesValuesRequest(**TEMPERATURE))
    precipitation = _get_stripes_data(StripesValuesRequest(**PRECIPITATION))

    assert _years(temperature)[1999] == pytest.approx(11.8, abs=1e-3)
    assert _years(precipitation)[1991] == pytest.approx(stub.rain_of(1991))
    assert temperature.series.parameter == "temperature_air_mean_2m"


def test_a_station_by_name() -> None:
    """Test the station is found by its name, fuzzily, as for DWD."""
    data = _get_stripes_data(StripesValuesRequest(kind="temperature", **GHCN, name="Stub Station"))
    assert data.series.station["station_id"] == stub.STATION


def test_a_window_of_years_keeps_the_classes_of_the_whole_record() -> None:
    """Test `start_year` and `end_year` cut the years that are shown, not the record the colours are relative to."""
    whole = _get_stripes_data(StripesValuesRequest(**TEMPERATURE))
    window = _get_stripes_data(StripesValuesRequest(**TEMPERATURE, start_year=2011, end_year=2014))

    assert list(_years(window)) == [2011, 2012, 2013, 2014]
    assert window.reference == whole.reference
    shown = whole.df.filter(pl.col("timestamp").dt.year().is_between(2011, 2014))
    assert window.df.get_column("stripe_class").to_list() == shown.get_column("stripe_class").to_list()


def test_an_unknown_station_is_not_found() -> None:
    """Test an id that is not in the list is the `StationNotFoundError` of DWD's."""
    with pytest.raises(StationNotFoundError, match="No station with a station_id similar to 'USW99999999' found"):
        _get_stripes_data(StripesValuesRequest(kind="temperature", **GHCN, station="USW99999999"))


def test_a_record_of_fewer_valid_years_than_the_minimum_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test 9 years with a value are too few to scale, as for DWD, however many days they are made of."""
    from tests.provider.value_stubs import serve  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn import api  # noqa: PLC0415

    serve(
        monkeypatch,
        api,
        {
            "ghcnd-stations": stub.stations_text().encode("utf8"),
            "ghcnd-inventory": stub.inventory_text().encode("utf8"),
            "by_station/USW00000009": stub.station_csv("USW00000009", last_year=1998),
        },
    )
    with pytest.raises(NotEnoughDataError, match=r"At least 10 years with data are required to scale climate stripes"):
        _get_stripes_data(StripesValuesRequest(kind="temperature", **GHCN, station="USW00000009"))


# --- the stations the stripes are made for ----------------------------------------------------


def _ids(kind: Literal["temperature", "precipitation"], **kwargs: Any) -> set[str]:  # noqa: ANN401
    return set(_get_stripes_stations(kind=kind, **GHCN, **kwargs).df.get_column("station_id").to_list())


@pytest.mark.parametrize(
    ("kind", "active", "expected"),
    [
        # TAVG alone (0002), TMAX with TMIN (0001, 0008); 0003's TMAX and TMIN overlap for 9 years, 0004 has TMAX only
        pytest.param("temperature", False, {"USW00000001", "USW00000002", "USW00000008"}, id="temperature"),
        # still reporting: a record that reaches into this or the last year
        pytest.param("temperature", True, {"USW00000002", "USW00000008"}, id="temperature-active"),
        pytest.param("precipitation", False, {"USW00000001", "USW00000005", "USW00000006"}, id="precipitation"),
        pytest.param("precipitation", True, {"USW00000006"}, id="precipitation-active"),
    ],
)
def test_the_stations_are_those_whose_record_can_reach_the_minimum_years(
    kind: Literal["temperature", "precipitation"],
    active: bool,  # noqa: FBT001
    expected: set[str],
) -> None:
    """Test the span of the elements the kind is made from decides, not that of any element the station has."""
    assert _ids(kind, active=active) == expected


def _years_of_the_generic_list(parameter: str) -> pl.DataFrame:
    """Give the years of `/api/stations` for one GHCN daily parameter, an empty end being this year."""
    this_year = dt.datetime.now(dt.UTC).year
    df = NoaaGhcnRequest(parameters=[("daily", "data", parameter)]).all().df
    return df.select(
        "station_id",
        pl.col("start_timestamp").dt.year().alias("first_year"),
        pl.col("end_timestamp").dt.year().fill_null(this_year).alias("last_year"),
    )


def _rebuilt_as_the_app_does(kind: str, *, active: bool) -> pl.DataFrame:
    """Rebuild the stripes' list of `kind` from the generic lists, as the app does.

    The precipitation is one request; the temperature is three (TAVG, TMAX, TMIN) combined as TAVG or the years TMAX
    and TMIN have in common. Then the rule on the span.
    """
    this_year = dt.datetime.now(dt.UTC).year
    if kind == "precipitation":
        record = _years_of_the_generic_list("precipitation_amount")
    else:
        mean = _years_of_the_generic_list("temperature_air_mean_2m")
        both = _years_of_the_generic_list("temperature_air_max_2m").join(
            _years_of_the_generic_list("temperature_air_min_2m"), on="station_id", suffix="_min"
        )
        # the years TMAX and TMIN have in common, empty where they do not meet
        both = both.select(
            "station_id",
            pl.max_horizontal("first_year", "first_year_min").alias("first_year"),
            pl.min_horizontal("last_year", "last_year_min").alias("last_year"),
        ).filter(pl.col("first_year") <= pl.col("last_year"))
        record = (
            pl.concat([mean, both]).group_by("station_id").agg(pl.col("first_year").min(), pl.col("last_year").max())
        )
    keep = pl.col("last_year") - pl.col("first_year") + 1 >= core.MIN_RECORD_YEARS
    if active:
        keep &= pl.col("last_year") >= this_year - 1
    return record.filter(keep)


@pytest.mark.parametrize("active", [True, False])
@pytest.mark.parametrize("kind", ["temperature", "precipitation"])
def test_the_generic_lists_with_the_apps_rule_are_the_stripes_list(
    kind: Literal["temperature", "precipitation"],
    active: bool,  # noqa: FBT001
) -> None:
    """Test `/api/stations` for one measurement each, combined and ruled as the app does, is the stripes' list.

    The precipitation is the list of `precipitation_amount`. The temperature is those of `temperature_air_mean_2m`
    (TAVG), `temperature_air_max_2m` (TMAX) and `temperature_air_min_2m` (TMIN): a station's span is TAVG's, or the
    years TMAX and TMIN have in common where it has both and they meet, or from the earliest start to the latest end
    of the two. Then a record of `MIN_RECORD_YEARS` or more years (an empty end is this year) that, for an active
    station, reaches into this year or the last. The same ids, with the same start and end.
    """
    this_year = dt.datetime.now(dt.UTC).year
    rebuilt = _rebuilt_as_the_app_does(kind, active=active).sort("station_id")
    stripes = core._get_stripes_ghcn_stations(kind, active=active).df.select(  # noqa: SLF001
        "station_id",
        pl.col("start_timestamp").dt.year().alias("first_year"),
        pl.col("end_timestamp").dt.year().fill_null(this_year).alias("last_year"),
    )
    assert stripes.height > 0
    assert rebuilt.equals(stripes.sort("station_id"))


def test_the_listing_gives_the_span_of_the_kind_and_no_end_for_a_station_that_still_reports() -> None:
    """Test `start_timestamp` and `end_timestamp` are the first and the last year of the elements of the kind."""
    rows = {
        row["station_id"]: row
        for row in _get_stripes_stations(kind="temperature", active=False, **GHCN).df.iter_rows(named=True)
    }

    one = rows[stub.STATION]
    assert one["start_timestamp"] == dt.datetime(1990, 1, 1, tzinfo=dt.UTC)
    assert one["end_timestamp"] == dt.datetime(2020, 12, 31, tzinfo=dt.UTC)
    assert one["name"] == "STUB STATION"
    # TAVG of 1950 to this year: its year has not ended
    assert rows["USW00000002"]["start_timestamp"] == dt.datetime(1950, 1, 1, tzinfo=dt.UTC)
    assert rows["USW00000002"]["end_timestamp"] is None


@pytest.mark.parametrize(
    ("box", "expected"),
    [
        pytest.param((-74.5, 40.0, -73.0, 41.5), {"USW00000001", "USW00000002"}, id="new-york"),
        pytest.param((-74.5, 40.0, -73.8, 41.5), {"USW00000001"}, id="narrower"),
        # borders are inside, as for `/api/stations`: the station is on the top border and the east one
        pytest.param((-74.5, 40.0, -73.5, 41.0), {"USW00000001", "USW00000002"}, id="borders"),
        pytest.param((-1.0, 51.0, 1.0, 52.0), {"USW00000008"}, id="london"),
        pytest.param((100.0, -10.0, 101.0, -9.0), set(), id="none-in-the-box"),
    ],
)
def test_a_bounding_box_keeps_the_stations_inside_it(
    box: tuple[float, float, float, float], expected: set[str]
) -> None:
    """Test the stations of GHCN come by box, which the map asks for instead of the whole list."""
    left, bottom, right, top = box
    assert _ids("temperature", active=False, left=left, bottom=bottom, right=right, top=top) == expected


def test_a_bounding_box_serves_the_stations_of_dwd_as_well(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the box is not GHCN's alone: DWD's listing takes it, and its default is the listing as it was."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    def station(station_id: str, latitude: float, longitude: float) -> dict[str, Any]:
        return {
            "resolution": "annual",
            "dataset": "climate_summary",
            "station_id": station_id,
            "start_timestamp": dt.datetime(1934, 1, 1, tzinfo=dt.UTC),
            "end_timestamp": dt.datetime(2025, 12, 31, tzinfo=dt.UTC),
            "latitude": latitude,
            "longitude": longitude,
            "elevation": 10.0,
            "name": station_id,
            "region": "Hamburg",
        }

    frame = pl.LazyFrame(
        [station("00001", 53.6, 10.0), station("00002", 48.1, 11.5), station("00003", 54.0, 9.9)],
        schema_overrides={"latitude": pl.Float64, "longitude": pl.Float64},
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: frame)

    everywhere = _get_stripes_stations(kind="temperature")
    boxed = _get_stripes_stations(kind="temperature", left=9.0, bottom=53.0, right=11.0, top=55.0)

    assert everywhere.df.get_column("station_id").to_list() == ["00001", "00002", "00003"]
    assert boxed.df.get_column("station_id").to_list() == ["00001", "00003"]


# --- the sources the stripes are made from ----------------------------------------------------


@pytest.mark.parametrize("model", [StripesStationsRequest, StripesValuesRequest, StripesImageRequest])
def test_the_source_defaults_to_dwd_observation(model: type) -> None:
    """Test a request that names no source is the stripes of DWD, as every call was before."""
    request = model(kind="temperature", **({} if model is StripesStationsRequest else {"station": "01048"}))
    assert (request.provider, request.network) == ("dwd", "observation")


@pytest.mark.parametrize("model", [StripesStationsRequest, StripesValuesRequest, StripesImageRequest])
def test_the_names_of_the_source_are_read_in_lower_case(model: type) -> None:
    """Test `NOAA` and `GHCN` are the pair `noaa` and `ghcn`, as the providers are everywhere."""
    request = model(
        kind="temperature",
        provider="NOAA",
        network=" GHCN ",
        **({} if model is StripesStationsRequest else {"station": "x"}),
    )
    assert (request.provider, request.network) == ("noaa", "ghcn")


@pytest.mark.parametrize(
    ("provider", "network"),
    [("noaa", "observation"), ("dwd", "ghcn"), ("dwd", "mosmix"), ("eccc", "observation"), ("nope", "nope")],
)
@pytest.mark.parametrize("model", [StripesStationsRequest, StripesValuesRequest, StripesImageRequest])
def test_any_other_pair_is_refused_and_the_sources_are_named(model: type, provider: str, network: str) -> None:
    """Test a pair that is not dwd/observation or noaa/ghcn is a validation error that says which are."""
    with pytest.raises(ValidationError) as error:
        model(
            kind="temperature",
            provider=provider,
            network=network,
            **({} if model is StripesStationsRequest else {"station": "x"}),
        )
    (detail,) = error.value.errors()
    assert detail["loc"] == ("provider",)
    assert f"not made from {provider}/{network}; the sources are dwd/observation, noaa/ghcn" in detail["msg"]


@pytest.mark.parametrize(
    ("given", "missing"),
    [
        pytest.param({"left": 9.0}, {"bottom", "right", "top"}, id="left-only"),
        pytest.param({"left": 9.0, "bottom": 50.0, "right": 10.0}, {"top"}, id="three"),
        pytest.param({"top": 50.0, "bottom": 40.0}, {"left", "right"}, id="two"),
    ],
)
def test_a_bounding_box_is_given_whole(given: dict[str, float], missing: set[str]) -> None:
    """Test a box with a border short is refused, naming the borders that are missing."""
    with pytest.raises(ValidationError) as error:
        StripesStationsRequest(kind="temperature", **given)
    assert {detail["loc"][0] for detail in error.value.errors()} == missing
    assert all(detail["type"] == "missing_with" for detail in error.value.errors())


@pytest.mark.parametrize(
    ("box", "field"),
    [
        pytest.param({"left": 10.0, "bottom": 40.0, "right": 10.0, "top": 50.0}, "right", id="no-width"),
        pytest.param({"left": 10.0, "bottom": 40.0, "right": 9.0, "top": 50.0}, "right", id="west-of-east"),
        pytest.param({"left": 9.0, "bottom": 50.0, "right": 10.0, "top": 40.0}, "top", id="south-of-north"),
    ],
)
def test_a_bounding_box_runs_west_to_east_and_south_to_north(box: dict[str, float], field: str) -> None:
    """Test a box that has no area is refused where it is wrong, before anything is read."""
    with pytest.raises(ValidationError) as error:
        StripesStationsRequest(kind="temperature", **box)
    assert [detail["loc"] for detail in error.value.errors()] == [(field,)]


# --- the REST API -----------------------------------------------------------------------------


def test_rest_values_say_where_the_years_come_from_and_how(client: TestClient) -> None:
    """Test the answer names GHCN, the daily parameters, and has a note on the rules in its `processing_note`."""
    response = client.get("/api/stripes/values", params=TEMPERATURE)

    assert response.status_code == 200
    body = response.json()
    request = body["metadata"]["request"]
    assert (request["provider"], request["network"]) == ("noaa", "ghcn")
    assert request["parameters"] == [
        "daily/data/temperature_air_mean_2m",
        "daily/data/temperature_air_max_2m",
        "daily/data/temperature_air_min_2m",
    ]
    note = body["metadata"]["processing_note"]
    assert "annual values were calculated from the provider's daily values by the rules of WMO-No. 1203" in note
    assert "a day is the midrange of TMAX and TMIN, which is no 24-hour mean" in note
    assert "at most 10 days missing and at most 4 in a row" in note
    assert "a year that fails is a gap" in note
    # and what the classes are relative to, as for DWD
    assert "Hawkins' method" in note
    assert body["metadata"]["provider"]["attribution"].startswith("NOAA National Centers for Environmental")
    assert body["series"]["parameter"] == "temperature_air_mean_2m"
    values = {item["timestamp"][:4]: item for item in body["values"]}
    assert values["2000"]["value"] is None
    assert values["2000"]["stripe_class"] is None
    assert values["1999"]["value"] == pytest.approx(11.8, abs=1e-3)


def test_rest_values_of_precipitation_name_the_one_parameter(client: TestClient) -> None:
    """Test the precipitation's note says the month is complete or none, and its parameter is PRCP's."""
    body = client.get("/api/stripes/values", params=PRECIPITATION).json()

    assert body["metadata"]["request"]["parameters"] == ["daily/data/precipitation_amount"]
    assert "a month counts only when complete" in body["metadata"]["processing_note"]


def test_rest_values_as_csv_carry_the_rules_in_the_headers(client: TestClient) -> None:
    """Test the CSV has no block, so the note of the rules goes in the header with the licence."""
    response = client.get("/api/stripes/values", params={**TEMPERATURE, "format": "csv"})

    assert response.status_code == 200
    assert "annual values were calculated" in response.headers["X-Wetterdienst-Processing"]
    assert "Atmospheric Administration" in response.headers["X-Wetterdienst-Provider"]
    assert "NOAA National Centers" in response.headers["X-Wetterdienst-Attribution"]


def test_rest_image_says_the_rules_in_its_headers(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the image, which holds no text of it, is sent with the note that it is drawn from calculated years."""

    class _Figure:
        def to_image(self, *_args: object, **_kwargs: object) -> bytes:
            return b"image"

    seen = []

    def draw(data: core.StripesData, request: StripesImageRequest) -> _Figure:
        seen.append((data.series.station["station_id"], request.provider, request.network))
        return _Figure()

    monkeypatch.setattr(restapi, "_draw_stripes", draw)
    monkeypatch.setattr(restapi, "render_image", lambda *_args, **_kwargs: b"image")
    monkeypatch.setattr(restapi, "require_kaleido", lambda: None)

    response = client.get("/api/stripes/image", params=TEMPERATURE)

    assert response.status_code == 200
    assert seen == [(stub.STATION, "noaa", "ghcn")]
    processing = response.headers["X-Wetterdienst-Processing"]
    assert "annual values were calculated from the provider's daily values" in processing
    assert "a day is the midrange of TMAX and TMIN" in processing
    # the image is of the years calculated above, not of the provider's own annual values, which the note denied
    assert processing.endswith(" The image is drawn from the annual values calculated above.")
    assert "provider's annual values" not in processing
    assert "of each year were calculated from the annual values calculated above: the mean of" in processing
    assert processing.count("The image is drawn") == 1


def test_the_image_names_the_source_and_no_country() -> None:
    """Test the figure credits NOAA and its title is no `Germany`; DWD's own keep their words."""
    ghcn = StripesImageRequest(**TEMPERATURE)
    figure = core._draw_stripes(_get_stripes_data(ghcn), ghcn)  # noqa: SLF001
    credit = next(a.text for a in figure.layout.annotations if a.text.startswith("Source:"))
    assert credit.startswith(f"Source: {NoaaGhcnRequest.metadata.attribution}. Colours: ")
    assert figure.layout.title.text == f"Climate stripes (temperature) for STUB STATION ({stub.STATION})"


def test_rest_stations_of_ghcn_come_by_box_with_their_own_block(client: TestClient) -> None:
    """Test the listing answers with the stations in the box and a block that names GHCN."""
    params = {"kind": "temperature", **GHCN, "active": False, "left": -74.5, "bottom": 40, "right": -73.8, "top": 41.5}

    response = client.get("/api/stripes/stations", params=params)

    assert response.status_code == 200
    body = response.json()
    assert [station["station_id"] for station in body["stations"]] == [stub.STATION]
    assert (body["metadata"]["request"]["provider"], body["metadata"]["request"]["network"]) == ("noaa", "ghcn")
    geojson = client.get("/api/stripes/stations", params={**params, "format": "geojson"}).json()
    assert [feature["properties"]["id"] for feature in geojson["data"]["features"]] == [stub.STATION]


@pytest.mark.parametrize("path", ["stations", "values", "image"])
@pytest.mark.parametrize(
    "pair",
    [{"provider": "noaa", "network": "observation"}, {"provider": "dwd", "network": "ghcn"}, {"provider": "eccc"}],
    ids=["noaa-observation", "dwd-ghcn", "eccc"],
)
def test_rest_refuses_any_other_pair_with_a_422(client: TestClient, path: str, pair: dict[str, str]) -> None:
    """Test a pair the stripes are not made from is the caller's 422, naming the sources, before anything is read."""
    params = {"kind": "temperature", **pair}
    if path != "stations":
        params["station"] = stub.STATION

    response = client.get(f"/api/stripes/{path}", params=params)

    assert response.status_code == 422
    assert "the sources are dwd/observation, noaa/ghcn" in json.dumps(response.json())


def test_rest_refuses_a_box_with_a_border_short(client: TestClient) -> None:
    """Test a box that is not whole is a 422 at the border that is missing."""
    response = client.get("/api/stripes/stations", params={"kind": "temperature", **GHCN, "left": 9, "bottom": 50})

    assert response.status_code == 422
    assert {tuple(error["loc"]) for error in response.json()["errors"]} == {("query", "right"), ("query", "top")}


def test_rest_a_station_that_is_not_listed_is_a_404(client: TestClient) -> None:
    """Test an id GHCN does not have is a 404 as DWD's is."""
    response = client.get("/api/stripes/values", params={**TEMPERATURE, "station": "USW99999999"})

    assert response.status_code == 404


# --- the command line -------------------------------------------------------------------------


def test_cli_stations_of_ghcn_in_a_box() -> None:
    """Test `stripes stations` takes the source and a box, and its block names GHCN."""
    result = CliRunner().invoke(
        cli,
        [
            *["stripes", "stations", "--kind=temperature", "--provider=noaa", "--network=ghcn", "--active=false"],
            *["--left=-74.5", "--bottom=40", "--right=-73.8", "--top=41.5"],
        ],
    )

    assert result.exit_code == 0, result.output
    body = json.loads(result.stdout)
    assert [station["station_id"] for station in body["stations"]] == [stub.STATION]
    assert body["metadata"]["request"]["provider"] == "noaa"
    assert body["metadata"]["request"]["network"] == "ghcn"


def test_cli_stations_default_to_dwd_and_a_pair_that_is_not_served_is_a_usage_error() -> None:
    """Test a pair the stripes are not made from is refused in click's terms, with the sources named."""
    result = CliRunner().invoke(cli, ["stripes", "stations", "--kind=temperature", "--provider=eccc"])

    assert result.exit_code == 2, result.output
    assert "the sources are dwd/observation, noaa/ghcn" in result.output


def test_cli_stations_refuse_a_box_with_a_border_short() -> None:
    """Test `--left` alone is a usage error."""
    result = CliRunner().invoke(
        cli, ["stripes", "stations", "--kind=temperature", "--provider=noaa", "--network=ghcn", "--left=9"]
    )

    assert result.exit_code == 2, result.output


@pytest.mark.usefixtures("figure_draws_itself")
def test_cli_image_takes_the_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test `stripes image --provider --network` reaches the request the figure is drawn from."""
    requests = []

    class _Figure:
        def to_image(self, **_kwargs: object) -> bytes:
            return b"png"

    def plot(request: StripesImageRequest) -> _Figure:
        requests.append(request)
        return _Figure()

    monkeypatch.setattr("wetterdienst.ui.cli._plot_stripes", plot)
    target = tmp_path / "stripes.png"
    result = CliRunner().invoke(
        cli,
        [
            *["stripes", "image", "--kind=temperature", "--provider=noaa", "--network=ghcn"],
            *[f"--station={stub.STATION}", f"--target={target}"],
        ],
    )

    assert result.exit_code == 0, result.output
    (request,) = requests
    assert (request.provider, request.network, request.station) == ("noaa", "ghcn", stub.STATION)


def test_cli_image_refuses_a_pair_that_is_not_served(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the image is not plotted for a source the stripes are not made from: a usage error, naming them."""
    monkeypatch.setattr("wetterdienst.ui.cli._plot_stripes", lambda _request: pytest.fail("plotted"))

    result = CliRunner().invoke(
        cli, ["stripes", "image", "--kind=temperature", "--provider=noaa", "--network=observation", "--station=x"]
    )

    assert result.exit_code == 2, result.output
    assert "the sources are dwd/observation, noaa/ghcn" in result.output


# --- MCP --------------------------------------------------------------------------------------


def _call_tool(name: str, arguments: dict[str, Any]) -> Any:  # noqa: ANN401
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(restapi.app)) as mcp_client:
            return await mcp_client.call_tool(name, arguments)

    return asyncio.run(call())


def test_mcp_stripes_values_take_the_source() -> None:
    """Test the `stripes_values` tool reads GHCN for `provider` and `network`, and says so in its block."""
    answer = json.loads(_call_tool("stripes_values", TEMPERATURE).content[0].text)["result"]

    assert answer["metadata"]["request"]["provider"] == "noaa"
    assert "WMO-No. 1203" in answer["metadata"]["processing_note"]
    assert answer["series"]["station"]["station_id"] == stub.STATION


def test_mcp_stripes_stations_take_the_source_and_a_box() -> None:
    """Test the `stripes_stations` tool lists GHCN's stations in a box."""
    arguments = {
        "kind": "temperature",
        **GHCN,
        "active": False,
        "left": -74.5,
        "bottom": 40,
        "right": -73.8,
        "top": 41.5,
    }
    answer = json.loads(_call_tool("stripes_stations", arguments).content[0].text)["result"]

    assert [station["station_id"] for station in answer["stations"]] == [stub.STATION]
    assert answer["metadata"]["request"]["provider"] == "noaa"


def test_mcp_refuses_a_pair_that_is_not_served() -> None:
    """Test a tool call for any other pair is an error that names the sources."""
    pytest.importorskip("fastmcp")
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    with pytest.raises(ToolError, match="the sources are dwd/observation, noaa/ghcn"):
        _call_tool(
            "stripes_values", {"kind": "temperature", "provider": "eccc", "network": "observation", "station": "x"}
        )


# --- the method of the days, as a field of the answer -----------------------------------------


@pytest.mark.parametrize(
    ("params", "method"),
    [
        pytest.param(TEMPERATURE, "midrange", id="midrange"),
        pytest.param({**TEMPERATURE, "station": stub.TAVG_ONLY_STATION}, "tavg", id="tavg-only"),
        pytest.param(PRECIPITATION, None, id="precipitation"),
    ],
)
def test_rest_values_carry_the_method_of_the_days_in_the_series(
    client: TestClient, params: dict[str, str], method: str | None
) -> None:
    """Test `series.method` is the structured field of the method, which the app need not read from the note."""
    body = client.get("/api/stripes/values", params=params).json()

    assert body["series"]["method"] == method
    note = body["metadata"]["processing_note"]
    if method == "midrange":
        assert "a day is the midrange of TMAX and TMIN" in note
    if method == "tavg":
        assert "a day is the source's TAVG" in note


def test_rest_values_of_dwd_have_no_method(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test DWD's own annual values have `series.method` null, present in the answer."""
    from tests.ui.test_restapi import _stub_stripes_station  # noqa: PLC0415

    _stub_stripes_station(monkeypatch, "temperature", [1.0 + year for year in range(10)])

    body = client.get("/api/stripes/values", params={"kind": "temperature", "station": "01048"}).json()

    assert "method" in body["series"]
    assert body["series"]["method"] is None
    assert body["metadata"]["request"]["provider"] == "dwd"


def test_mcp_stripes_values_carry_the_method() -> None:
    """Test the MCP tool, which answers through REST, has the field too."""
    answer = json.loads(_call_tool("stripes_values", TEMPERATURE).content[0].text)["result"]

    assert answer["series"]["method"] == "midrange"
