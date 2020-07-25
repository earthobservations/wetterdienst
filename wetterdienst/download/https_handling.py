from functools import lru_cache
import requests
from requests.adapters import HTTPAdapter

from wetterdienst.constants.access_credentials import HTTPS_EXPRESSION

MAX_RETRIES = 3


@lru_cache(maxsize=None)
def create_dwd_session() -> requests.Session:
    """
    Function used to create a global session that is used for listing/downloading data
    from the DWD server.

    Returns:
        requests.Session object that then can be used for requests to the server
    """
    dwd_session = requests.Session()

    dwd_session.mount(HTTPS_EXPRESSION, HTTPAdapter(max_retries=MAX_RETRIES))

    return dwd_session
