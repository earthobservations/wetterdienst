# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Example for DWD MOSMIX acquisition.

This program will request latest MOSMIX-L data for stations 01001 and 01008 and parameters DD and ww.
Other MOSMIX variants are also listed and can be enabled on demand.
"""

import polars as pl

from wetterdienst import Settings
from wetterdienst.provider.dwd.mosmix import (
    DwdForecastDate,
    DwdMosmixRequest,
)
from wetterdienst.util.cli import setup_logging


def mosmix_example() -> None:
    """Retrieve Mosmix mosmix data by DWD."""
    # A. MOSMIX-L -- Specific stations - each station with own file
    settings = Settings(ts_shape="wide", ts_humanize=True)

    request = DwdMosmixRequest(
        parameters=[("hourly", "large", "DD"), ("hourly", "large", "ww")],
        issue=DwdForecastDate.LATEST,  # automatically set if left empty
        settings=settings,
    )

    stations = request.filter_by_station_id(
        station_id=["01001", "01008"],
    )

    response = next(stations.values.query())

    # meta data enriched with information from metadata_for_forecasts()
    output_section("Metadata", response.stations.df)
    output_section("Forecasts", response.df)

    # B. MOSMIX-L -- All stations - specified stations are extracted.
    Settings.tidy = True
    Settings.humanize = True

    request = DwdMosmixRequest(
        parameters=[("hourly", "large", "DD"), ("hourly", "large", "ww")],
        issue=DwdForecastDate.LATEST,  # automatically set if left empty
        station_group="all_stations",
    )

    stations = request.filter_by_station_id(
        station_id=["01001", "01008"],
    )

    response = next(stations.values.query())

    # meta data enriched with information from metadata_for_forecasts()
    output_section("Metadata", response.stations.df)
    output_section("Forecasts", response.df)

    # C. MOSMIX-S -- All stations - specified stations are extracted.

    request = DwdMosmixRequest(
        parameters=[("hourly", "small", "DD"), ("hourly", "small", "ww")],
        issue=DwdForecastDate.LATEST,  # automatically set if left empty
    )

    stations = request.filter_by_station_id(
        station_id=["01001", "01008"],
    )

    response = next(stations.values.query())

    output_section("Metadata", response.stations.df)
    output_section("Forecasts", response.df)


def output_section(title: str, data: pl.DataFrame) -> None:  # pragma: no cover
    """Output section."""
    print("-" * len(title))
    print(title)
    print("-" * len(title))
    print(data)
    print()


def main() -> None:
    """Run example."""
    setup_logging()
    mosmix_example()


if __name__ == "__main__":
    main()
