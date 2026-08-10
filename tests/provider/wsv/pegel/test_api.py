# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for WSV Pegelonline, in particular its per-station source units."""

import pytest

from wetterdienst.provider.wsv.pegel import WsvPegelRequest
from wetterdienst.provider.wsv.pegel.api import _SOURCE_UNIT_FACTORS


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
        request = WsvPegelRequest(parameters=[("dynamic", "data", "wave_height_sign")])
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
        request = WsvPegelRequest(parameters=[("dynamic", "data", "wave_period")])
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
    df = WsvPegelRequest(parameters=[("dynamic", "data", "flow_direction")]).all().values.all().df
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
    stations = WsvPegelRequest(parameters=[("dynamic", "data", "stage")]).filter_by_station_id("27800090")
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
        parameters=[("dynamic", "data", p) for p in ("wave_period", "flow_direction", "wave_height_sign")],
    )
    df = request.filter_by_station_id("9460041").values.all().df
    # flow_direction has no data at this station while the other two do, which is the whole point:
    # the empty one must not take the populated ones down with it
    assert not df.is_empty()
    assert "wave_height_sign" in df.get_column("parameter").unique().to_list()


def test_wsv_source_units_are_not_cached_when_the_listing_is_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a failed station listing is retried rather than remembered as "no units known".

    An empty mapping cached after a transient failure makes every unit lookup miss, which skips
    every scaled parameter for the lifetime of the process -- long after the listing came back.
    """
    from io import BytesIO  # noqa: PLC0415

    import polars as pl  # noqa: PLC0415

    from wetterdienst.model.result import StationsFilter, StationsResult  # noqa: PLC0415
    from wetterdienst.provider.wsv.pegel import api  # noqa: PLC0415
    from wetterdienst.provider.wsv.pegel.api import WsvPegelValues  # noqa: PLC0415
    from wetterdienst.util.network import File, NoInternetError  # noqa: PLC0415

    # deliberately not `.all()`: that eagerly downloads the 1.2 MB station listing, which would
    # make this a network test in all but the marker
    request = WsvPegelRequest(parameters=[("dynamic", "data", "stage")])
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
    assert values._source_units(settings) == {}  # noqa: SLF001
    assert values._source_units_cache is None, "a failed listing must not be cached"  # noqa: SLF001

    listing = b'[{"number": "1", "timeseries": [{"shortname": "W", "unit": "cm"}]}]'
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(listing), status=200),
    )
    assert values._source_units(settings) == {("1", "W"): "cm"}  # noqa: SLF001
