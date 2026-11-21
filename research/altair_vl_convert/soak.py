"""Render one chart many times in one process, printing the resident set every 100 images (GH-3238).

    python research/altair_vl_convert/soak.py --engine altair --n 1000

A leak shows as a slope.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import psutil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, choices=["altair", "matplotlib"])
    parser.add_argument("--n", type=int, default=1000)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from research.altair_vl_convert import data  # noqa: PLC0415
    from research.altair_vl_convert.prototype import to_image  # noqa: PLC0415

    stripes = data.stripes()
    process = psutil.Process()
    started = time.perf_counter()
    for i in range(1, args.n + 1):
        to_image(stripes, engine=args.engine, fmt="png")
        if i % 100 == 0 or i == 1:
            print(
                f"after {i:5d} images: rss {process.memory_info().rss // 2**20} MiB, {time.perf_counter() - started:.0f} s"
            )  # noqa: T201


if __name__ == "__main__":
    main()
