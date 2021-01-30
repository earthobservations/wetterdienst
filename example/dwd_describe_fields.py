# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE.rst for more info.
"""
=====
About
=====
Acquire information about the data fields from DWD.

"""
import logging
from pprint import pprint

from wetterdienst.dwd.observations import (
    DWDObservationMetadata,
    DWDObservationParameterSet,
    DWDObservationPeriod,
    DWDObservationResolution,
)

log = logging.getLogger()


def fields_example():

    metadata = DWDObservationMetadata(
        parameter_set=DWDObservationParameterSet.CLIMATE_SUMMARY,
        resolution=DWDObservationResolution.DAILY,
        period=DWDObservationPeriod.RECENT,
    )

    # Output in JSON format.
    # import json; print(json.dumps(metadata.describe_fields(), indent=4))

    # Output in YAML format.
    # import yaml; print(yaml.dump(dict(metadata.describe_fields()), default_style="|"))

    # Output in pretty-print format.
    pprint(dict(metadata.describe_fields(language="en")))
    pprint(dict(metadata.describe_fields(language="de")))


def main():
    logging.basicConfig(level=logging.INFO)
    fields_example()


if __name__ == "__main__":
    main()
