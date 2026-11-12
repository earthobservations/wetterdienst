# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the monthly and the annual validated observations of KNMI (GH-4006).

The files are slices of the real ones, read from the Open Data API with a key on 2026-11-11: every variable and
attribute of the file is kept, the stations are cut down to De Bilt (06260), Eelde (06280), the platform D15-FA-1
(06201) and K13-A (06252, one of the three stations of 2024 that hold a sea temperature).

- `monthly-observations-validated-202609.nc`: September 2026, time coordinate 2026-10-01 00:00 UTC ("Time (in UTC)
  indicating the end of the monthly measurement interval"), the 67 stations of that file cut to three.
- `monthly-observations-validated-190101.nc`: January 1901, time coordinate 1901-02-01, a single station (De Bilt)
  that holds a temperature, humidity and sunshine and nothing else.
- `annual-observations-validated-2024.nc`: 2024, time coordinate 2025-01-01, the 62 stations cut to three.
"""

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.provider.value_stubs import stations_result
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.options import Options
from wetterdienst.provider.knmi.observation import KnmiObservationMetadata
from wetterdienst.provider.knmi.observation import api as knmi_api
from wetterdienst.provider.knmi.observation.api import (
    KnmiObservationRequest,
    _end_of,
    _file_expiry,
    _filename_for,
    _latest_filename,
    _moments,
    _stamp,
)
from wetterdienst.provider.knmi.observation.parser import open_netcdf, parse_knmi_netcdf
from wetterdienst.settings import Settings
from wetterdienst.util.network import File

h5netcdf = pytest.importorskip("h5netcdf", reason="h5netcdf not installed")
h5py = pytest.importorskip("h5py", reason="h5py not installed")

UTC = ZoneInfo("UTC")
FILES = Path(__file__).parent / "files"
DE_BILT = "06260"
MONTHLY = "monthly-observations-validated-202609.nc"
MONTHLY_1901 = "monthly-observations-validated-190101.nc"
ANNUAL = "annual-observations-validated-2024.nc"


def _real(name: str) -> bytes:
    return (FILES / name).read_bytes()


def _serve(monkeypatch: pytest.MonkeyPatch, files: dict[str, str]) -> list[str]:
    """Serve the slice that is named for each file of the datasets, and give the names KNMI is asked for."""
    asked: list[str] = []

    def fetch(_dataset: str, _version: str, filename: str, _settings: Settings) -> bytes | Exception:
        asked.append(filename)
        if filename not in files:
            return FileNotFoundError(filename)
        return _real(files[filename])

    monkeypatch.setattr(knmi_api, "_fetch_netcdf", fetch)
    return asked


def _values(parameters: list, start: dt.datetime, end: dt.datetime, station_id: str = DE_BILT) -> pl.DataFrame:
    request = KnmiObservationRequest(
        parameters=parameters, start=start, end=end, settings=Settings(auth={"knmi": "dummy-key-for-test"})
    )
    resolution = parameters[0][0]
    return stations_result(request, resolution, "data", station_id).values().all().df


def test_the_files_name_their_period() -> None:
    """A monthly file is named for its month and an annual file for its year."""
    assert _filename_for(Resolution.MONTHLY, dt.datetime(2026, 9, 1, tzinfo=UTC)) == MONTHLY
    assert _filename_for(Resolution.MONTHLY, dt.datetime(1901, 1, 1, tzinfo=UTC)) == MONTHLY_1901
    assert _filename_for(Resolution.ANNUAL, dt.datetime(2024, 1, 1, tzinfo=UTC)) == ANNUAL


@pytest.mark.parametrize("resolution", [Resolution.MONTHLY, Resolution.ANNUAL])
def test_a_value_is_stamped_with_the_first_day_of_its_period(resolution: Resolution) -> None:
    """The name is the period and the time coordinate its end, which is not the stamp (as for the daily file).

    `monthly-observations-validated-202609.nc` has the time 2026-10-01 and `annual-observations-validated-2024.nc` the
    time 2025-01-01 (read from the real files, 2026-11-11); the values of both are those of September 2026 and of 2024.
    """
    moment = (
        dt.datetime(2026, 9, 1, tzinfo=UTC) if resolution == Resolution.MONTHLY else dt.datetime(2024, 1, 1, tzinfo=UTC)
    )
    assert _stamp(moment, resolution) == moment


@pytest.mark.parametrize(
    ("resolution", "name", "end"),
    [
        (Resolution.MONTHLY, MONTHLY, "2026-10-01"),
        (Resolution.MONTHLY, "monthly-observations-validated-202612.nc", "2027-01-01"),
        (Resolution.MONTHLY, MONTHLY_1901, "1901-02-01"),
        (Resolution.ANNUAL, ANNUAL, "2025-01-01"),
    ],
)
def test_the_time_coordinate_of_a_real_file_is_the_end_of_the_period_its_name_says(
    resolution: Resolution, name: str, end: str
) -> None:
    """The coordinate of the real slices is the end of the period of the name, which is where `_end_of` puts it."""
    expected = dt.datetime.fromisoformat(end).replace(tzinfo=dt.UTC)
    assert _end_of(name) == expected
    if name in {MONTHLY, MONTHLY_1901, ANNUAL}:
        with open_netcdf(_real(name)) as file:
            seconds = float(file.variables["time"][:][0])
            assert file.variables["time"].attrs["units"] == "seconds since 1950-01-01"
            assert dt.datetime(1950, 1, 1, tzinfo=dt.UTC) + dt.timedelta(seconds=seconds) == expected
            assert resolution.value in file.variables["time"].attrs["long_name"].lower()


def test_moments_of_months_roll_over_the_year() -> None:
    """A range of months names one file per month, December to January included."""
    assert list(
        _moments(dt.datetime(2025, 11, 1, tzinfo=UTC), dt.datetime(2026, 2, 1, tzinfo=UTC), Resolution.MONTHLY)
    ) == [
        dt.datetime(2025, 11, 1, tzinfo=UTC),
        dt.datetime(2025, 12, 1, tzinfo=UTC),
        dt.datetime(2026, 1, 1, tzinfo=UTC),
        dt.datetime(2026, 2, 1, tzinfo=UTC),
    ]


def test_moments_of_months_end_with_the_month_that_starts_in_the_range() -> None:
    """The month of 2026-02-01 is stamped on the 1st: an end in that month includes it, an end before it does not."""
    start = dt.datetime(2026, 1, 1, tzinfo=UTC)
    assert list(_moments(start, dt.datetime(2026, 2, 20, tzinfo=UTC), Resolution.MONTHLY))[-1] == dt.datetime(
        2026, 2, 1, tzinfo=UTC
    )
    assert list(_moments(start, dt.datetime(2026, 1, 31, 23, tzinfo=UTC), Resolution.MONTHLY)) == [start]


def test_moments_of_a_mid_month_start_leave_out_that_month() -> None:
    """A start inside a month is after the month's stamp, so the first value is the next month's (mixed request)."""
    assert list(
        _moments(dt.datetime(2026, 1, 15, tzinfo=UTC), dt.datetime(2026, 3, 1, tzinfo=UTC), Resolution.MONTHLY)
    ) == [
        dt.datetime(2026, 2, 1, tzinfo=UTC),
        dt.datetime(2026, 3, 1, tzinfo=UTC),
    ]


def test_moments_of_years() -> None:
    """A range of years names one file per year."""
    assert list(
        _moments(dt.datetime(2023, 1, 1, tzinfo=UTC), dt.datetime(2025, 6, 1, tzinfo=UTC), Resolution.ANNUAL)
    ) == [dt.datetime(2023, 1, 1, tzinfo=UTC), dt.datetime(2024, 1, 1, tzinfo=UTC), dt.datetime(2025, 1, 1, tzinfo=UTC)]


@pytest.mark.parametrize(
    ("resolution", "start", "floored"),
    [
        (Resolution.MONTHLY, dt.datetime(2026, 9, 17, 6, 30, tzinfo=UTC), dt.datetime(2026, 9, 1, tzinfo=UTC)),
        (Resolution.ANNUAL, dt.datetime(2024, 5, 17, 6, 30, tzinfo=UTC), dt.datetime(2024, 1, 1, tzinfo=UTC)),
    ],
)
def test_a_single_monthly_or_annual_request_floors_its_start_to_the_period(
    resolution: Resolution, start: dt.datetime, floored: dt.datetime
) -> None:
    """As for a day, a start inside a month or a year includes it: its stamp is the first day of the period."""
    request = KnmiObservationRequest(
        parameters=[(resolution.value, "data", "temperature_air_mean_2m")],
        start=start,
        end=dt.datetime(2026, 12, 31, tzinfo=UTC),
        settings=Settings(auth={"knmi": "dummy-key-for-test"}),
    )
    assert request.start == floored


def test_a_mixed_request_keeps_its_start() -> None:
    """A request of a month and a day has no single boundary."""
    start = dt.datetime(2026, 9, 17, 6, 30, tzinfo=UTC)
    request = KnmiObservationRequest(
        parameters=[("monthly", "data", "temperature_air_mean_2m"), ("daily", "data", "temperature_air_mean_2m")],
        start=start,
        end=dt.datetime(2026, 12, 31, tzinfo=UTC),
        settings=Settings(auth={"knmi": "dummy-key-for-test"}),
    )
    assert request.start == start


@pytest.mark.parametrize(
    ("name", "now", "expiry"),
    [
        pytest.param(MONTHLY, "2026-10-01T05:00", CacheExpiry.FIVE_MINUTES, id="a month that ended 5 h ago"),
        pytest.param(MONTHLY, "2026-10-01T07:00", CacheExpiry.TWELVE_HOURS, id="a month that ended 7 h ago"),
        pytest.param(ANNUAL, "2025-01-01T07:00", CacheExpiry.TWELVE_HOURS, id="a year that ended 7 h ago"),
        pytest.param(ANNUAL, "2024-12-31T23:00", CacheExpiry.FIVE_MINUTES, id="a year that has not ended"),
    ],
)
def test_a_period_file_is_kept_by_the_age_of_the_end_of_its_period(
    monkeypatch: pytest.MonkeyPatch, name: str, now: str, expiry: CacheExpiry
) -> None:
    """A month that is over for more than six hours is kept for twelve hours, as the day of a daily file (GH-3927)."""
    monkeypatch.setattr(knmi_api, "_now", lambda: dt.datetime.fromisoformat(now).replace(tzinfo=dt.UTC))
    assert _file_expiry(_end_of(name)) == expiry


def _latest(monkeypatch: pytest.MonkeyPatch, dataset: str) -> str:
    """Give the URL that the listing of the latest file of a dataset is asked at."""
    asked: list[str] = []

    def download(url: str, *_args: object, **_kwargs: object) -> File:
        asked.append(url)
        import io  # noqa: PLC0415

        return File(url=url, content=io.BytesIO(b'{"files": [{"filename": "latest.nc"}]}'), status=200)

    monkeypatch.setattr(knmi_api, "_download_with_retry", download)
    assert _latest_filename(dataset, "1.0", Settings(auth={"knmi": "dummy-key-for-test"})) == "latest.nc"
    return asked[0]


@pytest.mark.parametrize(
    ("resolution", "order"),
    [
        (Resolution.MINUTE_10, "created"),
        (Resolution.HOURLY, "created"),
        (Resolution.DAILY, "created"),
        (Resolution.MONTHLY, "filename"),
        (Resolution.ANNUAL, "filename"),
    ],
)
def test_the_latest_file_of_a_period_dataset_is_the_last_period(
    monkeypatch: pytest.MonkeyPatch, resolution: Resolution, order: str
) -> None:
    """The annual file of 2023 was made after those of 2024 and 2025 (read 2026-11-11), so `created` is not the last."""
    dataset, _version = knmi_api._DATASET_BY_RESOLUTION[resolution]  # noqa: SLF001
    assert f"orderBy={order}&sorting=desc" in _latest(monkeypatch, dataset)


def test_the_latest_catalogue_is_the_last_date_in_a_name_and_its_listing_is_kept_for_half_a_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The catalogue file of 2012-01-01 was made after those of 2023 to 2026 (read 2026-11-11), so not `created`.

    Its listing is kept 12 hours (`_CATALOGUE_LISTING_EXPIRY`), where that of the others is kept an hour.
    """
    asked: list[tuple[str, CacheExpiry]] = []

    def download(url: str, _settings: Settings, ttl: CacheExpiry, **_kwargs: object) -> File:
        import io  # noqa: PLC0415

        asked.append((url, ttl))
        return File(url=url, content=io.BytesIO(b'{"files": [{"filename": "csv_knmi_nl_20260615.csv"}]}'), status=200)

    monkeypatch.setattr(knmi_api, "_download_with_retry", download)
    settings = Settings(auth={"knmi": "dummy-key-for-test"})
    dataset, version = knmi_api._STATIONS_DATASET  # noqa: SLF001

    assert _latest_filename(dataset, version, settings, CacheExpiry.TWELVE_HOURS) == "csv_knmi_nl_20260615.csv"
    assert _latest_filename("daily-in-situ-meteorological-observations-validated", "1.0", settings) is not None
    (catalogue, week), (daily, hour) = asked
    assert "/datasets/waarneemstations_csv/versions/1.0/files?" in catalogue
    assert "orderBy=filename&sorting=desc" in catalogue
    assert week == CacheExpiry.TWELVE_HOURS
    assert "orderBy=created" in daily
    assert hour == CacheExpiry.ONE_HOUR


def test_the_datasets_are_the_validated_ones() -> None:
    """The names and the version the Open Data API lists (2026-11-11: 1510 monthly files, 125 annual files)."""
    datasets = knmi_api._DATASET_BY_RESOLUTION  # noqa: SLF001
    assert datasets[Resolution.MONTHLY] == ("monthly-in-situ-meteorological-observations-validated", "1.0")
    assert datasets[Resolution.ANNUAL] == ("annual-in-situ-meteorological-observations-validated", "1.0")


def test_every_mapped_variable_is_in_the_real_files() -> None:
    """Each `name_original` of the two resolutions is a variable of the real monthly and annual file, with its unit."""
    units = {
        "degree_celsius": "°C",
        "percent": "%",
        "hectopascal": "hPa",
        "meter_per_second": "m/s",
        "degree": "°",
        "millimeter": "mm",
        "hour": "h",
        "joule_per_square_centimeter": "J/cm²",
        "one_eighth": "okta",
    }
    for name, file in (("monthly", MONTHLY), ("annual", ANNUAL)):
        with open_netcdf(_real(file)) as netcdf:
            for parameter in KnmiObservationMetadata[name]["data"]:
                variable = netcdf.variables[parameter.name_original]
                unit = variable.attrs["units"]
                unit = unit.decode() if isinstance(unit, bytes) else str(unit)
                assert unit == units[parameter.unit], parameter.name


def test_the_unmapped_variables_are_named() -> None:
    """The variables of the files that have no canonical name are left out, and nothing else is."""
    unmapped = {"EV24", "FHVEC", "T10N", "VVN", "VVX", "W1", "W2", "W3", "W5", "W6"}
    with open_netcdf(_real(MONTHLY)) as netcdf:
        data = {name for name, variable in netcdf.variables.items() if variable.dimensions == ("station", "time")}
    mapped = {parameter.name_original for parameter in KnmiObservationMetadata["monthly"]["data"]}
    assert data - mapped == unmapped
    assert {p.name_original for p in KnmiObservationMetadata["annual"]["data"]} == mapped


def test_monthly_values_of_a_real_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """De Bilt, September 2026, as the real file holds it, stamped with the first of the month."""
    asked = _serve(monkeypatch, {MONTHLY: MONTHLY})
    df = _values(
        [("monthly", "data")],
        # a start inside the month includes it: the request floors it to the 1st
        dt.datetime(2026, 9, 12, tzinfo=UTC),
        dt.datetime(2026, 9, 30, tzinfo=UTC),
    )
    assert asked == [MONTHLY]
    assert df["timestamp"].unique().to_list() == [dt.datetime(2026, 9, 1, tzinfo=UTC)]
    values = dict(zip(df["parameter"], df["value"], strict=True))
    assert values["temperature_air_mean_2m"] == pytest.approx(16.7)
    assert values["temperature_air_min_2m"] == pytest.approx(5.8)
    assert values["temperature_air_max_2m"] == pytest.approx(27.3)
    assert values["precipitation_amount"] == pytest.approx(56.4)
    assert values["precipitation_duration"] == pytest.approx(25.7)
    assert values["sunshine_duration"] == pytest.approx(163.9)
    assert values["wind_speed_mean"] == pytest.approx(2.8)
    assert values["wind_direction_mean"] == pytest.approx(231.0)
    # a variable of the file that is not mapped is not returned, nor one that is not measured at the station
    assert "temperature_water_mean" not in values


def test_annual_values_of_a_real_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station with a sea temperature, 2024, stamped with 1 January 2024."""
    asked = _serve(monkeypatch, {ANNUAL: ANNUAL})
    df = _values(
        [("annual", "data", "temperature_water_mean"), ("annual", "data", "precipitation_amount")],
        dt.datetime(2024, 1, 1, tzinfo=UTC),
        dt.datetime(2024, 6, 1, tzinfo=UTC),
        station_id="06252",
    )
    assert asked == [ANNUAL]
    assert df["timestamp"].unique().to_list() == [dt.datetime(2024, 1, 1, tzinfo=UTC)]
    assert dict(zip(df["parameter"], df["value"], strict=True)) == {"temperature_water_mean": pytest.approx(12.6)}


def test_a_month_that_is_not_published_is_left_out_and_the_others_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A range of months reads one file per month, and a 404 skips that month."""
    asked = _serve(monkeypatch, {MONTHLY: MONTHLY})
    df = _values(
        [("monthly", "data", "temperature_air_mean_2m")],
        dt.datetime(2026, 8, 1, tzinfo=UTC),
        dt.datetime(2026, 10, 1, tzinfo=UTC),
    )
    assert asked == [
        "monthly-observations-validated-202608.nc",
        MONTHLY,
        "monthly-observations-validated-202610.nc",
    ]
    assert df["timestamp"].to_list() == [dt.datetime(2026, 9, 1, tzinfo=UTC)]


def test_a_file_of_the_first_years_holds_few_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """January 1901 has the temperatures, the humidity and the sunshine, and null (so no row) for the rest."""
    _serve(monkeypatch, {MONTHLY_1901: MONTHLY_1901})
    df = _values([("monthly", "data")], dt.datetime(1901, 1, 1, tzinfo=UTC), dt.datetime(1901, 1, 31, tzinfo=UTC))
    assert dict(zip(df["parameter"], df["value"], strict=True)) == {
        "humidity_relative_mean": pytest.approx(80.0),
        "sunshine_duration_relative": pytest.approx(25.0),
        "sunshine_duration": pytest.approx(65.0),
        "temperature_air_max_2m": pytest.approx(9.6),
        "temperature_air_mean_2m": pytest.approx(-0.3),
        "temperature_air_min_2m": pytest.approx(-12.2),
    }
    assert df["timestamp"].unique().to_list() == [dt.datetime(1901, 1, 1, tzinfo=UTC)]


def _write(path: Path, values: dict[str, float]) -> bytes:
    string_dtype = h5py.string_dtype()
    with h5netcdf.File(path, "w") as file:
        file.dimensions = {"station": 1, "time": 1}
        station = file.create_variable("station", ("station",), dtype=string_dtype)
        station[:] = ["0-20000-0-06260"]
        for name, value in values.items():
            variable = file.create_variable(name, ("station", "time"), dtype="f8")
            variable[:] = [[value]]
    return path.read_bytes()


def test_the_vector_mean_direction_has_the_code_of_a_calm_and_the_others_have_none(tmp_path: Path) -> None:
    """DDVEC says "0=calm/variable" (the description of the files): no bearing, kept as `raw:0`; 360 is north."""
    moment = dt.datetime(2026, 9, 1, tzinfo=UTC)
    calm = parse_knmi_netcdf(
        _write(tmp_path / "calm.nc", {"DDVEC": 0.0, "NG": 9.0, "FHN": 0.0}),
        DE_BILT,
        ["DDVEC", "NG", "FHN"],
        moment,
        trace_codes=False,
    )
    rows = {row["parameter"]: row for row in calm.to_dicts()}
    assert rows["DDVEC"]["value"] is None
    assert rows["DDVEC"]["quality_flags"] == "raw:0"
    # the mean cloud cover "9=sky invisible" is no cover
    assert rows["NG"]["value"] is None
    assert rows["NG"]["quality_flags"] == "raw:9"
    # a lowest hourly wind speed of 0 is a speed
    assert rows["FHN"]["value"] == 0.0
    assert rows["FHN"]["quality_flags"] is None
    north = parse_knmi_netcdf(
        _write(tmp_path / "north.nc", {"DDVEC": 360.0}), DE_BILT, ["DDVEC"], moment, trace_codes=False
    )
    assert north["value"].to_list() == [360.0]


def test_the_trace_code_is_the_one_of_the_hourly_and_daily_files_only(tmp_path: Path) -> None:
    """A -1 is a trace in the hourly and the daily file; the monthly and the annual describe no such code (sums)."""
    moment = dt.datetime(2026, 9, 1, tzinfo=UTC)
    payload = _write(tmp_path / "trace.nc", {"RH": -1.0, "SQ": -1.0})
    traced = parse_knmi_netcdf(payload, DE_BILT, ["RH", "SQ"], moment)
    assert traced["value"].to_list() == [0.0, 0.0]
    assert traced["quality_flags"].to_list() == ["raw:-1", "raw:-1"]
    summed = parse_knmi_netcdf(payload, DE_BILT, ["RH", "SQ"], moment, trace_codes=False)
    assert summed["value"].to_list() == [-1.0, -1.0]
    assert summed["quality_flags"].to_list() == [None, None]


@pytest.mark.synthetic_values  # the -1 is served on purpose, where it is no reading
@pytest.mark.parametrize("resolution", ["monthly", "annual"])
def test_a_minus_one_of_a_monthly_or_annual_file_is_not_read_as_a_trace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resolution: str
) -> None:
    """The values path does not turn a -1 of `RH` or `SQ` of these files into 0.0 with `raw:-1`.

    The hourly and the daily file write a trace so; the sums of these two describe no such code, so a -1 is a number
    that is no precipitation, which the range check rejects (and `trace_codes` of `parse_knmi_netcdf` is wired by the
    resolution, not set for all).
    """
    payload = _write(tmp_path / "minus_one.nc", {"RH": -1.0, "SQ": -1.0, "TG": 3.2})
    monkeypatch.setattr(knmi_api, "_fetch_netcdf", lambda *_args: payload)
    moment = dt.datetime(2026, 9, 1, tzinfo=UTC) if resolution == "monthly" else dt.datetime(2024, 1, 1, tzinfo=UTC)
    request = KnmiObservationRequest(
        parameters=[(resolution, "data", "precipitation_amount"), (resolution, "data", "sunshine_duration")],
        start=moment,
        end=moment,
        settings=Settings(auth={"knmi": "dummy-key-for-test"}),
        options=Options(drop_nulls=False),
    )
    df = stations_result(request, resolution, "data", DE_BILT).values().all().df
    rows = {row["parameter"]: row for row in df.to_dicts()}
    assert set(rows) == {"precipitation_amount", "sunshine_duration"}
    for row in rows.values():
        # a trace would be 0.0 with `raw:-1`; the number is kept out of range and rejected, not turned into a zero
        assert row["value"] is None
        assert row["quality_flags"] != "raw:-1"
        assert "rejected:range" in row["quality_flags"]
        assert row["quality_flags"].endswith("raw:-1")


def test_the_missing_value_of_a_variable_is_null(tmp_path: Path) -> None:
    """The _FillValue of every variable of the files is NaN: no value, kept as `raw:NaN`."""
    payload = _write(tmp_path / "nan.nc", {"TG": float("nan")})
    df = parse_knmi_netcdf(payload, DE_BILT, ["TG"], dt.datetime(2026, 9, 1, tzinfo=UTC), trace_codes=False)
    assert df["value"].to_list() == [None]
    assert df["quality_flags"].to_list() == ["raw:NaN"]
    with open_netcdf(_real(MONTHLY)) as netcdf:
        assert str(netcdf.variables["TG"].attrs["_FillValue"]) == "nan"
