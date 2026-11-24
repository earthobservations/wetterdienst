# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The check of the geometry of a sweep file that the remote tests share holds what it should (GH-4399)."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import pytest

from tests.provider.dwd.radar.sweep import PRECIPITATION_SCAN_RANGES, assert_sweep_geometry

if TYPE_CHECKING:
    from collections.abc import Callable

np = pytest.importorskip("numpy", reason="numpy not installed")
h5py = pytest.importorskip("h5py", reason="h5py not installed")


def sweep(
    *,
    nrays: int = 360,
    nbins: int = 720,
    rscale: float = 250.0,
    shape: tuple[int, int] | None = None,
    range_m: float | None = None,
    rays: int | None = None,
    quantity: bytes = b"VRADH",
) -> h5py.File:
    """Build a sweep as DWD writes it (the attributes of `sweep_pcp_v` of BOO), with the geometry that is asked for."""
    f = h5py.File(BytesIO(), "w")
    dataset = f.create_group("dataset1")
    dataset.create_group("where").attrs.update({"nrays": nrays, "nbins": nbins, "rscale": rscale, "rstart": 0.0})
    azimuths = np.linspace(0.0, 359.0, rays if rays is not None else nrays)
    dataset.create_group("how").attrs.update(
        {
            "range": nbins * rscale if range_m is None else range_m,
            "startazA": azimuths,
            "stopazA": azimuths + 1.0,
        },
    )
    data = dataset.create_group("data1")
    data.create_group("what").attrs["quantity"] = np.bytes_(quantity)
    data.create_dataset("data", shape=shape or (nrays, nbins), dtype="uint16")
    return f


@pytest.mark.parametrize(
    ("nbins", "range_m"),
    [(600, 150_000.0), (720, 180_000.0)],
    ids=["until 2026-11-24 09:15 UTC: 150 km", "since 2026-11-24 09:20 UTC: 180 km"],
)
def test_precipitation_scan_of_either_range(nbins: int, range_m: float) -> None:
    """The bins follow the file: the scan before and the scan after the extension of 24 November 2026 are both held."""
    f = sweep(nbins=nbins)
    assert float(f["dataset1/how"].attrs["range"]) == range_m
    assert assert_sweep_geometry(f, b"VRADH", PRECIPITATION_SCAN_RANGES) == (360, nbins)


@pytest.mark.parametrize("nrays", [356, 358, 359, 360, 361])
def test_azimuths_in_the_known_range(nrays: int) -> None:
    """A scan of 356 to 361 rays, as DWD has delivered them, is held."""
    assert assert_sweep_geometry(sweep(nrays=nrays), b"VRADH")[0] == nrays


def test_volume_scan_without_the_range_of_the_precipitation_scan() -> None:
    """The highest elevation of the volume scan (240 bins) is a sweep, but not a precipitation scan."""
    f = sweep(nbins=240)
    assert assert_sweep_geometry(f, b"VRADH") == (360, 240)
    with pytest.raises(AssertionError):
        assert_sweep_geometry(f, b"VRADH", PRECIPITATION_SCAN_RANGES)


@pytest.mark.parametrize(
    "broken",
    [
        pytest.param(lambda: sweep(shape=(360, 600)), id="an array that is not the one nbins says (truncated)"),
        pytest.param(lambda: sweep(shape=(359, 720)), id="an array that is not the one nrays says"),
        pytest.param(lambda: sweep(range_m=150_000.0), id="a range that is not the bins times their length"),
        pytest.param(lambda: sweep(rays=359), id="fewer azimuths than rays"),
        pytest.param(lambda: sweep(nrays=300), id="far too few rays"),
        pytest.param(lambda: sweep(nbins=5000), id="far too many bins"),
        pytest.param(lambda: sweep(nbins=50), id="far too few bins"),
        pytest.param(lambda: sweep(rscale=1.0, nbins=720), id="a bin of a metre"),
        pytest.param(lambda: sweep(rscale=5000.0, nbins=100), id="a bin of 5 km"),
        pytest.param(lambda: sweep(quantity=b"DBZH"), id="the reflectivity where the velocity was asked for"),
    ],
)
def test_broken_sweep_fails(broken: Callable[[], h5py.File]) -> None:
    """A file that its own metadata contradicts, or that is no sweep of a radar, is no precipitation scan."""
    with pytest.raises(AssertionError):
        assert_sweep_geometry(broken(), b"VRADH", PRECIPITATION_SCAN_RANGES)


def test_range_of_neither_precipitation_scan() -> None:
    """A sweep of 200 km is a sweep, which a range of the precipitation scan only holds if DWD said it was."""
    f = sweep(nbins=800)
    assert assert_sweep_geometry(f, b"VRADH") == (360, 800)
    with pytest.raises(AssertionError):
        assert_sweep_geometry(f, b"VRADH", PRECIPITATION_SCAN_RANGES)
