# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for WSV Pegelonline, in particular its per-station source units."""

import json

import pytest

from wetterdienst.provider.wsv.pegel import WsvPegelRequest
from wetterdienst.provider.wsv.pegel.api import _SOURCE_UNIT_FACTORS
from wetterdienst.util.network import File


def test_wsv_source_unit_factors_are_identity_for_the_declared_unit() -> None:
    """Test that every scaled parameter leaves the unit it is declared in untouched.

    The factors convert a station's own unit to the unit declared in the metadata, so the declared
    unit must map to 1.0. A factor other than 1.0 there would rescale the majority of stations,
    which is the failure this whole mechanism exists to prevent, only inverted.
    """
    metadata = WsvPegelRequest.metadata
    declared = {
        parameter.name_original: parameter.unit
        for resolution in metadata
        for dataset in resolution
        for parameter in dataset.parameters
    }
    # the source's spelling of each declared unit; a declared unit missing here is a KeyError
    # rather than a silent skip, so this cannot go stale unnoticed
    unit_names = {
        "centimeter": "cm",
        "meter_per_second": "m/s",
        "microsiemens_per_centimeter": "µS/cm",
        "nephelometric_turbidity": "NTU",
        "second": "s",
    }
    for name_original, factors in _SOURCE_UNIT_FACTORS.items():
        source_unit = unit_names[declared[name_original]]
        assert source_unit in factors, f"{name_original}: no source unit matches the declared unit"
        assert factors[source_unit] == 1.0, f"{name_original}: {source_unit} is the declared unit but is scaled"


def test_wsv_source_unit_factors_convert_the_other_units_correctly() -> None:
    """Test the factors that actually rescale, which the identity check above cannot reach.

    A typo in one of these is the failure mode this whole mechanism exists to prevent, and it would
    be invisible: the value is simply wrong by a power of ten at the minority of stations.
    """
    expected = {
        "W": {"cm": 1.0, "m+NN": 100.0, "m+PNP": 100.0},  # metres above a datum -> centimetres
        "LF": {"µS/cm": 1.0, "mS/cm": 1000.0},  # 1 mS == 1000 µS
        "VA": {"m/s": 1.0, "cm/s": 0.01},
        "SIGH": {"cm": 1.0, "m": 100.0},
        "MAXH": {"cm": 1.0, "m": 100.0},
        "TP": {"s": 1.0, "1/100s": 0.01},  # hundredths of a second -> seconds
        "TR": {"NTU": 1.0, "FNU": 1.0, "TE/F": 1.0},  # one formazin scale under three names
    }
    assert expected == _SOURCE_UNIT_FACTORS


@pytest.mark.remote
def test_wsv_wave_height_is_comparable_across_stations() -> None:
    """Test that wave height is returned in one unit regardless of what the station publishes.

    Pegelonline publishes significant wave height in m at MELLUMPLATE and cm at LT ALTE WESER. The
    metadata declares centimetre, so the metre station used to come back around 100x too small --
    0.07-1.32 next to 12.66-280.6 for the same quantity, both labelled cm.
    """
    values = {}
    for station_id in ("9420010", "9460041"):
        request = WsvPegelRequest(parameters=[("1_minute", "data", "wave_height_sign")])
        df = request.filter_by_station_id(station_id).values.all().df
        series = df.get_column("value").drop_nulls()
        assert not series.is_empty(), f"no data for {station_id}"
        values[station_id] = series.mean()
    # both are wave heights in cm at neighbouring North Sea stations, so they belong to the same
    # order of magnitude; before the fix they differed by roughly 100x
    ratio = max(values.values()) / min(values.values())
    assert ratio < 10, f"wave heights still differ by {ratio:.0f}x: {values}"


@pytest.mark.remote
def test_wsv_wave_period_is_seconds() -> None:
    """Test that wave period comes back as a duration in seconds.

    It was declared with a `wave_period` unit whose symbol was `1/s`, a frequency, and the source
    publishes seconds at one station and hundredths of a second at another.
    """
    for station_id in ("9420010", "9460041"):
        request = WsvPegelRequest(parameters=[("1_minute", "data", "wave_period")])
        df = request.filter_by_station_id(station_id).values.all().df
        series = df.get_column("value").drop_nulls()
        assert not series.is_empty(), f"no data for {station_id}"
        # wind waves on the German North Sea coast run a few seconds; hundredths would read in
        # the hundreds and a frequency would be far below one
        assert 1 < series.mean() < 20, f"{station_id}: implausible wave period {series.mean()}"


