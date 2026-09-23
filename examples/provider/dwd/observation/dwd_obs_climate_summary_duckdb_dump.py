# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Create a DuckDB dump of DWD climate summary data."""

import os
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
from tqdm import tqdm

from wetterdienst.provider.dwd.observation import DwdObservationRequest

ROOT = Path(__file__).parent.parent


def duckdb_target(path: Path, table: str) -> str:
    r"""Address a table in a DuckDB file, as ``to_target`` wants it.

    Three slashes, not four: ``ConnectionString`` takes the database as the URL path with one
    leading slash removed, so the path has to arrive with exactly one slash of its own in front of
    it. A POSIX path brings that itself (``duckdb:///`` + ``/tmp/x`` reads back as ``/tmp/x``),
    where a Windows one does not (``duckdb:///`` + ``C:\x`` reads back as ``C:\x``). A fourth
    slash left the POSIX form with a harmless doubled ``//``, and the Windows form with a leading
    slash that DuckDB reads as a UNC network path: ``Cannot open file "//C:\..."``.

    Named rather than written inline so that a test can hold it: the wrong slash count is silent on
    POSIX, so nothing that runs the example here would catch it coming back.
    """
    return f"duckdb:///{path}?table={table}"


def create_dwd_climate_summary_duckdb_dump(path: Path, *, test: bool) -> None:
    """Create a DuckDB dump of DWD climate summary data."""
    request = DwdObservationRequest(
        parameters=("daily", "climate_summary"),
        periods="historical",
    ).filter_by_rank(latlon=(47.5, 7.5), rank=10)
    request.to_target(duckdb_target(path, "stations"))
    for result in tqdm(request.values.query(), total=request.df.shape[0]):
        result.to_target(duckdb_target(path, "values"))
        if test:
            break


def main() -> None:
    """Create a DuckDB dump of DWD climate summary data."""
    test = "PYTEST_CURRENT_TEST" in os.environ
    with ExitStack() as stack:
        if test:
            # somewhere that is not the repository. Under pytest this is a smoke test rather than
            # an artifact -- it writes one station's values and throws them away -- and writing to
            # the tracked dump left every test run with a dirty working tree, which has twice been
            # committed by accident along with unrelated work
            filepath = Path(stack.enter_context(TemporaryDirectory())) / "dwd_obs_daily_climate_summary.duckdb"
        else:
            filepath = ROOT / "dwd_obs_daily_climate_summary.duckdb"
        # this takes something like 15 min and will require roughly 1 gb on disk
        create_dwd_climate_summary_duckdb_dump(filepath, test=test)
        con = duckdb.connect(str(filepath))
        df_stations = con.execute("SELECT * FROM stations;").pl()
        print(df_stations)
        df_values = con.execute("SELECT * FROM values").pl()
        print(df_values)
        con.close()


if __name__ == "__main__":
    main()
