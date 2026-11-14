# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Draw the slim warming stripes band of the README: Hohenpeißenberg, 800 x 100 px at scale 2.

The command line (``wetterdienst stripes image``) and the REST API draw the same stripes with
their own margins and a source line, at a size of their own, and take no width or height. There is
no public way to the bare band, so this example takes the data and the chart they are made of
(``wetterdienst.ui.core._get_stripes_data`` and ``wetterdienst.io.charts.stripes_chart``, private,
they may change) and leaves out the text, the margins and the background. It needs the ``plotting``
extra.

Set ``SAVE_PLOT`` to write the image to ``docs/assets/readme-stripes.png``, where the README takes
it from. A test runs the example without writing it.
"""

from pathlib import Path

from wetterdienst.io.charts import stripes_chart
from wetterdienst.io.export import render_image
from wetterdienst.ui.core import CLIMATE_STRIPES_CONFIG, StripesImageRequest, _get_stripes_data

HERE = Path(__file__).parent
PLOT_PATH = HERE.parents[3] / "docs" / "assets" / "readme-stripes.png"
SAVE_PLOT = False

WIDTH = 800
HEIGHT = 100
SCALE = 2


def draw_band() -> bytes:
    """Draw the stripes of Hohenpeißenberg (DWD station 2290) as a PNG of ``WIDTH * SCALE`` x ``HEIGHT * SCALE``."""
    request = StripesImageRequest(
        kind="temperature",
        station="2290",
        show_title=False,
        show_years=False,
        show_data_availability=False,
    )
    data = _get_stripes_data(request)
    # no source line and no other text, no margins and no background
    chart = stripes_chart(
        data.df,
        colors=CLIMATE_STRIPES_CONFIG["temperature"]["colors"],
        title=None,
        source=None,
        show_years=False,
        show_data_availability=False,
        padding=0,
        background="transparent",
    )
    return render_image(chart, "png", width=WIDTH, height=HEIGHT, scale=SCALE)


def main() -> None:
    """Run example."""
    png = draw_band()
    if SAVE_PLOT:
        PLOT_PATH.write_bytes(png)


if __name__ == "__main__":
    main()
