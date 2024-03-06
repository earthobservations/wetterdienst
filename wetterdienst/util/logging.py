# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import io
import logging


class TqdmToLogger(io.StringIO):
    """
    Output stream for TQDM which will output to logger module instead of
    the StdOut.

    Source: https://stackoverflow.com/questions/14897756/python-progress-bar-through-logging-module
    """

    logger = None
    level = None
    buf = ""

    def __init__(self, logger, level=None):
        super().__init__()
        self.logger = logger
        self.level = level or logging.INFO

    def write(self, buf):
        self.buf = buf.strip("\r\n\t ")

    def flush(self):
        self.logger.log(self.level, self.buf)
