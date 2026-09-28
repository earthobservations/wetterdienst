# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Create a Zarr dump of DWD climate summary data."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import xarray as xr
from tqdm import tqdm

from wetterdienst.provider.dwd.observation import DwdObservationRequest

ZARR_OUTPUT_PATH = Path(__file__).parent / "dwd_obs_climate_summary.zarr"


def create_dwd_climate_summary_zarr_dump(filepath: Path, *, test: bool) -> None:
    """Create a Zarr dump of DWD climate summary data."""
    request = DwdObservationRequest(
        parameters=("daily", "climate_summary"),
        periods="historical",
    ).all()
    meta = request.df
    data = []
    for result in tqdm(request.values.query(), total=meta.shape[0]):
        df = result.df.drop("quality").to_pandas()
        df["timestamp"] = df["timestamp"].map(lambda timestamp: timestamp.to_datetime64())
        df = df.set_index(["station_id", "dataset", "parameter", "timestamp"])
        ds = df.to_xarray()
        data.append(ds)
        if test:
            break
    ds = xr.concat(data, dim="station_id")
    ds.to_zarr(filepath, mode="w")


def main() -> None:
    """Create a Zarr dump of DWD climate summary data."""
    test = "PYTEST_CURRENT_TEST" in os.environ
    if test:
        # somewhere that is not the repository: under pytest this is a smoke test that writes one
        # station and throws it away, as the DuckDB example does (GH-2044)
        with TemporaryDirectory() as directory:
            filepath = Path(directory) / ZARR_OUTPUT_PATH.name
            create_dwd_climate_summary_zarr_dump(filepath=filepath, test=test)
            # closed before the directory is removed, which Windows will not do under an open store
            with xr.open_zarr(filepath) as ds:
                print(ds)
        return
    # this takes something like 15 min and will require roughly 1 gb on disk
    create_dwd_climate_summary_zarr_dump(filepath=ZARR_OUTPUT_PATH, test=test)
    ds = xr.open_zarr(ZARR_OUTPUT_PATH)
    print(ds)


if __name__ == "__main__":
    main()
