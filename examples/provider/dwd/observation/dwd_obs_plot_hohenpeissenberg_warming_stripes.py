# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Plot warming stripes for Hohenpeissenberg."""

import os
from pathlib import Path

from wetterdienst.ui.core import _plot_stripes

HERE = Path(__file__).parent
ROOT = HERE.parent

SAVE_PLOT = False
SAVE_PLOT_HERE = True
PLOT_PATH = (
    HERE / "hohenpeissenberg_warming_stripes.png"
    if SAVE_PLOT_HERE
    else ROOT.parent.parent.parent / "docs" / "assets" / "hohenpeissenberg_warming_stripes.png"
)


def plot_hohenpeissenberg_warming_stripes() -> None:
    """Create warming stripes for Potsdam.

    Source: https://matplotlib.org/matplotblog/posts/warming-stripes/
    """
    fig = _plot_stripes(
        kind="temperature",
        name="Hohenpeissenberg",
        # bare stripes: this is the README's header image, where a title and an axis would only
        # repeat the sentence above it
        show_title=False,
        show_years=False,
        show_data_availability=False,
    )
    fig.update_layout(margin={"l": 0, "r": 0, "t": 0, "b": 0})

    if SAVE_PLOT:
        # 3200x1600: wide enough to read a single year as its own stripe, square enough not to
        # look like a rule across the page
        fig.write_image(file=PLOT_PATH, width=1600, height=800, scale=2)
    elif "PYTEST_CURRENT_TEST" not in os.environ:
        fig.show()


def main() -> None:
    """Run example."""
    plot_hohenpeissenberg_warming_stripes()


if __name__ == "__main__":
    main()
