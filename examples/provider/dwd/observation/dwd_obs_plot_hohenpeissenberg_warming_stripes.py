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
    else ROOT / "docs" / "img" / "hohenpeissenberg_warming_stripes.png"
)


def plot_hohenpeissenberg_warming_stripes() -> None:
    """Create warming stripes for Potsdam.

    Source: https://matplotlib.org/matplotblog/posts/warming-stripes/
    """
    fig = _plot_stripes(
        kind="temperature",
        name="Hohenpeissenberg",
    )

    if SAVE_PLOT:
        fig.write_image(file=PLOT_PATH)
    elif "PYTEST_CURRENT_TEST" not in os.environ:
        fig.show()


def main() -> None:
    """Run example."""
    plot_hohenpeissenberg_warming_stripes()


if __name__ == "__main__":
    main()