@pytest.mark.remote
def test_wsv_flow_direction_is_a_bearing() -> None:
    """Test that the direction of the water current is reported in degrees.

    Pegelonline gives `R` the unit `MGN`, degrees relative to magnetic north, which had been read
    as a magnetic quantity and declared as magnetic field strength in A/m.
    """
    df = WsvPegelRequest(parameters=[("5_minutes", "data", "flow_direction")]).all().values.all().df
    series = df.get_column("value").drop_nulls()
    assert not series.is_empty()
    assert series.min() >= 0
    assert series.max() <= 360


@pytest.mark.remote
def test_wsv_stage_is_scaled_for_metre_gauges() -> None:
    """Test that gauges publishing water level in metres are scaled to centimetres.

    Most gauges publish cm above gauge zero, but 66 have no gauge zero and publish metres above sea
    level, which used to be reported unscaled as centimetres -- 56.5 where the true figure is 5650.
    The datum still differs between the two groups; `gauge_zero` in the station metadata says which.
    """
    stations = WsvPegelRequest(parameters=[("1_minute", "data", "stage")]).filter_by_station_id("27800090")
    series = stations.values.all().df.get_column("value").drop_nulls()
    assert not series.is_empty()
    # metres above sea level for this canal gauge, so thousands of centimetres rather than tens
    assert series.mean() > 1000


@pytest.mark.remote
def test_wsv_multiple_parameters_with_missing_data() -> None:
    """Test that requesting several parameters works when one of them has no data for the station.

    Concatenating an empty frame with a populated one used to raise
    `polars.exceptions.ShapeError: unable to append to a DataFrame of width 6 with a DataFrame of
    width 0`.
    """
    request = WsvPegelRequest(
        parameters=[("1_minute", "data", p) for p in ("wave_period", "flow_direction", "wave_height_sign")],
    )
    df = request.filter_by_station_id("9460041").values.all().df
    # flow_direction has no data at this station while the other two do, which is the whole point:
    # the empty one must not take the populated ones down with it
    assert not df.is_empty()
    assert "wave_height_sign" in df.get_column("parameter").unique().to_list()


