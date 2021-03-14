# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====
Acquire information about the data fields from DWD.

"""
import logging
from pprint import pprint

from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)

log = logging.getLogger()


def fields_example():
    # Output in JSON format.
    # import json; print(json.dumps(metadata.describe_fields(), indent=4))

    # Output in YAML format.
    # import yaml; print(yaml.dump(dict(metadata.describe_fields()), default_style="|"))

    # Output in pretty-print format.
    pprint(
        DwdObservationRequest.describe_fields(
            dataset=DwdObservationDataset.CLIMATE_SUMMARY,
            resolution=DwdObservationResolution.DAILY,
            period=DwdObservationPeriod.RECENT,
            language="en",
        )
    )

    pprint(
        DwdObservationRequest.describe_fields(
            dataset=DwdObservationDataset.CLIMATE_SUMMARY,
            resolution=DwdObservationResolution.DAILY,
            period=DwdObservationPeriod.RECENT,
            language="de",
        )
    )


def main():
    logging.basicConfig(level=logging.INFO)
    fields_example()


if __name__ == "__main__":
    main()
