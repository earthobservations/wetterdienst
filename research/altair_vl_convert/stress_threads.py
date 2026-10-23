"""Render from many threads at once, as a long-running REST process does, and check what comes out (GH-3238).

    python research/altair_vl_convert/stress_threads.py --engine altair --threads 8 --per-thread 25

FastAPI runs a `def` route in a pool of 40 threads, so every image the REST API answers is drawn from a thread of a
process that stays up. Three charts of different data are drawn over and over by `--threads` threads, a round of
`--per-thread` images each, in a mixed order. The answer to each is compared with the one a single thread drew of
the same chart before (byte for byte, for PNG and SVG), which catches an image handed to the wrong caller, and the
run reports:

- `mismatches`: images that are not the one a single thread draws of that chart (0 is the answer a server needs);
- `errors`: exceptions, with the first;
- `wall_s` and `images_per_s` against `single_images_per_s`, which says whether the engine draws in parallel;
- `rss_start_mb`, `rss_end_mb` of this process (plus the Chrome of Kaleido), which a leak would raise.

`--engine plotly-server` starts the one Chrome `tests/conftest.py` starts for the image tests, *without* the lock
that fixture puts around `calc_fig_sync`, and `--lock` puts it back: the fixture's docstring says that two renders at
once can swap their images, and this is the measurement of it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psutil

STATIONS = ("02290", "03987", "01048")


def rss_mb() -> int:
    """Return the resident set of this process and its descendants, in MiB."""
    process = psutil.Process()
    total = 0
    for each in [process, *process.children(recursive=True)]:
        try:
            total += each.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total // 2**20


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, choices=["altair", "matplotlib", "plotly", "plotly-server"])
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--per-thread", type=int, default=25)
    parser.add_argument("--fmt", default="png", choices=["png", "svg"])
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument(
        "--lock", action="store_true", help="plotly-server: call kaleido under a lock, as conftest does"
    )
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from research.altair_vl_convert import data  # noqa: PLC0415
    from research.altair_vl_convert.prototype import to_image  # noqa: PLC0415

    engine = "plotly" if args.engine.startswith("plotly") else args.engine
    subjects = [data.stripes(station=station) for station in STATIONS]
    if args.engine == "plotly-server":
        import kaleido  # noqa: PLC0415

        kaleido.start_sync_server(silence_warnings=True)
        if args.lock:
            lock, calc = threading.Lock(), kaleido.calc_fig_sync

            def one_at_a_time(*a: object, **k: object) -> object:
                with lock:
                    return calc(*a, **k)

            kaleido.calc_fig_sync = one_at_a_time

    def render(index: int) -> bytes | str:
        return to_image(subjects[index], engine=engine, fmt=args.fmt, scale=args.scale)  # ty: ignore[invalid-argument-type]

    def digest(image: bytes | str) -> str:
        return hashlib.sha256(image if isinstance(image, bytes) else image.encode()).hexdigest()[:16]

    # a single thread first: the expected image of each chart, the same twice (else there is nothing to compare to),
    # and how many images a second one thread draws
    expected = [digest(render(i)) for i in range(len(subjects))]
    repeat = [digest(render(i)) for i in range(len(subjects))]
    deterministic = expected == repeat
    n_single = max(6, args.per_thread // 2)
    t = time.perf_counter()
    for k in range(n_single):
        render(k % len(subjects))
    single_rate = n_single / (time.perf_counter() - t)

    rss_start = rss_mb()
    plan = [
        [random.Random(thread).randrange(len(subjects)) for _ in range(args.per_thread)]
        for thread in range(args.threads)
    ]
    mismatches: list[tuple[int, int]] = []
    errors: list[str] = []

    def work(thread: int) -> None:
        for index in plan[thread]:
            try:
                if digest(render(index)) != expected[index]:
                    mismatches.append((thread, index))
            except Exception as error:  # noqa: BLE001
                errors.append(f"{type(error).__name__}: {str(error)[:200]}")

    started = time.perf_counter()
    with ThreadPoolExecutor(args.threads) as pool:
        list(pool.map(work, range(args.threads)))
    wall = time.perf_counter() - started
    total = args.threads * args.per_thread
    print(  # noqa: T201
        json.dumps(
            {
                "engine": args.engine + ("+lock" if args.lock else ""),
                "fmt": args.fmt,
                "threads": args.threads,
                "images": total,
                "deterministic_single_thread": deterministic,
                "mismatches": len(mismatches),
                "errors": len(errors),
                "first_error": errors[0] if errors else None,
                "wall_s": round(wall, 2),
                "images_per_s": round(total / wall, 2),
                "single_images_per_s": round(single_rate, 2),
                "rss_start_mb": rss_start,
                "rss_end_mb": rss_mb(),
            }
        )
    )
    if args.engine == "plotly-server":
        kaleido.stop_sync_server(silence_warnings=True)


if __name__ == "__main__":
    main()
