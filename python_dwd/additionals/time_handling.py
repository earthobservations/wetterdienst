""" date time handling functions """
from typing import Union
import pandas as pd
from pandas._libs.tslibs.timestamps import Timestamp


def parse_date(date_string) -> Union[None, pd.Timestamp]:
    """
    
    Args:
        date_string: 

    Returns:

    """
    date = Timestamp(date_string)

    if pd.isna(date):
        return None

    return date
