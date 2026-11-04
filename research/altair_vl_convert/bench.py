"""Time and memory of one chart, rendered by one engine, in one fresh process (GH-3238).

    python research/altair_vl_convert/bench.py --engine altair --chart stripes --fmt png --n 30

The inputs are read through the library from DWD's open data before anything is timed. One JSON line comes out:

- `import_s`: importing the engine's libraries (`altair` and `vl_convert`, `plotly`, `matplotlib`);
- `first_s`: the first image of the process, which is the cold start: it builds the chart and starts what the
  engine needs (V8 for vl-convert, a Chrome for Kaleido); `server_start_s` is the call that starts the Chrome of
  `plotly-server`, which may return before the Chrome is up, in which case `first_s` pays the rest;
- `median_s`, `p95_s`, `min_s`, `max_s`, `mean_s` over the `n` renders after it, chart building included, as a
  REST request pays it. The run stops early once it has spent `--budget` seconds, and says how many it did (`n`);
- `peak_rss_mb`: the largest resident set of the process and every process it started (the Chrome and its helpers,
  for Kaleido), sampled every 20 ms, and `baseline_rss_mb`, the same before the first image. Shared pages are
  counted once per process, so the sum is an upper bound;
- `bytes`: the size of the last image.

`--engine plotly` draws as the library does, which is a Chrome started and stopped per image; `--engine
plotly-server` keeps one Chrome up, as `tests/conftest.py` does for the image tests (GH-3250).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
from pathlib import Path

import psutil

CHARTS = {
    "stripes": lambda d: d.stripes(),
    "stations": lambda d: d.stations(),
    "values-month": lambda d: d.values(
        start="2025-12-01", end="2025-12-31", station_ids=("00433", "00403"), parameters=2
    ),
    "values-year": lambda d: d.values(start="2025-01-01", end="2025-12-31"),
    "values-10y": lambda d: d.values(start="2016-01-01", end="2025-12-31"),
}


class PeakRss:
    """Sample the resident set of this process and its descendants, and keep the largest sum."""

    def __init__(self, interval: float = 0.02) -> None:
        self.interval = interval
        self.peak = 0
        self._stop = threading.Event()
        self._process = psutil.Process()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def current(self) -> int:
        total = 0
        for process in [self._process, *self._process.children(recursive=True)]:
            try:
                total += process.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return total

    def _run(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, self.current())
            self._stop.wait(self.interval)

    def __enter__(self) -> PeakRss:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, choices=["altair", "matplotlib", "plotly", "plotly-server"])
    parser.add_argument("--chart", required=True, choices=list(CHARTS))
    parser.add_argument("--fmt", default="png", choices=["png", "jpg", "svg", "pdf", "html"])
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--basemap", type=Path, default=None, help="GeoJSON of country polygons for the station map")
    parser.add_argument("--budget", type=float, default=300.0, help="seconds after which no further render starts")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from research.altair_vl_convert import data  # noqa: PLC0415
    from research.altair_vl_convert.prototype import to_image  # noqa: PLC0415

    subject = CHARTS[args.chart](data)
    rows = len(subject.data.df if args.chart == "stripes" else subject.df)
    engine = "plotly" if args.engine.startswith("plotly") else args.engine
    # read and cut once, outside the timing: the file is 3 MB of JSON
    from research.altair_vl_convert.prototype import _features  # noqa: PLC0415

    basemap = _features(subject, args.basemap)

    started = time.perf_counter()
    if engine == "altair":
        import altair  # noqa: F401, PLC0415
        import vl_convert  # noqa: F401, PLC0415
    elif engine == "matplotlib":
        import matplotlib  # noqa: F401, PLC0415
        import matplotlib.pyplot  # noqa: F401, PLC0415
    else:
        import kaleido  # noqa: PLC0415
        import plotly.graph_objects  # noqa: F401, PLC0415

    import_s = time.perf_counter() - started
    server_s = 0.0
    if args.engine == "plotly-server":
        t = time.perf_counter()
        kaleido.start_sync_server(silence_warnings=True)
        server_s = time.perf_counter() - t

    def render() -> bytes | str:
        return to_image(subject, engine=engine, fmt=args.fmt, scale=args.scale, basemap=basemap)  # ty: ignore[invalid-argument-type]

    load_before = os.getloadavg()[0]
    times: list[float] = []
    with PeakRss() as peak:
        baseline = peak.current()
        t = time.perf_counter()
        out = render()
        first_s = time.perf_counter() - t
        begun = time.perf_counter()
        for _ in range(args.n):
            if time.perf_counter() - begun > args.budget and len(times) >= 5:
                break
            t = time.perf_counter()
            out = render()
            times.append(time.perf_counter() - t)
    if args.engine == "plotly-server":
        kaleido.stop_sync_server(silence_warnings=True)
    times.sort()
    result = {
        "engine": args.engine,
        "chart": args.chart,
        "fmt": args.fmt,
        "scale": args.scale,
        "rows": rows,
        "n": len(times),
        "import_s": round(import_s, 3),
        "server_start_s": round(server_s, 3),
        "first_s": round(first_s, 3),
        "median_s": round(statistics.median(times), 3),
        "p95_s": round(times[min(len(times) - 1, round(0.95 * (len(times) - 1) + 0.4999))], 3),
        "min_s": round(times[0], 3),
        "max_s": round(times[-1], 3),
        "mean_s": round(statistics.fmean(times), 3),
        "baseline_rss_mb": round(baseline / 2**20),
        "peak_rss_mb": round(peak.peak / 2**20),
        "bytes": len(out),
        # the machine was shared: a load above the cores' number says the timings are not to be trusted
        "load1_before": round(load_before, 1),
        "load1_after": round(os.getloadavg()[0], 1),
    }
    print(json.dumps(result))  # noqa: T201


if __name__ == "__main__":
    main()
