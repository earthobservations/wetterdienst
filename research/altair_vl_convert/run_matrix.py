"""Run `bench.py` for every engine and chart, one fresh process each, and append its JSON line to a file (GH-3238).

    python research/altair_vl_convert/run_matrix.py OUT.jsonl [--basemap FILE] [--only group]

The groups: `png` (every chart, 700 px), `dpi300` (the stripes at the 300 dpi the CLI and REST default to),
`formats` (svg, pdf and jpg of two charts).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ENGINES = ["altair", "matplotlib", "plotly", "plotly-server"]
CHARTS = ["stripes", "stations", "values-month", "values-year", "values-10y"]


def jobs(group: str) -> list[list[str]]:
    """Return the arguments of `bench.py` that make up a group."""
    if group == "png":
        return [["--engine", e, "--chart", c] for c in CHARTS for e in ENGINES]
    if group == "dpi300":
        return [["--engine", e, "--chart", "stripes", "--scale", "3"] for e in ENGINES]
    if group == "formats":
        return [
            ["--engine", e, "--chart", c, "--fmt", fmt]
            for c in ("stripes", "values-month")
            for fmt in ("svg", "pdf", "jpg")
            for e in ENGINES
            if e != "plotly"
        ]
    msg = f"unknown group {group}"
    raise SystemExit(msg)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--basemap", type=Path, default=None)
    parser.add_argument("--only", default=None)
    args = parser.parse_args()
    bench = str(Path(__file__).with_name("bench.py"))
    for group in [args.only] if args.only else ["png", "dpi300", "formats"]:
        for job in jobs(group):
            cmd = [sys.executable, bench, *job]
            if args.basemap:
                cmd += ["--basemap", str(args.basemap)]
            print(" ".join(job), flush=True)  # noqa: T201
            run = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
            line = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else ""
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                record = {"failed": job, "stderr": run.stderr[-800:]}
            with args.out.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"group": group, **record}) + "\n")


if __name__ == "__main__":
    main()
