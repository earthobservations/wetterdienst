# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import os
from pathlib import Path

import xarray as xr
import zarr
from tqdm import tqdm

from wetterdienst.provider.dwd.observation import DwdObservationRequest

ROOT = Path(__file__).parent.parent


def create_dwd_climate_summary_zarr_dump(filepath, test):
    request = DwdObservationRequest(
        parameters=("daily", "climate_summary"),
        periods="historical",
    ).all()
    meta = request.df
    store = zarr.DirectoryStore(filepath)
    data = []
    for result in tqdm(request.values.query(), total=meta.shape[0]):
        df = result.df.drop("quality").to_pandas()
        df.date = df.date.map(lambda date: date.to_datetime64())
        df = df.set_index(["station_id", "dataset", "parameter", "date"])
        ds = df.to_xarray()
        data.append(ds)
        if test:
            break
    ds = xr.concat(data, dim="station_id")
    ds.to_zarr(store, mode="w")


def main():
    filepath = ROOT / "dwd_obs_climate_summary.zarr"
    test = "PYTEST_CURRENT_TEST" in os.environ
    # this takes something like 15 min and will require roughly 1 gb on disk
    create_dwd_climate_summary_zarr_dump(filepath, test)
    ds = xr.open_zarr(filepath)
    print(ds)


if __name__ == "__main__":
    main()
