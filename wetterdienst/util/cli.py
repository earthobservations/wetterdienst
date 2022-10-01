# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
""" A set of utility functions """
import logging
import sys
from typing import List, Optional


def setup_logging(level=logging.INFO) -> None:
    log_format = "%(asctime)-15s [%(name)-32s] %(levelname)-7s: %(message)s"
    logging.basicConfig(format=log_format, stream=sys.stderr, level=level)

    # Silence INFO messages from numexpr.
    numexpr_logger = logging.getLogger("numexpr")
    numexpr_logger.setLevel(logging.WARN)


def read_list(data: Optional[str], separator: str = ",") -> List[str]:
    if data is None:
        return []

    result = [x.strip() for x in data.split(separator)]

    if len(result) == 1 and not result[0]:
        return []

    return result
