""" date time handling functions """
from typing import Optional
import pandas as pd
from pandas import Timestamp


def parse_date(date_string: str) -> Optional[Timestamp]:
    """
    A function used to parse a date from a string.

    Args:
        date_string: the string of the date
    Returns:
        Timestamp of the string or None
    """
    date = Timestamp(date_string)

    if pd.isna(date):
        return None

    return date
