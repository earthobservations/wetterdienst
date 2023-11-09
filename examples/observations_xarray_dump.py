# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import xarray as xr
import zarr
from tqdm import tqdm

from wetterdienst.provider.dwd.observation import DwdObservationRequest


def create_dwd_kl_zarr_dump(path):
    request = DwdObservationRequest(
        "kl",
        "daily",
        "historical",
    ).all()

    meta = request.df
    store = zarr.DirectoryStore(path)

    data = []

    for result in tqdm(request.values.query(), total=meta.shape[0]):
        df = result.df
        df[["station_id", "dataset", "parameter"]] = df[["station_id", "dataset", "parameter"]].astype(str)
        df.date = df.date.map(lambda date: date.to_datetime64())
        df = df.set_index(["station_id", "dataset", "parameter", "date"], inplace=False).drop(
            columns=["quality"]
        )  # "latitude", "longitude",
        ds = df.to_xarray()
        data.append(ds)
        data.append(df.to_xarray())

    ds = xr.concat(data, dim="station_id")
    ds.to_zarr(store, mode="w")


def main():
    # this takes something like 15 min and will require roughly 1 gb on disk
    create_dwd_kl_zarr_dump("dwd_kl.zarr")


if __name__ == "__main__":
    main()
