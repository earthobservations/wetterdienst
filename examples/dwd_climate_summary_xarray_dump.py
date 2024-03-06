# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import os
from pathlib import Path

import xarray as xr
import zarr
from tqdm import tqdm

from wetterdienst.provider.dwd.observation import DwdObservationRequest

ROOT = Path(__file__).parent.parent


def create_dwd_climate_summary_zarr_dump(path):
    request = DwdObservationRequest(
        "kl",
        "daily",
        "historical",
    ).all()
    meta = request.df
    store = zarr.DirectoryStore(path)
    data = []
    for result in tqdm(request.values.query(), total=meta.shape[0]):
        df = result.df.drop("quality").to_pandas()
        df.date = df.date.map(lambda date: date.to_datetime64())
        df = df.set_index(["station_id", "dataset", "parameter", "date"])
        ds = df.to_xarray()
        data.append(ds)
        if "PYTEST_CURRENT_TEST" in os.environ:
            break
    ds = xr.concat(data, dim="station_id")
    if "PYTEST_CURRENT_TEST" not in os.environ:
        ds.to_zarr(store, mode="w")


def main():
    # this takes something like 15 min and will require roughly 1 gb on disk
    create_dwd_climate_summary_zarr_dump(ROOT / "dwd_climate_summary.zarr")


if __name__ == "__main__":
    main()
