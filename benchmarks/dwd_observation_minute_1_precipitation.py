# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Benchmark the DWD observation 1-minute precipitation path, from the bytes of a file to the values.

``1_minute/precipitation`` is the largest and most dataframe-bound thing the library reads: one
station holds about two million rows of recent data, the files are zipped CSV, and the historical
files carry a dedicated transform that turns event ranges into one row per minute. A change in
polars shows up here before it does anywhere else.

The network is kept out of the measurement. ``--fetch`` downloads a fixed set of files once into a
local directory; every timed stage reads only from there, so the numbers come from polars and this
library, not from the server of DWD::

    uv run python -m benchmarks.dwd_observation_minute_1_precipitation --fetch --scale small
    uv run python -m benchmarks.dwd_observation_minute_1_precipitation --scale small
    uv run --with 'polars==1.43.2' python -m benchmarks.dwd_observation_minute_1_precipitation

Four stages are timed apart, each in a process of its own so that the peak resident memory is
that of the stage, its warm-up and the loading of the modules and files, not of the other stages
(``--in-process`` shares one process and reports no peak; Windows has none to report):

- ``parse``: ``parse_climate_observations_data`` on the recent product files, collected.
- ``historical``: the same on the historical (monthly) product files, which adds the transform from
  event ranges to one row per minute.
- ``values_long`` and ``values_wide``: ``DwdObservationRequest(...).filter_by_station_id(...).values.all()``
  on the cached recent files, with the unit conversion on, in both shapes. Only the discovery of the
  stations and files and the download are replaced by the local files; unpacking the zip is timed.

Each stage runs ``--warmup`` times, then ``--runs`` times. The result is written as one JSON file
(``--output``) with the polars, Python and platform in its header, and a table goes to stdout.
It is not a gate: nothing here fails on a slow run.
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import platform
import statistics
import subprocess
import sys
import time
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError

import polars as pl

from wetterdienst import Period, Settings
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.observation import DwdObservationMetadata, DwdObservationRequest
from wetterdienst.provider.dwd.observation import api as dwd_observation_api
from wetterdienst.provider.dwd.observation.download import _unpack_climate_observations_data
from wetterdienst.provider.dwd.observation.parser import parse_climate_observations_data
from wetterdienst.util.network import File

try:
    import resource
except ImportError:  # Windows
    resource = None

if TYPE_CHECKING:
    from collections.abc import Callable

BASE_URL = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/1_minute/precipitation"
"""Root of the 1-minute precipitation files on the open data server of DWD."""

HISTORICAL_YEAR = 2022
"""The year of the historical files of the manifest: twelve monthly files per station."""

MANIFEST: dict[str, tuple[str, ...]] = {
    # one station: about two million rows of recent data, plus a year of historical files
    "small": ("00044",),
    # ten stations
    "large": ("00020", "00029", "00044", "00046", "00053", "00073", "00078", "00087", "00091", "00096"),
}
"""The stations of each scale. The files are the recent archive and the twelve monthly historical ones."""

STAGES = ("parse", "historical", "values_long", "values_wide")

DEFAULT_CACHE_DIR = Path(__file__).parent / ".cache" / "dwd_observation_minute_1_precipitation"
DATASET = DwdObservationMetadata.minute_1.precipitation
DEFAULT_ENGINE = "in-memory"
"""The engine the library collects with, and the benchmark unless ``--engine`` says otherwise."""


def _recent_name(station_id: str) -> str:
    return f"1minutenwerte_nieder_{station_id}_akt.zip"


def _historical_names(station_id: str) -> list[str]:
    """Give the monthly historical file names of a station for the year of the manifest."""
    names = []
    for month in range(1, 13):
        last_day = calendar.monthrange(HISTORICAL_YEAR, month)[1]
        start = f"{HISTORICAL_YEAR}{month:02d}01"
        end = f"{HISTORICAL_YEAR}{month:02d}{last_day:02d}"
        names.append(f"1minutenwerte_nieder_{station_id}_{start}_{end}_hist.zip")
    return names


