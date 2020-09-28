import logging
from functools import lru_cache
from io import BytesIO

import requests
from requests.adapters import HTTPAdapter

from wetterdienst.dwd.metadata.constants import DWD_SERVER


logger = logging.getLogger(__name__)


def download_file_from_dwd(url: str) -> BytesIO:
    """
    A function used to download a specified file from the server.

    :param url:     The url to the file on the dwd server

    :return:        Bytes of the file.
    """
    dwd_session = create_dwd_session()

    logger.info(f"Downloading resource {url}")
    r = dwd_session.get(url)
    r.raise_for_status()

    return BytesIO(r.content)


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

    dwd_session.mount(DWD_SERVER, HTTPAdapter(max_retries=MAX_RETRIES))

    return dwd_session
