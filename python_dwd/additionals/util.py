""" A set of utility functions """
import sys
import logging

from docopt import docopt
from munch import Munch, munchify


def setup_logging(level=logging.INFO):
    log_format = '%(asctime)-15s [%(name)-30s] %(levelname)-7s: %(message)s'
    logging.basicConfig(
        format=log_format,
        stream=sys.stderr,
        level=level)

    # Silence INFO messages from numexpr.
    numexpr_logger = logging.getLogger('numexpr')
    numexpr_logger.setLevel(logging.WARN)


def normalize_options(options):
    normalized = {}
    for key, value in options.items():

        # Add primary variant.
        key = key.strip('--<>')
        normalized[key] = value

        # Add secondary variant.
        key = key.replace('-', '_')
        normalized[key] = value

    return munchify(normalized, factory=OptionMunch)


def read_list(data, separator=u','):
    if data is None:
        return []
    result = list(map(lambda x: x.strip(), data.split(separator)))
    if len(result) == 1 and not result[0]:
        result = []
    return result


class OptionMunch(Munch):

    def __setattr__(self, k, v):
        super().__setattr__(k.replace('-', '_'), v)
        super().__setattr__(k.replace('_', '-'), v)