def fetch(cache_dir: Path, stations: tuple[str, ...]) -> None:
    """Download the files of the manifest that are not in the cache directory yet."""
    for station_id in stations:
        targets = [("recent", _recent_name(station_id))] + [
            ("historical", name) for name in _historical_names(station_id)
        ]
        for period, name in targets:
            path = cache_dir / period / name
            if path.exists():
                continue
            url = (
                f"{BASE_URL}/{period}/{name}" if period == "recent" else f"{BASE_URL}/{period}/{HISTORICAL_YEAR}/{name}"
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310
                    payload = response.read()
            except HTTPError as e:
                print(f"skipped {url}: {e}", file=sys.stderr)
                continue
            path.write_bytes(payload)
            print(f"fetched {url} ({len(payload) / 1e6:.1f} MB)", file=sys.stderr)


def _cached(cache_dir: Path, period: str, stations: tuple[str, ...]) -> list[Path]:
    """Give the cached zip files of a period and the stations, in a fixed order."""
    paths = []
    for station_id in stations:
        pattern = f"1minutenwerte_nieder_{station_id}_*.zip"
        paths.extend(sorted((cache_dir / period).glob(pattern)))
    if not paths:
        msg = f"no cached {period} files in {cache_dir}: run with --fetch first"
        raise SystemExit(msg)
    return paths


def _products(paths: list[Path]) -> list[File]:
    """Unpack the product file of each zip, as the download step does, outside of any timing."""
    return [
        _unpack_climate_observations_data(File(url=path.as_uri(), content=BytesIO(path.read_bytes()), status=200))
        for path in paths
    ]


def _fresh(files: list[File]) -> list[File]:
    """Copy the files: the parser reads their bytes, and a file is read once."""
    return [File(url=file.url, content=BytesIO(file.content.getvalue()), status=200) for file in files]  # ty: ignore[unresolved-attribute]


def _values(cache_dir: Path, stations: tuple[str, ...], shape: str) -> pl.DataFrame:
    """Run the request on the cached recent files. Only the lookup of stations and files and the download are local."""
    paths = {path.name: path for path in _cached(cache_dir, "recent", stations)}
    original = (
        dwd_observation_api.create_file_list_for_climate_observations,
        dwd_observation_api.download_climate_observations_data,
    )

    def download(remote_files: pl.Series, _settings: Settings) -> list[File]:
        return [
            _unpack_climate_observations_data(
                File(url=url, content=BytesIO(paths[Path(url).name].read_bytes()), status=200),
            )
            for url in remote_files.to_list()
        ]

    def file_list(station_id: str, *_args: Any, **_kwargs: Any) -> pl.Series:  # noqa: ANN401
        return pl.Series([f"file:///{_recent_name(station_id)}"])

    dwd_observation_api.create_file_list_for_climate_observations = file_list
    dwd_observation_api.download_climate_observations_data = download
    try:
        settings = Settings(cache_disable=True, ts_shape=shape, ts_convert_units=True)
        request = DwdObservationRequest(
            parameters=[("minute_1", "precipitation")], periods={Period.RECENT}, settings=settings
        )
        return _stations_result(request, stations).values.all().df
    finally:
        (
            dwd_observation_api.create_file_list_for_climate_observations,
            dwd_observation_api.download_climate_observations_data,
        ) = original


def _stations_result(request: DwdObservationRequest, station_ids: tuple[str, ...]) -> Any:  # noqa: ANN401
    """Stand a station up rather than look it up: the catalogue is a network step this benchmark leaves out."""
    height = len(station_ids)
    df = pl.DataFrame(
        {
            "resolution": ["1_minute"] * height,
            "dataset": ["precipitation"] * height,
            "station_id": list(station_ids),
            "start_timestamp": [None] * height,
            "end_timestamp": [None] * height,
            "latitude": [50.0] * height,
            "longitude": [10.0] * height,
            "elevation": [100.0] * height,
            "name": ["Benchmark"] * height,
        },
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
        },
    )
    return StationsResult(stations=request, df=df, df_all=df, stations_filter=StationsFilter.BY_STATION_ID)


def _stage(name: str, cache_dir: Path, stations: tuple[str, ...], engine: str) -> Callable[[], int]:
    """Give the function of a stage, which returns the number of rows it made."""
    if name in ("parse", "historical"):
        period, parser_period = ("recent", Period.RECENT) if name == "parse" else ("historical", Period.HISTORICAL)
        products = _products(_cached(cache_dir, period, stations))

        def parse() -> int:
            return (
                parse_climate_observations_data(_fresh(products), DATASET, parser_period).collect(engine=engine).height
            )

        return parse
    shape = "long" if name == "values_long" else "wide"

    def values() -> int:
        return _values(cache_dir, stations, shape).height

    return values


