# Copyright (c) 2018-2023 earthobservations
import os
from pathlib import Path

from matplotlib import pyplot as plt
from PIL import Image

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

plt.style.use("ggplot")


def plot_hohenpeissenberg_warming_stripes():
    """Create warming stripes for Potsdam
    Source: https://matplotlib.org/matplotblog/posts/warming-stripes/
    """
    buf = _plot_stripes(
        kind="temperature",
        name="Hohenpeissenberg",
        fmt="png",
    )

    image = Image.open(buf, formats=["png"])
    plt.imshow(image)
    plt.axis("off")

    if SAVE_PLOT:
        plt.savefig(PLOT_PATH, dpi=100, bbox_inches="tight")
    elif "PYTEST_CURRENT_TEST" not in os.environ:
        plt.show()


def main():
    plot_hohenpeissenberg_warming_stripes()


if __name__ == "__main__":
    main()
