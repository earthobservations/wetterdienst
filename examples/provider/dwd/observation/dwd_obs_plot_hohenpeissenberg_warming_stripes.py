# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Plot warming stripes for Hohenpeißenberg.

One stripe per year of the mean air temperature, drawn with the Altair chart that the climate stripes of
the command line (``wetterdienst stripes image``) and of the REST API are made of. The chart is
shown in a browser, unless the example runs as a test. It needs the ``plotting`` extra. See
``dwd_obs_plot_hohenpeissenberg_warming_stripes_band.py`` for the slim band of the README.
"""

import os

from wetterdienst.ui.core import StripesImageRequest, _plot_stripes


def plot_hohenpeissenberg_warming_stripes() -> None:
    """Create warming stripes for Hohenpeißenberg."""
    request = StripesImageRequest(
        kind="temperature",
        name="Hohenpeissenberg",
        # bare stripes: no title, no years and no availability line
        show_title=False,
        show_years=False,
        show_data_availability=False,
    )
    chart = _plot_stripes(request)

    if "PYTEST_CURRENT_TEST" not in os.environ:
        chart.show()


def main() -> None:
    """Run example."""
    plot_hohenpeissenberg_warming_stripes()


if __name__ == "__main__":
    main()
