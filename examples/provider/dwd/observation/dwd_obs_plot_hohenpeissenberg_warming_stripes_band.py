# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Draw the slim warming stripes band of the README: Hohenpeißenberg, 800 x 100 px at scale 2.

The command line (``wetterdienst stripes image``) and the REST API draw the same stripes with
their own margins and a source line, at a size of their own, and take no width or height. There is
no public way to the bare band, so this example takes the figure they are made of
(``wetterdienst.ui.core._plot_stripes``, private, it may change) and strips the annotations and
the margins. It needs the ``plotting`` extra.

Set ``SAVE_PLOT`` to write the image to ``docs/assets/readme-stripes.png``, where the README takes
it from. A test runs the example without writing it.
"""

from pathlib import Path

from wetterdienst.ui.core import StripesImageRequest, _plot_stripes

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
    fig = _plot_stripes(request)
    # the source line and the other annotations, then the margins and the background
    fig.layout.annotations = ()
    fig.update_layout(
        width=WIDTH,
        height=HEIGHT,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig.to_image("png", scale=SCALE)


def main() -> None:
    """Run example."""
    png = draw_band()
    if SAVE_PLOT:
        PLOT_PATH.write_bytes(png)


if __name__ == "__main__":
    main()
