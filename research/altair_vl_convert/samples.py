"""Draw the three charts with the three engines side by side, as small PNG files (GH-3238).

    python research/altair_vl_convert/samples.py OUT_DIR [--basemap FILE]

One file per chart and engine, `<chart>-<engine>.png`, each reduced to a palette of 16 to 128 colors so that
the nine of them are under 200 KB together. The Plotly station map is drawn with a zoom that fits the stations
(`fit_plotly_zoom`): the zoom the library sets crops them out of the picture (see the pull request).
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--basemap", type=Path, default=None)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from research.altair_vl_convert import data  # noqa: PLC0415
    from research.altair_vl_convert.prototype import to_image  # noqa: PLC0415

    subjects = {
        "stripes": data.stripes(),
        "stations": data.stations(),
        "values": data.values(start="2025-12-01", end="2025-12-31", station_ids=("00433", "00403"), parameters=2),
    }
    # the stripes are a few flat colours and need many shades; the map and the lines need few
    colors = {"stripes": 128, "stations": 16, "values": 16}
    args.out.mkdir(parents=True, exist_ok=True)
    for chart, subject in subjects.items():
        for engine in ("plotly", "altair", "matplotlib"):
            png = to_image(subject, engine=engine, fmt="png", basemap=args.basemap, fit_plotly_zoom=True)  # ty: ignore[invalid-argument-type]
            image = Image.open(io.BytesIO(png)).convert("RGB").quantize(colors[chart], method=Image.Quantize.MEDIANCUT)
            path = args.out / f"{chart}-{engine}.png"
            image.save(path, optimize=True)
            print(path, path.stat().st_size // 1024, "KiB")  # noqa: T201


if __name__ == "__main__":
    main()
