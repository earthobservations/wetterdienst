# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import os
from pathlib import Path

import duckdb
from tqdm import tqdm

from wetterdienst.provider.dwd.observation import DwdObservationRequest

ROOT = Path(__file__).parent.parent


def create_dwd_climate_summary_duckdb_dump(path, test):
    request = DwdObservationRequest(
        parameters=("daily", "climate_summary"),
        periods="historical",
    ).filter_by_rank(latlon=(47.5, 7.5), rank=10)
    connection = f"duckdb:////{path}"
    request.to_target(f"{connection}?table=stations")
    for result in tqdm(request.values.query(), total=request.df.shape[0]):
        result.to_target(f"{connection}?table=values")
        if test:
            break


def main():
    filepath = ROOT / "dwd_obs_daily_climate_summary.duckdb"
    test = "PYTEST_CURRENT_TEST" in os.environ
    # this takes something like 15 min and will require roughly 1 gb on disk
    create_dwd_climate_summary_duckdb_dump(filepath, test=test)
    con = duckdb.connect(str(filepath))
    df_stations = con.execute("SELECT * FROM stations;").pl()
    print(df_stations)
    df_values = con.execute("SELECT * FROM values").pl()
    print(df_values)


if __name__ == "__main__":
    main()
