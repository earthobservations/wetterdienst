# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Acquire information about the data fields from DWD."""

import logging
from pprint import pprint

from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)

log = logging.getLogger()


def fields_example() -> None:
    """Print DWD field examples for one specification."""
    # Output in JSON format.
    # import json; print(json.dumps(metadata.describe_fields(), indent=4))  # noqa: ERA001

    # Output in YAML format.
    # import yaml; print(yaml.dump(dict(metadata.describe_fields()), default_style="|"))  # noqa: ERA001

    # Output in pretty-print format.
    pprint(
        DwdObservationRequest.describe_fields(
            dataset=("daily", "climate_summary"),
            period="recent",
            language="en",
        ),
    )

    pprint(
        DwdObservationRequest.describe_fields(
            dataset=("daily", "climate_summary"),
            period="recent",
            language="de",
        ),
    )


def main() -> None:
    """Run example."""
    logging.basicConfig(level=logging.INFO)
    fields_example()


if __name__ == "__main__":
    main()