def test_wsv_timeseries_meta_is_not_cached_when_the_listing_is_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a failed station listing is retried rather than remembered as "nothing known".

    An empty mapping cached after a transient failure makes every lookup miss, which skips every
    scaled parameter for the lifetime of the process -- long after the listing came back.
    """
    from io import BytesIO  # noqa: PLC0415

    import polars as pl  # noqa: PLC0415

    from wetterdienst.model.result import StationsFilter, StationsResult  # noqa: PLC0415
    from wetterdienst.provider.wsv.pegel import api  # noqa: PLC0415
    from wetterdienst.provider.wsv.pegel.api import TimeseriesMeta, WsvPegelValues  # noqa: PLC0415
    from wetterdienst.util.network import File, NoInternetError  # noqa: PLC0415

    # deliberately not `.all()`: that eagerly downloads the 1.2 MB station listing, which would
    # make this a network test in all but the marker
    request = WsvPegelRequest(parameters=[("1_minute", "data", "stage")])
    values = WsvPegelValues(
        sr=StationsResult(
            stations=request,
            df=pl.DataFrame(),
            df_all=pl.DataFrame(),
            stations_filter=StationsFilter.ALL,
        ),
    )
    settings = request.settings

    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=NoInternetError(), status=-1),
    )
    assert values._timeseries_meta(settings) == {}  # noqa: SLF001
    assert values._timeseries_meta_cache is None, "a failed listing must not be cached"  # noqa: SLF001

    listing = b'[{"number": "1", "timeseries": [{"shortname": "W", "unit": "cm", "equidistance": 15}]}]'
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(listing), status=200),
    )
    assert values._timeseries_meta(settings) == {  # noqa: SLF001
        ("1", "W"): TimeseriesMeta(unit="cm", equidistance=15),
    }


def test_wsv_every_parameter_is_described() -> None:
    """Test that expanding the descriptions over the resolutions actually reaches all of them.

    The parameter descriptions are declared once and keyed by resolution name, so they attach only
    to resolutions spelled the same way in both places. A resolution added to the provider but not
    to `_WSV_PEGEL_RESOLUTIONS` would leave a whole resolution's worth of parameters undescribed in
    the docs, the REST API and the MCP tools, without anything failing.
    """
    undescribed = sorted(
        f"{resolution.name}/{dataset.name}/{parameter.name}"
        for resolution in WsvPegelRequest.metadata
        for dataset in resolution
        for parameter in dataset.parameters
        if not parameter.description
    )
    # NIEDERSCHLAG and NIEDERSCHLAGSINTENSITAET are declared but served by no station today, so
    # they are described here and simply never appear in a station list
    assert not undescribed, f"parameters with no description: {undescribed}"


def test_wsv_resolutions_are_the_intervals_the_service_publishes() -> None:
    """Test that the resolutions and the interval mapping cannot drift apart.

    The resolutions are built from `_EQUIDISTANCE_TO_RESOLUTION`, and the station list assigns a
    station to a resolution by looking its published `equidistance` up in the same mapping. An
    interval mapped to a resolution that is not declared would silently produce station rows under
    a resolution nothing can be requested for.
    """
    from wetterdienst.metadata.source_descriptions import _WSV_PEGEL_RESOLUTIONS  # noqa: PLC0415
    from wetterdienst.provider.wsv.pegel.api import _EQUIDISTANCE_TO_RESOLUTION  # noqa: PLC0415

    declared = [resolution.name for resolution in WsvPegelRequest.metadata]
    assert declared == list(_EQUIDISTANCE_TO_RESOLUTION.values())
    assert declared == list(_WSV_PEGEL_RESOLUTIONS)


@pytest.mark.remote
def test_wsv_station_mixing_intervals_serves_each_parameter_at_its_own_resolution() -> None:
    """Test that a station recording at two intervals does not report either under the other.

    PASSAU DONAU records stage every 15 minutes and air and water temperature every 60, so it is in
    the station list under both resolutions. Serving every requested parameter for both rows would
    label the 15-minute stage hourly, which is wrong for every reader downstream.
    """
    parameters = [
        (resolution, "data", parameter)
        for resolution in ("15_minutes", "hourly")
        for parameter in ("stage", "temperature_air_mean_2m")
    ]
    request = WsvPegelRequest(parameters=parameters).filter_by_station_id("10091008")
    assert set(request.df.get_column("resolution")) == {"15_minutes", "hourly"}
    df = request.values.all().df
    served = {
        (row["resolution"], row["parameter"]) for row in df.select("resolution", "parameter").unique().rows(named=True)
    }
    assert served == {("15_minutes", "stage"), ("hourly", "temperature_air_mean_2m")}


def test_wsv_unmapped_equidistance_is_reported(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that an interval no resolution covers is announced rather than silently dropped.

    A station recording at an interval absent from `_EQUIDISTANCE_TO_RESOLUTION` belongs to no
    resolution and so appears in no station list. That is the right outcome -- better than filing
    it under a neighbouring interval and misdescribing it -- but on its own it is indistinguishable
    from the station not existing, and the service adding a sixth interval is exactly the change
    that would need a new member in the mapping.
    """
    import logging  # noqa: PLC0415

    import polars as pl  # noqa: PLC0415

    from wetterdienst.provider.wsv.pegel import api  # noqa: PLC0415

    # the reporter remembers what it has already said, for the lifetime of the process
    monkeypatch.setattr(api, "_reported_equidistances", set())
    schema = {"timeseries": pl.List(pl.Struct({"equidistance": pl.Int64}))}
    unmapped = pl.DataFrame({"timeseries": [[{"equidistance": 15}, {"equidistance": 30}]]}, schema=schema)

    caplog.set_level(logging.WARNING)
    api._log_unmapped_equidistances(  # noqa: SLF001
        pl.DataFrame({"timeseries": [[{"equidistance": 15}], []]}, schema=schema),
    )
    assert not caplog.messages, "the five known intervals must not warn"

    api._log_unmapped_equidistances(unmapped)  # noqa: SLF001
    assert len(caplog.messages) == 1
    # only the unknown interval is named; 15 minutes has a resolution and is not a problem
    assert "[30]" in caplog.messages[0]

    # `_all` scans the whole listing on every call, and `filter_by_name`/`filter_by_rank` call it
    # twice, so repeating the warning per request would drown the one that carries the news
    api._log_unmapped_equidistances(unmapped)  # noqa: SLF001
    assert len(caplog.messages) == 1, "an interval already reported must not warn again"


