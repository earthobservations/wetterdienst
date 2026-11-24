# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the geometry of an ODIM sweep file has to be (GH-4399).

DWD extended the range of the precipitation scan from 150 km to 180 km on 24 November 2026: 720 bins of 250 m a
ray instead of 600. At the five sites looked at (BOO, ASB, FLD, NHB, TUR) the last file with 600 bins is the scan of
09:15 UTC and the first with 720 that of 09:20; the latest file of all 17 sites has 720. A file of the day before
holds 600, one of the day after 720, and a request for "yesterday" or "the last hour" returns either. So a test does
not pin the bins: it holds the file to what the file itself states.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from h5py import File

# The azimuths of a sweep: one ray a degree (`angle_step`), 360 of them. A scan has been seen to lack up to four, so
# 356 to 361 are held, the range the tests have always held.
SWEEP_RAYS = (356, 361)
# The length of a bin in m: 250 m for every sweep of DWD ("Horizontale Auflösung: 1° x 250 m", the sheet of the
# precipitation scan). A range of 100 m to 1 km is a sweep of a radar, not another product.
SWEEP_BIN_LENGTH = (100.0, 1000.0)
# The bins of a ray: 240 (60 km) of the highest elevation of the volume scan to 720 (180 km) of the precipitation
# scan since 24 November 2026; 600 (150 km) before.
SWEEP_BINS = (100, 1500)
# The range of a sweep in m, `how/range` of its dataset: from 60 km to 180 km at DWD.
SWEEP_RANGE = (50_000.0, 300_000.0)
# The ranges the precipitation scan has had, in m: 150 km until 24 November 2026, 09:15 UTC, 180 km after (see above).
PRECIPITATION_SCAN_RANGES = (150_000.0, 180_000.0)


def assert_sweep_geometry(f: File, quantity: bytes, ranges: tuple[float, ...] | None = None) -> tuple[int, int]:
    """Assert that the first dataset of a sweep is a polar array that its own metadata describes, and return its shape.

    The array has `nrays` rows and `nbins` columns (`dataset1/where`), as many rays as `startazA` and `stopazA`
    (`dataset1/how`) hold azimuths, and the range of the dataset (`how/range`) is its bins times their length
    (`rscale`): a truncated or mixed-up file, or a reader that returns another array, fails one of these. The values
    have to be in the sanity ranges above, which do not move when DWD extends a scan, and the quantity is the one the
    request asked for. `ranges` are the ranges in m that the scan has had, where a test knows them: a precipitation
    scan is one of 150 or 180 km, whichever of the two the day of the file was.
    """
    where = f["dataset1/where"].attrs
    how = f["dataset1/how"].attrs
    data = f["dataset1/data1/data"]

    nrays = int(where["nrays"])
    nbins = int(where["nbins"])
    rscale = float(where["rscale"])

    assert data.shape == (nrays, nbins), "the array is not the one the file describes"
    assert len(how["startazA"]) == len(how["stopazA"]) == nrays
    assert SWEEP_RAYS[0] <= nrays <= SWEEP_RAYS[1]
    assert SWEEP_BINS[0] <= nbins <= SWEEP_BINS[1]
    assert SWEEP_BIN_LENGTH[0] <= rscale <= SWEEP_BIN_LENGTH[1]
    assert float(how["range"]) == nbins * rscale
    assert SWEEP_RANGE[0] <= float(how["range"]) <= SWEEP_RANGE[1]
    if ranges is not None:
        assert float(how["range"]) in ranges

    assert f["dataset1/data1/what"].attrs["quantity"] == quantity
    return data.shape