def _measure(
    name: str, cache_dir: Path, stations: tuple[str, ...], runs: int, warmup: int, engine: str, *, isolated: bool
) -> dict[str, Any]:
    """Time a stage and read the peak resident memory of this process afterwards."""
    run = _stage(name, cache_dir, stations, engine)
    for _ in range(warmup):
        run()
    seconds = []
    rows = 0
    for _ in range(runs):
        start = time.perf_counter()
        rows = run()
        seconds.append(time.perf_counter() - start)
    peak_mb = None
    if isolated and resource is not None:
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # macOS reports bytes, Linux kilobytes
        peak_mb = peak / 1e6 if sys.platform == "darwin" else peak / 1e3
    median = statistics.median(seconds)
    return {
        "stage": name,
        "rows": rows,
        "runs": runs,
        "median_s": median,
        "min_s": min(seconds),
        "max_s": max(seconds),
        "rows_per_s": rows / median if median else None,
        "peak_rss_mb": peak_mb,
    }


def _header() -> dict[str, Any]:
    return {
        "polars": pl.__version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
    }


def peak(result: dict[str, Any]) -> str:
    """Format the peak memory of a stage, or n/a where there is none."""
    return "n/a" if result["peak_rss_mb"] is None else f"{result['peak_rss_mb']:.0f}"


def _table(header: dict[str, Any], results: list[dict[str, Any]]) -> str:
    lines = [
        (
            f"polars {header['polars']} (engine {header['engine_affinity']}) / Python {header['python']} / "
            f"{header['platform']} / {header['cpu_count']} cpus"
        ),
        f"{'stage':<14}{'rows':>12}{'median s':>10}{'min s':>9}{'max s':>9}{'rows/s':>14}{'peak MB':>10}",
    ]
    lines.extend(
        f"{r['stage']:<14}{r['rows']:>12,}{r['median_s']:>10.3f}{r['min_s']:>9.3f}{r['max_s']:>9.3f}"
        f"{r['rows_per_s']:>14,.0f}{peak(r):>10}"
        for r in results
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    """Run the benchmark: fetch if asked, then time the stages and write the JSON."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--scale", choices=sorted(MANIFEST), default="small")
    parser.add_argument("--stations", nargs="+", help="Station ids instead of those of the scale.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--fetch", action="store_true", help="Download the files of the manifest, then exit.")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--stage", choices=STAGES, action="append", help="Only this stage (repeatable).")
    parser.add_argument(
        "--engine",
        choices=["in-memory", "streaming", "auto"],
        default=DEFAULT_ENGINE,
        help=(
            "The engine of the collects and the engine affinity of polars. The default is the in-memory engine, "
            "which is what polars 1 uses and what the library asks for. The values stages go through "
            "DwdObservationValues, which names the in-memory engine itself, so only parse and historical follow this."
        ),
    )
    parser.add_argument("--output", type=Path, help="Write the JSON here.")
    parser.add_argument("--in-process", action="store_true", help="Run the stages in this process, not one each.")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.cache_dir = args.cache_dir.resolve()
    stations = tuple(args.stations or MANIFEST[args.scale])
    pl.Config.set_engine_affinity(args.engine)
    if args.fetch:
        fetch(args.cache_dir, stations)
        return {}
    stages = args.stage or list(STAGES)
    if args.child:
        print(
            json.dumps(
                _measure(stages[0], args.cache_dir, stations, args.runs, args.warmup, args.engine, isolated=True)
            )
        )
        return {}
    results = []
    for name in stages:
        if args.in_process:
            results.append(
                _measure(name, args.cache_dir, stations, args.runs, args.warmup, args.engine, isolated=False)
            )
            continue
        command = [
            sys.executable,
            "-m",
            __spec__.name if __spec__ else "benchmarks.dwd_observation_minute_1_precipitation",
            "--child",
            "--stage",
            name,
            "--cache-dir",
            str(args.cache_dir),
            "--runs",
            str(args.runs),
            "--warmup",
            str(args.warmup),
            "--engine",
            args.engine,
            "--stations",
            *stations,
        ]
        completed = subprocess.run(command, check=True, stdout=subprocess.PIPE, text=True)  # noqa: S603
        results.append(json.loads(completed.stdout.strip().splitlines()[-1]))
    header = {**_header(), "engine_affinity": args.engine}
    report = {"header": header, "scale": args.scale, "stations": list(stations), "stages": results}
    if args.output:
        args.output.write_text(json.dumps(report, indent=2))
    print(_table(header, results))
    return report


if __name__ == "__main__":
    main()