def test_wsv_unmapped_equidistance_is_not_served_under_a_neighbouring_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a timeseries at an unknown interval is skipped rather than mislabelled.

    The station list already omits such a station, so this is the second half of the same rule: a
    caller reaching the values class for it directly -- by station id, say -- must not get a
    30-minute series labelled as one of the five declared resolutions.
    """
    import polars as pl  # noqa: PLC0415

    from wetterdienst.model.result import StationsFilter, StationsResult  # noqa: PLC0415
    from wetterdienst.provider.wsv.pegel import api  # noqa: PLC0415
    from wetterdienst.provider.wsv.pegel.api import TimeseriesMeta, WsvPegelValues  # noqa: PLC0415

    request = WsvPegelRequest(parameters=[("15_minutes", "data", "stage")])
    values = WsvPegelValues(
        sr=StationsResult(
            stations=request,
            df=pl.DataFrame(),
            df_all=pl.DataFrame(),
            stations_filter=StationsFilter.ALL,
        ),
    )
    values._timeseries_meta_cache = {  # noqa: SLF001
        ("1", "W"): TimeseriesMeta(unit="cm", equidistance=30),
        ("2", "W"): TimeseriesMeta(unit="cm", equidistance=60),
    }

    def _fail(**kwargs: object) -> None:
        msg = f"skipped series must not be downloaded: {kwargs['url']}"
        raise AssertionError(msg)

    # the guard has to come before the request, or a skipped series still costs a round trip
    monkeypatch.setattr(api, "download_file", _fail)
    parameter = request.metadata["15_minutes"]["data"]["stage"]
    # 30 minutes maps to no resolution at all, 60 maps to one other than the requested one
    assert values._collect_station_parameter_or_dataset("1", parameter).is_empty()  # noqa: SLF001
    assert values._collect_station_parameter_or_dataset("2", parameter).is_empty()  # noqa: SLF001


def test_wsv_station_list_pairs_each_resolution_with_the_parameters_asked_for_there(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a station qualifies on a requested pair, not on either half of one.

    Matching the requested parameters and the requested resolutions as two independent sets lets a
    station in on a combination nobody asked for. Requesting stage every 15 minutes and air
    temperature hourly used to list the four gauges that record air temperature every 15 minutes
    and no stage at all, purely because `15_minutes` and `LT` were each requested somewhere. Every
    one of them then cost a 404 for a stage series that does not exist and returned nothing.
    """
    from io import BytesIO  # noqa: PLC0415

    from wetterdienst.provider.wsv.pegel import api  # noqa: PLC0415

    def _station(number: str, timeseries: dict[str, int]) -> dict:
        return {
            "number": number,
            "shortname": number,
            "km": 1.0,
            "latitude": 50.0,
            "longitude": 10.0,
            "water": {"shortname": "TEST"},
            "timeseries": [
                {"shortname": shortname, "equidistance": equidistance, "characteristicValues": []}
                for shortname, equidistance in timeseries.items()
            ],
        }

    listing = json.dumps(
        [
            _station("matches-both", {"W": 15, "LT": 60}),
            _station("matches-stage-only", {"W": 15, "LT": 15}),
            _station("matches-neither", {"LT": 15, "WG": 15}),
            _station("stage-at-another-interval", {"W": 1}),
        ],
    ).encode()
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(listing), status=200),
    )

    df = (
        WsvPegelRequest(
            parameters=[("15_minutes", "data", "stage"), ("hourly", "data", "temperature_air_mean_2m")],
        )
        .all()
        .df
    )
    assert sorted(df.select("resolution", "station_id").rows()) == [
        # air temperature at 15 minutes is not the hourly air temperature that was asked for, and
        # stage at one minute is not the 15-minute stage
        ("15_minutes", "matches-both"),
        ("15_minutes", "matches-stage-only"),
        ("hourly", "matches-both"),
    ]
